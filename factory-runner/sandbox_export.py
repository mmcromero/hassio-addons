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
import sys
import stat

class SandboxUnavailable(Exception):
    pass

def _directory_bytes(root, max_bytes):
    total = 0
    def unreadable(error):
        raise SandboxUnavailable("Exporter output cannot be inspected") from error
    for base, dirs, files in os.walk(root, followlinks=False, onerror=unreadable):
        if any((Path(base) / name).is_symlink() for name in dirs + files):
            raise SandboxUnavailable("Exporter output contains symlinks")
        for name in files:
            path = Path(base) / name
            try:
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode):
                    raise SandboxUnavailable("Exporter output contains special files")
                total += info.st_size
            except FileNotFoundError:
                continue
            if total > max_bytes:
                return total
    return total

def _limits(cpu_seconds, memory_bytes, max_file_bytes, *, process_limit=True):
    # Called by a fresh single-threaded helper, never preexec_fn in the HTTP
    # server. These limits do not replace a cgroup
    # aggregate limit for an entire descendant process tree.
    limits = [
        (resource.RLIMIT_CPU, cpu_seconds),
        (resource.RLIMIT_AS, memory_bytes),
        (resource.RLIMIT_FSIZE, max_file_bytes),
        (resource.RLIMIT_CORE, 0),
        (resource.RLIMIT_NOFILE, 128),
    ]
    if process_limit:
        limits.append((resource.RLIMIT_NPROC, 32))
    for key, val in limits:
        soft, hard = resource.getrlimit(key)
        actual = val if hard == resource.RLIM_INFINITY else min(val, hard)
        resource.setrlimit(key, (actual, actual))

def _require_aggregate_isolation():
    # Etapa 5: a namespace smoke test is not an aggregate containment proof.
    # No environment variable, client parameter or project profile may bypass this.
    raise SandboxUnavailable("Aggregate sandbox isolation not homologated")


