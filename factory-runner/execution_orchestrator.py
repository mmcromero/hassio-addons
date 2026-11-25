"""Persistent, single-worker orchestration for trusted read-only execution plans.

The coordinator never executes project code. It accepts immutable FR-EXEC-001
contracts, schedules only the trusted planner, persists every state transition,
and fails closed on corrupt records, cancellation, or timeout.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import fcntl
import json
import os
from pathlib import Path
import platform
import re
import signal
import stat
import subprocess
import sys
import tempfile
import threading
import time
import uuid

import execution_contract
import execution_planner

FORMAT = "factory-job-v1"
MAX_REQUEST_BYTES = 32 * 1024
MAX_EVENT_BYTES = 2 * 1024 * 1024
MAX_WORKER_OUTPUT = 16 * 1024
MAX_ATTEMPTS = 5
MAX_EXPLICIT_RETRIES = 2
POLL_SECONDS = 0.2

STATES = frozenset({
    "RECEBIDA", "PLANEJADA", "EXECUTANDO", "VALIDANDO",
    "CONCLUIDA", "PARCIAL", "IMPEDIDA", "CANCELADA",
})
TERMINAL = frozenset({"CONCLUIDA", "PARCIAL", "IMPEDIDA", "CANCELADA"})
ALLOWED_TRANSITIONS = {
    "RECEBIDA": frozenset({"PLANEJADA", "CANCELADA", "IMPEDIDA"}),
    "PLANEJADA": frozenset({"EXECUTANDO", "CANCELADA", "IMPEDIDA"}),
    "EXECUTANDO": frozenset({"VALIDANDO", "RECEBIDA", "CANCELADA", "IMPEDIDA"}),
    "VALIDANDO": frozenset({"CONCLUIDA", "PARCIAL", "IMPEDIDA", "CANCELADA"}),
    "IMPEDIDA": frozenset({"RECEBIDA"}),
    "CONCLUIDA": frozenset(),
    "PARCIAL": frozenset(),
    "CANCELADA": frozenset(),
}
RETRYABLE_ERRORS = frozenset({"workspace_unavailable", "execution_worker_failed"})
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
PROJECT_RE = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


class OrchestrationError(ValueError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"),
        ensure_ascii=True, allow_nan=False,
    ).encode("ascii")


def _safe_root(root: Path) -> Path:
    path = Path(root).absolute()
    if path.is_symlink() or path.resolve() != path:
        raise OrchestrationError("unsafe_execution_store")
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    info = path.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise OrchestrationError("unsafe_execution_store")
    return path


def _job_id(value: str) -> str:
    try:
        normalized = str(uuid.UUID(value))
    except (ValueError, TypeError, AttributeError):
        raise OrchestrationError("invalid_execution_id") from None
    if normalized != value or not UUID_RE.fullmatch(value):
        raise OrchestrationError("invalid_execution_id")
    return normalized


def _job_dir(root: Path, execution_id: str, *, create: bool = False) -> Path:
    execution_id = _job_id(execution_id)
    base = _safe_root(root)
    directory = base / execution_id
    if directory.is_symlink():
        raise OrchestrationError("unsafe_job_directory")
    if create and not directory.exists():
        directory.mkdir(mode=0o700)
        fd = os.open(base, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    if not directory.exists():
        raise OrchestrationError("job_not_found")
    info = directory.lstat()
    if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
            or stat.S_IMODE(info.st_mode) & 0o077):
        raise OrchestrationError("unsafe_job_directory")
    return directory


def _store_lock(root: Path):
    base = _safe_root(root)
    path = base / ".orchestrator.lock"
    if path.is_symlink():
        raise OrchestrationError("unsafe_execution_store")
    try:
        fd = os.open(
            path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid()):
            os.close(fd)
            raise OrchestrationError("unsafe_execution_store")
        os.fchmod(fd, 0o600)
        fcntl.flock(fd, fcntl.LOCK_EX)
        return fd
    except OSError:
        raise OrchestrationError("execution_store_unavailable") from None


def _unlock(fd: int) -> None:
    try:
        fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


def _read_private_json(path: Path, maximum: int) -> dict:
    if path.is_symlink() or not path.exists():
        raise OrchestrationError("job_record_unavailable")
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > maximum):
            raise OrchestrationError("unsafe_job_record")
        raw = path.read_bytes()
        value = json.loads(raw)
    except OrchestrationError:
        raise
    except (OSError, ValueError, UnicodeError):
        raise OrchestrationError("invalid_job_record") from None
    if not isinstance(value, dict):
        raise OrchestrationError("invalid_job_record")
    return value


def _write_new_json(path: Path, value: dict) -> None:
    if path.is_symlink() or path.exists():
        raise OrchestrationError("job_record_conflict")
    data = _canonical(value) + b"\n"
    if len(data) > MAX_REQUEST_BYTES:
        raise OrchestrationError("job_request_too_large")
    fd = -1
    temporary = None
    try:
        # Publish atomically: an interrupted write leaves only an ignored
        # staging file, never a truncated request.json that poisons recovery.
        fd, temporary = tempfile.mkstemp(prefix=".request-", dir=str(path.parent))
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as stream:
            fd = -1
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if path.is_symlink() or path.exists():
            raise OrchestrationError("job_record_conflict")
        os.replace(temporary, path)
        temporary = None
        directory_fd = os.open(
            path.parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
        try:
            os.fsync(directory_fd)
        finally:
            os.close(directory_fd)
    except OrchestrationError:
        raise
    except OSError:
        raise OrchestrationError("job_request_persist_failed") from None
    finally:
        if fd >= 0:
            try:
                os.close(fd)
            except OSError:
                pass
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass


def _append_event(directory: Path, event: dict) -> None:
    path = directory / "events.jsonl"
    if path.is_symlink():
        raise OrchestrationError("unsafe_job_event_log")
    data = _canonical(event) + b"\n"
    created = not path.exists()
    try:
        fd = os.open(
            path, os.O_WRONLY | os.O_APPEND | os.O_CREAT
            | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid()):
            os.close(fd)
            raise OrchestrationError("unsafe_job_event_log")
        os.fchmod(fd, 0o600)
        try:
            written = os.write(fd, data)
            if written != len(data):
                raise OSError("short event write")
            os.fsync(fd)
        finally:
            os.close(fd)
        if created:
            directory_fd = os.open(
                directory, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
    except OrchestrationError:
        raise
    except OSError:
        raise OrchestrationError("job_event_persist_failed") from None


def _read_events(directory: Path) -> list[dict]:
    path = directory / "events.jsonl"
    if not path.exists() and not path.is_symlink():
        return []
    if path.is_symlink():
        raise OrchestrationError("unsafe_job_event_log")
    try:
        info = path.lstat()
        if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) & 0o077
                or info.st_size > MAX_EVENT_BYTES):
            raise OrchestrationError("unsafe_job_event_log")
        raw = path.read_bytes()
    except OrchestrationError:
        raise
    except OSError:
        raise OrchestrationError("job_event_log_unavailable") from None
    if raw and not raw.endswith(b"\n"):
        boundary = raw.rfind(b"\n") + 1
        try:
            fd = os.open(path, os.O_WRONLY | os.O_NOFOLLOW)
            try:
                os.ftruncate(fd, boundary)
                os.fsync(fd)
            finally:
                os.close(fd)
        except OSError:
            raise OrchestrationError("job_event_log_repair_failed") from None
        raw = raw[:boundary]
    lines = raw.splitlines(keepends=True)
    events = []
    for index, line in enumerate(lines):
        if not line.endswith(b"\n") and index == len(lines) - 1:
            # A power loss may truncate only the final append. The last complete
            # fsynced snapshot remains authoritative and startup recovery repairs it.
            break
        try:
            event = json.loads(line)
        except (ValueError, UnicodeError):
            raise OrchestrationError("job_event_log_corrupt") from None
        if (not isinstance(event, dict) or type(event.get("sequence")) is not int
                or event["sequence"] != len(events) + 1
                or not isinstance(event.get("snapshot"), dict)
                or event["snapshot"].get("status") not in STATES):
            raise OrchestrationError("job_event_log_corrupt")
        events.append(event)
    return events


def _initial_state(contract: dict, contract_digest: str, *, existing_plan: bool) -> dict:
    now = _now()
    return {
        "format": FORMAT,
        "execution_id": contract["execution_id"],
        "job_id": contract["execution_id"],
        "contract_digest": contract_digest,
        "project": contract["project"],
        "environment": "home_assistant_addon",
        "architecture": platform.machine(),
        "source_sha": contract["source"]["sha"],
        "source_ref": contract["source"]["ref"],
        "status": "VALIDANDO" if existing_plan else "RECEBIDA",
        "created_at": now,
        "updated_at": now,
        "started_at": None,
        "ended_at": None,
        "attempts": 0,
        "retry_count": 0,
        "recovery_count": 0,
        "cancel_requested": False,
        "deadline_epoch": 0,
        "next_attempt_epoch": 0,
        "error_code": None,
        "steps": [
            {"name": "contract_validation", "status": "PASS",
             "code": "contract_validated"}
        ],
        "result": None,
        "event_seq": 0,
    }


def _public_state(state: dict, events: list[dict] | None = None) -> dict:
    result = deepcopy(state)
    result.pop("event_seq", None)
    if events is not None:
        safe_events = [
            {
                "sequence": item["sequence"],
                "time": item["time"],
                "code": item["code"],
                "from_state": item.get("from_state"),
                "to_state": item.get("to_state"),
            }
            for item in events[-100:]
        ]
        result["events"] = safe_events
        result["logs_redacted"] = safe_events
    return result


class ExecutionOrchestrator:
    """One persistent queue and one trusted planner worker per add-on instance."""

    def __init__(
        self,
        executions_dir: Path,
        api_lock: threading.Lock,
        *,
        worker_script: Path = Path("/app/execution_plan_worker.py"),
        app_dir: Path = Path("/app"),
        projects_dir: Path = Path("/app/projects"),
        workspaces_dir: Path = Path("/data/factory-runner/workspaces"),
        catalog_dir: Path = Path("/app/test_catalogs"),
        audit_callback=None,
    ):
        self.root = Path(executions_dir)
        self.api_lock = api_lock
        self.worker_script = Path(worker_script)
        self.app_dir = Path(app_dir)
        self.projects_dir = Path(projects_dir)
        self.workspaces_dir = Path(workspaces_dir)
        self.catalog_dir = Path(catalog_dir)
        self.audit_callback = audit_callback
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._process_lock = threading.Lock()
        self._active_process: subprocess.Popen | None = None

    def _locked(self):
        return _store_lock(self.root)

    def _load_locked(self, execution_id: str):
        directory = _job_dir(self.root, execution_id)
        request = _read_private_json(directory / "request.json", MAX_REQUEST_BYTES)
        if (request.get("format") != FORMAT
                or request.get("execution_id") != execution_id
                or not isinstance(request.get("contract"), dict)
                or request.get("contract_digest")
                != execution_contract.digest(request["contract"])):
            raise OrchestrationError("job_request_binding_invalid")
        events = _read_events(directory)
        if events:
            for item in events:
                snapshot = item["snapshot"]
                if (snapshot.get("execution_id") != execution_id
                        or snapshot.get("contract_digest") != request["contract_digest"]
                        or snapshot.get("event_seq") != item["sequence"]):
                    raise OrchestrationError("job_state_binding_invalid")
            state = events[-1]["snapshot"]
        else:
            state = _initial_state(
                request["contract"], request["contract_digest"], existing_plan=False)
        return directory, request, state, events

    def _append_snapshot(
        self, directory: Path, state: dict, code: str,
        from_state: str | None, to_state: str,
    ) -> None:
        if to_state not in STATES:
            raise OrchestrationError("invalid_job_state")
        if (from_state is not None and to_state != from_state
                and to_state not in ALLOWED_TRANSITIONS.get(from_state, frozenset())):
            raise OrchestrationError("invalid_job_transition")
        next_state = deepcopy(state)
        next_state["event_seq"] = int(state.get("event_seq", 0)) + 1
        next_state["updated_at"] = _now()
        event = {
            "sequence": next_state["event_seq"],
            "time": next_state["updated_at"],
            "code": code,
            "from_state": from_state,
            "to_state": to_state,
            "snapshot": next_state,
        }
        _append_event(directory, event)
        state.clear()
        state.update(next_state)

    def _mark_cancelled(self, directory: Path, state: dict, code: str) -> None:
        previous = state["status"]
        state["status"] = "CANCELADA"
        state["ended_at"] = _now()
        state["error_code"] = None
        state["cancel_requested"] = True
        self._append_snapshot(directory, state, code, previous, state["status"])

    def submit(self, contract: dict, profile: dict) -> tuple[dict, bool]:
        try:
            validated = execution_contract.validate_contract(contract, profile)
        except execution_contract.ContractError as exc:
            raise OrchestrationError(str(exc)) from None
        normalized = validated["contract"]
        contract_digest = validated["contract_digest"]
        execution_id = normalized["execution_id"]
        fd = self._locked()
        try:
            directory = _job_dir(self.root, execution_id, create=True)
            request_path = directory / "request.json"
            if request_path.exists() or request_path.is_symlink():
                request = _read_private_json(request_path, MAX_REQUEST_BYTES)
                if request.get("contract_digest") != contract_digest:
                    raise OrchestrationError("execution_id_conflict")
                directory, request, state, events = self._load_locked(execution_id)
                if not events:
                    self._append_snapshot(
                        directory, state, "orphan_request_recovered", None, state["status"])
                    events = _read_events(directory)
                return _public_state(state, events), True

            try:
                existing_plan = execution_contract.load_existing(
                    self.root, execution_id, contract_digest)
            except execution_contract.ContractError as exc:
                raise OrchestrationError(str(exc)) from None
            request = {
                "format": FORMAT,
                "execution_id": execution_id,
                "contract_digest": contract_digest,
                "contract": normalized,
            }
            _write_new_json(request_path, request)
            state = _initial_state(
                normalized, contract_digest, existing_plan=existing_plan is not None)
            if existing_plan is not None:
                state["result"] = self._plan_summary(existing_plan)
                state["steps"].append({
                    "name": "plan_persistence", "status": "PASS",
                    "code": "existing_plan_reused",
                })
            self._append_snapshot(
                directory, state,
                "existing_plan_adopted" if existing_plan is not None else "job_received",
                None, state["status"])
            return _public_state(state, _read_events(directory)), False
        finally:
            _unlock(fd)

    def get(self, execution_id: str) -> dict:
        fd = self._locked()
        try:
            directory, _request, state, events = self._load_locked(_job_id(execution_id))
            if not events:
                return _public_state(state, [])
            return _public_state(state, events)
        finally:
            _unlock(fd)

    def list(
        self, *, project: str | None = None, source_sha: str | None = None,
        status: str | None = None, limit: int = 25, offset: int = 0,
    ) -> dict:
        if project is not None and not PROJECT_RE.fullmatch(project):
            raise OrchestrationError("invalid_project_filter")
        if source_sha is not None and not SHA_RE.fullmatch(source_sha):
            raise OrchestrationError("invalid_source_sha_filter")
        if status is not None and status not in STATES:
            raise OrchestrationError("invalid_status_filter")
        if type(limit) is not int or not 1 <= limit <= 100:
            raise OrchestrationError("invalid_page_limit")
        if type(offset) is not int or not 0 <= offset <= 10000:
            raise OrchestrationError("invalid_page_offset")
        fd = self._locked()
        try:
            root = _safe_root(self.root)
            items = []
            for entry in root.iterdir():
                if not UUID_RE.fullmatch(entry.name):
                    continue
                if entry.is_symlink():
                    raise OrchestrationError("unsafe_job_directory")
                if not (entry / "request.json").exists():
                    continue
                _directory, _request, state, _events = self._load_locked(entry.name)
                if project is not None and state["project"] != project:
                    continue
                if source_sha is not None and state["source_sha"] != source_sha:
                    continue
                if status is not None and state["status"] != status:
                    continue
                items.append(_public_state(state))
            items.sort(key=lambda item: (item["created_at"], item["execution_id"]), reverse=True)
            total = len(items)
            page = items[offset:offset + limit]
            next_offset = offset + limit if offset + limit < total else None
            return {"jobs": page, "total": total, "limit": limit,
                    "offset": offset, "next_offset": next_offset}
        finally:
            _unlock(fd)

    def cancel(self, execution_id: str) -> dict:
        execution_id = _job_id(execution_id)
        fd = self._locked()
        try:
            directory, _request, state, events = self._load_locked(execution_id)
            if not events:
                self._append_snapshot(directory, state, "job_request_recovered",
                                      None, state["status"])
            if state["status"] in TERMINAL:
                return _public_state(state, _read_events(directory))
            previous = state["status"]
            if previous in ("RECEBIDA", "PLANEJADA"):
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_execution")
            else:
                state["cancel_requested"] = True
                self._append_snapshot(
                    directory, state, "job_cancel_requested",
                    previous, state["status"])
            return _public_state(state, _read_events(directory))
        finally:
            _unlock(fd)

    def retry(self, execution_id: str) -> dict:
        execution_id = _job_id(execution_id)
        fd = self._locked()
        try:
            directory, _request, state, events = self._load_locked(execution_id)
            if (state["status"] != "IMPEDIDA"
                    or state.get("error_code") not in RETRYABLE_ERRORS
                    or state.get("retry_count", 0) >= MAX_EXPLICIT_RETRIES
                    or state.get("attempts", 0) >= MAX_ATTEMPTS):
                raise OrchestrationError("job_not_retryable")
            previous = state["status"]
            state["status"] = "RECEBIDA"
            state["retry_count"] += 1
            state["cancel_requested"] = False
            state["deadline_epoch"] = 0
            state["next_attempt_epoch"] = 0
            state["started_at"] = None
            state["ended_at"] = None
            state["error_code"] = None
            state["result"] = None
            self._append_snapshot(
                directory, state, "job_retry_accepted", previous, state["status"])
            return _public_state(state, _read_events(directory))
        finally:
            _unlock(fd)

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._recover()
        self._stop.clear()
        self._thread = threading.Thread(
            target=self._worker_loop, name="factory-execution-orchestrator", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 8.0) -> None:
        self._stop.set()
        with self._process_lock:
            process = self._active_process
        if process is not None and process.poll() is None:
            self._kill_process_group(process)
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=max(0.1, timeout))

    def _recover(self) -> None:
        fd = self._locked()
        try:
            root = _safe_root(self.root)
            for entry in root.iterdir():
                if not UUID_RE.fullmatch(entry.name):
                    continue
                if entry.is_symlink():
                    raise OrchestrationError("unsafe_job_directory")
                if not (entry / "request.json").exists():
                    continue
                directory, _request, state, events = self._load_locked(entry.name)
                if not events:
                    self._append_snapshot(
                        directory, state, "orphan_request_recovered", None, state["status"])
                    continue
                if state["status"] not in ("EXECUTANDO", "VALIDANDO"):
                    continue
                previous = state["status"]
                plan_path = directory / "plan.json"
                if plan_path.is_symlink():
                    raise OrchestrationError("unsafe_execution_record")
                if state.get("cancel_requested"):
                    state["status"] = "CANCELADA"
                    state["ended_at"] = _now()
                    code = "interrupted_job_cancelled"
                elif plan_path.is_file():
                    state["status"] = "VALIDANDO"
                    state["recovery_count"] += 1
                    state["next_attempt_epoch"] = 0
                    code = "persisted_plan_recovered_for_validation"
                elif state.get("deadline_epoch") and time.time() >= state["deadline_epoch"]:
                    state["status"] = "IMPEDIDA"
                    state["error_code"] = "execution_timeout"
                    state["ended_at"] = _now()
                    code = "interrupted_job_timed_out"
                else:
                    state["status"] = "RECEBIDA"
                    state["recovery_count"] += 1
                    state["next_attempt_epoch"] = 0
                    code = "job_recovered_after_restart"
                self._append_snapshot(
                    directory, state, code, previous, state["status"])
        finally:
            _unlock(fd)

    def _worker_loop(self) -> None:
        while not self._stop.is_set():
            try:
                execution_id = self._claim_next()
                if execution_id is None:
                    self._stop.wait(0.4)
                    continue
                try:
                    self._process(execution_id)
                except OrchestrationError:
                    # Corrupt or unsafe persistence is not skipped.
                    self._stop.set()
                except Exception:
                    try:
                        self._finish_blocked(execution_id, "orchestrator_internal_error")
                    except Exception:
                        self._stop.set()

    def _claim_next(self) -> str | None:
        fd = self._locked()
        try:
            root = _safe_root(self.root)
            candidates = []
            for entry in root.iterdir():
                if not UUID_RE.fullmatch(entry.name):
                    continue
                if entry.is_symlink():
                    raise OrchestrationError("unsafe_job_directory")
                if not (entry / "request.json").exists():
                    continue
                directory, _request, state, events = self._load_locked(entry.name)
                if not events:
                    self._append_snapshot(
                        directory, state, "orphan_request_recovered", None, state["status"])
                if state["status"] not in ("RECEBIDA", "PLANEJADA", "VALIDANDO"):
                    continue
                if state.get("next_attempt_epoch", 0) > time.time():
                    continue
                candidates.append((state["created_at"], entry.name, state))
            if not candidates:
                return None
            candidates.sort(key=lambda item: (item[0], item[1]))
            _created, execution_id, state = candidates[0]
            if state.get("cancel_requested"):
                directory = _job_dir(self.root, execution_id)
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_worker_claim")
                return None
            if state["status"] == "RECEBIDA":
                directory = _job_dir(self.root, execution_id)
                previous = state["status"]
                state["status"] = "PLANEJADA"
                self._append_snapshot(
                    directory, state, "job_planned", previous, state["status"])
            return execution_id
        finally:
            _unlock(fd)

    def _process(self, execution_id: str) -> None:
        if self._stop.is_set():
            return
        state = self.get(execution_id)
        worker_result = None
        if state["status"] == "PLANEJADA":
            if not self.api_lock.acquire(blocking=False):
                self._defer(execution_id, "api_busy", 1)
                return
            try:
                state = self._begin_attempt(execution_id)
                if state["status"] == "CANCELADA":
                    return
                if state["status"] != "EXECUTANDO":
                    return
                directory = _job_dir(self.root, execution_id)
                plan_path = directory / "plan.json"
                if plan_path.is_symlink():
                    self._finish_blocked(execution_id, "unsafe_execution_record")
                    return
                if plan_path.is_file():
                    self._set_status(execution_id, "VALIDANDO", "existing_plan_reused")
                else:
                    worker_result = self._run_plan_worker(execution_id)
                    if worker_result.get("error") == "cancelled":
                        self._finish_cancelled(execution_id)
                        return
                    if worker_result.get("error") == "interrupted":
                        return
                    if worker_result.get("error") == "execution_timeout":
                        self._finish_blocked(execution_id, "execution_timeout")
                        return
                    if worker_result.get("error") == "workspace_unavailable":
                        self._defer_or_block(execution_id, "workspace_unavailable")
                        return
                    if worker_result.get("error"):
                        self._finish_blocked(execution_id, "execution_worker_failed")
                        return
                    self._set_status(execution_id, "VALIDANDO", "plan_generated")
            finally:
                self.api_lock.release()

        state = self.get(execution_id)
        if state["status"] != "VALIDANDO":
            return
        if state.get("cancel_requested"):
            self._finish_cancelled(execution_id)
            return
        try:
            plan = execution_planner.get_execution(self.root, execution_id)
            directory = _job_dir(self.root, execution_id)
            request = _read_private_json(directory / "request.json", MAX_REQUEST_BYTES)
            if (plan.get("execution_id") != execution_id
                    or plan.get("contract_digest") != request.get("contract_digest")
                    or plan.get("project") != state.get("project")
                    or not isinstance(plan.get("source"), dict)
                    or plan["source"].get("sha") != state.get("source_sha")):
                raise OrchestrationError("execution_plan_binding_invalid")
            result = self._plan_summary(
                plan, execution_id=execution_id,
                contract_digest=request["contract_digest"],
                worker_result=worker_result)
        except (execution_planner.PlannerError, OSError, ValueError, TypeError):
            self._finish_blocked(execution_id, "execution_plan_integrity_failed")
            return
        selected = result["selected_count"]
        blocked = result["blocked_operations"]
        if plan.get("status") == "BLOCKED_SCOPE":
            final = "IMPEDIDA"
            error = "scope_outside_approved_contract"
        elif plan.get("status") == "PARTIAL" or selected or blocked:
            final = "PARCIAL"
            error = None
        else:
            final = "CONCLUIDA"
            error = None
        state = self._load_state_for_update(execution_id)
        if selected:
            test_status, test_code = "NOT_EXECUTED", "sandbox_stage_5_required"
        elif result["reused_count"]:
            test_status, test_code = "REUSED", "exact_evidence_reused"
        else:
            test_status, test_code = "NOT_REQUIRED", "no_execution_required"
        state["steps"] = [
            {"name": "contract_validation", "status": "PASS",
             "code": "contract_validated"},
            {"name": "workspace_resolution", "status": "PASS",
             "code": "managed_workspace_verified"},
            {"name": "impact_analysis", "status": "PASS",
             "code": "impact_plan_generated"},
            {"name": "plan_persistence", "status": "PASS",
             "code": "plan_and_receipt_persisted"},
            {"name": "receipt_validation", "status": "PASS",
             "code": "receipt_digest_verified"},
            {"name": "project_tests", "status": test_status, "code": test_code},
        ]
        state["result"] = result
        state["error_code"] = error
        state["ended_at"] = _now()
        state["status"] = final
        state["cancel_requested"] = False
        self._save_transition(execution_id, state, "job_finished", "VALIDANDO", final)

    def _load_state_for_update(self, execution_id: str) -> dict:
        fd = self._locked()
        try:
            _directory, _request, state, _events = self._load_locked(execution_id)
            return state
        finally:
            _unlock(fd)

    def _save_transition(
        self, execution_id: str, state: dict, code: str,
        from_state: str, to_state: str,
    ) -> dict:
        fd = self._locked()
        try:
            directory, _request, current, _events = self._load_locked(execution_id)
            if current["status"] in TERMINAL:
                return _public_state(current)
            if current["status"] != from_state:
                raise OrchestrationError("job_state_changed")
            if current.get("cancel_requested"):
                self._mark_cancelled(
                    directory, current, "job_cancelled_before_completion")
                return _public_state(current, _read_events(directory))
            next_state = deepcopy(current)
            for key in ("steps", "result", "error_code", "ended_at"):
                if key in state:
                    next_state[key] = deepcopy(state[key])
            next_state["status"] = to_state
            if self.audit_callback is not None:
                audit_state = ("completed_read_only"
                               if to_state in ("CONCLUIDA", "PARCIAL")
                               else "blocked_worker")
                try:
                    self.audit_callback("/api/jobs", None, audit_state, execution_id)
                except Exception:
                    next_state["status"] = "IMPEDIDA"
                    next_state["error_code"] = "audit_unavailable"
                    next_state["ended_at"] = _now()
                    code = "job_blocked_audit_unavailable"
                    to_state = "IMPEDIDA"
            self._append_snapshot(
                directory, next_state, code, from_state, to_state)
            return _public_state(next_state, _read_events(directory))
        finally:
            _unlock(fd)

    def _set_status(self, execution_id: str, status: str, code: str) -> None:
        if status not in STATES:
            raise OrchestrationError("invalid_job_state")
        fd = self._locked()
        try:
            directory, _request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return
            previous = state["status"]
            state["status"] = status
            self._append_snapshot(directory, state, code, previous, status)
        finally:
            _unlock(fd)

    def _begin_attempt(self, execution_id: str) -> dict:
        fd = self._locked()
        try:
            directory, request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return state
            if state.get("cancel_requested"):
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_execution")
                return state
            if state["status"] != "PLANEJADA":
                return state
            timeout = request["contract"]["limits"]["timeout_seconds"]
            state["status"] = "EXECUTANDO"
            state["attempts"] += 1
            if not state.get("started_at"):
                state["started_at"] = _now()
            if not state.get("deadline_epoch"):
                state["deadline_epoch"] = time.time() + timeout
            state["next_attempt_epoch"] = 0
            self._append_snapshot(
                directory, state, "job_execution_started",
                "PLANEJADA", state["status"])
            return state
        finally:
            _unlock(fd)

    def _defer(self, execution_id: str, code: str, seconds: int) -> None:
        fd = self._locked()
        try:
            directory, _request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return
            if state.get("cancel_requested"):
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_defer")
                return
            state["status"] = "PLANEJADA"
            state["next_attempt_epoch"] = time.time() + seconds
            self._append_snapshot(
                directory, state, "job_deferred_" + code,
                "PLANEJADA", state["status"])
        finally:
            _unlock(fd)

    def _defer_or_block(self, execution_id: str, code: str) -> None:
        fd = self._locked()
        try:
            directory, _request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return
            if state.get("cancel_requested"):
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_retry")
                return
            if (state["attempts"] >= MAX_ATTEMPTS
                    or (state.get("deadline_epoch")
                        and time.time() >= state["deadline_epoch"])):
                previous = state["status"]
                state["status"] = "IMPEDIDA"
                state["error_code"] = code
                state["ended_at"] = _now()
                self._append_snapshot(
                    directory, state, "job_blocked_" + code,
                    previous, state["status"])
            else:
                previous = state["status"]
                state["status"] = "RECEBIDA"
                state["error_code"] = code
                state["next_attempt_epoch"] = time.time() + min(15, 2 ** state["attempts"])
                self._append_snapshot(
                    directory, state, "job_retry_scheduled_" + code,
                    previous, state["status"])
        finally:
            _unlock(fd)

    def _finish_blocked(self, execution_id: str, code: str) -> None:
        fd = self._locked()
        try:
            directory, _request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return
            if state.get("cancel_requested"):
                self._mark_cancelled(
                    directory, state, "job_cancelled_before_block")
                return
            previous = state["status"]
            state["status"] = "IMPEDIDA"
            state["error_code"] = code
            state["ended_at"] = _now()
            self._append_snapshot(
                directory, state, "job_blocked_" + code,
                previous, state["status"])
        finally:
            _unlock(fd)

    def _finish_cancelled(self, execution_id: str) -> None:
        fd = self._locked()
        try:
            directory, _request, state, _events = self._load_locked(execution_id)
            if state["status"] in TERMINAL:
                return
            self._mark_cancelled(directory, state, "job_cancelled")
        finally:
            _unlock(fd)

    def _cancel_requested(self, execution_id: str) -> bool:
        try:
            return bool(self.get(execution_id).get("cancel_requested"))
        except OrchestrationError:
            return True

    @staticmethod
    def _kill_process_group(process: subprocess.Popen) -> None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
        except OSError:
            try:
                process.kill()
            except OSError:
                pass
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                process.kill()
                process.wait(timeout=2)
            except (OSError, subprocess.TimeoutExpired):
                pass
        except OSError:
            pass

    def _run_plan_worker(self, execution_id: str) -> dict:
        state = self.get(execution_id)
        directory = _job_dir(self.root, execution_id)
        request = _read_private_json(directory / "request.json", MAX_REQUEST_BYTES)
        project = request["contract"]["project"]
        if not PROJECT_RE.fullmatch(project):
            return {"error": "invalid_project"}
        if self.worker_script.is_symlink() or not self.worker_script.is_file():
            return {"error": "execution_worker_unavailable"}
        env = {
            "PATH": "/usr/bin:/bin",
            "HOME": "/nonexistent",
            "LC_ALL": "C",
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "GIT_OPTIONAL_LOCKS": "0",
            "GIT_NO_REPLACE_OBJECTS": "1",
            "GIT_LFS_SKIP_SMUDGE": "1",
            "RUNNER_PROJECTS_DIR": str(self.projects_dir),
            "RUNNER_WORKSPACES_DIR": str(self.workspaces_dir),
            "RUNNER_EXECUTIONS_DIR": str(self.root),
            "RUNNER_TEST_CATALOGS_DIR": str(self.catalog_dir),
        }
        try:
            process = subprocess.Popen(
                [sys.executable, "-I", str(self.worker_script), "--project", project],
                cwd=str(self.app_dir), env=env, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                start_new_session=True,
            )
        except OSError:
            return {"error": "execution_worker_unavailable"}
        with self._process_lock:
            self._active_process = process
        try:
            payload = _canonical({"contract": request["contract"]})
            try:
                process.stdin.write(payload)
                process.stdin.close()
            except OSError:
                self._kill_process_group(process)
                return {"error": "execution_worker_failed"}
            while process.poll() is None:
                if self._stop.is_set():
                    self._kill_process_group(process)
                    return {"error": "interrupted"}
                if self._cancel_requested(execution_id):
                    self._kill_process_group(process)
                    return {"error": "cancelled"}
                deadline = self.get(execution_id).get("deadline_epoch", 0)
                if deadline and time.time() >= deadline:
                    self._kill_process_group(process)
                    return {"error": "execution_timeout"}
                try:
                    process.wait(timeout=POLL_SECONDS)
                except subprocess.TimeoutExpired:
                    continue
            output = process.stdout.read(MAX_WORKER_OUTPUT + 1)
            if len(output) > MAX_WORKER_OUTPUT:
                return {"error": "execution_worker_failed"}
            try:
                result = json.loads(output.decode("utf-8"))
            except (ValueError, UnicodeError):
                return {"error": "execution_worker_failed"}
            if process.returncode != 0:
                code = result.get("error") if isinstance(result, dict) else None
                return {"error": code if code == "workspace_unavailable"
                        else "execution_worker_failed"}
            required = {
                "ok", "execution_id", "contract_digest", "plan_status",
                "plan_digest", "receipt_digest", "selected_count",
                "reused_count", "omitted_count",
            }
            if (not isinstance(result, dict) or set(result) != required
                    or result.get("ok") is not True
                    or result.get("execution_id") != execution_id
                    or result.get("contract_digest") != request["contract_digest"]
                    or result.get("plan_status") not in ("PLANNED", "PARTIAL", "BLOCKED_SCOPE")
                    or not isinstance(result.get("plan_digest"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", result["plan_digest"])
                    or not isinstance(result.get("receipt_digest"), str)
                    or not re.fullmatch(r"[0-9a-f]{64}", result["receipt_digest"])
                    or any(type(result.get(key)) is not int or result[key] < 0
                           for key in ("selected_count", "reused_count", "omitted_count"))):
                return {"error": "execution_worker_failed"}
            return result
        finally:
            if process.poll() is None:
                self._kill_process_group(process)
            with self._process_lock:
                if self._active_process is process:
                    self._active_process = None
            try:
                if process.stdin and not process.stdin.closed:
                    process.stdin.close()
                if process.stdout:
                    process.stdout.close()
            except OSError:
                pass

    @staticmethod
    def _plan_summary(
        plan: dict, *, execution_id: str | None = None,
        contract_digest: str | None = None,
        worker_result: dict | None = None,
    ) -> dict:
        tests = plan.get("tests", {})
        operations = plan.get("operations", {})
        receipt = plan.get("receipt", {})
        if (plan.get("format") != "factory-execution-plan-v1"
                or plan.get("status") not in ("PLANNED", "PARTIAL", "BLOCKED_SCOPE")
                or not isinstance(plan.get("execution_id"), str)
                or (execution_id is not None and plan.get("execution_id") != execution_id)
                or not isinstance(plan.get("contract_digest"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", plan["contract_digest"])
                or (contract_digest is not None
                    and plan.get("contract_digest") != contract_digest)
                or not isinstance(tests, dict) or tests.get("execution_performed") is not False
                or not isinstance(operations, dict)
                or operations.get("authorization_verified") is not False
                or not isinstance(receipt, dict)
                or not isinstance(receipt.get("digest"), str)
                or not re.fullmatch(r"[0-9a-f]{64}", receipt["digest"])):
            raise OrchestrationError("execution_plan_integrity_failed")
        selected = tests.get("selected_count")
        reused = tests.get("reused_count")
        omitted = tests.get("omitted_count")
        if any(type(value) is not int or value < 0 for value in (selected, reused, omitted)):
            raise OrchestrationError("execution_plan_integrity_failed")
        if worker_result is not None:
            if (not isinstance(worker_result, dict)
                    or worker_result.get("ok") is not True
                    or worker_result.get("execution_id") != plan.get("execution_id")
                    or worker_result.get("contract_digest") != plan.get("contract_digest")
                    or worker_result.get("plan_status") != plan.get("status")
                    or worker_result.get("plan_digest") != execution_contract.digest(plan)
                    or worker_result.get("receipt_digest") != receipt.get("digest")
                    or worker_result.get("selected_count") != selected
                    or worker_result.get("reused_count") != reused
                    or worker_result.get("omitted_count") != omitted):
                raise OrchestrationError("execution_plan_integrity_failed")
        blocked = operations.get("blocked", [])
        if (not isinstance(blocked, list)
                or any(not isinstance(item, dict)
                       or not isinstance(item.get("operation"), str)
                       or not isinstance(item.get("reason"), str)
                       for item in blocked)):
            raise OrchestrationError("execution_plan_integrity_failed")
        blocked_summary = [
            {"operation": item["operation"], "reason": item["reason"]}
            for item in blocked
        ]
        approval_required = any(
            item["operation"] in execution_contract.AUTH_REQUIRED
            for item in blocked_summary)
        if approval_required:
            next_action = "independent_authorization_required"
        elif plan["status"] == "BLOCKED_SCOPE":
            next_action = "scope_review_required"
        elif selected:
            next_action = "sandbox_stage_5_required"
        elif blocked_summary:
            next_action = "resolve_blocked_operations"
        else:
            next_action = "none"
        return {
            "plan_status": plan["status"],
            "plan_digest": execution_contract.digest(plan),
            "receipt_digest": receipt["digest"],
            "evidence_digest": receipt["digest"],
            "selected_count": selected,
            "reused_count": reused,
            "omitted_count": omitted,
            "test_counts": {"selected": selected, "reused": reused, "omitted": omitted},
            "blocked_operations": blocked_summary,
            "approval_required": approval_required,
            "tests_execution_performed": False,
            "authorization_verified": False,
            "next_action": next_action,
        }
