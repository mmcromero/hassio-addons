import importlib.util
import unittest
from pathlib import Path
from urllib.parse import urlencode

SRC = Path(__file__).resolve().parents[1] / "panel_actions.py"
spec = importlib.util.spec_from_file_location("instagram_panel_actions", SRC)
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class PanelActionsTests(unittest.TestCase):
    PASSWORD = "strong-test-password-12345"

    def form(self, account="ig-business", sender="ig-customer", state="human", secret=None):
        pwd = self.PASSWORD if secret is None else secret
        token = panel.token_for(account, sender, state, pwd)
        return urlencode({"accountId": account, "senderId": sender,
                          "state": state, "csrf": token}).encode()

    def test_valid_action(self):
        self.assertEqual(panel.parse_action(self.form(), self.PASSWORD),
                         {"accountId": "ig-business", "senderId": "ig-customer", "state": "human"})

    def test_wrong_password_rejected(self):
        self.assertIsNone(panel.parse_action(self.form(), "another-strong-password"))

    def test_changed_target_rejected(self):
        raw = self.form().replace(b"ig-customer", b"ig-attacker")
        self.assertIsNone(panel.parse_action(raw, self.PASSWORD))

    def test_unexpected_state_rejected(self):
        self.assertIsNone(panel.parse_action(self.form(state="unknown"), self.PASSWORD))

    def test_reject_duplicate_parameters(self):
        self.assertIsNone(panel.parse_action(self.form() + b"&state=bot", self.PASSWORD))

    def test_account_must_differ_from_sender(self):
        self.assertIsNone(panel.parse_action(self.form(sender="ig-business"), self.PASSWORD))

    def test_expired_token_rejected(self):
        token = panel.token_for("ig-business", "ig-customer", "human",
                                self.PASSWORD, bucket=1)
        raw = urlencode({"accountId": "ig-business", "senderId": "ig-customer",
                         "state": "human", "csrf": token}).encode()
        self.assertIsNone(panel.parse_action(raw, self.PASSWORD))

    def test_reject_missing_fields(self):
        self.assertIsNone(panel.parse_action(b"accountId=ig-business", self.PASSWORD))

    def test_reject_large_body(self):
        self.assertIsNone(panel.parse_action(b"x" * 4097, self.PASSWORD))


if __name__ == "__main__":
    unittest.main()
