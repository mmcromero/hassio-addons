"""Persistent job queue, recovery, cancellation and timeout regressions."""
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import unittest
import uuid
from unittest.mock import patch

import execution_contract
import execution_orchestrator as orchestration


PROFILE = {
    "id": "sample",
    "source_repo": "example/source",
    "source_ref": "refs/remotes/origin/development",
    "distribution_repo": "example/distribution",
    "public_ref": "refs/remotes/origin/main",
    "rc_ref": "refs/remotes/origin/release-candidate",
}


def make_contract(*, execution_id=None, source_sha=None, objective="Plan a safe run"):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "schema_version": "FR-EXEC-001/v1",
        "execution_id": execution_id or str(uuid.uuid4()),
        "created_at": now,
        "objective": objective,
        "project": "sample",
        "source": {
            "repository": PROFILE["source_repo"],
            "ref": PROFILE["source_ref"],
            "sha": source_sha or "a" * 40,
            "base_sha": None,
        },
        "scope": {
            "include_paths": [],
            "exclude_paths": [],
            "constraints": ["Read-only planning; never execute project code"],
        },
        "requested_operations": ["analyze", "plan", "test"],
        "authorization": {
            "reference": None,
            "declared_operations": ["analyze", "plan", "test"],
        },
        "destinations": [],
        "acceptance_criteria": ["Persist a verifiable read-only plan"],
        "limits": {
            "timeout_seconds": 60,
            "max_changed_files": 100,
            "network_policy": "read_only",
            "data_access": "approved_workspace",
            "max_cost_usd": None,
        },
    }


class ExecutionOrchestratorTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.executions = self.root / "executions"
        self.orchestrator = orchestration.ExecutionOrchestrator(
            self.executions,
            threading.Lock(),
            worker_script=self.root / "worker.py",
            app_dir=self.root,
            projects_dir=self.root / "projects",
            workspaces_dir=self.root / "workspaces",
            catalog_dir=self.root / "catalogs",
        )

    def _mutate(self, execution_id, code, **changes):
        fd = self.orchestrator._locked()
        try:
            directory, _request, state, _events = self.orchestrator._load_locked(execution_id)
            previous = state["status"]
            target = changes.get("status", previous)
            if target == "EXECUTANDO" and previous == "RECEBIDA":
                state["status"] = "PLANEJADA"
                self.orchestrator._append_snapshot(
                    directory, state, code + "_planned", previous, "PLANEJADA")
                previous = "PLANEJADA"
            state.update(changes)
            self.orchestrator._append_snapshot(
                directory, state, code, previous, state["status"])
        finally:
            orchestration._unlock(fd)

    def test_submit_is_idempotent_and_binds_contract_digest(self):
        contract = make_contract()
        first, first_idempotent = self.orchestrator.submit(contract, PROFILE)
        second, second_idempotent = self.orchestrator.submit(contract, PROFILE)
        self.assertFalse(first_idempotent)
        self.assertTrue(second_idempotent)
        self.assertEqual(first["execution_id"], second["execution_id"])
        self.assertEqual(first["contract_digest"], second["contract_digest"])
        self.assertEqual(second["status"], "RECEBIDA")

        changed = make_contract(
            execution_id=contract["execution_id"], objective="Different objective")
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "execution_id_conflict"):
            self.orchestrator.submit(changed, PROFILE)


    def test_request_write_is_atomic_when_replace_fails(self):
        contract = make_contract()
        with patch.object(orchestration.os, "replace",
                          side_effect=OSError("simulated interrupted commit")):
            with self.assertRaisesRegex(orchestration.OrchestrationError,
                                        "job_request_persist_failed"):
                self.orchestrator.submit(contract, PROFILE)
        directory = self.executions / contract["execution_id"]
        self.assertTrue(directory.is_dir())
        self.assertFalse((directory / "request.json").exists())
        self.assertEqual(list(directory.glob(".request-*")), [])

    def test_illegal_terminal_transition_is_rejected(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "invalid_job_transition"):
            self._mutate(contract["execution_id"], "test_illegal_transition",
                         status="CONCLUIDA", ended_at=orchestration._now())

    def test_cancel_queued_job_is_terminal_and_idempotent(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        first = self.orchestrator.cancel(contract["execution_id"])
        second = self.orchestrator.cancel(contract["execution_id"])
        self.assertEqual(first["status"], "CANCELADA")
        self.assertEqual(second["status"], "CANCELADA")
        self.assertTrue(first["cancel_requested"])
        self.assertEqual(first["events"][-1]["code"],
                         "job_cancelled_before_execution")

    def test_running_cancel_is_cooperative_and_persisted(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_started",
                     status="EXECUTANDO", deadline_epoch=time.time() + 30)
        job = self.orchestrator.cancel(contract["execution_id"])
        self.assertEqual(job["status"], "EXECUTANDO")
        self.assertTrue(job["cancel_requested"])
        self.assertEqual(job["events"][-1]["code"], "job_cancel_requested")

    def test_cancel_request_wins_against_concurrent_job_finalization(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_started",
                     status="EXECUTANDO", deadline_epoch=time.time() + 30)
        self._mutate(contract["execution_id"], "test_validating",
                     status="VALIDANDO")
        self._mutate(contract["execution_id"], "test_cancel_requested",
                     cancel_requested=True)
        candidate = self.orchestrator.get(contract["execution_id"])
        candidate.update({
            "status": "CONCLUIDA",
            "result": {"plan_status": "PLANNED"},
            "ended_at": orchestration._now(),
            "cancel_requested": False,
        })
        audit_calls = []
        self.orchestrator.audit_callback = lambda *args: audit_calls.append(args)
        self.orchestrator._save_transition(
            contract["execution_id"], candidate, "job_finished",
            "VALIDANDO", "CONCLUIDA")
        job = self.orchestrator.get(contract["execution_id"])
        self.assertEqual(job["status"], "CANCELADA")
        self.assertTrue(job["cancel_requested"])
        self.assertEqual(audit_calls, [])

    def test_audit_failure_blocks_job_finalization(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_started",
                     status="EXECUTANDO", deadline_epoch=time.time() + 30)
        self._mutate(contract["execution_id"], "test_validating",
                     status="VALIDANDO")
        candidate = self.orchestrator.get(contract["execution_id"])
        candidate.update({
            "status": "CONCLUIDA",
            "result": {"plan_status": "PLANNED"},
            "ended_at": orchestration._now(),
        })

        def fail_audit(*_args):
            raise RuntimeError("audit unavailable")

        self.orchestrator.audit_callback = fail_audit
        self.orchestrator._save_transition(
            contract["execution_id"], candidate, "job_finished",
            "VALIDANDO", "CONCLUIDA")
        job = self.orchestrator.get(contract["execution_id"])
        self.assertEqual(job["status"], "IMPEDIDA")
        self.assertEqual(job["error_code"], "audit_unavailable")

    def test_late_worker_failure_does_not_override_requested_cancel(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_started",
                     status="EXECUTANDO", deadline_epoch=time.time() + 30)
        self._mutate(contract["execution_id"], "test_cancel_requested",
                     cancel_requested=True)
        self.orchestrator._finish_blocked(
            contract["execution_id"], "execution_worker_failed")
        job = self.orchestrator.get(contract["execution_id"])
        self.assertEqual(job["status"], "CANCELADA")
        self.assertTrue(job["cancel_requested"])

    def test_list_filters_and_pagination(self):
        first = make_contract(source_sha="a" * 40)
        second = make_contract(source_sha="b" * 40)
        self.orchestrator.submit(first, PROFILE)
        self.orchestrator.submit(second, PROFILE)
        page = self.orchestrator.list(
            project="sample", source_sha="b" * 40, limit=1, offset=0)
        self.assertEqual(page["total"], 1)
        self.assertEqual(page["jobs"][0]["source_sha"], "b" * 40)
        self.assertEqual(page["jobs"][0]["job_id"], second["execution_id"])

    def test_explicit_retry_is_limited_to_retryable_failures(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_worker_failure",
                     status="IMPEDIDA", error_code="execution_worker_failed",
                     ended_at=orchestration._now())
        retried = self.orchestrator.retry(contract["execution_id"])
        self.assertEqual(retried["status"], "RECEBIDA")
        self.assertEqual(retried["retry_count"], 1)
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "job_not_retryable"):
            self.orchestrator.retry(contract["execution_id"])

    def test_retry_refuses_policy_and_security_blocks(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_policy_block",
                     status="IMPEDIDA", error_code="scope_outside_approved_contract",
                     ended_at=orchestration._now())
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "job_not_retryable"):
            self.orchestrator.retry(contract["execution_id"])

    def test_restart_recovers_interrupted_job_without_losing_identity(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_interrupted",
                     status="EXECUTANDO", attempts=1,
                     deadline_epoch=time.time() + 30)
        self.orchestrator._recover()
        job = self.orchestrator.get(contract["execution_id"])
        self.assertEqual(job["status"], "RECEBIDA")
        self.assertEqual(job["recovery_count"], 1)
        self.assertEqual(job["contract_digest"],
                         execution_contract.digest(contract))
        self.assertIn("job_recovered_after_restart",
                      [event["code"] for event in job["events"]])

    def test_restart_validates_plan_already_persisted_before_crash(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        directory = orchestration._job_dir(
            self.executions, contract["execution_id"])
        plan_path = directory / "plan.json"
        plan_path.write_text("{}", encoding="utf-8")
        plan_path.chmod(0o600)
        self._mutate(contract["execution_id"], "test_interrupted_after_plan",
                     status="EXECUTANDO", attempts=1,
                     deadline_epoch=time.time() + 30)
        self.orchestrator._recover()
        job = self.orchestrator.get(contract["execution_id"])
        self.assertEqual(job["status"], "VALIDANDO")
        self.assertEqual(job["recovery_count"], 1)

    def test_truncated_event_tail_is_repaired_before_next_append(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        directory = orchestration._job_dir(
            self.executions, contract["execution_id"])
        with (directory / "events.jsonl").open("ab") as stream:
            stream.write(b'{"sequence":')
            stream.flush()
            os.fsync(stream.fileno())
        job = self.orchestrator.cancel(contract["execution_id"])
        self.assertEqual(job["status"], "CANCELADA")
        raw = (directory / "events.jsonl").read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        for line in raw.splitlines():
            json.loads(line)


    def test_job_records_are_private_and_event_history_is_append_only(self):
        contract = make_contract(objective="private objective text")
        self.orchestrator.submit(contract, PROFILE)
        directory = orchestration._job_dir(
            self.executions, contract["execution_id"])
        request_path = directory / "request.json"
        events_path = directory / "events.jsonl"
        self.assertEqual(os.stat(directory).st_mode & 0o777, 0o700)
        self.assertEqual(os.stat(request_path).st_mode & 0o777, 0o600)
        self.assertEqual(os.stat(events_path).st_mode & 0o777, 0o600)
        first_history = events_path.read_bytes()
        self.assertNotIn(b"private objective text", first_history)
        self.orchestrator.cancel(contract["execution_id"])
        second_history = events_path.read_bytes()
        self.assertTrue(second_history.startswith(first_history))
        self.assertGreater(len(second_history), len(first_history))

    def test_symlink_event_log_fails_closed(self):
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        directory = orchestration._job_dir(
            self.executions, contract["execution_id"])
        event_path = directory / "events.jsonl"
        event_path.unlink()
        target = self.root / "outside.jsonl"
        target.write_text("{}", encoding="utf-8")
        event_path.symlink_to(target)
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "unsafe_job_event_log"):
            self.orchestrator.get(contract["execution_id"])

    def test_plan_summary_rejects_claimed_test_execution_or_verified_authority(self):
        plan = {
            "format": "factory-execution-plan-v1",
            "execution_id": str(uuid.uuid4()),
            "contract_digest": "a" * 64,
            "status": "PARTIAL",
            "tests": {
                "execution_performed": False,
                "selected_count": 2,
                "reused_count": 0,
                "omitted_count": 1,
            },
            "operations": {
                "authorization_verified": False,
                "blocked": [{"operation": "test", "reason": "sandbox_required"}],
            },
            "receipt": {"digest": "b" * 64},
        }
        worker_result = {
            "ok": True,
            "execution_id": plan["execution_id"],
            "contract_digest": plan["contract_digest"],
            "plan_status": plan["status"],
            "plan_digest": execution_contract.digest(plan),
            "receipt_digest": plan["receipt"]["digest"],
            "selected_count": 2,
            "reused_count": 0,
            "omitted_count": 1,
        }
        summary = self.orchestrator._plan_summary(
            plan, execution_id=plan["execution_id"],
            contract_digest=plan["contract_digest"],
            worker_result=worker_result)
        self.assertFalse(summary["tests_execution_performed"])
        self.assertFalse(summary["authorization_verified"])
        self.assertEqual(summary["test_counts"]["selected"], 2)
        self.assertFalse(summary["approval_required"])

        worker_result["plan_digest"] = "c" * 64
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "execution_plan_integrity_failed"):
            self.orchestrator._plan_summary(
                plan, execution_id=plan["execution_id"],
                contract_digest=plan["contract_digest"],
                worker_result=worker_result)

        plan["tests"]["execution_performed"] = True
        with self.assertRaisesRegex(orchestration.OrchestrationError,
                                    "execution_plan_integrity_failed"):
            self.orchestrator._plan_summary(plan)

    def test_plan_worker_timeout_kills_child_process_group(self):
        worker = self.root / "worker.py"
        worker.write_text(
            "import sys, time\nsys.stdin.buffer.read()\ntime.sleep(10)\n",
            encoding="utf-8")
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_worker_running",
                     status="EXECUTANDO", deadline_epoch=time.time() + 0.35)
        result = self.orchestrator._run_plan_worker(contract["execution_id"])
        self.assertEqual(result, {"error": "execution_timeout"})

    def test_plan_worker_is_killed_after_running_cancellation(self):
        worker = self.root / "worker.py"
        worker.write_text(
            "import sys, time\nsys.stdin.buffer.read()\ntime.sleep(10)\n",
            encoding="utf-8")
        contract = make_contract()
        self.orchestrator.submit(contract, PROFILE)
        self._mutate(contract["execution_id"], "test_worker_running",
                     status="EXECUTANDO", deadline_epoch=time.time() + 30)
        result = {}

        thread = threading.Thread(
            target=lambda: result.update(
                self.orchestrator._run_plan_worker(contract["execution_id"])))
        thread.start()
        time.sleep(0.25)
        self.orchestrator.cancel(contract["execution_id"])
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(result, {"error": "cancelled"})


if __name__ == "__main__":
    unittest.main()
