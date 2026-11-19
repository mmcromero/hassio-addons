#!/usr/bin/env python3
"""Isolated authenticated container smoke. No host ports, real data or secrets.

Optional BuildKit user-mode QEMU runs without registering host binfmt. This
is emulation evidence, never Home Assistant/hardware homologation.
"""
import argparse
import json
from pathlib import Path
import secrets
import subprocess
import tempfile
import uuid

CLIENT = r'''
import http.client,json,pathlib,platform,time
options=pathlib.Path('/data/options.json')
token=json.loads(options.read_text())['runner_auth_token']
def request(method,path,authorized=True,payload=None):
 c=http.client.HTTPConnection('127.0.0.1',9876,timeout=3)
 headers={'Content-Type':'application/json'}
 if authorized: headers['Authorization']='Bearer '+token
 c.request(method,path,body=json.dumps(payload or {'project':'avisaqui','expected_source_sha':'a'*40}) if method=='POST' else None,headers=headers)
 response=c.getresponse();value=(response.status,json.loads(response.read()));c.close();return value
deadline=time.monotonic()+30
while True:
 try:
  assert request('GET','/api/status',False)[0]==401
  break
 except (ConnectionError,OSError):
  if time.monotonic()>deadline:raise
  time.sleep(.2)
for method,path in [('GET','/api/status'),('GET','/api/projects'),('POST','/api/preflight'),('POST','/api/prepare')]:
 assert request(method,path,False)[0]==401
status,data=request('GET','/api/status');assert status==200 and data['publication']=='disabled'
status,data=request('GET','/api/projects');assert status==200 and any(p['id']=='avisaqui' for p in data['projects'])
for path in ['/api/preflight','/api/prepare']:assert request('POST',path)[0]==503
for path in ['/api/fechar-pacote','/api/corrigir-issue']:assert request('POST',path,payload={'issue':2})[0]==403
assert not pathlib.Path('/app/tests').exists()
assert not pathlib.Path('/run/secrets/build_ca').exists()
audit=pathlib.Path('/data/factory-runner/audit.jsonl')
assert token not in audit.read_text()
assert audit.stat().st_mode&0o777==0o600
print(json.dumps({'result':'PASS','machine':platform.machine(),'unauthenticated':401,'status':200,'projects':200,'missing_workspace':503,'legacy_operations':403,'audit_rows':len(audit.read_text().splitlines()),'audit_sanitized':True,'runtime_tests_absent':True}))
'''

def command(args, timeout=60):
    proc=subprocess.run(args,capture_output=True,text=True,timeout=timeout)
    if proc.returncode:
        # Never dump container environment/options or arbitrary subprocess output.
        raise RuntimeError('Container smoke command failed: '+args[0]+' exit '+str(proc.returncode))
    return proc.stdout

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',required=True)
    parser.add_argument('--platform',choices=['linux/amd64','linux/arm64'],required=True)
    parser.add_argument('--emulator',type=Path)
    args=parser.parse_args()
    name='factory-runner-smoke-'+uuid.uuid4().hex[:12]
    image=json.loads(command(['docker','image','inspect',args.image]))[0]
    assert image['Os']+'/'+image['Architecture']==args.platform
    cgroups=command(['docker','info','--format','{{.CgroupDriver}}']).strip()!='none'
    with tempfile.TemporaryDirectory(prefix='factory-runner-smoke-') as folder:
        data=Path(folder)
        options=data/'options.json'
        options.write_text(json.dumps({'runner_auth_token':secrets.token_urlsafe(48)}))
        options.chmod(0o600)
        argv=['docker','run','-d','--name',name,'--platform',args.platform,
              '--network','none',
              '--read-only','--tmpfs','/tmp:rw,nosuid,size=64m',
              '--mount','type=bind,source='+str(data)+',target=/data']
        prefix=[]
        if cgroups:argv+=['--cpus','1','--memory','256m','--pids-limit','128']
        if args.emulator:
            emulator=args.emulator.resolve(strict=True)
            argv+=['--mount','type=bind,source='+str(emulator)+',target=/.buildkit_qemu_emulator,readonly',
                   '--entrypoint','/.buildkit_qemu_emulator']
            prefix=['/.buildkit_qemu_emulator']
        argv+=[args.image]
        if args.emulator:argv+=['/bin/bash','/app/run.sh']
        try:
            command(argv)
            inspect=json.loads(command(['docker','inspect',name]))[0]
            assert not any((inspect['NetworkSettings'].get('Ports') or {}).values())
            previous_rows=0
            for phase in ('startup','restart'):
                if phase=='restart':command(['docker','restart',name])
                result=command(['docker','exec',name,*prefix,'/usr/bin/python3','-c',CLIENT])
                observed=json.loads(result)
                assert observed['machine']==('aarch64' if args.platform=='linux/arm64' else 'x86_64')
                assert observed['audit_rows']>previous_rows
                previous_rows=observed['audit_rows']
                print(phase+' '+result.strip(),flush=True)
            metadata={'image':image['Id'],'architecture':args.platform,
                'emulation':bool(args.emulator),'host_ports':False,
                'cgroup_limits_available':cgroups,
                'cpu_limit':1 if cgroups else None,
                'memory_limit_bytes':268435456 if cgroups else None,
                'pids_limit':128 if cgroups else None,
                'result':'PASS'}
        finally:
            try:
                # Rootless Docker may map created files to another host UID.
                # Remove only this smoke's synthetic data through its own container.
                command(['docker','exec',name,*prefix,'/usr/bin/python3','-c',
                    "from pathlib import Path;import shutil;p=Path('/data/factory-runner');shutil.rmtree(p) if p.exists() else None"])
            finally:
                subprocess.run(['docker','rm','-f',name],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,timeout=30)
    print(json.dumps(metadata),flush=True)

if __name__=='__main__':
    main()
