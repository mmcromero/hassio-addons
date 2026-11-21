"""Safe diagnostics and state/config regressions. Synthetic data and no network."""
import io
import json
import socket
import sqlite3
import ssl
import sys
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qs, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import oauth_meta as oauth

CONFIG = {"meta_oauth_enabled": True, "meta_app_id": "12345678", "meta_login_config_id": "87654321",
          "meta_app_secret": "synthetic-secret-no-provider-1234", "meta_graph_version": "v27.0",
          "meta_oauth_redirect_uri": "https://example.test:8443/oauth/meta/callback",
          "business_id": "umdoislab", "instagram_account_id": "11111111"}


class Response:
    def __init__(self, raw): self.raw = raw
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def read(self, size): return self.raw[:size]


class SafeDiagnosticsTests(unittest.TestCase):
    def test_cookie_presence_does_not_confuse_absent_unrelated_and_other_attempt(self):
        target, cookie = oauth.start_cookie_probe(CONFIG)
        query = urlsplit(target).query
        _, other = oauth.start_cookie_probe(CONFIG)
        cases = [("", False, False, False), ("unrelated=PRIVATE_VALUE", True, False, False),
                 (other.split(";", 1)[0], True, True, False),
                 (cookie.split(";", 1)[0], True, True, True),
                 ("ig_oauth_probe=PRIVATE_VALUE", True, False, False)]
        for header, present, related, expected in cases:
            with self.subTest(present=present, related=related, expected=expected):
                diagnostic = oauth.cookie_diagnostics(query, header, probe=True)
                self.assertEqual(diagnostic["cookie_header_present"], present)
                self.assertEqual(diagnostic["state_cookie_present"], related)
                self.assertEqual(diagnostic["expected_cookie_present"], expected)
                self.assertTrue(all(type(v) in (bool, int) for v in diagnostic.values()))
                self.assertNotIn("PRIVATE_VALUE", repr(diagnostic))
                self.assertNotIn(parse_qs(query)["probe"][0], repr(diagnostic))

    def test_cookie_diagnostics_bound_count_and_malformed_query(self):
        target, cookie = oauth.start_cookie_probe(CONFIG)
        pair = cookie.split(";", 1)[0]
        self.assertEqual(oauth.cookie_diagnostics(urlsplit(target).query, "; ".join([pair] * 9), probe=True)["expected_cookie_count"], 3)
        for query in ("probe=short", "probe=x&probe=y", "probe=" + "x" * 9000, "state=é" * 3):
            self.assertFalse(oauth.cookie_diagnostics(query, pair, probe=True)["query_state_valid"])

    def test_http_errors_expose_only_allowlisted_numbers(self):
        forbidden = "PRIVATE_MESSAGE_URL_CODE_TOKEN_SECRET"
        raw = json.dumps({"error": {"message": forbidden, "type": forbidden, "code": 100, "error_subcode": 36008},
                          "access_token": forbidden}).encode()
        def fake(*_a, **_k):
            raise HTTPError("https://example.invalid/?secret=" + forbidden, 400, forbidden,
                            {"Secret": forbidden}, io.BytesIO(raw))
        with self.assertRaises(oauth.OAuthExchangeError) as caught:
            oauth.exchange_code(forbidden, CONFIG, opener=fake)
        error = caught.exception
        self.assertEqual(error.kind, "http")
        self.assertEqual(error.http_status, 400)
        self.assertEqual(error.provider_code, 100)
        self.assertEqual(error.provider_subcode, 36008)
        self.assertNotIn(forbidden, str(error) + error.safe_details())

    def test_provider_fields_reject_booleans_strings_negative_and_unbounded_integers(self):
        for value in (True, "SECRET", -1, 2**40, [100], {"code": 100}):
            with self.subTest(value_type=type(value).__name__):
                raw = json.dumps({"error": {"code": value, "error_subcode": value}}).encode()
                with self.assertRaises(oauth.OAuthExchangeError) as caught:
                    oauth.exchange_code("synthetic", CONFIG, opener=lambda *_a, **_k: Response(raw))
                self.assertIsNone(caught.exception.provider_code)
                self.assertIsNone(caught.exception.provider_subcode)

    def test_http_body_malformed_oversize_and_read_failure_are_not_logged(self):
        for raw in (b"not json PRIVATE", b"X" * (oauth.MAX_TOKEN_BYTES + 1)):
            def fake(*_a, **_k): raise HTTPError("https://example.invalid/", 502, "PRIVATE", {}, io.BytesIO(raw))
            with self.assertRaises(oauth.OAuthExchangeError) as caught:
                oauth.exchange_code("synthetic", CONFIG, opener=fake)
            self.assertEqual(caught.exception.http_status, 502)
            self.assertIsNone(caught.exception.provider_code)
            self.assertNotIn("PRIVATE", caught.exception.safe_details())

    def test_transport_failures_remain_distinguishable_without_raw_details(self):
        for kind, reason in (("tls", ssl.SSLError("PRIVATE")), ("timeout", TimeoutError("PRIVATE")),
                             ("dns", socket.gaierror("PRIVATE")), ("network", OSError("PRIVATE"))):
            for wrapped in (False, True):
                def fake(*_a, **_k): raise URLError(reason) if wrapped else reason
                with self.assertRaises(oauth.OAuthExchangeError) as caught:
                    oauth.exchange_code("synthetic", CONFIG, opener=fake)
                self.assertEqual(caught.exception.kind, kind)
                self.assertNotIn("PRIVATE", caught.exception.safe_details())

    def test_json_failure_is_separate_and_success_contract_unchanged(self):
        with self.assertRaises(oauth.OAuthExchangeError) as caught:
            oauth.exchange_code("synthetic", CONFIG, opener=lambda *_a, **_k: Response(b"{"))
        self.assertEqual(caught.exception.kind, "invalid_json")
        def fake(req, timeout):
            query = parse_qs(urlsplit(req.full_url).query)
            self.assertEqual(query["redirect_uri"], [CONFIG["meta_oauth_redirect_uri"]])
            self.assertEqual(req.method, "GET")
            return Response(json.dumps({"access_token": "SYNTHETIC" * 5, "expires_in": 10}).encode())
        self.assertEqual(oauth.exchange_code("synthetic", CONFIG, opener=fake)["expires_in"], 10)


