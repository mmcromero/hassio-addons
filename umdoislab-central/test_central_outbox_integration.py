"""Integração isolada da Central com outbox. Sem webhook real ou rede."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch


class CentralOutboxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.folder = tempfile.TemporaryDirectory()
        cls.old = {k: os.environ.get(k) for k in ("CENTRAL_DATA_DIR", "CENTRAL_OPTIONS")}
        os.environ["CENTRAL_DATA_DIR"] = cls.folder.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(cls.folder.name) / "options.json")
        Path(os.environ["CENTRAL_OPTIONS"]).write_text(json.dumps({}))
        spec = importlib.util.spec_from_file_location("central_outbox_test", Path(__file__).parent / "server.py")
        cls.central = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.central)
        cls.central.init()

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()
        for key, value in cls.old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def setUp(self):
        with self.central.connect() as db:
            for table in ("inbound_ids", "conversation_turns", "conversations",
                          "contact_rules", "n8n_outbox", "handoff_offers", "bot_guard", "operator_activity", "bot_outbound_ids", "outgoing_observations"):
                db.execute("DELETE FROM " + table)
            db.execute("DELETE FROM policy_settings")
            db.execute("INSERT INTO contact_rules(sender_id,category) VALUES(?,?)",
                       ("5511999999999@s.whatsapp.net", "test"))

    def event(self, message_id="evt-1"):
        return {
            "instance": "umdoislab", "isClientMessage": True, "isGroup": False,
            "senderId": "5511999999999@s.whatsapp.net", "senderName": "Teste",
            "messageId": message_id, "messageText": "Olá",
            "category": "saudacao"
        }

    def test_queues_accepted_event_once(self):
        result = self.central.process_inbound(self.event(), enqueue=True)
        self.assertEqual(result["action"], "auto")
        self.assertEqual(self.central.process_inbound(self.event(), enqueue=True)["state"], "duplicate")
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM inbound_ids").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM n8n_outbox").fetchone()[0], 1)

    def test_policy_rejection_not_queued(self):
        ev = self.event()
        ev["senderId"] = "5511888888888@s.whatsapp.net"
        self.assertEqual(self.central.process_inbound(ev, enqueue=True)["state"], "policy_blocked")
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM n8n_outbox").fetchone()[0], 0)

    def test_legacy_entry_does_not_enqueue(self):
        self.central.process_inbound(self.event(), enqueue=False)
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM n8n_outbox").fetchone()[0], 0)

    def test_queue_error_rolls_back_inbound(self):
        with patch.object(self.central, "queue_decision", side_effect=RuntimeError("isolated test failure")):
            with self.assertRaises(RuntimeError):
                self.central.process_inbound(self.event(), enqueue=True)
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM inbound_ids").fetchone()[0], 0)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM n8n_outbox").fetchone()[0], 0)
    def test_manual_message_blocks_recovery_and_preserves_pending(self):
        from n8n_outbox import claim, counts
        self.central.process_inbound(self.event("queued-1"), enqueue=True)
        outcome = self.central.record_operator_activity({
            "instance": "umdoislab", "fromMe": True, "isGroup": False,
            "senderId": self.event()["senderId"], "messageId": "manual-1", "verifiedManual": True})
        self.assertTrue(outcome["manualActive"])
        self.assertEqual(outcome["queue"]["rejected"], 1)
        self.assertEqual(self.central.routing_decision("umdoislab", self.event()["senderId"])["allowAutoReply"], False)
        with self.central.connect() as db:
            self.assertIsNone(claim(db))
            self.assertEqual(counts(db), {"rejected": 1})

    def test_manual_event_is_idempotent(self):
        ev = {"instance": "umdoislab", "fromMe": True, "isGroup": False,
              "senderId": self.event()["senderId"], "messageId": "manual-1", "verifiedManual": True}
        self.assertFalse(self.central.record_operator_activity(ev)["duplicate"])
        self.assertTrue(self.central.record_operator_activity(ev)["duplicate"])
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM operator_activity").fetchone()[0], 1)

    def test_manual_message_without_prior_conversation(self):
        ev = {"instance": "umdoislab", "fromMe": True, "isGroup": False,
              "senderId": self.event()["senderId"], "messageId": "manual-fresh", "verifiedManual": True}
        self.assertTrue(self.central.record_operator_activity(ev)["ok"])
        self.assertEqual(self.central.routing_decision("umdoislab", ev["senderId"])["state"], "human")

    def test_manual_event_rejects_untrusted_forms(self):
        base = {"instance": "umdoislab", "fromMe": True, "isGroup": False,
                "senderId": self.event()["senderId"], "messageId": "manual-1", "verifiedManual": True}
        for changes in ({"verifiedManual": False}, {"fromMe": False}, {"isGroup": True},
                        {"senderId": "group@g.us"}, {"messageId": ""}):
            self.assertIsNone(self.central.record_operator_activity({**base, **changes}))
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM operator_activity").fetchone()[0], 0)

    def test_inflight_after_manual_is_uncertain(self):
        from n8n_outbox import claim
        self.central.process_inbound(self.event("queued-2"), enqueue=True)
        with self.central.connect() as db:
            self.assertEqual(claim(db)["messageId"], "queued-2")
        outcome = self.central.record_operator_activity({
            "instance": "umdoislab", "fromMe": True, "isGroup": False,
            "senderId": self.event()["senderId"], "messageId": "manual-2", "verifiedManual": True})
        self.assertEqual(outcome["queue"]["uncertain"], 1)
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT state FROM n8n_outbox").fetchone()[0], "uncertain")

    def test_bot_echo_does_not_take_over(self):
        sender=self.event()["senderId"]
        with self.central.connect() as db:
            db.execute("INSERT INTO bot_outbound_ids VALUES(?,?,?)",
                       (sender,"bot-out-1",self.central.now()))
        with patch.object(self.central,"verify_outgoing",return_value=True):
            result=self.central.observe_outgoing({"instance":"umdoislab",
                "senderId":sender,"messageId":"bot-out-1","fromMe":True,"isGroup":False})
        self.assertEqual(result["classification"], "bot")
        self.assertTrue(self.central.routing_decision("umdoislab",sender)["allowAutoReply"])

    def test_unidentified_outgoing_blocks_recovery(self):
        self.central.process_inbound(self.event("older"), enqueue=True)
        sender=self.event()["senderId"]
        with patch.object(self.central,"verify_outgoing",return_value=True):
            result=self.central.observe_outgoing({"instance":"umdoislab",
                "senderId":sender,"messageId":"out-unmatched-1","fromMe":True,"isGroup":False})
        self.assertEqual(result["classification"], "uncertain")
        self.assertFalse(self.central.routing_decision("umdoislab",sender)["allowAutoReply"])
        with self.central.connect() as db:
            row=db.execute("SELECT state FROM n8n_outbox").fetchone()
            self.assertEqual(row[0], "rejected")

    def test_outgoing_echo_is_idempotent(self):
        msg={"instance":"umdoislab","senderId":self.event()["senderId"],
             "messageId":"out-unmatched-2","fromMe":True,"isGroup":False}
        with patch.object(self.central,"verify_outgoing",return_value=True):
            self.assertFalse(self.central.observe_outgoing(msg)["duplicate"])
            self.assertTrue(self.central.observe_outgoing(msg)["duplicate"])
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outgoing_observations").fetchone()[0],1)

    def test_untrusted_outgoing_not_processed(self):
        base={"instance":"umdoislab","senderId":self.event()["senderId"],
              "messageId":"abc","fromMe":True,"isGroup":False}
        for invalid in ({"fromMe":False},{"isGroup":True},
                        {"senderId":"not-a-phone"},{"messageId":""}):
            self.assertIsNone(self.central.observe_outgoing({**base, **invalid}))

    def test_outgoing_unverified_does_not_change_central_state(self):
        self.central.process_inbound(self.event("queued-unverified"), enqueue=True)
        sender=self.event()["senderId"]
        ev={"instance":"umdoislab","senderId":sender,"messageId":"forged-out-1",
            "fromMe":True,"isGroup":False}
        with patch.object(self.central,"verify_outgoing",return_value=False) as verify:
            self.assertIsNone(self.central.observe_outgoing(ev))
            self.assertEqual(verify.call_count,1)
        with self.central.connect() as db:
            self.assertEqual(db.execute("SELECT state FROM n8n_outbox").fetchone()[0],
                             "pending")
            self.assertEqual(db.execute("SELECT COUNT(*) FROM outgoing_observations").fetchone()[0],0)

    def test_evolution_outbound_id_is_strict(self):
        sender=self.event()["senderId"]
        valid={"key":{"id":"3EB0-test:1","remoteJid":sender,"fromMe":True}}
        self.assertEqual(self.central.evolution_outbound_id(valid,sender),"3EB0-test:1")
        self.assertIsNone(self.central.evolution_outbound_id({"key":{**valid["key"],"id":"bad / value"}},sender))
        self.assertIsNone(self.central.evolution_outbound_id({"messageId":"guess"},sender))
        self.assertIsNone(self.central.evolution_outbound_id(valid,"5511888888888@s.whatsapp.net"))
        self.assertIsNone(self.central.evolution_outbound_id({"key":{**valid["key"],"fromMe":False}},sender))
        self.assertIsNone(self.central.evolution_outbound_id({"key":{**valid["key"],"remoteJid":"unknown@lid"}},sender))


    def test_sendtext_lid_with_pn_link_is_accepted(self):
        sender = self.event()["senderId"]
        lid_key = {"id":"3EB0-LID:rc2", "remoteJid":"123456789012345@lid",
                   "remoteJidAlt":sender, "fromMe":True}
        self.assertEqual(self.central.evolution_outbound_id({"key":lid_key}, sender),
                         "3EB0-LID:rc2")
        self.assertEqual(self.central.evolution_outbound_id(
            {"key":{"id":"3EB0-PN:rc2", "remoteJid":sender, "fromMe":True}}, sender),
            "3EB0-PN:rc2")

    def test_sendtext_lid_requires_explicit_correct_pn(self):
        sender = self.event()["senderId"]
        base = {"id":"3EB0-LID:rc2", "remoteJid":"123456789012345@lid",
                "remoteJidAlt":sender, "fromMe":True}
        for wrong in ({"remoteJidAlt":None},
                      {"remoteJidAlt":"5511888888888@s.whatsapp.net"},
                      {"remoteJid":"1234@lid"},
                      {"remoteJid":"12345678901234567890123456@lid"},
                      {"remoteJid":"notlid@lid"},
                      {"remoteJid":"12345@g.us"},
                      {"remoteJid":"5511888888888@s.whatsapp.net"},
                      {"fromMe":False}, {"fromMe":"true"},
                      {"fromMe":1}, {"id":"wrong id"}):
            with self.subTest(wrong=wrong):
                self.assertIsNone(self.central.evolution_outbound_id(
                    {"key":{**base,**wrong}}, sender))
        self.assertIsNone(self.central.evolution_outbound_id(
            {"key":base}, "5511888888888@s.whatsapp.net"))
        self.assertIsNone(self.central.evolution_outbound_id({"key":base}, None))


if __name__ == "__main__":
    unittest.main()
