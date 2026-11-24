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
import fcntl
from publication_workflow import capabilities as publication_capabilities
import stat
from contextlib import contextmanager
from pathlib import Path

from rc_fastlane import PreflightError, evaluate, load_profile, prepare, git as trusted_git
from sandbox_export import SandboxUnavailable
from declarative_export import (DeclarativeExportError, prepare_declarative,
                                expand_trusted_rules, extend_approved_mapping,
                                write_distribution_provenance)
from release_receipt import (seal_receipt, verify_receipt, digest,
                             ReceiptError)
from publisher_permissions import share_readonly
from publisher_ipc import PublisherRPCClient
from publication_contract import PublicationError

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
        if AUDIT_PATH.is_symlink() or AUDIT_PATH.parent.resolve() != AUDIT_PATH.parent.absolute():
            raise OSError("Unsafe audit path")
        fd = os.open(AUDIT_PATH, os.O_WRONLY | os.O_APPEND | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            os.close(fd)
            raise OSError("Unsafe audit file")
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as log:
            log.write(json.dumps(event, separators=(",", ":")) + "\n")
        AUDIT_PATH.chmod(0o600)
    except OSError:
        # Do not silently accept privileged actions if audit storage is unavailable.
        raise RuntimeError("Audit storage unavailable")

def recent_operations():
    """Return bounded, sanitized audit statuses; no paths, tokens or bodies."""
    if AUDIT_PATH.is_symlink():
        raise RuntimeError("Unsafe audit log")
    if not AUDIT_PATH.exists():
        return []
    try:
        if not AUDIT_PATH.is_file():
            raise RuntimeError("Unsafe audit log")
        with AUDIT_PATH.open("rb") as log:
            log.seek(0, os.SEEK_END)
            length = log.tell()
            window = min(length, 131072)
            log.seek(length - window)
            raw = log.read(window)
        if length > window:
            # First entry may be partial: discard it.
            raw = raw.partition(b"\n")[2]
        lines = raw.splitlines()[-256:]
        safe_actions = OPERATIONS | {
            "/api/preflight", "/api/prepare", "/api/prepare-declarative",
            "/api/release-plan", "/api/publication-preview",
            "/api/publication-propose", "/api/publish",
            "/api/publication-reconcile",
            "/api/worker/run:diagnose", "/api/worker/run:profile",
            "/api/worker/run:preflight"
        }
        safe_states = {
            "requested", "blocked_authorization", "blocked_policy",
            "blocked_workspace_or_git", "blocked_worker", "completed_read_only",
            "completed_preparation", "completed_workspace_sync",
            "blocked_workspace_sync", "completed_publication",
            "published_verified_pending_homologation", "completed_reconciliation"
        }
        found = {}
        for line in reversed(lines):
            try:
                event = json.loads(line)
            except (UnicodeError, ValueError):
                continue
            if not isinstance(event, dict):
                continue
            operation_id = event.get("operation_id")
            action = event.get("action")
            state = event.get("status")
            when = event.get("time")
            if (not isinstance(operation_id, str)
                    or not re.fullmatch(r"[0-9a-f-]{36}", operation_id)
                    or not isinstance(action, str)
                    or not isinstance(state, str)
                    or not (action in safe_actions
                            or (action.startswith("workspace_sync:")
                                and bool(PROJECT_ID.fullmatch(action.split(":", 1)[1]))))
                    or state not in safe_states
                    or not isinstance(when, str)
                    or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ", when)):
                continue
            if operation_id not in found:
                found[operation_id] = {
                    "operation_id": operation_id, "action": action,
                    "status": state, "time": when
                }
            if len(found) >= 20:
                break
        return list(found.values())
    except OSError as exc:
        raise RuntimeError("Audit log unreadable") from exc


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
            mode = profile.get("mode")
            readonly = mode == "sync_only"
            artesao = mode == "artesao_package"
            result[profile["id"]] = {
                "id": profile["id"],
                "product": profile["product"],
                "preflight": ("verified_dual_distribution_plan" if artesao
                              else "sync_only_no_release_gate" if readonly
                              else "supported"),
                "preparation": ("blocked_pending_external_validation" if artesao
                                else "disabled_sync_only" if readonly
                                else "local_only_no_publish"),
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
    if profile.get("mode") == "sync_only":
        raise PreflightError("Sync-only project has no approved release adapter")
    if profile.get("mode") == "artesao_package":
        from artesao_adapter import evaluate_artesao
        return evaluate_artesao(source, distribution, expected_sha, profile=profile)
    return evaluate(source, distribution, expected_sha, profile=profile)


def unique_json_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_key")
        result[key] = value
    return result


def publisher_request(action, **body):
    import pwd
    client = PublisherRPCClient(
        "/data/factory-runner-authority/publisher-ipc/publisher.sock",
        pwd.getpwnam("publisher").pw_uid)
    return client.request(action, **body)


def release_plan(project_id, expected_sha):
    """Read-only publication readiness; bearer authentication is NOT approval.

    Only a trusted project profile and pinned workspace may inform this
    report. Never return credentials, checkout paths or arbitrary metadata.
    """
    report = preflight_project(project_id, expected_sha)
    if not isinstance(report, dict):
        raise PreflightError("Invalid preflight result")
    raw_errors = report.get("errors")
    if not isinstance(raw_errors, list) or any(
            not isinstance(code, str)
            or not re.fullmatch(r"[A-Z][A-Z0-9_]{0,79}", code)
            for code in raw_errors):
        raise PreflightError("Invalid policy evidence")
    eligible = report.get("eligible_for_preparation")
    if type(eligible) is not bool:
        raise PreflightError("Unverified preparation eligibility")
    return {
        "project": project_id,
        "source_sha": expected_sha,
        "preparation": "eligible_for_separate_preparation" if eligible
                       else "blocked_by_project_policy",
        "policy_errors": sorted(set(raw_errors)),
        "publication": "disabled_pending_independent_authorization",
        "published": False,
        "requirements": [
            "verified_project_package_and_version",
            "immutable_source_and_distribution_shas",
            "tests_and_provenance_for_exact_artifact",
            "independent_owner_approval_for_scope_and_destination",
            "safe_publisher_and_idempotent_remote_verification"
        ]
    }


def release_plan_health(project_id, expected_sha):
    """Read-only verification against the existing trusted workspace.

    Prints only constant status codes and an approved project ID. It does not
    assert the HTTP authentication path, grant publishing, or expose policy data.
    """
    try:
        plan = release_plan(project_id, expected_sha)
        if (plan["published"] is not False
                or plan["publication"] != "disabled_pending_independent_authorization"):
            raise PreflightError("Unsafe publication plan")
        print("[RELEASE-PLAN] PASS: project=" + project_id
              + " preparation=" + plan["preparation"]
              + " publication=disabled", flush=True)
        return True
    except (PreflightError, OSError, ValueError, TypeError):
        print("[RELEASE-PLAN] BLOCKED: project=" + project_id
              + " preflight_unavailable", flush=True)
        return False


def prepare_project(project_id, expected_sha, operation_id):
    """Export into an isolated local checkout. No Git push or release publication."""
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise PreflightError("Invalid source SHA")
    profile, source, distribution = project_workspace(project_id)
    if profile.get("mode") == "sync_only":
        raise PreflightError("Sync-only project has no approved release adapter")
    if profile.get("mode") == "artesao_package":
        from artesao_adapter import evaluate_artesao
        report = evaluate_artesao(source, distribution, expected_sha, profile=profile)
        # This runner does not possess the validated release receipt or the
        # architecture-specific build outputs. Do not fake package production.
        return {"eligible": False, "state": "BLOCKED_PENDING_EXTERNAL_VALIDATION",
                "project": project_id, "source_sha": expected_sha,
                "errors": report["errors"], "published": False}
    # An approved deterministic recipe requires no source-script execution.
    # Keep the original Bubblewrap path strictly fail-closed for other profiles.
    if "declarative_rules" in profile or "declarative_mapping" in profile:
        return prepare_project_declarative(project_id, expected_sha, operation_id)
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

@contextmanager
def preparation_lock(destination):
    """Serialize API and console writers across processes after policy gates."""
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = destination.parent / (destination.name + '.lock')
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_nlink != 1:
            raise ReceiptError('unsafe_preparation_lock')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ReceiptError('preparation_busy') from exc
        yield
    finally:
        os.close(fd)


def prepare_project_declarative(project_id, expected_sha, operation_id):
    """Prepare a local artifact from trusted mappings. Never execute exporter code."""
    # Use the same policy gate as /api/prepare. Do not accept mappings in HTTP.
    profile, source, distribution = project_workspace(project_id)
    if profile.get("mode") == "artesao_package":
        raise PreflightError("Artesao adapter cannot use Avisaqui declarative exporter")
    report = preflight_project(project_id, expected_sha)
    if not report["eligible_for_preparation"]:
        return {"eligible": False, "errors": report["errors"]}
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
        # Inspect ONLY the pinned public commit, never a mutable/uncommitted
        # checkout file. Otherwise the CI gate could be bypassed by a dirty tree.
        content = trusted_git(
            distribution, "show", report["public_main_sha"] + ":" +
            ci_contract["workflow_path"])
        if not all(marker in content for marker in ci_contract["compatible_markers"]):
            raise DeclarativeExportError("ci_patch_requires_separate_review")
    destination = PREPARATIONS_DIR.absolute()
    if destination.is_symlink() or destination.resolve() != destination:
        raise DeclarativeExportError("unsafe_preparations_directory")
    with preparation_lock(destination):
        return _store_declarative(destination, project_id, expected_sha, profile,
                                  source, report, mapping, ci_contract)


def _store_declarative(destination, project_id, expected_sha, profile,
                       source, report, mapping, ci_contract):
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    # Server-owned identity covers source, destination snapshot and trusted recipe.
    # A retry verifies existing bytes rather than creating a second candidate.
    identity = digest({"source": expected_sha, "distribution": report["public_main_sha"],
                       "profile": profile})
    output = destination / (project_id + "-" + identity)
    if output.exists() or output.is_symlink():
        receipt = verify_receipt(output)
        share_readonly(output)
        if (receipt["source_sha"] != expected_sha
                or receipt["profile_sha256"] != digest(profile)
                or receipt["expected_distribution_sha"] != report["public_main_sha"]):
            raise ReceiptError("cached_preparation_mismatch")
        return {"eligible": True, "state": "PREPARED_NOT_PUBLISHED",
                "source_sha": expected_sha, "published": False,
                "receipt_sha256": digest(receipt), "idempotent": True,
                "publication": "disabled", "tests": receipt["tests"]["status"]}
    # Publish the local directory atomically only after sealing it. Failed
    # staging directories are retained for inspection and never reused.
    staging = destination / (output.name + '.incomplete-' + uuid.uuid4().hex)
    manifest = prepare_declarative(
        source, expected_sha, staging, mapping,
        expected_version=report["candidate_version"], project=project_id)
    release_provenance = write_distribution_provenance(
        staging, manifest, source_repository=profile["source_repo"],
        distribution_prefix=profile["distribution_prefix"],
        provenance_path=profile["provenance_path"],
        ci_patch_source=(ci_contract["patch_source"] if ci_contract else None),
        allowed_shared_paths=profile["allowed_shared_paths"])
    receipt = seal_receipt(staging, profile=profile, report=report)
    share_readonly(staging)
    staging.rename(output)
    return {"eligible": True, "state": "PREPARED_NOT_PUBLISHED",
            "files": len(manifest["files"]), "source_sha": expected_sha,
            "provenance_files": len(release_provenance["files"]),
            "published": False, "method": "declarative_no_script",
            "receipt_sha256": digest(receipt), "idempotent": False,
            "publication": "disabled", "tests": receipt["tests"]["status"]}


def run_workspace_sync(project, token, auto_prepare=False):
    """One trusted startup synchronization with audit and serialization.

    Invoked on a background thread while the API is available. The caller
    already holds the global operation lock. No URLs, Git parameters or
    credentials are received over the HTTP API.
    """
    from workspace_sync import SyncError, synchronize
    operation_id = str(uuid.uuid4())
    try:
        record("workspace_sync:" + project, None, "requested", operation_id,
               actor="trusted_startup")
        result = synchronize(project, token=token, projects_dir=PROJECTS_DIR,
                             workspaces_dir=WORKSPACES_DIR)
        print("[WORKSPACE] " + result["state"] + ": project=" + project
              + " source=" + result["source_sha"][:12]
              + " public=" + result["public_sha"][:12]
              + (" remote_public=" + result["remote_public_sha"][:12]
                 if result.get("remote_public_sha") else ""), flush=True)
        record("workspace_sync:" + project, None, "completed_workspace_sync",
               operation_id, actor="trusted_startup")
        readonly = "SYNC_ONLY_NO_PREPARATION" in result["errors"]
        if readonly:
            print("[WORKSPACE] SYNC_ONLY: project=" + project
                  + " package_preparation_disabled", flush=True)
            record("workspace_sync:" + project, None, "completed_read_only",
                   operation_id, actor="trusted_startup")
        elif result["eligible"] is False:
            print("[WORKSPACE] POLICY_BLOCKED: " + ",".join(result["errors"]), flush=True)
            record("workspace_sync:" + project, None, "blocked_policy",
                   operation_id, actor="trusted_startup")
        if not readonly:
            # Exercise the real read-only plan against the verified workspace.
            # A blocked package is a valid plan, not authorization to publish.
            release_plan_health(project, result["source_sha"])
        if auto_prepare:
            if readonly:
                print("[WORKSPACE] PREPARE_BLOCKED_BY_PROFILE: project=" + project, flush=True)
            else:
                report = preflight_project(project, result["source_sha"])
                if not report["eligible_for_preparation"]:
                    print("[WORKSPACE] PREPARE_BLOCKED_BY_POLICY: " +
                          ",".join(report["errors"]), flush=True)
                else:
                    prepared = prepare_project(project, result["source_sha"], operation_id)
                    if not prepared["eligible"] or prepared["published"]:
                        raise RuntimeError("unexpected_prepare_result")
                    record("workspace_sync:" + project, None, "completed_preparation",
                           operation_id, actor="trusted_startup")
                    print("[WORKSPACE] PREPARED_NOT_PUBLISHED: project=" + project
                          + " source=" + result["source_sha"][:12], flush=True)
        return result
    except (SyncError, PreflightError, DeclarativeExportError, ReceiptError, SandboxUnavailable,
            OSError, ValueError, TypeError, subprocess.TimeoutExpired, RuntimeError) as exc:
        # Report only constant error codes; no URL, token, request payload or
        # subprocess stderr. Audit failure is fatal to this operation.
        code = str(exc) if isinstance(exc, (SyncError, DeclarativeExportError)) else type(exc).__name__
        print("[WORKSPACE] BLOCKED: " + code[:80], flush=True)
        try:
            record("workspace_sync:" + project, None, "blocked_workspace_sync",
                   operation_id, actor="trusted_startup")
        except RuntimeError:
            pass
        return None


MAX_SYNC_PROJECTS = 32


def workspace_audit_health(projects):
    """Verify only the sanitized audit listing after the sync batch.

    This is an internal diagnostic, not proof of the HTTP authentication gate.
    Never log operation identifiers, paths, source SHAs or credential values.
    """
    try:
        recent = recent_operations()
        observed = {event["action"].split(":", 1)[1]
                    for event in recent
                    if event["action"].startswith("workspace_sync:")}
        missing = sum(1 for project in projects if project not in observed)
        if missing:
            print("[OPERATIONS] BLOCKED: workspace_audit_entries_missing count="
                  + str(missing), flush=True)
            return False
        print("[OPERATIONS] PASS: sanitized_workspace_audit projects="
              + str(len(projects)), flush=True)
        return True
    except RuntimeError:
        print("[OPERATIONS] BLOCKED: audit_unavailable", flush=True)
        return False


def launch_workspace_sync():
    """Opt-in multi-project sync of every *approved* on-image project profile.

    Adding a project requires a separately approved, versioned profile; HTTP
    clients and HA options cannot inject repositories, branches, or file paths.
    Sync is sequential and serializes with preparation through the API LOCK.
    Failure of one project does not prevent the next approved project's sync.
    """
    enabled = os.environ.pop("RUNNER_WORKSPACE_SYNC_ENABLED", "false") == "true"
    # The RC7 single-project option is intentionally ignored (migration to
    # all approved profiles); it cannot silently enable remote access.
    os.environ.pop("RUNNER_WORKSPACE_SYNC_PROJECT", None)
    # Clear secret from process environment even when sync is disabled.
    token = os.environ.pop("RUNNER_GITHUB_READ_TOKEN", "")
    auto = os.environ.pop("RUNNER_WORKSPACE_AUTO_PREPARE", "false") == "true"
    if not enabled:
        return None
    projects = tuple(sorted(listed_projects()))
    if not projects:
        print("[WORKSPACE] BLOCKED: no_approved_projects", flush=True)
        return None
    if len(projects) > MAX_SYNC_PROJECTS:
        print("[WORKSPACE] BLOCKED: approved_project_limit", flush=True)
        return None
    print("[WORKSPACE] START: approved_projects=" + str(len(projects)), flush=True)

    def work():
        for project in projects:
            with LOCK:
                # This function contains each project's audit, errors, policy
                # gates and credential scrubbing. No single project aborts all.
                try:
                    run_workspace_sync(project, token, auto_prepare=auto)
                except Exception:
                    # Unexpected errors are sanitized; never show token/data.
                    print("[WORKSPACE] BLOCKED: unexpected_sync_error", flush=True)
        print("[WORKSPACE] FINISHED: approved_projects=" + str(len(projects)), flush=True)
        workspace_audit_health(projects)

    thread = threading.Thread(target=work, name="workspace-sync-all", daemon=True)
    thread.start()
    return thread


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
        if self.path not in ("/", "/api/status", "/api/projects", "/api/operations", "/api/publication-status"):
            return self.respond(404, {"error": "not_found"})
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        if self.path == "/api/publication-status":
            try:
                return self.respond(200, publisher_request("status"))
            except (PublicationError, KeyError, OSError):
                return self.respond(200, {**publication_capabilities(),
                                          "ipc": "unavailable", "publication": "disabled"})
        if self.path == "/api/projects":
            return self.respond(200, {"projects": list(listed_projects().values())})
        if self.path == "/api/operations":
            try:
                return self.respond(200, {"operations": recent_operations(),
                                          "source": "sanitized_audit"})
            except RuntimeError:
                return self.respond(503, {"error": "audit_unavailable"})
        return self.respond(200, {
            "service": "factory-runner",
            "status": "read_only_preflight",
            "preflight": "available_with_preprovisioned_workspaces",
            "publication": "disabled",
            "autonomous_changes": "disabled",
            "controlled_worker": "read_only_only"
        })

    def do_POST(self):
        publication_routes = {
            "/api/publication-preview": "preview",
            "/api/publication-propose": "propose",
            "/api/publish": "publish",
            "/api/publication-reconcile": "reconcile",
        }
        if self.path not in OPERATIONS and self.path not in ("/api/preflight", "/api/prepare", "/api/prepare-declarative", "/api/release-plan", "/api/worker/run") and self.path not in publication_routes:
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
            body = json.loads(self.rfile.read(length).decode("utf-8"), object_pairs_hook=unique_json_object)
        except (UnicodeDecodeError, ValueError):
            return self.respond(400, {"error": "invalid_json"})
        if not isinstance(body, dict):
            return self.respond(400, {"error": "invalid_payload"})
        if self.path in publication_routes:
            action = publication_routes[self.path]
            expected = {
                "preview": {"project", "issue", "receipt_digest"},
                "propose": {"project", "issue", "receipt_digest"},
                "publish": {"project", "issue", "receipt_digest", "proposal_id"},
                "reconcile": {"project", "nonce"},
            }[action]
            if set(body) != expected:
                return self.respond(400, {"error": "invalid_publication_payload"})
            project = body.get("project")
            if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
                return self.respond(400, {"error": "invalid_project"})
            if action in ("preview", "propose", "publish"):
                issue = body.get("issue")
                receipt_digest = body.get("receipt_digest")
                if (type(issue) is not int or not ISSUE.fullmatch(str(issue))
                        or not isinstance(receipt_digest, str)
                        or not re.fullmatch(r"[0-9a-f]{64}", receipt_digest)):
                    return self.respond(400, {"error": "invalid_publication_binding"})
            if action == "publish" and (
                    not isinstance(body.get("proposal_id"), str)
                    or not re.fullmatch(r"[a-f0-9]{32}", body["proposal_id"])):
                return self.respond(400, {"error": "invalid_proposal"})
            if action == "reconcile" and (
                    not isinstance(body.get("nonce"), str)
                    or not re.fullmatch(r"[a-f0-9]{32}", body["nonce"])):
                return self.respond(400, {"error": "invalid_nonce"})
            operation_id = str(uuid.uuid4())
            try:
                record(self.path, body.get("issue"), "requested", operation_id)
                result = publisher_request(action, **body)
                state = result.get("state") if isinstance(result, dict) else None
                audit_state = ("published_verified_pending_homologation"
                               if state == "PUBLISHED_VERIFIED_PENDING_HOMOLOGATION"
                               else "completed_reconciliation" if action == "reconcile"
                               else "completed_publication" if action == "publish"
                               else "completed_read_only")
                record(self.path, body.get("issue"), audit_state, operation_id)
                return self.respond(200, {"operation_id": operation_id, "result": result})
            except PublicationError as exc:
                try:
                    record(self.path, body.get("issue"), "blocked_authorization", operation_id)
                except RuntimeError:
                    return self.respond(503, {"error": "audit_unavailable"})
                if str(exc) in ("publisher_ipc_unavailable", "publisher_peer_mismatch"):
                    return self.respond(503, {"error": "publisher_unavailable", "operation_id": operation_id})
                return self.respond(409, {"error": "publication_blocked", "operation_id": operation_id})
            except RuntimeError:
                return self.respond(503, {"error": "audit_unavailable"})
            except (OSError, KeyError):
                return self.respond(503, {"error": "publisher_unavailable", "operation_id": operation_id})

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

        if self.path in ("/api/preflight", "/api/prepare", "/api/prepare-declarative", "/api/release-plan"):
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
                    elif action == "/api/release-plan":
                        result = release_plan(project, source_sha)
                    elif action == "/api/prepare":
                        result = prepare_project(project, source_sha, operation_id)
                    else:
                        result = prepare_project_declarative(project, source_sha, operation_id)
                except (PreflightError, SandboxUnavailable, DeclarativeExportError, ReceiptError, OSError, subprocess.TimeoutExpired, ValueError, TypeError):
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
    launch_workspace_sync()
    print("[API] READY: loopback-only; authenticated; worker read-only; publication disabled", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
