"""Supervised Ephemeral Chroot Jail with Stream Confinement.

Factory Runner Stage 5B.2 (M170):
1. Ephemeral minimal rootfs in /dev/shm with exclusive per-execution directory.
2. Read-only workspace integration preventing modification of original project.
3. Stream confinement via stdout into trusted archive validator (max 30 MB).
4. Subreaper, FD auditing, Seccomp-BPF, drop privileges (UID 1001), oom_score_adj (+500).
5. No /data, no /proc, no /sys inside the jail; zero access to HA/Supervisor secrets.
6. Guaranteed cleanup on success, failure, and timeout.
"""
from __future__ import annotations

import ctypes
import errno
import hashlib
import io
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
from typing import Any, Callable, Dict, List, Optional, Sequence, Set, Tuple
import uuid

# Base directories and limits
DEFAULT_JAIL_BASE_DIR = "/dev/shm"
MAX_STREAM_BYTES = 30 * 1024 * 1024  # Strict 30 MB stream limit
MAX_WORKSPACE_COPY_BYTES = 50 * 1024 * 1024  # 50 MB max input workspace size
MAX_WORKSPACE_FILES = 10000
EXECUTOR_USER = "executor"
DEFAULT_EXECUTOR_UID = 1001
DEFAULT_EXECUTOR_GID = 1001
DEFAULT_JAIL_TIMEOUT_SECONDS = 60

# Linux prctl constants
PR_SET_NO_NEW_PRIVS = 38
PR_GET_NO_NEW_PRIVS = 39

# Sensitive filenames that must never be exposed or copied into the jail
SENSITIVE_FILENAMES = frozenset({
    ".git", ".ssh", ".aws", "options.json", "id_rsa", "id_ed25519",
    ".env", ".env.local", ".env.production", "SUPERVISOR_TOKEN",
})

# Import 5B.1 hardening and seccomp modules
try:
    import executor_hardening as hardening
except ImportError:
    hardening = None

try:
    import seccomp_policy as seccomp
except ImportError:
    seccomp = None

try:
    import archive_stream
except ImportError:
    archive_stream = None


WNOHANG = getattr(os, "WNOHANG", 1)
WIFEXITED = getattr(os, "WIFEXITED", lambda s: True)
WEXITSTATUS = getattr(os, "WEXITSTATUS", lambda s: s)
WIFSIGNALED = getattr(os, "WIFSIGNALED", lambda s: False)
WTERMSIG = getattr(os, "WTERMSIG", lambda s: 0)


class ChrootJailError(Exception):
    """Base exception for ephemeral chroot jail errors."""


class JailSecurityViolation(ChrootJailError):
    """A security boundary violation was detected (e.g. traversal, leak, symlink escape)."""


class JailPrivilegeError(ChrootJailError):
    """Missing necessary privileges or platform support for isolation."""


class JailStreamError(ChrootJailError):
    """Archive stream exceeded budgets, contained invalid headers, or was malformed."""


class JailExecutionTimeout(ChrootJailError):
    """The jailed worker exceeded its allotted wall-clock execution deadline."""


def get_executor_identity() -> Tuple[int, int]:
    """Resolve executor UID and GID safely."""
    if hardening is not None:
        uid = hardening.get_executor_uid()
        if uid is not None:
            return uid, DEFAULT_EXECUTOR_GID
    if platform.system() == "Linux":
        try:
            import pwd
            entry = pwd.getpwnam(EXECUTOR_USER)
            return entry.pw_uid, entry.pw_gid
        except (KeyError, ImportError):
            pass
    return DEFAULT_EXECUTOR_UID, DEFAULT_EXECUTOR_GID


