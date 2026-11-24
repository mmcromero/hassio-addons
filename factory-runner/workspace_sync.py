#!/usr/bin/env python3
"""Verified, read-only GitHub checkout provisioning within app private storage.

Only trusted project profiles select the GitHub repositories and refs. GitHub
branch heads are verified independently via API over TLS and compared with
full Git clones. The clone never checks out or executes project-controlled files.
Data in an existing workspace is never overwritten/deleted: prior managed
snapshots are archived under this app's own /data workspace volume.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import stat
import subprocess
import tempfile
import time
from urllib import parse, request
import uuid
from publisher_permissions import share_readonly, share_root_traverse

from rc_fastlane import PreflightError, evaluate, fullsha, git_blob, load_profile, read_json

IDENT = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SHA = re.compile(r"^[0-9a-f]{40}$")
REF_HEAD = "refs/remotes/origin/"
MANAGED = ".factory-runner-workspace.json"
MAX_GIT_BYTES = 512 * 1024 * 1024
# Preserve historical clones in their original paths. Limit storage globally,
# not by an arbitrary number of snapshots per project. No automatic deletion.
MAX_ARCHIVE_BYTES = 16 * MAX_GIT_BYTES
MIN_FREE_BYTES = 4 * MAX_GIT_BYTES
ARCHIVE_NAME = re.compile(r"^\.archive-([a-z][a-z0-9_-]{1,47})-[0-9a-f]{12}$")

class SyncError(Exception):
    pass

class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise SyncError("remote_redirect_not_approved")


def _branch(ref: str) -> str:
    if (not isinstance(ref, str) or not ref.startswith(REF_HEAD)
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", ref[len(REF_HEAD):])
            or any(x in ("", ".", "..") for x in ref[len(REF_HEAD):].split("/"))):
        raise SyncError("invalid_approved_git_ref")
    return ref[len(REF_HEAD):]


def _remote_head(repo: str, ref: str, token: str) -> str:
    if not REPO.fullmatch(repo):
        raise SyncError("invalid_approved_repository")
    branch = _branch(ref)
    url = ("https://api.github.com/repos/" + repo + "/commits/" +
           parse.quote(branch, safe=""))
    headers = {"User-Agent": "Factory-Runner-Read-Only", "Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    opener = request.build_opener(NoRedirect)
    try:
        with opener.open(request.Request(url, headers=headers), timeout=18) as resp:
            if resp.status != 200:
                raise SyncError("remote_head_not_accessible")
            obj = json.loads(resp.read(1024 * 1024))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise SyncError("remote_head_not_accessible") from exc
    sha = obj.get("sha")
    if not isinstance(sha, str) or not SHA.fullmatch(sha):
        raise SyncError("remote_head_invalid")
    return sha


def _public_scope_unchanged(profile: dict, old_sha: str, new_sha: str) -> bool:
    """Safely skip full clones for unrelated commits in a shared public catalog.

    Fail closed on API error, pagination ambiguity, non-ancestry or a change to
    any path that belongs to the approved distribution or shared CI rules.
    Never use this fast path for profiles without a reviewed distribution prefix.
    """
    prefix = profile.get("distribution_prefix")
    if (not isinstance(prefix, str) or not prefix.endswith("/")
            or not SHA.fullmatch(old_sha) or not SHA.fullmatch(new_sha)
            or old_sha == new_sha):
        return False
    shared = profile.get("allowed_shared_paths")
    if not isinstance(shared, list) or any(not isinstance(p, str) for p in shared):
        return False
    ci = profile.get("declarative_ci")
    if ci is not None:
        if not isinstance(ci, dict) or not isinstance(ci.get("workflow_path"), str):
            return False
        shared = [*shared, ci["workflow_path"]]
    repo = profile.get("distribution_repo")
    if not isinstance(repo, str) or not REPO.fullmatch(repo):
        return False
    url = ("https://api.github.com/repos/" + repo + "/compare/"
           + old_sha + "..." + new_sha + "?per_page=100")
    req = request.Request(url, headers={
        "User-Agent": "Factory-Runner-Read-Only",
        "Accept": "application/vnd.github+json",
    })
    try:
        opener = request.build_opener(NoRedirect)
        with opener.open(req, timeout=18) as resp:
            if resp.status != 200:
                return False
            payload = resp.read(2 * 1024 * 1024 + 1)
        if len(payload) > 2 * 1024 * 1024:
            return False
        data = json.loads(payload)
    except (OSError, ValueError, TypeError, SyncError):
        return False
    if not isinstance(data, dict):
        return False
    files = data.get("files")
    merge_base = data.get("merge_base_commit")
    if (data.get("status") != "ahead"
            or data.get("behind_by") != 0
            or not isinstance(merge_base, dict)
            or merge_base.get("sha") != old_sha
            or not isinstance(files, list) or len(files) >= 300):
        return False
    for file in files:
        if not isinstance(file, dict):
            return False
        name = file.get("filename")
        previous = file.get("previous_filename")
        if not isinstance(name, str) or (previous is not None
                and not isinstance(previous, str)):
            return False
        for path in (name, previous):
            if path and (path.startswith(prefix) or path in shared):
                return False
    return True


def _git(repo: Path, *args: str) -> str:
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "GIT_CONFIG_NOSYSTEM": "1",
           "GIT_CONFIG_GLOBAL": os.devnull, "GIT_TERMINAL_PROMPT": "0",
           "GIT_OPTIONAL_LOCKS": "0", "GIT_NO_REPLACE_OBJECTS": "1"}
    try:
        result = subprocess.run(["git", "-c", "core.hooksPath=/dev/null", "-C",
                                 str(repo), *args], capture_output=True,
                                stdin=subprocess.DEVNULL, env=env, timeout=25, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError("git_verify_failed") from exc
    if result.returncode:
        raise SyncError("git_verify_failed")
    return result.stdout.decode("utf-8", "strict").strip()


def _clone(repo: str, path: Path, token: str) -> None:
    if not REPO.fullmatch(repo) or path.exists() or path.is_symlink():
        raise SyncError("invalid_clone_target")
    secret_dir = None
    env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_OPTIONAL_LOCKS": "0",
           "GIT_NO_REPLACE_OBJECTS": "1", "GIT_LFS_SKIP_SMUDGE": "1",
           "GIT_PROTOCOL_FROM_USER": "0"}
    try:
        if token:
            secret_dir = tempfile.TemporaryDirectory(prefix="factory-git-cred-", dir="/tmp")
            token_file = Path(secret_dir.name) / "secret"
            token_file.write_text(token, encoding="utf-8")
            token_file.chmod(0o600)
            env.update({"GIT_ASKPASS": str(Path(__file__).with_name("workspace_askpass.py")),
                        "FACTORY_GIT_SECRET_FILE": str(token_file)})
        command = ["git", "-c", "core.hooksPath=/dev/null", "-c",
                   "protocol.file.allow=never", "clone", "--quiet", "--no-checkout",
                   "--no-recurse-submodules", "--", "https://github.com/" + repo + ".git",
                   str(path)]
        proc = subprocess.run(command, capture_output=True, stdin=subprocess.DEVNULL,
                              env=env, timeout=220, check=False)
        if proc.returncode:
            raise SyncError("clone_unavailable")
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise SyncError("clone_unavailable") from exc
    finally:
        if secret_dir is not None:
            secret_dir.cleanup()


def _bytes(root: Path) -> int:
    total = 0
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            p = Path(base) / name
            if p.is_symlink():
                raise SyncError("unsafe_clone_symlink")
            total += p.lstat().st_size
            if total > MAX_GIT_BYTES:
                raise SyncError("workspace_budget_exceeded")
    return total


def _retained_snapshot_bytes(path: Path) -> int:
    """Count a verified managed no-checkout snapshot; never modify its data."""
    try:
        info = path.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or path.resolve() != path.absolute()):
            raise SyncError("workspace_archive_unmanaged")
        if {p.name for p in path.iterdir()} != {"source", "distribution", MANAGED}:
            raise SyncError("workspace_archive_unmanaged")
        manifest = path / MANAGED
        meta = manifest.lstat()
        if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid()
                or meta.st_nlink != 1 or meta.st_size > 65536):
            raise SyncError("workspace_archive_unmanaged")
        data = json.loads(manifest.read_bytes())
        if (not isinstance(data, dict)
                or data.get("managed_by") != "factory-runner-workspace-v1"
                or not all(isinstance(data.get(k), str) and REPO.fullmatch(data[k])
                           for k in ("source_repo", "distribution_repo"))
                or not all(isinstance(data.get(k), str) and SHA.fullmatch(data[k])
                           for k in ("source_sha", "public_sha"))):
            raise SyncError("workspace_archive_unmanaged")
        for name in ("source", "distribution"):
            checkout = path / name
            if (not stat.S_ISDIR(checkout.lstat().st_mode)
                    or {p.name for p in checkout.iterdir()} != {".git"}
                    or not stat.S_ISDIR((checkout / ".git").lstat().st_mode)):
                raise SyncError("workspace_archive_unmanaged")
        total = max(info.st_size, info.st_blocks * 512)
        def walk_error(error):
            raise SyncError("workspace_archive_unreadable") from error
        for base, dirs, files in os.walk(path, followlinks=False, onerror=walk_error):
            for name in dirs + files:
                entry = (Path(base) / name).lstat()
                if (entry.st_uid != os.geteuid()
                        or not (stat.S_ISDIR(entry.st_mode)
                                or (stat.S_ISREG(entry.st_mode) and entry.st_nlink == 1))):
                    raise SyncError("workspace_archive_unmanaged")
                total += max(entry.st_size, entry.st_blocks * 512)
                if total > MAX_ARCHIVE_BYTES:
                    raise SyncError("workspace_archive_storage_limit")
        return total
    except (OSError, ValueError, TypeError) as exc:
        raise SyncError("workspace_archive_unreadable") from exc


def _archive_capacity(root: Path, workspace: Path, previous: dict | None) -> tuple[int, int]:
    """Account for every retained clone plus the active clone about to be archived."""
    total, count = 0, 0
    for path in root.glob(".archive-*"):
        if not ARCHIVE_NAME.fullmatch(path.name):
            raise SyncError("workspace_archive_unmanaged")
        total += _retained_snapshot_bytes(path)
        count += 1
        if total > MAX_ARCHIVE_BYTES:
            raise SyncError("workspace_archive_storage_limit")
    if previous is not None:
        total += _retained_snapshot_bytes(workspace)
        count += 1
    if total > MAX_ARCHIVE_BYTES:
        raise SyncError("workspace_archive_storage_limit")
    if shutil.disk_usage(root).free < MIN_FREE_BYTES + MAX_GIT_BYTES:
        raise SyncError("workspace_disk_reserve")
    return count, total


def _safe_workspace_root(root: Path) -> None:
    if root.is_symlink() or root.resolve() != root.absolute():
        raise SyncError("unsafe_workspace_root")
    root.mkdir(mode=0o700, parents=True, exist_ok=True)
    if root.stat().st_uid != os.geteuid():
        raise SyncError("workspace_owner_mismatch")
    try:
        share_root_traverse(root)
    except (OSError, ValueError, KeyError) as exc:
        raise SyncError("publisher_workspace_acl_unavailable") from exc


def _existing(workspace: Path, profile: dict) -> dict | None:
    if not workspace.exists() and not workspace.is_symlink():
        return None
    if workspace.is_symlink() or not workspace.is_dir():
        raise SyncError("unsafe_previous_workspace")
    manifest = workspace / MANAGED
    if manifest.is_symlink() or not manifest.is_file():
        raise SyncError("unmanaged_workspace_preserved")
    try:
        data = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise SyncError("invalid_managed_workspace") from exc
    if (data.get("managed_by") != "factory-runner-workspace-v1"
            or data.get("source_repo") != profile["source_repo"]
            or data.get("distribution_repo") != profile["distribution_repo"]):
        raise SyncError("unmanaged_workspace_preserved")
    for name, remote in (("source", profile["source_repo"]),
                         ("distribution", profile["distribution_repo"])):
        path = workspace / name
        if path.is_symlink() or not path.is_dir() or path.resolve() != path.absolute():
            raise SyncError("unsafe_previous_checkout")
        if _git(path, "remote", "get-url", "origin") != "https://github.com/" + remote + ".git":
            raise SyncError("previous_remote_changed")
        head_ref = profile["source_ref"] if name == "source" else profile["public_ref"]
        expected_sha = data["source_sha"] if name == "source" else data["public_sha"]
        if not SHA.fullmatch(str(expected_sha)) or fullsha(path, head_ref) != expected_sha:
            raise SyncError("previous_commit_changed")
        # A no-checkout clone must not contain user-modified files.
        if any(p.name not in (".git",) for p in path.iterdir()):
            raise SyncError("previous_checkout_modified")
    return data


def _verified_profile_report(profile: dict, source: Path,
                             distribution: Path, source_sha: str) -> dict:
    """Use approved release gates, or strictly read-only source metadata."""
    if profile.get("mode") == "artesao_package":
        from artesao_adapter import evaluate_artesao
        return evaluate_artesao(source, distribution, source_sha, profile=profile)
    if profile.get("mode") == "sync_only":
        try:
            metadata = read_json(
                git_blob(source, source_sha, profile["source_version_file"]),
                "read-only source version")
        except (PreflightError, OSError, ValueError) as exc:
            raise SyncError("source_version_unavailable") from exc
        version = metadata.get("version")
        if (not isinstance(version, str) or not 1 <= len(version) <= 80
                or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._+-]*", version)):
            raise SyncError("source_version_invalid")
        return {"eligible_for_preparation": False,
                "errors": ["SYNC_ONLY_NO_PREPARATION"]}
    return evaluate(source, distribution, source_sha, profile=profile)


def synchronize(project: str, *, token: str, projects_dir: Path,
                workspaces_dir: Path, remote_head=_remote_head,
                clone=_clone) -> dict:
    if os.geteuid() == 0:
        raise SyncError("requires_non_root")
    if not isinstance(project, str) or not IDENT.fullmatch(project):
        raise SyncError("invalid_project")
    file = Path(projects_dir) / (project + ".json")
    if file.is_symlink() or not file.is_file():
        raise SyncError("approved_project_missing")
    try:
        profile = load_profile(file)
    except (PreflightError, OSError, ValueError, TypeError) as exc:
        raise SyncError("approved_profile_invalid") from exc
    if profile["id"] != project:
        raise SyncError("approved_profile_mismatch")
    root = Path(workspaces_dir).absolute()
    _safe_workspace_root(root)
    workspace = root / project
    previous = _existing(workspace, profile)
    source_sha = remote_head(profile["source_repo"], profile["source_ref"], token)
    public_sha = remote_head(profile["distribution_repo"], profile["public_ref"], "")
    if previous is not None and previous.get("source_sha") == source_sha:
        existing_public_sha = previous.get("public_sha")
        if existing_public_sha == public_sha or _public_scope_unchanged(
                profile, existing_public_sha, public_sha):
            try:
                report = _verified_profile_report(
                    profile, workspace / "source", workspace / "distribution", source_sha)
            except (PreflightError, OSError, ValueError, subprocess.SubprocessError) as exc:
                raise SyncError("preflight_failed") from exc
            try:
                share_readonly(workspace)
            except (OSError, ValueError, KeyError) as exc:
                raise SyncError("publisher_workspace_acl_unavailable") from exc
            if existing_public_sha == public_sha:
                return {"state": "UNCHANGED", "project": project,
                        "source_sha": source_sha, "public_sha": public_sha,
                        "eligible": bool(report["eligible_for_preparation"]),
                        "errors": list(report["errors"])}
            # Only skip an unrelated catalog update when the old snapshot is
            # already policy-blocked. Never prepare from a stale public base.
            if not report["eligible_for_preparation"]:
                return {"state": "UNCHANGED_SCOPE", "project": project,
                        "source_sha": source_sha, "public_sha": existing_public_sha,
                        "remote_public_sha": public_sha, "eligible": False,
                        "errors": list(report["errors"]) + ["PUBLIC_HEAD_OUTSIDE_APPROVED_SCOPE"]}
    archive_count, archive_bytes = _archive_capacity(root, workspace, previous)
    # Temporary staging must be a sibling on the same private filesystem.
    stage = Path(tempfile.mkdtemp(prefix=".stage-" + project + "-", dir=root))
    saved = None
    try:
        source, distribution = stage / "source", stage / "distribution"
        clone(profile["source_repo"], source, token)
        clone(profile["distribution_repo"], distribution, "")
        _bytes(stage)
        if fullsha(source, profile["source_ref"]) != source_sha:
            raise SyncError("source_head_moved")
        if fullsha(distribution, profile["public_ref"]) != public_sha:
            raise SyncError("public_head_moved")
        # Check no unexpected on-disk project files or remote URL rewrites.
        for path, remote in ((source, profile["source_repo"]),
                             (distribution, profile["distribution_repo"])):
            if _git(path, "remote", "get-url", "origin") != "https://github.com/" + remote + ".git":
                raise SyncError("remote_rewritten")
            if any(p.name != ".git" for p in path.iterdir()):
                raise SyncError("checked_out_untrusted_files")
        try:
            report = _verified_profile_report(
                profile, source, distribution, source_sha)
        except (PreflightError, OSError, ValueError, subprocess.SubprocessError) as exc:
            raise SyncError("preflight_failed") from exc
        status = {"managed_by": "factory-runner-workspace-v1",
                  "source_repo": profile["source_repo"],
                  "distribution_repo": profile["distribution_repo"],
                  "source_sha": source_sha, "public_sha": public_sha}
        (stage / MANAGED).write_text(json.dumps(status, sort_keys=True), encoding="utf-8")
        (stage / MANAGED).chmod(0o600)
        try:
            share_readonly(stage)
        except (OSError, ValueError, KeyError) as exc:
            raise SyncError("publisher_workspace_acl_unavailable") from exc
        # Recheck after cloning, before changing the live workspace. No old
        # snapshots are removed or moved for capacity recovery.
        if shutil.disk_usage(root).free < MIN_FREE_BYTES:
            raise SyncError("workspace_disk_reserve")
        if previous is not None:
            saved = root / (".archive-" + project + "-" + uuid.uuid4().hex[:12])
            os.rename(workspace, saved)
        try:
            os.rename(stage, workspace)
        except OSError:
            if saved is not None and not workspace.exists():
                os.rename(saved, workspace)
            raise
        result = {"state": "SYNCED", "project": project,
                  "source_sha": source_sha, "public_sha": public_sha,
                  "eligible": bool(report["eligible_for_preparation"]),
                  "errors": list(report["errors"]),
                  "archive_count": archive_count, "archive_bytes": archive_bytes,
                  "archive_budget_bytes": MAX_ARCHIVE_BYTES}
        return result
    finally:
        if stage.exists():
            # Only a runner-created temporary staging directory is removed.
            shutil.rmtree(stage)
