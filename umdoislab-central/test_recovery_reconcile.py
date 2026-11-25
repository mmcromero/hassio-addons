"""Testes isolados do reconciliador, sem rede nem mensagem real."""
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta

from n8n_outbox import ensure_outbox, put, claim, deliver_one
from recovery_reconcile import evaluate

SENDER = "5511999999999@s.whatsapp.net"


def iso(d):
    return d.isoformat(timespec="seconds")


class ReconcileTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        ensure_outbox(self.db)
        self.db.execute("CREATE TABLE conversations(sender_id TEXT PRIMARY KEY,status TEXT)")
        self.db.execute("""CREATE TABLE inbound_ids(sender_id TEXT,message_id TEXT,
                         created_at TEXT,PRIMARY KEY(sender_id,message_id))""")
        self.db.execute("""CREATE TABLE outgoing_observations
                         (sender_id TEXT,message_id TEXT,classification TEXT,created_at TEXT)""")
        self.db.execute("""CREATE TABLE bot_outbound_ids
                         (sender_id TEXT,message_id TEXT)""")
        self.now = datetime.now(timezone.utc)
        self.item = {"senderId": SENDER, "messageId": "m1", "messageText": "Oi"}
        self.db.execute("INSERT INTO inbound_ids VALUES(?,?,?)",(SENDER,"m1",iso(self.now)))
        put(self.db, self.item, {"action":"auto"})
        claim(self.db)

    def tearDown(self):
        self.db.close()

    def snapshot(self, **change):
        current = {"senderId": SENDER, "complete": True,
                   "since":iso(self.now-timedelta(minutes=10)),
                   "checkedAt":iso(self.now),
                   "outbound":[],
                   "inbound":[{"id":"m1","fromMe":False,"timestamp":iso(self.now)}]}
        current.update(change)
        return current

    def check(self, snapshot=None, policy=None):
        return evaluate(self.db,self.item,snapshot if snapshot is not None else self.snapshot(),
                        policy_check=policy or (lambda db,s: True),clock=self.now)

    def test_complete_history_without_outgoing_allows_recovery(self):
        self.assertTrue(self.check()["safe"])

    def test_no_snapshot_blocks(self):
        self.assertFalse(self.check(snapshot={})["safe"])

    def test_wrong_sender_blocks(self):
        self.assertEqual(self.check(self.snapshot(senderId="other"))["reason"],"history_unverified")

    def test_unknown_outgoing_blocks(self):
        out={"id":"manual-1","timestamp":iso(self.now),"fromMe":True}
        self.assertEqual(self.check(self.snapshot(outbound=[out]))["reason"],"outgoing_after_request")

    def test_recognized_bot_echo_still_blocks_duplicate_replay(self):
        self.db.execute("INSERT INTO bot_outbound_ids VALUES(?,?)",(SENDER,"bot-1"))
        out={"id":"bot-1","timestamp":iso(self.now),"fromMe":True}
        self.assertEqual(self.check(self.snapshot(outbound=[out]))["reason"],"outgoing_after_request")

    def test_operator_assumed_blocks(self):
        self.db.execute("INSERT INTO conversations VALUES(?, 'human')",(SENDER,))
        self.assertEqual(self.check()["reason"],"operator_or_handoff")

    def test_pending_handoff_blocks(self):
        self.db.execute("INSERT INTO conversations VALUES(?, 'pending')",(SENDER,))
        self.assertFalse(self.check()["safe"])

    def test_newer_client_message_blocks(self):
        self.db.execute("INSERT INTO inbound_ids VALUES(?,?,?)",(SENDER,"m2",iso(self.now)))
        self.assertEqual(self.check()["reason"],"newer_inbound")

    def test_local_unknown_echo_blocks(self):
        self.db.execute("INSERT INTO outgoing_observations VALUES(?,?,?,?)",(SENDER,"unknown","uncertain",iso(self.now)))
        self.assertEqual(self.check()["reason"],"outgoing_unclassified")

    def test_policy_denied_blocks(self):
        self.assertEqual(self.check(policy=lambda db,s: False)["reason"],"policy_block")

    def test_policy_exception_blocks(self):
        def failure(db,s):
            raise RuntimeError("policy unavailable")
        self.assertEqual(self.check(policy=failure)["reason"],"policy_unavailable")

    def test_stale_snapshot_blocks(self):
        when=iso(self.now-timedelta(minutes=2))
        self.assertEqual(self.check(self.snapshot(checkedAt=when))["reason"],"history_stale")

    def test_partial_page_blocks(self):
        self.assertEqual(self.check(self.snapshot(complete=False))["reason"],"history_unverified")

    def test_missing_original_inbound_blocks(self):
        self.db.execute("DELETE FROM inbound_ids")
        self.assertEqual(self.check()["reason"],"inbound_not_recorded")

    def test_unclaimed_queue_blocks(self):
        self.db.execute("UPDATE n8n_outbox SET state='pending'")
        self.assertEqual(self.check()["reason"],"not_claimed")

    def test_missing_outbound_list_blocks(self):
        self.assertEqual(self.check(self.snapshot(outbound=None))["reason"],"history_missing_outgoing")

    def test_history_with_new_client_message_blocks(self):
        events=[{"id":"m1","fromMe":False,"timestamp":iso(self.now)},
                {"id":"m3","fromMe":False,"timestamp":iso(self.now+timedelta(seconds=3))}]
        self.assertEqual(self.check(self.snapshot(inbound=events))["reason"],"newer_inbound_history")

    def test_history_missing_original_blocks(self):
        self.assertEqual(self.check(self.snapshot(inbound=[]))["reason"],"original_missing_from_history")

    def test_missing_inbound_history_blocks(self):
        self.assertEqual(self.check(self.snapshot(inbound=None))["reason"],"history_missing_inbound")

    def test_transport_never_called_on_failed_reconciliation(self):
        self.db.execute("UPDATE n8n_outbox SET state='pending'")
        touched=[]
        bad=self.snapshot(complete=False)
        result=deliver_one(self.db,lambda item:touched.append(item),
                           reconcile=lambda item:evaluate(self.db,item,bad,
                               policy_check=lambda db,s:True,clock=self.now))
        self.assertEqual(result["outcome"],"blocked_reconciliation")
        self.assertEqual(touched,[])


if __name__=="__main__":
    unittest.main()
