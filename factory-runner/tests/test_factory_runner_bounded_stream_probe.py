import os
import unittest

import bounded_stream_probe as probe


class BoundedStreamProbeTests(unittest.TestCase):
    def _require_runtime(self):
        if os.geteuid() != 0:
            self.skipTest("requires root-owned chroot fixture")
        try:
            import pwd
            pwd.getpwnam("executor")
        except KeyError:
            self.skipTest("executor account is not available")
        try:
            if os.statvfs("/dev/shm").f_blocks <= 0:
                self.skipTest("tmpfs is unavailable")
        except OSError:
            self.skipTest("tmpfs is unavailable")

    def test_readonly_chroot_allows_only_bounded_stdout(self):
        self._require_runtime()
        result = probe.run_probe()
        self.assertEqual(result["status"], "pass", result)
        self.assertTrue(result["filesystem_write_denied"], result)
        self.assertTrue(result["network_denied"], result)
        self.assertTrue(result["process_creation_denied"], result)
        self.assertEqual(result["fd_audit"]["status"], "ok", result)
        self.assertTrue(result["chroot_entered"], result)
        self.assertTrue(result["uid_dropped"], result)
        self.assertTrue(result["seccomp_loaded"], result)
        self.assertLessEqual(result["stdout_bytes"], result["output_limit_bytes"])
        self.assertTrue(result["tmpfs_cleanup_restored"], result)
        self.assertFalse(result["safe_for_untrusted_code"])
        self.assertFalse(result["project_code_executed"])

    def test_stdout_limit_kills_overflowing_synthetic_payload(self):
        self._require_runtime()
        result = probe.run_probe(max_output_bytes=128, payload_mode="overflow")
        self.assertEqual(result["status"], "blocked_output_limit", result)
        self.assertTrue(result["output_limit_enforced"], result)
        self.assertEqual(result["stdout_bytes"], 129, result)
        self.assertTrue(result["tmpfs_cleanup_restored"], result)
        self.assertFalse(result["project_code_executed"])


if __name__ == "__main__":
    unittest.main()
