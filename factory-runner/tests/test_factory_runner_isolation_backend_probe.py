"""Synthetic contract tests for the chroot/seccomp feasibility probe."""
import unittest
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import isolation_backend_probe as probe
import seccomp_policy as policy


class IsolationBackendProbeTests(unittest.TestCase):
    def test_capability_bit_mapping(self):
        value = probe.root_capabilities_from_masks((1 << 18) | (1 << 5) | (1 << 7),
                                                   (1 << 18) | (1 << 5))
        self.assertTrue(value["sys_chroot"])
        self.assertTrue(value["kill"])
        self.assertTrue(value["setuid"])
        self.assertFalse(value["sys_admin"])
        self.assertFalse(value["sys_resource"])

    def test_clone_namespace_mask_contains_all_namespace_flags(self):
        self.assertEqual(len(policy.CLONE_NAMESPACE_FLAGS), 8)
        self.assertEqual(len(set(policy.CLONE_NAMESPACE_FLAGS)), 8)
        for flag in (0x10000000, 0x20000000, 0x40000000, 0x00000080):
            self.assertIn(flag, policy.CLONE_NAMESPACE_FLAGS)

    def test_network_and_ipc_syscalls_are_denied(self):
        for name in ("socket", "socketpair", "connect", "bind", "shmget",
                     "shmat", "semget", "msgget", "mq_open"):
            self.assertIn(name, policy.DENIED_SYSCALLS)

    def test_process_escape_and_introspection_syscalls_are_denied(self):
        for name in ("ptrace", "process_vm_readv", "pidfd_open", "kill",
                     "tgkill", "setsid", "setpgid", "getppid"):
            self.assertIn(name, policy.DENIED_SYSCALLS)

    def test_mount_and_namespace_mutation_syscalls_are_denied(self):
        for name in ("mount", "umount2", "pivot_root", "chroot", "unshare",
                     "setns", "clone3", "open_tree", "move_mount", "fsopen"):
            self.assertIn(name, policy.DENIED_SYSCALLS)

    def test_privilege_and_kernel_attack_surface_syscalls_are_denied(self):
        for name in ("capset", "setuid", "setgroups", "bpf", "perf_event_open",
                     "userfaultfd", "io_uring_setup", "keyctl", "init_module", "reboot"):
            self.assertIn(name, policy.DENIED_SYSCALLS)

    def test_probe_is_explicitly_diagnostic_not_a_sandbox(self):
        self.assertFalse(probe.SAFE_FOR_UNTRUSTED_CODE)


if __name__ == "__main__":
    unittest.main()
