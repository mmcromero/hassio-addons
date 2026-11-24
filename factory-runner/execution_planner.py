"""Read-only FR-EXEC-001 impact analysis, proportional test selection and receipt.

This planner reads only the approved, no-checkout Git workspace and trusted
on-image test catalogs. It does not execute tests, scripts, exporters or project
code. Project tests remain gated until the sandbox stage is approved.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import time
import uuid
from datetime import datetime, timezone

import execution_contract as contracts
import execution_evidence as evidence

PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_GIT_OUTPUT = 8 * 1024 * 1024
MAX_CHANGED_PATHS = 1000
DEFAULT_CATALOG_DIR = Path(os.environ.get("RUNNER_TEST_CATALOG_DIR", "/app/test_catalogs"))
DEFAULT_EXECUTIONS_DIR = Path(os.environ.get("RUNNER_EXECUTIONS_DIR", "/data/factory-runner/executions"))


class PlannerError(ValueError):
    pass


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _digest(value):
    return hashlib.sha256(_canonical(value)).hexdigest()


def _run_git(source, *args, timeout=20):
    source = Path(source).absolute()
    if (source.resolve() != source or source.is_symlink()
            or not source.is_dir() or (source / ".git").is_symlink()
            or not (source / ".git").exists()):
        raise PlannerError("unsafe_source_workspace")
    env = {
        "PATH": "/usr/bin:/bin",
        "HOME": "/nonexistent",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
        "GIT_OPTIONAL_LOCKS": "0",
        "GIT_NO_REPLACE_OBJECTS": "1",
        "GIT_LFS_SKIP_SMUDGE": "1",
    }
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(source), *args],
            capture_output=True, stdin=subprocess.DEVNULL, env=env,
            timeout=timeout, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        raise PlannerError("git_analysis_unavailable") from None
    if result.returncode != 0 or len(result.stdout) > MAX_GIT_OUTPUT:
        raise PlannerError("git_analysis_unavailable")
    return result.stdout


def _commit_exists(source, sha, timeout=20):
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        return False
    output = _run_git(source, "rev-parse", "--verify", sha + "^{commit}", timeout=timeout)
    return output.decode("ascii", "strict").strip() == sha


def _diff_paths(source, base_sha, target_sha, timeout=20):
    if not _commit_exists(source, base_sha, timeout) or not _commit_exists(source, target_sha, timeout):
        raise PlannerError("source_commit_unavailable")
    ancestor = subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null", "-C", str(Path(source).absolute()),
         "merge-base", "--is-ancestor", base_sha, target_sha],
        capture_output=True, stdin=subprocess.DEVNULL,
        env={
            "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
            "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1",
        },
        timeout=timeout, check=False,
    )
    if ancestor.returncode != 0:
        raise PlannerError("base_not_ancestor")
    raw = _run_git(source, "diff", "--no-ext-diff", "--no-renames",
                   "--name-only", "-z", base_sha, target_sha, "--", timeout=timeout)
    paths = []
    for item in raw.split(b"\0"):
        if not item:
            continue
        try:
            path = item.decode("utf-8", "strict")
        except UnicodeError:
            raise PlannerError("invalid_git_path") from None
        if (path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..", ".git") for part in path.split("/"))
                or any(ord(ch) < 32 or ord(ch) == 127 for ch in path)):
            raise PlannerError("unsafe_git_path")
        paths.append(path)
        if len(paths) > MAX_CHANGED_PATHS:
            raise PlannerError("changed_path_budget_exceeded")
    return sorted(set(paths))


def _git_tree(source, target_sha, timeout=20):
    raw = _run_git(source, "ls-tree", "-r", "-z", "--full-tree", target_sha, timeout=timeout)
    result = {}
    for record in raw.split(b"\0"):
        if not record:
            continue
        try:
            meta, path_bytes = record.split(b"\t", 1)
            mode, kind, blob = meta.decode("ascii").split(" ")
            path = path_bytes.decode("utf-8", "strict")
        except (ValueError, UnicodeError):
            raise PlannerError("invalid_git_tree") from None
        if kind != "blob":
            continue
        if (path.startswith("/") or "\\" in path
                or any(part in ("", ".", "..", ".git") for part in path.split("/"))
                or not re.fullmatch(r"[0-9a-f]{40}", blob)):
            raise PlannerError("unsafe_git_tree_path")
        result[path] = blob
    return result


def _safe_pattern(value):
    return (isinstance(value, str) and 1 <= len(value) <= 240
            and not value.startswith("/") and "\\" not in value
            and all(part not in ("", ".", "..", ".git") for part in value.split("/")))


def load_catalog(project, catalog_dir=DEFAULT_CATALOG_DIR):
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise PlannerError("invalid_project")
    root = Path(catalog_dir).absolute()
    path = root / (project + ".json")
    if (root.resolve() != root or root.is_symlink() or path.is_symlink()
            or not path.is_file() or path.resolve() != path.absolute()
            or path.stat().st_nlink != 1 or path.stat().st_size > 1024 * 1024):
        raise PlannerError("test_catalog_unavailable")
    try:
        catalog = json.loads(path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise PlannerError("test_catalog_invalid") from None
    if (not isinstance(catalog, dict)
            or set(catalog) != {"schema_version", "project_id", "catalog_version",
                                "environment_id", "modules", "tests"}
            or catalog.get("schema_version") != 1
            or catalog.get("project_id") != project
            or not isinstance(catalog.get("catalog_version"), str)
            or not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", catalog["catalog_version"])
            or not isinstance(catalog.get("environment_id"), str)
            or not re.fullmatch(r"[a-z][a-z0-9_-]{1,79}", catalog["environment_id"])
            or not isinstance(catalog.get("modules"), list)
            or not isinstance(catalog.get("tests"), list)
            or not catalog["tests"] or len(catalog["tests"]) > 300):
        raise PlannerError("test_catalog_invalid")
    module_ids = set()
    for module in catalog["modules"]:
        if (not isinstance(module, dict)
                or set(module) != {"id", "path_patterns", "depends_on", "risk_tags"}
                or not isinstance(module.get("id"), str)
                or not re.fullmatch(r"[a-z][a-z0-9_-]{1,63}", module["id"])
                or module["id"] in module_ids
                or not isinstance(module.get("path_patterns"), list)
                or not module["path_patterns"]
                or any(not _safe_pattern(x) for x in module["path_patterns"])
                or not isinstance(module.get("depends_on"), list)
                or any(not isinstance(x, str) for x in module["depends_on"])
                or not isinstance(module.get("risk_tags"), list)
                or any(not isinstance(x, str) for x in module["risk_tags"])):
            raise PlannerError("test_catalog_invalid")
        module_ids.add(module["id"])
    for module in catalog["modules"]:
        if any(item not in module_ids for item in module["depends_on"]):
            raise PlannerError("test_catalog_dependency_invalid")
    test_ids = set()
    for test in catalog["tests"]:
        required = {"id", "version", "path", "modules", "kind", "risk",
                    "requires_sandbox", "artifact_required", "operation_types"}
        if (not isinstance(test, dict) or set(test) != required
                or not isinstance(test.get("id"), str)
                or not re.fullmatch(r"[a-z][a-z0-9_.:-]{1,127}", test["id"])
                or test["id"] in test_ids
                or not isinstance(test.get("version"), str)
                or not re.fullmatch(r"[A-Za-z0-9._-]{1,40}", test["version"])
                or not _safe_pattern(test.get("path"))
                or not isinstance(test.get("modules"), list)
                or not test["modules"]
                or any(x not in module_ids for x in test["modules"])
                or test.get("kind") not in ("unit", "contract", "integration", "browser", "security", "build", "policy")
                or test.get("risk") not in ("low", "normal", "high", "critical")
                or type(test.get("requires_sandbox")) is not bool
                or type(test.get("artifact_required")) is not bool
                or not isinstance(test.get("operation_types"), list)
                or any(x not in contracts.OPERATIONS for x in test["operation_types"])):
            raise PlannerError("test_catalog_invalid")
        test_ids.add(test["id"])
    return catalog, hashlib.sha256(_canonical(catalog)).hexdigest()


def _matches(path, patterns):
    return any(fnmatch.fnmatchcase(path, pattern) for pattern in patterns)


def _module_closure(catalog, changed_paths):
    modules = {item["id"]: item for item in catalog["modules"]}
    affected = {
        module_id for module_id, module in modules.items()
        if any(_matches(path, module["path_patterns"]) for path in changed_paths)
    }
    reverse = {key: set() for key in modules}
    for module_id, module in modules.items():
        for dependency in module["depends_on"]:
            reverse[dependency].add(module_id)
    pending = list(affected)
    while pending:
        current = pending.pop()
        for dependent in reverse[current] - affected:
            affected.add(dependent)
            pending.append(dependent)
    return sorted(affected)


def _module_files(catalog, module_ids, tree):
    modules = {item["id"]: item for item in catalog["modules"]}
    found = {}
    for module_id in module_ids:
        module = modules[module_id]
        for path, blob in tree.items():
            if _matches(path, module["path_patterns"]):
                found[path] = blob
    return found


def _test_binding(test, catalog, tree):
    module_ids = set(test["modules"])
    modules = {item["id"]: item for item in catalog["modules"]}
    pending = list(module_ids)
    while pending:
        current = pending.pop()
        for dependency in modules[current]["depends_on"]:
            if dependency not in module_ids:
                module_ids.add(dependency)
                pending.append(dependency)
    files = _module_files(catalog, module_ids, tree)
    test_blob = tree.get(test["path"])
    if test_blob:
        files[test["path"]] = test_blob
    if not files:
        return None, None
    unit_digest = hashlib.sha256(_canonical(sorted(files.items()))).hexdigest()
    dependency_digest = hashlib.sha256(_canonical({
        "catalog_version": catalog["catalog_version"],
        "modules": sorted(module_ids),
        "files": sorted(files.items()),
    })).hexdigest()
    return unit_digest, dependency_digest


def _scope_outside(paths, scope):
    include = scope["include_paths"]
    exclude = scope["exclude_paths"]
    outside = []
    for path in paths:
        if include and not _matches(path, include):
            outside.append(path)
        elif exclude and _matches(path, exclude):
            outside.append(path)
    return outside


def build_plan(contract, contract_digest, profile, source, marker,
               *, executions_dir=DEFAULT_EXECUTIONS_DIR,
               catalog_dir=DEFAULT_CATALOG_DIR,
               now=None):
    """Build a deterministic plan. The caller validates/persists the contract."""
    project = contract["project"]
    source_sha = contract["source"]["sha"]
    base_sha = contract["source"]["base_sha"]
    if (marker.get("source_sha") != source_sha
            or marker.get("source_repo") != profile.get("source_repo")):
        raise PlannerError("workspace_source_binding_mismatch")
    catalog, catalog_sha = load_catalog(project, catalog_dir)
    timeout = min(20, contract["limits"]["timeout_seconds"])
    if base_sha is None:
        changed_paths = []
        impact_unknown = True
    else:
        changed_paths = _diff_paths(source, base_sha, source_sha, timeout=timeout)
        impact_unknown = False
    if len(changed_paths) > contract["limits"]["max_changed_files"]:
        raise PlannerError("changed_file_limit_exceeded")
    outside = _scope_outside(changed_paths, contract["scope"])
    tree = _git_tree(source, source_sha, timeout=timeout)
    if any(test["path"] not in tree for test in catalog["tests"]):
        raise PlannerError("test_catalog_stale_for_source_sha")
    if base_sha is None:
        affected_modules = sorted(item["id"] for item in catalog["modules"])
        unknown_paths = []
    else:
        affected_modules = _module_closure(catalog, changed_paths)
        mapped = set()
        for module in catalog["modules"]:
            if module["id"] in affected_modules:
                for path in changed_paths:
                    if _matches(path, module["path_patterns"]):
                        mapped.add(path)
        unknown_paths = sorted(set(changed_paths) - mapped)
        if unknown_paths:
            impact_unknown = True
            affected_modules = sorted(item["id"] for item in catalog["modules"])

    requested = set(contract["requested_operations"])
    force_all = impact_unknown or bool(outside)
    selected, reused, omitted = [], [], []
    evidence_path = Path(executions_dir) / "evidence.jsonl"
    for test in catalog["tests"]:
        path_changed = test["path"] in changed_paths
        module_hit = bool(set(test["modules"]) & set(affected_modules))
        operation_hit = bool(requested & set(test["operation_types"]))
        if force_all or path_changed or module_hit or operation_hit:
            unit_digest, dependency_digest = _test_binding(test, catalog, tree)
            artifact_digest = None
            found = None
            if (unit_digest and dependency_digest
                    and not (test["artifact_required"] and artifact_digest is None)):
                found = evidence.reusable_evidence(
                    evidence_path, test_id=test["id"], test_version=test["version"],
                    unit_digest=unit_digest, dependency_digest=dependency_digest,
                    environment_id=catalog["environment_id"],
                    artifact_digest=artifact_digest)
            entry = {
                "test_id": test["id"], "test_version": test["version"],
                "path": test["path"], "modules": test["modules"],
                "kind": test["kind"], "risk": test["risk"],
                "unit_digest": unit_digest, "dependency_digest": dependency_digest,
                "environment_id": catalog["environment_id"],
                "requires_sandbox": test["requires_sandbox"],
                "artifact_required": test["artifact_required"],
            }
            if found:
                reused.append({**entry, "evidence_id": found["evidence_id"],
                               "result": "PASS", "reason": "exact_binding_match"})
            else:
                reason = ("no_base_sha_full_regression" if base_sha is None
                          else "unknown_impact_full_regression" if impact_unknown
                          else "affected_test_or_dependency")
                selected.append({**entry, "result": "NOT_EXECUTED",
                                 "reason": reason,
                                 "execution_gate": ("sandbox_stage_5_required"
                                                    if test["requires_sandbox"]
                                                    else "trusted_executor_not_yet_integrated")})
        else:
            omitted.append({"test_id": test["id"], "path": test["path"],
                            "reason": "no_affected_module_or_requested_operation"})

    blocked_operations = []
    for operation in contract["requested_operations"]:
        if operation in ("analyze", "plan"):
            continue
        if operation == "test":
            if selected:
                reason = "project_test_execution_requires_sandbox_stage_5"
            elif reused:
                reason = "all_applicable_tests_reused_from_exact_evidence"
            else:
                reason = "no_test_execution_requested_by_plan"
            if selected:
                blocked_operations.append({"operation": operation, "reason": reason})
        elif operation in contracts.PRIVILEGED:
            blocked_operations.append({"operation": operation,
                                       "reason": "independent_owner_grant_required_publisher_disabled"})
        elif operation == "homologate":
            blocked_operations.append({"operation": operation,
                                       "reason": "requires_installed_artifact_and_approved_environment"})
        elif operation in ("develop", "prepare", "package"):
            blocked_operations.append({"operation": operation,
                                       "reason": "execution_not_part_of_read_only_planner"})
    if outside:
        status = "BLOCKED_SCOPE"
    elif blocked_operations:
        status = "PARTIAL"
    else:
        status = "PLANNED"

    timestamp = now or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    receipt_body = {
        "format": "factory-execution-receipt-v1",
        "schema_version": contracts.SCHEMA_VERSION,
        "execution_id": contract["execution_id"],
        "contract_digest": contract_digest,
        "project": project,
        "source_sha": source_sha,
        "base_sha": base_sha,
        "catalog_version": catalog["catalog_version"],
        "catalog_sha256": catalog_sha,
        "changed_paths": changed_paths,
        "affected_modules": affected_modules,
        "unknown_impact_paths": unknown_paths,
        "scope_outside_paths": outside,
        "selected_tests": [{key: item[key] for key in ("test_id", "test_version", "path", "reason", "unit_digest", "dependency_digest", "environment_id")} for item in selected],
        "reused_evidence": [{key: item[key] for key in ("test_id", "test_version", "evidence_id", "unit_digest", "dependency_digest", "environment_id")}
                            for item in reused],
        "omitted_tests": [{"test_id": item["test_id"], "reason": item["reason"]}
                          for item in omitted],
        "blocked_operations": blocked_operations,
        "authorization_declaration": contract["authorization"],
        "authorization_verified": False,
        "created_at": timestamp,
    }
    receipt_digest = _digest(receipt_body)
    receipt = {**receipt_body, "digest": receipt_digest}
    return {
        "format": "factory-execution-plan-v1",
        "execution_id": contract["execution_id"],
        "contract_digest": contract_digest,
        "project": project,
        "objective": contract["objective"],
        "source": contract["source"],
        "status": status,
        "impact": {
            "changed_paths": changed_paths,
            "affected_modules": affected_modules,
            "unknown_paths": unknown_paths,
            "impact_unknown": impact_unknown,
            "scope_outside_paths": outside,
        },
        "tests": {
            "selected": selected,
            "reused": reused,
            "omitted": omitted,
            "selected_count": len(selected),
            "reused_count": len(reused),
            "omitted_count": len(omitted),
            "execution_performed": False,
        },
        "operations": {
            "requested": contract["requested_operations"],
            "blocked": blocked_operations,
            "authorization_reference": contract["authorization"]["reference"],
            "authorization_declared_operations": contract["authorization"]["declared_operations"],
            "authorization_verified": False,
        },
        "catalog": {"version": catalog["catalog_version"], "sha256": catalog_sha},
        "receipt": receipt,
    }


def plan_execution(contract, profile, source, marker, *, executions_dir=DEFAULT_EXECUTIONS_DIR,
                   catalog_dir=DEFAULT_CATALOG_DIR):
    validated = contracts.validate_contract(contract, profile)
    normalized = validated["contract"]
    existing = contracts.load_existing(
        executions_dir, normalized["execution_id"], validated["contract_digest"])
    if existing is not None:
        return existing, True
    plan = build_plan(normalized, validated["contract_digest"], profile, source, marker,
                      executions_dir=executions_dir, catalog_dir=catalog_dir)
    saved, idempotent = contracts.save_execution(
        executions_dir, normalized, validated["contract_digest"], plan)
    return saved, idempotent


def get_execution(executions_dir, execution_id):
    try:
        normalized = str(uuid.UUID(execution_id))
    except (ValueError, TypeError, AttributeError):
        raise PlannerError("invalid_execution_id") from None
    if normalized != execution_id:
        raise PlannerError("invalid_execution_id")
    root = Path(executions_dir).absolute()
    if (root.resolve() != root or root.is_symlink() or not root.is_dir()
            or root.stat().st_uid != os.geteuid() or root.stat().st_mode & 0o077):
        raise PlannerError("execution_store_unavailable")
    directory = root / normalized
    plan_path = directory / "plan.json"
    if (directory.is_symlink() or not directory.is_dir()
            or directory.stat().st_uid != os.geteuid() or directory.stat().st_mode & 0o077
            or plan_path.is_symlink() or not plan_path.is_file()
            or plan_path.stat().st_nlink != 1 or plan_path.stat().st_mode & 0o077):
        raise PlannerError("execution_plan_unavailable")
    try:
        plan = json.loads(plan_path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise PlannerError("execution_plan_invalid") from None
    receipt = plan.get("receipt")
    if (plan.get("execution_id") != normalized
            or not isinstance(plan.get("contract_digest"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", plan["contract_digest"])
            or not isinstance(receipt, dict)
            or receipt.get("contract_digest") != plan.get("contract_digest")
            or receipt.get("digest") != _digest(
                {key: value for key, value in receipt.items() if key != "digest"})):
        raise PlannerError("execution_receipt_integrity_failed")
    return plan
