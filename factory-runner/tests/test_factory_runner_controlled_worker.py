"""Regressoes do worker read-only; nao executa scripts nem faz requests externos."""
import hashlib
import http.client
import json
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import controlled_worker as worker
import server

TOKEN = "safe-local-test-token-not-for-production-012345"


class ControlledWorkerTests(unittest.TestCase):
    def test_worker_allowlist(self):
        for task in ("execute", "publish", "prepare", "shell", "../diagnose"):
            with self.assertRaises(worker.WorkerBlocked):
                worker.execute(task)
        for project in ("../secret", "Abc", "x", "a" * 50):
            with self.assertRaises(worker.WorkerBlocked):
                worker.profile_audit(project)
        with self.assertRaises(worker.WorkerBlocked):
            worker.execute("diagnose", "avisaqui")
        with self.assertRaises(worker.WorkerBlocked):
            worker.read_only_preflight("avisaqui", "../badsha")

    def test_worker_refuses_root(self):
        with patch.object(worker.os, "geteuid", return_value=0):
            with self.assertRaises(worker.WorkerBlocked):
                worker.restrict_process()

    def test_security_report_does_not_leak_env(self):
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "DO_NOT_EXPOSE_ME"}):
            report = worker.security_diagnostic()
        self.assertEqual(report["sandbox_ready"], False)
        self.assertIn("landlock", report)
        self.assertFalse(report["landlock"]["enforcement_verified"])
        self.assertFalse(report["landlock"]["safe_for_untrusted_code"])
        self.assertNotIn("DO_NOT_EXPOSE_ME", json.dumps(report))

    def test_profile_only_from_fixed_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "avisaqui.json"
            obj = {"id":"avisaqui","product":"Test",
                   "source_repo":"test/source","distribution_repo":"test/target"}
            payload = json.dumps(obj).encode()
            target.write_bytes(payload)
            fake = types.ModuleType("rc_fastlane")
            fake.load_profile = lambda path: json.loads(path.read_text())
            with patch.dict(os.environ, {"RUNNER_PROJECTS_DIR": directory}), patch.dict(sys.modules, {"rc_fastlane": fake}):
                result = worker.profile_audit("avisaqui")
                self.assertEqual(result["profile_sha256"], hashlib.sha256(payload).hexdigest())
                self.assertFalse(result["scripts_executed"])
                target.unlink()
                target.symlink_to(Path(directory) / "missing")
                with self.assertRaises(worker.WorkerBlocked):
                    worker.profile_audit("avisaqui")

    def test_preflight_never_runs_exporter(self):
        fake = types.ModuleType("server")
        fake.preflight_project = lambda project, sha: {"mode":"read_only","eligible_for_preparation":False}
        with patch.dict(sys.modules, {"server": fake}):
            self.assertFalse(worker.read_only_preflight("avisaqui", "a"*40)["eligible_for_preparation"])
            fake.preflight_project = lambda *_: {"mode":"write"}
            with self.assertRaises(worker.WorkerBlocked):
                worker.read_only_preflight("avisaqui", "a"*40)

    def test_http_worker_route_auth_block_and_audit(self):
        with tempfile.TemporaryDirectory() as directory:
            previous = server.AUDIT_PATH
            server.AUDIT_PATH = Path(directory) / "audit.jsonl"
            httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
            thread = threading.Thread(target=httpd.serve_forever, daemon=True)
            thread.start()
            def call(body, auth=True):
                conn = http.client.HTTPConnection("127.0.0.1", httpd.server_port, timeout=4)
                headers = {"Content-Type":"application/json"}
                if auth:
                    headers["Authorization"] = "Bearer " + TOKEN
                conn.request("POST", "/api/worker/run", body=json.dumps(body), headers=headers)
                resp = conn.getresponse()
                out = resp.status, json.loads(resp.read())
                conn.close()
                return out
            try:
                with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": TOKEN}):
                    self.assertEqual(call({"task":"diagnose"}, False)[0], 401)
                    self.assertEqual(call({"task":"publish"})[0], 400)
                    self.assertEqual(call({"task":"profile","project":"../../private"})[0], 400)
                    self.assertEqual(call({"task":"diagnose","path":"/etc"})[0], 400)
                    with patch.object(server, "run_controlled_worker",
                                      return_value={"mode":"diagnostic_only","sandbox_ready":False}):
                        ok, data = call({"task":"diagnose"})
                        self.assertEqual(ok, 200)
                        self.assertFalse(data["published"])
                        self.assertFalse(data["result"]["sandbox_ready"])
                    with patch.object(server, "run_controlled_worker",
                                      side_effect=server.WorkerUnavailable()):
                        self.assertEqual(call({"task":"diagnose"})[0], 503)
                    audit = server.AUDIT_PATH.read_text()
                    self.assertIn("completed_read_only", audit)
                    self.assertIn("blocked_worker", audit)
                    self.assertNotIn(TOKEN, audit)
            finally:
                httpd.shutdown()
                httpd.server_close()
                server.AUDIT_PATH = previous

    def test_parent_strips_token_environment(self):
        class FakeProcess:
            returncode = 0
            def communicate(self, timeout):
                return (b'{"worker":"factory-runner-controlled","task":"diagnose","ok":true,"result":{"sandbox_ready":false}}', b'')
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "SECRET_TEST_TOKEN"}):
            with patch.object(server.subprocess, "Popen", return_value=FakeProcess()) as pop:
                value = server.run_controlled_worker("diagnose")
        self.assertFalse(value["sandbox_ready"])
        env = pop.call_args.kwargs["env"]
        self.assertNotIn("RUNNER_AUTH_TOKEN", env)
        self.assertEqual(env["GIT_TERMINAL_PROMPT"], "0")


    def test_parent_rejects_invalid_or_oversized_child_response(self):
        class FakeProcess:
            returncode = 0
            def __init__(self, out):
                self.out = out
            def communicate(self, timeout):
                return self.out, b""
        valid = b'{"worker":"factory-runner-controlled","task":"diagnose","ok":true,"result":{"sandbox_ready":false}}'
        for response in (b"not-json", b'{"worker":"bad","task":"diagnose","ok":true,"result":{}}',
                         b'{"worker":"factory-runner-controlled","task":"publish","ok":true,"result":{}}',
                         valid + b" " * 20000):
            with self.subTest(response=response[:18]):
                with patch.object(server.subprocess, "Popen", return_value=FakeProcess(response)):
                    with self.assertRaises(server.WorkerUnavailable):
                        server.run_controlled_worker("diagnose")

    def test_parent_times_out_and_kills_process_group(self):
        class TimeoutProcess:
            pid = 67890
            returncode = -9
            calls = 0
            def communicate(self, timeout=None):
                self.calls += 1
                if self.calls == 1:
                    raise server.subprocess.TimeoutExpired(cmd=["worker"], timeout=50)
                return b"", b""
        worker_process = TimeoutProcess()
        with patch.object(server.subprocess, "Popen", return_value=worker_process):
            with patch.object(server.os, "killpg") as kill:
                with self.assertRaises(server.WorkerUnavailable):
                    server.run_controlled_worker("diagnose")
        kill.assert_called_once_with(worker_process.pid, server.signal.SIGKILL)
        self.assertEqual(worker_process.calls, 2)

    def test_parent_never_passes_runner_or_github_tokens(self):
        class FakeProcess:
            returncode = 0
            def communicate(self, timeout):
                return (b'{"worker":"factory-runner-controlled","task":"diagnose","ok":true,"result":{"sandbox_ready":false}}', b'')
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "sensitive-runner-test",
                                     "GITHUB_TOKEN": "sensitive-git-test",
                                     "PYTHONPATH": "/tmp/untrusted"}):
            with patch.object(server.subprocess, "Popen", return_value=FakeProcess()) as pop:
                server.run_controlled_worker("diagnose")
        child_env = pop.call_args.kwargs["env"]
        for name in ("RUNNER_AUTH_TOKEN", "GITHUB_TOKEN", "PYTHONPATH"):
            self.assertNotIn(name, child_env)
        argv = pop.call_args.args[0]
        self.assertIn("-I", argv)
        self.assertNotIn("sensitive-runner-test", " ".join(argv))
        self.assertNotIn("sensitive-git-test", " ".join(argv))


if __name__ == "__main__":
    unittest.main()
