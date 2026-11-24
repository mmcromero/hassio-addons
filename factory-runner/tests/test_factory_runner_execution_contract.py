"""FR-EXEC-001 strict contract and persistence regressions."""
import json
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import execution_contract as contract


PROFILE = {
    "id": "avisaqui",
    "source_repo": "mmcromero/pager-virtual",
    "source_ref": "refs/remotes/origin/desenvolvimento",
    "distribution_repo": "mmcromero/hassio-addons",
    "public_ref": "refs/remotes/origin/main",
    "rc_ref": "refs/remotes/origin/release-candidate",
}


def make_contract():
    return {
        "schema_version": "FR-EXEC-001/v1",
        "execution_id": str(uuid.uuid4()),
        "created_at": "2026-11-24T18:00:00Z",
        "objective": "Validar alteração de autenticação",
        "project": "avisaqui",
        "source": {
            "repository": "mmcromero/pager-virtual",
            "ref": "refs/remotes/origin/desenvolvimento",
            "sha": "a" * 40,
            "base_sha": "b" * 40,
        },
        "scope": {"include_paths": ["src/**"], "exclude_paths": [],
                  "constraints": ["Somente leitura e planejamento"]},
        "requested_operations": ["analyze", "plan", "test"],
        "authorization": {"reference": "issue:2#M068", "declared_operations": ["analyze", "plan", "test"]},
        "destinations": [],
        "acceptance_criteria": ["Plano contém testes afetados e justificativas"],
        "limits": {
            "timeout_seconds": 120, "max_changed_files": 100,
            "network_policy": "read_only", "data_access": "approved_workspace",
            "max_cost_usd": None,
        },
    }


def make_plan(execution_id, contract_digest):
    receipt_body = {"format": "factory-execution-receipt-v1",
                    "contract_digest": contract_digest}
    receipt = {**receipt_body, "digest": contract.digest(receipt_body)}
    return {
        "format": "factory-execution-plan-v1",
        "execution_id": execution_id,
        "contract_digest": contract_digest,
        "receipt": receipt,
    }


class ExecutionContractTests(unittest.TestCase):
    def test_valid_contract_is_bound_to_trusted_profile(self):
        value = make_contract()
        result = contract.validate_contract(value, PROFILE)
        self.assertEqual(result["contract_digest"], contract.digest(value))
        self.assertEqual(result["privileged_operations"], [])
        self.assertFalse(result["authorization_verified"])

    def test_extra_fields_and_profile_mismatch_are_rejected(self):
        value = make_contract()
        value["shell_command"] = "echo unsafe"
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)
        value = make_contract()
        value["source"]["repository"] = "attacker/repo"
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_scope_traversal_and_invalid_sha_are_rejected(self):
        value = make_contract()
        value["scope"]["include_paths"] = ["src/../secrets"]
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)
        value = make_contract()
        value["source"]["sha"] = "not-a-sha"
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_declared_authorization_does_not_grant_privileged_operation(self):
        value = make_contract()
        value["requested_operations"] = ["publish"]
        value["authorization"] = {"reference": "issue:2#M068", "declared_operations": ["publish"]}
        value["destinations"] = [{
            "repository": "mmcromero/hassio-addons",
            "ref": "refs/heads/main",
            "environment": "home-assistant",
        }]
        result = contract.validate_contract(value, PROFILE)
        self.assertEqual(result["privileged_operations"], ["publish"])
        self.assertFalse(result["authorization_verified"])

    def test_package_requires_declared_authorization_reference(self):
        value = make_contract()
        value["requested_operations"] = ["package"]
        value["authorization"] = {"reference": None, "declared_operations": []}
        value["destinations"] = [{
            "repository": "mmcromero/hassio-addons",
            "ref": "refs/heads/main",
            "environment": "candidate",
        }]
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_destination_outside_profile_is_rejected(self):
        value = make_contract()
        value["requested_operations"] = ["publish"]
        value["authorization"] = {"reference": "issue:2#M068", "declared_operations": ["publish"]}
        value["destinations"] = [{
            "repository": "attacker/repo", "ref": "refs/heads/main",
            "environment": "production",
        }]
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_secret_like_authorization_reference_is_rejected(self):
        value = make_contract()
        value["authorization"]["reference"] = "Bearer ghp_12345678901234567890"
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_declared_authorized_operations_must_be_requested(self):
        value = make_contract()
        value["authorization"]["declared_operations"] = ["publish"]
        with self.assertRaises(contract.ContractError):
            contract.validate_contract(value, PROFILE)

    def test_partial_contract_write_can_be_completed_idempotently(self):
        value = make_contract()
        validated = contract.validate_contract(value, PROFILE)
        with tempfile.TemporaryDirectory() as folder:
            directory = contract.execution_directory(folder, value["execution_id"])
            contract._atomic_json(directory / "contract.json", {
                "contract_digest": validated["contract_digest"], "contract": value})
            plan = make_plan(value["execution_id"], validated["contract_digest"])
            saved, reused = contract.save_execution(
                folder, value, validated["contract_digest"], plan)
            self.assertEqual(saved, plan)
            self.assertFalse(reused)

    def test_same_execution_id_and_digest_is_idempotent(self):
        value = make_contract()
        validated = contract.validate_contract(value, PROFILE)
        with tempfile.TemporaryDirectory() as folder:
            plan = make_plan(value["execution_id"], validated["contract_digest"])
            first, first_reused = contract.save_execution(
                folder, value, validated["contract_digest"], plan)
            second, second_reused = contract.save_execution(
                folder, value, validated["contract_digest"], {"different": True})
            self.assertEqual(first, second)
            self.assertFalse(first_reused)
            self.assertTrue(second_reused)

    def test_same_execution_id_with_different_contract_is_rejected(self):
        value = make_contract()
        validated = contract.validate_contract(value, PROFILE)
        with tempfile.TemporaryDirectory() as folder:
            plan = make_plan(value["execution_id"], validated["contract_digest"])
            contract.save_execution(folder, value, validated["contract_digest"], plan)
            changed = dict(value)
            changed["objective"] = "Different objective"
            new_digest = contract.digest(changed)
            with self.assertRaises(contract.ContractError):
                contract.load_existing(folder, value["execution_id"], new_digest)


if __name__ == "__main__":
    unittest.main()
