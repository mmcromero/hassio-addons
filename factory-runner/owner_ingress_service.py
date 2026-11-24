"""HA Ingress status/owner-consent adapter, isolated under owner_ui UID."""
import grp, json, os, stat, sys
from pathlib import Path
from approval_ipc import ApprovalRPCClient
from ha_ingress_identity import verify_ha_ingress_context
from ha_ingress_server import serve_owner_consent, serve_owner_ingress_disabled
from owner_consent_ui import OwnerConsentUI
from publication_contract import PublicationError

ROOT=Path("/data/factory-runner-authority")
CONFIG=ROOT/"owner-ui-config"/"ingress.json"
SOCKET=ROOT/"consent-ipc"/"approval.sock"

def load_config():
    if CONFIG.is_symlink() or not CONFIG.is_file() or CONFIG.resolve()!=CONFIG:
        raise PublicationError("owner_ingress_config_unavailable")
    info=CONFIG.stat()
    if info.st_uid!=0 or info.st_gid!=grp.getgrnam("owner_ui").gr_gid or stat.S_IMODE(info.st_mode)!=0o440 or info.st_nlink!=1:
        raise PublicationError("owner_ingress_config_untrusted")
    value=json.loads(CONFIG.read_text())
    required={"schema_version","expected_ha_user_id","owner_id","origin","approval_uid"}
    if set(value)!=required or value["schema_version"]!=1:
        raise PublicationError("owner_ingress_config_invalid")
    return value

def serve():
    config=load_config()
    rpc=ApprovalRPCClient(SOCKET,config["approval_uid"])
    verifier=lambda context: verify_ha_ingress_context(
        context,expected_ha_user_id=config["expected_ha_user_id"],
        owner_id=config["owner_id"])
    ui=OwnerConsentUI(rpc,config["origin"],ingress_verifier=verifier)
    print("[OWNER-UI] READY: HA Ingress identity verified; consent only",flush=True)
    serve_owner_consent(ui,expected_ha_user_id=config["expected_ha_user_id"],
                        owner_id=config["owner_id"],port=8099)

def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if argv == ["--disabled"]:
        print("[OWNER-UI] STATUS-ONLY: consent and publication unavailable", flush=True)
        serve_owner_ingress_disabled(port=8099)
        return 0
    if argv:
        print("[OWNER-UI] BLOCKED: invalid service mode", file=sys.stderr)
        return 2
    serve()
    return 0


if __name__=="__main__":
    raise SystemExit(main())
