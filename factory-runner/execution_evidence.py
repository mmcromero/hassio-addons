"""Private evidence ledger for FR-EXEC-001.

Only trusted in-process executors may append evidence. No HTTP endpoint accepts
PASS results. Planning reads this ledger and reuses only exact evidence bindings.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import fcntl
import json
import os
from pathlib import Path
import re
import stat
import tempfile
import uuid

MAX_LEDGER_BYTES = 8 * 1024 * 1024
MAX_RECORD_BYTES = 16 * 1024
SHA256 = re.compile(r"^[0-9a-f]{64}$")
IDENT = re.compile(r"^[a-z][a-z0-9_.:-]{1,127}$")
VERSION = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,63}$")
ISSUER = "factory-runner-trusted-executor-v1"


class EvidenceError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("ascii")


def _validation_error(value):
    required = {
        "evidence_id", "test_id", "test_version", "source_sha",
        "unit_digest", "dependency_digest", "environment_id",
        "artifact_digest", "result", "executor", "recorded_at",
        "issuer", "verified",
    }
    if not isinstance(value, dict) or set(value) != required:
        return "record_shape"
    try:
        if str(uuid.UUID(value["evidence_id"])) != value["evidence_id"]:
            return "evidence_id"
    except (ValueError, TypeError, AttributeError):
        return "evidence_id"
    if not isinstance(value["test_id"], str) or not IDENT.fullmatch(value["test_id"]):
        return "test_id"
    if not isinstance(value["test_version"], str) or not VERSION.fullmatch(value["test_version"]):
        return "test_version"
    if not isinstance(value["source_sha"], str) or not re.fullmatch(r"[0-9a-f]{40}", value["source_sha"]):
        return "source_sha"
    if not isinstance(value["unit_digest"], str) or not SHA256.fullmatch(value["unit_digest"]):
        return "unit_digest"
    if not isinstance(value["dependency_digest"], str) or not SHA256.fullmatch(value["dependency_digest"]):
        return "dependency_digest"
    if not isinstance(value["environment_id"], str) or not IDENT.fullmatch(value["environment_id"]):
        return "environment_id"
    if value["artifact_digest"] is not None and (
            not isinstance(value["artifact_digest"], str)
            or not SHA256.fullmatch(value["artifact_digest"])):
        return "artifact_digest"
    if value["result"] != "PASS":
        return "result"
    if not isinstance(value["executor"], str) or not IDENT.fullmatch(value["executor"]):
        return "executor"
    if value["issuer"] != ISSUER:
        return "issuer"
    if value["verified"] is not True:
        return "verified"
    try:
        parsed = datetime.fromisoformat(value["recorded_at"].replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return "recorded_at_timezone"
    except (ValueError, AttributeError, TypeError):
        return "recorded_at"
    if len(canonical(value)) > MAX_RECORD_BYTES:
        return "record_size"
    return None


def _valid_record(value):
    return _validation_error(value) is None


def _safe_ledger(path):
    path = Path(path).absolute()
    if path.resolve() != path or path.is_symlink():
        raise EvidenceError("unsafe_evidence_path_resolution")
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    parent = path.parent.lstat()
    if (not stat.S_ISDIR(parent.st_mode) or parent.st_uid != os.geteuid()
            or stat.S_IMODE(parent.st_mode) & 0o077):
        raise EvidenceError("unsafe_evidence_directory")
    if path.exists():
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.geteuid()
                or info.st_nlink != 1):
            raise EvidenceError("unsafe_evidence_file_metadata")
        if stat.S_IMODE(info.st_mode) != 0o600:
            raise EvidenceError("unsafe_evidence_file_mode")
        if info.st_size > MAX_LEDGER_BYTES:
            raise EvidenceError("evidence_ledger_budget_exceeded")
    return path


def load_evidence(path):
    path = _safe_ledger(path)
    if not path.exists():
        return []
    try:
        raw = path.read_bytes()
    except OSError:
        raise EvidenceError("evidence_ledger_unreadable") from None
    if len(raw) > MAX_LEDGER_BYTES:
        raise EvidenceError("evidence_ledger_budget_exceeded")
    records = []
    for line in raw.splitlines()[-4096:]:
        if len(line) > MAX_RECORD_BYTES:
            continue
        try:
            item = json.loads(line)
        except (ValueError, UnicodeError):
            continue
        if _valid_record(item):
            records.append(item)
    return records


def reusable_evidence(path, *, test_id, test_version, unit_digest,
                      dependency_digest, environment_id, artifact_digest=None):
    for item in reversed(load_evidence(path)):
        if (item["test_id"] == test_id
                and item["test_version"] == test_version
                and item["unit_digest"] == unit_digest
                and item["dependency_digest"] == dependency_digest
                and item["environment_id"] == environment_id
                and item["artifact_digest"] == artifact_digest):
            return item
    return None


def record_evidence(path, *, test_id, test_version, source_sha, unit_digest,
                    dependency_digest, environment_id, artifact_digest,
                    executor):
    """Internal trusted-executor hook; deliberately not exposed by the HTTP API."""
    record = {
        "evidence_id": str(uuid.uuid4()),
        "test_id": test_id,
        "test_version": test_version,
        "source_sha": source_sha,
        "unit_digest": unit_digest,
        "dependency_digest": dependency_digest,
        "environment_id": environment_id,
        "artifact_digest": artifact_digest,
        "result": "PASS",
        "executor": executor,
        "recorded_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "issuer": ISSUER,
        "verified": True,
    }
    validation_error = _validation_error(record)
    if validation_error:
        raise EvidenceError("invalid_evidence_record:" + validation_error)
    path = _safe_ledger(path)
    created = not path.exists()
    fd = os.open(path, os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise EvidenceError("unsafe_evidence_ledger")
        os.fchmod(fd, 0o600)
        existing = reusable_evidence(
            path, test_id=test_id, test_version=test_version,
            unit_digest=unit_digest, dependency_digest=dependency_digest,
            environment_id=environment_id, artifact_digest=artifact_digest)
        if existing:
            return existing
        stream = os.fdopen(fd, "ab")
        fd = -1
        with stream:
            stream.write(canonical(record) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
        if created:
            directory_fd = os.open(path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OSError:
        raise EvidenceError("evidence_ledger_write_failed") from None
    finally:
        if fd >= 0:
            os.close(fd)
    return record