class AuthorizationContextTests(unittest.TestCase):
    def test_config_changes_cannot_consume_original_attempt(self):
        for key, value in (("meta_app_id", "23456789"), ("meta_login_config_id", "34567890"),
                           ("meta_oauth_redirect_uri", "https://other.test/oauth/meta/callback"),
                           ("meta_graph_version", "v26.0"), ("business_id", "synthetic_b"),
                           ("instagram_account_id", "22222222")):
            with self.subTest(field=key), sqlite3.connect(":memory:") as db:
                target, _ = oauth.start(db, CONFIG, now=1000); db.commit()
                state = parse_qs(urlsplit(target).query)["state"][0]
                with self.assertRaisesRegex(oauth.OAuthError, "configuration changed"):
                    with db: oauth.consume_state(db, state, now=1001, cfg={**CONFIG, key: value})
                with db: oauth.consume_state(db, state, now=1001, cfg=CONFIG)

    def test_old_schema_and_inflight_state_fail_closed_without_deleting_records(self):
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE meta_oauth_states(digest TEXT PRIMARY KEY,expires_at INTEGER NOT NULL,consumed_at INTEGER)")
            db.execute("INSERT INTO meta_oauth_states VALUES('legacy',9999999999,NULL)"); db.commit()
            target, _ = oauth.start(db, CONFIG, now=1000); db.commit()
            columns = {r[1] for r in db.execute("PRAGMA table_info(meta_oauth_states)")}
            self.assertIn("authorization_context", columns)
            self.assertEqual(db.execute("SELECT authorization_context FROM meta_oauth_states WHERE digest='legacy'").fetchone()[0], "")
            state = parse_qs(urlsplit(target).query)["state"][0]
            with db: oauth.consume_state(db, state, now=1001, cfg=CONFIG)
            self.assertEqual(db.execute("SELECT COUNT(*) FROM meta_oauth_states").fetchone()[0], 2)

    def test_parallel_starts_upgrade_legacy_schema_once(self):
        from concurrent.futures import ThreadPoolExecutor
        import tempfile
        import threading
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "synthetic.sqlite3")
            with sqlite3.connect(path) as db:
                db.execute("CREATE TABLE meta_oauth_states(digest TEXT PRIMARY KEY,expires_at INTEGER NOT NULL,consumed_at INTEGER)")
            barrier = threading.Barrier(2)
            def start(_):
                with sqlite3.connect(path, timeout=10) as db:
                    barrier.wait(timeout=3)
                    oauth.start(db, CONFIG)
                return True
            with ThreadPoolExecutor(2) as pool:
                self.assertEqual(list(pool.map(start, range(2))), [True, True])
            with sqlite3.connect(path) as db:
                self.assertEqual(db.execute("SELECT COUNT(*) FROM meta_oauth_states").fetchone()[0], 2)

    def test_two_businesses_tabs_expiry_and_replay(self):
        other = {**CONFIG, "business_id": "synthetic_b", "instagram_account_id": "22222222"}
        with sqlite3.connect(":memory:") as db:
            u1, c1 = oauth.start(db, CONFIG, now=1000)
            u2, c2 = oauth.start(db, other, now=1000); db.commit()
            s1, s2 = [parse_qs(urlsplit(u).query)["state"][0] for u in (u1, u2)]
            self.assertNotEqual(oauth._state_cookie_name(s1), oauth._state_cookie_name(s2))
            header = c1.split(";", 1)[0] + "; " + c2.split(";", 1)[0]
            for state in (s1, s2): self.assertEqual(oauth.parse_callback("state=" + state + "&code=synthetic", header)[0], state)
            with self.assertRaises(oauth.OAuthError):
                with db: oauth.consume_state(db, s1, now=1001, cfg=other)
            with db: oauth.consume_state(db, s1, now=1001, cfg=CONFIG)
            with self.assertRaises(oauth.OAuthError):
                with db: oauth.consume_state(db, s1, now=1002, cfg=CONFIG)
            with self.assertRaises(oauth.OAuthError):
                with db: oauth.consume_state(db, s2, now=1601, cfg=other)


if __name__ == "__main__": unittest.main()
