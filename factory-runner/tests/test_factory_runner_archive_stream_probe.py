import os
import unittest

import archive_stream_probe as probe


class ArchiveStreamProbeTests(unittest.TestCase):
    def _require_runtime(self):
        if os.geteuid() != 0:
            self.skipTest("requires root-owned chroot fixture")
        try:
            import pwd
            pwd.getpwnam("executor")
        except KeyError:
            self.skipTest("executor account is not available")
        try:
            import os as _os
            if _os.statvfs("/dev/shm").f_blocks <= 0:
                self.skipTest("tmpfs is unavailable")
        except OSError:
            self.skipTest("tmpfs is unavailable")

    def test_chroot_stdout_stream_is_validated_and_adversarial_cases_blocked(self):
        self._require_runtime()
        result = probe.run_probe()
        self.assertEqual(result["status"], "pass", result)
        self.assertFalse(result["safe_for_untrusted_code"], result)
        self.assertFalse(result["project_code_executed"], result)

        safe = result["safe_stream"]
        self.assertEqual(safe["archive_validation"], "pass", result)
        self.assertEqual(safe["state"], "VALIDATED_NOT_PUBLISHED", result)
        self.assertTrue(safe["content_matches"], result)
        self.assertEqual(safe["extracted_sha256"], probe.SAFE_SHA256, result)
        self.assertTrue(safe["tmpfs_cleanup_restored"], result)

        security = result["security"]
        self.assertEqual(security["fd_audit"]["status"], "ok", result)
        for field in ("chroot_entered", "uid_dropped", "environment_empty",
                      "effective_capabilities_zero", "no_new_privs",
                      "seccomp_loaded", "filesystem_write_denied",
                      "network_denied", "process_creation_denied"):
            self.assertTrue(security[field], result)

        traversal = result["traversal_stream"]
        self.assertTrue(traversal["rejected"], result)
        self.assertTrue(traversal["target_absent"], result)
        self.assertTrue(traversal["tmpfs_cleanup_restored"], result)

        overflow = result["overflow"]
        self.assertTrue(overflow["overflow"], result)
        self.assertEqual(overflow["stdout_bytes"], 129, result)
        self.assertTrue(overflow["child_killed"], result)
        self.assertTrue(overflow["tmpfs_cleanup_restored"], result)

        timeout = result["timeout"]
        self.assertTrue(timeout["timed_out"], result)
        self.assertTrue(timeout["child_killed"], result)
        self.assertTrue(timeout["tmpfs_cleanup_restored"], result)


if __name__ == "__main__":
    unittest.main()
