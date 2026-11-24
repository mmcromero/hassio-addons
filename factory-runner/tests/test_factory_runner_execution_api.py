"""Authenticated HTTP surface tests for FR-EXEC-001 planning endpoints."""
import http.client
import json
import sys
import threading
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import server


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
