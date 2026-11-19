#!/usr/bin/env python3
"""Read-only startup probe for Bubblewrap under the actual Home Assistant add-on policy.

This is NOT a full security, resource-budget or workflow certification.
It runs as the non-root service UID, never mounts /data, never enables privileges,
and logs only PASS/BLOCKED/ERROR with a bounded diagnostic.
"""
import os
from pathlib import Path
import shutil
import subprocess

def main():
    if os.geteuid() == 0:
        print("[ISOLATION] ERROR: expected non-root service", flush=True)
        return 0
    bwrap = shutil.which("bwrap")
    if not bwrap:
        print("[ISOLATION] BLOCKED: bubblewrap executable unavailable", flush=True)
        return 0
    args = [bwrap, "--die-with-parent", "--unshare-user",
            "--uid", str(os.geteuid()), "--gid", str(os.getegid()),
            "--unshare-ipc", "--unshare-pid", "--unshare-net", "--unshare-uts",
            "--cap-drop", "ALL", "--clearenv", "--proc", "/proc",
            "--dev", "/dev", "--size", str(32 * 1024 * 1024),
            "--tmpfs", "/tmp", "--dir", "/source", "--dir", "/target",
            "--dir", "/runner"]
    for directory in ("/usr", "/bin", "/lib", "/lib64"):
        if Path(directory).exists():
            args.extend(("--ro-bind", directory, directory))
    args.extend(("--chdir", "/tmp", "/bin/true"))
    try:
        result = subprocess.run(args, env={"PATH": "/usr/bin:/bin"},
                                stdin=subprocess.DEVNULL,
                                stdout=subprocess.DEVNULL,
                                stderr=subprocess.PIPE, timeout=10, check=False)
        if result.returncode == 0:
            print("[ISOLATION] PASS: bubblewrap namespaces available to service UID; cgroup/quota/workflow NOT validated", flush=True)
        else:
            detail = result.stderr.decode("utf-8", "replace").strip().splitlines()
            reason = (detail[-1] if detail else "no diagnostic")
            # Only bounded diagnostics from our own local probe, never secret or input.
            reason = "".join(c for c in reason[:180] if c.isprintable())
            print("[ISOLATION] BLOCKED: bubblewrap probe exit " + str(result.returncode) + " (" + reason + ")", flush=True)
    except (OSError, subprocess.TimeoutExpired) as error:
        print("[ISOLATION] ERROR: probe could not execute (" + type(error).__name__ + ")", flush=True)
    return 0  # Only the probe is optional; /api/prepare still fails closed.

if __name__ == "__main__":
    raise SystemExit(main())
