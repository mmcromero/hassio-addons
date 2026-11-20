"""Artesao Digital package adapter: real local Git fixtures, no external services."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import artesao_adapter as adapter
from rc_fastlane import PreflightError, load_profile
import server
import workspace_sync


class ArtesaoPackageAdapterTests(unittest.TestCase):
    schemas = {"tenant": 11, "control": 5, "interest": 2, "support": 2, "legal": 3}

    def git(self, repo, *args):
        return subprocess.check_output(["git", "-C", str(repo), *args],
            stderr=subprocess.DEVNULL, text=True, env={
                "PATH": "/usr/bin:/bin", "HOME": "/nonexistent",
                "GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull
            }).strip()

    def put(self, repo, path, text):
        file = repo / path
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_text(text, encoding="utf-8")

    def put_json(self, repo, path, data):
        self.put(repo, path, json.dumps(data) + "\n")

    def commit(self, repo):
        self.git(repo, "add", ".")
        self.git(repo, "-c", "user.name=Fixture", "-c", "user.email=x@invalid.test",
                 "commit", "-qm", "test")
        sha = self.git(repo, "rev-parse", "HEAD")
        self.git(repo, "update-ref", "refs/remotes/origin/main", sha)
        return sha

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.projects = self.root / "projects"
        self.projects.mkdir()
        self.workspaces = self.root / "workspaces"
        self.source = self.workspaces / "artesao_digital" / "source"
        self.dist = self.workspaces / "artesao_digital" / "distribution"
        for repo in (self.source, self.dist):
            repo.mkdir(parents=True)
            self.git(repo, "init", "-q", "-b", "main")

        self.put_json(self.source, "apps/umdoislab/package.json",
                      {"name": "umdoislab", "version": "0.1.23"})
        self.base_sha = self.commit(self.source)
        self.scripts = {}
        for script in adapter.REQUIRED_SCRIPTS:
            self.put(self.source, script, "raise RuntimeError('NEVER RUN')\n")
        self.put_json(self.source, "apps/umdoislab/pilot/core-base.json",
                      {"version": "0.1.23", "commit": self.base_sha})
        self.source_version = "0.2.0-dev.29"
        self.write_release(self.source_version)
        self.source_sha = self.commit(self.source)
        for script in adapter.REQUIRED_SCRIPTS:
            self.scripts[script] = self.git(self.source, "rev-parse",
                                            self.source_sha + ":" + script)

        self.put(self.dist, "apps/artesaos-piloto/config.yaml",
                 'version: "0.2.0-dev.28"\nslug: artesaos_piloto\n')
        self.put_json(self.dist, "apps/artesaos-piloto/release.json",
                      {"releaseVersion": "0.2.0-dev.28",
                       "sourceCommit": "1"*40, "runtimeSourceCommit": "1"*40,
                       "architecture": "linux/arm64", "distribution": "home-assistant",
                       "packageKind": "home-assistant-precompiled-aarch64",
                       "schemaVersions": self.schemas})
        self.put_json(self.dist, "forja-01/publicacao-atual.json",
                      {"version": "0.2.0-dev.26", "distribution": "debian",
                       "repository": adapter.SOURCE_REPO,
                       "sourceCommit": "2"*40, "sha256": "a"*64})
        self.public_sha = self.commit(self.dist)
        self.profile = {
            "schema_version": 1, "mode": "artesao_package",
            "id": "artesao_digital", "product": "Artesão Digital",
            "source_repo": adapter.SOURCE_REPO,
            "distribution_repo": adapter.DISTRIBUTION_REPO,
            "source_ref": "refs/remotes/origin/main",
            "public_ref": "refs/remotes/origin/main",
            "source_version_file": "apps/umdoislab/artesao-release.json",
            "pilot_manifest_path": "apps/umdoislab/pilot/config.yaml",
            "pilot_base_path": "apps/umdoislab/pilot/core-base.json",
            "base_package_path": "apps/umdoislab/package.json",
            "public_release_path": "apps/artesaos-piloto/release.json",
            "public_manifest_path": "apps/artesaos-piloto/config.yaml",
            "public_debian_path": "forja-01/publicacao-atual.json",
            "trusted_script_blobs": self.scripts,
        }
        self.profile_path = self.projects / "artesao_digital.json"
        self.save_profile()

    def save_profile(self):
        self.profile_path.write_text(json.dumps(self.profile) + "\n")

    def write_release(self, version, schemas=None):
        self.put_json(self.source, "apps/umdoislab/artesao-release.json",
                      {"version": version, "distributions": ["home-assistant", "debian"],
                       "schemaVersions": schemas or self.schemas})
        self.put(self.source, "apps/umdoislab/pilot/config.yaml",
                 'version: "'+version+'"\nslug: artesaos_piloto\narch:\n'
                 '  - aarch64\n  - amd64\n')

    def evaluate(self):
        return adapter.evaluate_artesao(self.source, self.dist, self.source_sha,
                                        profile=load_profile(self.profile_path))

    def test_new_release_plans_both_distributions_without_publishing(self):
        result = self.evaluate()
        self.assertEqual(result["blocking_errors"], [])
        self.assertFalse(result["eligible_for_preparation"])
        self.assertFalse(result["eligible_for_publication"])
        self.assertEqual(result["state"], "PLAN_ONLY_NO_PACKAGE")
        self.assertEqual(result["source_sha"], self.source_sha)
        self.assertEqual(result["public_sha"], self.public_sha)
        self.assertEqual(result["candidate_version"], "0.2.0-dev.29")
        self.assertEqual(result["distribution_tracks"]["home_assistant"]["required_arch"],
                         "linux/arm64")
        self.assertEqual(result["distribution_tracks"]["debian"]["required_arch"],
                         "linux/amd64")
        self.assertIn("VALIDATION_RECEIPT_NOT_VERIFIED", result["errors"])

    def test_current_reused_ha_version_is_blocked(self):
        self.write_release("0.2.0-dev.28")
        self.source_sha = self.commit(self.source)
        result = self.evaluate()
        self.assertIn("VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE",
                      result["blocking_errors"])

    def test_schema_migration_requires_approval(self):
        self.write_release("0.2.0-dev.29",
                           {**self.schemas, "control": self.schemas["control"] + 1})
        self.source_sha = self.commit(self.source)
        self.assertIn("SCHEMA_CHANGE_REQUIRES_EXPLICIT_MIGRATION_APPROVAL",
                      self.evaluate()["blocking_errors"])

    def test_unapproved_recipe_change_is_blocked(self):
        self.put(self.source, "scripts/release-evidence.py", "print('CHANGED')\n")
        self.source_sha = self.commit(self.source)
        self.assertIn("TRUSTED_RELEASE_RECIPE_CHANGED",
                      self.evaluate()["blocking_errors"])

    def test_source_sha_drift_is_blocked(self):
        self.put(self.source, "next.txt", "changed")
        self.commit(self.source)
        with self.assertRaisesRegex(PreflightError, "advanced"):
            self.evaluate()

    def test_invalid_profile_injection_is_rejected(self):
        for altered in ({"source_repo": "other/repo"},
                        {"pilot_manifest_path": "../../etc/passwd"},
                        {"trusted_script_blobs": {"other": "0"*40}},
                        {"extra_script": "evil"}):
            candidate = dict(self.profile, **altered)
            self.profile_path.write_text(json.dumps(candidate))
            with self.assertRaises(PreflightError):
                load_profile(self.profile_path)
        self.save_profile()

    def test_server_preflight_is_read_only_and_prepare_denied(self):
        with (patch.object(server, "PROJECTS_DIR", self.projects),
              patch.object(server, "WORKSPACES_DIR", self.workspaces),
              patch.object(server, "PREPARATIONS_DIR", self.root / "never-create")):
            project = server.listed_projects()["artesao_digital"]
            self.assertEqual(project["preflight"], "verified_dual_distribution_plan")
            self.assertEqual(project["preparation"],
                             "blocked_pending_external_validation")
            report = server.preflight_project("artesao_digital", self.source_sha)
            self.assertEqual(report["candidate_version"], "0.2.0-dev.29")
            blocked = server.prepare_project("artesao_digital", self.source_sha,
                                             "test-operation")
            self.assertFalse(blocked["eligible"])
            self.assertFalse(blocked["published"])
            self.assertIn("VALIDATION_RECEIPT_NOT_VERIFIED", blocked["errors"])
            with self.assertRaises(PreflightError):
                server.prepare_project_declarative("artesao_digital", self.source_sha,
                                                   "test-operation")
        self.assertFalse((self.root / "never-create").exists())

    def test_workspace_sync_preflight_keeps_policy_gate(self):
        report = workspace_sync._verified_profile_report(
            self.profile, self.source, self.dist, self.source_sha)
        self.assertFalse(report["eligible_for_preparation"])
        self.assertEqual(report["project"], "artesao_digital")

    def test_missing_public_release_is_not_fabricated(self):
        self.profile["public_release_path"] = "apps/artesaos-piloto/missing.json"
        self.save_profile()
        with self.assertRaises(PreflightError):
            load_profile(self.profile_path)


if __name__ == "__main__":
    unittest.main()
