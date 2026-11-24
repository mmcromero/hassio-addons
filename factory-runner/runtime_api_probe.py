"""Authenticated, read-only smoke probe against the live loopback API.

Runs inside the add-on container. It never prints the Bearer token and never
calls preparation, proposal, publication, reconciliation, or project scripts.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

# Python -I omits the script directory from sys.path; only this trusted path is added.
if "/app" not in sys.path:
    sys.path.insert(0, "/app")

BASE_URL = "http://127.0.0.1:9876"
MAX_RESPONSE = 262144
OPERATION_ID = re.compile(r"^[0-9a-f-]{36}$")
SOURCE_SHA = re.compile(r"^[0-9a-f]{40}$")


class ProbeError(Exception):
    pass


def request_json(method, path, token, payload=None, *, timeout=3):
    headers = {"Accept": "application/json"}
    body = None
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(
        BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            status = response.status
            raw = response.read(MAX_RESPONSE + 1)
    except urllib.error.HTTPError as exc:
        status = exc.code
        raw = exc.read(MAX_RESPONSE + 1)
    except (OSError, urllib.error.URLError, TimeoutError):
        raise ProbeError("api_unreachable") from None
    if len(raw) > MAX_RESPONSE:
        raise ProbeError("api_response_too_large")
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        raise ProbeError("api_invalid_json") from None
    if not isinstance(data, (dict, list)):
        raise ProbeError("api_invalid_response")
    return status, data


def _expect(condition, code):
    if not condition:
        raise ProbeError(code)


def _post_readonly(requester, path, token, payload):
    for _ in range(20):
        status, data = requester("POST", path, token, payload)
        if status == 409 and data.get("error") == "busy":
            time.sleep(0.5)
            continue
        if status == 503 and data.get("error") == "workspace_or_export_unavailable":
            raise ProbeError("workspace_sync_in_progress")
        return status, data
    raise ProbeError("api_busy")


def run_probe(token, snapshots, requester=request_json, boot_started_at=None):
    """Exercise only authenticated reads and read-only preflight endpoints."""
    _expect(isinstance(token, str) and len(token) >= 32, "auth_token_unavailable")

    status, _ = requester("GET", "/api/status", "")
    _expect(status == 401, "unauthenticated_request_not_rejected")

    status, data = requester("GET", "/api/status", token)
    _expect(status == 200, "authenticated_status_failed")
    _expect(data.get("status") == "read_only_preflight"
            and data.get("publication") == "disabled"
            and data.get("autonomous_changes") == "disabled"
            and data.get("controlled_worker") == "read_only_only",
            "runtime_status_contract_mismatch")

    status, data = requester("GET", "/api/projects", token)
    _expect(status == 200 and isinstance(data.get("projects"), list),
            "projects_endpoint_failed")
    project_ids = {
        item.get("id") for item in data["projects"]
        if isinstance(item, dict) and item.get("publication") == "disabled"
    }
    _expect(len(project_ids) == len(data["projects"]),
            "project_publication_not_disabled")

    status, publication = requester("GET", "/api/publication-status", token)
    _expect(status == 200 and isinstance(publication, (dict, list)),
            "publication_status_unavailable")
    if isinstance(publication, dict):
        _expect(publication.get("published") is not True,
                "publication_status_unsafe")

    status, prior_audit = requester("GET", "/api/operations", token)
    _expect(status == 200 and prior_audit.get("source") == "sanitized_audit"
            and isinstance(prior_audit.get("operations"), list),
            "prior_audit_endpoint_failed")
    prior_boot_audit_events = 0
    if isinstance(boot_started_at, str) and boot_started_at:
        prior_boot_audit_events = sum(
            1 for event in prior_audit["operations"]
            if isinstance(event, dict) and isinstance(event.get("time"), str)
            and event["time"] < boot_started_at
        )

    operation_ids = []
    results = []
    for project, source_sha in snapshots:
        _expect(project in project_ids, "workspace_project_not_approved")
        _expect(isinstance(source_sha, str) and SOURCE_SHA.fullmatch(source_sha),
                "workspace_source_sha_invalid")
        payload = {"project": project, "expected_source_sha": source_sha}

        status, response = _post_readonly(requester, "/api/preflight", token, payload)
        _expect(status == 200 and isinstance(response.get("result"), dict),
                "live_preflight_failed")
        preflight = response["result"]
        _expect(type(preflight.get("eligible_for_preparation")) is bool,
                "preflight_eligibility_unverified")
        errors = preflight.get("errors")
        _expect(isinstance(errors, list)
                and all(isinstance(item, str)
                        and re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", item)
                        for item in errors),
                "preflight_policy_evidence_invalid")
        operation_id = response.get("operation_id")
        _expect(isinstance(operation_id, str)
                and OPERATION_ID.fullmatch(operation_id),
                "preflight_operation_id_invalid")
        operation_ids.append(operation_id)

        status, response = _post_readonly(requester, "/api/release-plan", token, payload)
        _expect(status == 200 and isinstance(response.get("result"), dict),
                "live_release_plan_failed")
        plan = response["result"]
        _expect(plan.get("published") is False
                and plan.get("publication") == "disabled_pending_independent_authorization",
                "release_plan_publication_not_disabled")
        operation_id = response.get("operation_id")
        _expect(isinstance(operation_id, str)
                and OPERATION_ID.fullmatch(operation_id),
                "release_plan_operation_id_invalid")
        operation_ids.append(operation_id)
        results.append((project, preflight["eligible_for_preparation"], len(errors),
                        plan.get("preparation")))

    status, audit = requester("GET", "/api/operations", token)
    _expect(status == 200 and audit.get("source") == "sanitized_audit"
            and isinstance(audit.get("operations"), list),
            "sanitized_audit_endpoint_failed")
    events = {item.get("operation_id"): item for item in audit["operations"]
              if isinstance(item, dict)}
    for operation_id in operation_ids:
        event = events.get(operation_id)
        _expect(event is not None and event.get("status") == "completed_read_only",
                "read_only_operation_not_audited")
    serialized = json.dumps(audit, sort_keys=True)
    _expect(token not in serialized and "source_sha" not in serialized,
            "audit_exposed_sensitive_data")
    return {
        "projects": len(project_ids),
        "preflight_checks": len(snapshots),
        "audited_read_only_operations": len(operation_ids),
        "publication": "disabled",
        "prior_boot_audit_events": prior_boot_audit_events,
        "results": results,
    }


def workspace_snapshots():
    # Trusted in-image profiles and managed-workspace markers only.
    import server
    from workspace_sync import _existing

    snapshots = []
    for project in sorted(server.listed_projects()):
        profile_path = server.PROJECTS_DIR / (project + ".json")
        profile = server.load_profile(profile_path)
        if profile.get("mode") == "sync_only":
            continue
        marker = _existing(server.WORKSPACES_DIR / project, profile)
        if marker is not None:
            snapshots.append((project, marker.get("source_sha")))
    return snapshots


def main():
    token = os.environ.get("RUNNER_AUTH_TOKEN", "")
    if len(token) < 32:
        print("[API-PROBE] BLOCKED: auth_token_unavailable", flush=True)
        return 1
    print("[API-PROBE] START: authenticated loopback; read/preflight only", flush=True)

    # The server starts independently. Do not make its startup depend on this probe.
    ready = False
    for _ in range(30):
        try:
            status, _ = request_json("GET", "/api/status", token)
            if status == 200:
                ready = True
                break
            if status == 401:
                print("[API-PROBE] BLOCKED: live_api_authentication_failed", flush=True)
                return 1
        except ProbeError:
            time.sleep(0.25)
    if not ready:
        print("[API-PROBE] BLOCKED: live_api_not_ready", flush=True)
        return 1

    expect_workspaces = os.environ.get("RUNNER_API_PROBE_EXPECT_WORKSPACES") == "true"
    deadline = time.monotonic() + (90 if expect_workspaces else 10)
    result = None
    last_error = "workspace_sync_in_progress"
    while time.monotonic() < deadline:
        snapshots = []
        if expect_workspaces:
            try:
                import server
                expected = []
                for project in sorted(server.listed_projects()):
                    profile = server.load_profile(server.PROJECTS_DIR / (project + ".json"))
                    if profile.get("mode") != "sync_only":
                        expected.append(project)
                snapshots = workspace_snapshots()
                if not snapshots or len(snapshots) != len(expected):
                    time.sleep(2)
                    continue
            except Exception:
                time.sleep(2)
                continue
        try:
            boot_started_at = os.environ.get("RUNNER_API_PROBE_BOOT_STARTED_AT", "")
            result = run_probe(
                token, snapshots, boot_started_at=boot_started_at or None)
            break
        except ProbeError as exc:
            last_error = str(exc)
            if last_error not in ("workspace_sync_in_progress", "api_busy"):
                print("[API-PROBE] BLOCKED: " + last_error, flush=True)
                return 1
            time.sleep(2)
    if result is None:
        print("[API-PROBE] BLOCKED: " + last_error, flush=True)
        return 1
    print("[API-PROBE] PASS: authenticated live loopback API; projects="
          + str(result["projects"]) + " preflight_checks="
          + str(result["preflight_checks"]) + " audited_read_only_operations="
          + str(result["audited_read_only_operations"])
          + " prior_boot_audit_events="
          + str(result["prior_boot_audit_events"])
          + " publication=disabled", flush=True)
    for project, eligible, errors, preparation in result["results"]:
        print("[API-PROBE] PROJECT: " + project
              + " eligible=" + str(eligible).lower()
              + " policy_errors=" + str(errors)
              + " preparation=" + str(preparation), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
