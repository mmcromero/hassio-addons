#!/usr/bin/env python3
"""Exercise trusted declarative export against a real synchronized Git workspace.

This is diagnostic-only: it writes a temporary bundle under /tmp, verifies the
real pinned Git blobs and generated provenance, then removes the bundle. It
does not bypass package policy, create a release receipt, or publish anything.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import tempfile

from declarative_export import (
    DeclarativeExportError,
    expand_trusted_rules,
    extend_approved_mapping,
    prepare_declarative,
    write_distribution_provenance,
)
from rc_fastlane import git as trusted_git, git_blob

SHA40 = re.compile(r"^[0-9a-f]{40}$")


def _verify_commit(repository: Path, sha: str) -> None:
    if not isinstance(sha, str) or not SHA40.fullmatch(sha):
        raise DeclarativeExportError("invalid_workspace_sha")
    resolved = trusted_git(repository, "rev-parse", "--verify", sha + "^{commit}")
    if resolved != sha:
        raise DeclarativeExportError("workspace_sha_mismatch")


def probe_declarative_workspace(
    project: str,
    source_sha: str,
    public_sha: str,
    profile: dict,
    source_repository: Path,
    distribution_repository: Path,
) -> dict:
    """Run the production blob-copy/provenance path on a real workspace snapshot.

    Release eligibility is deliberately NOT evaluated here. This proves only
    that the trusted mapping can read and verify the actual pinned Git objects.
    The normal /api/prepare-declarative endpoint continues to enforce all
    package/version/branch/provenance policy gates before durable preparation.
    """
    if os.geteuid() == 0:
        raise DeclarativeExportError("requires_non_root")
    if (not isinstance(project, str) or profile.get("id") != project
            or profile.get("mode") in ("sync_only", "artesao_package")):
        raise DeclarativeExportError("unsupported_probe_profile")
    if "declarative_rules" not in profile:
        raise DeclarativeExportError("declarative_rules_unavailable")

    source = Path(source_repository)
    distribution = Path(distribution_repository)
    if (source.is_symlink() or distribution.is_symlink()
            or not source.is_dir() or not distribution.is_dir()
            or source.resolve() != source.absolute()
            or distribution.resolve() != distribution.absolute()
            or source.resolve() == distribution.resolve()):
        raise DeclarativeExportError("unsafe_workspace")

    _verify_commit(source, source_sha)
    _verify_commit(distribution, public_sha)

    rules = profile["declarative_rules"]
    mapping = expand_trusted_rules(
        source, source_sha,
        destination_prefix=profile["distribution_prefix"],
        required=rules["required"],
        optional=rules.get("optional", {}),
        include_prefixes=rules["include_prefixes"],
        include_suffixes=rules["include_suffixes"],
    )
    mapping = extend_approved_mapping(
        source, source_sha, mapping,
        conditional_groups=rules.get("conditional_groups", []),
        shared_optional=rules.get("shared_optional", {}),
        allowed_shared_paths=profile["allowed_shared_paths"],
        distribution_prefix=profile["distribution_prefix"],
    )

    required_evidence = {
        profile["package_json_path"],
        profile["manifest_path"],
    }
    if not required_evidence.issubset(set(mapping.values())):
        raise DeclarativeExportError("package_version_evidence_missing")

    exporter_blob = trusted_git(
        source, "rev-parse", source_sha + ":" + profile["exporter_path"]
    )
    if exporter_blob != profile["exporter_git_blob_sha"]:
        raise DeclarativeExportError("declarative_rules_not_approved_for_exporter")

    ci_contract = profile.get("declarative_ci")
    if ci_contract is not None:
        trusted_git(source, "rev-parse",
                    source_sha + ":" + ci_contract["patch_source"])
        workflow = trusted_git(
            distribution, "show",
            public_sha + ":" + ci_contract["workflow_path"],
        )
        if not all(marker in workflow for marker in ci_contract["compatible_markers"]):
            raise DeclarativeExportError("ci_patch_requires_separate_review")

    package_text = git_blob(source, source_sha, profile["package_json_path"])
    try:
        package = json.loads(package_text)
    except (TypeError, ValueError) as exc:
        raise DeclarativeExportError("invalid_source_version") from exc
    version = package.get("version")
    if not isinstance(version, str) or not re.fullmatch(r"[0-9A-Za-z.+-]{1,80}", version):
        raise DeclarativeExportError("invalid_source_version")

    temp_root = Path("/tmp")
    if temp_root.is_symlink() or temp_root.resolve() != temp_root.absolute():
        raise DeclarativeExportError("unsafe_probe_temp_root")

    with tempfile.TemporaryDirectory(prefix="factory-declarative-real-", dir=str(temp_root)) as scratch:
        output = Path(scratch) / "bundle"
        manifest = prepare_declarative(
            source, source_sha, output, mapping,
            expected_version=version, project=project,
        )
        provenance = write_distribution_provenance(
            output, manifest,
            source_repository=profile["source_repo"],
            distribution_prefix=profile["distribution_prefix"],
            provenance_path=profile["provenance_path"],
            ci_patch_source=ci_contract["patch_source"] if ci_contract else None,
            allowed_shared_paths=profile["allowed_shared_paths"],
        )

        total_bytes = 0
        for item in manifest["files"]:
            target = output / item["path"]
            if (target.is_symlink() or not target.is_file()
                    or hashlib.sha256(target.read_bytes()).hexdigest() != item["sha256"]):
                raise DeclarativeExportError("real_workspace_hash_mismatch")
            total_bytes += target.stat().st_size

        provenance_path = output / profile["provenance_path"]
        if provenance_path.is_symlink() or not provenance_path.is_file():
            raise DeclarativeExportError("real_workspace_provenance_missing")
        saved = json.loads(provenance_path.read_text(encoding="utf-8"))
        if (saved.get("commit") != source_sha or saved.get("version") != version
                or saved.get("repository") != profile["source_repo"]
                or saved.get("files") != provenance.get("files")):
            raise DeclarativeExportError("real_workspace_provenance_mismatch")

        return {
            "project": project,
            "source_sha": source_sha,
            "public_sha": public_sha,
            "version": version,
            "files": len(manifest["files"]),
            "total_bytes": total_bytes,
            "provenance_files": len(provenance["files"]),
            "method": "real_git_blobs_no_script",
            "persistent_output": False,
        }
