"""Pinned-source planning comparison, no working tree, Git process, or writes.

Exporter source: pager-virtual/scripts/export-distribution.py blob
e67c816405707545b21b0e6863814ada7b26d0f1.
Fixture contains metadata only from source commit a4b97c1...
"""
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from trusted_export_plan import plan_files, PlanBlocked

FIXTURE = ROOT / "tests/fixtures/avisaqui_git_tree_20261119.json"

# Explicit script-derived mappings. Keep these independent from fixture's
# expected_mapping, so this test detects rule drift instead of copying answer.
EXACT = {
    ".dockerignore": ".dockerignore",
    "package.json": "package.json",
    "package-lock.json": "package-lock.json",
    "Dockerfile": "Dockerfile",
    "config.yaml": "config.yaml",
    "run.sh": "run.sh",
    "scripts/bootstrap-admin.js": "scripts/bootstrap-admin.js",
    "docs/AVISAQUI-HTTPS-001-nginx.conf.example": "docs/AVISAQUI-HTTPS-001-nginx.conf.example",
    "docs/AVISAQUI-HTTPS-001-publicacao.md": "docs/AVISAQUI-HTTPS-001-publicacao.md",
    "docs/AVISAQUI_PRINT_HA_001.md": "docs/AVISAQUI_PRINT_HA_001.md",
    "docs/AVISAQUI-PONG-014.md": "docs/AVISAQUI-PONG-014.md",
    "distribution/README.md": "README.md",
    "distribution/CHANGELOG.md": "CHANGELOG.md",
    "distribution/AGENTS.md": "AGENTS.md",
    "distribution/RC-001.md": "docs/RC-001.md",
    "distribution/hotfix-0.1.16/README.md": "docs/WEBUI-CATALOGO-016.md",
    "distribution/hotfix-0.1.17/README.md": "docs/WEBUI-PROXY-017.md",
    "scripts/impressao_windows/cliente_pair_v1.py": "scripts/impressao_windows/cliente_pair_v1.py",
    "scripts/impressao_windows/pair_v1.py": "scripts/impressao_windows/pair_v1.py",
    "distribution/governance/package-policy.json": ".governance/package-policy.json",
    ".governance/approved-pager-ci.patch": ".governance/approved-pager-ci.patch",
    "distribution/governance/product.gitignore": ".gitignore",
    "scripts/check-package-policy.py": "scripts/check-package-policy.py",
    "tests/package-policy.test.py": "tests/package-policy.test.py",
    "distribution/governance/GOVERNANCA-DO-PACOTE.md": "docs/GOVERNANCA-DO-PACOTE.md",
}
RULES = {
    "prefix": "pager-virtual/",
    "include_prefixes": ["src/", "tests/fixtures/"],
    "include_suffixes": [{"prefix": "tests/", "suffix": ".test.js"}],
    "exact": EXACT,
    "allowed_shared_paths": [],
}


class RealTreePlanTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))
        assert cls.fixture["schema_version"] == 1
        assert cls.fixture["source_commit"] == "a4b97c1d353e6111dc48933806f13c77d0dec6f9"
        assert cls.fixture["exporter_blob_sha"] == "e67c816405707545b21b0e6863814ada7b26d0f1"

    def plan(self, entries=None, rules=None):
        return plan_files(
            self.fixture["entries"] if entries is None else entries,
            RULES if rules is None else rules,
            max_files=200, max_file_bytes=256000, max_total_bytes=2_000_000)

    def test_mapping_equals_exporter_fixed_snapshot(self):
        actual=self.plan()
        self.assertEqual(
            [(x["source"],x["destination"]) for x in actual["files"]],
            [(x["source"],x["destination"]) for x in
             sorted(self.fixture["expected_mapping"],key=lambda x:x["destination"])])
        self.assertEqual(len(actual["files"]),135)
        self.assertEqual(actual["total_bytes"],995337)
        self.assertFalse(actual["requires_shared_path_approval"])
        self.assertFalse(actual["published"])

    def test_shared_workflow_separate_and_requires_approval(self):
        shared=self.fixture["shared_mapping"][0]
        rules={"prefix":"pager-virtual/","include_prefixes":[],
               "include_suffixes":[],"exact":{shared["source"]:shared["destination"]},
               "allowed_shared_paths":[shared["destination"]]}
        result=self.plan(rules=rules)
        self.assertEqual(len(result["files"]),1)
        self.assertEqual(result["files"][0]["destination"],shared["destination"])
        self.assertTrue(result["requires_shared_path_approval"])

    def test_all_selected_paths_are_regular_files(self):
        bypath={x["path"]:x for x in self.fixture["entries"]}
        for mapping in self.fixture["expected_mapping"]:
            entry=bypath[mapping["source"]]
            self.assertEqual(entry["type"],"blob")
            self.assertIn(entry["mode"],("100644","100755"))

    def test_pinned_snapshot_has_no_missing_sources(self):
        bypath={x["path"] for x in self.fixture["entries"]}
        self.assertTrue(set(EXACT).issubset(bypath))
        self.assertTrue({x["source"] for x in self.fixture["expected_mapping"]}.issubset(bypath))

    def test_symlink_in_selected_file_denied(self):
        entries=[dict(x) for x in self.fixture["entries"]]
        for x in entries:
            if x["path"]=="src/public/cliente.html":
                x["mode"]="120000"
        with self.assertRaises(PlanBlocked):
            self.plan(entries=entries)

    def test_single_blob_size_over_limit_denied(self):
        entries=[dict(x) for x in self.fixture["entries"]]
        for x in entries:
            if x["path"]=="src/public/cliente.html":
                x["size"]=256001
        with self.assertRaises(PlanBlocked):
            self.plan(entries=entries)

    def test_shared_workflow_cannot_be_auto_added_without_gate(self):
        shared=self.fixture["shared_mapping"][0]
        rules={"prefix":"pager-virtual/","include_prefixes":[],
               "include_suffixes":[],"exact":{shared["source"]:shared["destination"]},
               "allowed_shared_paths":[]}
        actual=self.plan(rules=rules)
        self.assertFalse(actual["requires_shared_path_approval"])
        self.assertEqual(actual["files"][0]["destination"],
                         "pager-virtual/"+shared["destination"])
        # Without approval this is merely an internal product path, not the real
        # global workflow. The real workflow write must be a separate action.


if __name__ == "__main__":
    unittest.main()
