"""Testes locais sem Home Assistant, Evolution API ou n8n."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
import json
from unittest.mock import patch

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

    def test_routing_denies_human_and_pending(self):
        sender = "5511999999999@s.whatsapp.net"
        decision = self.mod.routing_decision("umdoislab", sender)
        self.assertEqual(decision["allowAutoReply"], True)
        self.assertEqual(decision["state"], "none")
        self.mod.store_event(self.event())
        pending = self.mod.routing_decision("umdoislab", sender)
        self.assertFalse(pending["allowAutoReply"])
        self.assertTrue(pending["needsCustomerChoice"])
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='human'")
        human = self.mod.routing_decision("umdoislab", sender)
        self.assertFalse(human["allowAutoReply"])
        self.assertFalse(human["needsCustomerChoice"])
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='done'")
        done = self.mod.routing_decision("umdoislab", sender)
        self.assertTrue(done["allowAutoReply"])

    def test_routing_rejects_unknown_instance_and_unsafe_sender(self):
        self.assertIsNone(self.mod.routing_decision("outra", "5511999999999@s.whatsapp.net"))
        self.assertIsNone(self.mod.routing_decision("umdoislab", "5511999999999@g.us"))
        self.assertIsNone(self.mod.routing_decision("umdoislab", "status@broadcast"))
        self.assertIsNone(self.mod.routing_decision("umdoislab", "123@lid"))

    def test_auto_sender_guard_blocks_when_human_assumed(self):
        sender = "5511999999999@s.whatsapp.net"
        self.mod.store_event(self.event())
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='human'")
        options_path = Path(os.environ["CENTRAL_OPTIONS"])
        options_path.write_text(json.dumps({
            "bridge_secret":"a"*32,"evolution_api_key":"test-not-real",
            "evolution_url":"http://example.invalid:8080","evolution_instance":"umdoislab",
            "auto_test_sender":sender}))
        class FakeRequest:
            def respond(self, code, body):
                return code, body
        req = {"instance":"umdoislab","senderId":sender,"messageId":"msg-1",
               "text":"mensagem fictícia"}
        with patch.object(self.mod.urllib.request, "urlopen") as send:
            code, result = self.mod.Handler.send_automated(FakeRequest(), req)
            self.assertEqual(code, 409)
            self.assertEqual(result["state"], "human")
            send.assert_not_called()
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM replies").fetchone()[0],0)

    def test_auto_sender_guard_blocks_other_contacts(self):
        sender = "5511999999999@s.whatsapp.net"
        Path(os.environ["CENTRAL_OPTIONS"]).write_text(json.dumps({
            "evolution_api_key":"test-not-real","evolution_url":"http://example.invalid:8080",
            "evolution_instance":"umdoislab","auto_test_sender":"OUTRO"}))
        class FakeRequest:
            def respond(self, code, body):
                return code, body
        with patch.object(self.mod.urllib.request, "urlopen") as send:
            code, result = self.mod.Handler.send_automated(FakeRequest(),
                 {"instance":"umdoislab","senderId":sender,"messageId":"msg-1","text":"Teste"})
            self.assertEqual(code,403)
            send.assert_not_called()

    def test_auto_sender_guard_avoids_duplicar_mensagem(self):
        sender = "5511999999999@s.whatsapp.net"
        Path(os.environ["CENTRAL_OPTIONS"]).write_text(json.dumps({
            "evolution_api_key":"test-not-real","evolution_url":"http://example.invalid:8080",
            "evolution_instance":"umdoislab","auto_test_sender":sender}))
        class FakeRequest:
            def respond(self, code, body):
                return code, body
        class FakeHTTP:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, size): return b'{"ok":true}'
        payload = {"instance":"umdoislab","senderId":sender,"messageId":"msg-1","text":"Teste"}
        with patch.object(self.mod.urllib.request, "urlopen", return_value=FakeHTTP()) as send:
            code, result = self.mod.Handler.send_automated(FakeRequest(), payload)
            self.assertEqual(code,200)
            self.assertEqual(result["delivery"],"accepted_not_confirmed")
            repeated, _ = self.mod.Handler.send_automated(FakeRequest(), payload)
            self.assertEqual(repeated,409)
            self.assertEqual(send.call_count,1)

    def test_invalid_event_not_registered(self):
        self.assertFalse(self.mod.store_event(self.event(instance="outra")))
        self.assertFalse(self.mod.store_event(self.event(isClientMessage=False)))
        self.assertFalse(self.mod.store_event(self.event(isGroup=True)))
        self.assertFalse(self.mod.store_event(self.event(senderId="")))
        with self.mod.connect() as db:
            self.assertEqual(db.execute("select count(*) from conversations").fetchone()[0],0)

if __name__ == "__main__":
    unittest.main()