def sandbox_export(*, source, target, script, sha, verify, env, max_output_bytes,
                   memory_bytes, cpu_seconds, elapsed_seconds):
    """Run only inside bwrap, with network off and no access to HA /data.

    Returns no captured output to avoid leaking private source data.
    The target must be a fresh isolated checkout, never a real distribution.
    """
    source, target = Path(source).absolute(), Path(target).absolute()
    if source.resolve() != source or target.resolve() != target:
        raise SandboxUnavailable("Symlink source/target rejected")
    if not source.is_dir() or not target.is_dir() or source == target:
        raise SandboxUnavailable("Invalid sandbox source/target")
    if source in target.parents or target in source.parents:
        raise SandboxUnavailable("Overlapping sandbox directories")
    bwrap = shutil.which("bwrap")
    if bwrap is None:
        raise SandboxUnavailable("Bubblewrap unavailable; unsafe exporter refused")
    if not isinstance(script, str) or script.startswith("/") or chr(92) in script or any(p in ("", ".", "..") for p in script.split("/")):
        raise SandboxUnavailable("Invalid script path")
    if not (source / script).is_file() or (source / script).resolve() != source / script:
        raise SandboxUnavailable("Pinned exporter not present or unsafe")
    if os.geteuid() == 0:
        # Never turn a failed namespace setup into host-root execution.
        raise SandboxUnavailable("Refusing exporter execution as root")
    if any(type(v) is not int or v <= 0 for v in
           (max_output_bytes, memory_bytes, cpu_seconds, elapsed_seconds)):
        raise SandboxUnavailable("Invalid sandbox resource budget")
    if _directory_bytes(target, max_output_bytes) > max_output_bytes:
        raise SandboxUnavailable("Exporter aggregate output limit exceeded")
    args = [bwrap, "--die-with-parent", "--unshare-user",
            "--uid", str(os.geteuid()), "--gid", str(os.getegid()),
            "--unshare-ipc", "--unshare-pid", "--unshare-net", "--unshare-uts",
            "--cap-drop", "ALL", "--clearenv",
            "--proc", "/proc", "--dev", "/dev",
            "--size", str(32 * 1024 * 1024), "--tmpfs", "/tmp",
            "--dir", "/source", "--dir", "/target", "--dir", "/runner",
            "--ro-bind", str(Path(__file__).resolve()), "/runner/sandbox_export.py",
            "--ro-bind", str(source), "/source",
            "--bind", str(target), "/target"]
    # Alpine uses /usr/bin, /bin and /lib; bind only system libraries/binaries.
    for folder in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(folder).exists():
            args.extend(["--ro-bind", folder, folder])
    # An exporter must not plant config/hooks/fsmonitor commands that the
    # parent would later execute outside the sandbox during git status.
    metadata = target / ".git"
    if metadata.exists() or metadata.is_symlink():
        if metadata.is_symlink() or not metadata.is_dir():
            raise SandboxUnavailable("Unsafe target Git metadata")
        args.extend(["--ro-bind", str(metadata), "/target/.git"])
    args.extend(["--chdir", "/source", "--setenv", "HOME", "/tmp",
                 "--setenv", "TMPDIR", "/tmp",
                 "--setenv", "PATH", "/usr/bin:/bin",
                 "--setenv", "GIT_CONFIG_GLOBAL", "/dev/null",
                 "--setenv", "GIT_CONFIG_NOSYSTEM", "1",
                 "--setenv", "GIT_TERMINAL_PROMPT", "0"])
    # Probe only the trusted bwrap/busybox binaries, never the exporter. Keep
    # its bounded diagnostic so EPERM/userns denial is distinguishable from an
    # exporter error; exporter output itself remains suppressed.
    safe_env = {k: env[k] for k in ("PATH", "LANG", "LC_ALL") if k in env}
    try:
        probe = subprocess.run(args + ["/bin/true"], env=safe_env,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE, timeout=10, start_new_session=True)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SandboxUnavailable("Bubblewrap namespace probe unavailable") from exc
    if probe.returncode:
        detail = probe.stderr.decode("utf-8", "replace")[:512].strip()
        raise SandboxUnavailable("Bubblewrap namespace probe failed: " + detail)
    _require_aggregate_isolation()
    # NPROC counts the service's real UID before unshare. Apply it only after
    # user/PID namespace setup, in a trusted read-only helper, before any
    # exporter code. The fixed process ceiling is unchanged.
    args.extend(["/usr/bin/python3", "-I", "/runner/sandbox_export.py", "--exec-limited",
                 str(cpu_seconds), str(memory_bytes), str(max_output_bytes),
                 "/usr/bin/python3", "-I", "/source/" + script,
                 "--commit", sha, "--target", "/target"])
    if verify:
        args.append("--verify")
    # Keep a bounded tmpfs, CPU seconds, address space and individual file size.
    # Aggregate disk usage is sampled, and process group killed on threshold.
    # A cgroup cap is still required for a hard aggregate CPU/RAM/PID budget.
    helper = [sys.executable, "-I", str(Path(__file__).resolve()), "--bootstrap-limited",
              str(cpu_seconds), str(memory_bytes), str(max_output_bytes), *args]
    p = subprocess.Popen(helper, cwd=source, env=safe_env, stdin=subprocess.DEVNULL,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         start_new_session=True)
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
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        if p.poll() is None:
            p.wait(timeout=10)

if __name__ == "__main__":
    if len(sys.argv) < 6 or sys.argv[1] not in ("--exec-limited", "--bootstrap-limited"):
        raise SystemExit("Internal sandbox helper only")
    if os.geteuid() == 0:
        raise SystemExit("Refusing sandbox helper execution as root")
    _limits(*(int(value) for value in sys.argv[2:5]), process_limit=sys.argv[1]=="--exec-limited")
    os.execvpe(sys.argv[5], sys.argv[5:], os.environ)
