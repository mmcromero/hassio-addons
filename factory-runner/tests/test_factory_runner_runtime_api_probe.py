"""Tests for the in-container live API smoke probe; no real credentials/network."""
import unittest
from unittest.mock import patch

from runtime_api_probe import ProbeError, run_probe


class RuntimeApiProbeTests(unittest.TestCase):
    TOKEN = "synthetic-probe-token-that-is-not-real-012345"

    def fake_requester(self, *, publish=False, bad_audit=False):
        calls = []
        operations = []
        def request(method, path, token, payload=None):
            calls.append((method, path, token, payload))
            if path == "/api/status" and not token:
                return 401, {"error": "unauthorized"}
            if path == "/api/status":
                return 200, {
                    "status": "read_only_preflight",
                    "publication": "disabled",
                    "autonomous_changes": "disabled",
                    "controlled_worker": "read_only_only",
                }
            if path == "/api/projects":
                return 200, {"projects": [
                    {"id": "avisaqui", "publication": "disabled"}
                ]}
            if path == "/api/publication-status":
                return 200, {"publication": "disabled",
                             "published": True if publish else False}
            if path == "/api/preflight":
                operation = "a" * 8 + "-1234-1234-1234-" + "a" * 12
                operations.append({"operation_id": operation,
                                   "action": path,
                                   "status": "completed_read_only"})
                return 200, {"operation_id": operation, "result": {
                    "eligible_for_preparation": False,
                    "errors": ["NO_OPEN_PACKAGE"],
                }}
            if path == "/api/release-plan":
                operation = "b" * 8 + "-1234-1234-1234-" + "b" * 12
                operations.append({"operation_id": operation,
                                   "action": path,
                                   "status": "completed_read_only"})
                return 200, {"operation_id": operation, "result": {
                    "preparation": "blocked_by_project_policy",
                    "publication": "disabled_pending_independent_authorization",
                    "published": False,
                }}
            if path == "/api/operations":
                if bad_audit:
                    return 200, {"source": "sanitized_audit", "operations": []}
                return 200, {"source": "sanitized_audit",
                             "operations": operations}
            raise AssertionError("unexpected route: " + path)
        return request, calls

    def test_live_api_probe_uses_only_read_and_preflight_routes(self):
        requester, calls = self.fake_requester()
        result = run_probe(self.TOKEN, [("avisaqui", "a" * 40)], requester)
        self.assertEqual(result["projects"], 1)
        self.assertEqual(result["preflight_checks"], 1)
        paths = [item[1] for item in calls]
        self.assertIn("/api/preflight", paths)
        self.assertIn("/api/release-plan", paths)
        self.assertNotIn("/api/prepare", paths)
        self.assertNotIn("/api/prepare-declarative", paths)
        self.assertNotIn("/api/publish", paths)
        self.assertNotIn("/api/publication-propose", paths)
        self.assertNotIn("/api/publication-reconcile", paths)

    def test_live_api_probe_retries_while_workspace_sync_holds_api_lock(self):
        requester, calls = self.fake_requester()
        seen = {"busy": False}
        def transient_busy(method, path, token, payload=None):
            if path == "/api/preflight" and not seen["busy"]:
                seen["busy"] = True
                return 409, {"error": "busy"}
            return requester(method, path, token, payload)
        with patch("runtime_api_probe.time.sleep"):
            result = run_probe(self.TOKEN, [("avisaqui", "a" * 40)], transient_busy)
        self.assertTrue(seen["busy"])
        self.assertEqual(result["preflight_checks"], 1)

    def test_live_api_probe_fails_if_publication_is_reported(self):
        requester, _ = self.fake_requester(publish=True)
        with self.assertRaisesRegex(ProbeError, "publication_status_unsafe"):
            run_probe(self.TOKEN, [], requester)

    def test_live_api_probe_requires_audited_read_only_operations(self):
        requester, _ = self.fake_requester(bad_audit=True)
        with self.assertRaisesRegex(ProbeError, "read_only_operation_not_audited"):
            run_probe(self.TOKEN, [("avisaqui", "a" * 40)], requester)


if __name__ == "__main__":
    unittest.main()
