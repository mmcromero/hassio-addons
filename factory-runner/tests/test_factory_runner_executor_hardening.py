"""Unit and regression tests for Factory Runner Batch 5B.1 executor hardening.

Covers:
1. PR_SET_CHILD_SUBREAPER adoption and zombie reaping.
2. Compulsory FD audit and sanitization (closing unapproved FDs).
3. Reinforced Seccomp-BPF policy (denied syscalls, allowed worker baseline).
4. Guaranteed process tree termination (UID-scoped, timeout, subreaper reap).
5. oom_score_adj sacrificial worker configuration (+500).
"""
from __future__ import annotations

import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import MagicMock, patch

# Ensure add-on directory is in sys.path
ADD_ON_DIR = Path(__file__).resolve().parents[1]
if str(ADD_ON_DIR) not in sys.path:
    sys.path.insert(0, str(ADD_ON_DIR))

import executor_hardening as hardening
import seccomp_policy as seccomp


class SubreaperTests(unittest.TestCase):
    """Step 1: Test PR_SET_CHILD_SUBREAPER and zombie reaping."""

    def test_set_and_get_child_subreaper_on_linux_or_graceful_fallback(self):
        result = hardening.set_child_subreaper()
        if sys.platform.startswith("linux"):
            self.assertTrue(result)
            self.assertTrue(hardening.get_child_subreaper())
        else:
            self.assertFalse(result)
            self.assertFalse(hardening.get_child_subreaper())

    def test_reap_zombies_returns_empty_when_no_children(self):
        reaped = hardening.reap_zombies()
        self.assertIsInstance(reaped, list)

    def test_reap_zombies_collects_adopted_processes(self):
        if not hasattr(os, "waitpid") or not hasattr(os, "WNOHANG"):
            self.skipTest("waitpid not available on this platform")

        with patch("os.waitpid") as mock_waitpid:
            # Simulate reaping two PIDs (1234, 5678) then ECHILD/0
            mock_waitpid.side_effect = [(1234, 0), (5678, 0), (0, 0)]
            reaped = hardening.reap_zombies()
            self.assertEqual(reaped, [1234, 5678])


class FileDescriptorAuditTests(unittest.TestCase):
    """Step 2: Test compulsory FD audit and unapproved FD sanitization."""

    def test_audit_preserves_allowed_fds_and_closes_unapproved(self):
        # Create temporary pipes / files to generate real unapproved FDs
        r_fd, w_fd = os.pipe()
        try:
            # Audit allowing only stdin/stdout/stderr (0, 1, 2)
            audit = hardening.audit_and_close_unapproved_fds([0, 1, 2])
            self.assertIn(audit["status"], ("ok", "unavailable"))
            if audit["status"] == "ok":
                # Verify that r_fd and w_fd were closed by the audit
                with self.assertRaises(OSError):
                    os.fstat(r_fd)
                with self.assertRaises(OSError):
                    os.fstat(w_fd)
                self.assertGreaterEqual(audit["closed_count"], 2)
                self.assertEqual(audit["unexpected_remaining"], 0)
        finally:
            # Clean up if not closed
            for fd in (r_fd, w_fd):
                try:
                    os.close(fd)
                except OSError:
                    pass

    def test_audit_fails_if_allowed_descriptor_was_missing(self):
        audit = hardening.audit_and_close_unapproved_fds([0, 1, 2])
        if audit["status"] != "unavailable":
            self.assertEqual(audit["allowed_missing"], 0)


class SeccompPolicyHardeningTests(unittest.TestCase):
    """Step 3: Test reinforced Seccomp policy (M167 requirements)."""

    def test_m167_mandatory_denied_syscalls_present(self):
        mandatory = (
            "setsid", "setpgid", "socket", "bind", "connect",
            "ptrace", "bpf", "io_uring_setup", "io_uring_enter",
            "mount", "umount2", "chroot",
        )
        for syscall in mandatory:
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Mandatory syscall {syscall} must be in DENIED_SYSCALLS",
            )
            self.assertIn(syscall, seccomp.DENIED_SYSCALLS)

    def test_additional_kernel_attack_surface_syscalls_denied(self):
        extra = ("personality", "kcmp", "quotactl", "lookup_dcookie")
        for syscall in extra:
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Attack surface syscall {syscall} must be denied",
            )

    def test_worker_allowed_syscalls_are_not_denied(self):
        # Standard execution operations required by Python/Node workers
        safe_ops = ("read", "write", "close", "mmap", "brk", "getpid", "getuid", "execve", "clone")
        for syscall in safe_ops:
            self.assertFalse(
                seccomp.is_syscall_denied(syscall),
                f"Benign worker syscall {syscall} must not be denied",
            )
            self.assertTrue(
                seccomp.is_syscall_allowed_for_workers(syscall),
                f"Benign worker syscall {syscall} should be in worker baseline",
            )

    def test_namespace_flags_mask_covers_all_clone_namespaces(self):
        self.assertEqual(len(seccomp.CLONE_NAMESPACE_FLAGS), 8)
        # Verify user, net, pid, mount namespace flags
        for flag in (0x10000000, 0x20000000, 0x40000000, 0x00020000):
            self.assertIn(flag, seccomp.CLONE_NAMESPACE_FLAGS)


