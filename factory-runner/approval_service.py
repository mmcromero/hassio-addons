"""Separate approval UID service. Starts after root-owned owner identity config; supports one-time enrollment."""
import grp, json, os, pwd, stat
from pathlib import Path
from approval_ipc import ApprovalRPCServer
from owner_approval import ApprovalAuthority
from publication_contract import PublicationError

ROOT=Path("/data/factory-runner-authority")
CONFIG=ROOT/"approval-config"/"runtime.json"
PRIVATE_KEY=ROOT/"approval"/"credentials"/"signing.pem"
OWNER_RECORD=ROOT/"approval"/"credentials"/"owner.json"
SOCKET=ROOT/"consent-ipc"/"approval.sock"

def load_config():
    if CONFIG.is_symlink() or not CONFIG.is_file() or CONFIG.resolve()!=CONFIG:
        raise PublicationError("approval_runtime_config_unavailable")
    info=CONFIG.stat()
    if info.st_uid!=0 or info.st_gid!=grp.getgrnam("approval").gr_gid or stat.S_IMODE(info.st_mode)!=0o440 or info.st_nlink!=1:
        raise PublicationError("approval_runtime_config_untrusted")
    value=json.loads(CONFIG.read_text())
    required={"schema_version","authority","owner_id","publisher_uid","owner_ui_uid"}
    if set(value)!=required or value["schema_version"]!=1:
        raise PublicationError("approval_runtime_config_invalid")
    return value

def serve():
    config=load_config()
    issuer=ApprovalAuthority(ROOT/"approval",PRIVATE_KEY,OWNER_RECORD,
                             config["authority"],config["owner_id"])
    roles={
        0:{"enroll","enrollment_status"},
        config["publisher_uid"]:{"propose","status","grant","public_key"},
        config["owner_ui_uid"]:{"view","consent","revoke","enroll","enrollment_status"},
    }
    server=ApprovalRPCServer(SOCKET,issuer,roles)
    print("[APPROVAL] READY: isolated owner authority and kernel UID ACL",flush=True)
    try: server.serve_forever()
    finally:
        server.server_close()
        issuer.close()

if __name__=="__main__":
    serve()
