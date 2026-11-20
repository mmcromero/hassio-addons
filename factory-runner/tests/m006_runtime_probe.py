#!/usr/bin/env python3
"""Container-only synthetic UID/IPC separation proof. Never enrolls a real owner."""
import hashlib
import json
import os
from pathlib import Path
import pwd
import grp
import shutil
import subprocess
import sys
import tempfile
import time
sys.path.insert(0,'/app')
from owner_approval import ApprovalIssuer,password_digest
from approval_ipc import ApprovalRPCServer,ApprovalRPCClient
from publication_contract import PublicationError


def command(argv,**kwargs):
    return subprocess.run(argv,env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/nonexistent'},
                          stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,timeout=10,**kwargs)


def main():
    if len(sys.argv)>1:
        root=Path(sys.argv[2]);owner=pwd.getpwnam('approval');publisher=pwd.getpwnam('publisher')
        if sys.argv[1]=='issuer':
            issuer=ApprovalIssuer(root/'issuer',root/'issuer/signing.pem',root/'issuer/owner.json','fixture-uid-issuer')
            rpc=ApprovalRPCServer(root/'ipc/approval.sock',issuer,{0:{'propose','view','consent'},publisher.pw_uid:{'status','propose'},pwd.getpwnam('owner_ui').pw_uid:{'view','consent','revoke'}})
            rpc.serve_forever()
        if sys.argv[1]=='client':
            client=ApprovalRPCClient(root/'ipc/approval.sock',owner.pw_uid)
            proof=client.status('0'*32,'fixture-challenge','0'*64,'check')
            assert proof['payload']['active'] is False and proof['signature']
            try:client.request('consent',proposal='0'*32,password='synthetic invalid passphrase',consent_digest='0'*64,confirmation='PUBLICAR')
            except PublicationError:return 0
            return 9
    if os.geteuid()!=0:raise SystemExit('container root fixture required')
    root=Path(tempfile.mkdtemp(prefix='m006-uid-'));root.chmod(0o755)
    roles={name:pwd.getpwnam(name) for name in ('approval','publisher','runner','owner_ui')}
    try:
        for name in ('approval','publisher'):
            path=root/('issuer' if name=='approval' else 'publisher');path.mkdir(mode=0o700);os.chown(path,roles[name].pw_uid,roles[name].pw_gid)
        ipc=root/'ipc';ipc.mkdir(mode=0o2750);os.chown(ipc,roles['approval'].pw_uid,grp.getgrnam('consent_clients').gr_gid);ipc.chmod(0o2750)
        key=root/'issuer/signing.pem'
        assert command(['su-exec','approval','openssl','genpkey','-algorithm','ED25519','-out',str(key)]).returncode==0
        owner={'owner_id':'fixture-owner','salt':'a'*32};owner['password_scrypt']=password_digest('synthetic owner passphrase',bytes.fromhex(owner['salt']))
        record=root/'issuer/owner.json';record.write_text(json.dumps(owner));record.chmod(0o600);os.chown(record,roles['approval'].pw_uid,roles['approval'].pw_gid)
        token=root/'publisher/token';token.write_text('synthetic_transport_token');token.chmod(0o600);os.chown(token,roles['publisher'].pw_uid,roles['publisher'].pw_gid)
        for role,secret in (('runner',key),('runner',token),('publisher',key),('approval',token),('owner_ui',key),('owner_ui',token)):
            assert command(['su-exec',role,'test','-r',str(secret)]).returncode!=0
        assert command(['su-exec','runner','test','-w','/app/projects/avisaqui.json']).returncode!=0
        process=subprocess.Popen(['su-exec','approval','/usr/bin/python3',__file__,'issuer',str(root)],
                 env={'PATH':'/usr/sbin:/usr/bin:/sbin:/bin','HOME':'/nonexistent'},stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
        try:
            for _ in range(50):
                if (ipc/'approval.sock').exists():break
                time.sleep(.05)
            if not (ipc/'approval.sock').exists():
                if process.poll() is not None:
                    raise RuntimeError('synthetic issuer startup failed: '+process.stderr.read().decode()[-1500:])
                raise RuntimeError('synthetic issuer socket deadline')
            assert command(['su-exec','publisher','/usr/bin/python3',__file__,'client',str(root)]).returncode==0
            # Worker cannot even traverse the socket directory.
            assert command(['su-exec','runner','test','-x',str(ipc)]).returncode!=0
            print(json.dumps({'result':'PASS','different_os_uids':len({p.pw_uid for p in roles.values()})==4,
                'preparer_cannot_read_signing_or_transport_secrets':True,'issuer_cannot_read_transport_secret':True,
                'publisher_cannot_read_signing_secret':True,'publisher_cannot_issue_grants':True,
                'worker_cannot_connect_approval_socket':True,'profile_not_worker_writable':True}))
        finally:
            process.terminate();process.wait(timeout=5);process.stderr.close()
    finally:shutil.rmtree(root)
    return 0


if __name__=='__main__':raise SystemExit(main())
