"""Targeted offline tests for Meta Unified Login; never contact Meta."""
import importlib.util
import json
import os
import secrets
import sqlite3
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

BASE = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("oauth_meta", BASE / "oauth_meta.py")
oauth = importlib.util.module_from_spec(spec)
spec.loader.exec_module(oauth)

CONFIG = {
    "meta_oauth_enabled": True,
    "meta_app_id": "178361319962332",
    "meta_login_config_id": "990074610355962",
    "meta_app_secret": "LOCAL_TEST_APP_SECRET_NEVER_REAL",
    "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
    "meta_graph_version": "v24.0"
}


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, size):
        return self.payload[:size]


class OAuthTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.db = sqlite3.connect(":memory:")

    def tearDown(self):
        self.db.close()
        self.folder.cleanup()

    def test_disabled_by_default(self):
        cfg = {**CONFIG, "meta_oauth_enabled": False}
        self.assertFalse(oauth.is_ready(cfg))
        with self.assertRaises(oauth.OAuthError):
            oauth.start(self.db, cfg)

    def test_missing_credentials_and_insecure_redirect(self):
        for field in ("meta_app_id", "meta_login_config_id", "meta_app_secret"):
            self.assertFalse(oauth.is_ready({**CONFIG, field: ""}))
        self.assertFalse(oauth.is_ready({**CONFIG, "meta_oauth_redirect_uri": "http://example.org/oauth/meta/callback"}))
        self.assertFalse(oauth.is_ready({**CONFIG, "meta_oauth_redirect_uri": "https://evil.example.org/other"}))
        self.assertFalse(oauth.is_ready({**CONFIG, "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback?next=evil"}))
        self.assertFalse(oauth.is_ready({**CONFIG, "meta_graph_version": "../../latest"}))

    def test_reject_local_and_malformed_callback_hosts(self):
        for uri in (
            "https://localhost/oauth/meta/callback",
            "https://homeassistant.local/oauth/meta/callback",
            "https://[::1/oauth/meta/callback",
            "https://example.org:99999/oauth/meta/callback",
            "https:///oauth/meta/callback"
        ):
            self.assertFalse(oauth.is_ready({**CONFIG, "meta_oauth_redirect_uri": uri}))

    def test_reject_broad_key_permissions(self):
        if os.name != "posix":
            self.skipTest("POSIX permission behavior only")
        credential = {"access_token": "A" * 40}
        oauth.store_token(self.folder.name, credential)
        key = Path(self.folder.name, oauth.KEY_FILENAME)
        key.chmod(0o644)
        with self.assertRaises(oauth.OAuthError):
            oauth.store_token(self.folder.name, credential)

    def test_start_sets_secure_cookie_and_exact_config(self):
        url, cookie = oauth.start(self.db, CONFIG)
        params = parse_qs(urlsplit(url).query)
        self.assertEqual(urlsplit(url).netloc, "www.facebook.com")
        self.assertEqual(params["config_id"], [CONFIG["meta_login_config_id"]])
        self.assertEqual(params["client_id"], [CONFIG["meta_app_id"]])
        self.assertEqual(params["redirect_uri"], [CONFIG["meta_oauth_redirect_uri"]])
        self.assertEqual(params["response_type"], ["code"])
        self.assertNotIn("scope", params)
        self.assertNotIn(CONFIG["meta_app_secret"], url)
        self.assertIn("Secure; HttpOnly; SameSite=Lax", cookie)
        self.assertIn("Path=/oauth/meta/callback", cookie)
        cookie_name, cookie_value = cookie.split(";", 1)[0].split("=", 1)
        self.assertEqual(cookie_name, oauth._state_cookie_name(params["state"][0]))
        self.assertEqual(cookie_value, params["state"][0])

    def test_callback_requires_browser_cookie_and_no_duplicates(self):
        url, cookie = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        query = "code=test-code&state=" + state
        self.assertEqual(oauth.parse_callback(query, cookie) , (state, "test-code"))
        with self.assertRaisesRegex(oauth.OAuthError, "OAuth state cookie missing"):
            oauth.parse_callback(query, "")
        with self.assertRaises(oauth.OAuthError):
            oauth.parse_callback(query + "&state=attacker", cookie)
        with self.assertRaises(oauth.OAuthError):
            oauth.parse_callback("state=" + state + "&code=a&code=b", cookie)

    def test_callback_distinguishes_duplicate_state_cookie(self):
        url, cookie = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        query = "code=test-code&state=" + state
        cookie_pair = cookie.split(";", 1)[0]
        with self.assertRaisesRegex(oauth.OAuthError, "OAuth state cookie duplicated"):
            oauth.parse_callback(query, cookie + "; " + cookie_pair)

    def test_callback_distinguishes_mismatched_state_cookie(self):
        url, cookie = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        query = "code=test-code&state=" + state
        wrong_value = ("A" if state[0] != "A" else "B") + state[1:]
        wrong_cookie = oauth._state_cookie_name(state) + "=" + wrong_value
        with self.assertRaisesRegex(oauth.OAuthError, "OAuth browser state mismatch"):
            oauth.parse_callback(query, wrong_cookie)

    def test_concurrent_oauth_starts_keep_independent_browser_cookies(self):
        url1, cookie1 = oauth.start(self.db, CONFIG)
        url2, cookie2 = oauth.start(self.db, CONFIG)
        state1 = parse_qs(urlsplit(url1).query)["state"][0]
        state2 = parse_qs(urlsplit(url2).query)["state"][0]
        pair1 = cookie1.split(";", 1)[0]
        pair2 = cookie2.split(";", 1)[0]
        self.assertNotEqual(pair1.split("=", 1)[0], pair2.split("=", 1)[0])
        browser_cookies = pair1 + "; " + pair2
        self.assertEqual(
            oauth.parse_callback("code=first&state=" + state1, browser_cookies),
            (state1, "first"))
        self.assertEqual(
            oauth.parse_callback("code=second&state=" + state2, browser_cookies),
            (state2, "second"))
        with self.assertRaisesRegex(oauth.OAuthError, "OAuth state cookie missing"):
            oauth.parse_callback("code=first&state=" + state1, pair2)

    def test_legacy_shared_state_cookie_is_not_accepted(self):
        url, _ = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        with self.assertRaisesRegex(oauth.OAuthError, "OAuth state cookie missing"):
            oauth.parse_callback(
                "code=test-code&state=" + state, "ig_oauth_state=" + state)

    def test_cookie_probe_validates_browser_roundtrip_without_meta(self):
        url, cookie = oauth.start_cookie_probe(CONFIG)
        callback = urlsplit(url)
        nonce = parse_qs(callback.query)["probe"][0]
        self.assertEqual(callback.scheme, "https")
        self.assertEqual(callback.path, "/oauth/meta/callback")
        self.assertEqual(len(nonce), 43)
        self.assertIn("Path=/oauth/meta/callback", cookie)
        self.assertIn("Secure; HttpOnly; SameSite=Lax", cookie)
        cookie_name, cookie_value = cookie.split(";", 1)[0].split("=", 1)
        self.assertEqual(cookie_name, oauth._state_cookie_name(nonce))
        self.assertEqual(cookie_value, nonce)
        self.assertTrue(oauth.check_cookie_probe(callback.query, cookie))
        # The probe uses the same cookie parser and state-derived name as OAuth.
        wrong_value = ("A" if nonce[0] != "A" else "B") + nonce[1:]
        wrong_cookie = oauth._state_cookie_name(nonce) + "=" + wrong_value
        with self.assertRaisesRegex(oauth.OAuthError, "cookie probe mismatch"):
            oauth.check_cookie_probe(callback.query, wrong_cookie)
        other_nonce = secrets.token_urlsafe(32)
        other_cookie = oauth._state_cookie_name(other_nonce) + "=" + other_nonce
        with self.assertRaisesRegex(oauth.OAuthError, "cookie probe missing"):
            oauth.check_cookie_probe(callback.query, other_cookie)
        # A probe does not create OAuth states or start a Meta authorization.
        self.assertIsNone(self.db.execute(
            "SELECT name FROM sqlite_master WHERE name='meta_oauth_states'").fetchone())
        with self.assertRaisesRegex(oauth.OAuthError, "cookie probe missing"):
            oauth.check_cookie_probe(callback.query, "")
        with self.assertRaisesRegex(oauth.OAuthError, "cookie probe duplicated"):
            oauth.check_cookie_probe(callback.query, cookie + "; " +
                                     cookie.split(";", 1)[0])
        other = ("A" if nonce[0] != "A" else "B") + nonce[1:]
        with self.assertRaisesRegex(oauth.OAuthError, "cookie probe missing"):
            oauth.check_cookie_probe(callback.query, "ig_oauth_probe=" + other)
        for bad in ("probe=short", "probe=" + nonce + "&probe=" + nonce,
                    "code=ignored&probe=" + nonce, "probe=" + nonce + "&state=other"):
            with self.assertRaisesRegex(oauth.OAuthError, "cookie probe invalid"):
                oauth.check_cookie_probe(bad, cookie)

    def test_replay_and_expiry_fail_closed(self):
        with patch.object(oauth.time, "time", return_value=100000):
            url, cookie = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        self.db.commit()
        oauth.consume_state(self.db, state, now=100001, cfg=CONFIG)
        self.db.commit()
        with self.assertRaises(oauth.OAuthError):
            oauth.consume_state(self.db, state, now=100002, cfg=CONFIG)
        with patch.object(oauth.time, "time", return_value=100000):
            new_url, cookie = oauth.start(self.db, CONFIG)
        state2 = parse_qs(urlsplit(new_url).query)["state"][0]
        self.db.commit()
        with self.assertRaises(oauth.OAuthError):
            oauth.consume_state(self.db, state2, now=100700, cfg=CONFIG)

    def test_cancel_rejected_without_exchange(self):
        url, cookie = oauth.start(self.db, CONFIG)
        state = parse_qs(urlsplit(url).query)["state"][0]
        with self.assertRaises(oauth.OAuthError):
            oauth.parse_callback("state=" + state + "&error=access_denied", cookie)

    def test_graph_exchange_uses_get_and_fixed_host(self):
        sent = {}
        def opener(req, timeout):
            sent["req"] = req
            sent["timeout"] = timeout
            return FakeResponse(json.dumps({"access_token": "A" * 40, "expires_in": 0}).encode())
        result = oauth.exchange_code("dummy-test-code", CONFIG, opener=opener)
        self.assertEqual(result["access_token"], "A" * 40)
        self.assertEqual(sent["req"].get_method(), "GET")
        parts = urlsplit(sent["req"].full_url)
        self.assertEqual(parts.netloc, "graph.facebook.com")
        self.assertEqual(parts.path, "/v24.0/oauth/access_token")
        params = parse_qs(parts.query)
        self.assertEqual(params["code"], ["dummy-test-code"])
        self.assertEqual(params["client_id"], [CONFIG["meta_app_id"]])
        self.assertEqual(params["client_secret"], [CONFIG["meta_app_secret"]])
        self.assertEqual(params["redirect_uri"], [CONFIG["meta_oauth_redirect_uri"]])
        self.assertNotIn("config_id", params)
        self.assertIsNone(sent["req"].data)

    def test_graph_exchange_requires_and_includes_redirect_uri(self):
        """Regression test: Meta Graph /oauth/access_token requires redirect_uri identical to dialog."""
        captured = {}
        def opener(req, timeout):
            captured["url"] = req.full_url
            return FakeResponse(json.dumps({"access_token": "T" * 40, "expires_in": 3600}).encode())
        res = oauth.exchange_code("code-123", CONFIG, opener=opener)
        self.assertEqual(res["access_token"], "T" * 40)
        query = parse_qs(urlsplit(captured["url"]).query)
        self.assertEqual(query.get("redirect_uri"), [CONFIG["meta_oauth_redirect_uri"]])
        self.assertEqual(query.get("client_id"), [CONFIG["meta_app_id"]])
        self.assertEqual(query.get("client_secret"), [CONFIG["meta_app_secret"]])
        self.assertEqual(query.get("code"), ["code-123"])

    def test_graph_error_and_oversized_response(self):
        def bad(*args, **kwargs):
            return FakeResponse(b'{"error":{"message":"denied"}}')
        with self.assertRaises(oauth.OAuthError):
            oauth.exchange_code("code", CONFIG, opener=bad)
        def huge(*args, **kwargs):
            return FakeResponse(b"X" * (oauth.MAX_TOKEN_BYTES + 10))
        with self.assertRaises(oauth.OAuthError):
            oauth.exchange_code("code", CONFIG, opener=huge)

    def test_secure_credential_load_and_invalid_file(self):
        credential = {"access_token": "A" * 40, "account_id": "17841454345931235"}
        self.assertIsNone(oauth.load_token(self.folder.name))
        oauth.store_token(self.folder.name, credential)
        self.assertEqual(oauth.load_token(self.folder.name), credential)
        file = Path(self.folder.name) / oauth.TOKEN_FILENAME
        file.write_text("not encrypted")
        with self.assertRaises(oauth.OAuthError):
            oauth.load_token(self.folder.name)

    def test_encrypted_storage_has_no_plaintext(self):
        credential = {"access_token": "A" * 40, "received_at": 5000, "expires_in": 0}
        oauth.store_token(self.folder.name, credential)
        saved = Path(self.folder.name, oauth.TOKEN_FILENAME)
        key = Path(self.folder.name, oauth.KEY_FILENAME)
        self.assertTrue(oauth.token_exists(self.folder.name))
        self.assertNotIn("A" * 40, saved.read_text())
        from cryptography.fernet import Fernet
        restored = json.loads(Fernet(key.read_bytes()).decrypt(saved.read_bytes()))
        self.assertEqual(restored, credential)
        if os.name == "posix":
            self.assertEqual(saved.stat().st_mode & 0o777, 0o600)
            self.assertEqual(key.stat().st_mode & 0o777, 0o600)


if __name__ == "__main__":
    unittest.main()
