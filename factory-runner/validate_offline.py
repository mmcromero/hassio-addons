#!/usr/bin/env python3
"""Run trusted offline tests with no inherited credentials; retain exact logs."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    root=Path(__file__).resolve().parent
    output=args.output.absolute()
    output.mkdir(mode=0o700,parents=True,exist_ok=False)
    env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C.UTF-8',
         'PYTHONPYCACHEPREFIX':str(output/'pycache')}
    suites=[('addon',[sys.executable,'-m','unittest','discover','-s',str(root/'tests'),'-p','test_factory_runner_*.py','-v'])]
    if (root.parent/'tests/test_worker_dev.py').is_file():
        suites.append(('repository',[sys.executable,'-m','unittest','discover','-s',str(root.parent/'tests'),'-v']))
    results=[]
    for name,argv in suites:
        with (output/(name+'.log')).open('wb') as stream:
            result=subprocess.run(argv,cwd=root.parent,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=240,check=False)
        results.append({'suite':name,'command':argv,'exit_code':result.returncode})
    files={path.relative_to(root).as_posix():hashlib.sha256(path.read_bytes()).hexdigest()
           for path in sorted(root.rglob('*')) if path.is_file() and not path.is_symlink()
           and '__pycache__' not in path.parts and (path.suffix in ('.py','.json','.yaml') or path.name=='Dockerfile')}
    report={'python':sys.version.split()[0],'suites':results,'file_sha256':files,
            'production_credentials_inherited':False,'published':False}
    (output/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'results':results,'artifact':str(output/'validation.json')}))
    return int(any(result['exit_code'] for result in results))


if __name__=='__main__':raise SystemExit(main())
