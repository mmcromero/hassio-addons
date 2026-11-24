"""Automatic-assistance policy and bridge enforcement; SQLite and synthetic IDs only."""
import sqlite3
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import automation_policy
import server


class AutomationPolicyTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        automation_policy.ensure_schema(self.db)

    def tearDown(self):
        self.db.close()

    def test_default_is_tests_and_denies_everyone(self):
        state = automation_policy.snapshot(self.db, "business-1")
        self.assertEqual(state["mode"], "tests")
        self.assertFalse(automation_policy.allowed(self.db, "business-1", "12345678"))

    def test_test_profile_is_allowed_but_unknown_is_not(self):
        automation_policy.save(self.db, "business-1", "tests", "12345678", "")
        self.assertTrue(automation_policy.allowed(self.db, "business-1", "12345678"))
        self.assertFalse(automation_policy.allowed(self.db, "business-1", "87654321"))

    def test_exclusion_overrides_production(self):
        automation_policy.save(self.db, "business-1", "all", "12345678", "87654321")
        self.assertTrue(automation_policy.allowed(self.db, "business-1", "12345678"))
        self.assertFalse(automation_policy.allowed(self.db, "business-1", "87654321"))
        self.assertTrue(automation_policy.allowed(self.db, "business-1", "11112222"))

    def test_profiles_are_scoped_to_account(self):
        automation_policy.save(self.db, "business-1", "tests", "12345678", "")
        self.assertFalse(automation_policy.allowed(self.db, "business-2", "12345678"))

    def test_account_cannot_be_added_as_sender(self):
        with self.assertRaises(automation_policy.PolicyError):
            automation_policy.save(self.db, "12345678", "tests", "12345678", "")

    def test_invalid_ids_reject_the_whole_update(self):
        with self.assertRaises(automation_policy.PolicyError):
            automation_policy.save(self.db, "business-1", "all", "12345678;@someone", "")
        self.assertEqual(automation_policy.snapshot(self.db, "business-1")["mode"], "tests")

    def test_invalid_mode_rejected(self):
        with self.assertRaises(automation_policy.PolicyError):
            automation_policy.save(self.db, "business-1", "new", "", "")

    def test_bridge_claim_filters_before_exposing_to_n8n(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.multiple(server, DATA_DIR=Path(directory), DB_PATH=Path(directory) / "instagram.sqlite3"):
                with server.database() as db:
                    db.execute("""INSERT INTO inbound
                      (recipient_id,sender_id,message_id,message_text,received_at,message_at)
                      VALUES(?,?,?,?,?,?)""",
                      ("business-1", "12345678", "m-test", "oi",
                       datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
                    db.execute("""INSERT INTO inbound
                      (recipient_id,sender_id,message_id,message_text,received_at,message_at)
                      VALUES(?,?,?,?,?,?)""",
                      ("business-1", "87654321", "m-other", "hello",
                       datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
                self.assertEqual(server.list_pending(account_id="business-1"), [])
                self.assertIsNone(server.claim_message(account_id="business-1"))
                with server.database() as db:
                    automation_policy.save(db, "business-1", "tests", "12345678", "")
                pending = server.list_pending(account_id="business-1")
                self.assertEqual([item["senderId"] for item in pending], ["12345678"])
                claimed = server.claim_message(account_id="business-1")
                self.assertEqual(claimed["senderId"], "12345678")

    def test_bridge_exclusion_still_applies_in_production(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.multiple(server, DATA_DIR=Path(directory), DB_PATH=Path(directory) / "instagram.sqlite3"):
                with server.database() as db:
                    db.execute("""INSERT INTO inbound
                      (recipient_id,sender_id,message_id,message_text,received_at,message_at)
                      VALUES(?,?,?,?,?,?)""",
                      ("business-1", "12345678", "m-excluded", "oi",
                       datetime.now(timezone.utc).isoformat(), datetime.now(timezone.utc).isoformat()))
                    automation_policy.save(db, "business-1", "all", "", "12345678")
                self.assertEqual(server.list_pending(account_id="business-1"), [])
                self.assertIsNone(server.claim_message(account_id="business-1"))

    def prepare_claim(self, directory, *, sender="12345678", age_minutes=1, handoff="bot"):
        patcher = patch.multiple(server, DATA_DIR=Path(directory),
                                 DB_PATH=Path(directory) / "instagram.sqlite3")
        patcher.start()
        now = datetime.now(timezone.utc)
        received = (now - timedelta(minutes=age_minutes)).isoformat()
        until = (now + timedelta(minutes=2)).isoformat()
        token = "c" * 48
        with server.database() as db:
            automation_policy.save(db, "business-1", "tests", sender, "")
            db.execute("""INSERT INTO inbound
              (recipient_id,sender_id,message_id,message_text,received_at,message_at,claim_token,claim_until)
              VALUES(?,?,?,?,?,?,?,?)""",
              ("business-1", sender, "m-reply", "oi", now.isoformat(), received, token, until))
            if handoff != "bot":
                db.execute("""INSERT INTO handoff(recipient_id,sender_id,state,updated_at)
                  VALUES(?,?,?,?)""", ("business-1", sender, handoff, now.isoformat()))
        return ({"accountId": "business-1", "senderId": sender, "messageId": "m-reply",
                 "claimToken": token, "text": "Oi! Como posso ajudar?"}, patcher)

    def test_automatic_reply_requires_live_claim_and_is_idempotent(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, patcher = self.prepare_claim(directory)
            try:
                calls = []
                def sender(cfg, credential, recipient, text):
                    calls.append((recipient, text))
                    return {"recipient_id": recipient, "message_id": "remote-1"}
                result = server.send_automatic_reply(payload, {"instagram_account_id": "business-1"},
                                                     {"synthetic": True}, sender=sender)
                self.assertEqual(result, {"status": "sent", "messageId": "remote-1"})
                self.assertEqual(len(calls), 1)
                repeated = server.send_automatic_reply(payload, {"instagram_account_id": "business-1"},
                                                       {"synthetic": True}, sender=sender)
                self.assertNotEqual(repeated["status"], "sent")
                self.assertEqual(len(calls), 1)
                with server.database() as db:
                    self.assertEqual(db.execute("SELECT status FROM automation_sends").fetchone(), ("sent",))
                    self.assertIsNotNone(db.execute("SELECT processed_at FROM inbound").fetchone()[0])
            finally:
                patcher.stop()

    def test_automatic_reply_refuses_excluded_or_human_owned_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, patcher = self.prepare_claim(directory)
            try:
                with server.database() as db:
                    automation_policy.save(db, "business-1", "all", "", "12345678")
                calls = []
                result = server.send_automatic_reply(payload, {"instagram_account_id": "business-1"},
                    {}, sender=lambda *args: calls.append(args))
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(calls, [])
            finally:
                patcher.stop()
        with tempfile.TemporaryDirectory() as directory:
            payload, patcher = self.prepare_claim(directory, sender="87654321", handoff="human")
            try:
                calls = []
                result = server.send_automatic_reply(payload, {"instagram_account_id": "business-1"},
                    {}, sender=lambda *args: calls.append(args))
                self.assertEqual(result["status"], "rejected")
                self.assertEqual(calls, [])
            finally:
                patcher.stop()

    def test_automatic_reply_refuses_messages_outside_24_hours(self):
        with tempfile.TemporaryDirectory() as directory:
            payload, patcher = self.prepare_claim(directory, age_minutes=24 * 60 + 1)
            try:
                calls = []
                result = server.send_automatic_reply(payload, {"instagram_account_id": "business-1"},
                    {}, sender=lambda *args: calls.append(args))
                self.assertEqual(result["reason"], "outside_messaging_window")
                self.assertEqual(calls, [])
            finally:
                patcher.stop()


if __name__ == "__main__":
    unittest.main()