def check_chroot_capability() -> Dict[str, Any]:
    """Check if the current runtime environment supports os.chroot safely.

    Returns a diagnostic dict with 'available', 'reason', 'euid', and 'platform'.
    """
    sys_platform = platform.system()
    euid = getattr(os, "geteuid", lambda: -1)()

    if sys_platform != "Linux":
        return {
            "available": False,
            "reason": f"unsupported_platform_{sys_platform.lower()}",
            "euid": euid,
            "platform": sys_platform,
        }

    if not hasattr(os, "chroot"):
        return {
            "available": False,
            "reason": "os_chroot_missing",
            "euid": euid,
            "platform": sys_platform,
        }

    # In Linux, chroot requires CAP_SYS_CHROOT or root (euid == 0)
    if euid != 0:
        # Check if CAP_SYS_CHROOT is in effective capability mask
        has_cap = False
        try:
            from isolation_backend_probe import effective_capabilities_via_capget
            caps = effective_capabilities_via_capget()
            # CAP_SYS_CHROOT is bit 18 (1 << 18)
            effective_mask = caps.get("effective", 0)
            if effective_mask & (1 << 18):
                has_cap = True
        except Exception:
            pass

        if not has_cap:
            return {
                "available": False,
                "reason": "insufficient_privileges_non_root",
                "euid": euid,
                "platform": sys_platform,
            }

    return {
        "available": True,
        "reason": "chroot_supported",
        "euid": euid,
        "platform": sys_platform,
    }


def _resolve_jail_base_dir(base_dir: Optional[str | Path] = None) -> Path:
    """Determine and validate the base directory for creating ephemeral jails."""
    if base_dir is None:
        env_base = os.environ.get("FR_JAIL_BASE_DIR")
        if env_base:
            base = Path(env_base)
        else:
            shm = Path(DEFAULT_JAIL_BASE_DIR)
            if shm.is_dir() and os.access(shm, os.W_OK):
                base = shm
            else:
                base = Path(tempfile.gettempdir())
    else:
        base = Path(base_dir)

    if not base.is_absolute():
        base = base.resolve()

    if not base.is_dir():
        raise JailSecurityViolation(f"jail_base_dir_not_directory: {base}")
    if base.is_symlink():
        raise JailSecurityViolation(f"jail_base_dir_is_symlink: {base}")

    return base


def prepare_ephemeral_rootfs(
    base_dir: Optional[str | Path] = None,
    execution_id: Optional[str] = None,
    executor_uid: Optional[int] = None,
    executor_gid: Optional[int] = None,
) -> Path:
    """Step 1: Construct a minimal ephemeral rootfs in /dev/shm.

    - Creates an exclusive directory per execution with mode 0755.
    - Sets up standard directories: bin, lib, usr/bin, usr/lib, dev, tmp, workspace, app.
    - Configures tmp as writable by executor (mode 01777 or 0700).
    - Configures workspace as read-only (mode 0555).
    - NEVER mounts or creates /data, /proc, or /sys inside the jail!
    - Zero access to Home Assistant or Supervisor credentials.
    """
    base = _resolve_jail_base_dir(base_dir)

    if executor_uid is None or executor_gid is None:
        res_uid, res_gid = get_executor_identity()
        executor_uid = executor_uid if executor_uid is not None else res_uid
        executor_gid = executor_gid if executor_gid is not None else res_gid

    jail_name = f"fr-jail-{execution_id or uuid.uuid4().hex}"
    jail_root = base / jail_name

    # Create root directory with mode 0755
    try:
        jail_root.mkdir(mode=0o755, parents=False, exist_ok=False)
    except OSError as exc:
        raise JailSecurityViolation(f"failed_to_create_jail_root: {exc}") from exc

    # Ensure permissions on jail_root
    try:
        os.chmod(jail_root, 0o755)
    except OSError:
        pass

    # Create directory layout
    dirs_to_create = [
        ("bin", 0o755, False),
        ("sbin", 0o755, False),
        ("lib", 0o755, False),
        ("usr", 0o755, False),
        ("usr/bin", 0o755, False),
        ("usr/lib", 0o755, False),
        ("dev", 0o755, False),
        ("app", 0o755, False),
        ("tmp", 0o1777, True),       # Writable by executor
        ("workspace", 0o555, False),  # Read-only
    ]

    for rel_path, mode, is_tmp in dirs_to_create:
        target = jail_root / rel_path
        target.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(target, mode)
        except OSError:
            pass

        if is_tmp and os.geteuid() == 0 if hasattr(os, "geteuid") else False:
            try:
                os.chown(target, executor_uid, executor_gid)
            except OSError:
                pass

    # Setup essential device nodes in dev/ if on Linux with root
    dev_dir = jail_root / "dev"
    if platform.system() == "Linux" and hasattr(os, "mknod") and getattr(os, "geteuid", lambda: -1)() == 0:
        devices = [
            ("null", stat.S_IFCHR | 0o666, os.makedev(1, 3)),
            ("zero", stat.S_IFCHR | 0o666, os.makedev(1, 5)),
            ("urandom", stat.S_IFCHR | 0o666, os.makedev(1, 9)),
        ]
        for dev_name, dev_mode, dev_id in devices:
            dev_path = dev_dir / dev_name
            if not dev_path.exists():
                try:
                    os.mknod(dev_path, dev_mode, dev_id)
                except OSError:
                    # If mknod fails (e.g. without CAP_MKNOD in docker-default), fallback to empty file
                    dev_path.touch(mode=0o666)
    else:
        # On non-root or simulated environments, ensure minimal dev stubs exist
        for dev_name in ("null", "zero", "urandom"):
            dev_path = dev_dir / dev_name
            if not dev_path.exists():
                try:
                    dev_path.touch(mode=0o666)
                except OSError:
                    pass

    # STRICT VERIFICATION: Ensure /data, /proc, and /sys are ABSENT
    for forbidden in ("data", "proc", "sys", "etc/shadow"):
        forbidden_path = jail_root / forbidden
        if forbidden_path.exists():
            cleanup_ephemeral_rootfs(jail_root)
            raise JailSecurityViolation(f"prohibited_path_in_jail: {forbidden}")

    return jail_root


