"""Negative sandbox tests; never require network, root or HA access."""
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import sandbox_export as sandbox

class SandboxTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.target = self.root / "target"
        self.source.mkdir()
        self.target.mkdir()
        (self.source / "export.py").write_text("print('synthetic only')\n")

    def call(self):
        return sandbox.sandbox_export(
            source=self.source, target=self.target, script="export.py",
            sha="a" * 40, verify=False, env={"PATH": os.environ.get("PATH", "")},
            max_output_bytes=1024 * 1024, memory_bytes=128 * 1024 * 1024,
            cpu_seconds=10, elapsed_seconds=2)

    def test_missing_bwrap_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value=None):
            with self.assertRaisesRegex(sandbox.SandboxUnavailable, "Bubblewrap"):
                self.call()

    def test_root_execution_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
            with patch.object(sandbox.os, "geteuid", return_value=0):
                with self.assertRaisesRegex(sandbox.SandboxUnavailable, "root"):
                    self.call()

    def test_unsafe_exporter_path_fails_closed(self):
        with patch.object(sandbox.shutil, "which", return_value="/usr/bin/bwrap"):
            with patch.object(sandbox.os, "geteuid", return_value=1000):
                with self.assertRaisesRegex(sandbox.SandboxUnavailable, "Invalid script"):
                    sandbox.sandbox_export(
                        source=self.source, target=self.target, script="../passwd",
                        sha="a" * 40, verify=False, env={},
                        max_output_bytes=1024, memory_bytes=1024 * 1024,
                        cpu_seconds=1, elapsed_seconds=1)

    def test_aggregate_size_detection(self):
        (self.target / "a.bin").write_bytes(b"x" * 6)
        (self.target / "b.bin").write_bytes(b"x" * 6)
        self.assertGreater(sandbox._directory_bytes(self.target, 10), 10)

    def test_namespace_is_explicit_not_optional(self):
        # Regression: bwrap --unshare-all uses --unshare-user-try and could
        # silently skip user namespaces on some systems.
        code = (Path(sandbox.__file__)).read_text()
        self.assertIn('"--unshare-user"', code)
        self.assertIn('"--unshare-net"', code)
        self.assertNotIn('"--unshare-all"', code)

if __name__ == "__main__":
    unittest.main()
