"""Local HTTP contract tests. The server binds only to 127.0.0.1, never Meta/n8n."""
import base64
import hashlib
import hmac
import importlib.util
import json
import sys
import tempfile
import threading
import unittest
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
from pathlib import Path
from urllib.parse import urlencode

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("instagram_http_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
from panel_actions import token_for


class HTTPContractTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_dir, self.old_db, self.old_settings = server.DATA_DIR, server.DB_PATH, server.settings
        server.DATA_DIR = Path(self.tmp.name)
        server.DB_PATH = server.DATA_DIR / "instagram.sqlite3"
        self.config = {
            "meta_app_secret": "test-meta-app-secret",
            "meta_verify_token": "test-verify-token",
            "instagram_account_id": "business-1",
            "panel_password": "test-panel-password-long-enough",
            "bridge_secret": "test-bridge-secret-with-at-least-32-characters",
            "ingress_enabled": True,
            "drafts_enabled": False,
        }
        server.settings = lambda: self.config
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = "http://127.0.0.1:%d" % self.http.server_address[1]

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)
        server.DATA_DIR, server.DB_PATH, server.settings = self.old_dir, self.old_db, self.old_settings
        self.tmp.cleanup()

    def request(self, path, method="GET", body=None, headers=None):
        connection = HTTPConnection("127.0.0.1", self.http.server_address[1], timeout=3)
        try:
            connection.request(method, path, body=body, headers=headers or {})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def event(self):
        return json.dumps({"object": "instagram", "entry": [{"id": "business-1",
            "messaging": [{"sender": {"id": "customer-1"}, "recipient": {"id": "business-1"},
                            "message": {"mid": "m1", "text": "oi"}}]}]}).encode()

    def post_event(self, valid=True):
        raw = self.event()
        digest = hmac.new(self.config["meta_app_secret"].encode(), raw, hashlib.sha256).hexdigest()
        signature = "sha256=" + (digest if valid else "0" * 64)
        return self.request("/webhook/instagram", "POST", raw,
                            {"X-Hub-Signature-256": signature, "Content-Type": "application/json"})

    def admin_header(self):
        raw = ("admin:" + self.config["panel_password"]).encode()
        return {"Authorization": "Basic " + base64.b64encode(raw).decode()}

    def bridge_header(self):
        return {"X-Instagram-Bridge-Secret": self.config["bridge_secret"],
                "Content-Type": "application/json"}

    def test_meta_challenge_good_and_bad(self):
        status, _, body = self.request("/webhook/instagram?hub.mode=subscribe&hub.verify_token=test-verify-token&hub.challenge=123")
        self.assertEqual((status, body), (200, b"123"))
        status, _, _ = self.request("/webhook/instagram?hub.mode=subscribe&hub.verify_token=wrong&hub.challenge=123")
        self.assertEqual(status, 403)

    def test_meta_challenge_unicode_token_is_denied_safely(self):
        status, _, _ = self.request(
            "/webhook/instagram?hub.mode=subscribe&hub.verify_token=%C3%A9&hub.challenge=123")
        self.assertEqual(status, 403)

    def test_bad_signature_rejected_without_persist(self):
        self.assertEqual(self.post_event(False)[0], 403)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbound").fetchone()[0], 0)

    def test_signed_webhook_idempotent(self):
        self.assertEqual(self.post_event()[0], 200)
        self.assertEqual(self.post_event()[0], 200)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbound").fetchone()[0], 1)

    def test_disabled_meta_webhook(self):
        self.config["ingress_enabled"] = False
        self.assertEqual(self.post_event()[0], 503)

    def test_panel_requires_login_and_escapes(self):
        self.assertEqual(self.post_event()[0], 200)
        self.assertEqual(self.request("/panel")[0], 401)
        status, headers, body = self.request("/panel", headers=self.admin_header())
        self.assertEqual(status, 200)
        self.assertIn(b"Assumir", body)
        self.assertIn("Content-Security-Policy", headers)

    def test_panel_form_requires_valid_csrf(self):
        self.assertEqual(self.post_event()[0], 200)
        form = {"accountId": "business-1", "senderId": "customer-1", "state": "human",
                "csrf": "invalid"}
        headers = {**self.admin_header(), "Content-Type": "application/x-www-form-urlencoded"}
        self.assertEqual(self.request("/panel/handoff", "POST", urlencode(form).encode(), headers)[0], 403)
        form["csrf"] = token_for("business-1", "customer-1", "human", self.config["panel_password"])
        status, response_headers, _ = self.request("/panel/handoff", "POST", urlencode(form).encode(), headers)
        self.assertEqual(status, 303)
        self.assertEqual(response_headers.get("Location"), "../panel")
        with server.database() as conn:
            row = conn.execute("SELECT state FROM handoff WHERE sender_id='customer-1'").fetchone()
            self.assertEqual(row, ("human",))

    def test_bridge_secret_required_for_claim(self):
        self.assertEqual(self.request("/bridge/claim", "POST")[0], 403)
        self.assertEqual(self.post_event()[0], 200)
        status, _, data = self.request("/bridge/claim", "POST", headers=self.bridge_header())
        self.assertEqual(status, 200)
        self.assertEqual(json.loads(data)["message"]["messageId"], "m1")

    def test_decision_with_valid_claim_no_send(self):
        self.assertEqual(self.post_event()[0], 200)
        status, _, raw = self.request("/bridge/claim", "POST", headers=self.bridge_header())
        item = json.loads(raw)["message"]
        claim = {key: item[key] for key in ("accountId", "senderId", "messageId", "claimToken")}
        status, _, data = self.request("/bridge/decision", "POST", json.dumps(claim).encode(), self.bridge_header())
        self.assertEqual(status, 200)
        decision = json.loads(data)["decision"]
        self.assertEqual(decision["action"], "greeting")
        self.assertFalse(decision["maySend"])
        self.assertFalse(decision["mayCallGemini"])

    def test_draft_endpoint_disabled_by_default(self):
        self.assertEqual(self.post_event()[0], 200)
        status, _, raw = self.request("/bridge/claim", "POST", headers=self.bridge_header())
        item = json.loads(raw)["message"]
        draft = {key: item[key] for key in ("accountId", "senderId", "messageId", "claimToken")}
        draft["draftText"] = "Olá, como posso ajudar?"
        status, _, _ = self.request("/bridge/draft", "POST", json.dumps(draft).encode(), self.bridge_header())
        self.assertEqual(status, 503)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
