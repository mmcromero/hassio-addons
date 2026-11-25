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
        for name in ("cpu.max", "memory.max", "pids.max", "cgroup.kill",
                     "cgroup.procs", "cgroup.subtree_control"):
            (self.current / name).touch()
        (self.current / "cgroup.controllers").write_text("cpu memory pids io")

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
        self.assertTrue(r["delegation_candidate"])
        self.assertFalse(r["enforcement_verified"])
        self.assertFalse(r["safe_for_untrusted_code"])

    def test_missing_controller_or_resource_file_fails_closed(self):
        self.mount_info("rw")
        (self.current / "cgroup.controllers").write_text("cpu memory")
        self.assertFalse(self.inspect()["delegation_candidate"])
        (self.current / "cgroup.controllers").write_text("cpu memory pids")
        (self.current / "cgroup.kill").unlink()
        self.assertFalse(self.inspect()["delegation_candidate"])

    def test_missing_or_ambiguous_metadata_fails_closed(self):
        self.assertFalse(self.inspect()["delegation_candidate"])
        self.mount_info("rw")
        (self.proc / "cgroup").write_text("0::/../worker" + chr(10))
        self.assertFalse(self.inspect()["delegation_candidate"])


if __name__ == "__main__":
    unittest.main()
