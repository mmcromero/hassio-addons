"""Testes locais sem Home Assistant, Evolution API ou n8n."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parent
class CentralTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CENTRAL_DATA_DIR"] = self.tmp.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(self.tmp.name)/"options.json")
        spec = importlib.util.spec_from_file_location("central_tested", ROOT/"server.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init()
    def tearDown(self):
        self.tmp.cleanup()

    def event(self, **extra):
        e = {"instance":"umdoislab","isClientMessage":True,"isGroup":False,
             "senderId":"5511999999999@s.whatsapp.net","senderName":"Teste",
             "messageId":"m1","messageText":"Preço?", "category":"preco",
             "handoffRequested":True}
        e.update(extra)
        return e

    def test_only_handoff_opens_ticket(self):
        self.assertFalse(self.mod.store_event(self.event(handoffRequested=False)))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)
        self.assertTrue(self.mod.store_event(self.event()))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("select status from conversations").fetchone()[0],"pending")

    def test_repeated_message_id_does_not_replace_last_message(self):
        self.mod.store_event(self.event())
        self.mod.store_event(self.event(messageText="Diferente",messageId="m1"))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("select last_message from conversations").fetchone()[0],"Preço?")

    def test_human_state_stays_during_new_client_message(self):
        self.mod.store_event(self.event())
        with self.mod.connect() as db:
            db.execute("update conversations set status='human'")
        self.mod.store_event(self.event(messageId="m2",messageText="Outra dúvida",
                                        handoffRequested=False))
        with self.mod.connect() as db:
            row = db.execute("select status,last_message from conversations").fetchone()
            self.assertEqual((row["status"],row["last_message"]),("human","Outra dúvida"))

    def test_safe_send_jid_validation(self):
        self.assertTrue(self.mod.valid_sender_for_send("5511999999999@s.whatsapp.net"))
        self.assertFalse(self.mod.valid_sender_for_send("5511999999999@g.us"))
        self.assertFalse(self.mod.valid_sender_for_send("abc@lid"))
        self.assertFalse(self.mod.valid_sender_for_send("status@broadcast"))
        self.assertFalse(self.mod.valid_sender_for_send("5511999999999@sXwhatsappXnet"))

    def test_resolved_conversation_reopens_only_on_explicit_handoff(self):
        self.mod.store_event(self.event())
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='done'")
        self.mod.store_event(self.event(messageId="m2", handoffRequested=False))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM conversations").fetchone()[0], "done")
        self.mod.store_event(self.event(messageId="m3", handoffRequested=True))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT status FROM conversations").fetchone()[0], "pending")

    def test_invalid_event_not_registered(self):
        self.assertFalse(self.mod.store_event(self.event(instance="outra")))
        self.assertFalse(self.mod.store_event(self.event(isClientMessage=False)))
        self.assertFalse(self.mod.store_event(self.event(isGroup=True)))
        self.assertFalse(self.mod.store_event(self.event(senderId="")))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)

if __name__ == "__main__":
    unittest.main()
