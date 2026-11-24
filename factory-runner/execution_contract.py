"""FR-EXEC-001 v1 contract validation and immutable execution records.

This module validates declarative requests only. It never executes project code,
commands, tests, exporters, or publication operations.
"""
from __future__ import annotations

from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

SCHEMA_VERSION = "FR-EXEC-001/v1"
MAX_CONTRACT_BYTES = 16 * 1024
PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REPOSITORY = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
REF = re.compile(r"^refs/remotes/origin/[A-Za-z0-9._/-]+$")
OPERATIONS = frozenset({
    "analyze", "plan", "develop", "test", "prepare", "package",
    "publish", "deploy", "update", "homologate", "promote",
})
PRIVILEGED = frozenset({"publish", "deploy", "update", "promote"})
AUTH_REQUIRED = PRIVILEGED | frozenset({"prepare", "package", "homologate"})
DISTRIBUTION = frozenset({"package", "publish", "deploy", "update", "homologate", "promote"})


class ContractError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def _text(value, *, minimum=1, maximum=512):
    return (isinstance(value, str) and minimum <= len(value) <= maximum
            and value == value.strip()
            and not any(ord(ch) < 32 or ord(ch) == 127 for ch in value))


def _path_pattern(value):
    if not _text(value, maximum=240) or value.startswith("/") or "\\" in value:
        return False
    parts = value.split("/")
    return all(part not in ("", ".", "..", ".git") for part in parts)


