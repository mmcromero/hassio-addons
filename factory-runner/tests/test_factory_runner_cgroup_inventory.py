import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from runtime_probe import cgroup_inventory


class CgroupInventoryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        root = Path(self.tmp.name)
        self.proc = root / "proc"
        self.mount = root / "cgroup"
        self.proc.mkdir()
        self.mount.mkdir()
        self.current = self.mount / "worker"
        self.current.mkdir()
        (self.proc / "cgroup").write_text("0::/worker" + chr(10))
        for name in ("cgroup.controllers", "cpu.max", "memory.max",
                     "memory.swap.max", "memory.oom.group", "pids.max",
                     "cgroup.kill", "cgroup.procs", "cgroup.subtree_control",
                     "cgroup.type", "cpu.stat", "memory.current", "memory.events",
                     "memory.swap.current", "pids.current", "pids.events",
                     "cgroup.events"):
            (self.current / name).touch()
        (self.current / "cpu.max").write_text("max 100000")
        (self.current / "memory.max").write_text("max")
        (self.current / "pids.max").write_text("max")
        # Every visible ancestor must expose parseable swap limits.
        (self.current / "memory.swap.max").write_text("max")
        (self.current / "cgroup.controllers").write_text("cpu memory pids io")
        (self.current / "cgroup.type").write_text("domain")
        for name, value in (("cpu.max", "max 100000"),
                            ("memory.max", "max"),
                            ("memory.swap.max", "max"),
                            ("pids.max", "max")):
            (self.mount / name).write_text(value)

    def mount_info(self, mode):
        (self.proc / "mountinfo").write_text(
            f"1 2 0:1 / {self.mount} {mode} - cgroup2 cgroup {mode}" + chr(10))

    def inspect(self):
        with patch("runtime_probe.os.geteuid", return_value=1000), patch(
                "runtime_probe.os.access", return_value=True):
            return cgroup_inventory(self.proc, self.mount)

    def test_readonly_mount_cannot_be_delegation_candidate(self):
        self.mount_info("ro")
        r = self.inspect()
        self.assertTrue(r["cgroup_v2"])
        self.assertTrue(r["aggregate_controls_present"])
        self.assertFalse(r["delegation_candidate"])
        self.assertFalse(r["enforcement_verified"])
        self.assertFalse(r["safe_for_untrusted_code"])

    def test_writable_mount_is_only_candidate_never_proof(self):
        self.mount_info("rw")
        r = self.inspect()
        self.assertTrue(r["hierarchy_complete"])
        self.assertTrue(r["delegation_candidate"])
        self.assertFalse(r["enforcement_verified"])
        self.assertFalse(r["safe_for_untrusted_code"])

    def test_effective_limits_use_tightest_visible_ancestor(self):
        self.mount_info("ro")
        (self.mount / "cpu.max").write_text("50000 100000")
        (self.mount / "memory.max").write_text(str(268435456))
        (self.mount / "memory.swap.max").write_text(str(134217728))
        (self.mount / "pids.max").write_text("64")
        r = self.inspect()
        self.assertEqual(r["hierarchy_levels"], 2)
        self.assertTrue(r["hierarchy_complete"])
        self.assertEqual(r["effective_limits"]["cpu_cores"], 0.5)
        self.assertEqual(r["effective_limits"]["cpu_quota_us"], 50000)
        self.assertEqual(r["effective_limits"]["cpu_period_us"], 100000)
        self.assertEqual(r["effective_limits"]["memory_bytes"], 268435456)
        self.assertEqual(r["effective_limits"]["memory_swap_bytes"], 134217728)
        self.assertEqual(r["effective_limits"]["pids"], 64)
        self.assertTrue(r["effective_limits"]["has_finite_cpu_limit"])
        self.assertTrue(r["effective_limits"]["has_finite_memory_limit"])
        self.assertTrue(r["effective_limits"]["has_finite_pids_limit"])

    def test_unlimited_ancestors_are_not_reported_as_finite_quotas(self):
        self.mount_info("ro")
        (self.mount / "cpu.max").write_text("max 100000")
        (self.mount / "memory.max").write_text("max")
        (self.mount / "memory.swap.max").write_text("max")
        (self.mount / "pids.max").write_text("max")
        r = self.inspect()
        self.assertTrue(r["hierarchy_complete"])
        self.assertIsNone(r["effective_limits"]["cpu_cores"])
        self.assertIsNone(r["effective_limits"]["memory_bytes"])
        self.assertIsNone(r["effective_limits"]["memory_swap_bytes"])
        self.assertIsNone(r["effective_limits"]["pids"])
        self.assertFalse(r["effective_limits"]["has_finite_cpu_limit"])
        self.assertFalse(r["effective_limits"]["has_finite_memory_limit"])
        self.assertFalse(r["effective_limits"]["has_finite_memory_swap_limit"])
        self.assertFalse(r["effective_limits"]["has_finite_pids_limit"])

    def test_missing_controller_or_resource_file_fails_closed(self):
        self.mount_info("rw")
        (self.current / "cgroup.controllers").write_text("cpu memory")
        self.assertFalse(self.inspect()["delegation_candidate"])
        (self.current / "cgroup.controllers").write_text("cpu memory pids")
        (self.current / "cgroup.kill").unlink()
        self.assertFalse(self.inspect()["delegation_candidate"])

    def test_quota_candidate_requires_every_resource_control_writable(self):
        self.mount_info("rw")

        def access(path, mode):
            if Path(path).name == "memory.max" and mode & os.W_OK:
                return False
            return True

        with patch("runtime_probe.os.geteuid", return_value=1000), patch(
                "runtime_probe.os.access", side_effect=access):
            report = cgroup_inventory(self.proc, self.mount)
        self.assertTrue(report["aggregate_controls_present"])
        self.assertFalse(report["required_write_controls_writable"])
        self.assertFalse(report["delegation_candidate"])
        self.assertFalse(report["enforcement_verified"])
        self.assertFalse(report["safe_for_untrusted_code"])

    def test_missing_swap_or_accounting_control_fails_closed(self):
        self.mount_info("rw")
        (self.current / "memory.swap.max").unlink()
        report = self.inspect()
        # Presence and readability are separate diagnostics: the file exists,
        # but the read permission check must still block delegation candidacy.
        self.assertTrue(report["aggregate_controls_present"])
        self.assertFalse(report["delegation_candidate"])
        (self.current / "memory.swap.max").touch()
        (self.current / "cgroup.events").unlink()
        report = self.inspect()
        self.assertFalse(report["monitor_controls_present"])
        self.assertFalse(report["delegation_candidate"])

    def test_missing_swap_limit_on_visible_ancestor_makes_hierarchy_incomplete(self):
        self.mount_info("ro")
        (self.mount / "memory.swap.max").unlink()
        report = self.inspect()
        self.assertFalse(report["hierarchy_complete"])
        self.assertFalse(report["delegation_candidate"])
        self.assertIsNone(report["effective_limits"]["memory_swap_bytes"])
        self.assertFalse(report["effective_limits"]["has_finite_memory_swap_limit"])

    def test_effective_limits_are_scoped_to_visible_mount_ancestors(self):
        self.mount_info("ro")
        report = self.inspect()
        self.assertEqual(
            report["effective_limits_scope"],
            "visible_cgroup_mount_ancestors_only",
        )

    def test_quota_candidate_requires_readable_accounting_controls(self):
        self.mount_info("rw")

        def access(path, mode):
            if Path(path).name == "cgroup.events" and mode & os.R_OK:
                return False
            return True

        with patch("runtime_probe.os.geteuid", return_value=1000), patch(
                "runtime_probe.os.access", side_effect=access):
            report = cgroup_inventory(self.proc, self.mount)
        self.assertTrue(report["monitor_controls_present"])
        self.assertFalse(report["monitor_controls_readable"])
        self.assertTrue(report["required_write_controls_present"])
        self.assertTrue(report["required_write_controls_writable"])
        self.assertFalse(report["aggregate_controls_present"])
        self.assertFalse(report["delegation_candidate"])
        self.assertFalse(report["safe_for_untrusted_code"])

    def test_threaded_cgroup_is_not_a_quota_candidate(self):
        self.mount_info("rw")
        (self.current / "cgroup.type").write_text("threaded")
        report = self.inspect()
        self.assertEqual(report["cgroup_type"], "threaded")
        self.assertFalse(report["domain_type_usable"])
        self.assertFalse(report["delegation_candidate"])

    def test_readback_of_limit_controls_is_required(self):
        self.mount_info("rw")

        def access(path, mode):
            if Path(path).name == "memory.max" and mode & os.R_OK:
                return False
            return True

        with patch("runtime_probe.os.geteuid", return_value=1000), patch(
                "runtime_probe.os.access", side_effect=access):
            report = cgroup_inventory(self.proc, self.mount)
        self.assertTrue(report["required_write_controls_writable"])
        self.assertFalse(report["monitor_controls_readable"])
        self.assertFalse(report["delegation_candidate"])

    def test_missing_or_ambiguous_metadata_fails_closed(self):
        self.assertFalse(self.inspect()["cgroup_v2"])
        self.mount_info("rw")
        (self.proc / "cgroup").write_text("0::/../worker" + chr(10))
        self.assertFalse(self.inspect()["delegation_candidate"])


if __name__ == "__main__":
    unittest.main()
