"""Fail-closed sandbox for executing a pinned project exporter.

The Home Assistant add-on has no Docker socket or privileged host access.
Bubblewrap needs working user/mount namespaces; never fall back to unsafe
in-container Python execution when those namespaces are unavailable.
"""
import os
from pathlib import Path
import resource
import shutil
import signal
import subprocess
import time

class SandboxUnavailable(Exception):
    pass

def _directory_bytes(root, max_bytes):
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in files:
            path = Path(base) / name
            try:
                total += path.lstat().st_size
            except FileNotFoundError:
                continue
            if total > max_bytes:
                return total
    return total

def _limits(cpu_seconds, memory_bytes, max_file_bytes):
    # Called in child, before exec. These limits do not replace a cgroup
    # aggregate limit for an entire descendant process tree.
    os.setsid()
    for key, val in [
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_FSIZE, max_file_bytes),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 128),
        (resource.RLIMIT_NPROC, 32)
    ]:
        soft, hard = resource.getrlimit(key)
        actual = val if hard == resource.RLIM_INFINITY else min(val, hard)
        resource.setrlimit(key, (actual, actual))

def sandbox_export(*, source, target, script, sha, verify, env, max_output_bytes,
                   memory_bytes, cpu_seconds, elapsed_seconds):
    """Run only inside bwrap, with network off and no access to HA /data.

    Returns no captured output to avoid leaking private source data.
    The target must be a fresh isolated checkout, never a real distribution.
    """
    source, target = Path(source).resolve(), Path(target).resolve()
    if not source.is_dir() or not target.is_dir() or source == target:
        raise SandboxUnavailable("Invalid sandbox source/target")
    if shutil.which("bwrap") is None:
        raise SandboxUnavailable("Bubblewrap unavailable; unsafe exporter refused")
    if not isinstance(script, str) or script.startswith("/") or ".." in script.split("/"):
        raise SandboxUnavailable("Invalid script path")
    if not (source / script).is_file() or (source / script).is_symlink():
        raise SandboxUnavailable("Pinned exporter not present or unsafe")
    if target.is_symlink():
        raise SandboxUnavailable("Symlink target rejected")
    if os.geteuid() == 0:
        # Never turn a failed namespace setup into host-root execution.
        raise SandboxUnavailable("Refusing exporter execution as root")
    args = ["bwrap", "--die-with-parent", "--unshare-user",
            "--unshare-ipc", "--unshare-pid", "--unshare-net", "--unshare-uts",
            "--proc", "/proc", "--dev", "/dev",
            "--size", str(32 * 1024 * 1024), "--tmpfs", "/tmp",
            "--dir", "/source", "--dir", "/target",
            "--ro-bind", str(source), "/source",
            "--bind", str(target), "/target"]
    # Alpine uses /usr/bin, /bin and /lib; bind only system libraries/binaries.
    for folder in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(folder).exists():
            args.extend(["--ro-bind", folder, folder])
    args.extend(["--chdir", "/source", "--setenv", "HOME", "/tmp",
                 "--setenv", "TMPDIR", "/tmp",
                 "/usr/bin/python3", "-I", "/source/" + script,
                 "--commit", sha, "--target", "/target"])
    if verify:
        args.append("--verify")
    # Keep a bounded tmpfs, CPU seconds, address space and individual file size.
    # Aggregate disk usage is sampled, and process group killed on threshold.
    # A cgroup cap is still required for a hard aggregate CPU/RAM/PID budget.
    p = subprocess.Popen(args, cwd=source, env=env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         preexec_fn=lambda: _limits(cpu_seconds, memory_bytes, max_output_bytes))
    start = time.monotonic()
    try:
        while p.poll() is None:
            if time.monotonic() - start > elapsed_seconds:
                raise SandboxUnavailable("Exporter elapsed-time limit exceeded")
            if _directory_bytes(target, max_output_bytes) > max_output_bytes:
                raise SandboxUnavailable("Exporter aggregate output limit exceeded")
            time.sleep(0.15)
        if p.returncode:
            raise SandboxUnavailable("Sandboxed exporter failed, exit " + str(p.returncode))
        if _directory_bytes(target, max_output_bytes) > max_output_bytes:
            raise SandboxUnavailable("Exporter aggregate output limit exceeded")
        for directory, subdirs, files in os.walk(target, followlinks=False):
            if any((Path(directory) / name).is_symlink() for name in subdirs + files):
                raise SandboxUnavailable("Exporter output contains symlinks")
    finally:
        if p.poll() is None:
            os.killpg(p.pid, signal.SIGKILL)
            p.wait(timeout=10)
