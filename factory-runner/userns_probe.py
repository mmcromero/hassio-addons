#!/usr/bin/env python3
"""Fail-closed namespace/tmpfs diagnostic delegated to a dedicated ELF helper.

The helper is the only executable eligible for an AppArmor cx transition.
This diagnostic never executes project code and never changes host policy.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from isolation_backend_probe import effective_capabilities_via_capget, root_capabilities

HELPER_PATH = "/usr/local/libexec/fr-userns-probe"
CHILD_TIMEOUT_SECONDS = 6
EXPECTED_APPARMOR_CONTEXT = "45c28620_fabrica_software//fr_userns_probe (enforce)"


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


def _run_helper(helper_path: str, mountpoint: str):
    """Run only the fixed native helper, with a clean environment and FDs."""
    report = {}
    process = None
    try:
        process = subprocess.Popen(
            [helper_path, mountpoint],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            close_fds=True,
            start_new_session=True,
            env={"PATH": "/usr/bin:/bin", "HOME": "/nonexistent"},
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        try:
            stdout, _ = process.communicate(timeout=CHILD_TIMEOUT_SECONDS)
            report["helper_exit_code"] = process.returncode
        except subprocess.TimeoutExpired:
            try:
                os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            stdout, _ = process.communicate()
            report["timed_out"] = True
            report["helper_exit_code"] = process.returncode
        else:
            report["timed_out"] = False
        if stdout:
            try:
                report["child"] = json.loads(stdout.strip().splitlines()[-1])
            except (ValueError, IndexError):
                report["child"] = {"errors": {"helper_report": "invalid_json"}}
        else:
            report["child"] = {"errors": {"helper_report": "empty"}}
    except OSError as exc:
        report["timed_out"] = False
        report["helper_exit_code"] = None
        report["child"] = {"errors": {"helper_launch": type(exc).__name__}}
    return report


def summarize_status(child, *, timed_out=False, parent_mount_leaked=False,
                     scratch_cleanup_ok=False, parent_capabilities_unchanged=False,
                     parent_sys_admin_before=False, parent_sys_admin_after=False):
    if (parent_mount_leaked or not scratch_cleanup_ok or not parent_capabilities_unchanged
            or parent_sys_admin_before is not False
            or parent_sys_admin_after is not False):
        return "failed_cleanup_or_parent_state"
    if timed_out:
        return "timeout"
    if child.get("helper_exit_code") != 0:
        return "blocked"
    if child.get("user_namespace_created") is not True:
        return "blocked"
    errors = child.get("errors")
    if not isinstance(errors, dict) or errors:
        return "partial"
    security = child.get("child_security_context") or {}
    if (security.get("no_new_privs") != "1"
            or security.get("cap_sys_admin_in_userns") is not True
            or security.get("apparmor_profile") != EXPECTED_APPARMOR_CONTEXT):
        return "partial"
    required = (
        "uid_map_written", "gid_map_written", "mount_namespace_created",
        "mount_propagation_private", "tmpfs_mounted", "tmpfs_mode_verified", "tmpfs_flags_verified",
        "tmpfs_quota_enforced", "tmpfs_unmount_ok", "mountpoint_restored",
        "net_namespace_created", "pid_namespace_created",
        "pid_namespace_init_verified",
    )
    return "available" if all(child.get(key) is True for key in required) else "partial"


def _cleanup_scratch(mountpoint: str, initial_stat):
    """Remove only the exact 0700 directory created by this probe."""
    if os.path.ismount(mountpoint):
        return True, False, "PARENT_MOUNT_LEAKED"
    try:
        current = os.lstat(mountpoint)
    except OSError as exc:
        return False, False, type(exc).__name__
    if (not stat.S_ISDIR(current.st_mode)
            or current.st_uid != os.geteuid()
            or (current.st_mode & 0o7777) != 0o700
            or current.st_dev != initial_stat.st_dev
            or current.st_ino != initial_stat.st_ino):
        return False, False, "SCRATCH_IDENTITY_CHANGED"
    try:
        os.rmdir(mountpoint)
    except OSError as exc:
        return False, False, type(exc).__name__
    return False, not os.path.lexists(mountpoint), None


def run_probe(helper_path: str = HELPER_PATH):
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
    scratch_initial = os.lstat(mountpoint)
    parent_mount_leaked = False
    scratch_cleanup_ok = False
    try:
        helper = _run_helper(helper_path, mountpoint)
        result["child"] = helper.get("child", {})
        result["child"]["helper_exit_code"] = helper.get("helper_exit_code")
        result["timed_out"] = helper.get("timed_out", False)
        if helper.get("helper_exit_code") not in (0, None):
            result["child"].setdefault("errors", {})["helper_exit"] = str(helper["helper_exit_code"])
        if helper.get("helper_exit_code") is None:
            result["child"].setdefault("errors", {}).setdefault("helper", "unavailable")
    finally:
        (parent_mount_leaked, scratch_cleanup_ok,
         cleanup_error) = _cleanup_scratch(mountpoint, scratch_initial)
        if cleanup_error:
            result["scratch_cleanup_error"] = cleanup_error

    result["parent_mount_leaked"] = parent_mount_leaked
    result["scratch_cleanup_ok"] = scratch_cleanup_ok
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
        child, timed_out=result.get("timed_out", False),
        parent_mount_leaked=parent_mount_leaked,
        scratch_cleanup_ok=scratch_cleanup_ok,
        parent_capabilities_unchanged=result["parent_capabilities_unchanged"],
        parent_sys_admin_before=result["parent_sys_admin_before"],
        parent_sys_admin_after=result["parent_sys_admin_after"],
    )
    return result


if __name__ == "__main__":
    print("[USERNS-PROBE] " + json.dumps(run_probe(), sort_keys=True), flush=True)
