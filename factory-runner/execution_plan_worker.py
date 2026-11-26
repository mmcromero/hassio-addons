#!/usr/bin/env python3
"""Trusted, read-only FR-EXEC-001 planner child.

This process reads only a pre-approved profile and managed local Git workspace.
It never executes project scripts, tests, exporters, shell payloads, or network
operations. The parent coordinator supplies one validated contract on stdin.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import sys

APP_DIR = Path("/app")
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

MAX_INPUT = 32 * 1024
PROJECT_RE = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")


def _emit_error(code: str, status: int = 2) -> int:
    safe = code if re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code or "") else "execution_worker_failed"
    sys.stdout.write(json.dumps({"ok": False, "error": safe}, separators=(",", ":")) + "\n")
    sys.stdout.flush()
    return status


def main() -> int:
    try:
        import executor_hardening as hardening
        audit = hardening.audit_and_close_unapproved_fds([0, 1, 2])
        if audit.get("status") == "failed" and (audit.get("unexpected_remaining") or 0) > 0:
            return _emit_error("unapproved_fds_detected")
        hardening.configure_oom_score_adj(500)
    except Exception:
        pass

    if len(sys.argv) != 3 or sys.argv[1] != "--project":
        return _emit_error("invalid_worker_arguments")
    project = sys.argv[2]
    if not PROJECT_RE.fullmatch(project):
        return _emit_error("invalid_project")

    raw = sys.stdin.buffer.read(MAX_INPUT + 1)
    if len(raw) > MAX_INPUT:
        return _emit_error("job_request_too_large")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError):
        return _emit_error("invalid_job_request")
    if not isinstance(payload, dict) or set(payload) != {"contract"}:
        return _emit_error("invalid_job_request")
    contract = payload["contract"]
    if not isinstance(contract, dict) or contract.get("project") != project:
        return _emit_error("invalid_job_request")

    projects_dir = Path(os.environ.get("RUNNER_PROJECTS_DIR", "/app/projects"))
    workspaces_dir = Path(os.environ.get(
        "RUNNER_WORKSPACES_DIR", "/data/factory-runner/workspaces"))
    executions_dir = Path(os.environ.get(
        "RUNNER_EXECUTIONS_DIR", "/data/factory-runner/executions"))
    profile_path = projects_dir / (project + ".json")
    workspace = workspaces_dir / project
    source = workspace / "source"
    distribution = workspace / "distribution"

    try:
        if (projects_dir.is_symlink() or profile_path.is_symlink()
                or not profile_path.is_file() or workspace.is_symlink()
                or not workspace.is_dir() or source.is_symlink()
                or distribution.is_symlink() or not source.is_dir()
                or not distribution.is_dir()
                or source.resolve() != source.absolute()
                or distribution.resolve() != distribution.absolute()):
            return _emit_error("workspace_unavailable")
        from rc_fastlane import load_profile
        from workspace_sync import _existing
        from execution_contract import digest
        from execution_planner import PlannerError, plan_execution

        profile = load_profile(profile_path)
        if profile.get("id") != project:
            return _emit_error("profile_mismatch")
        marker = _existing(workspace, profile)
        if marker is None:
            return _emit_error("workspace_unavailable")
        plan, _idempotent = plan_execution(
            contract, profile, source, marker, executions_dir=executions_dir)
        tests = plan.get("tests", {})
        operations = plan.get("operations", {})
        receipt = plan.get("receipt", {})
        if (plan.get("execution_id") != contract.get("execution_id")
                or tests.get("execution_performed") is not False
                or operations.get("authorization_verified") is not False
                or not isinstance(receipt, dict)
                or not isinstance(receipt.get("digest"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", receipt["digest"])):
            return _emit_error("execution_plan_integrity_failed")
        result = {
            "ok": True,
            "execution_id": plan["execution_id"],
            "contract_digest": plan["contract_digest"],
            "plan_status": plan["status"],
            "plan_digest": digest(plan),
            "receipt_digest": receipt["digest"],
            "selected_count": tests.get("selected_count"),
            "reused_count": tests.get("reused_count"),
            "omitted_count": tests.get("omitted_count"),
        }
        sys.stdout.write(json.dumps(result, separators=(",", ":")) + "\n")
        sys.stdout.flush()
        return 0
    except Exception:
        return _emit_error("execution_worker_failed")


if __name__ == "__main__":
    raise SystemExit(main())
