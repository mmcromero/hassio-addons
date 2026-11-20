#!/usr/bin/env python3
"""Verified Artesao Digital dual-distribution release adapter: PLAN ONLY.

Never executes source scripts, builds containers, accepts external validation
receipts over HTTP, installs, pushes or publishes. The canonical build sequence
must be executed and evidenced separately in an approved isolated builder.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from rc_fastlane import (
    PreflightError, SHA, VERSION, fullsha, git, git_blob,
    local_environment, read_json,
)

SOURCE_REPO = "mmcromero/fabricacao_e_orcamentos"
DISTRIBUTION_REPO = "mmcromero/fabricacao-e-orcamentos-ha"
REQUIRED_SCRIPTS = (
    "scripts/release-evidence.py",
    "scripts/prepare-pilot-release.py",
    "scripts/prepare-distributions.py",
    "scripts/prepare-ha-aarch64.py",
    "scripts/prepare-forja-windows.py",
)
REQUIRED_SCHEMAS = ("tenant", "control", "interest", "support", "legal")
VER = re.compile(r"^([0-9]+)\.([0-9]+)\.([0-9]+)(?:-dev\.([0-9]+))?$")
MAX_METADATA = 128 * 1024


def _json(repo, sha, path, label):
    content = git_blob(repo, sha, path)
    if len(content.encode("utf-8")) > MAX_METADATA:
        raise PreflightError("Oversized Artesao metadata: " + label)
    return read_json(content, label)


def _version(value):
    if not isinstance(value, str):
        raise PreflightError("Invalid Artesao version")
    match = VER.fullmatch(value)
    if not match:
        raise PreflightError("Unsupported Artesao version format")
    major, minor, patch = (int(match.group(i)) for i in range(1, 4))
    # A dev build precedes the stable build with the same numeric version.
    return (major, minor, patch, 0 if match.group(4) is not None else 1,
            int(match.group(4)) if match.group(4) is not None else 0)


def _version_line(manifest):
    if len(manifest.encode("utf-8")) > MAX_METADATA:
        raise PreflightError("Oversized Artesao config")
    match = VERSION.search(manifest)
    if not match:
        raise PreflightError("Missing Artesao manifest version")
    return match.group(1)


def _schemas(value):
    return (isinstance(value, dict) and set(value) == set(REQUIRED_SCHEMAS)
            and all(type(value[key]) is int and value[key] >= 1
                    for key in REQUIRED_SCHEMAS))


def _require_profile(profile):
    if (profile.get("mode") != "artesao_package"
            or profile.get("id") != "artesao_digital"
            or profile.get("product") != "Artesão Digital"
            or profile.get("source_repo") != SOURCE_REPO
            or profile.get("distribution_repo") != DISTRIBUTION_REPO
            or profile.get("source_ref") != "refs/remotes/origin/main"
            or profile.get("public_ref") != "refs/remotes/origin/main"):
        raise PreflightError("Unapproved Artesao adapter profile")
    paths = {
        "source_version_file": "apps/umdoislab/artesao-release.json",
        "pilot_manifest_path": "apps/umdoislab/pilot/config.yaml",
        "pilot_base_path": "apps/umdoislab/pilot/core-base.json",
        "base_package_path": "apps/umdoislab/package.json",
        "public_release_path": "apps/artesaos-piloto/release.json",
        "public_manifest_path": "apps/artesaos-piloto/config.yaml",
        "public_debian_path": "forja-01/publicacao-atual.json",
    }
    if any(profile.get(key) != path for key, path in paths.items()):
        raise PreflightError("Unapproved Artesao adapter paths")
    pinned = profile.get("trusted_script_blobs")
    if not isinstance(pinned, dict) or set(pinned) != set(REQUIRED_SCRIPTS):
        raise PreflightError("Incomplete trusted release script pins")
    if any(not isinstance(x, str) or not SHA.fullmatch(x)
           for x in pinned.values()):
        raise PreflightError("Invalid trusted script pin")


def evaluate_artesao(source, distribution, expected_sha, *, profile):
    """Read immutable Git objects for BOTH official distribution tracks.

    Preflight is a plan, not a release approval. Missing validation receipts and
    architecture-specific build outputs always prevent /api/prepare.
    """
    _require_profile(profile)
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise PreflightError("Invalid pinned Artesao source SHA")
    source, distribution = Path(source), Path(distribution)
    head = fullsha(source, profile["source_ref"])
    public = fullsha(distribution, profile["public_ref"])
    if head != expected_sha or fullsha(source, expected_sha) != expected_sha:
        raise PreflightError("Artesao source advanced or pinned SHA invalid")

    common = _json(source, expected_sha, profile["source_version_file"], "source release")
    package = _json(source, expected_sha, profile["base_package_path"], "base package")
    base = _json(source, expected_sha, profile["pilot_base_path"], "pilot base")
    config = git_blob(source, expected_sha, profile["pilot_manifest_path"])
    version = common.get("version")
    candidate_key = _version(version)
    errors = []

    if (common.get("distributions") != ["home-assistant", "debian"]
            or not _schemas(common.get("schemaVersions"))):
        errors.append("INVALID_SOURCE_DISTRIBUTIONS_OR_SCHEMAS")
    if _version_line(config) != version:
        errors.append("SOURCE_PILOT_VERSION_MISMATCH")
    if ("slug: artesaos_piloto" not in config
            or not re.search(r"(?m)^  - aarch64\s*$", config)):
        errors.append("HA_IDENTITY_OR_ARCH_CHANGED")
    core = base.get("commit")
    core_version = base.get("version")
    if (not isinstance(core, str) or not SHA.fullmatch(core)
            or not isinstance(core_version, str)
            or package.get("version") != core_version):
        errors.append("INVALID_PILOT_CORE_BASE")
    else:
        try:
            if fullsha(source, core) != core:
                errors.append("INVALID_PILOT_CORE_BASE")
            else:
                ancestor = subprocess.run(
                    ["git", "-C", str(source), "merge-base", "--is-ancestor",
                     core, expected_sha],
                    capture_output=True, timeout=30, check=False,
                    env=local_environment())
                if ancestor.returncode != 0:
                    errors.append("CORE_BASE_NOT_ANCESTOR")
                else:
                    base_package = _json(
                        source, core, profile["base_package_path"], "pinned core package")
                    if base_package.get("version") != core_version:
                        errors.append("CORE_BASE_VERSION_MISMATCH")
        except (PreflightError, subprocess.SubprocessError, OSError):
            errors.append("CORE_BASE_UNAVAILABLE")
    for path, approved_blob in profile["trusted_script_blobs"].items():
        try:
            actual = git(source, "rev-parse", expected_sha + ":" + path)
        except (PreflightError, OSError):
            actual = None
        if actual != approved_blob:
            errors.append("TRUSTED_RELEASE_RECIPE_CHANGED")
            break

    public_release = _json(distribution, public, profile["public_release_path"],
                           "published HA release")
    public_config = git_blob(distribution, public, profile["public_manifest_path"])
    forja = _json(distribution, public, profile["public_debian_path"],
                  "published Debian pointer")
    public_version = public_release.get("releaseVersion")
    public_source = public_release.get("sourceCommit")
    ha_public_key = _version(public_version)
    debian_version = forja.get("version")
    debian_key = _version(debian_version)
    if (_version_line(public_config) != public_version
            or public_release.get("distribution") != "home-assistant"
            or public_release.get("packageKind") != "home-assistant-precompiled-aarch64"
            or public_release.get("runtimeSourceCommit") != public_source
            or not isinstance(public_source, str) or not SHA.fullmatch(public_source)
            or public_release.get("architecture") != "linux/arm64"
            or not _schemas(public_release.get("schemaVersions"))):
        errors.append("INVALID_PUBLISHED_HA_PROVENANCE")
    if (forja.get("distribution") != "debian"
            or forja.get("repository") != SOURCE_REPO
            or not SHA.fullmatch(str(forja.get("sourceCommit", "")))
            or not re.fullmatch(r"[0-9a-f]{64}", str(forja.get("sha256", "")))):
        errors.append("INVALID_PUBLISHED_DEBIAN_PROVENANCE")
    if candidate_key == ha_public_key:
        if public_source == expected_sha:
            errors.append("SOURCE_ALREADY_PUBLISHED_HA")
        else:
            errors.append("VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE")
    elif candidate_key < ha_public_key:
        errors.append("HA_VERSION_NOT_NEWER")
    if candidate_key <= debian_key:
        errors.append("DEBIAN_VERSION_NOT_NEWER")
    if _schemas(common.get("schemaVersions")) and _schemas(public_release.get("schemaVersions")):
        if common["schemaVersions"] != public_release["schemaVersions"]:
            errors.append("SCHEMA_CHANGE_REQUIRES_EXPLICIT_MIGRATION_APPROVAL")

    # The official release-evidence.py executes npm build/tests and generates
    # an untracked receipt. It MUST NOT be synthesized from Git metadata.
    pending = [
        "VALIDATION_RECEIPT_NOT_VERIFIED",
        "HA_ARM64_IMAGE_NOT_BUILT_OR_VERIFIED",
        "DEBIAN_AMD64_IMAGE_NOT_BUILT_OR_VERIFIED",
        "PACKAGE_ARTIFACT_CHECKSUMS_NOT_VERIFIED",
        "OWNER_PUBLICATION_AUTHORIZATION_NOT_GRANTED",
    ]
    return {
        "project": profile["id"], "adapter": "artesao-dual-distribution-v1",
        "mode": "read_only_release_plan", "source_sha": expected_sha,
        "public_sha": public, "candidate_version": version,
        "published_ha_version": public_version,
        "published_debian_version": debian_version,
        "schema_versions": common.get("schemaVersions"),
        "distribution_tracks": {
            "home_assistant": {
                "role": "manual_contingency", "slug": "artesaos_piloto",
                "destination": "apps/artesaos-piloto/",
                "required_arch": "linux/arm64",
                "official_builder": "scripts/prepare-ha-aarch64.py",
            },
            "debian": {
                "role": "Forja_01_primary", "destination": "forja-01/",
                "required_arch": "linux/amd64",
                "official_exporter": "scripts/prepare-distributions.py",
                "official_updater": "scripts/prepare-forja-windows.py",
            },
        },
        "trusted_scripts_verified": "TRUSTED_RELEASE_RECIPE_CHANGED" not in errors,
        "blocking_errors": errors,
        "external_evidence_pending": pending,
        "errors": errors + pending,
        "eligible_for_preparation": False,
        "eligible_for_publication": False,
        "state": "PLAN_ONLY_NO_PACKAGE",
        "published": False,
    }
