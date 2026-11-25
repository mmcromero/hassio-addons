"""Testes locais, somente SQLite em memória; sem rede e sem envios."""
import json
import sqlite3
import unittest
from n8n_outbox import ensure_outbox, put, claim, settle, counts, deliver_one


def trusted(payload):
    # Evidência simulada SOMENTE nos testes; não autoriza recuperação em produção.
    return {"safe": True, "senderId": payload["senderId"], "messageId": payload["messageId"]}


def event(mid="m1"):
    return {"senderId": "5511999999999@s.whatsapp.net",
            "messageId": mid, "messageText": "Preço?",
            "senderName": "Teste"}


class OutboxTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        ensure_outbox(self.db)

    def tearDown(self):
        self.db.close()

    def test_pending_and_claim(self):
        self.assertTrue(put(self.db, event(), {"action": "auto"}))
        self.assertEqual(claim(self.db)["messageId"], "m1")
        self.assertIsNone(claim(self.db))

    def test_duplicate_never_overwrites(self):
        put(self.db, event(), {"action": "auto"})
        self.assertFalse(put(self.db, event(), {"action": "handoff"}))
        self.assertEqual(claim(self.db)["action"], "auto")

    def test_silent_does_not_dispatch(self):
        put(self.db, event(), {"action": "silent"})
        self.assertIsNone(claim(self.db))
        self.assertEqual(counts(self.db), {"rejected": 1})

    def test_uncertain_never_auto_retries(self):
        put(self.db, event(), {"action": "auto"})
        claim(self.db)
        self.assertTrue(settle(self.db, event()["senderId"], "m1", "uncertain"))
        self.assertIsNone(claim(self.db))
        self.assertEqual(counts(self.db), {"uncertain": 1})

    def test_accepted_never_auto_retries(self):
        put(self.db, event(), {"action": "auto"})
        claim(self.db)
        self.assertTrue(settle(self.db, event()["senderId"], "m1", "accepted"))
        self.assertIsNone(claim(self.db))

    def test_cannot_settle_twice(self):
        put(self.db, event(), {"action": "auto"})
        claim(self.db)
        settle(self.db, event()["senderId"], "m1", "accepted")
        self.assertFalse(settle(self.db, event()["senderId"], "m1", "uncertain"))

    def test_invalid_outcome_rejected(self):
        with self.assertRaises(ValueError):
            settle(self.db, "s", "m", "pending")

    def test_bad_action_rejected(self):
        with self.assertRaises(ValueError):
            put(self.db, event(), {"action": "send_direct"})

    def test_multiple_items(self):
        put(self.db, event("m1"), {"action": "auto"})
        put(self.db, event("m2"), {"action": "auto"})
        self.assertEqual(claim(self.db)["messageId"], "m1")
        self.assertEqual(claim(self.db)["messageId"], "m2")
        self.assertIsNone(claim(self.db))

    def test_payload_is_bounded(self):
        e = event()
        e["messageText"] = "x" * 2000
        put(self.db, e, {"action": "auto"})
        self.assertEqual(len(claim(self.db)["messageText"]), 500)

    def test_transport_http_2xx(self):
        put(self.db, event(), {"action": "auto"})
        result = deliver_one(self.db, lambda payload: 202, reconcile=trusted)
        self.assertEqual(result["outcome"], "accepted")
        self.assertIsNone(deliver_one(self.db, lambda payload: 202, reconcile=trusted))

    def test_transport_http_403(self):
        put(self.db, event(), {"action": "auto"})
        self.assertEqual(deliver_one(self.db, lambda payload: 403, reconcile=trusted)["outcome"], "rejected")
        self.assertIsNone(claim(self.db))

    def test_transport_timeout_is_uncertain(self):
        put(self.db, event(), {"action": "auto"})
        def timeout(payload):
            raise TimeoutError("simulado")
        self.assertEqual(deliver_one(self.db, timeout, reconcile=trusted)["outcome"], "uncertain")
        self.assertIsNone(claim(self.db))

    def test_transport_http_5xx_is_uncertain(self):
        put(self.db, event(), {"action": "auto"})
        self.assertEqual(deliver_one(self.db, lambda payload: 503, reconcile=trusted)["outcome"], "uncertain")
        self.assertIsNone(claim(self.db))

    def test_survives_db_reopen(self):
        import os
        import tempfile
        with tempfile.TemporaryDirectory() as folder:
            path = os.path.join(folder, "test.sqlite")
            with sqlite3.connect(path) as db:
                ensure_outbox(db)
                put(db, event(), {"action": "auto"})
            with sqlite3.connect(path) as db:
                ensure_outbox(db)
                self.assertEqual(claim(db)["messageId"], "m1")


    def test_claim_rejects_queue_if_human_already_active(self):
        from n8n_outbox import cancel_for_manual
        self.db.execute("CREATE TABLE conversations(sender_id TEXT PRIMARY KEY, status TEXT NOT NULL)")
        self.db.execute("INSERT INTO conversations VALUES(?, 'human')", (event()["senderId"],))
        put(self.db, event(), {"action": "auto"})
        self.assertIsNone(claim(self.db))
        self.assertEqual(counts(self.db), {"rejected": 1})

    def test_manual_takeover_during_transport_keeps_uncertain(self):
        from n8n_outbox import cancel_for_manual
        put(self.db, event(), {"action": "auto"})
        def concurrent_takeover(payload):
            cancel_for_manual(self.db, payload["senderId"])
            return 200
        result = deliver_one(self.db, concurrent_takeover, reconcile=trusted)
        self.assertEqual(result["outcome"], "uncertain")
        self.assertEqual(counts(self.db), {"uncertain": 1})
        self.assertIsNone(claim(self.db))

    def test_manual_takeover_rejects_only_that_contact(self):
        from n8n_outbox import cancel_for_manual
        put(self.db, event("one"), {"action": "auto"})
        other = dict(event("two"), senderId="5511888888888@s.whatsapp.net")
        put(self.db, other, {"action": "auto"})
        self.assertEqual(cancel_for_manual(self.db, event()["senderId"])["rejected"], 1)
        self.assertEqual(claim(self.db)["senderId"], other["senderId"])

    def test_no_reconciliation_blocks_without_network(self):
        put(self.db, event(), {"action": "auto"})
        calls=[]
        result=deliver_one(self.db, lambda payload: calls.append(payload))
        self.assertEqual(result["outcome"], "blocked_reconciliation")
        self.assertEqual(calls, [])
        self.assertEqual(counts(self.db), {"pending": 1})

    def test_reconciliation_inconclusive_stops_automatic_replay(self):
        put(self.db, event(), {"action": "auto"})
        calls=[]
        result=deliver_one(self.db, lambda payload: calls.append(payload),
                           reconcile=lambda payload: {"safe": False})
        self.assertEqual(result["outcome"], "blocked_reconciliation")
        self.assertEqual(calls, [])
        self.assertEqual(counts(self.db), {"uncertain": 1})

    def test_reconciliation_must_match_sender_and_message(self):
        put(self.db, event(), {"action": "auto"})
        result=deliver_one(self.db, lambda payload: 200,
                           reconcile=lambda payload: {"safe": True,
                               "senderId": payload["senderId"], "messageId": "wrong"})
        self.assertEqual(result["outcome"], "blocked_reconciliation")
        self.assertEqual(counts(self.db), {"uncertain": 1})


if __name__ == "__main__":
    unittest.main()
