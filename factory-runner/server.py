#!/usr/bin/env python3
"""Factory Runner: authenticated, fail-closed API.

No Git publication or AI-supplied filesystem writes are exposed until an
independent authorization/publishing workflow has been reviewed and approved.
"""
import hmac
import http.server
import json
import os
import re
import signal
import sys
import subprocess
import threading
import time
import uuid
from pathlib import Path

from rc_fastlane import PreflightError, evaluate, load_profile, prepare, git as trusted_git
from sandbox_export import SandboxUnavailable
from declarative_export import (DeclarativeExportError, prepare_declarative,
                                expand_trusted_rules, extend_approved_mapping,
                                write_distribution_provenance)

HOST = os.environ.get("RUNNER_BIND_HOST", "127.0.0.1")
PORT = int(os.environ.get("RUNNER_PORT", "9876"))
MAX_BODY = 4096
LOCK = threading.Lock()
OPERATIONS = {"/api/fechar-pacote", "/api/corrigir-issue"}
ISSUE = re.compile(r"^[1-9][0-9]{0,7}$")
PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
PROJECTS_DIR = Path(os.environ.get("RUNNER_PROJECTS_DIR", "/app/projects"))
WORKSPACES_DIR = Path(os.environ.get("RUNNER_WORKSPACES_DIR", "/data/factory-runner/workspaces"))
PREPARATIONS_DIR = Path(os.environ.get("RUNNER_PREPARATIONS_DIR", "/data/factory-runner/preparations"))
AUDIT_PATH = Path(os.environ.get("RUNNER_AUDIT_PATH", "/data/factory-runner/audit.jsonl"))

def authenticated(header):
    """Fail closed; never accept a missing, empty, or malformed bearer token."""
    expected = os.environ.get("RUNNER_AUTH_TOKEN", "")
    if not expected or not header or len(header) > 4096 or len(expected) < 32:
        return False
    scheme, sep, value = header.partition(" ")
    if scheme.lower() != "bearer" or sep != " " or not value or value != value.strip():
        return False
    return hmac.compare_digest(value.encode(), expected.encode())

def record(action, issue, status, request_id, actor="authenticated-client"):
    """Write only sanitized metadata. Never log secrets or request bodies."""
    event = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "operation_id": request_id,
        "action": action,
        "issue": issue,
        "status": status,
        "actor": actor,
    }
    try:
        AUDIT_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(event, separators=(",", ":")) + "\n")
        AUDIT_PATH.chmod(0o600)
    except OSError:
        # Do not silently accept privileged actions if audit storage is unavailable.
        raise RuntimeError("Audit storage unavailable")

def listed_projects():
    """Only configured, validated project profiles; never auto-discover scripts."""
    result = {}
    if not PROJECTS_DIR.is_dir():
        return result
    for path in sorted(PROJECTS_DIR.glob("*.json")):
        if path.is_symlink() or not PROJECT_ID.fullmatch(path.stem):
            continue
        try:
            profile = load_profile(path)
        except (PreflightError, OSError, ValueError, TypeError):
            continue
        if profile["id"] == path.stem:
            result[profile["id"]] = {
                "id": profile["id"],
                "product": profile["product"],
                "preflight": "supported",
                "preparation": "local_only_no_publish",
                "publication": "disabled",
            }
    return result


def project_workspace(project_id):
    """Resolve a pre-approved project and immutable workspace paths."""
    if not isinstance(project_id, str) or not PROJECT_ID.fullmatch(project_id):
        raise PreflightError("Invalid project")
    path = PROJECTS_DIR / (project_id + ".json")
    if path.is_symlink() or not path.is_file():
        raise PreflightError("Project not configured")
    profile = load_profile(path)
    if profile["id"] != project_id:
        raise PreflightError("Profile identity mismatch")
    root = WORKSPACES_DIR.resolve()
    workspace = root / project_id
    if workspace.is_symlink() or not workspace.is_dir():
        raise PreflightError("Project workspace not configured")
    source = workspace / "source"
    distribution = workspace / "distribution"
    if (not source.is_dir() or not distribution.is_dir()
            or source.is_symlink() or distribution.is_symlink()
            or source.resolve() != source.absolute()
            or distribution.resolve() != distribution.absolute()):
        raise PreflightError("Workspace checkouts unavailable or unsafe")
    return profile, source, distribution


