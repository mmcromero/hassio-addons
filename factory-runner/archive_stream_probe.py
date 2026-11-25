#!/usr/bin/env python3
"""Synthetic chroot -> bounded stdout -> trusted archive validator integration.

This diagnostic never loads a project-supplied script and never enables sandbox_export.
"""
import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import pwd
import resource
import select
import shutil
import signal
import socket
import sys
import tarfile
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parent))

from archive_stream import ArchiveStreamError, validate_and_extract_tar
from isolation_backend_probe import (
    audit_and_close_unapproved_fds,
    effective_capabilities_via_capget,
    memory_mounts,
)
from seccomp_policy import _load_library, install_restrictions

SAFE_CONTENT = b"factory-runner-archive-stream-probe-v1"
SAFE_SHA256 = hashlib.sha256(SAFE_CONTENT).hexdigest()

SAFE_PAYLOAD = r'''
checks = {}
try:
    os.open("/source/write-attempt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
except OSError as exc:
    checks["filesystem_write_denied"] = exc.errno == errno.EPERM
else:
    os._exit(91)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError as exc:
    checks["network_denied"] = exc.errno == errno.EPERM
else:
    os._exit(92)
try:
    os.fork()
except OSError as exc:
    checks["process_creation_denied"] = exc.errno == errno.EPERM
else:
    os._exit(93)
if not all(checks.values()):
    os._exit(94)
security_report.update(checks)
os.write(3, json.dumps(security_report, sort_keys=True).encode("utf-8"))
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
    info = tarfile.TarInfo("package/manifest.json")
    info.size = len(content)
    info.mode = 0o777
    info.uid = 0
    info.gid = 0
    archive.addfile(info, io.BytesIO(content))
sys.stdout.flush()
'''

TRAVERSAL_PAYLOAD = r'''
checks = {}
try:
    os.open("/source/write-attempt", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
except OSError as exc:
    checks["filesystem_write_denied"] = exc.errno == errno.EPERM
else:
    os._exit(91)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except OSError as exc:
    checks["network_denied"] = exc.errno == errno.EPERM
else:
    os._exit(92)
try:
    os.fork()
except OSError as exc:
    checks["process_creation_denied"] = exc.errno == errno.EPERM
else:
    os._exit(93)
if not all(checks.values()):
    os._exit(94)
security_report.update(checks)
os.write(3, json.dumps(security_report, sort_keys=True).encode("utf-8"))
with tarfile.open(fileobj=sys.stdout.buffer, mode="w|", format=tarfile.USTAR_FORMAT) as archive:
    info = tarfile.TarInfo("../escape.txt")
    info.size = 1
    archive.addfile(info, io.BytesIO(b"x"))
sys.stdout.flush()
'''

OVERFLOW_PAYLOAD = 'while True:\n    os.write(1, b"x" * 2048)\n'
TIMEOUT_PAYLOAD = "while True:\n    time.sleep(1)\n"


def _child(root, payload, stdout_read, stdout_write, report_read, report_write,
           stdin_fd, stderr_fd, uid, gid, seccomp_lib):
    try:
        os.close(stdout_read)
        os.close(report_read)
        os.environ.clear()
        os.setsid()
        os.dup2(stdin_fd, 0)
        os.dup2(stdout_write, 1)
        os.dup2(stderr_fd, 2)
        os.dup2(report_write, 3)
        for fd in {stdin_fd, stdout_write, stderr_fd, report_write}:
            if fd > 3:
                try:
                    os.close(fd)
                except OSError:
                    pass

        fd_audit = audit_and_close_unapproved_fds([0, 1, 2, 3])
        if fd_audit.get("status") != "ok":
            os.write(3, json.dumps({"fd_audit": fd_audit}).encode("utf-8"))
            os._exit(80)

        os.chroot(str(root))
        os.chdir("/")
        os.setgroups([])
        os.setgid(gid)
        os.setuid(uid)
        uid_dropped = os.geteuid() == uid and os.getegid() == gid

        resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
        resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        resource.setrlimit(resource.RLIMIT_NOFILE, (4, 4))

        capabilities = effective_capabilities_via_capget()
        install_restrictions(
            library=seccomp_lib,
            deny_filesystem_writes=True,
            deny_process_creation=True,
        )
        libc = ctypes.CDLL(None, use_errno=True)
        no_new_privs = libc.prctl(39, 0, 0, 0, 0) == 1
        security = {
            "fd_audit": fd_audit,
            "chroot_entered": True,
            "uid_dropped": uid_dropped,
            "environment_empty": not bool(os.environ),
            "effective_capabilities_zero": capabilities.get("zero") is True,
            "no_new_privs": no_new_privs,
            "seccomp_loaded": True,
        }
        namespace = {
            "os": os,
            "errno": errno,
            "json": json,
            "socket": socket,
            "tarfile": tarfile,
            "io": io,
            "sys": sys,
            "time": time,
            "content": SAFE_CONTENT,
        }
        if payload in (SAFE_PAYLOAD, TRAVERSAL_PAYLOAD):
            if not all((uid_dropped, security["effective_capabilities_zero"],
                        no_new_privs, security["seccomp_loaded"])):
                os.write(3, json.dumps(security, sort_keys=True).encode("utf-8"))
                os._exit(81)
            namespace.update({"security_report": security})
        exec(compile(payload, "/source/payload.py", "exec"), namespace, namespace)
        os._exit(0)
    except BaseException as exc:
        try:
            os.write(3, json.dumps({"child_error": type(exc).__name__}).encode("utf-8"))
        except BaseException:
            pass
        os._exit(1)


