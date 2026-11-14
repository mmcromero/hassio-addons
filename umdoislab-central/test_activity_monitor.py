"""Painel de atividade: testes locais, sem rede/WhatsApp."""
import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent


class ActivityMonitorTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CENTRAL_DATA_DIR"] = self.tmp.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(self.tmp.name) / "options.json")
        spec = importlib.util.spec_from_file_location("central_activity", ROOT / "server.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init()
        self.sender = "5511999999999@s.whatsapp.net"
        with self.mod.connect() as db:
            db.execute("INSERT INTO contact_rules(sender_id,category) VALUES(?,?)",
                       (self.sender, "test"))

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, mid, message):
        return {"instance": "umdoislab", "senderId": self.sender,
                "messageId": mid, "messageText": message, "senderName": "Contato teste",
                "category": "produto", "handoffRequested": False,
                "isClientMessage": True, "isGroup": False}

    def snapshot(self):
        with self.mod.connect() as db:
            return self.mod.activity_list(db)

    def test_unanswered_is_visible_without_human_ticket(self):
        self.mod.process_inbound(self.event("m1", "Quero consultar um produto"))
        item = self.snapshot()[0]
        self.assertEqual(item["activity_status"], "unanswered")
        self.assertEqual(item["sender_name"], "Contato teste")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM conversations").fetchone()[0], 0)

    def test_duplicate_does_not_create_second_contact(self):
        self.mod.process_inbound(self.event("m1", "Primeira pergunta"))
        self.mod.process_inbound(self.event("m1", "Duplicada"))
        self.assertEqual(len(self.snapshot()), 1)
        self.assertEqual(self.snapshot()[0]["last_message"], "Primeira pergunta")

    def test_accepted_bot_response_not_claimed_delivered(self):
        self.mod.process_inbound(self.event("m1", "Preço"))
        with self.mod.connect() as db:
            db.execute("""INSERT INTO conversation_turns(sender_id,message_id,role,text,created_at)
                VALUES(?,?,?,?,?)""", (self.sender, "auto-1", "assistant", "Vou consultar", self.mod.now()))
        self.assertEqual(self.snapshot()[0]["activity_status"], "accepted")
        self.mod.process_inbound(self.event("m2", "E o estoque?"))
        self.assertEqual(self.snapshot()[0]["activity_status"], "unanswered")

    def test_human_ticket_is_not_mislabeled_as_automatic(self):
        ev = self.event("m1", "atendente")
        ev["handoffRequested"] = True
        self.mod.process_inbound(ev)
        self.assertEqual(self.snapshot()[0]["activity_status"], "pending")
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='human' WHERE sender_id=?", (self.sender,))
        self.assertEqual(self.snapshot()[0]["activity_status"], "human")

    def test_excluded_sender_does_not_enter_monitor(self):
        with self.mod.connect() as db:
            db.execute("INSERT INTO contact_rules(sender_id,category) VALUES(?, 'excluded')", (self.sender,))
        self.mod.process_inbound(self.event("m1", "Olá"))
        self.assertEqual(self.snapshot(), [])

    def test_migration_backfills_prior_turns(self):
        with self.mod.connect() as db:
            db.execute("""INSERT INTO conversation_turns(sender_id,message_id,role,text,created_at)
                VALUES(?,?,?,?,?)""", (self.sender, "old-1", "client", "Mensagem anterior", self.mod.now()))
        self.mod.init()
        self.assertEqual(self.snapshot()[0]["last_message"], "Mensagem anterior")


if __name__ == "__main__":
    unittest.main()
