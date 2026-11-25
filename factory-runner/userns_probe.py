#!/usr/bin/env python3
"""Non-mutating probe for user/mount/net/PID namespaces and private tmpfs quotas.

Only synthetic files are created in a private mount namespace. No project code,
host mount, Docker API, cgroup, capability or AppArmor setting is modified.
"""
from __future__ import annotations

import ctypes
import errno
import json
import os
from pathlib import Path
import select
import shutil
import signal
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from isolation_backend_probe import effective_capabilities_via_capget, root_capabilities

CLONE_NEWNS = 0x00020000
CLONE_NEWPID = 0x20000000
CLONE_NEWNET = 0x40000000
CLONE_NEWUSER = 0x10000000
MS_NOSUID = 2
MS_NODEV = 4
MS_NOEXEC = 8
MS_REC = 16384
MS_PRIVATE = 1 << 18
MNT_DETACH = 2
TMPFS_BYTES = 1024 * 1024
WRITE_TEST_BYTES = 2 * 1024 * 1024
CHILD_TIMEOUT_SECONDS = 6


def _libc():
    libc = ctypes.CDLL(None, use_errno=True)
    libc.unshare.argtypes = [ctypes.c_int]
    libc.unshare.restype = ctypes.c_int
    libc.mount.argtypes = [ctypes.c_char_p, ctypes.c_char_p,
                           ctypes.c_char_p, ctypes.c_ulong, ctypes.c_char_p]
    libc.mount.restype = ctypes.c_int
    libc.umount2.argtypes = [ctypes.c_char_p, ctypes.c_int]
    libc.umount2.restype = ctypes.c_int
    return libc


def _call(libc, name, *args):
    ctypes.set_errno(0)
    result = getattr(libc, name)(*args)
    if result != 0:
        code = ctypes.get_errno()
        raise OSError(code, errno.errorcode.get(code, "OS_ERROR"))
    return True


def _write_map(path: str, value: str):
    fd = os.open(path, os.O_WRONLY | getattr(os, "O_CLOEXEC", 0))
    try:
        data = value.encode("ascii")
        written = os.write(fd, data)
        if written != len(data):
            raise OSError(errno.EIO, "short_proc_map_write")
    finally:
        os.close(fd)


def _parse_security_context(status_text: str, apparmor_profile: str | None):
    fields = {}
    for line in status_text.splitlines():
        if ':' in line:
            key, value = line.split(':', 1)
            fields[key.strip()] = value.strip()
    cap_eff = fields.get('CapEff')
    try:
        cap_mask = int(cap_eff, 16) if cap_eff is not None else None
    except ValueError:
        cap_mask = None
    return {
        'cap_eff': cap_eff,
        'cap_sys_admin_in_userns': bool(cap_mask & (1 << 21)) if cap_mask is not None else None,
        'no_new_privs': fields.get('NoNewPrivs'),
        'seccomp_mode': fields.get('Seccomp'),
        'apparmor_profile': (apparmor_profile or '').strip()[:128] or None,
    }


def _read_security_context():
    try:
        status_text = Path('/proc/self/status').read_text(encoding='ascii', errors='replace')
    except OSError as exc:
        status_text = ''
        status_error = errno.errorcode.get(exc.errno, 'OS_ERROR')
    else:
        status_error = None
    try:
        profile = Path('/proc/self/attr/current').read_text(encoding='utf-8', errors='replace').strip()
    except OSError:
        profile = None
    result = _parse_security_context(status_text, profile)
    if status_error is not None:
        result['status_read_error'] = status_error
    return result