def validate_contract(value, profile):
    """Strictly validate a caller-supplied contract against a trusted profile."""
    if not isinstance(value, dict):
        raise ContractError("invalid_contract")
    required = {
        "schema_version", "execution_id", "created_at", "objective", "project",
        "source", "scope", "requested_operations", "authorization",
        "destinations", "acceptance_criteria", "limits",
    }
    if set(value) != required or value.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("contract_schema_mismatch")

    execution_id = value.get("execution_id")
    try:
        if not isinstance(execution_id, str) or str(uuid.UUID(execution_id)) != execution_id:
            raise ValueError
    except (ValueError, TypeError, AttributeError):
        raise ContractError("invalid_execution_id") from None

    created_at = value.get("created_at")
    try:
        parsed = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            raise ValueError
    except (ValueError, AttributeError, TypeError):
        raise ContractError("invalid_created_at") from None

    project = value.get("project")
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise ContractError("invalid_project")
    if profile.get("id") != project:
        raise ContractError("profile_mismatch")

    objective = value.get("objective")
    if not _text(objective, maximum=1000):
        raise ContractError("invalid_objective")

    source = value.get("source")
    if not isinstance(source, dict) or set(source) != {"repository", "ref", "sha", "base_sha"}:
        raise ContractError("invalid_source_binding")
    if (source.get("repository") != profile.get("source_repo")
            or source.get("ref") != profile.get("source_ref")
            or not isinstance(source.get("repository"), str)
            or not REPOSITORY.fullmatch(source["repository"])
            or not isinstance(source.get("ref"), str)
            or not REF.fullmatch(source["ref"])
            or not isinstance(source.get("sha"), str)
            or not SHA.fullmatch(source["sha"])):
        raise ContractError("source_not_bound_to_approved_profile")
    base_sha = source.get("base_sha")
    if base_sha is not None and (not isinstance(base_sha, str) or not SHA.fullmatch(base_sha)):
        raise ContractError("invalid_base_sha")
    if base_sha == source.get("sha"):
        raise ContractError("base_equals_target")

    scope = value.get("scope")
    if not isinstance(scope, dict) or set(scope) != {"include_paths", "exclude_paths", "constraints"}:
        raise ContractError("invalid_scope")
    for field in ("include_paths", "exclude_paths"):
        paths = scope.get(field)
        if (not isinstance(paths, list) or len(paths) > 128
                or any(not _path_pattern(path) for path in paths)
                or len(paths) != len(set(paths))):
            raise ContractError("invalid_scope_paths")
    constraints = scope.get("constraints")
    if (not isinstance(constraints, list) or len(constraints) > 32
            or any(not _text(item, maximum=300) for item in constraints)):
        raise ContractError("invalid_scope_constraints")

    operations = value.get("requested_operations")
    if (not isinstance(operations, list) or not operations or len(operations) > len(OPERATIONS)
            or any(item not in OPERATIONS for item in operations)
            or len(operations) != len(set(operations))):
        raise ContractError("invalid_requested_operations")

    authorization = value.get("authorization")
    if (not isinstance(authorization, dict)
            or set(authorization) != {"reference", "declared_operations"}):
        raise ContractError("invalid_authorization_declaration")
    reference = authorization.get("reference")
    if reference is not None and not _text(reference, maximum=256):
        raise ContractError("invalid_authorization_reference")
    declared_operations = authorization.get("declared_operations")
    if (not isinstance(declared_operations, list) or len(declared_operations) > len(OPERATIONS)
            or any(item not in OPERATIONS for item in declared_operations)
            or len(declared_operations) != len(set(declared_operations))
            or not set(declared_operations).issubset(set(operations))):
        raise ContractError("invalid_declared_authorized_operations")
    privileged = set(operations) & PRIVILEGED
    authorization_required = set(operations) & AUTH_REQUIRED
    if authorization_required and (not reference or not authorization_required.issubset(set(declared_operations))):
        raise ContractError("operation_not_declared_authorized")
    if reference and re.search(r"(?i)(bearer\s|gh[pousr]_|github_pat_|xox[baprs]-|sk-[a-z0-9]{12})", reference):
        raise ContractError("secret_like_authorization_reference")

    destinations = value.get("destinations")
    if not isinstance(destinations, list) or len(destinations) > 8:
        raise ContractError("invalid_destinations")
    for item in destinations:
        if not isinstance(item, dict) or set(item) != {"repository", "ref", "environment"}:
            raise ContractError("invalid_destination")
        if (not isinstance(item.get("repository"), str)
                or not REPOSITORY.fullmatch(item["repository"])
                or not isinstance(item.get("ref"), str)
                or not re.fullmatch(r"refs/(?:heads|remotes/origin)/[A-Za-z0-9._/-]+", item["ref"])
                or not _text(item.get("environment"), maximum=80)):
            raise ContractError("invalid_destination")
    if any(op in DISTRIBUTION for op in operations) and not destinations:
        raise ContractError("destination_required_for_distribution_operation")
    if destinations:
        approved_repo = profile.get("distribution_repo")
        allowed_refs = {profile.get("public_ref"), profile.get("rc_ref")}
        normalized_refs = {
            ref.replace("refs/remotes/origin/", "refs/heads/")
            for ref in allowed_refs if isinstance(ref, str)
        }
        if any(item["repository"] != approved_repo
               or item["ref"].replace("refs/remotes/origin/", "refs/heads/") not in normalized_refs
               for item in destinations):
            raise ContractError("destination_outside_approved_profile")

    criteria = value.get("acceptance_criteria")
    if (not isinstance(criteria, list) or not 1 <= len(criteria) <= 30
            or any(not _text(item, maximum=500) for item in criteria)):
        raise ContractError("invalid_acceptance_criteria")

    limits = value.get("limits")
    if not isinstance(limits, dict) or set(limits) != {
        "timeout_seconds", "max_changed_files", "network_policy",
        "data_access", "max_cost_usd",
    }:
        raise ContractError("invalid_limits")
    timeout = limits.get("timeout_seconds")
    changed = limits.get("max_changed_files")
    cost = limits.get("max_cost_usd")
    if type(timeout) is not int or not 1 <= timeout <= 3600:
        raise ContractError("invalid_timeout_limit")
    if type(changed) is not int or not 1 <= changed <= 1000:
        raise ContractError("invalid_changed_file_limit")
    if limits.get("network_policy") not in ("none", "read_only"):
        raise ContractError("invalid_network_policy")
    if limits.get("data_access") not in ("metadata_only", "approved_workspace"):
        raise ContractError("invalid_data_access")
    if cost is not None and (isinstance(cost, bool) or not isinstance(cost, (int, float))
                             or cost < 0 or cost > 10000):
        raise ContractError("invalid_cost_limit")

    encoded = canonical(value)
    if len(encoded) > MAX_CONTRACT_BYTES:
        raise ContractError("contract_size_exceeded")
    return {
        "contract": value,
        "contract_digest": hashlib.sha256(encoded).hexdigest(),
        "privileged_operations": sorted(privileged),
        "authorization": authorization,
        "authorization_verified": False,
    }