def _statvfs_available(path="/dev/shm"):
    info = os.statvfs(path)
    return info.f_bavail * info.f_frsize


def _run_child(payload, *, max_output_bytes, timeout_seconds, uid, gid, seccomp_lib):
    before = _statvfs_available()
    with tempfile.TemporaryDirectory(prefix="fr-archive-stream-root-", dir="/dev/shm") as temp:
        root = Path(temp) / "root"
        source = root / "source"
        source.mkdir(parents=True)
        payload_file = source / "payload.py"
        payload_file.write_text(payload, encoding="utf-8")
        os.chown(payload_file, 0, 0)
        os.chmod(payload_file, 0o444)
        os.chown(source, 0, 0)
        os.chmod(source, 0o555)
        os.chown(root, 0, 0)
        os.chmod(root, 0o555)

        stdout_read, stdout_write = os.pipe()
        report_read, report_write = os.pipe()
        stdin_fd = os.open(os.devnull, os.O_RDONLY)
        stderr_fd = os.open(os.devnull, os.O_WRONLY)
        pid = os.fork()
        if pid == 0:
            _child(root, payload, stdout_read, stdout_write, report_read,
                   report_write, stdin_fd, stderr_fd, uid, gid, seccomp_lib)

        os.close(stdout_write)
        os.close(report_write)
        os.close(stdin_fd)
        os.close(stderr_fd)
        output = bytearray()
        report_bytes = bytearray()
        stdout_eof = False
        report_eof = False
        timed_out = False
        overflow = False
        report_overflow = False
        child_status = None
        deadline = time.monotonic() + timeout_seconds

        try:
            while not (stdout_eof and report_eof and child_status is not None):
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    timed_out = True
                    break
                ready, _, _ = select.select(
                    [fd for fd, eof in ((stdout_read, stdout_eof),
                                        (report_read, report_eof)) if not eof],
                    [], [], min(remaining, 0.1),
                )
                for fd in ready:
                    if fd == stdout_read:
                        chunk = os.read(fd, min(4096, max_output_bytes + 1 - len(output)))
                        if not chunk:
                            stdout_eof = True
                        else:
                            output.extend(chunk)
                            if len(output) > max_output_bytes:
                                overflow = True
                                break
                    else:
                        chunk = os.read(fd, 4096 - len(report_bytes) + 1)
                        if not chunk:
                            report_eof = True
                        else:
                            report_bytes.extend(chunk)
                            if len(report_bytes) > 4096:
                                report_overflow = True
                                break
                if overflow or report_overflow:
                    break
                if child_status is None:
                    waited, status = os.waitpid(pid, os.WNOHANG)
                    if waited == pid:
                        child_status = status
        finally:
            if timed_out or overflow or report_overflow:
                try:
                    os.killpg(pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if child_status is None:
                try:
                    _, child_status = os.waitpid(pid, 0)
                except ChildProcessError:
                    child_status = None
            for fd in (stdout_read, report_read):
                try:
                    os.close(fd)
                except OSError:
                    pass

        exit_code = (os.WEXITSTATUS(child_status)
                     if child_status is not None and os.WIFEXITED(child_status) else None)
        child_signal = (os.WTERMSIG(child_status)
                        if child_status is not None and os.WIFSIGNALED(child_status) else None)
        result = {
            "output": bytes(output),
            "report": json.loads(report_bytes.decode("utf-8")) if report_bytes and not report_overflow else {},
            "stdout_bytes": len(output),
            "exit_code": exit_code,
            "child_signal": child_signal,
            "timed_out": timed_out,
            "overflow": overflow,
            "report_overflow": report_overflow,
            "child_killed": child_signal == signal.SIGKILL,
        }
    after = _statvfs_available()
    result["tmpfs_cleanup_restored"] = after >= before - 65536
    return result


def run_probe():
    mounts = memory_mounts()
    shm = mounts.get("/dev/shm", {})
    report = {
        "mode": "archive_stream_chroot_synthetic_probe",
        "status": "blocked",
        "safe_for_untrusted_code": False,
        "project_code_executed": False,
        "tmpfs_filesystem": shm.get("filesystem"),
        "tmpfs_upper_bound_bytes": shm.get("total_bytes"),
        "safe_stream": {},
        "traversal_stream": {},
        "overflow": {},
        "timeout": {},
    }
    if os.geteuid() != 0 or shm.get("filesystem") != "tmpfs":
        report["reason"] = "root_or_bounded_tmpfs_unavailable"
        return report
    try:
        account = pwd.getpwnam("executor")
        seccomp_lib = _load_library()
        safe = _run_child(SAFE_PAYLOAD, max_output_bytes=65536,
                          timeout_seconds=8, uid=account.pw_uid,
                          gid=account.pw_gid, seccomp_lib=seccomp_lib)
        report["safe_stream"] = {
            k: v for k, v in safe.items() if k not in ("output",)
        }
        security = safe["report"]
        report["security"] = security
        if safe["exit_code"] != 0 or safe["timed_out"] or safe["overflow"]:
            report["reason"] = "safe_stream_child_failed"
            return report
        if not all(security.get(k) is True for k in
                   ("chroot_entered", "uid_dropped", "effective_capabilities_zero",
                    "no_new_privs", "seccomp_loaded")):
            report["reason"] = "security_primitives_not_proven"
            return report
        if security.get("fd_audit", {}).get("status") != "ok":
            report["reason"] = "fd_audit_failed"
            return report
        if not all(security.get(k) is True for k in
                   ("filesystem_write_denied", "network_denied",
                    "process_creation_denied")):
            report["reason"] = "child_policy_probe_failed"
            return report

        with tempfile.TemporaryDirectory(prefix="fr-archive-stream-out-", dir="/dev/shm") as temp:
            target = Path(temp) / "candidate"
            validated = validate_and_extract_tar(
                io.BytesIO(safe["output"]),
                target,
                allowed_paths=["package/manifest.json"],
                required_paths=["package/manifest.json"],
                max_files=1,
                max_file_bytes=128,
                max_total_bytes=128,
                max_archive_bytes=65536,
                max_elapsed_seconds=5,
                max_members=4,
            )
            extracted = (target / "package/manifest.json").read_bytes()
            report["safe_stream"].update({
                "archive_validation": "pass",
                "file_count": validated["file_count"],
                "total_bytes": validated["total_bytes"],
                "archive_sha256": validated["archive_sha256"],
                "extracted_sha256": hashlib.sha256(extracted).hexdigest(),
                "content_matches": extracted == SAFE_CONTENT,
                "state": validated["state"],
            })
            if extracted != SAFE_CONTENT or validated["state"] != "VALIDATED_NOT_PUBLISHED":
                report["reason"] = "safe_archive_content_mismatch"
                return report

        traversal = _run_child(TRAVERSAL_PAYLOAD, max_output_bytes=65536,
                               timeout_seconds=8, uid=account.pw_uid,
                               gid=account.pw_gid, seccomp_lib=seccomp_lib)
        with tempfile.TemporaryDirectory(prefix="fr-archive-stream-reject-", dir="/dev/shm") as temp:
            target = Path(temp) / "candidate"
            try:
                validate_and_extract_tar(
                    io.BytesIO(traversal["output"]), target,
                    allowed_paths=["package/manifest.json"],
                    required_paths=[], max_files=1, max_file_bytes=128,
                    max_total_bytes=128, max_archive_bytes=65536,
                    max_elapsed_seconds=5, max_members=4,
                )
                traversal_rejected = False
                traversal_error = "archive_unexpectedly_accepted"
            except ArchiveStreamError as exc:
                traversal_rejected = True
                traversal_error = str(exc)
            report["traversal_stream"] = {
                "child_exit_code": traversal["exit_code"],
                "rejected": traversal_rejected,
                "error": traversal_error,
                "target_absent": not target.exists(),
                "tmpfs_cleanup_restored": traversal["tmpfs_cleanup_restored"],
            }
            if not traversal_rejected or target.exists() or traversal["exit_code"] != 0:
                report["reason"] = "traversal_archive_not_rejected"
                return report

        overflow = _run_child(OVERFLOW_PAYLOAD, max_output_bytes=128,
                              timeout_seconds=8, uid=account.pw_uid,
                              gid=account.pw_gid, seccomp_lib=seccomp_lib)
        report["overflow"] = {k: v for k, v in overflow.items() if k != "output"}
        if not overflow["overflow"] or overflow["stdout_bytes"] != 129 or not overflow["child_killed"]:
            report["reason"] = "stdout_overflow_not_enforced"
            return report

        timeout = _run_child(TIMEOUT_PAYLOAD, max_output_bytes=65536,
                             timeout_seconds=1, uid=account.pw_uid,
                             gid=account.pw_gid, seccomp_lib=seccomp_lib)
        report["timeout"] = {k: v for k, v in timeout.items() if k != "output"}
        if not timeout["timed_out"] or not timeout["child_killed"]:
            report["reason"] = "external_deadline_not_enforced"
            return report

        report["status"] = "pass"
        return report
    except (OSError, ValueError, KeyError, ArchiveStreamError) as exc:
        report["reason"] = type(exc).__name__
        return report


if __name__ == "__main__":
    print("[ARCHIVE-STREAM-PROBE] " + json.dumps(run_probe(), sort_keys=True), flush=True)
