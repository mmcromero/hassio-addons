"""One-time owner enrollment from Home Assistant add-on settings.

Runs as root during startup, forwards credentials only over the local approval
IPC, then clears the temporary option fields through the Supervisor self API.
Never logs, persists, or returns submitted passwords.
"""
import json
import os
import pwd
import secrets
import stat
import sys
import urllib.error
import urllib.request
from pathlib import Path

from approval_ipc import ApprovalRPCClient
from publication_contract import PublicationError

OPTIONS = Path("/data/options.json")
SOCKET = "/data/factory-runner-authority/consent-ipc/approval.sock"


def read_options():
    if OPTIONS.is_symlink() or OPTIONS.resolve() != OPTIONS or not OPTIONS.is_file():
        raise PublicationError("unsafe_supervisor_options_file")
    info = OPTIONS.stat()
    if info.st_uid != 0 or info.st_nlink != 1 or stat.S_IMODE(info.st_mode) & 0o077:
        raise PublicationError("unsafe_supervisor_options_permissions")
    value = json.loads(OPTIONS.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise PublicationError("invalid_supervisor_options")
    return value


def clear_temporary_options(token):
    if not isinstance(token, str) or len(token) < 16:
        raise PublicationError("supervisor_api_token_unavailable")
    payload = json.dumps({"options": {
        "owner_password": "",
        "owner_password_confirm": "",
    }}, separators=(",", ":")).encode("utf-8")
    request = urllib.request.Request(
        "http://supervisor/addons/self/options",
        data=payload,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            result = json.loads(response.read(65536))
    except (OSError, urllib.error.URLError, TimeoutError, ValueError):
        raise PublicationError("supervisor_options_clear_failed") from None
    if not isinstance(result, dict) or result.get("result") != "ok":
        raise PublicationError("supervisor_options_clear_failed")


def main():
    if os.geteuid() != 0:
        raise PublicationError("root_required_for_owner_settings")
    options = read_options()
    password = options.get("owner_password", "")
    confirmation = options.get("owner_password_confirm", "")
    if not password and not confirmation:
        return 0
    if (not isinstance(password, str) or not isinstance(confirmation, str)
            or not 16 <= len(password) <= 256
            or not secrets.compare_digest(password.encode("utf-8"), confirmation.encode("utf-8"))):
        raise PublicationError("owner_settings_password_invalid")
    if (options.get("owner_ingress_enabled") is not True
            or not isinstance(options.get("owner_ha_user_id"), str) or not options["owner_ha_user_id"].strip()
            or not isinstance(options.get("owner_ingress_origin"), str) or not options["owner_ingress_origin"].strip()):
        raise PublicationError("owner_settings_identity_incomplete")

    issuer_uid = pwd.getpwnam("approval").pw_uid
    rpc = ApprovalRPCClient(SOCKET, issuer_uid)
    status = rpc.enrollment_status()
    if status != {"enrolled": True}:
        rpc.enroll(password, confirmation, "CADASTRAR")
    # Only after the durable authority confirms enrollment do we clear the
    # transient fields in Supervisor's own options store.
    clear_temporary_options(os.environ.get("SUPERVISOR_TOKEN", ""))
    password = None
    confirmation = None
    options = None
    print("[OWNER-SETTINGS] enrollment state confirmed; temporary password options cleared",
          file=sys.stderr, flush=True)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (PublicationError, OSError, ValueError, KeyError) as exc:
        print("[OWNER-SETTINGS] BLOCKED: " + str(exc), file=sys.stderr, flush=True)
        raise SystemExit(1)
