"""Bounded Linux Unix IPC with kernel peer UID checks; no active listener by default.

Only root-controlled deployment may select socket path, roles and peer IDs.
No request can select a key, credential file, Git URL, command or filesystem path.
"""
import json
import grp
import os
from pathlib import Path
import socket
import socketserver
import stat
import struct
from publication_contract import PublicationError
from release_receipt import canonical

MAX_MESSAGE=3*1024*1024


def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key]=value
    return result


def peer_uid(sock):
    if not hasattr(socket,'SO_PEERCRED'):raise PublicationError('kernel_peer_identity_unavailable')
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]


def _remove_stale_socket(path, owner_uid, group_gid):
    if not path.exists() and not path.is_symlink():
        return
    info=path.lstat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid!=owner_uid
            or info.st_gid!=group_gid or stat.S_IMODE(info.st_mode)!=0o660):
        raise PublicationError('unsafe_existing_approval_socket')
    probe=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    probe.settimeout(1)
    try:
        probe.connect(str(path))
    except ConnectionRefusedError:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        raise PublicationError('approval_socket_state_unknown') from None
    else:
        raise PublicationError('approval_socket_already_active')
    finally:
        probe.close()


class ApprovalRPCServer(socketserver.UnixStreamServer):
    def __init__(self,path,issuer,roles,*,group_gid=None):
        path=Path(path).absolute()
        parent=path.parent
        if parent.resolve()!=parent or not parent.is_dir():
            raise PublicationError('unsafe_approval_socket')
        gid=grp.getgrnam("consent_clients").gr_gid if group_gid is None else group_gid
        info=parent.stat()
        if (info.st_uid!=os.geteuid() or info.st_gid!=gid
                or stat.S_IMODE(info.st_mode)!=0o750):
            raise PublicationError('unsafe_approval_socket')
        _remove_stale_socket(path,os.geteuid(),gid)
        self.issuer=issuer;self.roles={uid:frozenset(actions) for uid,actions in roles.items()}
        super().__init__(str(path),ApprovalRPCHandler)
        os.chown(path,-1,gid)
        path.chmod(0o660)

    def handle_error(self,request,client_address):pass


class ApprovalRPCHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            allowed=self.server.roles.get(peer_uid(self.connection),frozenset())
            if not allowed:raise PublicationError('peer_not_authorized')
            raw=self.rfile.readline(MAX_MESSAGE+1)
            if len(raw)>MAX_MESSAGE or not raw.endswith(b'\n'):raise PublicationError('invalid_ipc_size')
            body=json.loads(raw,object_pairs_hook=_unique_object)
            if not isinstance(body,dict) or body.get('action') not in allowed:raise PublicationError('ipc_action_denied')
            action=body.pop('action')
            keys={'propose':{'body','preview','receipt'},'view':{'proposal'},
                  'consent':{'proposal','password','consent_digest','confirmation'},
                  'revoke':{'nonce','password'},'status':{'nonce','challenge','grant_digest','purpose'},
                  'grant':{'proposal'},'public_key':set(),
                  'enroll':{'password','password_confirm','confirmation'},'enrollment_status':set()}
            if action not in keys or set(body)!=keys[action]:raise PublicationError('invalid_ipc_contract')
            result=getattr(self.server.issuer,action)(**body)
            data=canonical({'ok':True,'result':result})+b'\n'
            if len(data)>MAX_MESSAGE:raise PublicationError('ipc_result_budget')
        except Exception:
            data=b'{"ok":false,"error":"approval_request_denied"}\n'
        self.wfile.write(data)


class ApprovalRPCClient:
    def __init__(self,path,issuer_uid):self.path=str(path);self.issuer_uid=issuer_uid
    def request(self,action,**body):
        raw=canonical({'action':action,**body})+b'\n'
        if len(raw)>MAX_MESSAGE:raise PublicationError('ipc_request_budget')
        try:
            with socket.socket(socket.AF_UNIX,socket.SOCK_STREAM) as sock:
                sock.settimeout(5);sock.connect(self.path)
                if peer_uid(sock)!=self.issuer_uid:raise PublicationError('issuer_peer_mismatch')
                sock.sendall(raw)
                with sock.makefile('rb') as stream:response=stream.readline(MAX_MESSAGE+1)
        except (OSError,ValueError) as exc:raise PublicationError('approval_ipc_unavailable') from None
        if len(response)>MAX_MESSAGE:raise PublicationError('ipc_response_budget')
        try:result=json.loads(response)
        except ValueError:raise PublicationError('invalid_ipc_response') from None
        if result.get('ok') is not True:raise PublicationError('approval_request_denied')
        return result.get('result')
    def enroll(self,password,password_confirm,confirmation):
        return self.request('enroll',password=password,password_confirm=password_confirm,confirmation=confirmation)
    def enrollment_status(self):
        return self.request('enrollment_status')

    def propose(self,body,preview,receipt):
        return self.request('propose',body=body,preview=preview,receipt=receipt)
    def grant(self,proposal):
        return self.request('grant',proposal=proposal)
    def public_key(self):
        return self.request('public_key')

    def status(self,nonce,challenge,grant_digest,purpose):
        return self.request('status',nonce=nonce,challenge=challenge,grant_digest=grant_digest,purpose=purpose)


if __name__=='__main__':raise SystemExit('publication disabled: no production approval listener activated')
