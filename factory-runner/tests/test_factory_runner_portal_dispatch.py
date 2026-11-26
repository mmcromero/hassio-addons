"""Tests for the restricted Portal dispatch bridge."""
import http.client
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from portal_dispatch import PortalDispatchHTTPServer, PortalDispatchService


class FakeOrchestrator:
    def __init__(self):
        self.submitted = []
        self.job = {"execution_id": "00000000-0000-4000-8000-000000000001",
                    "status": "RECEBIDA", "project": "avisaqui"}

    def submit(self, contract, profile):
        self.submitted.append((contract, profile))
        self.job = {**self.job, "execution_id": contract["execution_id"],
                    "project": contract["project"]}
        return self.job, False

    def get(self, execution_id):
        return self.job


class PortalDispatchTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        root = Path(self.temp.name)
        projects = root / "projects"
        workspaces = root / "workspaces"
        projects.mkdir()
        workspaces.mkdir()
        (projects / "avisaqui.json").write_text("{}", encoding="utf-8")
        workspace = workspaces / "avisaqui"
        (workspace / "source").mkdir(parents=True)
        (workspace / "distribution").mkdir()
        self.orchestrator = FakeOrchestrator()
        self.service = PortalDispatchService(
            token="t" * 64, orchestrator=self.orchestrator,
            projects_dir=projects, workspaces_dir=workspaces,
        )
        self.httpd = PortalDispatchHTTPServer(("127.0.0.1", 0), self.service)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]
        self.addCleanup(self.cleanup)
        self.prompt = "Analisar o projeto e produzir um plano read-only sem executar código."

    def cleanup(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)
        self.temp.cleanup()

    def request(self, method, path, body=None, token="t" * 64):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        raw = json.dumps(body).encode() if body is not None else None
        headers = {"X-Portal-Dispatch-Token": token}
        if raw is not None:
            headers["Content-Type"] = "application/json"
        conn.request(method, path, body=raw, headers=headers)
        response = conn.getresponse()
        result = json.loads(response.read())
        conn.close()
        return response.status, result

    def test_requires_dedicated_dispatch_token(self):
        status, body = self.request("POST", "/v1/jobs", {
            "mission_id": "00000000-0000-4000-8000-000000000001",
            "project_id": "avisaqui", "prompt": self.prompt,
            "created_at": "2026-11-26T14:00:00.000Z",
        }, token="wrong")
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")

    def test_submits_only_plan_operation_and_never_grants_authorization(self):
        with patch("portal_dispatch.load_profile", return_value={
            "id": "avisaqui", "source_repo": "mmcromero/pager-virtual",
            "source_ref": "refs/remotes/origin/desenvolvimento",
        }), patch("portal_dispatch._existing", return_value={
            "source_sha": "a" * 40, "source_repo": "mmcromero/pager-virtual",
        }):
            status, body = self.request("POST", "/v1/jobs", {
                "mission_id": "00000000-0000-4000-8000-000000000001",
                "project_id": "avisaqui", "prompt": self.prompt,
            "created_at": "2026-11-26T14:00:00.000Z",
            })
        self.assertEqual(status, 202)
        contract = self.orchestrator.submitted[0][0]
        self.assertEqual(contract["requested_operations"], ["plan"])
        self.assertEqual(contract["authorization"]["declared_operations"], [])
        self.assertIsNone(contract["authorization"]["reference"])
        self.assertIsNone(contract["source"]["base_sha"])
        self.assertEqual(contract["source"]["sha"], "a" * 40)
        self.assertEqual(contract["scope"]["include_paths"], [])
        self.assertEqual(contract["limits"]["network_policy"], "none")
        self.assertEqual(contract["limits"]["data_access"], "approved_workspace")
        self.assertLessEqual(len(contract["objective"]), 900)
        self.assertTrue(any(item.startswith("portal_prompt_sha256:") for item in contract["scope"]["constraints"]))


    def test_rejects_project_outside_fixed_allowlist(self):
        with patch("portal_dispatch.load_profile") as load:
            with self.assertRaisesRegex(ValueError, "project_not_approved_for_portal"):
                self.service.submit({
                    "mission_id": "00000000-0000-4000-8000-000000000001",
                    "project_id": "unknown_project",
                    "prompt": self.prompt,
                    "created_at": "2026-11-26T14:00:00.000Z",
                })
        load.assert_not_called()

    def test_rejects_unknown_fields_and_secret_like_prompt(self):
        status, body = self.request("POST", "/v1/jobs", {
            "mission_id": "00000000-0000-4000-8000-000000000001",
            "project_id": "avisaqui", "prompt": self.prompt,
            "created_at": "2026-11-26T14:00:00.000Z", "operation": "publish",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "invalid_portal_payload")

        status, body = self.request("POST", "/v1/jobs", {
            "mission_id": "00000000-0000-4000-8000-000000000001",
            "project_id": "avisaqui", "prompt": self.prompt + " ghp_abcdefghijklmnopqrstuvwxyz123456",
            "created_at": "2026-11-26T14:00:00.000Z",
        })
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "secret_pattern_rejected")


    def test_retry_keeps_contract_timestamp_and_execution_id_stable(self):
        payload = {
            "mission_id": "00000000-0000-4000-8000-000000000003",
            "project_id": "avisaqui",
            "prompt": self.prompt,
            "created_at": "2026-11-26T14:00:00.000Z",
        }
        with patch("portal_dispatch.load_profile", return_value={
            "id": "avisaqui", "source_repo": "mmcromero/pager-virtual",
            "source_ref": "refs/remotes/origin/desenvolvimento",
        }), patch("portal_dispatch._existing", return_value={"source_sha": "a" * 40}):
            self.service.submit(payload)
            first_contract = self.orchestrator.submitted[-1][0]
            self.service.submit(payload)
            second_contract = self.orchestrator.submitted[-1][0]
        self.assertEqual(first_contract["execution_id"], second_contract["execution_id"])
        self.assertEqual(first_contract["created_at"], second_contract["created_at"])

    def test_get_job_requires_token_and_returns_real_orchestrator_state(self):
        status, body = self.request(
            "GET", "/v1/jobs/00000000-0000-4000-8000-000000000001"
        )
        self.assertEqual(status, 200)
        self.assertEqual(body["job"]["status"], "RECEBIDA")


if __name__ == "__main__":
    unittest.main()
