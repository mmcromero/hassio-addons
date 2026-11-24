"""Private evidence-ledger binding regressions."""
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import execution_evidence as evidence


class ExecutionEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.root = Path(self.folder.name) / "executions"
        self.root.mkdir(mode=0o700)
        self.ledger = self.root / "evidence.jsonl"
        self.values = {
            "test_id": "avisaqui.auth-api",
            "test_version": "1",
            "source_sha": "a" * 40,
            "unit_digest": "b" * 64,
            "dependency_digest": "c" * 64,
            "environment_id": "avisaqui-ha-arm64",
            "artifact_digest": None,
            "executor": "ha-supervisor",
        }

    def test_exact_binding_is_reusable(self):
        item = evidence.record_evidence(self.ledger, **self.values)
        found = evidence.reusable_evidence(
            self.ledger, test_id=item["test_id"], test_version=item["test_version"],
            unit_digest=item["unit_digest"], dependency_digest=item["dependency_digest"],
            environment_id=item["environment_id"], artifact_digest=None)
        self.assertEqual(found["evidence_id"], item["evidence_id"])

    def test_duplicate_binding_returns_existing_evidence(self):
        first = evidence.record_evidence(self.ledger, **self.values)
        second = evidence.record_evidence(self.ledger, **self.values)
        self.assertEqual(first["evidence_id"], second["evidence_id"])
        self.assertEqual(len(self.ledger.read_text(encoding="utf-8").splitlines()), 1)

    def test_environment_or_dependency_mismatch_is_not_reused(self):
        evidence.record_evidence(self.ledger, **self.values)
        found = evidence.reusable_evidence(
            self.ledger, test_id="avisaqui.auth-api", test_version="1",
            unit_digest="b" * 64, dependency_digest="c" * 64,
            environment_id="different-environment", artifact_digest=None)
        self.assertIsNone(found)
        found = evidence.reusable_evidence(
            self.ledger, test_id="avisaqui.auth-api", test_version="1",
            unit_digest="b" * 64, dependency_digest="d" * 64,
            environment_id="avisaqui-ha-arm64", artifact_digest=None)
        self.assertIsNone(found)

    def test_corrupt_lines_are_ignored_not_reused(self):
        self.ledger.write_text("{invalid}\n", encoding="utf-8")
        os.chmod(self.ledger, 0o600)
        self.assertEqual(evidence.load_evidence(self.ledger), [])

    def test_untrusted_pass_record_is_rejected(self):
        with self.assertRaises(evidence.EvidenceError):
            evidence.record_evidence(self.ledger, **{
                **self.values, "executor": "../attacker",
            })


if __name__ == "__main__":
    unittest.main()