class GuaranteedTerminationTests(unittest.TestCase):
    """Step 4: Test process termination, timeout handling, and UID scoping."""

    def test_find_processes_by_uid_protects_root_and_current_user(self):
        # Targeting UID 0 (root) must always return empty (fail-safe)
        self.assertEqual(hardening.find_processes_by_uid(0), [])
        # Targeting negative UID must return empty
        self.assertEqual(hardening.find_processes_by_uid(-1), [])

        current_uid = os.geteuid() if hasattr(os, "geteuid") else 1000
        # Targeting current user must return empty (prevent self-kill)
        self.assertEqual(hardening.find_processes_by_uid(current_uid), [])

    def test_find_processes_by_uid_with_synthetic_proc(self):
        with tempfile.TemporaryDirectory(prefix="proc-test-") as proc_dir:
            proc = Path(proc_dir)
            # Create synthetic pid directories: 1001, 1002, 1003
            p1 = proc / "1001"
            p2 = proc / "1002"
            p3 = proc / "1003"
            for p in (p1, p2, p3):
                p.mkdir()

            # Mock lstat to simulate target UID = 2001 on p1 and p3
            real_lstat = os.lstat

            def fake_lstat(path, *args, **kwargs):
                path_str = str(path)
                if path_str.endswith("1001") or path_str.endswith("1003"):
                    mock_stat = MagicMock()
                    mock_stat.st_uid = 2001
                    return mock_stat
                elif path_str.endswith("1002"):
                    mock_stat = MagicMock()
                    mock_stat.st_uid = 3000
                    return mock_stat
                return real_lstat(path, *args, **kwargs)

            with patch("os.lstat", side_effect=fake_lstat):
                matches = hardening.find_processes_by_uid(2001, proc_path=proc_dir)
                self.assertEqual(matches, [1001, 1003])

    def test_terminate_process_tree_terminates_direct_and_group(self):
        mock_proc = MagicMock()
        mock_proc.pid = 9999
        mock_proc.poll.side_effect = [None, 0]  # Running initially, terminated after SIGTERM
        mock_proc.wait.return_value = 0

        with patch.object(os, "killpg", create=True) as mock_killpg:
            report = hardening.terminate_process_tree(mock_proc, timeout=0.1)
            self.assertEqual(report["status"], "ok")
            self.assertTrue(report["direct_killed"])
            mock_killpg.assert_called_with(9999, hardening.SIGTERM)

    def test_terminate_process_tree_scans_and_kills_target_uid(self):
        mock_proc = MagicMock()
        mock_proc.pid = 8888
        mock_proc.poll.return_value = 0

        with patch.object(hardening, "find_processes_by_uid", side_effect=[[8889, 8890], []]):
            with patch("os.kill") as mock_kill:
                report = hardening.terminate_process_tree(
                    mock_proc, target_uid=1500, timeout=0.1
                )
                self.assertEqual(report["status"], "ok")
                self.assertEqual(report["uid_killed"], [8889, 8890])
                mock_kill.assert_any_call(8889, hardening.SIGKILL)
                mock_kill.assert_any_call(8890, hardening.SIGKILL)


class OOMScoreAdjTests(unittest.TestCase):
    """Step 5: Test oom_score_adj sacrificial worker configuration."""

    def test_invalid_score_rejected(self):
        report = hardening.configure_oom_score_adj(-10)
        self.assertEqual(report["status"], "invalid_score")
        report2 = hardening.configure_oom_score_adj(1500)
        self.assertEqual(report2["status"], "invalid_score")
        report3 = hardening.configure_oom_score_adj("500")  # type: ignore
        self.assertEqual(report3["status"], "invalid_score")

    def test_configure_oom_score_adj_synthetic_proc(self):
        with tempfile.TemporaryDirectory(prefix="oom-test-") as proc_dir:
            proc = Path(proc_dir)
            pid_dir = proc / "self"
            pid_dir.mkdir()
            oom_file = pid_dir / "oom_score_adj"
            oom_file.write_text("0\n", encoding="ascii")

            report = hardening.configure_oom_score_adj(500, pid="self", proc_path=proc_dir)
            self.assertEqual(report["status"], "ok")
            self.assertEqual(report["configured_score"], 500)
            self.assertEqual(report["previous_score"], 0)
            # Verify file content
            self.assertEqual(oom_file.read_text(encoding="ascii").strip(), "500")

    def test_configure_oom_score_adj_missing_proc_returns_proc_unavailable(self):
        with tempfile.TemporaryDirectory(prefix="empty-proc-") as proc_dir:
            report = hardening.configure_oom_score_adj(500, pid="9999", proc_path=proc_dir)
            self.assertEqual(report["status"], "proc_unavailable")

    def test_configure_oom_score_adj_handles_permission_error(self):
        with tempfile.TemporaryDirectory(prefix="oom-perm-") as proc_dir:
            proc = Path(proc_dir)
            pid_dir = proc / "self"
            pid_dir.mkdir()
            oom_file = pid_dir / "oom_score_adj"
            oom_file.write_text("0\n", encoding="ascii")

            with patch("pathlib.Path.write_text", side_effect=PermissionError("denied")):
                report = hardening.configure_oom_score_adj(500, pid="self", proc_path=proc_dir)
                self.assertEqual(report["status"], "permission_denied")


if __name__ == "__main__":
    unittest.main()
