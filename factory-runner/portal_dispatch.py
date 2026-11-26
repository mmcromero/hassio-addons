"""Narrow Portal-to-Runner dispatch bridge.

Only creates FR-EXEC-001 read-only planning jobs. It never accepts arbitrary
commands, scripts, test execution, preparation, publication, or deployment.
The bridge is separately authenticated and listens on an internal-only port.
"""
from __future__ import annotations

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import hashlib
import hmac
import json
from pathlib import Path
import re
import uuid

from rc_fastlane import load_profile
from workspace_sync import _existing

PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
APPROVED_PROJECTS = frozenset({"avisaqui", "artesao_digital"})
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
SECRET_RE = re.compile(
    r"(?i)(Bearer\s+\S{16,}|gh[pousr]_[A-Za-z0-9]{20,}|"
    r"github_pat_[A-Za-z0-9_]{20,}|sk-[A-Za-z0-9]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,})"
)
MAX_BODY = 64 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _error_code(value: str) -> str:
    return value if isinstance(value, str) and re.fullmatch(
        r"[a-z][a-z0-9_]{0,63}", value
    ) else "portal_dispatch_failed"


class PortalDispatchService:
    def __init__(
        self, *, token: str, orchestrator, projects_dir: Path,
        workspaces_dir: Path, audit_callback=None,
    ):
        self.token = token
        self.orchestrator = orchestrator
        self.projects_dir = Path(projects_dir)
        self.workspaces_dir = Path(workspaces_dir)
        self.audit_callback = audit_callback

    def authorized(self, supplied: str | None) -> bool:
        return (
            isinstance(self.token, str) and len(self.token) >= 32
            and isinstance(supplied, str) and len(supplied) >= 32
            and hmac.compare_digest(supplied.encode(), self.token.encode())
        )

    def submit(self, payload: dict) -> tuple[dict, bool]:
        if not isinstance(payload, dict) or set(payload) != {
            "mission_id", "project_id", "prompt", "created_at"
        }:
            raise ValueError("invalid_portal_payload")

        mission_id = payload.get("mission_id")
        project = payload.get("project_id")
        prompt = payload.get("prompt")
        raw_created_at = payload.get("created_at")
        if not isinstance(mission_id, str) or not UUID_RE.fullmatch(mission_id):
            raise ValueError("invalid_mission_id")
        if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
            raise ValueError("invalid_project")
        if project not in APPROVED_PROJECTS:
            raise ValueError("project_not_approved_for_portal")
        if not isinstance(prompt, str) or not 30 <= len(prompt) <= 8000:
            raise ValueError("invalid_mission_prompt")
        if not isinstance(raw_created_at, str) or len(raw_created_at) > 40:
            raise ValueError("invalid_mission_created_at")
        try:
            parsed_created_at = datetime.fromisoformat(raw_created_at.replace("Z", "+00:00"))
            if parsed_created_at.tzinfo is None:
                raise ValueError
            mission_created_at = parsed_created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        except (ValueError, TypeError):
            raise ValueError("invalid_mission_created_at") from None
        if SECRET_RE.search(prompt):
            raise ValueError("secret_pattern_rejected")

        if (self.projects_dir.is_symlink()
                or self.projects_dir.resolve() != self.projects_dir.absolute()
                or self.workspaces_dir.is_symlink()
                or self.workspaces_dir.resolve() != self.workspaces_dir.absolute()):
            raise ValueError("workspace_roots_unsafe")
        profile_path = self.projects_dir / (project + ".json")
        if (profile_path.is_symlink() or not profile_path.is_file()
                or profile_path.resolve() != profile_path.absolute()):
            raise ValueError("project_profile_unavailable")
        profile = load_profile(profile_path)
        if profile.get("id") != project:
            raise ValueError("profile_mismatch")

        workspace = self.workspaces_dir / project
        if workspace.is_symlink() or not workspace.is_dir():
            raise ValueError("workspace_unavailable")
        marker = _existing(workspace, profile)
        if not isinstance(marker, dict):
            raise ValueError("workspace_unavailable")
        source_sha = marker.get("source_sha")
        if not isinstance(source_sha, str) or not re.fullmatch(r"[0-9a-f]{40}", source_sha):
            raise ValueError("workspace_source_binding_invalid")

        source_path = workspace / "source"
        distribution_path = workspace / "distribution"
        if (source_path.is_symlink() or not source_path.is_dir()
                or source_path.resolve() != source_path.absolute()
                or distribution_path.is_symlink() or not distribution_path.is_dir()
                or distribution_path.resolve() != distribution_path.absolute()):
            raise ValueError("workspace_unavailable")

        execution_id = str(uuid.uuid5(
            uuid.NAMESPACE_URL, "portal-mission:" + mission_id
        ))
        prompt_digest = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        compact_prompt = " ".join(prompt.split())
        excerpt = compact_prompt[:900].strip()
        if not excerpt:
            raise ValueError("invalid_mission_prompt")

        # The full prompt remains in the Portal ledger. The HA Runner receives
        # only a bounded objective excerpt + digest and performs plan-only work.
        contract = {
            "schema_version": "FR-EXEC-001/v1",
            "execution_id": execution_id,
            "created_at": mission_created_at,
            "objective": excerpt,
            "project": project,
            "source": {
                "repository": profile["source_repo"],
                "ref": profile["source_ref"],
                "sha": source_sha,
                "base_sha": None,
            },
            "scope": {
                "include_paths": [],
                "exclude_paths": [],
                "constraints": [
                    "portal_mission_id:" + mission_id,
                    "portal_prompt_sha256:" + prompt_digest,
                    "prompt_full_text_remains_in_portal_ledger",
                ],
            },
            "requested_operations": ["plan"],
            "authorization": {
                "reference": None,
                "declared_operations": [],
            },
            "destinations": [],
            "acceptance_criteria": [
                "Generate a read-only impact and proportional test plan.",
                "Do not execute project code, scripts, tests, builds, or publication.",
            ],
            "limits": {
                "timeout_seconds": 300,
                "max_changed_files": 1000,
                "network_policy": "none",
                "data_access": "approved_workspace",
                "max_cost_usd": None,
            },
        }

        if self.audit_callback:
            self.audit_callback(
                "/api/portal/jobs", None, "requested", execution_id,
                actor="portal-integration",
            )
        job, idempotent = self.orchestrator.submit(contract, profile)
        if not isinstance(job, dict) or job.get("execution_id") != execution_id:
            raise ValueError("execution_job_binding_mismatch")
        return job, idempotent

    def get(self, execution_id: str) -> dict:
        if not isinstance(execution_id, str) or not UUID_RE.fullmatch(execution_id):
            raise ValueError("invalid_execution_id")
        return self.orchestrator.get(execution_id)


class PortalDispatchHTTPServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, address, service: PortalDispatchService):
        self.service = service
        super().__init__(address, PortalDispatchHandler)


class PortalDispatchHandler(BaseHTTPRequestHandler):
    server: PortalDispatchHTTPServer

    def _respond(self, status: int, payload: dict):
        raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=True).encode("ascii")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(raw)

    def _authorized(self) -> bool:
        values = self.headers.get_all("X-Portal-Dispatch-Token", [])
        return len(values) == 1 and self.server.service.authorized(values[0])

    def do_POST(self):
        if self.path != "/v1/jobs":
            self._respond(404, {"error": "not_found"})
            return
        if not self._authorized():
            self._respond(401, {"error": "unauthorized"})
            return
        if self.headers.get("Transfer-Encoding"):
            self._respond(400, {"error": "invalid_transfer_encoding"})
            return
        if self.headers.get_content_type() != "application/json":
            self._respond(415, {"error": "content_type_required"})
            return
        content_lengths = self.headers.get_all("Content-Length", [])
        if len(content_lengths) != 1:
            self._respond(400, {"error": "invalid_content_length"})
            return
        try:
            length = int(content_lengths[0])
        except ValueError:
            self._respond(400, {"error": "invalid_content_length"})
            return
        if length < 1 or length > MAX_BODY:
            self._respond(413, {"error": "request_size_invalid"})
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            job, idempotent = self.server.service.submit(payload)
            self._respond(200 if idempotent else 202, {
                "job": job, "idempotent": idempotent,
            })
        except (ValueError, TypeError, KeyError) as exc:
            self._respond(400, {"error": _error_code(str(exc))})
        except Exception as exc:
            code = _error_code(getattr(exc, "code", "portal_dispatch_failed"))
            self._respond(503, {"error": code})

    def do_GET(self):
        if not self._authorized():
            self._respond(401, {"error": "unauthorized"})
            return
        match = re.fullmatch(r"/v1/jobs/([0-9a-f-]{36})", self.path)
        if not match:
            self._respond(404, {"error": "not_found"})
            return
        try:
            self._respond(200, {"job": self.server.service.get(match.group(1))})
        except Exception as exc:
            code = _error_code(getattr(exc, "code", str(exc)))
            status = 404 if code == "job_not_found" else 400
            self._respond(status, {"error": code})

    def log_message(self, _fmt, *_args):
        return
