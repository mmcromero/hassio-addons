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
import subprocess
import uuid
from datetime import datetime, timezone
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


def _post_readonly(requester, path, token, payload, timeout=3):
    for _ in range(20):
        status, data = requester("POST", path, token, payload, timeout=timeout)
        if status == 409 and data.get("error") == "busy":
            time.sleep(0.5)
            continue
        if status == 503 and data.get("error") == "workspace_or_export_unavailable":
            raise ProbeError("workspace_sync_in_progress")
        return status, data
    raise ProbeError("api_busy")


def run_probe(token, snapshots, requester=request_json, boot_started_at=None,
              execution_contract_factory=None):
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

        execution_summary = None
        if execution_contract_factory is not None:
            contract = execution_contract_factory(project, source_sha)
            status, response = _post_readonly(
                requester, "/api/execution-plan", token, contract, timeout=20)
            _expect(status == 200 and isinstance(response.get("plan"), dict),
                    "live_execution_plan_failed")
            execution_plan = response["plan"]
            _expect(execution_plan.get("format") == "factory-execution-plan-v1"
                    and execution_plan.get("project") == project
                    and execution_plan.get("source", {}).get("sha") == source_sha
                    and execution_plan.get("tests", {}).get("execution_performed") is False
                    and execution_plan.get("operations", {}).get("authorization_verified") is False
                    and execution_plan.get("status") in ("PLANNED", "PARTIAL"),
                    "execution_plan_contract_mismatch")
            operation_id = response.get("operation_id")
            _expect(isinstance(operation_id, str)
                    and OPERATION_ID.fullmatch(operation_id),
                    "execution_plan_operation_id_invalid")
            operation_ids.append(operation_id)
            status, stored = requester(
                "GET", "/api/executions/" + contract["execution_id"], token)
            _expect(status == 200 and isinstance(stored.get("plan"), dict)
                    and stored["plan"].get("receipt", {}).get("digest")
                    == execution_plan.get("receipt", {}).get("digest"),
                    "execution_plan_persistence_failed")
            execution_summary = {
                "status": execution_plan["status"],
                "selected": execution_plan["tests"]["selected_count"],
                "reused": execution_plan["tests"]["reused_count"],
                "omitted": execution_plan["tests"]["omitted_count"],
            }
        results.append((project, preflight["eligible_for_preparation"], len(errors),
                        plan.get("preparation"), execution_summary))

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


def build_execution_contract(project, source_sha):
    """Build a deterministic, plan-only smoke contract from trusted profile/workspace."""
    import server

    profile, source, _distribution = server.project_workspace(project)
    if profile.get("source_sha") not in (None, source_sha):
        raise ProbeError("workspace_source_binding_mismatch")
    env = {
        "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
    }
    def git_value(*args):
        try:
            result = subprocess.run(
                ["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), *args],
                capture_output=True, stdin=subprocess.DEVNULL, env=env,
                timeout=5, check=False,
            )
        except (OSError, subprocess.TimeoutExpired):
            raise ProbeError("execution_plan_git_metadata_unavailable") from None
        if result.returncode != 0:
            raise ProbeError("execution_plan_git_metadata_unavailable")
        return result.stdout.decode("ascii", "strict").strip()

    parents = git_value("rev-list", "--parents", "-n", "1", source_sha).split()
    if not parents or parents[0] != source_sha:
        raise ProbeError("execution_plan_source_binding_invalid")
    base_sha = parents[1] if len(parents) > 1 else None
    created_at = git_value("show", "-s", "--format=%cI", source_sha)
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except ValueError:
        raise ProbeError("execution_plan_commit_time_invalid") from None
    execution_id = str(uuid.uuid5(
        uuid.NAMESPACE_URL, "factory-runner-runtime-plan:" + project + ":" + source_sha))
    return {
        "schema_version": "FR-EXEC-001/v1",
        "execution_id": execution_id,
        "created_at": created_at,
        "objective": "Smoke probe autenticado do planejador; nenhuma execução de testes",
        "project": project,
        "source": {
            "repository": profile["source_repo"], "ref": profile["source_ref"],
            "sha": source_sha, "base_sha": base_sha,
        },
        "scope": {
            "include_paths": [], "exclude_paths": [],
            "constraints": ["Planejamento somente leitura; não executar código de projeto"],
        },
        "requested_operations": ["analyze", "plan", "test"],
        "authorization": {
            "reference": "runtime-api-probe",
            "declared_operations": ["analyze", "plan", "test"],
        },
        "destinations": [],
        "acceptance_criteria": ["Plano vinculado ao SHA sem executar testes"],
        "limits": {
            "timeout_seconds": 120, "max_changed_files": 1000,
            "network_policy": "read_only", "data_access": "approved_workspace",
            "max_cost_usd": None,
        },
    }


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
                token, snapshots, boot_started_at=boot_started_at or None,
                execution_contract_factory=build_execution_contract)
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
    for project, eligible, errors, preparation, execution_summary in result["results"]:
        print("[API-PROBE] PROJECT: " + project
              + " eligible=" + str(eligible).lower()
              + " policy_errors=" + str(errors)
              + " preparation=" + str(preparation)
              + " execution_plan=" + str(execution_summary), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
