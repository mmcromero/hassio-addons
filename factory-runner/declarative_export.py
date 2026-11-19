#!/usr/bin/env python3
"""Deterministic offline export of pinned Git blobs; NO source code execution.

This module is not wired to the legacy HTTP server or the published HA add-on.
The mapping MUST come from trusted runner-owned configuration, never a project
commit, user HTTP payload or AI output. No git checkout, Python/npm or shell.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess

SHA40 = re.compile(r"^[0-9a-f]{40}$")
SEGMENT = re.compile(r"^[A-Za-z0-9_.@+ -]+$")
MAX_FILES = 4096
MAX_TOTAL_BYTES = 256 * 1024 * 1024
MAX_FILE_BYTES = 32 * 1024 * 1024

class DeclarativeExportError(Exception):
    pass

def safe_path(value: str) -> str:
    if (not isinstance(value, str) or len(value) > 512 or not value
            or value.startswith("/") or "\\" in value or "\x00" in value
            or any(part in ("", ".", "..") or not SEGMENT.fullmatch(part)
                   for part in value.split("/")) or ".git" in value.split("/")):
        raise DeclarativeExportError("unsafe_path")
    return value

def _git(repo: Path, *args: str) -> bytes:
    env = {"PATH": "/usr/bin:/bin", "HOME": os.devnull,
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
           "GIT_TERMINAL_PROMPT": "0", "GIT_NO_REPLACE_OBJECTS": "1",
           "GIT_OPTIONAL_LOCKS": "0"}
    try:
        result = subprocess.run(
            ["git", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false",
             "-C", str(repo), *args],
            env=env, stdin=subprocess.DEVNULL, capture_output=True,
            shell=False, timeout=40, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise DeclarativeExportError("git_unavailable") from exc
    if result.returncode:
        raise DeclarativeExportError("git_object_unavailable")
    return result.stdout

def _blob(repo: Path, sha: str, source_path: str) -> bytes:
    # Check tree entry mode; refuse symlink (120000), submodule (160000),
    # directory and any non-blob object.
    entry = _git(repo, "ls-tree", "-z", sha, "--", source_path)
    rows = [row for row in entry.split(b"\x00") if row]
    if len(rows) != 1:
        raise DeclarativeExportError("missing_or_ambiguous_blob")
    try:
        header, path = rows[0].split(b"\t", 1)
        mode, kind, blob_sha = header.split(b" ")
    except ValueError as exc:
        raise DeclarativeExportError("bad_git_tree_entry") from exc
    if (path.decode("utf-8") != source_path or kind != b"blob"
            or mode not in (b"100644", b"100755")
            or not re.fullmatch(rb"[0-9a-f]{40,64}", blob_sha)):
        raise DeclarativeExportError("unsupported_git_object")
    size_bytes = _git(repo, "cat-file", "-s", blob_sha.decode("ascii")).decode().strip()
    if not size_bytes.isdecimal() or int(size_bytes) > MAX_FILE_BYTES:
        raise DeclarativeExportError("file_budget_exceeded")
    data = _git(repo, "cat-file", "blob", blob_sha.decode("ascii"))
    if len(data) > MAX_FILE_BYTES:
        raise DeclarativeExportError("file_budget_exceeded")
    return data

def expand_trusted_rules(source_repo: Path, source_sha: str, *,
                         destination_prefix: str, required: dict[str, str],
                         optional: dict[str, str], include_prefixes: list[str],
                         include_suffixes: dict[str, str]) -> dict[str, str]:
    """Compile trusted declarative rules against one pinned Git tree.

    This expands file names only. It never reads or executes source programs.
    Destination prefix, fixed file maps and selection rules belong to the
    runner-owned profile, not an API request or source repository.
    """
    if not isinstance(source_sha, str) or not SHA40.fullmatch(source_sha):
        raise DeclarativeExportError("invalid_sha")
    if (not isinstance(destination_prefix, str)
            or not destination_prefix.endswith("/")):
        raise DeclarativeExportError("invalid_destination_prefix")
    safe_path(destination_prefix[:-1])
    if (not isinstance(required, dict) or not isinstance(optional, dict)
            or not isinstance(include_prefixes, list)
            or not isinstance(include_suffixes, dict)
            or not all(isinstance(v, str) and v.endswith("/")
                       and safe_path(v[:-1]) for v in include_prefixes)):
        raise DeclarativeExportError("invalid_trusted_rules")
    for prefix, suffix in include_suffixes.items():
        if (not isinstance(prefix, str) or not prefix.endswith("/")
                or not isinstance(suffix, str) or not suffix.startswith(".")
                or len(suffix) > 64):
            raise DeclarativeExportError("invalid_suffix_rule")
        safe_path(prefix[:-1])
    entries = _git(Path(source_repo), "ls-tree", "-r", "-z", source_sha)
    available = {}
    for row in entries.split(b"\x00"):
        if not row:
            continue
        try:
            header, path = row.split(b"\t", 1)
            mode, kind, _blob_sha = header.split(b" ")
            filename = path.decode("utf-8")
        except (ValueError, UnicodeDecodeError) as exc:
            raise DeclarativeExportError("invalid_git_tree") from exc
        selected = (any(filename.startswith(p) for p in include_prefixes)
                    or any(filename.startswith(p) and filename.endswith(s)
                           for p, s in include_suffixes.items()))
        if selected:
            safe_path(filename)
            if kind != b"blob" or mode not in (b"100644", b"100755"):
                raise DeclarativeExportError("unsupported_git_object")
            available[filename] = True
            if len(available) > MAX_FILES:
                raise DeclarativeExportError("file_count_exceeded")
    mapping = {safe_path(destination_prefix + path): path
               for path in sorted(available)}
    for group, mandatory in ((required, True), (optional, False)):
        for dest, source in group.items():
            safe_path(dest)
            safe_path(source)
            if not dest.startswith(destination_prefix):
                raise DeclarativeExportError("rule_destination_escapes_prefix")
            if source in available or not mandatory:
                # Check optional against the exact pinned tree below.
                if not mandatory:
                    exact = _git(Path(source_repo), "ls-tree", "-z", source_sha,
                                 "--", source)
                    if not exact:
                        continue
                mapping[dest] = source
            else:
                # Required files may be outside the selected prefixes.
                exact = _git(Path(source_repo), "ls-tree", "-z", source_sha,
                             "--", source)
                if not exact:
                    raise DeclarativeExportError("required_source_missing")
                mapping[dest] = source
    if len(mapping) > MAX_FILES:
        raise DeclarativeExportError("file_count_exceeded")
    return mapping


def prepare_declarative(source_repo: Path, source_sha: str, output_dir: Path,
                        mappings: dict[str, str], *,
                        expected_version: str, project: str) -> dict:
    """Write one NEW local candidate directory. Never commit or publish.

    mappings: destination relative path -> source relative path.
    Caller supplies trusted mappings and a preflight-approved source SHA.
    Directory parent must be runner-owned and inaccessible to untrusted users.
    """
    if not isinstance(source_sha, str) or not SHA40.fullmatch(source_sha):
        raise DeclarativeExportError("invalid_sha")
    if not isinstance(project, str) or not re.fullmatch(r"[a-z][a-z0-9_-]{1,47}", project):
        raise DeclarativeExportError("invalid_project")
    if not isinstance(expected_version, str) or not re.fullmatch(r"[0-9A-Za-z.+-]{1,80}", expected_version):
        raise DeclarativeExportError("invalid_version")
    if not isinstance(mappings, dict) or not 0 < len(mappings) <= MAX_FILES:
        raise DeclarativeExportError("invalid_mapping")
    checked: dict[str, str] = {}
    for destination, origin in mappings.items():
        dest, src = safe_path(destination), safe_path(origin)
        if dest in ("SOURCE_PROVENANCE.json", "DECLARATIVE_BUNDLE_MANIFEST.json") or dest in checked:
            raise DeclarativeExportError("reserved_or_duplicate_destination")
        checked[dest] = src
    # No prefix collisions: one destination cannot be a parent of another.
    names = set(checked)
    for name in names:
        for part in range(1, len(name.split("/"))):
            if "/".join(name.split("/")[:part]) in names:
                raise DeclarativeExportError("destination_path_collision")
    source_repo = Path(source_repo)
    output_dir = Path(output_dir)
    parent = output_dir.parent
    if (not source_repo.is_dir() or source_repo.is_symlink()
            or not parent.is_dir() or parent.is_symlink()
            or output_dir.exists() or output_dir.is_symlink()
            or source_repo.resolve() == parent.resolve()
            or source_repo.resolve() in parent.resolve().parents):
        raise DeclarativeExportError("unsafe_workspace")
    resolved_sha = _git(source_repo, "rev-parse", "--verify", source_sha + "^{commit}").decode().strip()
    if resolved_sha != source_sha:
        raise DeclarativeExportError("sha_mismatch")

    # Read ALL objects before creating output. Reject missing, symlinked and
    # oversized content without touching the destination.
    files: list[tuple[str, str, bytes]] = []
    total = 0
    for destination, origin in sorted(checked.items()):
        payload = _blob(source_repo, source_sha, origin)
        total += len(payload)
        if total > MAX_TOTAL_BYTES:
            raise DeclarativeExportError("total_budget_exceeded")
        if origin == "package.json":
            try:
                manifest_version = json.loads(payload.decode("utf-8")).get("version")
            except (ValueError, UnicodeDecodeError, AttributeError) as exc:
                raise DeclarativeExportError("invalid_source_version") from exc
            if manifest_version != expected_version:
                raise DeclarativeExportError("source_version_mismatch")
        if origin == "config.yaml":
            version_line = next((line for line in payload.decode("utf-8").splitlines()
                                 if line.startswith("version:")), None)
            if version_line is None or version_line.split(":", 1)[1].strip().strip('"').strip("'") != expected_version:
                raise DeclarativeExportError("source_version_mismatch")
        files.append((destination, origin, payload))
    output_dir.mkdir(mode=0o700)
    records = []
    for destination, origin, payload in files:
        target = output_dir / destination
        target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(payload)
        records.append({"path": destination, "source_path": origin,
                        "sha256": hashlib.sha256(payload).hexdigest()})
    manifest = {"format": "factory-runner-bundle-v1", "project": project, "commit": source_sha,
                "version": expected_version, "files": records,
                "state": "PREPARED_NOT_PUBLISHED",
                "export_method": "declarative_no_script"}
    with (output_dir / "DECLARATIVE_BUNDLE_MANIFEST.json").open("x", encoding="utf-8") as stream:
        json.dump(manifest, stream, ensure_ascii=False, indent=2)
        stream.write("\n")
    for record in records:
        target = output_dir / record["path"]
        if (target.is_symlink()
                or hashlib.sha256(target.read_bytes()).hexdigest() != record["sha256"]):
            raise DeclarativeExportError("verification_failed")
    return manifest
