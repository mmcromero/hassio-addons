"""Regression tests for the offline declarative exporter (no network)."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from declarative_export import DeclarativeExportError, prepare_declarative, expand_trusted_rules, safe_path


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        def git(*args):
            return subprocess.check_output(["git", "-C", str(self.source), *args],
                                           stderr=subprocess.DEVNULL).decode().strip()
        git("init", "-q")
        git("config", "user.name", "Fixture")
        git("config", "user.email", "fixture@example.invalid")
        (self.source / "config.yaml").write_text("version: 0.0.1\n")
        (self.source / "package.json").write_text('{"version":"0.0.1"}\n')
        git("add", ".")
        git("commit", "-qm", "synthetic")
        self.sha = git("rev-parse", "HEAD")
        self.git = git
        self.out = self.root / "candidate"

    def export(self, mapping=None, **kwargs):
        return prepare_declarative(
            self.source, kwargs.get("sha", self.sha), self.out,
            {"pager-virtual/config.yaml": "config.yaml"} if mapping is None else mapping,
            expected_version="0.0.1", project="avisaqui")

    def test_success_with_hashes_and_no_publish(self):
        m = self.export()
        self.assertEqual(m["state"], "PREPARED_NOT_PUBLISHED")
        self.assertEqual((self.out / "pager-virtual/config.yaml").read_text(),
                         "version: 0.0.1\n")
        self.assertEqual(json.loads((self.out / "DECLARATIVE_BUNDLE_MANIFEST.json").read_text())["commit"], self.sha)

    def test_invalid_source_path_no_output(self):
        with self.assertRaises(DeclarativeExportError):
            self.export({"pager-virtual/ok": "../config.yaml"})
        self.assertFalse(self.out.exists())

    def test_absolute_destination_no_output(self):
        with self.assertRaises(DeclarativeExportError):
            self.export({"/tmp/unsafe": "config.yaml"})
        self.assertFalse(self.out.exists())

    def test_symlink_source_refused(self):
        (self.source / "link").symlink_to("config.yaml")
        self.git("add", "link")
        self.git("commit", "-qm", "link fixture")
        sha = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(DeclarativeExportError, "unsupported_git_object"):
            self.export({"pager-virtual/link": "link"}, sha=sha)
        self.assertFalse(self.out.exists())

    def test_missing_source_no_output(self):
        with self.assertRaises(DeclarativeExportError):
            self.export({"pager-virtual/absent": "absent"})
        self.assertFalse(self.out.exists())

    def test_duplicate_path_parent(self):
        with self.assertRaisesRegex(DeclarativeExportError, "destination_path_collision"):
            self.export({"pager-virtual/x": "config.yaml",
                         "pager-virtual/x/y": "package.json"})
        self.assertFalse(self.out.exists())

    def test_reserved_provenance_blocked(self):
        with self.assertRaises(DeclarativeExportError):
            self.export({"SOURCE_PROVENANCE.json": "config.yaml"})
        self.assertFalse(self.out.exists())

    def test_sha_mismatch_blocked(self):
        with self.assertRaises(DeclarativeExportError):
            self.export(sha="0" * 40)
        self.assertFalse(self.out.exists())

    def test_existing_candidate_preserved(self):
        self.out.mkdir()
        (self.out / "keep.txt").write_text("preserve")
        with self.assertRaisesRegex(DeclarativeExportError, "unsafe_workspace"):
            self.export()
        self.assertEqual((self.out / "keep.txt").read_text(), "preserve")

    def test_dot_git_destination_refused(self):
        with self.assertRaises(DeclarativeExportError):
            self.export({".git/config": "config.yaml"})
        self.assertFalse(self.out.exists())

    def test_mismatched_version_refused(self):
        with self.assertRaisesRegex(DeclarativeExportError, "source_version_mismatch"):
            prepare_declarative(
                self.source, self.sha, self.out,
                {"config.yaml": "config.yaml"},
                expected_version="9.9.9", project="avisaqui")
        self.assertFalse(self.out.exists())

    def test_package_json_version_refused(self):
        with self.assertRaisesRegex(DeclarativeExportError, "source_version_mismatch"):
            prepare_declarative(
                self.source, self.sha, self.out,
                {"package.json": "package.json"},
                expected_version="9.9.9", project="avisaqui")
        self.assertFalse(self.out.exists())

    def test_git_tree_rule_expansion_is_deterministic(self):
        (self.source / "src" / "sub").mkdir(parents=True)
        (self.source / "src" / "sub" / "feature.js").write_text("fixture")
        (self.source / "tests").mkdir()
        (self.source / "tests" / "unit.test.js").write_text("test")
        (self.source / "tests" / "ignored.txt").write_text("ignore")
        self.git("add", ".")
        self.git("commit", "-qm", "selection fixture")
        sha = self.git("rev-parse", "HEAD")
        m = expand_trusted_rules(
            self.source, sha, destination_prefix="demo/",
            required={"demo/config.yaml": "config.yaml"},
            optional={"demo/no-file.txt": "optional-absent.txt"},
            include_prefixes=["src/"], include_suffixes={"tests/": ".test.js"})
        self.assertEqual(m, {
            "demo/config.yaml": "config.yaml",
            "demo/src/sub/feature.js": "src/sub/feature.js",
            "demo/tests/unit.test.js": "tests/unit.test.js"
        })

    def test_git_tree_rule_rejects_matched_symlinks(self):
        (self.source / "src").mkdir()
        (self.source / "src" / "unsafe").symlink_to("../config.yaml")
        self.git("add", ".")
        self.git("commit", "-qm", "symlink fixture")
        sha = self.git("rev-parse", "HEAD")
        with self.assertRaisesRegex(DeclarativeExportError, "unsupported_git_object"):
            expand_trusted_rules(
                self.source, sha, destination_prefix="demo/",
                required={}, optional={}, include_prefixes=["src/"],
                include_suffixes={})

    def test_path_validation(self):
        for x in ("", ".", "..", "./a", "a//b", "a/../b", "a\\b", "a\x00b"):
            with self.subTest(x=x), self.assertRaises(DeclarativeExportError):
                safe_path(x)


if __name__ == "__main__":
    unittest.main()