def preflight_project(project_id, expected_sha):
    """Read-only preflight; never mutate the workspace or remote Git."""
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise PreflightError("Invalid source SHA")
    profile, source, distribution = project_workspace(project_id)
    return evaluate(source, distribution, expected_sha, profile=profile)


def prepare_project(project_id, expected_sha, operation_id):
    """Export into an isolated local checkout. No Git push or release publication."""
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise PreflightError("Invalid source SHA")
    profile, source, distribution = project_workspace(project_id)
    preflight = evaluate(source, distribution, expected_sha, profile=profile)
    if not preflight["eligible_for_preparation"]:
        return {"eligible": False, "errors": preflight["errors"]}
    # Server generates destination: client cannot select arbitrary filesystem path.
    destination = PREPARATIONS_DIR.absolute()
    if destination.resolve() != destination or destination.is_symlink():
        raise PreflightError("Unsafe preparations directory")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = destination / (project_id + "-" + expected_sha[:12] + "-" + operation_id)
    prepared = prepare(source, distribution, preflight, output, profile=profile)
    return {"eligible": True, "state": prepared["state"],
            "changed_files": prepared["changed_files"],
            "source_sha": expected_sha, "published": False}

def prepare_project_declarative(project_id, expected_sha, operation_id):
    """Prepare a local artifact from trusted mappings. Never execute exporter code."""
    # Use the same policy gate as /api/prepare. Do not accept mappings in HTTP.
    report = preflight_project(project_id, expected_sha)
    if not report["eligible_for_preparation"]:
        return {"eligible": False, "errors": report["errors"]}
    profile, source, distribution = project_workspace(project_id)
    mapping = profile.get("declarative_mapping")
    if "declarative_rules" in profile:
        rules = profile["declarative_rules"]
        mapping = expand_trusted_rules(
            source, expected_sha,
            destination_prefix=profile["distribution_prefix"],
            required=rules["required"], optional=rules["optional"],
            include_prefixes=rules["include_prefixes"],
            include_suffixes=rules["include_suffixes"])
        mapping = extend_approved_mapping(
            source, expected_sha, mapping,
            conditional_groups=rules.get("conditional_groups", []),
            shared_optional=rules.get("shared_optional", {}),
            allowed_shared_paths=profile["allowed_shared_paths"],
            distribution_prefix=profile["distribution_prefix"])
    if not isinstance(mapping, dict) or not mapping:
        raise DeclarativeExportError("approved_declarative_mapping_unavailable")
    sources = set(mapping.values())
    if (profile["package_json_path"] not in sources
            or profile["manifest_path"] not in sources):
        raise DeclarativeExportError("package_version_evidence_missing")
    pinned_exporter = trusted_git(
        source, "rev-parse", expected_sha + ":" + profile["exporter_path"])
    if pinned_exporter != profile["exporter_git_blob_sha"]:
        raise DeclarativeExportError("declarative_rules_not_approved_for_exporter")
    ci_contract = profile.get("declarative_ci")
    if ci_contract is not None:
        # The canonical exporter requires a pinned CI patch and either an
        # applicable patch or an already-compatible trusted workflow.
        # We support ONLY the already-compatible case, otherwise fail closed.
        trusted_git(source, "rev-parse",
                    expected_sha + ":" + ci_contract["patch_source"])
        workflow = distribution / ci_contract["workflow_path"]
        if (not workflow.is_file() or workflow.is_symlink()
                or workflow.resolve() != workflow.absolute()):
            raise DeclarativeExportError("unsafe_ci_workflow")
        content = workflow.read_text(encoding="utf-8")
        if not all(marker in content for marker in ci_contract["compatible_markers"]):
            raise DeclarativeExportError("ci_patch_requires_separate_review")
    destination = PREPARATIONS_DIR.absolute()
    if destination.is_symlink() or destination.resolve() != destination:
        raise DeclarativeExportError("unsafe_preparations_directory")
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    output = destination / (project_id + "-" + expected_sha[:12] + "-" + operation_id)
    manifest = prepare_declarative(
        source, expected_sha, output, mapping,
        expected_version=report["candidate_version"], project=project_id)
    release_provenance = write_distribution_provenance(
        output, manifest, source_repository=profile["source_repo"],
        distribution_prefix=profile["distribution_prefix"],
        provenance_path=profile["provenance_path"],
        ci_patch_source=(ci_contract["patch_source"] if ci_contract else None),
        allowed_shared_paths=profile["allowed_shared_paths"])
    return {"eligible": True, "state": "PREPARED_NOT_PUBLISHED",
            "files": len(manifest["files"]), "source_sha": expected_sha,
            "provenance_files": len(release_provenance["files"]),
            "published": False, "method": "declarative_no_script"}


