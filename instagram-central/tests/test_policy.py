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

    def test_greeting_without_product(self):
        for text in ("oi", "Oi!", "olá", "bom dia", "Boa tarde."):
            self.assertEqual(policy.prepare_decision(self.event(text))["action"], "greeting")

    def test_product_questions_are_distinct(self):
        self.assertEqual(policy.prepare_decision(
            self.event("Qual o preço do produto?"))["action"], "commercial_question")

    def test_ambiguous_message_routes_to_human(self):
        self.assertEqual(policy.prepare_decision(self.event("preciso de ajuda"))["action"], "human_review")

    def test_handoff_blocks_ai(self):
        result = policy.prepare_decision(self.event("preço", "human"))
        self.assertEqual(result["action"], "hold_for_human")
        self.assertFalse(result["mayCallGemini"])

    def test_wrong_channel_rejected(self):
        event = self.event()
        event["channel"] = "whatsapp"
        self.assertEqual(policy.prepare_decision(event)["action"], "reject")

    def test_never_sends(self):
        for text in ("oi", "preço da pracinha", "qualquer coisa"):
            decision = policy.prepare_decision(self.event(text))
            self.assertFalse(decision["maySend"])
            self.assertFalse(decision["mayCallGemini"])


if __name__ == "__main__":
    unittest.main()
