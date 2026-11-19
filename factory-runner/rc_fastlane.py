#!/usr/bin/env python3
"""Factory Runner Fastlane v1: deterministic read-only RC preflight.

No AI, Git writes, network requests or publication. Operates on local Git
references of trusted preexisting checkouts. To avoid stale refs, require
the SHA read from the GitHub API as --expected-source-sha.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
VERSION = re.compile(r"""(?m)^version:\s*["']?([^"'\s#]+)""")

class PreflightError(Exception):
    pass

def local_environment(home=None):
    """Local Git/export steps must not inherit API or cloud credentials."""
    keep = ("PATH", "LANG", "LC_ALL", "TMPDIR", "SYSTEMROOT", "WINDIR")
    env = {key: os.environ[key] for key in keep if key in os.environ}
    env.update({"GIT_TERMINAL_PROMPT": "0", "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull, "GIT_OPTIONAL_LOCKS": "0",
                "HOME": str(home) if home is not None else os.devnull})
    return env

def git(root, *args, check=True):
    proc = subprocess.run(
        ["git", "-C", str(root), *args],
        text=True, encoding="utf-8", errors="replace",
        capture_output=True, shell=False, timeout=30, env=local_environment(),
    )
    if check and proc.returncode:
        raise PreflightError("Git operation failed: " + " ".join(args))
    return proc.stdout.strip() if proc.returncode == 0 else None

def git_blob(repo, commit, path):
    if not SHA.fullmatch(commit):
        raise PreflightError("Invalid commit SHA")
    return git(repo, "show", commit + ":" + path)

def read_json(text, label):
    try:
        value = json.loads(text)
    except (ValueError, TypeError) as exc:
        raise PreflightError("Invalid JSON in " + label) from exc
    if not isinstance(value, dict):
        raise PreflightError("Invalid document in " + label)
    return value

def fullsha(repo, ref):
    sha = git(repo, "rev-parse", "--verify", ref + "^{commit}")
    if not SHA.fullmatch(sha or ""):
        raise PreflightError("Missing full SHA: " + ref)
    return sha

def load_profile(path):
    """Read a configured project; never accept commands or arbitrary Git paths."""
    obj = read_json(Path(path).read_text(encoding="utf-8"), "project profile")
    mandatory = ("id", "product", "source_repo", "distribution_repo",
                 "source_ref", "rc_ref", "public_ref", "package_policy_path",
                 "package_json_path", "manifest_path", "provenance_path",
                 "distribution_prefix", "exporter_path", "exporter_git_blob_sha", "allowed_shared_paths")
    if obj.get("schema_version") != 1 or any(k not in obj or obj[k] is None for k in mandatory):
        raise PreflightError("Incomplete or unsupported project profile")
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,47}", obj["id"]):
        raise PreflightError("Invalid project ID")
    if not isinstance(obj["allowed_shared_paths"], list) or not all(
        isinstance(x, str) for x in obj["allowed_shared_paths"]
    ):
        raise PreflightError("Invalid shared path allowlist")
    for key in ("package_policy_path", "package_json_path", "manifest_path",
                "provenance_path", "exporter_path"):
        p = obj[key]
        if not isinstance(p, str) or p.startswith("/") or chr(92) in p or any(
            part in ("", ".", "..") for part in p.split("/")
        ):
            raise PreflightError("Invalid project path: " + key)
    prefix = obj["distribution_prefix"]
    if not isinstance(prefix, str) or not prefix.endswith("/") or prefix.startswith("/") or (
        ".." in prefix.split("/")
    ):
        raise PreflightError("Invalid distribution prefix")
    if not obj["provenance_path"].startswith(prefix):
        raise PreflightError("Provenance must belong to the project prefix")
    if not isinstance(obj["exporter_git_blob_sha"], str) or not SHA.fullmatch(
        obj["exporter_git_blob_sha"]
    ):
        raise PreflightError("Invalid or missing pinned exporter Git blob SHA")
    for name in obj["allowed_shared_paths"]:
        if name.startswith("/") or any(p in ("", ".", "..") for p in name.split("/")):
            raise PreflightError("Unsafe shared path")
    for key in ("source_ref", "rc_ref", "public_ref"):
        if not re.fullmatch(r"refs/remotes/origin/[A-Za-z0-9._/-]+", obj[key]):
            raise PreflightError("Invalid branch reference")
    for key in ("source_repo", "distribution_repo"):
        if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", obj[key]):
            raise PreflightError("Invalid repository")
    return obj

