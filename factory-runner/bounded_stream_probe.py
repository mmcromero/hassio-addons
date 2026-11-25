#!/usr/bin/env python3
"""Synthetic proof of a read-only chroot with a byte-capped stdout channel.

This is a diagnostic only. It never loads or executes a project-supplied script.
"""
import errno
import json
import os
from pathlib import Path
import pwd
import resource
import select
import signal
import socket
import tempfile
import time
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from isolation_backend_probe import audit_and_close_unapproved_fds, memory_mounts
from seccomp_policy import _load_library, install_restrictions

SAFE_PAYLOAD = r'''
result = {"filesystem_write_denied": False, "network_denied": False,
          "process_creation_denied": False}
try:
    fd = os.open("/source/write-attempt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
except OSError as exc:
    result["filesystem_write_denied"] = exc.errno == errno.EPERM
else:
    os.close(fd)
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError as exc:
    result["network_denied"] = exc.errno == errno.EPERM
else:
    sock.close()
try:
    child = os.fork()
except OSError as exc:
    result["process_creation_denied"] = exc.errno == errno.EPERM
else:
    if child == 0:
        os._exit(0)
    os.waitpid(child, 0)
result["fd_audit"] = fd_audit
os.write(1, json.dumps(result, sort_keys=True).encode("utf-8"))
'''

OVERFLOW_PAYLOAD = 'os.write(1, b"x" * 2048)\n'


def _child(root, read_fd, write_fd, stdin_fd, stderr_fd, uid, gid, seccomp_lib):
    try:
        os.close(read_fd)
        os.dup2(stdin_fd, 0)
        os.dup2(write_fd, 1)
        os.dup2(stderr_fd, 2)
        for fd in {stdin_fd, write_fd, stderr_fd}:
            if fd > 2:
                try:
                    os.close(fd)
                except OSError:
                    pass
        fd_audit = audit_and_close_unapproved_fds([0, 1, 2])
        os.chroot(str(root))
        os.chdir("/")
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        with open("/source/payload.py", "r", encoding="utf-8") as handle:
            payload_source = handle.read()
        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        install_restrictions(library=seccomp_lib, deny_filesystem_writes=True,
                             deny_process_creation=True)
        resource.setrlimit(resource.RLIMIT_NOFILE, (3, 3))
        namespace = {
            "os": os, "errno": errno, "json": json, "socket": socket,
            "fd_audit": fd_audit,
        }
        exec(compile(payload_source, "/source/payload.py", "exec"),
             namespace, namespace)
        os._exit(0)
    except BaseException as exc:
        try:
            os.write(1, json.dumps({
                "child_error": type(exc).__name__,
            }).encode("utf-8"))
        except BaseException:
            pass
        os._exit(1)


