"""Synthetic contract tests for the chroot/seccomp feasibility probe."""
import unittest
import errno
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

    def test_path_access_status_distinguishes_absent_denied_and_readable(self):
        def missing(_path, _flags):
            raise FileNotFoundError(errno.ENOENT, "missing")
        def denied(_path, _flags):
            raise PermissionError(errno.EACCES, "denied")
        self.assertEqual(probe.path_access_status("/synthetic", open_fn=missing), "absent")
        self.assertEqual(probe.path_access_status("/synthetic", open_fn=denied), "permission_denied")
        self.assertEqual(
            probe.path_access_status("/synthetic", open_fn=lambda _p, _f: 7,
                                     read_fn=lambda _fd, _n: b"x", close_fn=lambda _fd: None),
            "readable",
        )

    def test_path_access_status_checks_directory_listing_without_returning_entries(self):
        self.assertEqual(
            probe.path_access_status("/synthetic", directory=True,
                                     open_fn=lambda _p, _f: 8,
                                     listdir_fn=lambda _fd: ["pid"],
                                     close_fn=lambda _fd: None),
            "readable",
        )

    def test_effective_capability_mask_combines_kernel_words(self):
        self.assertEqual(probe.effective_capabilities_mask(0, 0), 0)
        self.assertEqual(probe.effective_capabilities_mask(1, 2), (2 << 32) | 1)

    def test_probe_is_explicitly_diagnostic_not_a_sandbox(self):
        self.assertFalse(probe.SAFE_FOR_UNTRUSTED_CODE)

    def test_path_absence_does_not_accept_permission_denied(self):
        def denied(_path):
            raise PermissionError(13, "denied")
        def missing(_path):
            raise FileNotFoundError(2, "missing")
        self.assertFalse(probe.path_is_absent("/synthetic", stat_fn=denied))
        self.assertTrue(probe.path_is_absent("/synthetic", stat_fn=missing))

    def test_probe_root_has_root_owned_non_writable_workspace(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = probe.prepare_probe_root(Path(temp) / "root")
            work = root / "workspace"
            self.assertEqual(work.stat().st_mode & 0o7777, 0o555)
            if os.geteuid() == 0:
                self.assertEqual(work.stat().st_uid, 0)

    def test_fd_audit_closes_unapproved_descriptors_in_child(self):
        import json, os
        read_fd, write_fd = os.pipe()
        pid = os.fork()
        if pid == 0:
            os.close(read_fd)
            result = probe.audit_and_close_unapproved_fds([write_fd])
            os.write(write_fd, json.dumps(result).encode("utf-8"))
            os._exit(0)
        os.close(write_fd)
        chunks = []
        while True:
            part = os.read(read_fd, 4096)
            if not part:
                break
            chunks.append(part)
        os.close(read_fd)
        _, status = os.waitpid(pid, 0)
        self.assertTrue(os.WIFEXITED(status))
        result = json.loads(b"".join(chunks).decode("utf-8"))
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["unexpected_remaining"], 0)
        self.assertEqual(result["allowed_missing"], 0)

    def test_rootfs_write_probe_reports_permission_denial(self):
        import os, tempfile
        if os.geteuid() != 0:
            self.skipTest("requires root-owned synthetic rootfs and UID drop")
        import pwd
        account = pwd.getpwnam("executor")
        with tempfile.TemporaryDirectory() as temp:
            os.chmod(temp, 0o755)
            root = probe.prepare_probe_root(Path(temp) / "root")
            pid = os.fork()
            if pid == 0:
                os.setgroups([])
                os.setgid(account.pw_gid)
                os.setuid(account.pw_uid)
                result = probe.rootfs_write_probe(str(root / "workspace" / ".write-probe"))
                os._exit(0 if result["status"] == "denied" else 1)
            _, status = os.waitpid(pid, 0)
            self.assertTrue(os.WIFEXITED(status))
            self.assertEqual(os.WEXITSTATUS(status), 0)

    def test_probe_root_tmp_is_writable_sticky_directory(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temp:
            root = probe.prepare_probe_root(Path(temp) / "root")
            self.assertEqual((root / "tmp").stat().st_mode & 0o7777, 0o1777)

    def test_outside_sentinel_parent_is_traversable_for_negative_control(self):
        import os, tempfile
        with tempfile.TemporaryDirectory() as temp:
            os.chmod(temp, 0o755)
            self.assertEqual(Path(temp).stat().st_mode & 0o777, 0o755)



if __name__ == "__main__":
    unittest.main()