def evaluate(source, distribution, expected_sha, *, profile):
    """Read-only inspection, including history divergence and release gates."""
    source, distribution = Path(source), Path(distribution)
    if not SHA.fullmatch(expected_sha):
        raise PreflightError("--expected-source-sha must contain 40 hex characters")
    development_head = fullsha(source, profile["source_ref"])
    source_sha = fullsha(source, expected_sha)
    public_sha = fullsha(distribution, profile["public_ref"])
    rc_sha = fullsha(source, profile["rc_ref"])
    if source_sha != expected_sha:
        raise PreflightError("Pinned commit does not resolve to expected SHA")

    policy = read_json(git_blob(source, source_sha, profile["package_policy_path"]), "package policy")
    package = read_json(git_blob(source, source_sha, profile["package_json_path"]), "package.json")
    config = git_blob(source, source_sha, profile["manifest_path"])
    match = VERSION.search(config)
    candidate = package.get("version")
    manifest_version = match.group(1) if match else None
    active = policy.get("active_package", {})
    provenance = read_json(
        git_blob(distribution, public_sha, profile["provenance_path"]),
        "distribution provenance"
    )
    published_commit = provenance.get("commit")
    published_version = provenance.get("version")
    errors = []
    warnings = []

    if policy.get("schema_version") != 1 or policy.get("product") != profile["product"]:
        errors.append("INVALID_POLICY")
    if active.get("status") != "open":
        errors.append("NO_OPEN_PACKAGE")
    if active.get("candidate_version") != candidate:
        errors.append("PACKAGE_VERSION_MISMATCH")
    if not isinstance(candidate, str) or manifest_version != candidate:
        errors.append("SOURCE_MANIFEST_VERSION_MISMATCH")
    if published_commit != source_sha and published_version == candidate:
        errors.append("VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE")
    if not SHA.fullmatch(str(published_commit)):
        errors.append("INVALID_PUBLIC_PROVENANCE")
    if active.get("branches", {}).get(profile["source_repo"]) != profile["rc_ref"].removeprefix("refs/remotes/origin/"):
        errors.append("PRIVATE_RC_BRANCH_NOT_REGISTERED")

    ancestor = subprocess.run(
        ["git", "-C", str(source), "merge-base", "--is-ancestor", rc_sha, source_sha],
        capture_output=True, timeout=30, check=False, env=local_environment()
    )
    frozen = False
    if ancestor.returncode != 0:
        reverse = subprocess.run(
            ["git", "-C", str(source), "merge-base", "--is-ancestor", source_sha, rc_sha],
            capture_output=True, timeout=30, check=False, env=local_environment())
        if reverse.returncode == 0:
            source_tree = git(source, "rev-parse", source_sha + "^{tree}")
            rc_tree = git(source, "rev-parse", rc_sha + "^{tree}")
            frozen = bool(source_tree and source_tree == rc_tree)
        if not frozen:
            errors.append("PRIVATE_RC_NOT_ANCESTOR_OF_DEVELOPMENT")
    if frozen:
        warnings.append("PRIVATE_RC_ALREADY_FROZEN_AT_SOURCE_TREE")
    if development_head != source_sha:
        warnings.append("DEVELOPMENT_ADVANCED_AFTER_PIN")
        if not frozen:
            errors.append("PINNED_SHA_NOT_FROZEN_IN_PRIVATE_RC")
    relation = git(source, "rev-list", "--left-right", "--count",
                   rc_sha + "..." + source_sha)
    if relation and len(relation.split()) == 2:
        behind, ahead = (int(v) for v in relation.split())
    else:
        raise PreflightError("Unable to compare development and RC")
    if (behind or ahead) and not frozen:
        warnings.append("BRANCH_CONTENT_DIFFERS")

    return {
        "tool": "FACTORY-RUNNER-ESTEIRA-001",
        "project": profile["id"],
        "source_repo": profile["source_repo"],
        "distribution_repo": profile["distribution_repo"],
        "mode": "read_only",
        "source_sha": source_sha,
        "development_head_sha": development_head,
        "private_rc_sha": rc_sha,
        "public_main_sha": public_sha,
        "private_rc_unique_commits": behind,
        "development_unique_commits": ahead,
        "package_id": active.get("id"),
        "package_status": active.get("status"),
        "candidate_version": candidate,
        "published_version": published_version,
        "published_source_sha": published_commit,
        "eligible_for_preparation": not errors,
        "errors": errors,
        "warnings": warnings,
    }

