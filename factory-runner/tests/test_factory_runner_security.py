"""Local-only security regression tests; no Git writes or remote calls."""
import http.client
import importlib.util
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT if (ROOT / "server.py").is_file() else ROOT / "factory-runner-add-on"
SOURCE = ADDON / "server.py"
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("factory_runner_server", SOURCE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

class SecurityTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {
            "RUNNER_AUTH_TOKEN": "test-secret-not-for-production-0123456789",
        })
        self.env.start()
        self.addCleanup(self.env.stop)
        self.audit = server.AUDIT_PATH
        server.AUDIT_PATH = Path(self.folder.name) / "audit.jsonl"
        self.addCleanup(setattr, server, "AUDIT_PATH", self.audit)
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.worker = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.http.server_close)
        self.addCleanup(self.http.shutdown)

    def request(self, method, path, payload=None, token=None, raw=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.http.server_port, timeout=4)
        body = raw if raw is not None else json.dumps(payload or {"issue": 35}).encode()
        headers = {"Content-Type": "application/json"}
        if token is not None:
            headers["Authorization"] = token
        connection.request(method, path, body=body if method == "POST" else None, headers=headers)
        response = connection.getresponse()
        code, content = response.status, json.loads(response.read().decode())
        connection.close()
        return code, content

    def test_missing_auth(self):
        self.assertEqual(self.request("POST", "/api/fechar-pacote")[0], 401)

    def test_wrong_auth(self):
        self.assertEqual(self.request("POST", "/api/corrigir-issue", token="Bearer wrong")[0], 401)

    def test_missing_server_secret_fails_closed(self):
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": ""}):
            self.assertEqual(self.request("POST", "/api/corrigir-issue", token="Bearer test-secret-not-for-production-0123456789")[0], 401)

    def test_short_secret_fails_closed(self):
        with patch.dict(os.environ, {"RUNNER_AUTH_TOKEN": "short"}):
            self.assertEqual(
                self.request("POST", "/api/fechar-pacote",
                             token="Bearer short")[0], 401)

    def test_long_content_length_rejected(self):
        connection = http.client.HTTPConnection(
            "127.0.0.1", self.http.server_port, timeout=4)
        connection.request(
            "POST", "/api/fechar-pacote", body=b"{}",
            headers={"Authorization": "Bearer test-secret-not-for-production-0123456789",
                     "Content-Length": "9" * 100})
        self.assertEqual(connection.getresponse().status, 400)
        connection.close()

    def test_malformed_auth(self):
        for value in ("Basic test-secret-not-for-production-0123456789", "Bearer", "Bearer  test-secret-not-for-production-0123456789"):
            self.assertEqual(self.request("POST", "/api/fechar-pacote", token=value)[0], 401)

    def test_authenticated_actions_blocked_without_owner_approval(self):
        for path in server.OPERATIONS:
            code, data = self.request("POST", path, token="Bearer test-secret-not-for-production-0123456789")
            self.assertEqual(code, 403)
            self.assertEqual(data["error"], "owner_approval_required")

    def test_status_is_authenticated_and_sanitized(self):
        self.assertEqual(self.request("GET", "/api/status")[0], 401)
        code, data = self.request("GET", "/api/status", token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 200)
        self.assertNotIn("pager_virtual", data)

    def test_project_list_requires_token(self):
        self.assertEqual(self.request("GET", "/api/projects")[0], 401)
        code, data = self.request(
            "GET", "/api/projects",
            token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 200)
        self.assertIn("projects", data)
        self.assertIsInstance(data["projects"], list)
        self.assertFalse(any("token" in str(item).lower() for item in data["projects"]))

    def test_preflight_requires_auth_and_rejects_unknown_project(self):
        self.assertEqual(self.request("POST", "/api/preflight",
            payload={"project": "avisaqui", "expected_source_sha": "a" * 40})[0], 401)
        code, data = self.request("POST", "/api/preflight",
            payload={"project": "../private", "expected_source_sha": "a" * 40},
            token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 400)
        self.assertEqual(data["error"], "invalid_project_or_sha")

    def test_preflight_cannot_publish_or_write_and_audits(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "preflight_project", return_value={
            "project": "avisaqui", "eligible_for_preparation": False,
            "errors": ["NO_OPEN_PACKAGE"], "mode": "read_only"}):
            code, data = self.request("POST", "/api/preflight",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 200)
        self.assertFalse(data["result"]["eligible_for_preparation"])
        self.assertEqual(data["result"]["mode"], "read_only")
        self.assertIn("operation_id", data)
        audit = server.AUDIT_PATH.read_text(encoding="utf-8")
        self.assertIn("completed_read_only", audit)
        self.assertNotIn("test-secret-not-for-production-0123456789", audit)

    def test_preflight_missing_workspace_is_unavailable_not_success(self):
        with patch.object(server, "preflight_project",
                          side_effect=server.PreflightError("unavailable")):
            code, data = self.request("POST", "/api/preflight",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 503)
        self.assertEqual(data["error"], "workspace_or_export_unavailable")

    def test_prepare_is_local_only_and_cannot_publish(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "prepare_project", return_value={
            "eligible": True, "state": "PREPARED_NOT_PUBLISHED",
            "published": False, "changed_files": 3, "source_sha": "a" * 40
        }):
            code, data = self.request("POST", "/api/prepare",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 200)
        self.assertFalse(data["result"]["published"])
        self.assertEqual(data["result"]["state"], "PREPARED_NOT_PUBLISHED")
        self.assertIn("completed_preparation",
                      server.AUDIT_PATH.read_text(encoding="utf-8"))

    def test_prepare_rejects_client_selected_paths(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        code, data = self.request("POST", "/api/prepare",
            payload={"project": "avisaqui", "expected_source_sha": "a" * 40,
                     "output": "/etc/passwd"}, token=auth)
        self.assertEqual(code, 400)
        self.assertEqual(data["error"], "invalid_payload")

    def test_prepare_ineligible_package_returns_conflict(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "prepare_project", return_value={
            "eligible": False, "errors": ["NO_OPEN_PACKAGE"]
        }):
            code, data = self.request("POST", "/api/prepare",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 409)
        self.assertEqual(data["details"], ["NO_OPEN_PACKAGE"])

    def test_prepare_fails_closed_without_workspace(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "prepare_project",
                          side_effect=server.PreflightError("workspace missing")):
            code, data = self.request("POST", "/api/prepare",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 503)
        self.assertEqual(data["error"], "workspace_or_export_unavailable")

    def test_declarative_endpoint_requires_auth_and_rejects_client_mapping(self):
        payload = {"project": "avisaqui", "expected_source_sha": "a" * 40}
        self.assertEqual(self.request(
            "POST", "/api/prepare-declarative", payload=payload)[0], 401)
        code, data = self.request(
            "POST", "/api/prepare-declarative",
            payload=dict(payload, declarative_mapping={"private": "password"}),
            token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 400)
        self.assertEqual(data["error"], "invalid_payload")

    def test_declarative_endpoint_fails_closed_without_approved_mapping(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "preflight_project", return_value={
            "eligible_for_preparation": True, "candidate_version": "0.0.1"
        }), patch.object(server, "project_workspace", return_value=(
            {"id": "avisaqui"}, Path(self.folder.name), Path(self.folder.name))):
            code, data = self.request(
                "POST", "/api/prepare-declarative",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 503)
        self.assertEqual(data["error"], "workspace_or_export_unavailable")
        self.assertIn("blocked_workspace_or_git", server.AUDIT_PATH.read_text())

    def test_declarative_endpoint_respects_closed_package(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "preflight_project", return_value={
            "eligible_for_preparation": False, "errors": ["NO_OPEN_PACKAGE"]
        }), patch.object(server, "prepare_declarative") as executor:
            code, data = self.request(
                "POST", "/api/prepare-declarative",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 409)
        self.assertEqual(data["details"], ["NO_OPEN_PACKAGE"])
        executor.assert_not_called()

    def test_bad_issue_rejected(self):
        for value in (0, -1, True, "35", 100000000):
            self.assertEqual(self.request("POST", "/api/fechar-pacote",
                payload={"issue": value}, token="Bearer test-secret-not-for-production-0123456789")[0], 400)

    def test_bad_json_rejected(self):
        self.assertEqual(self.request("POST", "/api/corrigir-issue",
            token="Bearer test-secret-not-for-production-0123456789", raw=b"{not json")[0], 400)

    def test_audit_does_not_contain_secret(self):
        self.request("POST", "/api/corrigir-issue", token="Bearer test-secret-not-for-production-0123456789")
        data = server.AUDIT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("test-secret-not-for-production-0123456789", data)
        self.assertIn("blocked_authorization", data)

if __name__ == "__main__":
    unittest.main()