def cleanup_ephemeral_rootfs(jail_root: str | Path) -> bool:
    """Robust cleanup of the ephemeral jail directory.

    Handles read-only files (0444) and directories (0555) by making them writable
    before unlinking/removing. Confirms complete removal.
    """
    path = Path(jail_root)
    if not path.exists():
        return True

    # Safety guard: path must contain 'fr-jail-' in name to prevent catastrophic rm -rf
    if "fr-jail-" not in path.name:
        raise JailSecurityViolation(f"refusing_cleanup_unrecognized_jail_path: {path}")

    def _remove_readonly(func, target_path, exc_info):
        try:
            os.chmod(target_path, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
            func(target_path)
        except Exception:
            pass

    # Walk bottom-up and fix permissions to ensure everything can be removed
    try:
        for root, dirs, files in os.walk(str(path), topdown=False, followlinks=False):
            for file_name in files:
                file_path = os.path.join(root, file_name)
                try:
                    os.chmod(file_path, 0o700)
                    os.unlink(file_path)
                except OSError:
                    pass
            for dir_name in dirs:
                dir_path = os.path.join(root, dir_name)
                try:
                    os.chmod(dir_path, 0o700)
                    os.rmdir(dir_path)
                except OSError:
                    pass

        # Finally remove the root directory
        if path.exists():
            os.chmod(path, 0o700)
            shutil.rmtree(path, onerror=_remove_readonly)
    except Exception:
        # Second attempt with rmtree if walk had any edge case
        try:
            shutil.rmtree(path, onerror=_remove_readonly)
        except Exception:
            return False

    return not path.exists()


def integrate_workspace(
    jail_root: Path,
    source_workspace: Path,
    allowed_rel_paths: Optional[Sequence[str]] = None,
    max_total_bytes: int = MAX_WORKSPACE_COPY_BYTES,
    max_files: int = MAX_WORKSPACE_FILES,
) -> Dict[str, Any]:
    """Step 2: Integrate the audited project workspace into the jail as read-only.

    Requirements:
    - Worker cannot modify original project (workspace is copied into jail/workspace).
    - Escapes, path traversals ('..'), and symlinks pointing outside the workspace are rejected.
    - Sensitive files (.git/config, .ssh, options.json, .env) are blocked.
    - All copied files are mode 0444; directories are mode 0555.
    - Root ownership ensures unprivileged executor (UID 1001) cannot alter them.
    """
    source = Path(source_workspace)
    if not source.is_absolute():
        source = source.resolve()

    if not source.is_dir():
        raise JailSecurityViolation(f"source_workspace_not_directory: {source}")
    if source.is_symlink():
        raise JailSecurityViolation(f"source_workspace_is_symlink: {source}")

    # Prevent directory overlap between source and jail
    jail_root = Path(jail_root).resolve()
    if source == jail_root or source in jail_root.parents or jail_root in source.parents:
        raise JailSecurityViolation("overlapping_source_and_jail_directories")

    target_workspace = jail_root / "workspace"
    if not target_workspace.is_dir():
        target_workspace.mkdir(parents=True, exist_ok=True)
    try:
        os.chmod(target_workspace, 0o755)  # Temporarily writable for population
    except OSError:
        pass

    allowed_set: Optional[Set[str]] = None
    if allowed_rel_paths is not None:
        allowed_set = set()
        for p in allowed_rel_paths:
            if not p or p.startswith("/") or ".." in p.split("/"):
                raise JailSecurityViolation(f"unsafe_allowed_path: {p}")
            allowed_set.add(p)

    total_bytes = 0
    file_count = 0

    # Walk through source workspace and copy safely
    for root, dirs, files in os.walk(str(source), followlinks=False):
        current_dir = Path(root)
        rel_dir = current_dir.relative_to(source)

        # Check for directory traversal or sensitive directory names
        for part in rel_dir.parts:
            if part in ("..", "") or part in SENSITIVE_FILENAMES:
                raise JailSecurityViolation(f"sensitive_or_unsafe_workspace_directory: {part}")

        # Ensure target subdirectory exists
        dest_dir = target_workspace / rel_dir
        dest_dir.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(dest_dir, 0o755)
        except OSError:
            pass

        for file_name in files:
            file_count += 1
            if file_count > max_files:
                raise JailSecurityViolation(f"workspace_file_count_budget_exceeded: {file_count}")

            # Check sensitive filenames
            if file_name in SENSITIVE_FILENAMES or (file_name.startswith(".env.") and file_name != ".env.example"):
                raise JailSecurityViolation(f"sensitive_file_in_workspace: {file_name}")

            src_file = current_dir / file_name
            rel_file_str = str((rel_dir / file_name).as_posix())

            # Path allowlist filter
            if allowed_set is not None and rel_file_str not in allowed_set:
                continue

            # Symlink validation
            if src_file.is_symlink():
                resolved = src_file.resolve()
                try:
                    resolved.relative_to(source)
                except ValueError:
                    raise JailSecurityViolation(f"symlink_escapes_workspace: {src_file} -> {resolved}")
                # For regular files, we do not allow symlinks to special files or directories
                if not resolved.is_file():
                    raise JailSecurityViolation(f"symlink_points_to_non_file: {src_file}")

            # File size checks
            try:
                st = src_file.lstat()
            except OSError as exc:
                raise JailSecurityViolation(f"cannot_stat_source_file: {exc}") from exc

            if not stat.S_ISREG(st.st_mode) and not stat.S_ISLNK(st.st_mode):
                raise JailSecurityViolation(f"unsupported_special_file_in_workspace: {src_file}")

            total_bytes += st.st_size
            if total_bytes > max_total_bytes:
                raise JailSecurityViolation(f"workspace_size_budget_exceeded: {total_bytes} bytes")

            dest_file = dest_dir / file_name
            # Copy file contents
            try:
                shutil.copy2(src_file, dest_file)
            except OSError as exc:
                raise JailSecurityViolation(f"failed_to_copy_workspace_file: {exc}") from exc

            # Set file as strictly read-only: 0444
            try:
                os.chmod(dest_file, 0o444)
            except OSError:
                pass

    # Post-copy: Set all directories in workspace to 0555 (read-exec, no write)
    for root, dirs, _files in os.walk(str(target_workspace), topdown=False, followlinks=False):
        for d in dirs:
            try:
                os.chmod(os.path.join(root, d), 0o555)
            except OSError:
                pass
    try:
        os.chmod(target_workspace, 0o555)
    except OSError:
        pass

    return {
        "files_copied": file_count,
        "total_bytes": total_bytes,
        "target_dir": str(target_workspace),
    }


def populate_minimal_runtime(jail_root: Path | str, binaries: Sequence[str | Path] = ()) -> List[str]:
    """Copy or hardlink minimal binaries into the jail if external command execution is needed.

    Ensures that requested executable paths are positioned correctly under
    jail_root/bin, jail_root/sbin, or jail_root/usr/bin with mode 0755.
    """
    jail = Path(jail_root)
    copied = []
    for bin_target in binaries:
        p = Path(bin_target)
        host_bin = None
        if p.is_file():
            host_bin = p
        else:
            resolved = shutil.which(str(bin_target))
            if resolved:
                host_bin = Path(resolved)
        if host_bin is None or not host_bin.is_file():
            continue

        if p.is_absolute():
            parts = p.parts[1:] if (p.drive or p.root) else p.parts
            dest = jail.joinpath(*parts)
        else:
            dest = jail / "usr" / "bin" / p.name

        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(host_bin, dest)
            os.chmod(dest, 0o755)
            copied.append(str(dest))
        except OSError:
            pass
    return copied


def validate_jail_tar_stream(
    stream: Any,
    output_dir: str | Path,
    *,
    allowed_paths: Sequence[str],
    required_paths: Sequence[str] = (),
    executable_paths: Sequence[str] = (),
    max_archive_bytes: int = MAX_STREAM_BYTES,
    max_elapsed_seconds: int = DEFAULT_JAIL_TIMEOUT_SECONDS,
) -> Dict[str, Any]:
    """Step 3: Integrate archive stream ingestion from the jailed worker.

    - Communication by stdout with the trusted parent process.
    - Strict 30 MB maximum archive limit (MAX_STREAM_BYTES).
    - Continuous validation of TAR headers via archive_stream.py.
    - Path traversal prevention, no symlinks/hardlinks, sha256 hashing.
    - Writes only to a private staging directory and moves only upon total validation.
    """
    if archive_stream is None:
        raise JailStreamError("archive_stream_module_unavailable")

    if max_archive_bytes > MAX_STREAM_BYTES:
        raise JailStreamError(f"max_archive_bytes_exceeds_jail_limit: {max_archive_bytes} > {MAX_STREAM_BYTES}")

    try:
        result = archive_stream.validate_and_extract_tar(
            stream,
            output_dir,
            allowed_paths=allowed_paths,
            required_paths=required_paths,
            executable_paths=executable_paths,
            max_archive_bytes=max_archive_bytes,
            max_elapsed_seconds=max_elapsed_seconds,
        )
        return result
    except archive_stream.ArchiveStreamError as exc:
        raise JailStreamError(str(exc)) from exc


def execute_jailed_command(
    jail_root: Path,
    command: Sequence[str],
    *,
    allowed_archive_paths: Sequence[str],
    output_staging_dir: Path,
    timeout_seconds: int = DEFAULT_JAIL_TIMEOUT_SECONDS,
    executor_uid: Optional[int] = None,
    executor_gid: Optional[int] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    """Run an authorized worker inside the ephemeral chroot jail with full confinement.

    Applies the full sequence:
    1. Verify privileges and paths.
    2. Setup subreaper in parent.
    3. Fork child process:
       - audit_and_close_unapproved_fds
       - configure_oom_score_adj(500)
       - os.chroot(jail_root) and os.chdir("/")
       - drop privileges (setgroups, setgid, setuid to executor_uid)
       - prctl(PR_SET_NO_NEW_PRIVS, 1)
       - seccomp_policy.install_restrictions()
       - execve command
    4. Parent reads stdout with max 30 MB stream limit into validate_jail_tar_stream.
    5. Parent kills process tree on timeout.
    6. Parent collets zombies and cleans up ephemeral rootfs.
    """
    if executor_uid is None or executor_gid is None:
        res_uid, res_gid = get_executor_identity()
        executor_uid = executor_uid if executor_uid is not None else res_uid
        executor_gid = executor_gid if executor_gid is not None else res_gid

    capability = check_chroot_capability()
    if not capability["available"]:
        raise JailPrivilegeError(f"cannot_execute_jail: {capability['reason']}")

    if hardening is not None:
        hardening.set_child_subreaper()

    if not command:
        raise JailSecurityViolation("empty_command")
    cmd_name = command[0]
    jail_cmd_path = jail_root / cmd_name.lstrip("/") if cmd_name.startswith("/") else jail_root / "usr" / "bin" / cmd_name
    if not jail_cmd_path.is_file():
        populate_minimal_runtime(jail_root, [cmd_name])

    stdout_read, stdout_write = os.pipe()
    stdin_fd = os.open(os.devnull, os.O_RDONLY)
    stderr_fd = os.open(os.devnull, os.O_WRONLY)

    clean_env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/tmp",
        "TMPDIR": "/tmp",
        "LC_ALL": "C",
    }
    if env:
        for k, v in env.items():
            if k not in ("SUPERVISOR_TOKEN", "RUNNER_AUTH_TOKEN", "GITHUB_PUBLISH_TOKEN"):
                clean_env[k] = v

    pid = os.fork()
    if pid == 0:
        # Child process: apply confinement in exact sequence
        try:
            os.close(stdout_read)
            os.dup2(stdin_fd, 0)
            os.dup2(stdout_write, 1)
            os.dup2(stderr_fd, 2)
            for fd in {stdin_fd, stdout_write, stderr_fd}:
                if fd > 2:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

            # 1. Audit and close unexpected file descriptors
            if hardening is not None:
                audit = hardening.audit_and_close_unapproved_fds([0, 1, 2])
                if audit.get("status") == "failed" and (audit.get("unexpected_remaining") or 0) > 0:
                    os._exit(80)

            # 2. Configure sacrificial OOM score
            if hardening is not None:
                hardening.configure_oom_score_adj(500)

            # 3. Enter chroot jail
            os.chroot(str(jail_root))
            os.chdir("/")

            # 4. Drop privileges irreversibly
            os.setgroups([])
            os.setgid(executor_gid)
            os.setuid(executor_uid)

            # 5. Apply NoNewPrivs
            libc = ctypes.CDLL(None, use_errno=True)
            if hasattr(libc, "prctl"):
                libc.prctl(ctypes.c_int(PR_SET_NO_NEW_PRIVS), ctypes.c_ulong(1), 0, 0, 0)

            # 6. Apply Seccomp-BPF policy
            if seccomp is not None:
                seccomp.install_restrictions()

            # 7. Execute authorized command
            os.execvpe(command[0], list(command), clean_env)
        except Exception:
            os._exit(81)

    # Parent process
    os.close(stdout_write)
    os.close(stdin_fd)
    os.close(stderr_fd)

    stream_obj = os.fdopen(stdout_read, "rb")
    timed_out = False
    validation_result = None
    extraction_error = None
    start_time = time.monotonic()

    try:
        validation_result = validate_jail_tar_stream(
            stream_obj,
            output_staging_dir,
            allowed_paths=allowed_archive_paths,
            max_archive_bytes=MAX_STREAM_BYTES,
            max_elapsed_seconds=timeout_seconds,
        )
    except Exception as exc:
        extraction_error = exc
    finally:
        try:
            stream_obj.close()
        except OSError:
            pass

    # Wait or terminate child process
    elapsed = time.monotonic() - start_time
    child_exit_code = None
    try:
        waited_pid, status = os.waitpid(pid, WNOHANG) if hasattr(os, "waitpid") else (0, 0)
        if waited_pid == pid:
            child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
        else:
            # Child is still running; if deadline passed or error occurred, kill
            if elapsed >= timeout_seconds or extraction_error is not None:
                timed_out = elapsed >= timeout_seconds
                if hardening is not None:
                    class _ProcessHandle:
                        def __init__(self, p):
                            self.pid = p
                        def poll(self):
                            return None
                        def kill(self):
                            try:
                                os.kill(self.pid, signal.SIGKILL)
                            except OSError:
                                pass
                        def wait(self, timeout=None):
                            pass

                    proc_handle = _ProcessHandle(pid)
                    hardening.terminate_process_tree(proc_handle, target_uid=executor_uid)
                else:
                    try:
                        os.kill(pid, getattr(signal, "SIGKILL", 9))
                    except OSError:
                        pass
                if hasattr(os, "waitpid"):
                    try:
                        _, status = os.waitpid(pid, 0)
                        child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
                    except OSError:
                        pass
            else:
                if hasattr(os, "waitpid"):
                    try:
                        _, status = os.waitpid(pid, 0)
                        child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
                    except OSError:
                        pass
    except (OSError, AttributeError):
        pass

    # Harvest residual zombies
    if hardening is not None:
        hardening.reap_zombies()

    # Always cleanup ephemeral rootfs
    cleanup_ephemeral_rootfs(jail_root)

    if timed_out:
        raise JailExecutionTimeout(f"jailed_process_timed_out_after_{timeout_seconds}s")

    if extraction_error is not None:
        raise extraction_error

    return {
        "ok": child_exit_code == 0,
        "exit_code": child_exit_code,
        "archive_result": validation_result,
        "elapsed_seconds": elapsed,
    }


def execute_jailed_python_worker(
    jail_root: Path,
    script_source_or_path: str | Path,
    *,
    args: Sequence[str] = (),
    allowed_archive_paths: Sequence[str],
    output_staging_dir: Path,
    timeout_seconds: int = DEFAULT_JAIL_TIMEOUT_SECONDS,
    executor_uid: Optional[int] = None,
    executor_gid: Optional[int] = None,
) -> Dict[str, Any]:
    """Execute a Python worker in-process inside the ephemeral chroot jail.

    This avoids copying Python runtime binaries and standard libraries into /dev/shm,
    executing the pre-loaded Python interpreter directly in-process after confinement.
    """
    if executor_uid is None or executor_gid is None:
        res_uid, res_gid = get_executor_identity()
        executor_uid = executor_uid if executor_uid is not None else res_uid
        executor_gid = executor_gid if executor_gid is not None else res_gid

    capability = check_chroot_capability()
    if not capability["available"]:
        raise JailPrivilegeError(f"cannot_execute_jail: {capability['reason']}")

    # Read code if path provided
    if isinstance(script_source_or_path, Path) or (isinstance(script_source_or_path, str) and os.path.isfile(script_source_or_path)):
        with open(script_source_or_path, "r", encoding="utf-8") as f:
            code_str = f.read()
    else:
        code_str = str(script_source_or_path)

    if hardening is not None:
        hardening.set_child_subreaper()

    stdout_read, stdout_write = os.pipe()
    stdin_fd = os.open(os.devnull, os.O_RDONLY)
    stderr_fd = os.open(os.devnull, os.O_WRONLY)

    pid = os.fork()
    if pid == 0:
        try:
            os.close(stdout_read)
            os.dup2(stdin_fd, 0)
            os.dup2(stdout_write, 1)
            os.dup2(stderr_fd, 2)
            for fd in {stdin_fd, stdout_write, stderr_fd}:
                if fd > 2:
                    try:
                        os.close(fd)
                    except OSError:
                        pass

            # 1. Audit and close unexpected file descriptors
            if hardening is not None:
                audit = hardening.audit_and_close_unapproved_fds([0, 1, 2])
                if audit.get("status") == "failed" and (audit.get("unexpected_remaining") or 0) > 0:
                    os._exit(80)

            # 2. Configure sacrificial OOM score
            if hardening is not None:
                hardening.configure_oom_score_adj(500)

            # 3. Enter chroot jail
            os.chroot(str(jail_root))
            os.chdir("/")

            # 4. Drop privileges irreversibly
            os.setgroups([])
            os.setgid(executor_gid)
            os.setuid(executor_uid)

            # 5. Apply NoNewPrivs
            libc = ctypes.CDLL(None, use_errno=True)
            if hasattr(libc, "prctl"):
                libc.prctl(ctypes.c_int(PR_SET_NO_NEW_PRIVS), ctypes.c_ulong(1), 0, 0, 0)

            # 6. Apply Seccomp-BPF policy
            if seccomp is not None:
                seccomp.install_restrictions()

            # 7. Execute in-process compiled python worker
            compiled = compile(code_str, "/app/worker.py", "exec")
            sys.argv = ["/app/worker.py", *list(args)]
            namespace = {
                "__name__": "__main__",
                "__file__": "/app/worker.py",
                "sys": sys,
                "os": os,
                "io": io,
                "json": json,
                "tarfile": tarfile,
                "hashlib": hashlib,
                "time": time,
            }
            exec(compiled, namespace, namespace)
            os._exit(0)
        except Exception:
            os._exit(82)

    # Parent process
    os.close(stdout_write)
    os.close(stdin_fd)
    os.close(stderr_fd)

    stream_obj = os.fdopen(stdout_read, "rb")
    timed_out = False
    validation_result = None
    extraction_error = None
    start_time = time.monotonic()

    try:
        validation_result = validate_jail_tar_stream(
            stream_obj,
            output_staging_dir,
            allowed_paths=allowed_archive_paths,
            max_archive_bytes=MAX_STREAM_BYTES,
            max_elapsed_seconds=timeout_seconds,
        )
    except Exception as exc:
        extraction_error = exc
    finally:
        try:
            stream_obj.close()
        except OSError:
            pass

    elapsed = time.monotonic() - start_time
    child_exit_code = None
    try:
        waited_pid, status = os.waitpid(pid, WNOHANG) if hasattr(os, "waitpid") else (0, 0)
        if waited_pid == pid:
            child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
        else:
            if elapsed >= timeout_seconds or extraction_error is not None:
                timed_out = elapsed >= timeout_seconds
                if hardening is not None:
                    class _ProcessHandle:
                        def __init__(self, p):
                            self.pid = p
                        def poll(self):
                            return None
                        def kill(self):
                            try:
                                os.kill(self.pid, signal.SIGKILL)
                            except OSError:
                                pass
                        def wait(self, timeout=None):
                            pass

                    proc_handle = _ProcessHandle(pid)
                    hardening.terminate_process_tree(proc_handle, target_uid=executor_uid)
                else:
                    try:
                        os.kill(pid, getattr(signal, "SIGKILL", 9))
                    except OSError:
                        pass
                if hasattr(os, "waitpid"):
                    try:
                        _, status = os.waitpid(pid, 0)
                        child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
                    except OSError:
                        pass
            else:
                if hasattr(os, "waitpid"):
                    try:
                        _, status = os.waitpid(pid, 0)
                        child_exit_code = WEXITSTATUS(status) if WIFEXITED(status) else status
                    except OSError:
                        pass
    except (OSError, AttributeError):
        pass

    if hardening is not None:
        hardening.reap_zombies()

    cleanup_ephemeral_rootfs(jail_root)

    if timed_out:
        raise JailExecutionTimeout(f"jailed_worker_timed_out_after_{timeout_seconds}s")

    if extraction_error is not None:
        raise extraction_error

    return {
        "ok": child_exit_code == 0,
        "exit_code": child_exit_code,
        "archive_result": validation_result,
        "elapsed_seconds": elapsed,
    }
