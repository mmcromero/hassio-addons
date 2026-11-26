"""Hardening primitives for orchestrator subprocess management and worker confinement.

Part of Factory Runner Stage 5B.1 (Mission M167):
- PR_SET_CHILD_SUBREAPER for adoption and reaping of orphaned descendants.
- Compulsory file descriptor audit and sanitization (closing unapproved FDs).
- Sacrificial process OOM score adjustment (oom_score_adj = +500).
- Guaranteed UID-scoped process tree termination and zombie cleanup.
"""
from __future__ import annotations

import ctypes
import errno
import os
from pathlib import Path
import platform
import signal
import subprocess
import sys
from typing import Iterable, Sequence

SIGKILL = getattr(signal, "SIGKILL", 9)
SIGTERM = getattr(signal, "SIGTERM", 15)
PR_SET_CHILD_SUBREAPER = 36
PR_GET_CHILD_SUBREAPER = 37


def set_child_subreaper() -> bool:
    """Mark the calling process as a subreaper for all child descendants.

    When a child process exits after creating descendants (e.g. via double-fork
    or daemonization), those descendants will be reparented to this process
    rather than PID 1 (init / S6-overlay).

    Returns True if successfully set, or False if unsupported on this OS.
    """
    if platform.system() != "Linux":
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if not hasattr(libc, "prctl"):
            return False
        libc.prctl.restype = ctypes.c_int
        res = libc.prctl(
            ctypes.c_int(PR_SET_CHILD_SUBREAPER),
            ctypes.c_ulong(1),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
        )
        return res == 0
    except (OSError, AttributeError):
        return False


def get_child_subreaper() -> bool:
    """Check if the calling process is currently configured as a child subreaper."""
    if platform.system() != "Linux":
        return False
    try:
        libc = ctypes.CDLL(None, use_errno=True)
        if not hasattr(libc, "prctl"):
            return False
        value = ctypes.c_int(0)
        libc.prctl.restype = ctypes.c_int
        res = libc.prctl(
            ctypes.c_int(PR_GET_CHILD_SUBREAPER),
            ctypes.byref(value),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
            ctypes.c_ulong(0),
        )
        return res == 0 and value.value == 1
    except (OSError, AttributeError):
        return False


def reap_zombies() -> list[int]:
    """Reap any terminated child/descendant processes adopted by this subreaper.

    Uses non-blocking os.waitpid(-1, os.WNOHANG).
    Returns the list of reaped process IDs.
    """
    reaped: list[int] = []
    if not hasattr(os, "waitpid") or not hasattr(os, "WNOHANG"):
        return reaped
    while True:
        try:
            pid, _status = os.waitpid(-1, os.WNOHANG)
            if pid <= 0:
                break
            reaped.append(pid)
        except (ChildProcessError, OSError):
            break
    return reaped


def _snapshot_open_fds(proc_path: Path | str = "/proc") -> list[int]:
    """List file descriptors currently open in the calling process."""
    fd_dir = Path(proc_path) / "self" / "fd"
    if fd_dir.is_dir():
        names = os.listdir(fd_dir)
        result = []
        for name in names:
            if not name.isdigit():
                continue
            fd = int(name)
            try:
                os.fstat(fd)
                result.append(fd)
            except OSError as exc:
                if exc.errno == errno.EBADF:
                    continue
                raise
        return sorted(result)

    # Fallback when /proc/self/fd is not mounted: probe standard range 0..1024
    result = []
    for fd in range(1024):
        try:
            os.fstat(fd)
            result.append(fd)
        except OSError:
            pass
    return sorted(result)