def _safe_root(root):
    root = Path(root).absolute()
    if root.resolve() != root or root.is_symlink():
        raise ContractError("unsafe_execution_store")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = root.lstat()
    if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
        raise ContractError("unsafe_execution_store")
    return root


def _atomic_json(path, value):
    path = Path(path)
    parent = path.parent
    if parent.resolve() != parent.absolute() or parent.is_symlink():
        raise ContractError("unsafe_execution_record_path")
    data = canonical(value) + b"\n"
    fd, name = tempfile.mkstemp(prefix=".execution-", dir=str(parent))
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        directory_fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OSError:
        try:
            os.unlink(name)
        except OSError:
            pass
        raise ContractError("execution_record_write_failed") from None


def execution_directory(root, execution_id):
    try:
        normalized = str(uuid.UUID(execution_id))
    except (ValueError, TypeError, AttributeError):
        raise ContractError("invalid_execution_id") from None
    if normalized != execution_id:
        raise ContractError("invalid_execution_id")
    base = _safe_root(root)
    directory = base / normalized
    if directory.is_symlink():
        raise ContractError("unsafe_execution_record_path")
    if not directory.exists():
        directory.mkdir(mode=0o700)
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise ContractError("unsafe_execution_record_path")
    return directory


def load_existing(root, execution_id, contract_digest):
    """Return the immutable saved plan, or None; conflicting reuse is rejected."""
    directory = execution_directory(root, execution_id)
    contract_path = directory / "contract.json"
    plan_path = directory / "plan.json"
    if not contract_path.exists() and not plan_path.exists():
        if contract_path.is_symlink() or plan_path.is_symlink():
            raise ContractError("unsafe_execution_record")
        return None
    if contract_path.is_symlink() or plan_path.is_symlink():
        raise ContractError("unsafe_execution_record")
    if not contract_path.is_file() or contract_path.stat().st_nlink != 1:
        raise ContractError("unsafe_execution_record")
    if contract_path.stat().st_mode & 0o077:
        raise ContractError("unsafe_execution_record")
    try:
        saved = json.loads(contract_path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise ContractError("invalid_execution_record") from None
    if saved.get("contract_digest") != contract_digest:
        raise ContractError("execution_id_conflict")
    if not isinstance(saved.get("contract"), dict) or digest(saved["contract"]) != contract_digest:
        raise ContractError("execution_record_binding_invalid")
    if not plan_path.exists():
        return None
    if (not plan_path.is_file() or plan_path.stat().st_nlink != 1
            or plan_path.stat().st_mode & 0o077):
        raise ContractError("unsafe_execution_record")
    try:
        plan = json.loads(plan_path.read_bytes())
    except (OSError, ValueError, UnicodeError):
        raise ContractError("invalid_execution_record") from None
    if (plan.get("contract_digest") != contract_digest
            or plan.get("execution_id") != execution_id):
        raise ContractError("execution_record_binding_invalid")
    receipt = plan.get("receipt")
    if (not isinstance(receipt, dict)
            or receipt.get("contract_digest") != contract_digest
            or receipt.get("digest") != digest(
                {key: value for key, value in receipt.items() if key != "digest"})):
        raise ContractError("execution_receipt_integrity_failed")
    return plan


def save_execution(root, contract, contract_digest, plan):
    directory = execution_directory(root, contract["execution_id"])
    contract_path = directory / "contract.json"
    plan_path = directory / "plan.json"
    if contract_path.exists() or plan_path.exists() or contract_path.is_symlink() or plan_path.is_symlink():
        existing = load_existing(root, contract["execution_id"], contract_digest)
        if existing is not None:
            return existing, True
        if not contract_path.is_file() or plan_path.exists() or plan_path.is_symlink():
            raise ContractError("execution_record_incomplete")
        _atomic_json(plan_path, plan)
        return plan, False
    _atomic_json(contract_path, {"contract_digest": contract_digest, "contract": contract})
    _atomic_json(plan_path, plan)
    return plan, False
