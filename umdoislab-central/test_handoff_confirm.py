"""Regressão do encaminhamento humano: nenhuma chamada externa é feita."""
import importlib.util
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent


class VerifiedHandoffTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        os.environ["CENTRAL_DATA_DIR"] = self.tmp.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(self.tmp.name) / "options.json")
        spec = importlib.util.spec_from_file_location("central_verified_handoff", ROOT / "server.py")
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init()
        self.sender = "5511999999999@s.whatsapp.net"
        Path(os.environ["CENTRAL_OPTIONS"]).write_text(json.dumps({
            "evolution_url": "http://example.invalid:8080",
            "evolution_api_key": "fake-only",
            "evolution_instance": "umdoislab",
            "auto_test_sender": self.sender,
        }))

    def tearDown(self):
        self.tmp.cleanup()

    def event(self, mid, message, handoff=False):
        return {"instance": "umdoislab", "senderId": self.sender,
                "messageId": mid, "messageText": message, "senderName": "Simulação",
                "category": "outros", "handoffRequested": handoff,
                "isClientMessage": True, "isGroup": False}

    class Response:
        status = 200
        def __enter__(self): return self
        def __exit__(self, *args): return False
        def read(self, *_): return b'{}'

    class HandlerStub:
        def respond(self, status, data):
            return status, data

    def offer(self, mid="offer-1"):
        with patch.object(self.mod.urllib.request, "urlopen", return_value=self.Response()) as request:
            status, answer = self.mod.Handler.send_automated(self.HandlerStub(), {
                "instance": "umdoislab", "senderId": self.sender,
                "messageId": mid, "kind": "human_offer", "text": ""
            })
        self.assertEqual(status, 200, answer)
        self.assertIn(self.mod.HUMAN_OFFER_PROMPT,
                      json.loads(request.call_args.args[0].data)["text"])

    def test_yes_after_accepted_offer_creates_real_ticket(self):
        self.assertEqual(self.mod.process_inbound(self.event("m1", "Quanto custa?"))["action"], "auto")
        self.offer()
        result = self.mod.process_inbound(self.event("m2", "Sim"))
        self.assertEqual(result["action"], "handoff")
        self.assertEqual(result["state"], "pending")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations WHERE status='pending'").fetchone()[0], 1)
            self.assertEqual(db.execute("SELECT count(*) FROM handoff_offers").fetchone()[0], 0)
        self.assertEqual(self.mod.process_inbound(self.event("m2", "Sim"))["action"], "ignore")

    def test_generic_yes_without_prior_offer_not_handoff(self):
        self.assertEqual(self.mod.process_inbound(self.event("m1", "Sim"))["action"], "auto")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)

    def test_no_declines_and_consumes_offer(self):
        self.offer()
        self.assertEqual(self.mod.process_inbound(self.event("m2", "Não"))["action"], "auto")
        self.assertEqual(self.mod.process_inbound(self.event("m3", "Sim"))["action"], "auto")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)

    def test_unrelated_next_message_consumes_offer(self):
        self.offer()
        self.assertEqual(self.mod.process_inbound(self.event("m1", "Boa noite"))["action"], "auto")
        self.assertEqual(self.mod.process_inbound(self.event("m2", "Sim"))["action"], "auto")

    def test_expired_offer_does_not_authorize_yes(self):
        self.offer()
        with self.mod.connect() as db:
            db.execute("UPDATE handoff_offers SET created_at='2020-01-01T00:00:00+00:00'")
        self.assertEqual(self.mod.process_inbound(self.event("m2", "Sim"))["action"], "auto")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)

    def test_send_failure_does_not_register_offer(self):
        with patch.object(self.mod.urllib.request, "urlopen", side_effect=OSError("offline")):
            status, _ = self.mod.Handler.send_automated(self.HandlerStub(), {
                "instance": "umdoislab", "senderId": self.sender,
                "messageId": "offer-1", "kind": "human_offer", "text": ""
            })
        self.assertEqual(status, 502)
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM handoff_offers").fetchone()[0], 0)

    def test_hallucinated_confirmation_blocked_without_network(self):
        with patch.object(self.mod.urllib.request, "urlopen") as req:
            status, _ = self.mod.Handler.send_automated(self.HandlerStub(), {
                "instance": "umdoislab", "senderId": self.sender,
                "messageId": "m1", "kind": "normal",
                "text": "Feito! Encaminhei para um colega."
            })
        self.assertEqual(status, 422)
        req.assert_not_called()

    def test_human_assumed_blocks_offer(self):
        self.mod.process_inbound(self.event("m1", "atendente", handoff=True))
        with self.mod.connect() as db:
            db.execute("UPDATE conversations SET status='human'")
        with patch.object(self.mod.urllib.request, "urlopen") as req:
            status, _ = self.mod.Handler.send_automated(self.HandlerStub(), {
                "instance": "umdoislab", "senderId": self.sender,
                "messageId": "offer-2", "kind": "human_offer", "text": ""
            })
        self.assertEqual(status, 409)
        req.assert_not_called()

    def test_other_contact_offer_does_not_authorize(self):
        self.offer()
        other = self.event("m2", "Sim")
        other["senderId"] = "5511888888888@s.whatsapp.net"
        self.assertEqual(self.mod.process_inbound(other)["action"], "ignore")
        with self.mod.connect() as db:
            self.assertEqual(db.execute("SELECT count(*) FROM conversations").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