def audit_and_close_unapproved_fds(
    allowed_fds: Iterable[int],
    *,
    proc_path: Path | str = "/proc",
) -> dict:
    """Inspect all open descriptors and close any that are not explicitly approved.

    Ensures child worker processes never inherit sensitive open files,
    database handles, tokens, or sockets from parent services.
    """
    allowed = {int(fd) for fd in allowed_fds if int(fd) >= 0}
    try:
        before = _snapshot_open_fds(proc_path)
    except OSError as exc:
        return {
            "status": "unavailable",
            "errno": exc.errno,
            "before_count": None,
            "closed_count": 0,
            "remaining_count": None,
            "unexpected_remaining": None,
        }

    unexpected = [fd for fd in before if fd not in allowed]
    close_errors = 0
    for fd in unexpected:
        try:
            os.close(fd)
        except OSError as exc:
            if exc.errno != errno.EBADF:
                close_errors += 1

    try:
        after = _snapshot_open_fds(proc_path)
    except OSError as exc:
        return {
            "status": "post_close_unavailable",
            "errno": exc.errno,
            "before_count": len(before),
            "closed_count": len(unexpected),
            "remaining_count": None,
            "unexpected_remaining": None,
        }

    unexpected_after = [fd for fd in after if fd not in allowed]
    allowed_missing = [fd for fd in allowed if fd not in after and fd in before]
    ok = not close_errors and not unexpected_after and not allowed_missing

    return {
        "status": "ok" if ok else "failed",
        "before_count": len(before),
        "closed_count": len(unexpected),
        "remaining_count": len(after),
        "unexpected_remaining": len(unexpected_after),
        "allowed_missing": len(allowed_missing),
        "close_errors": close_errors,
    }


def configure_oom_score_adj(
    score: int = 500,
    pid: int | str = "self",
    *,
    proc_path: Path | str = "/proc",
) -> dict:
    """Adjust oom_score_adj to mark a sacrificial worker process for the Linux OOM killer.

    An unprivileged process can only increase its score (making itself more likely
    to be chosen by the OOM killer). Setting +500 ensures that if an untrusted job
    triggers an OOM condition, the kernel sacrifices the worker tree first,
    protecting the Home Assistant OS and core services.

    Acceptable range: 0 to 1000.
    """
    if type(score) is not int or not 0 <= score <= 1000:
        return {
            "status": "invalid_score",
            "configured_score": None,
            "previous_score": None,
            "target_pid": pid,
            "error": "score must be an integer between 0 and 1000",
        }

    target_file = Path(proc_path) / str(pid) / "oom_score_adj"

    if str(proc_path) == "/proc" and platform.system() != "Linux":
        return {
            "status": "unsupported_platform",
            "configured_score": None,
            "previous_score": None,
            "target_pid": pid,
            "target_path": str(target_file),
        }

    if not target_file.exists():
        return {
            "status": "proc_unavailable",
            "configured_score": None,
            "previous_score": None,
            "target_pid": pid,
            "target_path": str(target_file),
        }

    previous_score = None
    try:
        prev_raw = target_file.read_text(encoding="ascii").strip()
        previous_score = int(prev_raw)
    except (OSError, ValueError):
        pass

    try:
        target_file.write_text(f"{score}\n", encoding="ascii")
    except PermissionError:
        return {
            "status": "permission_denied",
            "configured_score": None,
            "previous_score": previous_score,
            "target_pid": pid,
            "target_path": str(target_file),
        }
    except OSError as exc:
        return {
            "status": "error",
            "errno": exc.errno,
            "configured_score": None,
            "previous_score": previous_score,
            "target_pid": pid,
            "target_path": str(target_file),
        }

    # Verify write
    try:
        new_raw = target_file.read_text(encoding="ascii").strip()
        new_score = int(new_raw)
        if new_score != score:
            return {
                "status": "verification_failed",
                "configured_score": new_score,
                "previous_score": previous_score,
                "target_pid": pid,
            }
    except (OSError, ValueError):
        return {
            "status": "verification_unreadable",
            "configured_score": None,
            "previous_score": previous_score,
            "target_pid": pid,
        }

    return {
        "status": "ok",
        "configured_score": score,
        "previous_score": previous_score,
        "target_pid": pid,
        "target_path": str(target_file),
    }


