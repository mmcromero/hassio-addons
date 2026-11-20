#!/usr/bin/env python3
"""Non-root, no-network synthetic readiness check for declarative preparation.

Runs once during add-on startup, with a clean environment and temporary data.
This is NOT a release, workflow, security sandbox or cgroup certification.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

# Python -I omits the script folder; imports remain fixed to the installed image.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from declarative_export import DeclarativeExportError, prepare_declarative

def main():
    if os.geteuid() == 0:
        print("[DECLARATIVE] BLOCKED: expected non-root service UID", flush=True)
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="factory-declarative-", dir="/tmp") as scratch:
            root = Path(scratch)
            source = root / "source"
            source.mkdir(mode=0o700)
            git_env = {
                "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                "GIT_CONFIG_NOSYSTEM": "1",
                "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_OPTIONAL_LOCKS": "0",
            }
            def git(*arguments):
                p = subprocess.run(
                    ["git", "-C", str(source), *arguments],
                    env=git_env, stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                    check=False, timeout=8)
                if p.returncode:
                    raise DeclarativeExportError("git_fixture_failed")
                return p.stdout.decode("ascii", errors="strict").strip()
            git("init", "-q")
            (source / "config.yaml").write_text('version: "0.0.1"\n', encoding="utf-8")
            (source / "package.json").write_text('{"version":"0.0.1"}\n', encoding="utf-8")
            git("add", "config.yaml", "package.json")
            git("-c", "user.name=Factory Probe", "-c", "user.email=probe@example.invalid",
                "commit", "-qm", "synthetic probe")
            sha = git("rev-parse", "HEAD")
            if not re.fullmatch(r"[a-f0-9]{40}", sha):
                raise DeclarativeExportError("invalid_fixture_commit")
            output = root / "package"
            report = prepare_declarative(
                source, sha, output,
                {"fixture/config.yaml": "config.yaml",
                 "fixture/package.json": "package.json"},
                expected_version="0.0.1", project="fixture")
            if (report.get("state") != "PREPARED_NOT_PUBLISHED"
                    or len(report.get("files", [])) != 2):
                raise DeclarativeExportError("invalid_fixture_report")
            for item in report["files"]:
                destination = output / item["path"]
                if (not destination.is_file() or destination.is_symlink()
                        or hashlib.sha256(destination.read_bytes()).hexdigest()
                        != item["sha256"]):
                    raise DeclarativeExportError("fixture_integrity_failed")
            parsed = json.loads((output / "DECLARATIVE_BUNDLE_MANIFEST.json").read_text())
            if parsed["commit"] != sha or parsed["state"] != "PREPARED_NOT_PUBLISHED":
                raise DeclarativeExportError("invalid_fixture_manifest")
        print("[DECLARATIVE] PASS: non-root Git-blob preparation and SHA-256 verification; project workspaces NOT tested", flush=True)
        return 0
    except (DeclarativeExportError, OSError, subprocess.TimeoutExpired,
            ValueError, KeyError, TypeError) as exc:
        print("[DECLARATIVE] BLOCKED: synthetic probe (" + type(exc).__name__ + ")", flush=True)
        return 2

if __name__ == "__main__":
    raise SystemExit(main())
