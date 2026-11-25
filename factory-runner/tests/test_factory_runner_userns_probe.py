import subprocess
import sys
import unittest
from pathlib import Path

from userns_probe import summarize_status


class UserNamespaceProbeSummaryTests(unittest.TestCase):
    def test_user_namespace_only_is_partial_not_available(self):
        child = {
            "user_namespace_created": True,
            "uid_map_written": True,
            "gid_map_written": True,
        }
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "partial")

    def test_full_namespace_and_tmpfs_quota_contract_is_available(self):
        keys = (
            "user_namespace_created", "uid_map_written", "gid_map_written",
            "mount_namespace_created", "mount_propagation_private",
            "tmpfs_mounted", "tmpfs_quota_enforced", "tmpfs_unmount_ok",
            "net_namespace_created", "pid_namespace_created",
            "pid_namespace_init_verified",
        )
        child = {key: True for key in keys}
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "available")

    def test_missing_tmpfs_quota_is_partial(self):
        keys = (
            "user_namespace_created", "uid_map_written", "gid_map_written",
            "mount_namespace_created", "mount_propagation_private",
            "tmpfs_mounted", "tmpfs_unmount_ok", "net_namespace_created",
            "pid_namespace_created", "pid_namespace_init_verified",
        )
        child = {key: True for key in keys}
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True), "partial")

    def test_parent_mount_leak_or_capability_change_fails_closed(self):
        child = {"user_namespace_created": True}
        self.assertEqual(summarize_status(child, parent_mount_leaked=True,
                                          parent_capabilities_unchanged=True),
                         "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=True,
                                          parent_sys_admin_before=True,
                                          parent_sys_admin_after=True),
                         "failed_cleanup_or_parent_state")
        self.assertEqual(summarize_status(child, parent_capabilities_unchanged=False),
                         "failed_cleanup_or_parent_state")

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
        result = _parse_security_context(status, 'docker-default (enforce)')
        self.assertTrue(result['cap_sys_admin_in_userns'])
        self.assertEqual(result['no_new_privs'], '1')
        self.assertEqual(result['seccomp_mode'], '2')
        self.assertEqual(result['apparmor_profile'], 'docker-default (enforce)')

    def test_security_context_handles_missing_capabilities(self):
        from userns_probe import _parse_security_context

        result = _parse_security_context('Name:\\tprobe\\n', None)
        self.assertIsNone(result['cap_sys_admin_in_userns'])
        self.assertIsNone(result['apparmor_profile'])

    def test_timeout_and_unavailable_userns(self):
        self.assertEqual(summarize_status({}, timed_out=True, parent_capabilities_unchanged=True), "timeout")
        self.assertEqual(summarize_status({}, parent_capabilities_unchanged=True), "blocked")


if __name__ == "__main__":
    unittest.main()