def get_executor_uid() -> int | None:
    """Retrieve the numeric UID of the dedicated executor account if present."""
    try:
        import pwd
        return pwd.getpwnam("executor").pw_uid
    except (ImportError, KeyError, OSError, AttributeError):
        return None


def find_processes_by_uid(
    target_uid: int,
    *,
    proc_path: Path | str = "/proc",
) -> list[int]:
    """Find all running process IDs owned by target_uid.

    Safety constraint:
    Never matches if target_uid <= 0 (root/kernel) or if target_uid matches
    the current process's own UID, ensuring orchestrator or system services
    are never targeted.
    """
    if type(target_uid) is not int or target_uid <= 0:
        return []

    current_uid = os.geteuid() if hasattr(os, "geteuid") else None
    current_real_uid = os.getuid() if hasattr(os, "getuid") else None
    if target_uid in (current_uid, current_real_uid):
        return []

    proc = Path(proc_path)
    if not proc.is_dir():
        return []

    matched: list[int] = []
    own_pid = os.getpid()

    for entry in proc.iterdir():
        if not entry.name.isdigit():
            continue
        pid = int(entry.name)
        if pid == own_pid:
            continue
        try:
            stat_info = os.lstat(entry)
            if stat_info.st_uid == target_uid:
                matched.append(pid)
        except OSError:
            # Process may have exited between iterdir and lstat
            continue

    return sorted(matched)


def terminate_process_tree(
    process: subprocess.Popen | None = None,
    *,
    target_uid: int | None = None,
    timeout: float = 2.0,
    proc_path: Path | str = "/proc",
) -> dict:
    """Guarantee termination of direct process, process group, and any orphaned descendants.

    Combines:
    1. Process group termination (SIGTERM -> SIGKILL) for direct process tree.
    2. UID-scoped process scan and SIGKILL for processes created under target_uid
       that attempted to escape via setsid() or daemonization.
    3. Child subreaper reaping loop (waitpid) to collect all adopted zombies.
    """
    direct_killed = False
    group_killed = False
    uid_killed: list[int] = []

    # 1. Direct process and group termination
    if process is not None and process.poll() is None:
        direct_pid = process.pid
        if hasattr(os, "killpg"):
            try:
                os.killpg(direct_pid, SIGTERM)
                group_killed = True
            except (ProcessLookupError, OSError):
                pass
        try:
            process.terminate()
            direct_killed = True
        except (ProcessLookupError, OSError):
            pass

        try:
            process.wait(timeout=max(0.1, timeout / 2))
        except (subprocess.TimeoutExpired, OSError):
            if hasattr(os, "killpg"):
                try:
                    os.killpg(direct_pid, SIGKILL)
                except (ProcessLookupError, OSError):
                    pass
            try:
                process.kill()
                process.wait(timeout=max(0.1, timeout / 2))
            except (subprocess.TimeoutExpired, OSError, ProcessLookupError):
                pass

    # 2. UID-scoped termination for runaway or reparented processes
    if target_uid is not None and target_uid > 0:
        candidates = find_processes_by_uid(target_uid, proc_path=proc_path)
        for pid in candidates:
            try:
                os.kill(pid, SIGKILL)
                uid_killed.append(pid)
            except (ProcessLookupError, OSError):
                pass

    # 3. Subreaper zombie reaping
    reaped = reap_zombies()

    # 4. Check if any target_uid processes still linger
    remaining: list[int] = []
    if target_uid is not None and target_uid > 0:
        remaining = find_processes_by_uid(target_uid, proc_path=proc_path)

    return {
        "status": "ok" if not remaining else "lingering_processes",
        "direct_killed": direct_killed,
        "group_killed": group_killed,
        "uid_killed": uid_killed,
        "reaped_pids": reaped,
        "remaining_count": len(remaining),
        "remaining_pids": remaining,
    }
