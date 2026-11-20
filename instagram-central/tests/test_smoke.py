"""Focused build smoke. Safe for HA Supervisor image build; never opens network ports."""
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path
import server


class BuildSmoke(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.original_dir = server.DATA_DIR
        self.original_db = server.DB_PATH
        server.DATA_DIR = Path(self.tmp.name)
        server.DB_PATH = server.DATA_DIR / "instagram.sqlite3"

    def tearDown(self):
        server.DATA_DIR = self.original_dir
        server.DB_PATH = self.original_db
        self.tmp.cleanup()

    def sample(self, text="oi"):
        return json.dumps({"object": "instagram", "entry": [{
            "id": "business-1", "messaging": [{
                "sender": {"id": "customer-1"},
                "recipient": {"id": "business-1"},
                "message": {"mid": "test-1", "text": text}
            }]}]}).encode("utf-8")

    def test_inbound_sqlite_schema_and_deduplication(self):
        body = self.sample()
        self.assertEqual(server.persist(body, "business-1"), 1)
        self.assertEqual(server.persist(body, "business-1"), 0)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbound").fetchone()[0], 1)

    def test_claim_decision_and_ack(self):
        self.assertEqual(server.persist(self.sample(), "business-1"), 1)
        claimed = server.claim_message()
        self.assertEqual(claimed["messageId"], "test-1")
        self.assertIsNone(server.claim_message())
        keys = ("accountId", "senderId", "messageId", "claimToken")
        reference = {key: claimed[key] for key in keys}
        decision = server.evaluate_claim(reference)
        self.assertEqual(decision["action"], "greeting")
        self.assertFalse(decision["maySend"])
        self.assertFalse(decision["mayCallGemini"])
        self.assertTrue(server.acknowledge_message(reference))
        self.assertFalse(server.acknowledge_message(reference))

    def test_handoff_blocks_bot(self):
        self.assertEqual(server.persist(self.sample(), "business-1"), 1)
        self.assertTrue(server.set_handoff({
            "accountId": "business-1",
            "senderId": "customer-1",
            "state": "human"}))
        self.assertIsNone(server.claim_message())

    def test_meta_signature_and_bridge_secret(self):
        body = self.sample()
        signature = "sha256=" + hmac.new(b"demo-secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(server.signature_valid(body, signature, "demo-secret"))
        self.assertFalse(server.signature_valid(body, signature, "different-secret"))
        self.assertFalse(server.signature_valid(body, "sha256=" + "G" * 64, "demo-secret"))
        secret = "test-bridge-secret-with-at-least-32-chars"
        self.assertTrue(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": secret}, {"bridge_secret": secret}))
        self.assertFalse(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": "short"}, {"bridge_secret": "short"}))


if __name__ == "__main__":
    unittest.main()
