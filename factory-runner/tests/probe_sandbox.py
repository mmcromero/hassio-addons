#!/usr/bin/env python3
"""Real non-root sandbox probe. Exit 2 means unavailable, never PASS/skipped.

Synthetic files only; no host settings, credentials or external network used.
"""
import argparse
import errno
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import time

SCRIPT = r'''
import errno,json,os,pathlib,resource,signal,socket,time
root=pathlib.Path('/target');inputs=json.loads(pathlib.Path('/source/input.json').read_text())
mode=inputs.get('mode','normal')
(root/'entered').write_text('synthetic')
if mode=='cpu':
 while True:pass
if mode=='elapsed':time.sleep(10)
if mode=='aggregate':
 for n in range(80):(root/str(n)).write_bytes(b'x'*32768)
 raise SystemExit(0)
result={'uid_nonroot':os.geteuid()!=0,'environment_clean':not os.environ.get('RUNNER_AUTH_TOKEN')}
result['namespaces']={kind:os.readlink('/proc/self/ns/'+kind)!=value for kind,value in inputs['namespaces'].items()}
try:pathlib.Path(inputs['private_path']).read_text();result['private_file_hidden']=False
except OSError:result['private_file_hidden']=True
result['ha_options_hidden']=not pathlib.Path('/data/options.json').exists()
try:pathlib.Path('/source/forbidden-write').write_text('x');result['source_readonly']=False
except OSError:result['source_readonly']=True
try:pathlib.Path('/target/.git/config').write_text('must not change');result['git_metadata_readonly']=False
except OSError:result['git_metadata_readonly']=True
sock=socket.socket();sock.settimeout(1)
try:sock.connect(('127.0.0.1',inputs['port']));result['host_loopback_blocked']=False
except OSError:result['host_loopback_blocked']=True
finally:sock.close()
status=pathlib.Path('/proc/self/status').read_text().splitlines()
result['capabilities_dropped']=int(next(s.split(':')[1].strip() for s in status if s.startswith('CapEff:')),16)==0
result['limits']={name:resource.getrlimit(getattr(resource,name))[1] for name in ['RLIMIT_CPU','RLIMIT_AS','RLIMIT_FSIZE','RLIMIT_NPROC','RLIMIT_NOFILE','RLIMIT_CORE']}
try:allocation=bytearray(256*1024*1024);result['memory_limit_enforced']=False
except MemoryError:result['memory_limit_enforced']=True
signal.signal(signal.SIGXFSZ,signal.SIG_IGN)
file=root/'size-test'
try:
 with file.open('wb') as stream:
  for n in range(3):stream.write(b'x'*(1024*1024))
 result['file_size_limit_enforced']=False
except OSError as error:result['file_size_limit_enforced']=error.errno==errno.EFBIG
finally:
 if file.exists():file.unlink()
temporary=pathlib.Path('/tmp/fill');temporary.mkdir()
try:
 for n in range(40):(temporary/str(n)).write_bytes(b'x'*(1024*1024))
 result['tmpfs_limit_enforced']=False
except OSError as error:result['tmpfs_limit_enforced']=error.errno==errno.ENOSPC
finally:
 for entry in temporary.iterdir():entry.unlink()
 temporary.rmdir()
# One UID, bounded attempts, own descendants only. No root exemption allowed.
pids=[];blocked=False
try:
 for n in range(40):
  try:pid=os.fork()
  except OSError as error:blocked=error.errno==errno.EAGAIN;break
  if pid==0:time.sleep(10);os._exit(0)
  pids.append(pid)
finally:
 for pid in pids:
  try:os.kill(pid,signal.SIGKILL)
  except ProcessLookupError:pass
 for pid in pids:os.waitpid(pid,0)
result['process_limit_enforced']=blocked and len(pids)<32
result['forked_children']=len(pids)
(root/'proof.json').write_text(json.dumps(result))
'''

