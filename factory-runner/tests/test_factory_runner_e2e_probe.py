"""One-shot full API test is self-contained, non-root, and safe on failure."""
import contextlib
import importlib.util
import io
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("factory_e2e_probe", ROOT / "factory_e2e_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

class E2EProbeTests(unittest.TestCase):
    @unittest.skipIf(os.geteuid() == 0, "run in non-root Docker validation")
    def test_full_real_loopback_preflight_and_prepare(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = probe.main()
        self.assertEqual(result, 0, out.getvalue())
        self.assertIn("[E2E] PASS:", out.getvalue())
        self.assertIn("5 synthetic Git blobs", out.getvalue())
        self.assertIn("NO real workspaces", out.getvalue())

    def test_root_denied_before_working(self):
        out = io.StringIO()
        with patch.object(probe.os, "geteuid", return_value=0), contextlib.redirect_stdout(out), (
             patch.object(probe.tempfile, "TemporaryDirectory", side_effect=AssertionError("should not create temp"))):
            result = probe.main()
        self.assertEqual(result, 2)
        self.assertIn("requires non-root", out.getvalue())

    @unittest.skipIf(os.geteuid() == 0, "run in non-root Docker validation")
    def test_fixture_git_has_no_token_or_remote(self):
        original = subprocess.run
        seen = []
        def guarded(*args, **kwargs):
            if args and isinstance(args[0], list) and args[0][0] == "git":
                seen.append(args[0])
                env = kwargs.get("env", {})
                self.assertNotIn("RUNNER_AUTH_TOKEN", env)
                self.assertNotIn("GH_TOKEN", env)
                self.assertNotIn("GITHUB_TOKEN", env)
                self.assertNotIn("synthetic-secret", str(args[0]))
                self.assertNotIn("https://", str(args[0]))
                self.assertNotIn("--upload-pack", args[0])
            return original(*args, **kwargs)
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "synthetic-secret", "GH_TOKEN":"synthetic-secret"}), (
             patch.object(probe.subprocess, "run", side_effect=guarded)), (
             contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(probe.main(), 0)
        self.assertGreater(len(seen), 6)

    @unittest.skipIf(os.geteuid() == 0, "run in non-root Docker validation")
    def test_local_http_only(self):
        original = probe.ThreadingHTTPServer
        addresses = []
        def checked(address, handler):
            addresses.append(address)
            self.assertEqual(address, ("127.0.0.1", 0))
            return original(address, handler)
        with patch.object(probe, "ThreadingHTTPServer", side_effect=checked), (
             contextlib.redirect_stdout(io.StringIO())):
            self.assertEqual(probe.main(), 0)
        self.assertEqual(len(addresses), 1)

if __name__ == "__main__":
    unittest.main()
