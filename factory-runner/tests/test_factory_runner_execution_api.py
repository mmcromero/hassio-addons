"""Authenticated HTTP surface tests for FR-EXEC-001 planning endpoints."""
import http.client
import json
import sys
import threading
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server
from execution_orchestrator import OrchestrationError


class ExecutionApiTests(unittest.TestCase):
    def setUp(self):
        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self.port = self.httpd.server_address[1]
        self.addCleanup(self._stop)

    def _stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=3)

    def _request(self, method, path, body=None):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=3)
        payload = json.dumps(body) if body is not None else None
        conn.request(method, path, body=payload, headers={"Content-Type": "application/json"})
        response = conn.getresponse()
        raw = response.read()
        conn.close()
        return response.status, json.loads(raw) if raw else None

    def test_execution_plan_requires_authentication(self):
        with patch.object(server, "authenticated", return_value=False):
            status, body = self._request("POST", "/api/execution-plan", {"project": "sample"})
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")

    def test_execution_plan_is_authenticated_and_returns_persisted_plan(self):
        execution_id = str(uuid.uuid4())
        plan = {"format": "factory-execution-plan-v1", "execution_id": execution_id,
                "status": "PLANNED", "tests": {"execution_performed": False}}
        profile = {"id": "sample"}
        with patch.object(server, "authenticated", return_value=True), \
             patch.object(server, "record"), \
             patch.object(server, "project_workspace",
                          return_value=(profile, Path("/tmp/source"), Path("/tmp/distribution"))), \
             patch("workspace_sync._existing", return_value={"source_sha": "a" * 40,
                                                             "source_repo": "example/sample"}), \
             patch("execution_planner.plan_execution", return_value=(plan, True)) as make_plan:
            status, body = self._request("POST", "/api/execution-plan", {
                "project": "sample", "execution_id": execution_id,
            })
            self.assertEqual(status, 200)
            self.assertTrue(body["idempotent"])
            self.assertEqual(body["plan"], plan)
            make_plan.assert_called_once()

            with patch("execution_planner.get_execution", return_value=plan):
                status, result = self._request("GET", "/api/executions/" + execution_id)
            self.assertEqual(status, 200)
            self.assertEqual(result["plan"], plan)


    def test_jobs_submission_requires_authentication(self):
        with patch.object(server, "authenticated", return_value=False):
            status, body = self._request("POST", "/api/jobs", {"project": "sample"})
        self.assertEqual(status, 401)
        self.assertEqual(body["error"], "unauthorized")

    def test_jobs_submission_is_authenticated_and_idempotent(self):
        execution_id = str(uuid.uuid4())
        job = {"execution_id": execution_id, "job_id": execution_id,
               "status": "RECEBIDA", "project": "sample"}
        class FakeOrchestrator:
            def submit(self, contract, profile):
                return job, False
        profile = {"id": "sample"}
        with tempfile.TemporaryDirectory() as directory:
            profile_path = Path(directory) / "sample.json"
            profile_path.write_text("{}", encoding="utf-8")
            with patch.object(server, "authenticated", return_value=True), \
                 patch.object(server, "ORCHESTRATOR", FakeOrchestrator()), \
                 patch.object(server, "PROJECTS_DIR", Path(directory)), \
                 patch.object(server, "load_profile", return_value=profile), \
                 patch.object(server, "record") as audit:
                status, body = self._request("POST", "/api/jobs", {
                    "execution_id": execution_id, "project": "sample",
                })
            self.assertEqual(status, 202)
            self.assertFalse(body["idempotent"])
            self.assertEqual(body["job"]["execution_id"], execution_id)
            self.assertEqual(audit.call_args_list[0].args[2], "requested")

    def test_job_get_list_cancel_and_retry_routes(self):
        execution_id = str(uuid.uuid4())
        job = {"execution_id": execution_id, "status": "RECEBIDA"}
        class FakeOrchestrator:
            def get(self, job_id):
                return job
            def list(self, **kwargs):
                return {"jobs": [job], "total": 1, "limit": 25,
                        "offset": 0, "next_offset": None}
            def cancel(self, job_id):
                return {**job, "status": "CANCELADA"}
            def retry(self, job_id):
                return {**job, "status": "RECEBIDA"}
        with patch.object(server, "authenticated", return_value=True), \
             patch.object(server, "ORCHESTRATOR", FakeOrchestrator()), \
             patch.object(server, "record"):
            status, body = self._request("GET", "/api/jobs/" + execution_id)
            self.assertEqual(status, 200)
            self.assertEqual(body["job"], job)

            status, body = self._request("GET", "/api/jobs?project=sample&limit=1")
            self.assertEqual(status, 200)
            self.assertEqual(body["total"], 1)

            status, body = self._request("POST", "/api/jobs/" + execution_id + "/cancel", {})
            self.assertEqual(status, 202)
            self.assertEqual(body["job"]["status"], "CANCELADA")

            status, body = self._request("POST", "/api/jobs/" + execution_id + "/retry", {})
            self.assertEqual(status, 202)
            self.assertEqual(body["job"]["status"], "RECEBIDA")

    def test_job_routes_fail_closed_when_orchestrator_is_unavailable(self):
        with patch.object(server, "authenticated", return_value=True), \
             patch.object(server, "ORCHESTRATOR", None):
            status, body = self._request("GET", "/api/jobs")
        self.assertEqual(status, 503)
        self.assertEqual(body["error"], "orchestration_unavailable")

    def test_job_identifier_validation_is_not_reported_as_server_failure(self):
        execution_id = "a" * 36
        class FakeOrchestrator:
            def get(self, job_id):
                raise OrchestrationError("invalid_execution_id")
        with patch.object(server, "authenticated", return_value=True), \
             patch.object(server, "ORCHESTRATOR", FakeOrchestrator()):
            status, body = self._request("GET", "/api/jobs/" + execution_id)
        self.assertEqual(status, 400)
        self.assertEqual(body["error"], "invalid_execution_id")

    def test_evidence_write_endpoint_is_not_exposed(self):
        status, body = self._request("POST", "/api/execution-evidence", {"result": "PASS"})
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "not_found")

    def test_unknown_execution_route_is_not_exposed(self):
        status, body = self._request("GET", "/api/executions/not-a-uuid")
        self.assertEqual(status, 404)
        self.assertEqual(body["error"], "not_found")


if __name__ == "__main__":
    unittest.main()