def probe(module):
    report={'uid':os.geteuid(),'state':'IMPEDIDO','checks_executed':False}
    report['ha_options_readable']=os.access('/data/options.json',os.R_OK)
    if os.geteuid()==0:
        report['reason']='Probe must run as non-root (container: docker exec --user runner)'
        return report
    if report['ha_options_readable']:
        report.update(state='FAIL',reason='Service UID can read private HA options')
        return report
    with tempfile.TemporaryDirectory(prefix='factory-sandbox-probe-') as folder:
        root=Path(folder);source=root/'source';source.mkdir();target=root/'target';target.mkdir()
        (target/'.git').mkdir();(target/'.git/config').write_text('synthetic metadata')
        private=root/'private-marker';private.write_text('synthetic-only-not-a-real-secret')
        listener=socket.socket();listener.bind(('127.0.0.1',0));listener.listen(1)
        try:
            inputs={'private_path':str(private),'port':listener.getsockname()[1],
                    'namespaces':{k:os.readlink('/proc/self/ns/'+k) for k in ('user','pid','net')}}
            (source/'input.json').write_text(json.dumps(inputs));(source/'probe.py').write_text(SCRIPT)
            def run(destination,mode='normal',cpu=2,elapsed=8):
                inputs['mode']=mode;(source/'input.json').write_text(json.dumps(inputs))
                module.sandbox_export(source=source,target=destination,script='probe.py',sha='a'*40,
                    verify=False,env={'PATH':os.environ.get('PATH',''),'RUNNER_AUTH_TOKEN':'synthetic-marker'},
                    max_output_bytes=1024*1024,memory_bytes=128*1024*1024,
                    cpu_seconds=cpu,elapsed_seconds=elapsed)
            try:run(target)
            except module.SandboxUnavailable as error:
                report['reason']=str(error);return report
            proof=json.loads((target/'proof.json').read_text())
            expected=['uid_nonroot','environment_clean','private_file_hidden','ha_options_hidden',
                'source_readonly','git_metadata_readonly','host_loopback_blocked','capabilities_dropped',
                'memory_limit_enforced','file_size_limit_enforced','tmpfs_limit_enforced','process_limit_enforced']
            assert all(proof[key] for key in expected),proof
            assert all(proof['namespaces'].values()),proof
            bounds={'RLIMIT_CPU':2,'RLIMIT_AS':128*1024*1024,'RLIMIT_FSIZE':1024*1024,
                    'RLIMIT_NPROC':32,'RLIMIT_NOFILE':128,'RLIMIT_CORE':0}
            assert all(proof['limits'][k]<=v for k,v in bounds.items()),proof
            proof['negative_limits']={}
            for mode,cpu,elapsed,reason in [('cpu',1,6,'Sandboxed exporter failed'),
                ('elapsed',2,1,'elapsed-time'),('aggregate',2,8,'aggregate output')]:
                destination=root/mode;destination.mkdir()
                try:run(destination,mode,cpu,elapsed)
                except module.SandboxUnavailable as error:
                    assert reason in str(error),(mode,str(error))
                    assert (destination/'entered').exists(),mode
                    proof['negative_limits'][mode]=True
                else:raise AssertionError('Unenforced '+mode+' limit')
            report.update(state='PASS',checks_executed=True,proof=proof,
                          aggregate_tree_cgroup_verified=False,
                          disk_budget='sampled aggregate monitor, not filesystem quota')
            return report
        finally:listener.close()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--module-dir',type=Path,default=Path(__file__).resolve().parents[1])
    parser.add_argument('--report',type=Path)
    args=parser.parse_args();sys.path.insert(0,str(args.module_dir))
    import sandbox_export
    try:result=probe(sandbox_export)
    except Exception as error:result={'state':'FAIL','reason':type(error).__name__+': '+str(error)}
    text=json.dumps(result,ensure_ascii=False,indent=2)
    if args.report:args.report.write_text(text+'\n');args.report.chmod(0o600)
    print(text)
    return 0 if result['state']=='PASS' else 2 if result['state']=='IMPEDIDO' else 1

if __name__=='__main__':sys.exit(main())