class WorkerUnavailable(Exception):
    """Worker failed or returned untrusted data; no privileged fallback."""
    pass


def run_controlled_worker(task, project=None, expected_sha=None):
    """Invoke one fixed read-only task with sanitized environment and deadline."""
    script = Path(__file__).with_name("controlled_worker.py")
    argv = [sys.executable, "-I", str(script), "--task", task]
    if project is not None:
        argv.extend(["--project", project])
    if expected_sha is not None:
        argv.extend(["--sha", expected_sha])
    child_env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LC_ALL": "C",
                 "GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                 "GIT_CONFIG_GLOBAL": os.devnull,
                 "RUNNER_PROJECTS_DIR": str(PROJECTS_DIR),
                 "RUNNER_WORKSPACES_DIR": str(WORKSPACES_DIR)}
    try:
        p = subprocess.Popen(argv, cwd=str(script.parent), env=child_env,
                             stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, start_new_session=True)
        try:
            output, _ = p.communicate(timeout=50)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(p.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            p.communicate()
            raise WorkerUnavailable("worker_timeout")
        if p.returncode != 0 or len(output) > 16 * 1024:
            raise WorkerUnavailable("worker_failed")
        parsed = json.loads(output)
        if (not isinstance(parsed, dict) or parsed.get("worker") != "factory-runner-controlled"
                or parsed.get("task") != task or parsed.get("ok") is not True
                or not isinstance(parsed.get("result"), dict)):
            raise WorkerUnavailable("invalid_worker_response")
        return parsed["result"]
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        raise WorkerUnavailable("worker_unavailable") from exc


class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self, status, payload):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return authenticated(self.headers.get("Authorization", ""))

    def do_GET(self):
        if self.path not in ("/", "/api/status", "/api/projects"):
            return self.respond(404, {"error": "not_found"})
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path == "/api/projects":
            return self.respond(200, {"projects": list(listed_projects().values())})
        return self.respond(200, {
            "service": "factory-runner",
            "status": "read_only_preflight",
            "preflight": "available_with_preprovisioned_workspaces",
            "publication": "disabled",
            "autonomous_changes": "disabled",
            "controlled_worker": "read_only_only"
        })

    def do_POST(self):
        if self.path not in OPERATIONS and self.path not in ("/api/preflight", "/api/prepare", "/api/prepare-declarative", "/api/worker/run"):
            return self.respond(404, {"error": "not_found"})
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        raw_length = self.headers.get("Content-Length", "")
        if not 1 <= len(raw_length) <= 5 or not raw_length.isascii() or not raw_length.isdecimal():
            return self.respond(400, {"error": "invalid_length"})
        length = int(raw_length)
        if not 0 < length <= MAX_BODY:
            return self.respond(413, {"error": "invalid_size"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.respond(400, {"error": "invalid_json"})
        if not isinstance(body, dict):
            return self.respond(400, {"error": "invalid_payload"})
        if self.path == "/api/worker/run":
            task = body.get("task")
            project = body.get("project")
            source_sha = body.get("expected_source_sha")
            if task == "diagnose":
                valid = set(body) == {"task"}
            elif task == "profile":
                valid = (set(body) == {"task", "project"}
                         and isinstance(project, str) and bool(PROJECT_ID.fullmatch(project)))
            elif task == "preflight":
                valid = (set(body) == {"task", "project", "expected_source_sha"}
                         and isinstance(project, str) and bool(PROJECT_ID.fullmatch(project))
                         and isinstance(source_sha, str) and bool(SHA.fullmatch(source_sha)))
            else:
                valid = False
            if not valid:
                return self.respond(400, {"error": "invalid_worker_task"})
            if not LOCK.acquire(blocking=False):
                return self.respond(409, {"error": "busy"})
            operation_id = str(uuid.uuid4())
            try:
                record("/api/worker/run:" + task, None, "requested", operation_id)
                try:
                    result = run_controlled_worker(task, project, source_sha)
                except WorkerUnavailable:
                    record("/api/worker/run:" + task, None, "blocked_worker", operation_id)
                    return self.respond(503, {"error": "worker_unavailable",
                                              "operation_id": operation_id})
                record("/api/worker/run:" + task, None, "completed_read_only", operation_id)
                return self.respond(200, {"operation_id": operation_id,
                                          "result": result, "published": False})
            except RuntimeError:
                return self.respond(503, {"error": "audit_unavailable"})
            finally:
                LOCK.release()

        if self.path in ("/api/preflight", "/api/prepare", "/api/prepare-declarative"):
            if set(body) != {"project", "expected_source_sha"}:
                return self.respond(400, {"error": "invalid_payload"})
            project = body["project"]
            source_sha = body["expected_source_sha"]
            if (not isinstance(project, str) or not PROJECT_ID.fullmatch(project)
                    or not isinstance(source_sha, str) or not SHA.fullmatch(source_sha)):
                return self.respond(400, {"error": "invalid_project_or_sha"})
            if not LOCK.acquire(blocking=False):
                return self.respond(409, {"error": "busy"})
            operation_id = str(uuid.uuid4())
            try:
                action = self.path
                record(action, None, "requested", operation_id)
                try:
                    if action == "/api/preflight":
                        result = preflight_project(project, source_sha)
                    elif action == "/api/prepare":
                        result = prepare_project(project, source_sha, operation_id)
                    else:
                        result = prepare_project_declarative(project, source_sha, operation_id)
                except (PreflightError, SandboxUnavailable, DeclarativeExportError, OSError, subprocess.TimeoutExpired, ValueError, TypeError):
                    record(action, None, "blocked_workspace_or_git", operation_id)
                    return self.respond(503, {"error": "workspace_or_export_unavailable",
                                              "operation_id": operation_id})
                if action in ("/api/prepare", "/api/prepare-declarative") and not result["eligible"]:
                    record(action, None, "blocked_policy", operation_id)
                    return self.respond(409, {"error": "package_policy_blocked",
                                              "operation_id": operation_id,
                                              "details": result["errors"]})
                record(action, None, "completed_preparation" if action in ("/api/prepare", "/api/prepare-declarative")
                       else "completed_read_only", operation_id)
                return self.respond(200, {"operation_id": operation_id, "result": result})
            except RuntimeError:
                return self.respond(503, {"error": "audit_unavailable"})
            finally:
                LOCK.release()

        issue = body.get("issue")
        if type(issue) is not int or not ISSUE.fullmatch(str(issue)):
            return self.respond(400, {"error": "invalid_issue"})
        request_id = str(uuid.uuid4())
        if not LOCK.acquire(blocking=False):
            return self.respond(409, {"error": "busy"})
        try:
            # A bearer token authenticates a client; it is NOT owner approval.
            # Until a canonical per-repo/issue/SHA authorization gate is integrated,
            # do not call any path that writes Git, executes model code or publishes.
            record(self.path, issue, "blocked_authorization", request_id)
            return self.respond(403, {
                "error": "owner_approval_required",
                "operation_id": request_id
            })
        except RuntimeError:
            return self.respond(503, {"error": "audit_unavailable"})
        finally:
            LOCK.release()

    def log_message(self, fmt, *args):
        # Suppress request headers, query strings, and PII from default logs.
        return

if __name__ == "__main__":
    if len(os.environ.get("RUNNER_AUTH_TOKEN", "")) < 32:
        raise SystemExit("RUNNER_AUTH_TOKEN required; refusing to start")
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    print("[API] READY: loopback-only; authenticated; worker read-only; publication disabled", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
