"""Offline tests for deterministic RC preflight; no network and no Git mutation."""
import importlib.util
import json
import tempfile
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT if (ROOT / "rc_fastlane.py").is_file() else ROOT / "factory-runner-add-on"
SCRIPT = ADDON / "rc_fastlane.py"
PROFILE = ADDON / "projects" / "avisaqui.json"
sys.path.insert(0, str(ADDON))
CONFIG = json.loads(PROFILE.read_text(encoding="utf-8"))
SPEC = importlib.util.spec_from_file_location("rc_fastlane", SCRIPT)
mod = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(mod)

SOURCE = "a" * 40
RC = "b" * 40
PUBLIC = "c" * 40
PUBLISHED_SOURCE = "d" * 40

def data(status="open", candidate="0.1.20-rc.8", version=None):
    version = version or candidate
    return {
        ".governance/package-policy.json": json.dumps({
            "schema_version": 1, "product": "Avisaqui",
            "active_package": {
                "id": "AVISAQUI-PACOTE-006",
                "status": status,
                "candidate_version": candidate,
                "branches": {"mmcromero/pager-virtual": "release-candidate"}
            }
        }),
        "package.json": json.dumps({"version": version}),
        "config.yaml": 'name: "Pager Virtual"\nversion: "' + version + '"\n',
        "pager-virtual/SOURCE_PROVENANCE.json": json.dumps({
            "commit": PUBLISHED_SOURCE, "version": "0.1.20-rc.7"
        }),
    }

