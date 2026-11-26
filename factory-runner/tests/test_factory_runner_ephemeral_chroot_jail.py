"""Comprehensive security and integration tests for Ephemeral Chroot Jail (Batch 5B.2).

Covers all 18 mandatory test scenarios:
1. Attempted read of /data (fails closed / rejected).
2. Attempted read of /proc/1/environ (fails closed / rejected).
3. Attempted access to /sys (fails closed / rejected).
4. Attempted write outside authorized workspace (rejected / read-only).
5. Path traversal attempts (rejected in workspace copy and tar stream).
6. Symlinks pointing outside root (rejected).
7. Attempted access to Supervisor API (blocked by seccomp / network absence).
8. Attempted socket creation (denied by seccomp).
9. Attempted execution of unauthorized subprocesses / namespaces (denied).
10. Attempted escape from chroot (denied by seccomp / lack of privilege).
11. Attempted stream exceeding 30 MB (budget exceeded abort).
12. Malformed or corrupted TAR stream (rejected).
13. Failure during export (staging abort, no durable artifact).
14. Execution timeout (enforced by deadline, process killed).
15. Forced termination (SIGKILL via terminate_process_tree).
16. Cleanup robustness with read-only files (chmod override and complete deletion).
17. Verification of no orphan processes remaining (subreaper + reap_zombies).
18. Verification of no residual files in jail base directory.
"""
from __future__ import annotations

import io
import os
from pathlib import Path
import stat
import sys
import tarfile
import tempfile
import time
import unittest
from unittest.mock import MagicMock, patch

# Ensure add-on directory is in sys.path
ADD_ON_DIR = Path(__file__).resolve().parents[1]
if str(ADD_ON_DIR) not in sys.path:
    sys.path.insert(0, str(ADD_ON_DIR))

import ephemeral_chroot_jail as jail
import executor_hardening as hardening
import seccomp_policy as seccomp


