"""Teste do worker desativado: SQLite em memória e transportes falsos."""
import sqlite3
import unittest
from datetime import datetime, timezone, timedelta

from n8n_outbox import ensure_outbox, put, counts
from recovery_worker import recover_one

SENDER="5511999999999@s.whatsapp.net"


class WorkerTests(unittest.TestCase):
    def setUp(self):
        self.db=sqlite3.connect(":memory:")
        ensure_outbox(self.db)
        self.db.execute("CREATE TABLE conversations(sender_id TEXT PRIMARY KEY,status TEXT)")
        self.db.execute("""CREATE TABLE inbound_ids(sender_id TEXT,message_id TEXT,
                         created_at TEXT,PRIMARY KEY(sender_id,message_id))""")
        self.db.execute("""CREATE TABLE outgoing_observations
                         (sender_id TEXT,message_id TEXT,classification TEXT,created_at TEXT)""")
        self.db.execute("""CREATE TABLE bot_outbound_ids
                         (sender_id TEXT,message_id TEXT)""")
        self.item={"senderId":SENDER,"messageId":"m1","messageText":"Oi"}
        self.now=datetime.now(timezone.utc)
        self.db.execute("INSERT INTO inbound_ids VALUES(?,?,?)",
                        (SENDER,"m1",self.now.isoformat(timespec="seconds")))
        put(self.db,self.item,{"action":"auto"})
        row=self.db.execute("SELECT created_at FROM n8n_outbox").fetchone()
        self.created=datetime.fromisoformat(row[0])
        self.now=self.created+timedelta(seconds=3)
        self.sent=[]

    def tearDown(self):
        self.db.close()

    def record(self, mid="m1", *, from_me=False, timestamp=None):
        ts=self.created if timestamp is None else timestamp
        return {"key":{"remoteJid":SENDER,"id":mid,"fromMe":from_me},
                "messageTimestamp":int(ts.timestamp())}

    def reader(self,records=None):
        records=[self.record()] if records is None else records
        def make(sender):
            self.assertEqual(sender,SENDER)
            def page(n):
                self.assertEqual(n,1)
                return {"messages":{"records":records,"total":len(records),
                                    "pages":1,"currentPage":1}}
            return page
        return make

    def deliver(self,item):
        self.sent.append(item["messageId"])
        return 200

    def run_worker(self,**changes):
        args={"enabled":True,"fetch_pages":self.reader(),
              "fetch_alt_pages":self.reader([]),
              "transport":self.deliver,
              "policy_check":lambda db,s:True,
              "max_age_seconds":900,"clock":self.now}
        args.update(changes)
        return recover_one(self.db,**args)

    def test_off_by_default_no_side_effect(self):
        outcome=recover_one(self.db,transport=self.deliver)
        self.assertEqual(outcome["outcome"],"disabled")
        self.assertEqual(self.sent,[])
        self.assertEqual(counts(self.db),{"pending":1})

    def test_valid_reconciliation_accepts_once(self):
        self.assertEqual(self.run_worker()["outcome"],"accepted")
        self.assertEqual(self.sent,["m1"])
        self.assertIsNone(self.run_worker())

    def test_manual_reply_after_request_blocks(self):
        messages=[self.record(),self.record("manual-1",from_me=True,
                                          timestamp=self.created+timedelta(seconds=1))]
        self.assertEqual(self.run_worker(fetch_pages=self.reader(messages))["outcome"],
                         "blocked_reconciliation")
        self.assertEqual(self.sent,[])
        self.assertEqual(counts(self.db),{"uncertain":1})

    def test_even_known_bot_reply_after_request_blocks(self):
        self.db.execute("INSERT INTO bot_outbound_ids VALUES(?,?)",(SENDER,"bot-1"))
        messages=[self.record(),self.record("bot-1",from_me=True,
                                           timestamp=self.created+timedelta(seconds=1))]
        self.assertEqual(self.run_worker(fetch_pages=self.reader(messages))["outcome"],
                         "blocked_reconciliation")
        self.assertEqual(self.sent,[])

    def test_newer_inbound_after_request_blocks(self):
        messages=[self.record(),self.record("m2",
                                           timestamp=self.created+timedelta(seconds=1))]
        self.assertEqual(self.run_worker(fetch_pages=self.reader(messages))["outcome"],
                         "blocked_reconciliation")
        self.assertEqual(self.sent,[])

    def test_human_takeover_blocks_queued_request(self):
        self.db.execute("INSERT INTO conversations VALUES(?,?)",(SENDER,"human"))
        self.assertIsNone(self.run_worker())
        self.assertEqual(counts(self.db),{"rejected":1})
        self.assertEqual(self.sent,[])

    def test_aged_item_blocks(self):
        self.now=self.created+timedelta(hours=2)
        self.assertEqual(self.run_worker()["outcome"],"blocked_reconciliation")
        self.assertEqual(self.sent,[])

    def test_no_snapshot_blocks(self):
        self.assertEqual(self.run_worker(fetch_pages=lambda sender: None)["outcome"],
                         "blocked_reconciliation")
        self.assertEqual(self.sent,[])

    def test_no_policy_blocks(self):
        self.assertEqual(self.run_worker(policy_check=lambda db,s:False)["outcome"],
                         "blocked_reconciliation")
        self.assertEqual(self.sent,[])

    def test_missing_transport_blocks_without_claim(self):
        self.assertEqual(self.run_worker(transport=None)["outcome"],"blocked_configuration")
        self.assertEqual(counts(self.db),{"pending":1})

    def test_no_maximum_age_blocks_without_claim(self):
        self.assertEqual(self.run_worker(max_age_seconds=None)["outcome"],
                         "blocked_configuration")
        self.assertEqual(counts(self.db),{"pending":1})


if __name__=="__main__":
    unittest.main()