class FastlaneTests(unittest.TestCase):
    def run_evaluation(self, content=None, ancestor=True, relation="0\t4",
                       frozen=False, development_head=None):
        blobs = content or data()
        def fake_git(repo, *args, **kwargs):
            if args[0] == "rev-parse":
                if args[-1].endswith("^{tree}"):
                    return "f" * 40
                if "desenvolvimento" in args[2]:
                    return development_head or SOURCE
                if "release-candidate" in args[2]:
                    return RC
                if args[2].startswith(SOURCE):
                    return SOURCE
                return PUBLIC
            if args[0] == "show":
                return blobs[args[1].split(":", 1)[1]]
            if args[0] == "rev-list":
                return relation
            raise AssertionError("Unplanned Git command " + str(args))
        ancestry_results = [SimpleNamespace(returncode=0 if ancestor else 1)]
        if not ancestor:
            ancestry_results.append(SimpleNamespace(returncode=0 if frozen else 1))
        with patch.object(mod, "git", side_effect=fake_git), patch.object(
            mod.subprocess, "run", side_effect=ancestry_results
        ):
            return mod.evaluate("/tmp/source", "/tmp/store", SOURCE, profile=CONFIG)

    def test_profile_is_independent_from_runner(self):
        self.assertEqual(mod.load_profile(PROFILE)["id"], "avisaqui")
        self.assertEqual(mod.load_profile(PROFILE)["distribution_prefix"], "pager-virtual/")

    def test_profile_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = dict(CONFIG)
            cfg["provenance_path"] = "../secrets.txt"
            profile = Path(folder) / "profile.json"
            profile.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(mod.PreflightError):
                mod.load_profile(profile)

    def test_rc4_profile_rejects_malformed_types_and_ambiguous_paths(self):
        # Trusted profiles must fail closed on invalid JSON types or path forms.
        changes = [
            ("id", 42),
            ("distribution_prefix", "pager-virtual//"),
            ("distribution_prefix", "pager-virtual/../"),
            ("distribution_prefix", "pager-virtual\\\\"),
            ("source_ref", 123),
            ("rc_ref", "refs/remotes/origin/../main"),
            ("rc_ref", "refs/remotes/origin/release//candidate"),
            ("source_repo", []),
        ]
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / "profile.json"
            for key, value in changes:
                with self.subTest(field=key, value=value):
                    cfg = dict(CONFIG)
                    cfg[key] = value
                    profile.write_text(json.dumps(cfg), encoding="utf-8")
                    with self.assertRaises(mod.PreflightError):
                        mod.load_profile(profile)
            cfg = dict(CONFIG)
            cfg["allowed_shared_paths"] = [".github\\\\workflow.yml"]
            profile.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(mod.PreflightError):
                mod.load_profile(profile)

    def test_trusted_declarative_mapping_rejects_unsafe_destinations(self):
        changes = [
            {"../escape": "config.yaml"},
            {"pager-virtual/.git/config": "config.yaml"},
            {"other-addon/config.yaml": "config.yaml"},
            {"pager-virtual/SOURCE_PROVENANCE.json": "config.yaml"},
            {"pager-virtual/config.yaml": "../config.yaml"},
            {"pager-virtual/config.yaml": "config\\\\evil.yaml"},
        ]
        with tempfile.TemporaryDirectory() as folder:
            profile = Path(folder) / "profile.json"
            for mapping in changes:
                with self.subTest(mapping=mapping):
                    cfg = dict(CONFIG)
                    cfg["declarative_mapping"] = mapping
                    profile.write_text(json.dumps(cfg), encoding="utf-8")
                    with self.assertRaises(mod.PreflightError):
                        mod.load_profile(profile)

    def test_trusted_declarative_mapping_is_optional_and_validated(self):
        self.assertNotIn("declarative_mapping", mod.load_profile(PROFILE))
        with tempfile.TemporaryDirectory() as folder:
            cfg = dict(CONFIG)
            cfg["declarative_mapping"] = {"pager-virtual/config.yaml": "config.yaml"}
            profile = Path(folder) / "profile.json"
            profile.write_text(json.dumps(cfg), encoding="utf-8")
            actual = mod.load_profile(profile)
            self.assertEqual(actual["declarative_mapping"]["pager-virtual/config.yaml"],
                             "config.yaml")

    def test_git_status_preserves_leading_porcelain_column(self):
        # An unstaged modification starts with a space, which .strip() destroys.
        payload = " M pager-virtual/config.yaml\\0"
        with patch.object(mod.subprocess, "run",
                          return_value=SimpleNamespace(returncode=0, stdout=payload)):
            actual = mod.run_checked(["git", "status"], preserve_output=True)
            self.assertEqual(actual, payload)
            self.assertEqual(actual.split("\\0")[0][3:],
                             "pager-virtual/config.yaml")

    def test_project_exporter_must_be_pinned(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = dict(CONFIG)
            cfg.pop("exporter_git_blob_sha")
            profile = Path(folder) / "profile.json"
            profile.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(mod.PreflightError):
                mod.load_profile(profile)

    def test_project_exporter_rejects_invalid_blob_hash(self):
        with tempfile.TemporaryDirectory() as folder:
            cfg = dict(CONFIG)
            cfg["exporter_git_blob_sha"] = "invalid"
            profile = Path(folder) / "profile.json"
            profile.write_text(json.dumps(cfg), encoding="utf-8")
            with self.assertRaises(mod.PreflightError):
                mod.load_profile(profile)

    def test_open_new_version_is_eligible_for_preparation(self):
        result = self.run_evaluation()
        self.assertTrue(result["eligible_for_preparation"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["candidate_version"], "0.1.20-rc.8")

    def test_closed_package_is_blocked(self):
        result = self.run_evaluation(data(status="closed_release_candidate_published_pending_homologation"))
        self.assertFalse(result["eligible_for_preparation"])
        self.assertIn("NO_OPEN_PACKAGE", result["errors"])

    def test_reused_version_with_new_source_is_blocked(self):
        result = self.run_evaluation(data(candidate="0.1.20-rc.7"))
        self.assertIn("VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE", result["errors"])

    def test_private_rc_divergence_is_blocked(self):
        result = self.run_evaluation(ancestor=False, relation="2\t18")
        self.assertIn("PRIVATE_RC_NOT_ANCESTOR_OF_DEVELOPMENT", result["errors"])

    def test_frozen_source_remains_valid_when_development_advances(self):
        result = self.run_evaluation(
            ancestor=False, frozen=True, relation="1\t0",
            development_head="e" * 40)
        self.assertTrue(result["eligible_for_preparation"])
        self.assertIn("DEVELOPMENT_ADVANCED_AFTER_PIN", result["warnings"])
        self.assertIn("PRIVATE_RC_ALREADY_FROZEN_AT_SOURCE_TREE", result["warnings"])

    def test_stale_source_without_frozen_rc_is_blocked(self):
        result = self.run_evaluation(
            ancestor=True, development_head="e" * 40)
        self.assertFalse(result["eligible_for_preparation"])
        self.assertIn("PINNED_SHA_NOT_FROZEN_IN_PRIVATE_RC", result["errors"])

    def test_package_manifest_version_mismatch_is_blocked(self):
        result = self.run_evaluation(data(candidate="0.1.20-rc.8", version="0.1.20-rc.9"))
        self.assertIn("PACKAGE_VERSION_MISMATCH", result["errors"])

    def test_wrong_expected_sha_is_rejected(self):
        with self.assertRaises(mod.PreflightError):
            mod.evaluate("/tmp/source", "/tmp/store", "invalid", profile=CONFIG)

    def test_existing_json_report_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as folder:
            report = Path(folder) / "report.json"
            report.write_text("keep", encoding="utf-8")
            with patch.object(mod, "evaluate", return_value={
                "eligible_for_preparation": True, "errors": []
            }):
                ret = mod.main(["--profile", str(PROFILE),
                                "--source", folder, "--distribution", folder,
                                "--expected-source-sha", SOURCE,
                                "--json-file", str(report)])
            self.assertEqual(ret, 2)
            self.assertEqual(report.read_text(encoding="utf-8"), "keep")

    def test_cli_reports_unavailable_sandbox_without_traceback(self):
        with tempfile.TemporaryDirectory() as folder:
            with patch.object(mod,'evaluate',return_value={'eligible_for_preparation':True,'errors':[]}), \
                 patch.object(mod,'prepare',side_effect=mod.SandboxUnavailable('namespace unavailable')):
                ret=mod.main(['--profile',str(PROFILE),'--source',folder,
                    '--distribution',folder,'--expected-source-sha',SOURCE,'--prepare-dir',folder+'/out'])
        self.assertEqual(ret,4)

if __name__ == "__main__":
    unittest.main()
