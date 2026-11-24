import importlib.util
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "policy.py"
spec = importlib.util.spec_from_file_location("instagram_policy", SOURCE)
policy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(policy)


class PolicyTests(unittest.TestCase):
    def event(self, text="oi", state="bot"):
        return {"channel": "instagram", "accountId": "business", "senderId": "customer",
                "messageId": "m-1", "messageText": text, "handoffState": state,
                "claimToken": "test-claim"}

    def test_all_valid_text_reaches_shared_core_without_semantic_block(self):
        for text in ("oi", "Olá!", "preço da pracinha", "teste 2",
                     "preciso de ajuda", "qual o horário?"):
            with self.subTest(text=text):
                result = policy.prepare_decision(self.event(text))
                self.assertEqual(result["action"], "auto")
                self.assertTrue(result["mayCallGemini"])
                self.assertFalse(result["maySend"])

    def test_handoff_blocks_ai(self):
        result = policy.prepare_decision(self.event("preço", "human"))
        self.assertEqual(result["action"], "hold_for_human")
        self.assertFalse(result["mayCallGemini"])

    def test_wrong_channel_rejected(self):
        event = self.event()
        event["channel"] = "whatsapp"
        self.assertEqual(policy.prepare_decision(event)["action"], "reject")

    def test_invalid_or_empty_text_rejected(self):
        for text in ("", "   ", "x" * 2001, None):
            event = self.event()
            event["messageText"] = text
            self.assertEqual(policy.prepare_decision(event)["action"], "reject")

    def test_missing_claim_or_identity_rejected(self):
        for key in ("accountId", "senderId", "messageId", "claimToken"):
            event = self.event()
            event.pop(key)
            self.assertEqual(policy.prepare_decision(event)["action"], "reject")


if __name__ == "__main__":
    unittest.main()