def run_checked(args, *, cwd=None, timeout=240, env=None, preserve_output=False):
    """No shell, bounded execution and no output of secret-bearing command lines."""
    result = subprocess.run(
        args, cwd=cwd, env=env, capture_output=True, text=True,
        encoding="utf-8", errors="replace", shell=False, timeout=timeout
    )
    if result.returncode:
        # Intentionally do not include stdout/stderr; external commands may
        # display credentials or private configuration on failure.
        raise PreflightError("Preparation step failed: " + str(args[0]) + " (exit " +
                             str(result.returncode) + ")")
    return result.stdout if preserve_output else result.stdout.strip()

def prepare(source, distribution, report, output, *, profile):
    """Create an isolated distribution candidate; never commit or push.

    Caller must separately authorize Git publication. No production secrets
    or local source worktree files are copied; only committed Git objects.
    """
    if not report["eligible_for_preparation"]:
        raise PreflightError("Not eligible for preparation: " + ",".join(report["errors"]))
    output = Path(output).absolute()
    source = Path(source).resolve()
    distribution = Path(distribution).resolve()
    if output.exists() or output.is_symlink():
        raise PreflightError("Output directory already exists")
    if not output.parent.is_dir():
        raise PreflightError("Output parent does not exist")
    parent = output.parent.resolve()
    if output == source or output == distribution:
        raise PreflightError("Output overlaps repository")
    if source == parent or source in parent.parents:
        raise PreflightError("Output cannot be inside source repository")
    if distribution == parent or distribution in parent.parents:
        raise PreflightError("Output cannot be inside distribution repository")
    # Git and exporter use local checkouts only; no cloud auth is required.
    # Whitelist inherited variables, rather than guessing secret variable names.
    with tempfile.TemporaryDirectory(prefix="factory-rc-source-") as tmp:
        home = Path(tmp) / "home"
        home.mkdir(mode=0o700)
        safe_env = local_environment(home)
        source_snapshot = Path(tmp) / "source"
        run_checked(["git", "clone", "--no-hardlinks", "--", str(source),
                     str(source_snapshot)], timeout=180, env=safe_env)
        run_checked(["git", "-C", str(source_snapshot), "checkout", "--detach",
                     report["source_sha"]], env=safe_env)
        run_checked(["git", "clone", "--no-hardlinks", "--", str(distribution),
                     str(output)], timeout=180, env=safe_env)
        try:
            run_checked(["git", "-C", str(output), "checkout", "-b",
                         "runner/prepared-" + report["source_sha"][:12],
                         report["public_main_sha"]], env=safe_env)
            exporter = source_snapshot / profile["exporter_path"]
            if not exporter.is_file() or exporter.is_symlink():
                raise PreflightError("Profile exporter is unavailable or unsafe")
            exporter_blob = run_checked(
                ["git", "-C", str(source_snapshot), "rev-parse", "HEAD:" +
                 profile["exporter_path"]], env=safe_env)
            if exporter_blob != profile["exporter_git_blob_sha"]:
                raise PreflightError("Exporter SHA differs from approved project profile")
            # Isolated Python mode prevents a source checkout from shadowing
            # stdlib modules through its scripts directory or PYTHONPATH.
            args = [sys.executable, "-I", str(exporter), "--commit", report["source_sha"],
                    "--target", str(output)]
            run_checked(args, cwd=source_snapshot, env=safe_env, timeout=240)
            run_checked(args + ["--verify"], cwd=source_snapshot,
                        env=safe_env, timeout=240)
            status = run_checked(["git", "-C", str(output), "status", "--porcelain=v1",
                                  "--no-renames", "--untracked-files=all", "-z"],
                                 preserve_output=True, env=safe_env)
            # --porcelain -z is a NUL-delimited sequence; no shell interpretation.
            paths = []
            entries = status.split("\0")
            for line in entries:
                if not line:
                    continue
                if len(line) < 4:
                    raise PreflightError("Invalid Git status entry")
                path = line[3:]
                if not (path.startswith(profile["distribution_prefix"]) or
                        path in profile["allowed_shared_paths"]):
                    raise PreflightError("Export changed a forbidden path")
                paths.append(path)
            prepared = dict(report)
            prepared.update({
                "mode": "isolated_preparation",
                "state": "PREPARED_NOT_PUBLISHED",
                "export_verified": True,
                "tests_executed": False,
                "changed_files": len(paths),
                "changed_paths": sorted(paths),
                "published": False,
                "approval": "required_before_any_remote_write",
            })
            report_file = output.parent / (output.name + ".report.json")
            if report_file.exists() or report_file.is_symlink():
                raise PreflightError("Preparation report already exists")
            with report_file.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(prepared, ensure_ascii=False, indent=2) + "\n")
            return prepared
        except Exception:
            # Failed outputs remain local only. Caller must not publish them;
            # review and delete them separately after checking ownership.
            raise

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, required=True,
                        help="Configured project profile; e.g. projects/avisaqui.json")
    parser.add_argument("--source", type=Path, required=True,
                        help="Existing local source repository for selected project")
    parser.add_argument("--distribution", type=Path, required=True,
                        help="Existing local distribution repository for selected project")
    parser.add_argument("--expected-source-sha", required=True,
                        help="Full SHA independently read from GitHub")
    parser.add_argument("--prepare-dir", type=Path,
                        help="New isolated output checkout for verified export; no commit or push")
    parser.add_argument("--json-file", type=Path,
                        help="Optional report destination (must not contain secrets)")
    args = parser.parse_args(argv)
    try:
        project_profile = load_profile(args.profile)
        report = evaluate(args.source, args.distribution, args.expected_source_sha,
                          profile=project_profile)
    except (PreflightError, OSError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"eligible_for_preparation": False, "errors": [str(exc)]},
                         ensure_ascii=False), file=sys.stderr)
        return 2
    encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    print(encoded, end="")
    if args.prepare_dir and report["eligible_for_preparation"]:
        try:
            prepared = prepare(args.source, args.distribution, report, args.prepare_dir,
                               profile=project_profile)
            print(json.dumps(prepared, ensure_ascii=False, indent=2))
        except (PreflightError, OSError, subprocess.TimeoutExpired) as exc:
            print("PREPARATION FAILED: " + str(exc), file=sys.stderr)
            return 4
    if args.json_file:
        if args.json_file.exists() or args.json_file.is_symlink():
            print("Report destination already exists; refusing overwrite", file=sys.stderr)
            return 2
        # Report contains only non-secret identifiers.
        with args.json_file.open("x", encoding="utf-8") as output:
            output.write(encoded)
    return 0 if report["eligible_for_preparation"] else 3

if __name__ == "__main__":
    sys.exit(main())
