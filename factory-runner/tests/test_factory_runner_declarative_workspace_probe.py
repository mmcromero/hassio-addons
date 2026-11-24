"""Real Git-object declarative probe tests; no network or product policy writes."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import sys
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from declarative_export import DeclarativeExportError
from declarative_workspace_probe import probe_declarative_workspace


def git(repo, *args):
    env = dict(os.environ)
    env.update({
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_CONFIG_GLOBAL": os.devnull,
        "GIT_TERMINAL_PROMPT": "0",
    })
    result = subprocess.run(
        ["git", "-C", str(repo), *args], env=env,
        capture_output=True, text=True, check=False, timeout=10,
    )
    if result.returncode:
        raise AssertionError(result.stderr)
    return result.stdout.strip()


def make_repo(path, files):
    path.mkdir()
    subprocess.run(["git", "init", "-q", str(path)], check=True, timeout=10)
    git(path, "config", "user.name", "Factory Runner Test")
    git(path, "config", "user.email", "factory-runner-test@example.invalid")
    for name, content in files.items():
        target = path / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    git(path, "add", ".")
    git(path, "commit", "-qm", "fixture")
    return git(path, "rev-parse", "HEAD")


class DeclarativeWorkspaceProbeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="factory-real-probe-test-")
        self.root = Path(self.temp.name)
        self.source = self.root / "source"
        self.distribution = self.root / "distribution"
        self.source_sha = make_repo(self.source, {
            "package.json": json.dumps({"version": "1.2.3"}) + "\n",
            "config.yaml": 'version: "1.2.3"\n',
            "scripts/export-distribution.py": "raise RuntimeError('must not execute')\n",
            "src/index.js": "export const value = 42;\n",
        })
        self.public_sha = make_repo(self.distribution, {
            "README.md": "fixture distribution\n",
        })
        self.exporter_blob = git(self.source, "rev-parse", "HEAD:scripts/export-distribution.py")
        self.profile = {
            "id": "avisaqui",
            "product": "Avisaqui",
            "source_repo": "fixture/source",
            "distribution_repo": "fixture/distribution",
            "distribution_prefix": "pager-virtual/",
            "provenance_path": "pager-virtual/SOURCE_PROVENANCE.json",
            "exporter_path": "scripts/export-distribution.py",
            "exporter_git_blob_sha": self.exporter_blob,
            "package_json_path": "package.json",
            "manifest_path": "config.yaml",
            "allowed_shared_paths": [],
            "declarative_rules": {
                "required": {
                    "pager-virtual/package.json": "package.json",
                    "pager-virtual/config.yaml": "config.yaml",
                },
                "optional": {},
                "include_prefixes": ["src/"],
                "include_suffixes": {},
                "conditional_groups": [],
                "shared_optional": {},
            },
        }

    def tearDown(self):
        self.temp.cleanup()

    def test_real_git_blobs_and_provenance_pass_without_mutating_workspaces(self):
        source_before = git(self.source, "status", "--porcelain")
        distribution_before = git(self.distribution, "status", "--porcelain")
        with patch.object(os, "geteuid", return_value=100):
            result = probe_declarative_workspace(
                "avisaqui", self.source_sha, self.public_sha,
                self.profile, self.source, self.distribution,
            )
        self.assertEqual(result["method"], "real_git_blobs_no_script")
        self.assertFalse(result["persistent_output"])
        self.assertEqual(result["files"], 3)
        self.assertEqual(result["provenance_files"], 3)
        self.assertEqual(result["version"], "1.2.3")
        self.assertEqual(git(self.source, "status", "--porcelain"), source_before)
        self.assertEqual(git(self.distribution, "status", "--porcelain"), distribution_before)

    def test_unpinned_exporter_is_rejected(self):
        self.profile["exporter_git_blob_sha"] = "0" * 40
        with patch.object(os, "geteuid", return_value=100):
            with self.assertRaises(DeclarativeExportError):
                probe_declarative_workspace(
                    "avisaqui", self.source_sha, self.public_sha,
                    self.profile, self.source, self.distribution,
                )

    def test_root_is_rejected(self):
        with patch.object(os, "geteuid", return_value=0):
            with self.assertRaises(DeclarativeExportError):
                probe_declarative_workspace(
                    "avisaqui", self.source_sha, self.public_sha,
                    self.profile, self.source, self.distribution,
                )


if __name__ == "__main__":
    unittest.main()
