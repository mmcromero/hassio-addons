"""Bounded runner-to-publisher Unix RPC with kernel peer UID verification."""
from __future__ import annotations
import json
import os
from pathlib import Path
import socket
import socketserver
import stat
import struct
from release_receipt import canonical
from publication_contract import PublicationError

MAX_MESSAGE = 3 * 1024 * 1024
ACTIONS = {
    "preview": {"project", "issue", "receipt_digest"},
    "propose": {"project", "issue", "receipt_digest"},
    "publish": {"project", "issue", "receipt_digest", "proposal_id"},
    "status": set(),
    "reconcile": {"project", "nonce"},
}

def _unique_object(pairs):
    result={}
    for key,value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key]=value
    return result


def peer_uid(sock):
    if not hasattr(socket, "SO_PEERCRED"):
        raise PublicationError("kernel_peer_identity_unavailable")
    return struct.unpack("3i", sock.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, 12))[1]

def _remove_stale_socket(path, owner_uid, group_gid):
    if not path.exists() and not path.is_symlink():
        return
    info=path.lstat()
    if (not stat.S_ISSOCK(info.st_mode) or info.st_uid!=owner_uid
            or info.st_gid!=group_gid or stat.S_IMODE(info.st_mode)!=0o660):
        raise PublicationError("unsafe_existing_publisher_socket")
    probe=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
    probe.settimeout(1)
    try:
        probe.connect(str(path))
    except ConnectionRefusedError:
        path.unlink()
    except FileNotFoundError:
        return
    except OSError:
        raise PublicationError("publisher_socket_state_unknown") from None
    else:
        raise PublicationError("publisher_socket_already_active")
    finally:
        probe.close()


class PublisherRPCServer(socketserver.UnixStreamServer):
    def __init__(self, path, service, runner_uid, *, group_name="publisher_clients", group_gid=None):
        path = Path(path).absolute()
        parent = path.parent
        if parent.resolve() != parent or not parent.is_dir():
            raise PublicationError("unsafe_publisher_socket")
        import grp
        gid = grp.getgrnam(group_name).gr_gid if group_gid is None else group_gid
        info = parent.stat()
        if (info.st_uid != os.geteuid() or info.st_gid != gid
                or stat.S_IMODE(info.st_mode) != 0o750):
            raise PublicationError("unsafe_publisher_socket")
        _remove_stale_socket(path,os.geteuid(),gid)
        self.service = service
        self.runner_uid = runner_uid
        super().__init__(str(path), PublisherRPCHandler)
        os.chown(path, -1, gid)
        os.chmod(path, 0o660)
    def handle_error(self, request, client_address):
        return

class PublisherRPCHandler(socketserver.StreamRequestHandler):
    def handle(self):
        self.connection.settimeout(5)
        try:
            if peer_uid(self.connection) != self.server.runner_uid:
                raise PublicationError("publisher_peer_denied")
            raw = self.rfile.readline(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE or not raw.endswith(b"\n"):
                raise PublicationError("invalid_publisher_message")
            body = json.loads(raw, object_pairs_hook=_unique_object)
            if not isinstance(body, dict) or not isinstance(body.get("action"), str):
                raise PublicationError("invalid_publisher_message")
            action = body.pop("action")
            if action not in ACTIONS or set(body) != ACTIONS[action]:
                raise PublicationError("invalid_publisher_contract")
            result = getattr(self.server.service, action)(**body)
            data = canonical({"ok": True, "result": result}) + b"\n"
            if len(data) > MAX_MESSAGE:
                raise PublicationError("publisher_result_budget")
        except Exception:
            data = b'{"ok":false,"error":"publisher_request_denied"}\n'
        self.wfile.write(data)

class PublisherRPCClient:
    def __init__(self, path, publisher_uid):
        self.path = str(path)
        self.publisher_uid = publisher_uid
    def request(self, action, **body):
        if action not in ACTIONS or set(body) != ACTIONS[action]:
            raise PublicationError("invalid_publisher_contract")
        raw = canonical({"action": action, **body}) + b"\n"
        if len(raw) > MAX_MESSAGE:
            raise PublicationError("publisher_request_budget")
        try:
            with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as sock:
                sock.settimeout(5)
                sock.connect(self.path)
                if peer_uid(sock) != self.publisher_uid:
                    raise PublicationError("publisher_peer_mismatch")
                sock.sendall(raw)
                with sock.makefile("rb") as stream:
                    response = stream.readline(MAX_MESSAGE + 1)
        except PublicationError:
            raise
        except (OSError, ValueError):
            raise PublicationError("publisher_ipc_unavailable") from None
        if len(response) > MAX_MESSAGE:
            raise PublicationError("publisher_response_budget")
        try:
            result = json.loads(response)
        except ValueError:
            raise PublicationError("invalid_publisher_response") from None
        if result.get("ok") is not True:
            raise PublicationError("publisher_request_denied")
        return result.get("result")
