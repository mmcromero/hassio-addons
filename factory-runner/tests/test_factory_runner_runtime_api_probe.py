"""Tests for the in-container live API smoke probe; no real credentials/network."""
import unittest
from unittest.mock import patch

from runtime_api_probe import ProbeError, run_probe


class RuntimeApiProbeTests(unittest.TestCase):
    TOKEN = "synthetic-probe-token-that-is-not-real-012345"

    def fake_requester(self, *, publish=False, bad_audit=False, prior_audit=False):
        calls = []
        operations = []
        if prior_audit:
            operations.append({
                "operation_id": "c" * 8 + "-1234-1234-1234-" + "c" * 12,
                "action": "workspace_sync:avisaqui",
                "status": "completed_workspace_sync",
                "time": "2026-11-24T18:00:00Z",
            })
        def request(method, path, token, payload=None, timeout=3):
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
            if path == "/api/execution-plan":
                operation = "d" * 8 + "-1234-1234-1234-" + "d" * 12
                operations.append({"operation_id": operation,
                                   "action": path,
                                   "status": "completed_read_only"})
                return 200, {"operation_id": operation, "idempotent": True,
                             "plan": {
                                 "format": "factory-execution-plan-v1",
                                 "project": payload["project"],
                                 "source": {"sha": payload["source"]["sha"]},
                                 "status": "PARTIAL",
                                 "tests": {"execution_performed": False,
                                           "selected_count": 2, "reused_count": 0,
                                           "omitted_count": 1},
                                 "operations": {"authorization_verified": False},
                                 "receipt": {"digest": "e" * 64},
                             }}
            if method == "GET" and path.startswith("/api/executions/"):
                return 200, {"plan": {
                    "receipt": {"digest": "e" * 64},
                }}
            if path == "/api/operations":
                if bad_audit:
                    return 200, {"source": "sanitized_audit", "operations": []}
                return 200, {"source": "sanitized_audit",
                             "operations": operations}
            raise AssertionError("unexpected route: " + path)
        return request, calls

    def test_isolated_runtime_import_path_is_explicit(self):
        import runtime_api_probe
        self.assertIn("/app", runtime_api_probe.sys.path)

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

    def test_live_api_probe_checks_execution_plan_without_running_tests(self):
        requester, calls = self.fake_requester()
        factory = lambda project, sha: {
            "execution_id": "00000000-0000-4000-8000-000000000001",
            "project": project, "source": {"sha": sha},
        }
        result = run_probe(
            self.TOKEN, [("avisaqui", "a" * 40)], requester,
            execution_contract_factory=factory)
        self.assertIn("/api/execution-plan", [item[1] for item in calls])
        self.assertEqual(result["audited_read_only_operations"], 3)
        self.assertEqual(result["results"][0][4]["selected"], 2)

    def test_live_api_probe_retries_while_workspace_sync_holds_api_lock(self):
        requester, calls = self.fake_requester()
        seen = {"busy": False}
        def transient_busy(method, path, token, payload=None, timeout=3):
            if path == "/api/preflight" and not seen["busy"]:
                seen["busy"] = True
                return 409, {"error": "busy"}
            return requester(method, path, token, payload, timeout=timeout)
        with patch("runtime_api_probe.time.sleep"):
            result = run_probe(self.TOKEN, [("avisaqui", "a" * 40)], transient_busy)
        self.assertTrue(seen["busy"])
        self.assertEqual(result["preflight_checks"], 1)

    def test_live_api_probe_detects_audit_events_from_before_current_boot(self):
        requester, _ = self.fake_requester(prior_audit=True)
        result = run_probe(
            self.TOKEN, [], requester,
            boot_started_at="2026-11-24T19:00:00Z")
        self.assertEqual(result["prior_boot_audit_events"], 1)

    def test_main_passes_boot_timestamp_into_live_probe(self):
        from runtime_api_probe import main, build_execution_contract

        timestamp = "2026-11-24T19:00:00Z"
        expected_result = {
            "projects": 0,
            "preflight_checks": 0,
            "audited_read_only_operations": 0,
            "prior_boot_audit_events": 2,
            "results": [],
        }
        with patch.dict("os.environ", {
            "RUNNER_AUTH_TOKEN": self.TOKEN,
            "RUNNER_API_PROBE_BOOT_STARTED_AT": timestamp,
            "RUNNER_API_PROBE_EXPECT_WORKSPACES": "false",
        }, clear=True), patch(
            "runtime_api_probe.request_json", return_value=(200, {})
        ), patch(
            "runtime_api_probe.run_probe", return_value=expected_result
        ) as run:
            self.assertEqual(main(), 0)

        run.assert_called_once_with(
            self.TOKEN, [], boot_started_at=timestamp,
            execution_contract_factory=build_execution_contract)

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