def run_probe(max_output_bytes=4096, timeout_seconds=8, payload_mode="safe"):
    if not isinstance(max_output_bytes, int) or not 1 <= max_output_bytes <= 1024 * 1024:
        raise ValueError("invalid output limit")
    if payload_mode not in ("safe", "overflow"):
        raise ValueError("invalid synthetic payload mode")
    mounts = memory_mounts()
    shm = mounts.get("/dev/shm", {})
    report = {
        "mode": "bounded_stream_synthetic_probe",
        "status": "blocked",
        "payload_mode": payload_mode,
        "output_limit_bytes": max_output_bytes,
        "stdout_bytes": 0,
        "output_limit_enforced": False,
        "filesystem_write_denied": False,
        "network_denied": False,
        "process_creation_denied": False,
        "fd_audit": None,
        "chroot_entered": False,
        "uid_dropped": False,
        "seccomp_loaded": False,
        "tmpfs_mount": "/dev/shm",
        "tmpfs_filesystem": shm.get("filesystem"),
        "tmpfs_upper_bound_bytes": shm.get("total_bytes"),
        "safe_for_untrusted_code": False,
        "project_code_executed": False,
    }
    if (os.geteuid() != 0 or shm.get("filesystem") != "tmpfs"
            or not isinstance(shm.get("total_bytes"), int)
            or shm["total_bytes"] <= 0):
        report["reason"] = "root_or_bounded_tmpfs_unavailable"
        return report
    try:
        account = pwd.getpwnam("executor")
    except KeyError:
        report["reason"] = "executor_account_missing"
        return report
    payload = SAFE_PAYLOAD if payload_mode == "safe" else OVERFLOW_PAYLOAD
    try:
        seccomp_lib = _load_library()
    except OSError as exc:
        report["reason"] = "seccomp_library_unavailable"
        report["errno"] = exc.errno
        return report
    before = os.statvfs("/dev/shm").f_bavail * os.statvfs("/dev/shm").f_frsize
    with tempfile.TemporaryDirectory(prefix="fr-stream-probe-", dir="/dev/shm") as temp:
        os.chmod(temp, 0o755)
        root = Path(temp) / "root"
        source = root / "source"
        source.mkdir(parents=True)
        source.mkdir(exist_ok=True)
        payload_file = source / "payload.py"
        payload_file.write_text(payload, encoding="utf-8")
        os.chown(payload_file, 0, 0)
        os.chmod(payload_file, 0o444)
        os.chown(source, 0, 0)
        os.chmod(source, 0o555)
        os.chown(root, 0, 0)
        os.chmod(root, 0o555)
        read_fd, write_fd = os.pipe()
        stdin_fd = os.open(os.devnull, os.O_RDONLY)
        stderr_fd = os.open(os.devnull, os.O_WRONLY)
        pid = os.fork()
        if pid == 0:
            _child(root, read_fd, write_fd, stdin_fd, stderr_fd,
                   account.pw_uid, account.pw_gid, seccomp_lib)
        os.close(write_fd)
        os.close(stdin_fd)
        os.close(stderr_fd)
        output = bytearray()
        overflow = False
        timed_out = False
        deadline = time.monotonic() + timeout_seconds
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            ready, _, _ = select.select([read_fd], [], [], remaining)
            if not ready:
                timed_out = True
                break
            chunk = os.read(read_fd, min(4096, max_output_bytes + 1 - len(output)))
            if not chunk:
                break
            output.extend(chunk)
            if len(output) > max_output_bytes:
                overflow = True
                break
        if overflow or timed_out:
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass
        os.close(read_fd)
        _, status = os.waitpid(pid, 0)
        report["stdout_bytes"] = len(output)
        report["output_limit_enforced"] = overflow
        report["timed_out"] = timed_out
        report["child_exit_code"] = os.WEXITSTATUS(status) if os.WIFEXITED(status) else None
        if overflow:
            report["status"] = "blocked_output_limit"
        elif timed_out:
            report["status"] = "blocked_timeout"
        elif report["child_exit_code"] == 0:
            try:
                payload_result = json.loads(output.decode("utf-8"))
            except (UnicodeDecodeError, ValueError):
                report["status"] = "blocked_invalid_stream"
            else:
                report.update({k: v for k, v in payload_result.items()
                               if k in ("filesystem_write_denied", "network_denied",
                                        "process_creation_denied")})
                report["fd_audit"] = payload_result.get("fd_audit")
                report["chroot_entered"] = True
                report["uid_dropped"] = True
                report["seccomp_loaded"] = True
                expected = all(report[k] for k in (
                    "filesystem_write_denied", "network_denied",
                    "process_creation_denied"))
                fd_ok = isinstance(report["fd_audit"], dict) and report["fd_audit"].get("status") == "ok"
                report["status"] = "pass" if expected and fd_ok else "blocked_policy_probe"
        else:
            report["status"] = "blocked_child_error"
    after = os.statvfs("/dev/shm").f_bavail * os.statvfs("/dev/shm").f_frsize
    report["tmpfs_available_before_bytes"] = before
    report["tmpfs_available_after_cleanup_bytes"] = after
    report["tmpfs_cleanup_restored"] = after >= before - 65536
    return report


if __name__ == "__main__":
    import sys
    mode = sys.argv[1] if len(sys.argv) > 1 else "safe"
    limit = int(sys.argv[2]) if len(sys.argv) > 2 else 4096
    print("[BOUNDED-STREAM] " + json.dumps(
        run_probe(max_output_bytes=limit, payload_mode=mode), sort_keys=True),
        flush=True)