def _namespace_child(mountpoint: str, report_fd: int):
    report = {
        "user_namespace_created": False,
        "uid_map_written": False,
        "gid_map_written": False,
        "mount_namespace_created": False,
        "mount_propagation_private": False,
        "net_namespace_created": False,
        "pid_namespace_created": False,
        "pid_namespace_init_verified": False,
        "tmpfs_mounted": False,
        "tmpfs_size_bytes": None,
        "tmpfs_quota_enforced": False,
        "tmpfs_written_before_enospc": 0,
        "tmpfs_unmount_ok": False,
        "child_security_context": None,
        "errors": {},
    }
    libc = _libc()
    outer_uid, outer_gid = os.getuid(), os.getgid()
    mounted = False
    try:
        os.setsid()
        try:
            _call(libc, "unshare", CLONE_NEWUSER)
            report["user_namespace_created"] = True
        except OSError as exc:
            report["errors"]["user_namespace"] = errno.errorcode.get(exc.errno, "OS_ERROR")
            return report

        try:
            _write_map("/proc/self/setgroups", "deny")
            _write_map("/proc/self/uid_map", f"0 {outer_uid} 1")
            report["uid_map_written"] = True
            _write_map("/proc/self/gid_map", f"0 {outer_gid} 1")
            report["gid_map_written"] = True
            report["child_security_context"] = _read_security_context()
        except OSError as exc:
            report["errors"]["id_map"] = errno.errorcode.get(exc.errno, "OS_ERROR")
            return report

        try:
            _call(libc, "unshare", CLONE_NEWNS)
            report["mount_namespace_created"] = True
            _call(libc, "mount", None, b"/", None,
                  ctypes.c_ulong(MS_REC | MS_PRIVATE), None)
            report["mount_propagation_private"] = True
        except OSError as exc:
            report["errors"]["mount_namespace"] = errno.errorcode.get(exc.errno, "OS_ERROR")

        if report["mount_namespace_created"] and report["mount_propagation_private"]:
            try:
                _call(libc, "mount", b"tmpfs", os.fsencode(mountpoint), b"tmpfs",
                      ctypes.c_ulong(MS_NOSUID | MS_NODEV | MS_NOEXEC),
                      f"size={TMPFS_BYTES},mode=0700".encode("ascii"))
                mounted = True
                report["tmpfs_mounted"] = True
                stat = os.statvfs(mountpoint)
                total = stat.f_blocks * stat.f_frsize
                report["tmpfs_size_bytes"] = total
                if 0 < total <= TMPFS_BYTES:
                    target = Path(mountpoint) / "quota-probe.bin"
                    written = 0
                    try:
                        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                        try:
                            chunk = b"x" * 65536
                            while written < WRITE_TEST_BYTES:
                                amount = min(len(chunk), WRITE_TEST_BYTES - written)
                                count = os.write(fd, chunk[:amount])
                                if count <= 0:
                                    raise OSError(errno.EIO, "short_tmpfs_write")
                                written += count
                        finally:
                            os.close(fd)
                    except OSError as exc:
                        report["tmpfs_quota_enforced"] = (
                            exc.errno == errno.ENOSPC and TMPFS_BYTES * 3 // 4 <= written <= TMPFS_BYTES + 65536
                        )
                        report["errors"]["tmpfs_write"] = errno.errorcode.get(exc.errno, "OS_ERROR")
                    report["tmpfs_written_before_enospc"] = written
                else:
                    report["errors"]["tmpfs_size"] = "unexpected_mount_capacity"
            except OSError as exc:
                report["errors"]["tmpfs_mount"] = errno.errorcode.get(exc.errno, "OS_ERROR")

        try:
            _call(libc, "unshare", CLONE_NEWNET)
            report["net_namespace_created"] = True
        except OSError as exc:
            report["errors"]["net_namespace"] = errno.errorcode.get(exc.errno, "OS_ERROR")

        try:
            _call(libc, "unshare", CLONE_NEWPID)
            pid = os.fork()
            if pid == 0:
                os._exit(0 if os.getpid() == 1 else 91)
            _, status = os.waitpid(pid, 0)
            report["pid_namespace_created"] = True
            report["pid_namespace_init_verified"] = os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
        except OSError as exc:
            report["errors"]["pid_namespace"] = errno.errorcode.get(exc.errno, "OS_ERROR")

    except BaseException as exc:
        report["errors"]["probe"] = type(exc).__name__
    finally:
        if mounted:
            try:
                _call(libc, "umount2", os.fsencode(mountpoint), MNT_DETACH)
                report["tmpfs_unmount_ok"] = True
            except OSError as exc:
                report["errors"]["tmpfs_unmount"] = errno.errorcode.get(exc.errno, "OS_ERROR")
        try:
            payload = json.dumps(report, sort_keys=True).encode("utf-8")
            os.write(report_fd, payload[:8192])
        except BaseException:
            pass
    return report


