"""Non-root declarative startup smoke: synthetic Git, no network or secrets."""
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
spec = importlib.util.spec_from_file_location(
    "factory_declarative_probe", ROOT / "declarative_runtime_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class RuntimeProbeTests(unittest.TestCase):
    def test_nonroot_synthetic_git_and_hashes_pass(self):
        output = io.StringIO()
        with patch.object(probe.os, "geteuid", return_value=100), (
                contextlib.redirect_stdout(output)):
            code = probe.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertIn("[DECLARATIVE] PASS:", output.getvalue())
        self.assertIn("workspaces NOT tested", output.getvalue())

    def test_root_is_refused(self):
        output = io.StringIO()
        with patch.object(probe.os, "geteuid", return_value=0), (
                contextlib.redirect_stdout(output)):
            code = probe.main()
        self.assertEqual(code, 2)
        self.assertIn("[DECLARATIVE] BLOCKED:", output.getvalue())

    def test_missing_git_fails_closed(self):
        output = io.StringIO()
        with patch.object(probe.os, "geteuid", return_value=100), (
                patch.object(probe.subprocess, "run", side_effect=OSError("unavailable"))), (
                contextlib.redirect_stdout(output)):
            code = probe.main()
        self.assertEqual(code, 2)
        self.assertIn("[DECLARATIVE] BLOCKED:", output.getvalue())

    def test_git_processes_do_not_receive_api_token(self):
        output = io.StringIO()
        original_run = subprocess.run
        def check_environment(*args, **kwargs):
            self.assertNotIn("RUNNER_AUTH_TOKEN", kwargs.get("env", {}))
            return original_run(*args, **kwargs)
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "synthetic-secret"}), (
                patch.object(probe.os, "geteuid", return_value=100)), (
                patch.object(probe.subprocess, "run", side_effect=check_environment)), (
                contextlib.redirect_stdout(output)):
            code = probe.main()
        self.assertEqual(code, 0, output.getvalue())
        self.assertNotIn("synthetic-secret", output.getvalue())


if __name__ == "__main__":
    unittest.main()
