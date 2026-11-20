"""Bounded Linux Unix IPC with kernel peer UID checks; no active listener by default.

Only root-controlled deployment may select socket path, roles and peer IDs.
No request can select a key, credential file, Git URL, command or filesystem path.
"""
import json
import os
from pathlib import Path
import socket
import socketserver
import stat
import struct
from publication_contract import PublicationError
from release_receipt import canonical

MAX_MESSAGE=3*1024*1024


def peer_uid(sock):
    if not hasattr(socket,'SO_PEERCRED'):raise PublicationError('kernel_peer_identity_unavailable')
    return struct.unpack('3i',sock.getsockopt(socket.SOL_SOCKET,socket.SO_PEERCRED,12))[1]


class ApprovalRPCServer(socketserver.UnixStreamServer):
    def __init__(self,path,issuer,roles):
        path=Path(path).absolute()
        parent=path.parent
        if (parent.resolve()!=parent or not parent.is_dir() or parent.stat().st_mode&0o027
                or parent.stat().st_uid!=os.geteuid() or path.exists() or path.is_symlink()):
            raise PublicationError('unsafe_approval_socket')
        self.issuer=issuer;self.roles={uid:frozenset(actions) for uid,actions in roles.items()}
        super().__init__(str(path),ApprovalRPCHandler)
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
            body=json.loads(raw)
            if not isinstance(body,dict) or body.get('action') not in allowed:raise PublicationError('ipc_action_denied')
            action=body.pop('action')
            keys={'propose':{'body','preview','receipt'},'view':{'proposal'},
                  'consent':{'proposal','password','consent_digest','confirmation'},
                  'revoke':{'nonce','password'},'status':{'nonce','challenge','grant_digest','purpose'}}
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
    def status(self,nonce,challenge,grant_digest,purpose):
        return self.request('status',nonce=nonce,challenge=challenge,grant_digest=grant_digest,purpose=purpose)


if __name__=='__main__':raise SystemExit('publication disabled: no production approval listener activated')