def run_probe():
    before = root_capabilities()
    before_mask = effective_capabilities_via_capget()
    result = {
        "mode": "user_namespace_capability_probe",
        "status": "blocked",
        "safe_for_untrusted_code": False,
        "project_code_executed": False,
        "parent_sys_admin_before": before.get("sys_admin"),
        "parent_sys_admin_after": None,
        "parent_capabilities_unchanged": False,
        "parent_mount_leaked": False,
        "child": {},
    }
    mountpoint = tempfile.mkdtemp(prefix="fr-userns-probe-")
    read_fd, write_fd = os.pipe()
    pid = os.fork()
    if pid == 0:
        os.close(read_fd)
        report = _namespace_child(mountpoint, write_fd)
        os._exit(0 if report.get("user_namespace_created") else 1)

    os.close(write_fd)
    deadline = time.monotonic() + CHILD_TIMEOUT_SECONDS
    payload = bytearray()
    timed_out = False
    child_status = None
    try:
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            ready, _, _ = select.select([read_fd], [], [], min(remaining, 0.1))
            if ready:
                chunk = os.read(read_fd, 8192 - len(payload))
                if not chunk:
                    break
                payload.extend(chunk)
                if len(payload) >= 8192:
                    break
            waited, status = os.waitpid(pid, os.WNOHANG)
            if waited == pid:
                child_status = status
                break
        if timed_out:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                os.kill(pid, signal.SIGKILL)
        if child_status is None:
            try:
                _, child_status = os.waitpid(pid, 0)
            except ChildProcessError:
                child_status = None
    finally:
        os.close(read_fd)
        parent_mount_leaked = os.path.ismount(mountpoint)
        if not parent_mount_leaked:
            shutil.rmtree(mountpoint, ignore_errors=True)

    if payload:
        try:
            result["child"] = json.loads(payload.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            result["child"] = {"errors": {"report": "invalid_json"}}
    result["timed_out"] = timed_out
    result["child_exit_code"] = (
        os.WEXITSTATUS(child_status) if child_status is not None and os.WIFEXITED(child_status) else None
    )
    result["parent_mount_leaked"] = parent_mount_leaked
    after = root_capabilities()
    after_mask = effective_capabilities_via_capget()
    result["parent_sys_admin_after"] = after.get("sys_admin")
    result["parent_capabilities_unchanged"] = (
        before_mask.get("status") == "ok"
        and after_mask.get("status") == "ok"
        and before_mask.get("mask") == after_mask.get("mask")
        and before.get("sys_admin") == after.get("sys_admin")
    )
    child = result["child"]
    result["status"] = summarize_status(
        child, timed_out=timed_out, parent_mount_leaked=parent_mount_leaked,
        parent_capabilities_unchanged=result["parent_capabilities_unchanged"],
        parent_sys_admin_before=result["parent_sys_admin_before"],
        parent_sys_admin_after=result["parent_sys_admin_after"],
    )
    return result


def summarize_status(child, *, timed_out=False, parent_mount_leaked=False,
                     parent_capabilities_unchanged=False,
                     parent_sys_admin_before=False, parent_sys_admin_after=False):
    if (parent_mount_leaked or not parent_capabilities_unchanged
            or parent_sys_admin_before is not False
            or parent_sys_admin_after is not False):
        return "failed_cleanup_or_parent_state"
    if timed_out:
        return "timeout"
    if child.get("user_namespace_created") is not True:
        return "blocked"
    required = (
        "uid_map_written", "gid_map_written", "mount_namespace_created",
        "mount_propagation_private", "tmpfs_mounted", "tmpfs_quota_enforced",
        "tmpfs_unmount_ok", "net_namespace_created", "pid_namespace_created",
        "pid_namespace_init_verified",
    )
    return "available" if all(child.get(key) is True for key in required) else "partial"

if __name__ == "__main__":
    print("[USERNS-PROBE] " + json.dumps(run_probe(), sort_keys=True), flush=True)
