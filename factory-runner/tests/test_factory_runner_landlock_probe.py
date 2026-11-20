"""Non-destructive ABI-query tests: no ruleset is applied to any process."""
import errno
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from landlock_probe import landlock_status


class LandlockProbeTests(unittest.TestCase):
    def run_probe(self, abi, err=0, *, machine="aarch64", os_name="linux"):
        return landlock_status(query=lambda: (abi, err), machine=machine, os_name=os_name)

    def test_abi_one_filesystem_only(self):
        data = self.run_probe(1)
        self.assertEqual(data["status"], "supported")
        self.assertTrue(data["filesystem_rules"])
        self.assertFalse(data["tcp_port_rules"])
        self.assertFalse(data["udp_port_rules"])
        self.assertFalse(data["safe_for_untrusted_code"])
        self.assertFalse(data["enforcement_verified"])

    def test_abi_six_tcp_and_ipc_but_not_udp(self):
        data = self.run_probe(6)
        self.assertTrue(data["tcp_port_rules"])
        self.assertTrue(data["ipc_scoping"])
        self.assertFalse(data["udp_port_rules"])

    def test_abi_ten_adds_udp(self):
        data = self.run_probe(10)
        self.assertTrue(data["udp_port_rules"])
        self.assertFalse(data["safe_for_untrusted_code"])

    def test_kernel_disabled(self):
        self.assertEqual(self.run_probe(-1, errno.EOPNOTSUPP)["status"], "disabled")

    def test_kernel_missing(self):
        self.assertEqual(self.run_probe(-1, errno.ENOSYS)["status"], "syscall_unavailable")

    def test_kernel_permission_denied(self):
        self.assertEqual(self.run_probe(-1, errno.EPERM)["status"], "permission_denied")

    def test_unknown_error_fails_closed(self):
        self.assertEqual(self.run_probe(-1, errno.EINVAL)["status"], "query_failed")

    def test_unknown_arch_no_syscall(self):
        def unexpected():
            raise AssertionError("Kernel must not be queried")
        value = landlock_status(query=unexpected, machine="armv7l", os_name="linux")
        self.assertEqual(value["status"], "unsupported_arch_or_os")

    def test_other_operating_system(self):
        self.assertEqual(self.run_probe(6, machine="x86_64", os_name="darwin")["status"], "unsupported_arch_or_os")

    def test_query_exception_fails_closed(self):
        def fail():
            raise OSError(errno.EPERM, "denied")
        self.assertEqual(landlock_status(query=fail, machine="x86_64", os_name="linux")["status"], "query_failed")

    def test_zero_does_not_signal_support(self):
        self.assertEqual(self.run_probe(0)["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
