#!/usr/bin/env python3
"""One-shot, non-root local E2E validation of the real Factory Runner API.

Creates only synthetic Git repositories in a private /tmp directory. Binds a
short-lived HTTP server to 127.0.0.1:0 INSIDE the add-on; never listens publicly,
contacts a remote, modifies real workspaces, invokes project scripts or publishes.
An ephemeral bearer token exists only inside this disposable child process.
"""
from __future__ import annotations

import hashlib
import http.client
from http.server import ThreadingHTTPServer
import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import tempfile
import threading

# Python -I deliberately ignores script folder; import trusted installed code.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import server as runner

MAX_SECONDS = 75


class ProbeFailed(Exception):
    pass


def _git(repository: Path, *args: str) -> str:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        proc = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-C", str(repository), *args],
            env=env, stdin=subprocess.DEVNULL, capture_output=True,
            timeout=12, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise ProbeFailed("fixture_git_unavailable") from exc
    if proc.returncode:
        raise ProbeFailed("fixture_git_failed")
    return proc.stdout.decode("utf-8", errors="strict").strip()


def _put(repository: Path, path: str, value: str) -> None:
    dest = repository / path
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(value, encoding="utf-8")


def _request(port: int, token: str, path: str, *, source_sha: str,
             authorized: bool = True, payload: dict | None = None) -> tuple[int, dict]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=25)
    headers = {"Content-Type": "application/json"}
    if authorized:
        headers["Authorization"] = "Bearer " + token
    data = payload if payload is not None else {
        "project": "laboratorio", "expected_source_sha": source_sha}
    try:
        c.request("POST", path, body=json.dumps(data), headers=headers)
        response = c.getresponse()
        code, body = response.status, json.loads(response.read(65536))
    except (OSError, ValueError) as exc:
        raise ProbeFailed("fixture_http_failed") from exc
    finally:
        c.close()
    # Read the audit after Handler's finally has released the global lock.
    if not runner.LOCK.acquire(timeout=10):
        raise ProbeFailed("fixture_http_lock_timeout")
    runner.LOCK.release()
    return code, body


def _require(condition: bool, code: str) -> None:
    if not condition:
        raise ProbeFailed(code)