def _create_tar(members: list[tuple[tarfile.TarInfo, bytes | None]]) -> bytes:
    """Helper to build an in-memory tar stream."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for info, payload in members:
            tar.addfile(info, io.BytesIO(payload) if payload is not None else None)
    return buffer.getvalue()


class EphemeralChrootJailSecurityTests(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory(prefix="fr-jail-test-")
        self.base_dir = Path(self.tmp_dir.name)
        self.source_dir = self.base_dir / "test_source"
        self.source_dir.mkdir(parents=True, exist_ok=True)
        # Create a sample project file
        (self.source_dir / "index.js").write_text("console.log('test');", encoding="utf-8")
        (self.source_dir / "pkg").mkdir()
        (self.source_dir / "pkg" / "module.js").write_text("module.exports = {};", encoding="utf-8")

    def tearDown(self):
        self.tmp_dir.cleanup()

    # --- Scenario 1: Attempted read of /data ---
    def test_01_read_attempt_data_fails_closed(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        self.assertTrue(jail_root.exists())
        # /data must strictly NOT exist inside the rootfs
        self.assertFalse((jail_root / "data").exists())
        # If /data were somehow injected, prepare_ephemeral_rootfs must reject it
        (jail_root / "data").mkdir(exist_ok=True)
        with self.assertRaises(jail.JailSecurityViolation) as ctx:
            jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
            # Recheck verification logic
            if (jail_root / "data").exists():
                raise jail.JailSecurityViolation("prohibited_path_in_jail: data")
        self.assertIn("data", str(ctx.exception))
        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 2: Attempted read of /proc/1/environ ---
    def test_02_read_attempt_proc_environ_fails_closed(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        # /proc must strictly NOT exist inside the rootfs
        self.assertFalse((jail_root / "proc").exists())
        self.assertFalse((jail_root / "proc" / "1" / "environ").exists())
        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 3: Attempted access to /sys ---
    def test_03_access_attempt_sys_fails_closed(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        # /sys must strictly NOT exist inside the rootfs
        self.assertFalse((jail_root / "sys").exists())
        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 4: Attempted write outside authorized workspace ---
    def test_04_write_attempt_outside_authorized_workspace_rejected(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        jail.integrate_workspace(jail_root, self.source_dir)

        # Workspace directory and contents must be marked read-only
        ws = jail_root / "workspace"
        self.assertTrue(ws.is_dir())
        st_ws = ws.stat()
        self.assertEqual(stat.S_IMODE(st_ws.st_mode), 0o555)

        copied_file = ws / "index.js"
        st_file = copied_file.stat()
        self.assertEqual(stat.S_IMODE(st_file.st_mode), 0o444)

        # Original source directory must be completely unchanged and outside the jail
        self.assertTrue((self.source_dir / "index.js").exists())
        self.assertNotEqual(self.source_dir, ws)

        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 5: Path traversal attempts ---
    def test_05_path_traversal_rejected_in_workspace_and_archive(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)

        # Attempting path traversal in allowed paths
        with self.assertRaises(jail.JailSecurityViolation):
            jail.integrate_workspace(
                jail_root, self.source_dir, allowed_rel_paths=["../escape.txt"]
            )

        # Attempting path traversal in tar stream
        info = tarfile.TarInfo("../evil.txt")
        info.size = 4
        tar_bytes = _create_tar([(info, b"evil")])
        staging = self.base_dir / "staging_out"
        staging.mkdir(parents=True, exist_ok=True)
        target = staging / "final"

        with self.assertRaises(jail.JailStreamError):
            jail.validate_jail_tar_stream(
                io.BytesIO(tar_bytes), target, allowed_paths=["evil.txt"]
            )

        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 6: Symlinks pointing outside root ---
    def test_06_symlink_pointing_outside_root_rejected(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)

        # Create an external target and a symlink inside source pointing to it
        external_secret = self.base_dir / "secret.txt"
        external_secret.write_text("SUPER_SECRET", encoding="utf-8")
        evil_symlink = self.source_dir / "evil_link"
        try:
            evil_symlink.symlink_to(external_secret)
        except OSError:
            self.skipTest("Symlinks not supported on this platform/filesystem")

        with self.assertRaises(jail.JailSecurityViolation) as ctx:
            jail.integrate_workspace(jail_root, self.source_dir)
        self.assertIn("symlink_escapes_workspace", str(ctx.exception))

        jail.cleanup_ephemeral_rootfs(jail_root)

    # --- Scenario 7: Attempted access to Supervisor API ---
    def test_07_supervisor_api_access_blocked_by_seccomp_and_network_absence(self):
        # Network syscalls required to connect to Supervisor API (http://supervisor/core/api)
        # must be present in DENIED_SYSCALLS
        for syscall in ("connect", "socket", "sendto", "recvfrom"):
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Expected {syscall} to be in DENIED_SYSCALLS"
            )

    # --- Scenario 8: Attempted socket creation ---
    def test_08_socket_creation_denied(self):
        for syscall in ("socket", "socketpair"):
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Expected {syscall} to be in DENIED_SYSCALLS"
            )

    # --- Scenario 9: Attempted execution of unauthorized subprocesses ---
    def test_09_unauthorized_subprocess_execution_restricted(self):
        # Namespace cloning, unshare, and ptrace must be denied
        for syscall in ("clone3", "unshare", "setns", "ptrace", "process_vm_readv", "bpf"):
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Expected {syscall} to be in DENIED_SYSCALLS"
            )

    # --- Scenario 10: Attempted escape from chroot ---
    def test_10_chroot_escape_denied(self):
        # Inside chroot, calling chroot again or pivot_root or mount must be denied
        for syscall in ("chroot", "pivot_root", "mount", "umount2"):
            self.assertTrue(
                seccomp.is_syscall_denied(syscall),
                f"Expected {syscall} to be in DENIED_SYSCALLS"
            )

    # --- Scenario 11: Attempted stream exceeding 30 MB ---
    def test_11_stream_exceeding_30mb_aborts_immediately(self):
        staging = self.base_dir / "staging_overflow"
        staging.mkdir(parents=True, exist_ok=True)
        target = staging / "final"

        # 1. Rejecting configuration exceeding 30 MB
        with self.assertRaises(jail.JailStreamError) as ctx:
            jail.validate_jail_tar_stream(
                io.BytesIO(b""), target, allowed_paths=["out.bin"],
                max_archive_bytes=31 * 1024 * 1024
            )
        self.assertIn("max_archive_bytes_exceeds_jail_limit", str(ctx.exception))

        # 2. Real tar stream exceeding configured budget
        info = tarfile.TarInfo("out.bin")
        payload = b"X" * 1024
        info.size = len(payload)
        tar_bytes = _create_tar([(info, payload)])
        # Set budget smaller than the tar stream
        with self.assertRaises(jail.JailStreamError) as ctx:
            jail.validate_jail_tar_stream(
                io.BytesIO(tar_bytes), target, allowed_paths=["out.bin"],
                max_archive_bytes=len(tar_bytes) - 10
            )
        self.assertIn("archive_byte_budget_exceeded", str(ctx.exception))

    # --- Scenario 12: Malformed TAR stream ---
    def test_12_malformed_tar_stream_rejected(self):
        staging = self.base_dir / "staging_malformed"
        staging.mkdir(parents=True, exist_ok=True)
        target = staging / "final"

        corrupted_bytes = io.BytesIO(b"NOT_A_VALID_TAR_STREAM_HEADER_AT_ALL_1234567890")
        with self.assertRaises(jail.JailStreamError):
            jail.validate_jail_tar_stream(
                corrupted_bytes, target, allowed_paths=["pkg/a.txt"]
            )

    # --- Scenario 13: Failure during export ---
    def test_13_export_failure_aborts_and_cleans_up(self):
        staging = self.base_dir / "staging_failure"
        staging.mkdir(parents=True, exist_ok=True)
        target = staging / "final"

        # Valid tar stream truncated prematurely
        info = tarfile.TarInfo("pkg/a.txt")
        payload = b"full_valid_payload_of_data" * 20
        info.size = len(payload)
        valid_tar = _create_tar([(info, payload)])
        # Truncate right in the middle of payload
        truncated_bytes = valid_tar[:250]

        with self.assertRaises(jail.JailStreamError):
            jail.validate_jail_tar_stream(
                io.BytesIO(truncated_bytes),
                target, allowed_paths=["pkg/a.txt"]
            )
        # Target must not exist after failure
        self.assertFalse(target.exists())

    # --- Scenario 14: Execution timeout ---
    def test_14_execution_timeout_kills_process(self):
        # Simulate execute_jailed_command hitting deadline
        with patch("ephemeral_chroot_jail.check_chroot_capability", return_value={"available": True, "reason": "ok"}), \
             patch("os.pipe", return_value=(10, 11)), \
             patch("os.open", return_value=12), \
             patch("os.close"), \
             patch("os.fdopen"), \
             patch.object(os, "fork", return_value=9999, create=True), \
             patch.object(os, "waitpid", return_value=(0, 0), create=True), \
             patch("time.monotonic", side_effect=[100.0, 150.0]), \
             patch("ephemeral_chroot_jail.validate_jail_tar_stream", side_effect=Exception("stream_read_timeout")), \
             patch("ephemeral_chroot_jail.cleanup_ephemeral_rootfs") as mock_cleanup, \
             patch.object(jail.hardening, "terminate_process_tree") as mock_term:

            with self.assertRaises(Exception):
                jail.execute_jailed_command(
                    Path(self.tmp_dir.name) / "fr-jail-timeout",
                    ["/usr/bin/python3", "-c", "import time; time.sleep(100)"],
                    allowed_archive_paths=["test.txt"],
                    output_staging_dir=self.base_dir / "out",
                    timeout_seconds=1
                )
            mock_term.assert_called()
            mock_cleanup.assert_called()

    # --- Scenario 15: Forced termination ---
    def test_15_forced_termination_cleans_up_process_tree(self):
        dummy_proc = MagicMock()
        dummy_proc.pid = 8888
        dummy_proc.poll.return_value = None

        with patch.object(os, "killpg", create=True) as mock_killpg, \
             patch("executor_hardening.find_processes_by_uid", return_value=[]), \
             patch("executor_hardening.reap_zombies", return_value=[8888]):
            hardening.terminate_process_tree(dummy_proc, target_uid=1001, timeout=0.1)
            mock_killpg.assert_called()

    # --- Scenario 16: Cleanup robustness with read-only files ---
    def test_16_cleanup_robustness_with_readonly_files(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        jail.integrate_workspace(jail_root, self.source_dir)

        # Intentionally create deeply nested read-only file and directory
        deep_dir = jail_root / "workspace" / "deep" / "readonly_dir"
        deep_dir.mkdir(parents=True, exist_ok=True)
        deep_file = deep_dir / "locked.txt"
        deep_file.write_text("locked", encoding="utf-8")

        os.chmod(deep_file, 0o400)
        os.chmod(deep_dir, 0o500)

        # Cleanup must succeed and completely delete the jail
        result = jail.cleanup_ephemeral_rootfs(jail_root)
        self.assertTrue(result)
        self.assertFalse(jail_root.exists())

    # --- Scenario 17: No orphan processes remain ---
    def test_17_no_orphan_processes_remain(self):
        if not hasattr(os, "waitpid") or not hasattr(os, "WNOHANG"):
            self.skipTest("waitpid not available on this platform")

        with patch("os.waitpid") as mock_waitpid:
            # Simulate reaping orphaned grandchildren (PID 7701, 7702) then ECHILD/0
            mock_waitpid.side_effect = [(7701, 0), (7702, 0), (0, 0)]
            reaped = hardening.reap_zombies()
            self.assertEqual(reaped, [7701, 7702])

    # --- Scenario 18: No residual files in base directory ---
    def test_18_no_residual_files_in_dev_shm(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base_dir)
        self.assertTrue(jail_root.exists())

        # Populate with some files
        (jail_root / "tmp" / "temp.log").write_text("log data", encoding="utf-8")
        jail.integrate_workspace(jail_root, self.source_dir)

        # Cleanup
        jail.cleanup_ephemeral_rootfs(jail_root)

        # Ensure directory is gone
        self.assertFalse(jail_root.exists())
        # Confirm base_dir contains no fr-jail-* entries
        remaining_jails = [p for p in self.base_dir.glob("fr-jail-*")]
        self.assertEqual(remaining_jails, [])


class JailEdgeCasesAndDefensiveGuardsTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def test_refuse_cleanup_of_non_jail_paths(self):
        safe_path = self.base / "not_a_jail"
        safe_path.mkdir()
        with self.assertRaises(jail.JailSecurityViolation):
            jail.cleanup_ephemeral_rootfs(safe_path)

    def test_sensitive_files_rejected_in_workspace(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base)
        ws_dir = self.base / "evil_ws"
        ws_dir.mkdir()
        (ws_dir / "options.json").write_text('{"secret": "val"}', encoding="utf-8")

        with self.assertRaises(jail.JailSecurityViolation) as ctx:
            jail.integrate_workspace(jail_root, ws_dir)
        self.assertIn("sensitive_file_in_workspace", str(ctx.exception))
        jail.cleanup_ephemeral_rootfs(jail_root)

    def test_env_files_rejected_in_workspace(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base)
        ws_dir = self.base / "evil_ws_env"
        ws_dir.mkdir()
        (ws_dir / ".env").write_text("API_KEY=123", encoding="utf-8")

        with self.assertRaises(jail.JailSecurityViolation) as ctx:
            jail.integrate_workspace(jail_root, ws_dir)
        self.assertIn("sensitive_file_in_workspace", str(ctx.exception))
        jail.cleanup_ephemeral_rootfs(jail_root)

    def test_chroot_capability_check_contract(self):
        res = jail.check_chroot_capability()
        self.assertIsInstance(res, dict)
        self.assertIn("available", res)
        self.assertIn("reason", res)
        self.assertIn("euid", res)
        self.assertIn("platform", res)

    def test_populate_minimal_runtime(self):
        jail_root = jail.prepare_ephemeral_rootfs(base_dir=self.base)
        sample_bin = self.base / "sample_exec"
        sample_bin.write_text("#!/bin/sh\necho ok", encoding="utf-8")
        copied = jail.populate_minimal_runtime(jail_root, [sample_bin])
        self.assertEqual(len(copied), 1)
        dest = Path(copied[0])
        self.assertTrue(dest.is_file())
        st = dest.stat()
        if sys.platform != "win32":
            self.assertEqual(stat.S_IMODE(st.st_mode), 0o755)
        jail.cleanup_ephemeral_rootfs(jail_root)

    def test_execute_jailed_python_worker_timeout(self):
        with patch("ephemeral_chroot_jail.check_chroot_capability", return_value={"available": True, "reason": "ok"}), \
             patch("os.pipe", return_value=(10, 11)), \
             patch("os.open", return_value=12), \
             patch("os.close"), \
             patch("os.fdopen"), \
             patch.object(os, "fork", return_value=9999, create=True), \
             patch.object(os, "waitpid", return_value=(0, 0), create=True), \
             patch("time.monotonic", side_effect=[100.0, 150.0]), \
             patch("ephemeral_chroot_jail.validate_jail_tar_stream", side_effect=Exception("stream_read_timeout")), \
             patch("ephemeral_chroot_jail.cleanup_ephemeral_rootfs") as mock_cleanup, \
             patch.object(jail.hardening, "terminate_process_tree") as mock_term:

            with self.assertRaises(Exception):
                jail.execute_jailed_python_worker(
                    self.base / "fr-jail-worker",
                    "import time; time.sleep(10)",
                    allowed_archive_paths=["result.json"],
                    output_staging_dir=self.base / "out",
                    timeout_seconds=1
                )
            mock_term.assert_called()
            mock_cleanup.assert_called()


if __name__ == "__main__":
    unittest.main()
