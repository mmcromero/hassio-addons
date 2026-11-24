"""Root-only provisioning of isolated stores and immutable runtime identity config.

It never generates owner credentials, writes GitHub tokens, or enables publishing.
The owner chooses the password through the verified HA Ingress enrollment screen.
"""
from __future__ import annotations

import os
import stat
import sys
import json
import hashlib
import re
import subprocess
import grp
import pwd
from urllib.parse import urlsplit
from pathlib import Path

LAYOUT = (
    ("approval", "approval", "approval", 0o700),
    ("publisher", "publisher", "publisher", 0o700),
    ("owner-ui", "owner_ui", "owner_ui", 0o700),
    # Root-owned, group-readable configuration directories. Service UIDs cannot replace entries.
    ("approval-config", "root", "approval", 0o750),
    ("publisher-config", "root", "publisher", 0o750),
    ("owner-ui-config", "root", "owner_ui", 0o750),
    ("consent-ipc", "approval", "consent_clients", 0o2750),
    ("publisher-ipc", "publisher", "publisher_clients", 0o2750),
)


def _identity(user, group, uid_for, gid_for):
    uid, gid = uid_for(user), gid_for(group)
    if type(uid) is not int or uid < 0 or type(gid) is not int or gid < 0:
        raise ValueError("invalid_service_identity")
    return uid, gid


def provision_layout(root, *, uid_for=None, gid_for=None,
                     root_uid=None, root_gid=None, root_mode=0o711):
    """Create missing service directories; refuse mismatches without repair."""
    uid_for = uid_for or (lambda name: pwd.getpwnam(name).pw_uid)
    gid_for = gid_for or (lambda name: grp.getgrnam(name).gr_gid)
    root_uid = os.geteuid() if root_uid is None else root_uid
    root_gid = os.getegid() if root_gid is None else root_gid
    root = Path(root).absolute()
    if root.resolve() != root:
        raise ValueError("unsafe_authority_root")
    try:
        root_info = root.lstat()
    except FileNotFoundError:
        raise ValueError("authority_root_missing") from None
    if (not stat.S_ISDIR(root_info.st_mode) or root_info.st_uid != root_uid
            or root_info.st_gid != root_gid
            or stat.S_IMODE(root_info.st_mode) != root_mode):
        raise ValueError("unsafe_authority_root")

    # Resolve every account/group and inspect every existing path before writes.
    entries = []
    for name, user, group, mode in LAYOUT:
        uid, gid = _identity(user, group, uid_for, gid_for)
        path = root / name
        try:
            info = path.lstat()
        except FileNotFoundError:
            info = None
        if info is not None and (
                not stat.S_ISDIR(info.st_mode) or info.st_uid != uid
                or info.st_gid != gid or stat.S_IMODE(info.st_mode) != mode):
            raise ValueError("unsafe_existing_service_directory")
        entries.append((path, uid, gid, mode))

    for path, uid, gid, mode in entries:
        try:
            os.mkdir(path, 0o700)
        except FileExistsError:
            # Recheck a concurrent creation; never follow a symlink.
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode):
                raise ValueError("unsafe_existing_service_directory")
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (uid, gid, mode):
                raise ValueError("unsafe_existing_service_directory")
            continue
        fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fchown(fd, uid, gid)
            os.fchmod(fd, mode)
            info = os.fstat(fd)
            if (info.st_uid, info.st_gid, stat.S_IMODE(info.st_mode)) != (uid, gid, mode):
                raise ValueError("service_directory_provision_failed")
        finally:
            os.close(fd)
    return tuple(path for path, _, _, _ in entries)


AUTHORITY = "factory-runner-owner-m006-v1"

def _write_root_config(path, value, group_name):
    path = Path(path)
    parent = path.parent
    parent_info = parent.lstat()
    gid = grp.getgrnam(group_name).gr_gid
    if (not stat.S_ISDIR(parent_info.st_mode) or parent_info.st_uid != 0
            or parent_info.st_gid != gid or stat.S_IMODE(parent_info.st_mode) != 0o750
            or parent.resolve() != parent):
        raise ValueError("unsafe_root_config_directory")
    data = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    if path.exists() or path.is_symlink():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != 0
                or info.st_gid != gid or stat.S_IMODE(info.st_mode) != 0o440
                or info.st_nlink != 1 or path.read_bytes() != data):
            raise ValueError("owner_runtime_config_change_requires_reenrollment")
        return
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchown(fd, 0, gid)
        os.fchmod(fd, 0o440)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        parent_fd = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    except Exception:
        try: os.close(fd)
        except OSError: pass
        try: path.unlink()
        except OSError: pass
        raise