def _execute() -> dict:
    _require(os.geteuid() != 0, "requires_non_root")
    with tempfile.TemporaryDirectory(prefix="factory-e2e-", dir="/tmp") as tmp:
        root = Path(tmp)
        workspace = root / "workspaces" / "laboratorio"
        source, distribution = workspace / "source", workspace / "distribution"
        for checkout in (source, distribution):
            checkout.mkdir(parents=True, mode=0o700)
            _git(checkout, "init", "-q", "-b", "main")
        project = "Laboratorio"
        version = "1.2.3-rc.2"
        release_policy = {"schema_version": 1, "product": project,
            "active_package": {"id": "SYNTHETIC-ONLY", "status": "open",
                "candidate_version": version,
                "branches": {"fixture/source": "release/rc"}}}
        _put(source, "policy.json", json.dumps(release_policy) + "\n")
        _put(source, "package.json", json.dumps({"version": version}) + "\n")
        _put(source, "config.yaml", 'version: "' + version + '"\n')
        _put(source, "src/payload.txt", "synthetic payload (not an application)\n")
        _put(source, "distribution/CHANGELOG.md", "synthetic candidate\n")
        _put(source, "distribution/governance/active.flag", "synthetic condition\n")
        _put(source, "distribution/governance/fixture-governance.yml", "name: Fixture only\n")
        _put(source, "distribution/fixture-ci.patch", "synthetic CI patch reference\n")
        # Deliberately failing source-side script: must NEVER be executed.
        _put(source, "scripts/export.py", 'raise AssertionError("source_script_executed")\n')
        _git(source, "add", ".")
        _git(source, "-c", "user.name=Factory Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "fixture source")
        sha = _git(source, "rev-parse", "HEAD")
        exporter_sha = _git(source, "rev-parse", "HEAD:scripts/export.py")
        for ref in ("refs/remotes/origin/desenvolvimento",
                    "refs/remotes/origin/release/rc"):
            _git(source, "update-ref", ref, sha)

        _put(distribution, "fixture/SOURCE_PROVENANCE.json", json.dumps(
            {"commit": "1" * 40, "version": "1.2.3-rc.1"}) + "\n")
        _put(distribution, ".github/workflows/validate.yml",
             'jobs:\n  fixture-validation:\n    - python --version\n')
        _put(distribution, "sentinel.txt", "do not modify\n")
        _git(distribution, "add", ".")
        _git(distribution, "-c", "user.name=Factory Fixture", "-c",
             "user.email=fixture@example.invalid", "commit", "-qm", "fixture target")
        public_sha = _git(distribution, "rev-parse", "HEAD")
        _git(distribution, "update-ref", "refs/remotes/origin/main", public_sha)

        rules = {
            "required": {"fixture/config.yaml": "config.yaml",
                         "fixture/package.json": "package.json"},
            "optional": {}, "include_prefixes": ["src/"], "include_suffixes": {},
            "conditional_groups": [{"trigger": "distribution/governance/active.flag",
                "required": {"fixture/CHANGELOG.md": "distribution/CHANGELOG.md"}}],
            "shared_optional": {
                ".github/workflows/fixture-governance.yml":
                    "distribution/governance/fixture-governance.yml"}}
        profile = {"schema_version": 1, "id": "laboratorio", "product": project,
            "source_repo": "fixture/source", "distribution_repo": "fixture/catalog",
            "source_ref": "refs/remotes/origin/desenvolvimento",
            "rc_ref": "refs/remotes/origin/release/rc",
            "public_ref": "refs/remotes/origin/main",
            "package_policy_path": "policy.json", "package_json_path": "package.json",
            "manifest_path": "config.yaml", "provenance_path": "fixture/SOURCE_PROVENANCE.json",
            "distribution_prefix": "fixture/", "exporter_path": "scripts/export.py",
            "exporter_git_blob_sha": exporter_sha,
            "allowed_shared_paths": [".github/workflows/fixture-governance.yml"],
            "declarative_rules": rules}
        projects = root / "projects"
        projects.mkdir(mode=0o700)
        (projects / "laboratorio.json").write_text(json.dumps(profile), encoding="utf-8")
        preparations = root / "preparations"
        audit = root / "audit.jsonl"
        token = secrets.token_hex(32)
        original_token = os.environ.get("RUNNER_AUTH_TOKEN")
        original = {key: getattr(runner, key) for key in
                    ("PROJECTS_DIR", "WORKSPACES_DIR", "PREPARATIONS_DIR", "AUDIT_PATH")}
        try:
            os.environ["RUNNER_AUTH_TOKEN"] = token
            runner.PROJECTS_DIR = projects
            runner.WORKSPACES_DIR = root / "workspaces"
            runner.PREPARATIONS_DIR = preparations
            runner.AUDIT_PATH = audit
            with ThreadingHTTPServer(("127.0.0.1", 0), runner.Handler) as http:
                http.daemon_threads = True
                thread = threading.Thread(target=http.serve_forever, daemon=True)
                thread.start()
                try:
                    port = http.server_port
                    code, _ = _request(port, token, "/api/preflight",
                                       source_sha=sha, authorized=False)
                    _require(code == 401, "unauthenticated_preflight_accepted")
                    code, preflight = _request(port, token, "/api/preflight", source_sha=sha)
                    _require(code == 200 and preflight.get("result", {}).get(
                        "eligible_for_preparation") is True, "preflight_not_eligible")
                    _require(preflight["result"].get("public_main_sha") == public_sha,
                             "preflight_wrong_public_commit")
                    before = {str(repo): (_git(repo, "show-ref"),
                         _git(repo, "status", "--porcelain"))
                         for repo in (source, distribution)}
                    code, prepared = _request(port, token, "/api/prepare", source_sha=sha)
                    result = prepared.get("result", {})
                    if not (code == 200 and result.get("method") == "declarative_no_script"
                            and result.get("state") == "PREPARED_NOT_PUBLISHED"
                            and result.get("published") is False):
                        error = prepared.get("error", "unknown")
                        raise ProbeFailed("standard_prepare_failed_" + str(code) + "_" + str(error)[:40])
                    candidates = list(preparations.iterdir())
                    _require(len(candidates) == 1, "unexpected_candidate_count")
                    output = candidates[0]
                    bundle = json.loads((output / "DECLARATIVE_BUNDLE_MANIFEST.json").read_text())
                    provenance = json.loads((output / "fixture/SOURCE_PROVENANCE.json").read_text())
                    _require(bundle["commit"] == sha and bundle["state"] ==
                             "PREPARED_NOT_PUBLISHED", "bundle_manifest_invalid")
                    _require(provenance["commit"] == sha and provenance["version"] == version,
                             "release_provenance_invalid")
                    _require(len(provenance["files"]) == 4 and
                             len(provenance.get("repository_files", [])) == 1,
                             "incomplete_distribution")
                    for item in bundle["files"]:
                        data = (output / item["path"]).read_bytes()
                        _require(hashlib.sha256(data).hexdigest() == item["sha256"],
                                 "candidate_hash_mismatch")
                    for repo in (source, distribution):
                        _require(before[str(repo)] == (_git(repo, "show-ref"),
                                 _git(repo, "status", "--porcelain")),
                                 "fixture_repository_modified")
                    _require((distribution / "sentinel.txt").read_text() ==
                             "do not modify\n", "distribution_modified")
                    code, _ = _request(port, token, "/api/prepare", source_sha="0" * 40)
                    _require(code == 503, "invalid_source_sha_not_blocked")
                    code, _ = _request(port, token, "/api/fechar-pacote", source_sha=sha,
                                       payload={"issue": 2})
                    _require(code == 403, "publication_not_blocked")
                    # Update only the disposable source fixture to prove closed-policy denial.
                    release_policy["active_package"]["status"] = "closed"
                    _put(source, "policy.json", json.dumps(release_policy) + "\n")
                    _git(source, "add", "policy.json")
                    _git(source, "-c", "user.name=Factory Fixture", "-c",
                         "user.email=fixture@example.invalid", "commit", "-qm", "close fixture")
                    closed_sha = _git(source, "rev-parse", "HEAD")
                    for ref in ("refs/remotes/origin/desenvolvimento",
                                "refs/remotes/origin/release/rc"):
                        _git(source, "update-ref", ref, closed_sha)
                    code, denial = _request(port, token, "/api/prepare", source_sha=closed_sha)
                    _require(code == 409 and "NO_OPEN_PACKAGE" in denial.get("details", []),
                             "closed_package_not_blocked")
                    audit_body = audit.read_text(encoding="utf-8")
                    _require("completed_preparation" in audit_body and
                             "blocked_policy" in audit_body and token not in audit_body,
                             "missing_or_leaking_audit")
                    return {"checks": 8, "files": len(bundle["files"]),
                            "method": "declarative_no_script"}
                finally:
                    http.shutdown()
                    thread.join(timeout=5)
        finally:
            if original_token is None:
                os.environ.pop("RUNNER_AUTH_TOKEN", None)
            else:
                os.environ["RUNNER_AUTH_TOKEN"] = original_token
            for key, value in original.items():
                setattr(runner, key, value)


def main() -> int:
    if os.geteuid() == 0:
        print("[E2E] BLOCKED: requires non-root", flush=True)
        return 2
    old_handler = None
    if hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread():
        old_handler = signal.getsignal(signal.SIGALRM)
        signal.signal(signal.SIGALRM, lambda _sig, _frame: (_ for _ in ()).throw(
            ProbeFailed("deadline_exceeded")))
        signal.alarm(MAX_SECONDS)
    try:
        result = _execute()
        print("[E2E] PASS: authenticated loopback + real preflight + verified local bundle; "
              f"{result['files']} synthetic Git blobs; publication denied; NO real workspaces",
              flush=True)
        return 0
    except (ProbeFailed, OSError, ValueError, KeyError, TypeError,
            subprocess.SubprocessError, AssertionError) as exc:
        reason = str(exc) if isinstance(exc, ProbeFailed) else type(exc).__name__
        print("[E2E] BLOCKED: " + reason[:80], flush=True)
        return 2
    finally:
        if old_handler is not None:
            signal.alarm(0)
            signal.signal(signal.SIGALRM, old_handler)


if __name__ == "__main__":
    raise SystemExit(main())
