#!/usr/bin/env python3
"""Artesao build executor for a dedicated disposable, network-isolated VM.

NEVER import this module into the HA runtime or give the HA add-on Docker access.
The executable is NOT a publisher, installer, updater, or GitHub Actions runner.
Execute only trusted scripts pinned by the reviewed Artesao project profile.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from artesao_adapter import evaluate_artesao
from rc_fastlane import PreflightError, SHA, load_profile, local_environment

IMAGE_PREFIX = "artesao-digital"
SAFE_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+-dev\.[0-9]+$")
HASH = re.compile(r"^[0-9a-f]{64}$")
MAX_RECEIPT = 2 * 1024 * 1024
MAX_FILE_LIST = 10000


class ExecutorBlocked(Exception):
    """A fixed failure reason, never subprocess logs or credentials."""


def _json_file(path: Path, limit=MAX_RECEIPT):
    if not path.is_file() or path.is_symlink() or path.stat().st_size > limit:
        raise ExecutorBlocked("INVALID_EVIDENCE_FILE")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, ValueError) as exc:
        raise ExecutorBlocked("INVALID_EVIDENCE_JSON") from exc
    if not isinstance(data, dict):
        raise ExecutorBlocked("INVALID_EVIDENCE_SCHEMA")
    return data


def _sha(path: Path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_sums(folder: Path, name="SHA256SUMS", *, require_complete=True):
    """Verify the canonical SHA-256 list, reject traversal, links and omissions."""
    folder = Path(folder)
    record = folder / name
    if not folder.is_dir() or folder.is_symlink() or not record.is_file() or record.is_symlink():
        raise ExecutorBlocked("CHECKSUM_LIST_MISSING")
    if record.stat().st_size > 2 * 1024 * 1024:
        raise ExecutorBlocked("CHECKSUM_LIST_TOO_LARGE")
    lines = record.read_text(encoding="utf-8").splitlines()
    if not 1 <= len(lines) <= MAX_FILE_LIST:
        raise ExecutorBlocked("CHECKSUM_LIST_INVALID")
    seen = set()
    for line in lines:
        if len(line) < 67 or line[64:66] != "  " or not HASH.fullmatch(line[:64]):
            raise ExecutorBlocked("CHECKSUM_ENTRY_INVALID")
        filename = line[66:]
        parts = filename.split("/")
        if (not filename or filename.startswith("/")
                or "\\" in filename or any(p in ("", ".", "..") for p in parts)
                or any(ord(c) < 32 for c in filename)
                or filename in seen or filename == name):
            raise ExecutorBlocked("CHECKSUM_PATH_UNSAFE")
        seen.add(filename)
        path = folder / filename
        if not path.is_file() or path.is_symlink():
            raise ExecutorBlocked("CHECKSUM_FILE_MISSING")
        # The checksum path must not pass through any symlinked directory.
        if any((folder.joinpath(*parts[:n])).is_symlink()
               for n in range(1, len(parts))):
            raise ExecutorBlocked("CHECKSUM_PATH_UNSAFE")
        if _sha(path) != line[:64]:
            raise ExecutorBlocked("CHECKSUM_MISMATCH")
    actual = set()
    for p in folder.rglob("*"):
        if p.is_symlink():
            raise ExecutorBlocked("CHECKSUM_SYMLINK")
        if p.is_file():
            rel = p.relative_to(folder).as_posix()
            if rel != name:
                actual.add(rel)
    if require_complete and seen != actual:
        raise ExecutorBlocked("CHECKSUM_LIST_INCOMPLETE")
    return len(seen)


def verify_receipt(path: Path, source_sha: str):
    """A receipt is valid only when produced by the official tests on this SHA."""
    receipt = _json_file(path)
    if receipt.get("sourceCommit") != source_sha or receipt.get("status") != "passed":
        raise ExecutorBlocked("RECEIPT_SOURCE_OR_STATUS_MISMATCH")
    checks = receipt.get("checks")
    names = {"build", "application-tests", "distribution-helper", "operations"}
    if (not isinstance(checks, list) or len(checks) != 4
            or any(not isinstance(x, dict) or not isinstance(x.get("name"), str)
                   or x.get("status") != "passed" for x in checks)
            or {x["name"] for x in checks} != names):
        raise ExecutorBlocked("RECEIPT_CHECKS_MISSING")
    schemas = receipt.get("schemaChecksums")
    scopes = {"tenant", "control", "interest", "support", "legal"}
    if (not isinstance(schemas, dict) or set(schemas) != scopes
            or any(not isinstance(records, list) or not records
                   or any(not isinstance(item, dict)
                          or not isinstance(item.get("version"), int)
                          or not isinstance(item.get("name"), str)
                          or not HASH.fullmatch(str(item.get("checksum", "")))
                          for item in records)
                   for records in schemas.values())):
        raise ExecutorBlocked("RECEIPT_SCHEMA_CHECKSUMS_MISSING")
    if receipt.get("physicalValidation") != "not-performed":
        raise ExecutorBlocked("RECEIPT_PHYSICAL_VALIDATION_UNTRUSTED")
    return {"sha256": _sha(path), "check_names": sorted(names)}


def verify_package_release(path: Path, source_sha: str, version: str, distribution: str):
    meta = _json_file(path)
    if (not isinstance(meta.get("validation"), dict)
            or meta.get("sourceCommit") != source_sha
            or meta.get("releaseVersion") != version
            or meta.get("distribution") != distribution
            or meta.get("validation", {}).get("sourceCommit") != source_sha
            or meta.get("validation", {}).get("status") != "passed"
            or not isinstance(meta.get("schemaChecksums"), dict)):
        raise ExecutorBlocked("PACKAGE_PROVENANCE_MISMATCH")
    if distribution == "home-assistant":
        if (meta.get("packageKind") != "home-assistant-precompiled-aarch64"
                or meta.get("architecture") != "linux/arm64"
                or meta.get("runtimeSourceCommit") != source_sha
                or meta.get("addonSlug") != "artesaos_piloto"):
            raise ExecutorBlocked("HA_RUNTIME_OR_ARCH_MISMATCH")
    elif distribution == "debian":
        if (meta.get("packageKind") != "compose-with-image"
                or meta.get("imageArchitecture") != "linux/amd64"
                or meta.get("imageSourceCommit") != source_sha
                or not HASH.fullmatch(str(meta.get("imageArchiveSha256", "")))):
            raise ExecutorBlocked("DEBIAN_RUNTIME_OR_ARCH_MISMATCH")
    else:
        raise ExecutorBlocked("UNAPPROVED_DISTRIBUTION")
    return meta


def isolated_builder_preflight(source: Path, distribution: Path, output: Path,
                               policy_path: Path, source_sha: str, version: str):
    """Enforce baseline checks; a policy file alone cannot certify VM isolation."""
    if sys.platform != "linux" or os.geteuid() == 0:
        raise ExecutorBlocked("DEDICATED_NON_ROOT_LINUX_VM_REQUIRED")
    if any(k in os.environ for k in ("SUPERVISOR_TOKEN", "HASSIO_TOKEN",
                                     "GITHUB_TOKEN", "GH_TOKEN", "RUNNER_AUTH_TOKEN")):
        raise ExecutorBlocked("PRODUCTION_CREDENTIAL_ENV_DETECTED")
    if Path("/data/options.json").exists() or Path("/run/s6").exists():
        raise ExecutorBlocked("HOME_ASSISTANT_ENVIRONMENT_REJECTED")
    if any(k in os.environ for k in ("DOCKER_HOST", "DOCKER_CONTEXT",
                                     "DOCKER_TLS_VERIFY", "DOCKER_CERT_PATH")):
        raise ExecutorBlocked("REMOTE_DOCKER_NOT_ALLOWED")
    policy = _json_file(policy_path, 8192)
    if (set(policy) != {"kind", "host_role", "network_policy", "production_access",
                        "docker_endpoint", "source_repository", "expected_source_sha",
                        "expected_version", "npm_cache"}
            or policy["kind"] != "factory-runner-disposable-builder-v1"
            or policy["host_role"] != "dedicated_disposable_vm"
            or policy["network_policy"] != "blocked_external"
            or policy["production_access"] is not False
            or policy["docker_endpoint"] != "unix:///var/run/docker.sock"
            or policy["source_repository"] != "mmcromero/fabricacao_e_orcamentos"
            or policy.get("expected_source_sha") != source_sha
            or policy.get("expected_version") != version
            or policy.get("npm_cache") != "/var/cache/factory-runner/npm"):

        raise ExecutorBlocked("BUILDER_POLICY_NOT_APPROVED")
    for path in (source, distribution, policy_path):
        if not path.exists() or path.is_symlink() or path.resolve() != path.absolute():
            raise ExecutorBlocked("UNSAFE_INPUT_PATH")
    if output.exists() or output.is_symlink() or output.parent.is_symlink():
        raise ExecutorBlocked("OUTPUT_MUST_NOT_EXIST")
    parent = output.parent.resolve()
    if not parent.is_dir() or parent != output.parent.absolute():
        raise ExecutorBlocked("UNSAFE_OUTPUT_PARENT")
    for root in (source.resolve(), distribution.resolve(), policy_path.resolve()):
        if output.resolve() == root or root in output.resolve().parents or output.resolve() in root.parents:
            raise ExecutorBlocked("OUTPUT_OVERLAPS_INPUT")
    cache = Path(policy["npm_cache"])
    if not cache.is_dir() or cache.is_symlink():
        raise ExecutorBlocked("OFFLINE_NPM_CACHE_REQUIRED")
    # Running source scripts requires an independently verified disposable VM
    # with a restricted firewall, no production routes, preseeded npm/Docker
    # caches and no mounted secrets. The policy attests operator configuration;
    # this software does not claim to inspect the external firewall.


def _run(argv: list[str], *, cwd: Path, timeout: int):
    """Fixed argv only; no shell, no inherited GitHub/HA credentials."""
    env = local_environment()
    env.update({
        "NPM_CONFIG_OFFLINE": "true", "NPM_CONFIG_AUDIT": "false",
        "NPM_CONFIG_FUND": "false", "CI": "true",
        "NPM_CONFIG_CACHE": "/var/cache/factory-runner/npm",
        "HOME": "/tmp",
    })
    try:
        result = subprocess.run(argv, cwd=cwd, env=env, capture_output=True,
                                timeout=timeout, check=False)
    except (subprocess.TimeoutExpired, OSError) as exc:
        raise ExecutorBlocked("BUILDER_STAGE_UNAVAILABLE") from exc
    if result.returncode != 0:
        raise ExecutorBlocked("BUILDER_STAGE_FAILED")
    return result.stdout


def _checked_profile(profile_file: Path):
    profile = load_profile(profile_file)
    if profile.get("mode") != "artesao_package":
        raise ExecutorBlocked("ARTESAO_PROFILE_REQUIRED")
    return profile


def verify_completed_builder(output, expected_sha, version):
    """Revalidate imported artifacts while preserving the CLI exception class."""
    from artesao_artifacts import verify_builder_artifacts
    from artesao_isolated_executor import ExecutorBlocked as ArtifactBlocked
    from release_receipt import ReceiptError
    try:
        return verify_builder_artifacts(output, expected_sha, version)
    except (ArtifactBlocked, ReceiptError) as exc:
        raise ExecutorBlocked('DUAL_ARTIFACT_VERIFICATION_FAILED') from exc


def _docker(args: list[str], *, cwd: Path, timeout: int):
    return _run(["docker", "--host=unix:///var/run/docker.sock", *args],
                cwd=cwd, timeout=timeout)


def _ensure_docker_tags_free(ha_tag: str, debian_tag: str, cwd: Path):
    """On a disposable builder, never replace an existing local Docker tag."""
    _docker(["version", "--format", "{{.Server.Version}}"], cwd=cwd, timeout=60)
    listing = _docker(["image", "ls", "--format",
                       "{{.Repository}}:{{.Tag}}"], cwd=cwd, timeout=60)
    try:
        existing = set(listing.decode("utf-8").splitlines())
    except (UnicodeDecodeError, AttributeError) as exc:
        raise ExecutorBlocked("DOCKER_IMAGE_LIST_INVALID") from exc
    if ha_tag in existing or debian_tag in existing:
        raise ExecutorBlocked("BUILDER_IMAGE_TAG_ALREADY_EXISTS")


def build(source: Path, distribution: Path, profile_file: Path, expected_sha: str,
          output: Path, builder_policy: Path, *, execute: bool):
    """Plan unconditionally; execute only when explicitly requested off-host."""
    source, distribution, output = map(Path, (source, distribution, output))
    if (not source.is_absolute() or not distribution.is_absolute()
            or not output.is_absolute() or not Path(profile_file).is_absolute()):
        raise ExecutorBlocked("ABSOLUTE_PATHS_REQUIRED")
    if builder_policy is not None and not Path(builder_policy).is_absolute():
        raise ExecutorBlocked("ABSOLUTE_BUILDER_POLICY_REQUIRED")
    profile = _checked_profile(Path(profile_file))
    report = evaluate_artesao(source, distribution, expected_sha, profile=profile)
    if report["blocking_errors"]:
        raise ExecutorBlocked("SOURCE_RELEASE_POLICY_BLOCKED")
    if not execute:
        return {"state": "PLAN_ONLY", "report": report, "published": False,
                "installed": False}
    if not SAFE_VERSION.fullmatch(report["candidate_version"]):
        raise ExecutorBlocked("UNAPPROVED_BUILD_VERSION")
    if builder_policy is None:
        raise ExecutorBlocked("ISOLATED_BUILDER_POLICY_REQUIRED")
    isolated_builder_preflight(
        source, distribution, output, Path(builder_policy), expected_sha,
        report["candidate_version"])
    version = report["candidate_version"]
    # Require the caller to stage a clean, dedicated detached checkout.
    if (_run(["git", "-C", str(source), "rev-parse", "HEAD"],
             cwd=source, timeout=60).decode("ascii").strip() != expected_sha):
        raise ExecutorBlocked("BUILDER_CHECKOUT_SHA_MISMATCH")
    # Ignored files may be malicious build inputs. Require a fresh checkout.
    if _run(["git", "-C", str(source), "status", "--porcelain",
             "--ignored", "--untracked-files=all", "-z"],
            cwd=source, timeout=60).strip():
        raise ExecutorBlocked("SOURCE_CHECKOUT_NOT_CLEAN")
    # Docker images are local to this disposable VM; do not replace a tag.
    version = report["candidate_version"]
    _ensure_docker_tags_free(f"artesao-digital-ha:{version}",
                             f"artesao-digital:{version}", source)
    # Do not initialize or modify any production source or distribution.
    output.mkdir(mode=0o700)
    stages = []
    def step(name, argv, cwd, timeout=3600):
        _run(argv, cwd=cwd, timeout=timeout)
        stages.append(name)

    try:
        # Canonical scripts are fixed by five Git blob pins checked by the
        # read-only adapter. Never accept a command from a web request.
        step("offline-npm-ci", ["npm", "ci", "--offline", "--no-audit", "--no-fund"],
             source / "apps/umdoislab")
        receipt = output / "validation.json"
        step("official-validation", ["python3", "-B", "scripts/release-evidence.py",
                                      "--output", str(receipt)], source)
        evidence = verify_receipt(receipt, expected_sha)

        initial = output / "source-exports"
        step("official-dual-source-export",
             ["python3", "-B", "scripts/prepare-distributions.py",
              "--output", str(initial), "--validation", str(receipt)], source)
        verify_sums(initial, require_complete=False)
        ha_source = initial / "artesaos_piloto"
        ha_tag = f"artesao-digital-ha:{version}"
        _docker(["buildx", "build", "--platform", "linux/arm64",
                 "--network=none", "--load", "-t", ha_tag, str(ha_source)],
                cwd=source, timeout=7200)
        stages.append("official-ha-arm64-image-build")
        ha_output = output / "home-assistant"
        step("official-ha-arm64-export",
             ["python3", "-B", "scripts/prepare-ha-aarch64.py",
              "--source", str(ha_source), "--image", ha_tag,
              "--output", str(ha_output)], source)
        verify_sums(ha_output, require_complete=False)
        verify_sums(ha_output / "apps" / "artesaos-piloto")
        ha_release = verify_package_release(
            ha_output / "apps" / "artesaos-piloto" / "release.json",
            expected_sha, version, "home-assistant")

        debian_src = output / "debian-source"
        step("official-debian-source-export",
             ["python3", "-B", "scripts/prepare-distributions.py",
              "--debian-only", "--output", str(debian_src),
              "--validation", str(receipt)], source)
        verify_sums(debian_src, require_complete=False)
        debian_tag = f"artesao-digital:{version}"
        _docker(["buildx", "build", "--platform", "linux/amd64",
                 "--network=none", "--load", "-t", debian_tag,
                 str(debian_src / "artesao-digital-debian" / "app")],
                cwd=source, timeout=7200)
        stages.append("official-debian-amd64-image-build")
        image = output / "debian-image.tar"
        _docker(["save", "--output", str(image), debian_tag],
                cwd=source, timeout=3600)
        stages.append("debian-image-export")

        debian_final = output / "debian-final"
        step("official-debian-image-package",
             ["python3", "-B", "scripts/prepare-distributions.py",
              "--debian-only", "--image-archive", str(image),
              "--output", str(debian_final), "--validation", str(receipt)], source)
        verify_sums(debian_final, require_complete=False)
        verify_sums(debian_final / "artesao-digital-debian")
        debian_release = verify_package_release(
            debian_final / "artesao-digital-debian" / "release.json",
            expected_sha, version, "debian")
        if _sha(debian_final / "artesao-digital-debian" / "image.tar") != debian_release["imageArchiveSha256"]:
            raise ExecutorBlocked("DEBIAN_IMAGE_HASH_MISMATCH")
        trusted_receipt = _json_file(receipt)
        if (ha_release.get("validation") != trusted_receipt
                or debian_release.get("validation") != trusted_receipt):
            raise ExecutorBlocked("PACKAGES_DO_NOT_MATCH_OFFICIAL_RECEIPT")
        if ha_release.get("schemaVersions") != debian_release.get("schemaVersions"):
            raise ExecutorBlocked("DISTRIBUTION_SCHEMA_DIVERGENCE")
        if ha_release.get("schemaChecksums") != debian_release.get("schemaChecksums"):
            raise ExecutorBlocked("DISTRIBUTION_CHECKSUMS_DIVERGENCE")

        # Windows drop-folder ZIP is NOT fabricated. A newly approved
        # version-specific descriptor is a separate explicit dependency.
        descriptor = source / "docs" / "operacao" / "publicacoes" / (version + ".json")
        forja_state = "BLOCKED_MISSING_APPROVED_DESCRIPTOR"
        if descriptor.is_file() and not descriptor.is_symlink():
            metadata = _json_file(descriptor)
            if metadata.get("version") != version or metadata.get("sourceCommit") != expected_sha:
                raise ExecutorBlocked("FORJA_DESCRIPTOR_SOURCE_MISMATCH")
            output_forja = output / "forja-windows"
            step("official-forja-zip-export",
                 ["python3", "-B", "scripts/prepare-forja-windows.py",
                  "--descriptor", str(descriptor),
                  "--package-archive", str(debian_final / ("artesao-digital-debian-" + version + ".tar.gz")),
                  "--output", str(output_forja)], source)
            verify_sums(output_forja)
            forja_state = "PREPARED_NOT_PUBLISHED"

        report_out = {
            "format": "factory-runner-artesao-isolated-builder-v1",
            "state": "PREPARED_LOCAL_ONLY",
            "source_sha": expected_sha, "public_sha_at_preflight": report["public_sha"],
            "version": version, "receipt_sha256": evidence["sha256"],
            "tracks": {
                "home_assistant": {
                    "state": "PREPARED_NOT_PUBLISHED", "arch": "linux/arm64",
                    "archive_sha256": _sha(ha_output / ("artesao-digital-home-assistant-aarch64-" + version + ".tar.gz")),
                },
                "debian": {
                    "state": "PREPARED_NOT_PUBLISHED", "arch": "linux/amd64",
                    "archive_sha256": _sha(debian_final / ("artesao-digital-debian-" + version + ".tar.gz")),
                },
                "forja_windows": {"state": forja_state},
            },
            "completed_stages": stages, "published": False,
            "installed": False, "owner_publication_authorized": False,
            "physical_validation": "not_performed",
        }
        out = output / "FACTORY_ARTESAO_BUILD_REPORT.json"
        with out.open("x", encoding="utf-8") as handle:
            json.dump(report_out, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        verify_completed_builder(output, expected_sha, version)
        return report_out
    except BaseException:
        # Never conceal a partial build as a completed deliverable.
        (output / "INCOMPLETE-NOT-FOR-PUBLICATION").write_text(
            "Builder did not finish verified artifacts. Never publish this directory.\n")
        raise


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--distribution", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--expected-source-sha", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--builder-policy", type=Path)
    parser.add_argument("--execute", action="store_true",
                        help="Run ONLY on a separately approved disposable VM")
    args = parser.parse_args(argv)
    try:
        result = build(args.source, args.distribution, args.profile,
                       args.expected_source_sha, args.output,
                       args.builder_policy, execute=args.execute)
    except (ExecutorBlocked, PreflightError, OSError, ValueError,
            subprocess.SubprocessError) as exc:
        # No commands, credentials, file contents or shell output in errors.
        code = str(exc) if isinstance(exc, ExecutorBlocked) else type(exc).__name__
        print(json.dumps({"state": "BLOCKED", "reason": code[:100],
                          "published": False, "installed": False}))
        return 3
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