def configure_from_options(root, options_path="/data/options.json"):
    """Write immutable root-owned runtime identity config; never enroll secrets."""
    options_path = Path(options_path).absolute()
    if (options_path.resolve() != options_path or options_path.is_symlink()
            or not options_path.is_file()):
        raise ValueError("unsafe_supervisor_options_file")
    options_info = options_path.stat()
    if (options_info.st_uid != 0 or options_info.st_nlink != 1
            or stat.S_IMODE(options_info.st_mode) & 0o077):
        raise ValueError("unsafe_supervisor_options_permissions")
    options = json.loads(options_path.read_text(encoding="utf-8"))
    if not isinstance(options, dict):
        raise ValueError("invalid_supervisor_options")
    ingress_enabled = options.get("owner_ingress_enabled", False)
    if type(ingress_enabled) is not bool:
        raise ValueError("invalid_owner_ingress_enabled")
    user_id = options.get("owner_ha_user_id", "")
    origin = options.get("owner_ingress_origin", "")
    if not ingress_enabled:
        return False
    if not user_id or not origin:
        raise ValueError("owner_ingress_configuration_required")
    if (not isinstance(user_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", user_id)
            or not isinstance(origin, str) or any(ch.isspace() for ch in origin)):
        raise ValueError("invalid_owner_ingress_configuration")
    try:
        parsed = urlsplit(origin)
        _ = parsed.port
    except ValueError:
        raise ValueError("invalid_owner_ingress_origin") from None
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username is not None
            or parsed.password is not None or parsed.path or parsed.query or parsed.fragment):
        raise ValueError("https_owner_origin_required")
    owner_id = "ha-" + hashlib.sha256(user_id.encode("utf-8")).hexdigest()[:32]
    approval_uid = pwd.getpwnam("approval").pw_uid
    publisher_uid = pwd.getpwnam("publisher").pw_uid
    owner_ui_uid = pwd.getpwnam("owner_ui").pw_uid
    runner_uid = pwd.getpwnam("runner").pw_uid
    _write_root_config(root / "approval-config" / "runtime.json", {
        "schema_version": 1, "authority": AUTHORITY, "owner_id": owner_id,
        "publisher_uid": publisher_uid, "owner_ui_uid": owner_ui_uid,
    }, "approval")
    _write_root_config(root / "owner-ui-config" / "ingress.json", {
        "schema_version": 1, "expected_ha_user_id": user_id,
        "owner_id": owner_id, "origin": origin, "approval_uid": approval_uid,
    }, "owner_ui")
    credentials = root / "approval" / "credentials"
    key = credentials / "signing.pem"
    record = credentials / "owner.json"
    if credentials.exists() or credentials.is_symlink():
        info = credentials.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != approval_uid
                or stat.S_IMODE(info.st_mode) != 0o700 or credentials.is_symlink()
                or {item.name for item in credentials.iterdir()} != {"signing.pem", "owner.json"}):
            raise ValueError("unsafe_owner_credentials_directory")
        for item in (key, record):
            item_info = item.lstat()
            if (not stat.S_ISREG(item_info.st_mode) or item_info.st_uid != approval_uid
                    or stat.S_IMODE(item_info.st_mode) != 0o600 or item_info.st_nlink != 1):
                raise ValueError("unsafe_owner_credential_file")
        env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}
        result = subprocess.run(["/usr/bin/openssl", "pkey", "-in", str(key), "-pubout"],
            env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=5)
        if result.returncode or not result.stdout.startswith(b"-----BEGIN PUBLIC KEY-----"):
            raise ValueError("approval_public_key_unavailable")
        _write_root_config(root / "publisher-config" / "runtime.json", {
            "schema_version": 1, "owner_id": owner_id, "authority": AUTHORITY,
            "public_key_sha256": hashlib.sha256(result.stdout).hexdigest(),
            "approval_uid": approval_uid, "runner_uid": runner_uid,
        }, "publisher")
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if os.geteuid() != 0 or len(argv) != 1:
        print("[OWNER-BOOTSTRAP] BLOCKED: root_and_single_path_required", file=sys.stderr)
        return 2
    try:
        paths = provision_layout(argv[0], root_uid=0, root_gid=0, root_mode=0o711)
        configured = configure_from_options(Path(argv[0]))
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("[OWNER-BOOTSTRAP] BLOCKED: " + str(exc), file=sys.stderr)
        return 1
    print("[OWNER-BOOTSTRAP] READY: isolated persistent directories; runtime identity configured="
          + ("yes" if configured else "no") + "; credentials are never generated here")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
