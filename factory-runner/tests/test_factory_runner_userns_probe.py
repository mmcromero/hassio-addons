import json
import os
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path

from userns_probe import EXPECTED_APPARMOR_CONTEXT, _cleanup_scratch, summarize_status


def full_child():
    keys = (
        "user_namespace_created", "uid_map_written", "gid_map_written",
        "mount_namespace_created", "mount_propagation_private",
        "tmpfs_mounted", "tmpfs_mode_verified", "tmpfs_flags_verified", "tmpfs_quota_enforced",
        "tmpfs_unmount_ok", "mountpoint_restored", "net_namespace_created",
        "pid_namespace_created", "pid_namespace_init_verified",
    )
    return {
        **{key: True for key in keys},
        "helper_exit_code": 0,
        "child_security_context": {
            "cap_sys_admin_in_userns": True,
            "no_new_privs": "1",
            "apparmor_profile": EXPECTED_APPARMOR_CONTEXT,
        },
        "errors": {},
    }


class UserNamespaceProbeSummaryTests(unittest.TestCase):
    def test_parent_cleanup_removes_only_original_scratch_inode(self):
        scratch = Path(tempfile.mkdtemp(prefix="fr-userns-probe-"))
        initial = os.lstat(scratch)
        leaked, cleaned, error = _cleanup_scratch(str(scratch), initial)
        self.assertFalse(leaked)
        self.assertTrue(cleaned)
        self.assertIsNone(error)
        self.assertFalse(os.path.lexists(scratch))

    def test_parent_cleanup_refuses_replaced_scratch_directory(self):
        with tempfile.TemporaryDirectory(prefix="fr-userns-parent-") as parent:
            scratch = Path(parent) / "fr-userns-probe-target"
            moved = Path(parent) / "original"
            scratch.mkdir(mode=0o700)
            initial = os.lstat(scratch)
            scratch.rename(moved)
            scratch.mkdir(mode=0o700)
            leaked, cleaned, error = _cleanup_scratch(str(scratch), initial)
            self.assertFalse(leaked)
            self.assertFalse(cleaned)
            self.assertEqual(error, "SCRATCH_IDENTITY_CHANGED")
            self.assertTrue(scratch.is_dir())
            scratch.rmdir()
            moved.rmdir()

    def test_parent_cleanup_refuses_mountpoint(self):
        scratch = Path(tempfile.mkdtemp(prefix="fr-userns-probe-"))
        initial = os.lstat(scratch)
        with patch("userns_probe.os.path.ismount", return_value=True):
            leaked, cleaned, error = _cleanup_scratch(str(scratch), initial)
        self.assertTrue(leaked)
        self.assertFalse(cleaned)
        self.assertEqual(error, "PARENT_MOUNT_LEAKED")
        self.assertTrue(scratch.is_dir())
        scratch.rmdir()

    def test_parent_cleanup_refuses_nonempty_directory(self):
        scratch = Path(tempfile.mkdtemp(prefix="fr-userns-probe-"))
        initial = os.lstat(scratch)
        (scratch / "unexpected").write_text("x")
        leaked, cleaned, error = _cleanup_scratch(str(scratch), initial)
        self.assertFalse(leaked)
        self.assertFalse(cleaned)
        self.assertEqual(error, "OSError")
        (scratch / "unexpected").unlink()
        scratch.rmdir()

    def test_parent_cleanup_refuses_special_mode_bits(self):
        scratch = Path(tempfile.mkdtemp(prefix="fr-userns-probe-"))
        initial = os.lstat(scratch)
        os.chmod(scratch, 0o4700)
        leaked, cleaned, error = _cleanup_scratch(str(scratch), initial)
        self.assertFalse(leaked)
        self.assertFalse(cleaned)
        self.assertEqual(error, "SCRATCH_IDENTITY_CHANGED")
        os.chmod(scratch, 0o700)
        scratch.rmdir()


    def test_user_namespace_only_is_partial_not_available(self):
        child = {"user_namespace_created": True, "uid_map_written": True,
                 "gid_map_written": True, "helper_exit_code": 0, "errors": {}}
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_full_namespace_and_tmpfs_contract_is_available(self):
        self.assertEqual(summarize_status(
            full_child(), scratch_cleanup_ok=True,
            parent_capabilities_unchanged=True
        ), "available")

    def test_available_requires_userns_sys_admin_and_no_new_privs(self):
        child = full_child()
        child["child_security_context"]["no_new_privs"] = "0"
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")
        child["child_security_context"]["no_new_privs"] = "1"
        child["child_security_context"]["cap_sys_admin_in_userns"] = False
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_wrong_or_missing_apparmor_context_never_reports_available(self):
        child = full_child()
        for value in (
            "45c28620_fabrica_software//fr_userns_probe (complain)",
            "docker-default (enforce)",
            None,
        ):
            child["child_security_context"]["apparmor_profile"] = value
            self.assertEqual(summarize_status(
                child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
            ), "partial")

    def test_missing_tmpfs_security_flags_is_partial(self):
        child = full_child()
        child["tmpfs_flags_verified"] = False
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_missing_tmpfs_mode_or_restoration_is_partial(self):
        child = full_child()
        child["tmpfs_mode_verified"] = False
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")
        child = full_child()
        child["mountpoint_restored"] = False
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_nonzero_helper_exit_or_any_probe_error_never_reports_available(self):
        child = full_child()
        child["helper_exit_code"] = 9
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "blocked")
        child["helper_exit_code"] = 0
        child["errors"] = {"tmpfs_write": "EIO"}
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_missing_helper_exit_or_error_object_never_reports_available(self):
        child = full_child()
        child.pop("helper_exit_code")
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "blocked")
        child = full_child()
        child.pop("errors")
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")
        child = full_child()
        child["errors"] = None
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "partial")

    def test_scratch_cleanup_failure_is_fatal(self):
        self.assertEqual(summarize_status(
            full_child(), scratch_cleanup_ok=False,
            parent_capabilities_unchanged=True
        ), "failed_cleanup_or_parent_state")

    def test_parent_mount_leak_or_capability_change_fails_closed(self):
        child = full_child()
        self.assertEqual(summarize_status(
            child, parent_mount_leaked=True, scratch_cleanup_ok=True,
            parent_capabilities_unchanged=True
        ), "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=False
        ), "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(
            child, scratch_cleanup_ok=True, parent_capabilities_unchanged=True,
            parent_sys_admin_before=True, parent_sys_admin_after=True
        ), "failed_cleanup_or_parent_state")

    def test_import_works_under_python_isolated_mode(self):
        app_dir = Path(__file__).resolve().parents[1]
        script = app_dir / "userns_probe.py"
        result = subprocess.run(
            [sys.executable, "-I", "-c",
             "import runpy, sys; runpy.run_path(sys.argv[1], run_name='probe_import')",
             str(script)],
            capture_output=True, text=True, timeout=5,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_manifest_identity_and_root_ingress_contract(self):
        app_dir = Path(__file__).resolve().parents[1]
        manifest = (app_dir / "config.yaml").read_text(encoding="utf-8")
        self.assertIn('name: "Fábrica de Ideias - Factory Runner"', manifest)
        self.assertNotIn("ingress_entry:", manifest)

    def test_security_context_parses_user_namespace_cap_sys_admin(self):
        from userns_probe import _parse_security_context
        status = "Name:\tprobe\nCapEff:\t0000000000200000\nNoNewPrivs:\t1\nSeccomp:\t2\n"
        result = _parse_security_context(status, "docker-default (enforce)")
        self.assertTrue(result["cap_sys_admin_in_userns"])
        self.assertEqual(result["no_new_privs"], "1")
        self.assertEqual(result["seccomp_mode"], "2")
        self.assertEqual(result["apparmor_profile"], "docker-default (enforce)")

    def test_security_context_handles_missing_capabilities(self):
        from userns_probe import _parse_security_context
        result = _parse_security_context("Name:\tprobe\n", None)
        self.assertIsNone(result["cap_sys_admin_in_userns"])
        self.assertIsNone(result["apparmor_profile"])

    def test_timeout_and_unavailable_userns(self):
        self.assertEqual(summarize_status(
            {}, timed_out=True, scratch_cleanup_ok=True,
            parent_capabilities_unchanged=True
        ), "timeout")
        self.assertEqual(summarize_status(
            {}, scratch_cleanup_ok=True, parent_capabilities_unchanged=True
        ), "blocked")

    def test_native_helper_is_built_and_rejects_untrusted_scratch_paths(self):
        app_dir = Path(__file__).resolve().parents[1]
        helper = Path("/app/fr-userns-probe")
        if not helper.exists():
            helper = app_dir / "fr-userns-probe"
        self.assertTrue(helper.is_file(),
                        "native helper must be built in Docker validation stage")
        self.assertTrue(os.access(helper, os.X_OK))
        result = subprocess.run(
            [str(helper), "/tmp"], capture_output=True, text=True, timeout=3
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["user_namespace_created"])
        self.assertEqual(payload["errors"]["user_namespace"], "INVALID_SCRATCH")

    def test_native_helper_reports_real_probe_without_claiming_success(self):
        app_dir = Path(__file__).resolve().parents[1]
        helper = Path("/app/fr-userns-probe")
        if not helper.exists():
            helper = app_dir / "fr-userns-probe"
        with tempfile.TemporaryDirectory(
            prefix="fr-userns-probe-", dir="/tmp"
        ) as scratch:
            os.chmod(scratch, 0o700)
            result = subprocess.run(
                [str(helper), scratch], capture_output=True, text=True, timeout=8
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        for key in (
            "user_namespace_created", "uid_map_written", "gid_map_written",
            "mount_namespace_created", "mount_propagation_private",
            "tmpfs_mounted", "tmpfs_mode_verified", "tmpfs_mode",
            "tmpfs_flags_verified", "tmpfs_flags", "tmpfs_size_bytes",
            "tmpfs_quota_enforced", "tmpfs_unmount_ok",
            "mountpoint_restored", "net_namespace_created",
            "pid_namespace_created", "pid_namespace_init_verified",
            "child_security_context", "errors",
        ):
            self.assertIn(key, payload)
        self.assertEqual(payload["child_security_context"]["no_new_privs"], "1")
        if not payload["mount_propagation_private"]:
            self.assertFalse(payload["tmpfs_mounted"])
        if payload["tmpfs_mounted"]:
            self.assertTrue(payload["mount_propagation_private"])
            self.assertTrue(payload["tmpfs_mode_verified"])
            self.assertEqual(payload["tmpfs_mode"], 0o700)
            self.assertTrue(payload["tmpfs_flags_verified"])
            self.assertTrue(payload["tmpfs_unmount_ok"])
            self.assertTrue(payload["mountpoint_restored"])
        self.assertIsInstance(payload["errors"], dict)

    def test_native_helper_rejects_special_bits_on_scratch(self):
        app_dir = Path(__file__).resolve().parents[1]
        helper = Path("/app/fr-userns-probe")
        if not helper.exists():
            helper = app_dir / "fr-userns-probe"
        with tempfile.TemporaryDirectory(
            prefix="fr-userns-probe-", dir="/tmp"
        ) as scratch:
            os.chmod(scratch, 0o4700)
            result = subprocess.run(
                [str(helper), scratch], capture_output=True, text=True, timeout=3
            )
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["user_namespace_created"])
        self.assertEqual(payload["errors"]["user_namespace"], "INVALID_SCRATCH")

    def test_native_helper_rejects_symlink_scratch(self):
        app_dir = Path(__file__).resolve().parents[1]
        helper = Path("/app/fr-userns-probe")
        if not helper.exists():
            helper = app_dir / "fr-userns-probe"
        with tempfile.TemporaryDirectory(prefix="fr-userns-target-") as parent:
            target = Path(parent) / "target"
            target.mkdir(mode=0o700)
            fd, link_name = tempfile.mkstemp(prefix="fr-userns-probe-", dir="/tmp")
            os.close(fd)
            os.unlink(link_name)
            link = Path(link_name)
            link.symlink_to(target, target_is_directory=True)
            try:
                result = subprocess.run(
                    [str(helper), str(link)], capture_output=True, text=True, timeout=3
                )
            finally:
                link.unlink(missing_ok=True)
        payload = json.loads(result.stdout)
        self.assertFalse(payload["user_namespace_created"])
        self.assertEqual(payload["errors"]["user_namespace"], "INVALID_SCRATCH")

    def test_helper_launcher_uses_clean_environment_and_fails_closed_when_missing(self):
        from userns_probe import _run_helper
        with tempfile.TemporaryDirectory(prefix="fr-userns-probe-") as scratch:
            result = _run_helper("/missing/fr-userns-probe", scratch)
        self.assertIsNone(result["helper_exit_code"])
        self.assertIn("helper_launch", result["child"]["errors"])

    def test_probe_never_claims_sandbox_safety(self):
        from userns_probe import run_probe
        result = run_probe(helper_path="/missing/fr-userns-probe")
        self.assertFalse(result["safe_for_untrusted_code"])
        self.assertFalse(result["project_code_executed"])
        self.assertIn(result["status"], ("blocked", "failed_cleanup_or_parent_state"))


if __name__ == "__main__":
    unittest.main()
