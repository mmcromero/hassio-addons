"""Read-only FR-EXEC-001 impact and proportional-selection regressions."""
import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import execution_planner as planner
import execution_evidence as evidence


PROFILE = {
    "id": "sample",
    "source_repo": "example/sample",
    "source_ref": "refs/remotes/origin/development",
    "distribution_repo": "example/distribution",
    "public_ref": "refs/remotes/origin/main",
    "rc_ref": "refs/remotes/origin/release-candidate",
}


def run_git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True,
                          capture_output=True, text=True).stdout.strip()


class ExecutionPlannerTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name)
        self.source = self.root / "source"
        self.source.mkdir()
        run_git(self.source, "init")
        run_git(self.source, "config", "user.email", "factory-runner-tests@example.invalid")
        run_git(self.source, "config", "user.name", "Factory Runner Tests")
        self._write("src/core.py", "VALUE = 1\n")
        self._write("src/auth.py", "from core import VALUE\nAUTH = VALUE\n")
        self._write("tests/test_auth.py", "def test_auth(): pass\n")
        self._write("tests/test_core.py", "def test_core(): pass\n")
        run_git(self.source, "add", ".")
        run_git(self.source, "commit", "-m", "base")
        self.base_sha = run_git(self.source, "rev-parse", "HEAD")
        self.catalog_dir = self.root / "catalogs"
        self.catalog_dir.mkdir()
        self.catalog = {
            "schema_version": 1, "project_id": "sample",
            "catalog_version": "1.0.0", "environment_id": "sample-ha-arm64",
            "modules": [
                {"id": "core", "path_patterns": ["src/core.py"],
                 "depends_on": [], "risk_tags": ["core"]},
                {"id": "auth", "path_patterns": ["src/auth.py"],
                 "depends_on": ["core"], "risk_tags": ["security"]},
            ],
            "tests": [
                {"id": "sample.auth", "version": "1", "path": "tests/test_auth.py",
                 "modules": ["auth"], "kind": "unit", "risk": "high",
                 "requires_sandbox": True, "artifact_required": False, "operation_types": []},
                {"id": "sample.core", "version": "1", "path": "tests/test_core.py",
                 "modules": ["core"], "kind": "unit", "risk": "normal",
                 "requires_sandbox": True, "artifact_required": False, "operation_types": []},
            ],
        }
        (self.catalog_dir / "sample.json").write_text(
            json.dumps(self.catalog), encoding="utf-8")
        self.executions = self.root / "executions"
        self.executions.mkdir(mode=0o700)

    def _write(self, path, text):
        target = self.source / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def _target(self, path="src/auth.py", text="from core import VALUE\nAUTH = VALUE + 1\n"):
        self._write(path, text)
        run_git(self.source, "add", ".")
        run_git(self.source, "commit", "-m", "target")
        return run_git(self.source, "rev-parse", "HEAD")

    def _contract(self, target_sha, *, base_sha=None, include=None):
        return {
            "schema_version": "FR-EXEC-001/v1",
            "execution_id": str(uuid.uuid4()),
            "created_at": "2026-11-24T18:00:00Z",
            "objective": "Planejar validação proporcional",
            "project": "sample",
            "source": {
                "repository": "example/sample",
                "ref": "refs/remotes/origin/development",
                "sha": target_sha,
                "base_sha": base_sha,
            },
            "scope": {
                "include_paths": include or [],
                "exclude_paths": [],
                "constraints": ["Não executar código de projeto"],
            },
            "requested_operations": ["analyze", "plan", "test"],
            "authorization": {"reference": None, "declared_operations": ["analyze", "plan", "test"]},
            "destinations": [],
            "acceptance_criteria": ["Selecionar testes afetados"],
            "limits": {
                "timeout_seconds": 120, "max_changed_files": 100,
                "network_policy": "read_only", "data_access": "approved_workspace",
                "max_cost_usd": None,
            },
        }

    def _plan(self, contract):
        marker = {"source_sha": contract["source"]["sha"],
                  "source_repo": PROFILE["source_repo"]}
        return planner.plan_execution(
            contract, PROFILE, self.source, marker,
            executions_dir=self.executions, catalog_dir=self.catalog_dir)

    def test_local_change_selects_only_affected_test(self):
        target = self._target()
        plan, reused = self._plan(self._contract(target, base_sha=self.base_sha))
        self.assertFalse(reused)
        self.assertEqual([x["test_id"] for x in plan["tests"]["selected"]], ["sample.auth"])
        self.assertEqual([x["test_id"] for x in plan["tests"]["omitted"]], ["sample.core"])
        self.assertFalse(plan["tests"]["execution_performed"])
        self.assertEqual(plan["status"], "PARTIAL")
        self.assertEqual(plan["impact"]["affected_modules"], ["auth"])

    def test_dependency_change_selects_dependent_module_tests(self):
        target = self._target("src/core.py", "VALUE = 2\n")
        plan, _ = self._plan(self._contract(target, base_sha=self.base_sha))
        self.assertEqual({x["test_id"] for x in plan["tests"]["selected"]},
                         {"sample.auth", "sample.core"})

    def test_unknown_path_falls_back_to_full_regression(self):
        target = self._target("unknown.py", "UNKNOWN = True\n")
        plan, _ = self._plan(self._contract(target, base_sha=self.base_sha))
        self.assertTrue(plan["impact"]["impact_unknown"])
        self.assertEqual({x["test_id"] for x in plan["tests"]["selected"]},
                         {"sample.auth", "sample.core"})

    def test_scope_escape_blocks_plan(self):
        target = self._target("src/core.py", "VALUE = 2\n")
        plan, _ = self._plan(self._contract(
            target, base_sha=self.base_sha, include=["src/auth.py"]))
        self.assertEqual(plan["status"], "BLOCKED_SCOPE")
        self.assertEqual(plan["impact"]["scope_outside_paths"], ["src/core.py"])

    def test_missing_base_sha_selects_full_regression(self):
        target = self._target()
        plan, _ = self._plan(self._contract(target, base_sha=None))
        self.assertTrue(plan["impact"]["impact_unknown"])
        self.assertEqual(len(plan["tests"]["selected"]), 2)

    def test_same_contract_returns_same_persisted_plan(self):
        target = self._target()
        contract = self._contract(target, base_sha=self.base_sha)
        first, first_reused = self._plan(contract)
        second, second_reused = self._plan(contract)
        self.assertFalse(first_reused)
        self.assertTrue(second_reused)
        self.assertEqual(first, second)

    def test_same_id_with_changed_contract_is_rejected(self):
        target = self._target()
        contract = self._contract(target, base_sha=self.base_sha)
        self._plan(contract)
        changed = dict(contract)
        changed["objective"] = "Objetivo diferente"
        with self.assertRaises(Exception):
            self._plan(changed)

    def test_exact_evidence_is_reused_without_running_test(self):
        target = self._target()
        catalog, _ = planner.load_catalog("sample", self.catalog_dir)
        tree = planner._git_tree(self.source, target)
        test = catalog["tests"][0]
        unit, dependencies = planner._test_binding(test, catalog, tree)
        evidence.record_evidence(
            self.executions / "evidence.jsonl",
            test_id=test["id"], test_version=test["version"],
            source_sha=target, unit_digest=unit, dependency_digest=dependencies,
            environment_id=catalog["environment_id"], artifact_digest=None,
            executor="ha-supervisor",
        )
        plan, _ = self._plan(self._contract(target, base_sha=self.base_sha))
        self.assertEqual([x["test_id"] for x in plan["tests"]["reused"]], ["sample.auth"])
        self.assertNotIn("sample.auth", [x["test_id"] for x in plan["tests"]["selected"]])
        self.assertFalse(plan["tests"]["execution_performed"])

    def test_saved_plan_is_readable_and_receipt_tampering_is_detected(self):
        target = self._target()
        contract = self._contract(target, base_sha=self.base_sha)
        plan, _ = self._plan(contract)
        loaded = planner.get_execution(self.executions, contract["execution_id"])
        self.assertEqual(loaded, plan)
        path = self.executions / contract["execution_id"] / "plan.json"
        tampered = json.loads(path.read_text(encoding="utf-8"))
        tampered["receipt"]["status"] = "FORGED"
        path.write_text(json.dumps(tampered), encoding="utf-8")
        with self.assertRaises(planner.PlannerError):
            planner.get_execution(self.executions, contract["execution_id"])

    def test_plan_read_does_not_create_missing_execution(self):
        with self.assertRaises(planner.PlannerError):
            planner.get_execution(self.executions, str(uuid.uuid4()))


if __name__ == "__main__":
    unittest.main()
