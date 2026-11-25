"""Local-only security regression tests; no Git writes or remote calls."""
import http.client
import importlib.util
import json
import os
import subprocess
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

    def test_runner_publication_routes_forward_only_strict_bindings_to_publisher_ipc(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        calls = []
        def fake_publisher(action, **body):
            calls.append((action, body))
            return {"state": "PREVIEW_NOT_CONSENT", "publication": "disabled"}
        preview = {"project": "avisaqui", "issue": 7, "receipt_digest": "a" * 64}
        publish = {**preview, "proposal_id": "b" * 32}
        reconcile = {"project": "avisaqui", "nonce": "c" * 32}
        with patch.object(server, "publisher_request", side_effect=fake_publisher):
            self.assertEqual(self.request("POST", "/api/publication-preview", preview)[0], 401)
            self.assertEqual(calls, [])
            for path, payload, action in (
                ("/api/publication-preview", preview, "preview"),
                ("/api/publication-propose", preview, "propose"),
                ("/api/publish", publish, "publish"),
                ("/api/publication-reconcile", reconcile, "reconcile"),
            ):
                code, response = self.request("POST", path, payload, auth)
                self.assertEqual(code, 200, response)
                self.assertEqual(response["result"]["publication"], "disabled")
                self.assertEqual(calls[-1], (action, payload))
            invalid = {**publish, "grant": {"forged": True}}
            self.assertEqual(
                self.request("POST", "/api/publish", invalid, auth)[0], 400
            )
        self.assertEqual(len(calls), 4)
        audit = server.AUDIT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("test-secret-not-for-production-0123456789", audit)
        self.assertNotIn("a" * 64, audit)
        self.assertNotIn("b" * 32, audit)
        self.assertNotIn("c" * 32, audit)

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

    def test_operations_requires_auth_and_returns_sanitized_status(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        self.assertEqual(self.request("GET", "/api/operations")[0], 401)
        self.assertEqual(self.request("GET", "/api/operations", token=auth),
                         (200, {"operations": [], "source": "sanitized_audit"}))
        with patch.object(server, "preflight_project", return_value={
                "eligible_for_preparation": False,
                "errors": ["NO_OPEN_PACKAGE"]}):
            code, response = self.request(
                "POST", "/api/preflight",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 200)
        code, listing = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 200)
        found = [item for item in listing["operations"]
                 if item["operation_id"] == response["operation_id"]]
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["status"], "completed_read_only")
        self.assertEqual(found[0]["action"], "/api/preflight")
        self.assertNotIn("test-secret-not-for-production", json.dumps(listing))
        self.assertNotIn("source_sha", json.dumps(listing))

    def test_operations_rejects_symlinked_log(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        private = Path(self.folder.name) / "private.txt"
        private.write_text("secret-not-for-client\n", encoding="utf-8")
        server.AUDIT_PATH.symlink_to(private)
        code, data = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 503)
        self.assertEqual(data["error"], "audit_unavailable")
        self.assertNotIn("secret-not-for-client", json.dumps(data))

    def test_operations_discard_untrusted_audit_fields(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        server.AUDIT_PATH.write_text(json.dumps({
            "operation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "action": "/api/preflight", "status": "requested",
            "time": "2026-11-20T05:00:00Z", "secret": "must-not-leak",
            "path": "/data/private", "actor": "attacker"
        }) + "\n")
        code, data = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 200)
        self.assertEqual(len(data["operations"]), 1)
        self.assertEqual(set(data["operations"][0]),
                         {"operation_id", "action", "status", "time"})
        self.assertNotIn("must-not-leak", json.dumps(data))
        self.assertNotIn("/data/private", json.dumps(data))

    def test_operations_ignore_invalid_audit_types(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        invalid = {
            "operation_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
            "action": {"not": "a-string"},
            "status": ["not-a-string"],
            "time": "2026-11-20T05:00:00Z"
        }
        server.AUDIT_PATH.write_text(json.dumps(invalid) + "\n")
        code, data = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 200)
        self.assertEqual(data["operations"], [])

    def test_operations_lists_real_workspace_sync_outcomes(self):
        # Workspace synchronization uses the existing audit writer, not HTTP
        # preflight. These states were omitted from the RC12 read-only listing.
        auth = "Bearer test-secret-not-for-production-0123456789"
        op = "cccccccc-cccc-cccc-cccc-cccccccccccc"
        with server.AUDIT_PATH.open("w", encoding="utf-8") as handle:
            for status in ("requested", "completed_workspace_sync", "blocked_policy"):
                handle.write(json.dumps({
                    "time": "2026-11-20T05:00:00Z",
                    "operation_id": op,
                    "action": "workspace_sync:avisaqui",
                    "issue": None, "actor": "trusted_startup",
                    "status": status
                }) + "\n")
        code, result = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 200)
        self.assertEqual(result["operations"], [{
            "operation_id": op, "action": "workspace_sync:avisaqui",
            "status": "blocked_policy", "time": "2026-11-20T05:00:00Z"
        }])

    def test_operations_rejects_invalid_workspace_project(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        server.AUDIT_PATH.write_text(json.dumps({
            "time": "2026-11-20T05:00:00Z",
            "operation_id": "dddddddd-dddd-dddd-dddd-dddddddddddd",
            "action": "workspace_sync:../private",
            "status": "completed_workspace_sync"
        }) + "\n", encoding="utf-8")
        code, result = self.request("GET", "/api/operations", token=auth)
        self.assertEqual(code, 200)
        self.assertEqual(result["operations"], [])

    def test_workspace_audit_health_reports_real_sanitized_events(self):
        # This checks the actual startup audit reader, not a synthetic
        # publication or a request that would need production credentials.
        for project, operation_id in (
                ("artesao_digital", "eeeeeeee-eeee-eeee-eeee-eeeeeeeeeeee"),
                ("avisaqui", "dddddddd-dddd-dddd-dddd-dddddddddddd")):
            server.record("workspace_sync:" + project, None,
                          "completed_workspace_sync", operation_id)
        with patch("builtins.print") as output:
            self.assertTrue(server.workspace_audit_health(
                ("artesao_digital", "avisaqui")))
        self.assertIn("sanitized_workspace_audit",
                      str(output.call_args_list))
        self.assertNotIn("eeeeeeee-eeee", str(output.call_args_list))

    def test_workspace_audit_health_fails_without_project_evidence(self):
        server.record("workspace_sync:avisaqui", None,
                      "completed_workspace_sync",
                      "ffffffff-ffff-ffff-ffff-ffffffffffff")
        with patch("builtins.print") as output:
            self.assertFalse(server.workspace_audit_health(
                ("artesao_digital", "avisaqui")))
        self.assertIn("workspace_audit_entries_missing",
                      str(output.call_args_list))

    def test_workspace_audit_health_fails_closed_on_unreadable_audit(self):
        private = Path(self.folder.name) / "private.txt"
        private.write_text("sensitive-data", encoding="utf-8")
        server.AUDIT_PATH.symlink_to(private)
        with patch("builtins.print") as output:
            self.assertFalse(server.workspace_audit_health(("avisaqui",)))
        self.assertIn("audit_unavailable", str(output.call_args_list))
        self.assertNotIn("sensitive-data", str(output.call_args_list))

    def test_release_plan_requires_auth_and_is_never_publication(self):
        auth = "Bearer test-secret-not-for-production-0123456789"
        payload = {"project": "avisaqui", "expected_source_sha": "a" * 40}
        self.assertEqual(self.request("POST", "/api/release-plan",
                                      payload=payload)[0], 401)
        with patch.object(server, "preflight_project", return_value={
                "eligible_for_preparation": False,
                "errors": ["NO_OPEN_PACKAGE", "VERSION_ALREADY_PUBLISHED"]}):
            code, data = self.request("POST", "/api/release-plan",
                                      payload=payload, token=auth)
        self.assertEqual(code, 200)
        plan = data["result"]
        self.assertFalse(plan["published"])
        self.assertEqual(plan["preparation"], "blocked_by_project_policy")
        self.assertIn("NO_OPEN_PACKAGE", plan["policy_errors"])
        self.assertEqual(plan["publication"],
                         "disabled_pending_independent_authorization")
        self.assertEqual(set(plan), {"project", "source_sha", "preparation",
                                    "policy_errors", "publication", "published",
                                    "requirements"})
        self.assertIn("completed_read_only",
                      server.AUDIT_PATH.read_text(encoding="utf-8"))

    def test_release_plan_never_promotes_eligible_preflight_to_approval(self):
        payload = {"project": "avisaqui", "expected_source_sha": "a" * 40}
        auth = "Bearer test-secret-not-for-production-0123456789"
        with patch.object(server, "preflight_project", return_value={
                "eligible_for_preparation": True, "errors": [],
                "private_token": "not-for-client",
                "workspace_path": "/data/private"}):
            code, data = self.request("POST", "/api/release-plan",
                                      payload=payload, token=auth)
        self.assertEqual(code, 200)
        self.assertEqual(data["result"]["preparation"],
                         "eligible_for_separate_preparation")
        self.assertFalse(data["result"]["published"])
        self.assertNotIn("not-for-client", json.dumps(data))
        self.assertNotIn("/data/private", json.dumps(data))
        self.assertNotIn("approved", data["result"]["publication"])

    def test_release_plan_rejects_untrusted_policy_results(self):
        payload = {"project": "avisaqui", "expected_source_sha": "a" * 40}
        auth = "Bearer test-secret-not-for-production-0123456789"
        for report in (
                {"eligible_for_preparation": 1, "errors": []},
                {"eligible_for_preparation": True, "errors": ["/data/secret"]},
                {"eligible_for_preparation": False, "errors": "NO_OPEN_PACKAGE"},
                {"eligible_for_preparation": True, "errors": [{"secret": True}]}):
            with self.subTest(report=report):
                with patch.object(server, "preflight_project", return_value=report):
                    code, data = self.request("POST", "/api/release-plan",
                                              payload=payload, token=auth)
                self.assertEqual(code, 503)
                self.assertEqual(data["error"], "workspace_or_export_unavailable")
                self.assertNotIn("secret", json.dumps(data))

    def test_release_plan_rejects_client_supplied_approval(self):
        payload = {"project": "avisaqui", "expected_source_sha": "a" * 40,
                   "owner_approved": True}
        code, data = self.request(
            "POST", "/api/release-plan", payload=payload,
            token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 400)
        self.assertEqual(data["error"], "invalid_payload")

    def test_release_plan_health_validates_blocked_package(self):
        with (patch.object(server, "release_plan", return_value={
                "publication": "disabled_pending_independent_authorization",
                "published": False, "preparation": "blocked_by_project_policy"}),
              patch("builtins.print") as printed):
            self.assertTrue(server.release_plan_health("avisaqui", "a" * 40))
        out = str(printed.call_args_list)
        self.assertIn("[RELEASE-PLAN] PASS", out)
        self.assertIn("publication=disabled", out)

    def test_release_plan_health_refuses_published_result(self):
        with (patch.object(server, "release_plan", return_value={
                "publication": "disabled_pending_independent_authorization",
                "published": True, "preparation": "eligible_for_separate_preparation"}),
              patch("builtins.print") as printed):
            self.assertFalse(server.release_plan_health("avisaqui", "a" * 40))
        self.assertIn("preflight_unavailable", str(printed.call_args_list))

    def test_release_plan_health_handles_unavailable_workspace_without_leak(self):
        with (patch.object(server, "release_plan",
                           side_effect=server.PreflightError("/data/private-token")),
              patch("builtins.print") as printed):
            self.assertFalse(server.release_plan_health("avisaqui", "a" * 40))
        self.assertNotIn("/data/private-token", str(printed.call_args_list))

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
        # The route resolves its workspace before evaluating package policy.
        # Provide only a synthetic workspace; do not change fail-closed behavior.
        with (patch.object(server, "project_workspace", return_value=(
                  {"mode": "avisaqui"}, Path(self.folder.name), Path(self.folder.name))),
              patch.object(server, "preflight_project", return_value={
                  "eligible_for_preparation": False, "errors": ["NO_OPEN_PACKAGE"]
              }),
              patch.object(server, "prepare_declarative") as executor):
            code, data = self.request(
                "POST", "/api/prepare-declarative",
                payload={"project": "avisaqui", "expected_source_sha": "a" * 40},
                token=auth)
        self.assertEqual(code, 409)
        self.assertEqual(data["details"], ["NO_OPEN_PACKAGE"])
        executor.assert_not_called()

    def test_declarative_ci_uses_pinned_public_commit(self):
        trusted = "b" * 40
        exporter_blob = "c" * 40
        profile = {
            "declarative_mapping": {
                "demo/config.yaml": "config.yaml",
                "demo/package.json": "package.json"},
            "package_json_path": "package.json",
            "manifest_path": "config.yaml",
            "exporter_path": "scripts/export.py",
            "exporter_git_blob_sha": exporter_blob,
            "declarative_ci": {
                "patch_source": "ci/approved.patch",
                "workflow_path": ".github/workflows/validate.yml",
                "compatible_markers": ["trusted-marker"]},
            "distribution_prefix": "demo/",
            "provenance_path": "demo/SOURCE_PROVENANCE.json",
            "source_repo": "fixture/source",
            "allowed_shared_paths": [".github/workflows/validate.yml"],
        }
        public_commit = trusted + ":.github/workflows/validate.yml"
        calls = []
        def read_pinned(repo, *args):
            calls.append(args)
            if args == ("show", public_commit):
                return "trusted-marker"
            if args == ("rev-parse", "a" * 40 + ":scripts/export.py"):
                return exporter_blob
            if args == ("rev-parse", "a" * 40 + ":ci/approved.patch"):
                return "d" * 40
            raise AssertionError("unexpected Git operation: " + repr(args))
        with patch.object(server, "preflight_project", return_value={
            "eligible_for_preparation": True,
            "candidate_version": "0.0.1",
            "public_main_sha": trusted
        }), patch.object(server, "project_workspace", return_value=(
            profile, Path(self.folder.name) / "source",
            Path(self.folder.name) / "distribution"
        )), patch.object(server, "trusted_git", side_effect=read_pinned), (
            patch.object(server, "PREPARATIONS_DIR", Path(self.folder.name) / "preparations")
        ), patch.object(server, "_store_declarative", return_value={
            "state": "PREPARED_NOT_PUBLISHED"
        }) as copied:
            result = server.prepare_project_declarative("avisaqui", "a" * 40, "fixture")
        self.assertEqual(result["state"], "PREPARED_NOT_PUBLISHED")
        self.assertIn(("show", public_commit), calls)
        copied.assert_called_once()

    def test_declarative_ci_rejects_incompatible_pinned_commit(self):
        from declarative_export import DeclarativeExportError
        profile = {
            "declarative_mapping": {
                "demo/config.yaml": "config.yaml",
                "demo/package.json": "package.json"},
            "package_json_path": "package.json",
            "manifest_path": "config.yaml",
            "exporter_path": "scripts/export.py",
            "exporter_git_blob_sha": "c" * 40,
            "declarative_ci": {
                "patch_source": "ci/approved.patch",
                "workflow_path": ".github/workflows/validate.yml",
                "compatible_markers": ["trusted-marker"]},
        }
        def fake_git(repo, *args):
            if args[0] == "show":
                return "incompatible"
            if args[-1].endswith(":scripts/export.py"):
                return "c" * 40
            return "d" * 40
        with patch.object(server, "preflight_project", return_value={
            "eligible_for_preparation": True,
            "candidate_version": "0.0.1",
            "public_main_sha": "b" * 40
        }), patch.object(server, "project_workspace", return_value=(
            profile, Path(self.folder.name), Path(self.folder.name)
        )), patch.object(server, "trusted_git", side_effect=fake_git), (
            patch.object(server, "prepare_declarative")
        ) as copied:
            with self.assertRaisesRegex(
                    DeclarativeExportError, "ci_patch_requires_separate_review"):
                server.prepare_project_declarative("avisaqui", "a" * 40, "fixture")
            copied.assert_not_called()

    def test_standard_prepare_dispatches_approved_declarative_recipe(self):
        # Standard endpoint must not invoke a source script or Bubblewrap when
        # the installed profile has an approved deterministic export recipe.
        project = {"declarative_mapping": {"demo/config.yaml": "config.yaml"}}
        ready = {"eligible": True, "state": "PREPARED_NOT_PUBLISHED",
                 "published": False, "method": "declarative_no_script"}
        with patch.object(server, "project_workspace", return_value=(
                project, Path(self.folder.name), Path(self.folder.name))), (
                patch.object(server, "prepare_project_declarative",
                             return_value=ready)) as declarative, (
                patch.object(server, "prepare",
                             side_effect=AssertionError("legacy exporter called"))):
            code, response = self.request(
                "POST", "/api/prepare",
                payload={"project": "avisaqui",
                         "expected_source_sha": "a" * 40},
                token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 200, response)
        self.assertEqual(response["result"]["method"], "declarative_no_script")
        self.assertFalse(response["result"]["published"])
        declarative.assert_called_once()

    def test_standard_prepare_without_recipe_remains_fail_closed(self):
        with patch.object(server, "project_workspace", return_value=(
                {}, Path(self.folder.name), Path(self.folder.name))), (
                patch.object(server, "evaluate",
                             side_effect=server.PreflightError("blocked"))), (
                patch.object(server, "prepare",
                             side_effect=AssertionError("untrusted exporter called"))):
            code, response = self.request(
                "POST", "/api/prepare",
                payload={"project": "avisaqui",
                         "expected_source_sha": "a" * 40},
                token="Bearer test-secret-not-for-production-0123456789")
        self.assertEqual(code, 503, response)
        self.assertEqual(response["error"], "workspace_or_export_unavailable")

    def test_bad_issue_rejected(self):
        for value in (0, -1, True, "35", 100000000):
            self.assertEqual(self.request("POST", "/api/fechar-pacote",
                payload={"issue": value}, token="Bearer test-secret-not-for-production-0123456789")[0], 400)

    def test_bad_json_rejected(self):
        self.assertEqual(self.request("POST", "/api/corrigir-issue",
            token="Bearer test-secret-not-for-production-0123456789", raw=b"{not json")[0], 400)

    def test_authority_services_start_without_runner_credentials(self):
        run_script = (ADDON / "run.sh").read_text(encoding="utf-8")
        expected = {"approval": 1, "publisher": 1, "owner_ui": 2}
        for service, count in expected.items():
            launches = [
                line.strip() for line in run_script.splitlines()
                if f"su-exec {service} python3" in line
            ]
            self.assertEqual(len(launches), count, service)
            for command in launches:
                self.assertTrue(
                    command.startswith(
                        f"env -i PATH=/usr/sbin:/usr/bin:/sbin:/bin su-exec {service} "
                    ),
                    command,
                )
                self.assertNotIn("RUNNER_AUTH_TOKEN", command)
                self.assertNotIn("RUNNER_GITHUB_READ_TOKEN", command)

        # The API remains the only child that receives its own Bearer and
        # workspace read token; clean service launches do not change this.
        self.assertIn("export RUNNER_AUTH_TOKEN", run_script)
        self.assertIn(
            "export RUNNER_WORKSPACE_SYNC_ENABLED RUNNER_GITHUB_READ_TOKEN RUNNER_WORKSPACE_AUTO_PREPARE",
            run_script,
        )
        self.assertIn("su-exec runner python3 -u /app/server.py &", run_script)

    def test_env_i_removes_inherited_runner_secrets(self):
        parent_env = os.environ.copy()
        parent_env.update({
            "RUNNER_AUTH_TOKEN": "synthetic-runner-bearer",
            "RUNNER_GITHUB_READ_TOKEN": "synthetic-read-token",
            "UNRELATED_SECRET": "synthetic-unrelated-secret",
        })
        probe = "import json,os; print(json.dumps(sorted(os.environ)))"
        result = subprocess.run(
            ["/usr/bin/env", "-i", "PATH=/usr/bin:/bin",
             sys.executable, "-I", "-c", probe],
            env=parent_env, capture_output=True, text=True, check=True, timeout=5,
        )
        observed = set(json.loads(result.stdout))
        self.assertIn("PATH", observed)
        self.assertLessEqual(observed, {"PATH", "LC_CTYPE"})
        self.assertNotIn("synthetic-runner-bearer", result.stdout)
        self.assertNotIn("synthetic-read-token", result.stdout)
        self.assertNotIn("synthetic-unrelated-secret", result.stdout)

    def test_audit_record_fsyncs_file_and_new_directory_entry(self):
        with patch.object(server.os, "fsync") as sync:
            server.record("workspace_sync:avisaqui", None,
                          "completed_workspace_sync",
                          "a" * 8 + "-1234-1234-1234-" + "a" * 12)
        self.assertEqual(sync.call_count, 2)

    def test_audit_record_fsyncs_each_append(self):
        server.AUDIT_PATH.write_text("", encoding="utf-8")
        with patch.object(server.os, "fsync") as sync:
            server.record("workspace_sync:avisaqui", None,
                          "completed_workspace_sync",
                          "b" * 8 + "-1234-1234-1234-" + "b" * 12)
        self.assertEqual(sync.call_count, 1)

    def test_audit_does_not_contain_secret(self):
        self.request("POST", "/api/corrigir-issue", token="Bearer test-secret-not-for-production-0123456789")
        data = server.AUDIT_PATH.read_text(encoding="utf-8")
        self.assertNotIn("test-secret-not-for-production-0123456789", data)
        self.assertIn("blocked_authorization", data)

if __name__ == "__main__":
    unittest.main()
