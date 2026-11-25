#!/usr/bin/env python3
"""Read-only startup probe for Bubblewrap and inherited cgroup limits.

This is NOT a full security, resource-budget or workflow certification.
It runs as the non-root service UID, never mounts /data, never enables privileges,
and logs only bounded, sanitized numeric resource limits.
"""
import os
import json
from pathlib import Path
import shutil
import subprocess


def _read_cgroup_limit(path, kind):
    """Parse one cgroup-v2 limit without exposing its filesystem path."""
    try:
        raw = path.read_text(encoding="ascii").strip().split()
        if kind == "cpu":
            if len(raw) != 2 or int(raw[1]) <= 0:
                return None
            if raw[0] == "max":
                return {"quota_us": None, "period_us": int(raw[1]), "cores": None}
            quota = int(raw[0])
            if quota <= 0:
                return None
            period = int(raw[1])
            return {"quota_us": quota, "period_us": period,
                    "cores": round(quota / period, 6)}
        if len(raw) != 1:
            return None
        if raw[0] == "max":
            return "max"
        value = int(raw[0])
        return value if value >= 0 else None
    except (OSError, UnicodeError, ValueError, IndexError):
        return None


def _effective_cgroup_limits(levels):
    cpu = [v["cpu"] for v in levels
           if isinstance(v.get("cpu"), dict) and v["cpu"].get("cores") is not None]
    memory = [v["memory_bytes"] for v in levels
              if isinstance(v.get("memory_bytes"), int)]
    pids = [v["pids"] for v in levels if isinstance(v.get("pids"), int)]
    cpu_limit = min(cpu, key=lambda v: v["cores"]) if cpu else None
    return {
        "cpu_cores": cpu_limit["cores"] if cpu_limit else None,
        "cpu_quota_us": cpu_limit["quota_us"] if cpu_limit else None,
        "cpu_period_us": cpu_limit["period_us"] if cpu_limit else None,
        "memory_bytes": min(memory) if memory else None,
        "pids": min(pids) if pids else None,
        "has_finite_cpu_limit": bool(cpu),
        "has_finite_memory_limit": bool(memory),
        "has_finite_pids_limit": bool(pids),
    }


def cgroup_inventory(proc=Path("/proc/self"), mount=Path("/sys/fs/cgroup")):
    """Read-only feasibility diagnostic. Never creates or modifies a cgroup."""
    report = {"cgroup_v2": False, "mount_read_only": None,
              "controllers": [], "aggregate_controls_present": False,
              "delegation_candidate": False, "enforcement_verified": False,
              "hierarchy_levels": 0, "hierarchy_complete": False,
              "effective_limits": _effective_cgroup_limits([]),
              "safe_for_untrusted_code": False, "status": "unavailable"}
    try:
        matches = []
        for line in (proc / "mountinfo").read_text().splitlines():
            left, right = line.split(" - ", 1)
            fields, fs = left.split(), right.split()
            if fields[4] == str(mount) and fs[0] == "cgroup2":
                matches.append((fields, fs))
        if len(matches) != 1:
            return report
        fields, fs = matches[0]
        report["cgroup_v2"] = True
        report["mount_read_only"] = ("ro" in fields[5].split(",")
                                     or "ro" in fs[2].split(","))
        members = [line[3:] for line in (proc / "cgroup").read_text().splitlines()
                   if line.startswith("0::")]
        if len(members) != 1:
            return report
        member = members[0]
        root = fields[3]
        if (not member.startswith("/") or not root.startswith("/")
                or any(p in (".", "..") for p in member.split("/") + root.split("/"))
                or chr(92) in member or chr(92) in root):
            return report
        if root != "/" and member != root and not member.startswith(root + "/"):
            return report
        relative = member[len(root):].lstrip("/")
        current = mount / relative
        available = set((current / "cgroup.controllers").read_text().split())
        wanted = {"cpu", "memory", "pids"}
        report["controllers"] = sorted(available & wanted)
        controls = ("cpu.max", "memory.max", "pids.max", "cgroup.kill",
                    "cgroup.procs", "cgroup.subtree_control")
        report["aggregate_controls_present"] = all(
            (current / name).is_file() for name in controls)
        report["delegation_candidate"] = (
            os.geteuid() != 0 and not report["mount_read_only"]
            and wanted <= available and report["aggregate_controls_present"]
            and os.access(current, os.W_OK | os.X_OK)
            and os.access(current / "cgroup.subtree_control", os.W_OK)
            and os.access(current / "cgroup.procs", os.W_OK))

        # Read every visible ancestor up to the cgroup mount root. The tightest
        # finite value is the effective inherited hard ceiling for this container.
        levels = []
        node = current
        while True:
            levels.append({
                "cpu": _read_cgroup_limit(node / "cpu.max", "cpu"),
                "memory_bytes": _read_cgroup_limit(node / "memory.max", "scalar"),
                "pids": _read_cgroup_limit(node / "pids.max", "scalar"),
            })
            if node == mount:
                break
            if mount not in node.parents:
                return report
            node = node.parent
        report["hierarchy_levels"] = len(levels)
        report["hierarchy_complete"] = all(
            level["cpu"] is not None and level["memory_bytes"] is not None
            and level["pids"] is not None for level in levels)
        report["effective_limits"] = _effective_cgroup_limits(levels)
        report["status"] = "inventory_only"
    except (OSError, ValueError, IndexError):
        pass
    return report


def main():
    if os.geteuid() == 0:
        print("[ISOLATION] ERROR: expected non-root service", flush=True)
        return 0
    print("[ISOLATION-CGROUP] " + json.dumps(cgroup_inventory(), sort_keys=True), flush=True)
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
