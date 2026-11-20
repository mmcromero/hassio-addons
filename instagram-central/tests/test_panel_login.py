"""Offline tests for browser sessions. No HA, Meta, network, or real credentials."""
import sqlite3
import unittest
import uuid

import panel_login


PASSWORD = "test-panel-password-long-enough"


class BrowserSessionTests(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()

    def test_session_created_and_cookie_reusable(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        self.assertRegex(token, r"^[A-Za-z0-9_-]{43}$")
        cookie = panel_login.set_cookie_header(token)
        self.assertIn("HttpOnly; SameSite=Strict", cookie)
        self.assertIn("Max-Age=43200", cookie)
        self.assertNotIn("Secure", cookie)
        self.assertTrue(panel_login.valid_session(self.db,
            "ig_panel_session=" + token, PASSWORD, now=10001))
        self.assertFalse(panel_login.valid_session(self.db,
            "ig_panel_session=" + token, PASSWORD, now=10000 + panel_login.SESSION_SECONDS))

    def test_secure_cookie_on_https(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        self.assertIn("; Secure", panel_login.set_cookie_header(token, secure=True))
        self.assertIn("Max-Age=0", panel_login.clear_cookie_header(secure=True))

    def test_no_plaintext_session_in_sqlite(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        row = self.db.execute("SELECT session_digest FROM panel_sessions").fetchone()[0]
        self.assertEqual(len(row), 64)
        self.assertNotEqual(token, row)
        self.assertNotIn(token, row)
        self.assertNotIn(PASSWORD, row)

    def test_password_change_revokes_access(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        cookie = "ig_panel_session=" + token
        self.assertTrue(panel_login.valid_session(self.db, cookie, PASSWORD, now=10001))
        self.assertFalse(panel_login.valid_session(self.db, cookie,
                          "changed-long-panel-password", now=10001))

    def test_logout_revokes_server_side(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        cookie = "ig_panel_session=" + token
        panel_login.revoke_session(self.db, cookie, PASSWORD)
        self.assertFalse(panel_login.valid_session(self.db, cookie, PASSWORD, now=10001))

    def test_malformed_and_forged_cookies_denied(self):
        token = panel_login.create_session(self.db, PASSWORD, now=10000)
        self.assertFalse(panel_login.valid_session(self.db,
            "ig_panel_session=" + ("X" * 43), PASSWORD, now=10001))
        self.assertFalse(panel_login.valid_session(self.db,
            "ig_panel_session=" + token[:-1] + "?", PASSWORD, now=10001))
        self.assertFalse(panel_login.valid_session(self.db, "junk=1", PASSWORD, now=10001))
        self.assertFalse(panel_login.valid_session(self.db, "ig_panel_session=" + token,
                                                  "", now=10001))

    def test_password_required_for_creation(self):
        with self.assertRaises(ValueError):
            panel_login.create_session(self.db, "")

    def test_rate_limiter_blocks_and_expires(self):
        client = "test-" + uuid.uuid4().hex
        try:
            for n in range(8):
                self.assertTrue(panel_login.allowed_attempt(client, now=20000))
                panel_login.failed_attempt(client, now=20000)
            self.assertFalse(panel_login.allowed_attempt(client, now=20010))
            self.assertTrue(panel_login.allowed_attempt(client, now=20121))
        finally:
            panel_login.successful_attempt(client)


if __name__ == "__main__":
    unittest.main()
