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
from urllib.parse import urlencode, parse_qs, urlsplit
from unittest.mock import patch

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
            "meta_oauth_enabled": False,
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

    def test_get_routes_do_not_shadow_urlsplit(self):
        # Regression: v0.1.2 crashed every GET with UnboundLocalError on urlsplit.
        health_status, _, health_body = self.request("/health")
        self.assertEqual(health_status, 200)
        self.assertEqual(json.loads(health_body)["version"], "0.1.34")
        status, headers, body = self.request("/panel")
        self.assertEqual(status, 200)
        self.assertNotIn("WWW-Authenticate", headers)
        self.assertIn(b'autocomplete="current-password"', body)
        # Basic cannot bypass the on-page login.
        status, _, body = self.request("/panel", headers=self.admin_header())
        self.assertEqual(status, 200)
        self.assertIn(b'autocomplete="current-password"', body)
        # Disabled webhook must be explicitly disabled in this test fixture.
        self.assertEqual(self.request("/webhook/instagram?hub.mode=subscribe")[0], 403)
        self.config["ingress_enabled"] = False
        self.assertEqual(self.request("/webhook/instagram?hub.mode=subscribe")[0], 503)

    def test_oauth_off_by_default_and_admin_only(self):
        self.assertEqual(self.request("/oauth/meta/status")[0], 401)
        status, _, body = self.request("/oauth/meta/status", headers=self.admin_header())
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertFalse(result["enabled"])
        self.assertFalse(result["credentialStored"])
        self.assertFalse(result["sendingEnabled"])
        self.assertEqual(self.request("/oauth/meta/start", headers=self.admin_header())[0], 503)
        self.assertEqual(self.request("/oauth/meta/callback?code=abc&state=fake")[0], 503)

    def test_oauth_callback_requires_state_and_does_not_expose_token(self):
        self.config.update({
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
            "meta_graph_version": "v24.0",
            "instagram_account_id": "17841454345931235"})
        status, headers, _ = self.request("/oauth/meta/start", headers=self.admin_header())
        self.assertEqual(status, 302)
        self.assertTrue(headers["Location"].startswith("https://www.facebook.com/dialog/oauth?"))
        self.assertIn("Secure; HttpOnly; SameSite=Lax", headers["Set-Cookie"])
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        params = urlencode({"code": "test-only-code", "state": state})
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertEqual(self.request("/oauth/meta/callback?" + params)[0], 400)
        credential = {"access_token": "X"*40, "expires_in": 0, "received_at": 5000}
        identity = {"account_id": "17841454345931235", "username": "umdoislab",
                    "client_business_id": "338861439025441", "verified_at": 10000}
        with patch.object(server.oauth_meta, "exchange_code", return_value=credential) as exchange, \
             patch.object(server.instagram_connection, "verify_access", return_value=identity) as verify:
            status, _, body = self.request("/oauth/meta/callback?" + params,
                                          headers={"Cookie": cookie})
            self.assertEqual(status, 200)
            self.assertNotIn(b"X"*40, body)
            self.assertEqual(exchange.call_count, 1)
            self.assertEqual(self.request("/oauth/meta/callback?" + params,
                                          headers={"Cookie": cookie})[0], 400)
        status, _, body = self.request("/oauth/meta/status", headers=self.admin_header())
        self.assertTrue(json.loads(body)["credentialStored"])
        self.assertTrue(json.loads(body)["accountVerified"])
        self.assertFalse(json.loads(body)["sendingEnabled"])

    def test_oauth_callback_logs_safe_failure_stage_without_code(self):
        self.config.update({
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
            "meta_graph_version": "v27.0",
            "instagram_account_id": "17841454345931235"})
        status, headers, _ = self.request("/oauth/meta/start", headers=self.admin_header())
        self.assertEqual(status, 302)
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        params = urlencode({"code": "test-only-code", "state": state})
        with patch.object(server.oauth_meta, "exchange_code",
                          side_effect=server.oauth_meta.OAuthError("Meta authorization exchange failed")):
            with self.assertLogs(server.LOGGER, level="ERROR") as captured:
                status, _, _ = self.request("/oauth/meta/callback?" + params,
                                            headers={"Cookie": cookie})
        self.assertEqual(status, 400)
        diagnostic = "\n".join(captured.output)
        self.assertIn("stage=exchange_code", diagnostic)
        self.assertNotIn("test-only-code", diagnostic)
        self.assertNotIn(state, diagnostic)

    def test_oauth_callback_exchange_passes_redirect_uri_and_succeeds(self):
        """End-to-end regression test: callback invokes exchange_code which sends redirect_uri to Meta."""
        class _Resp:
            def __init__(self, data):
                self._data = data
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size):
                return self._data[:size]

        self.config.update({
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
            "meta_graph_version": "v27.0",
            "instagram_account_id": "17841454345931235"})
        status, headers, _ = self.request("/oauth/meta/start", headers=self.admin_header())
        self.assertEqual(status, 302)
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        params = urlencode({"code": "valid-auth-code", "state": state})
        sent_requests = []
        def fake_opener(req, timeout=12):
            sent_requests.append(req)
            return _Resp(json.dumps({"access_token": "T" * 40, "expires_in": 3600}).encode("utf-8"))
        identity = {"account_id": "17841454345931235", "username": "umdoislab",
                    "client_business_id": "338861439025441", "verified_at": 10000}
        with patch.object(server.oauth_meta, "urlopen", fake_opener), \
             patch.object(server.instagram_connection, "verify_access", return_value=identity):
            status, _, body = self.request("/oauth/meta/callback?" + params,
                                          headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn("Conta @umdoislab verificada e autorizada".encode("utf-8"), body)
        self.assertEqual(len(sent_requests), 1)
        req_query = parse_qs(urlsplit(sent_requests[0].full_url).query)
        self.assertEqual(req_query.get("redirect_uri"), ["https://example.org/oauth/meta/callback"])
        self.assertEqual(req_query.get("code"), ["valid-auth-code"])

    def test_oauth_callback_logs_cookie_and_proxy_diagnostics_safely(self):
        self.config.update({
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
            "meta_graph_version": "v27.0",
            "instagram_account_id": "17841454345931235"})
        status, headers, _ = self.request("/oauth/meta/start", headers=self.admin_header())
        self.assertEqual(status, 302)
        state = parse_qs(urlsplit(headers["Location"]).query)["state"][0]
        params = urlencode({"code": "test-only-code", "state": state})
        with self.assertLogs(server.LOGGER, level="ERROR") as captured:
            status, _, _ = self.request(
                "/oauth/meta/callback?" + params,
                headers={"Host": "example.org", "X-Forwarded-Proto": "https"})
        self.assertEqual(status, 400)
        diagnostic = "\n".join(captured.output)
        self.assertIn("stage=parse_callback", diagnostic)
        self.assertIn("OAuth state cookie missing", diagnostic)
        self.assertIn("redirect_authority_match=True", diagnostic)
        self.assertIn("forwarded_https=True", diagnostic)
        self.assertNotIn("test-only-code", diagnostic)
        self.assertNotIn(state, diagnostic)

    def test_cookie_probe_checks_public_https_transport_without_meta(self):
        self.config.update({
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
            "meta_graph_version": "v27.0",
            "instagram_account_id": "17841454345931235"})
        self.assertEqual(self.request("/oauth/meta/start?probe=1")[0], 401)
        status, headers, _ = self.request(
            "/oauth/meta/start?probe=1", headers=self.admin_header())
        self.assertEqual(status, 302)
        self.assertIn("?probe=", headers["Location"])
        self.assertEqual(urlsplit(headers["Location"]).netloc, "example.org")
        self.assertIn("Path=/oauth/meta/callback", headers["Set-Cookie"])
        probe_query = urlsplit(headers["Location"]).query
        nonce = parse_qs(probe_query)["probe"][0]
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        cookie_name, cookie_value = cookie.split("=", 1)
        self.assertEqual(cookie_name, server.oauth_meta._state_cookie_name(nonce))
        self.assertEqual(cookie_value, nonce)
        public_headers = {"Host": "example.org", "X-Forwarded-Proto": "https",
                          "Cookie": cookie}
        with patch.object(server.oauth_meta, "exchange_code",
                          side_effect=AssertionError("must not call Meta")):
            status, _, body = self.request(
                "/oauth/meta/callback?" + probe_query, headers=public_headers)
        self.assertEqual(status, 200)
        self.assertIn(b"Teste aprovado", body)
        self.assertIn(b"0.1.34", body)
        self.assertNotIn(nonce.encode("ascii"), body)
        # Missing browser cookie fails before any Meta request.
        with self.assertLogs(server.LOGGER, level="ERROR") as captured:
            status, _, body = self.request(
                "/oauth/meta/callback?" + probe_query,
                headers={"Host": "example.org", "X-Forwarded-Proto": "https"})
        self.assertEqual(status, 400)
        self.assertIn("cookie probe missing", "\n".join(captured.output))
        self.assertNotIn(nonce, "\n".join(captured.output))
        # A wrong authority or missing HTTPS at the proxy is also rejected.
        for changes in ({"Host": "wrong.example.org"},
                        {"X-Forwarded-Proto": "http"}):
            with self.assertLogs(server.LOGGER, level="ERROR"):
                status, _, _ = self.request(
                    "/oauth/meta/callback?" + probe_query,
                    headers={**public_headers, **changes})
            self.assertEqual(status, 400)
            self.assertIn(b"0.1.34", body)

    def test_meta_oauth_link_opens_in_new_tab(self):
        cfg = {
            **self.config,
            "meta_oauth_enabled": True,
            "meta_app_id": "178361319962332",
            "meta_login_config_id": "990074610355962",
            "meta_app_secret": "LOCAL_TEST_SECRET_NEVER_REAL",
            "meta_oauth_redirect_uri": "https://romeropi.duckdns.org:8443/oauth/meta/callback",
            "meta_graph_version": "v27.0",
        }
        summary = {
            "oauthReady": True,
            "accountVerified": False,
            "webhookEnabled": True,
            "subscriptionRequested": False,
            "lastMessageReceived": None,
            "messagesStored": 0,
        }
        rendered = server.render_connection_section(cfg, summary)
        self.assertIn('target="_blank"', rendered)
        self.assertIn('rel="noopener noreferrer"', rendered)
        self.assertIn('Conectar Instagram pela Meta', rendered)
        self.assertIn('Testar navegador e proxy (sem Meta)', rendered)
        self.assertIn('/oauth/meta/start?probe=1', rendered)

    def test_meta_status_never_falsely_claims_connected(self):
        cfg = self.config
        cfg["meta_oauth_enabled"] = False
        status, _, body = self.request("/oauth/meta/status", headers=self.admin_header())
        result = json.loads(body)
        self.assertEqual(status, 200)
        self.assertFalse(result["accountVerified"])
        self.assertFalse(result["subscriptionRequested"])
        self.assertFalse(result["sendingEnabled"])

    def test_meta_check_and_subscribe_require_browser_session(self):
        for path in ("/panel/meta/check", "/panel/meta/subscribe"):
            status, _, _ = self.request(path, "POST", b"csrf=bad",
                            {"Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(status, 403)

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

    def test_signed_unified_webhook_is_stored_visible_and_diagnostics_are_redacted(self):
        payload=json.loads(self.event());entry=payload['entry'][0]
        event=entry.pop('messaging')[0]
        event['message']['text']='private synthetic message must not be logged'
        entry['changes']=[{'field':'messages','value':event}]
        raw=json.dumps(payload).encode()
        digest=hmac.new(self.config['meta_app_secret'].encode(),raw,hashlib.sha256).hexdigest()
        with self.assertLogs(server.LOGGER,level='INFO') as logs:
            status,_,body=self.request('/webhook/instagram','POST',raw,
                {'X-Hub-Signature-256':'sha256='+digest,'Content-Type':'application/json'})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body),{'accepted':True,'new_text_messages':1})
        log='\n'.join(logs.output)
        for expected in ('Meta webhook accepted:', 'legacy_events=0', 'unified_events=1',
                         'recipient_match=1', 'matched_text=1', 'stored=1'):
            self.assertIn(expected,log)
        for private in ('business-1','customer-1',event['message']['text'],digest,
                        self.config['meta_app_secret'],self.config['meta_verify_token']):
            self.assertNotIn(private,log)
        self.assertEqual(self.post_event()[0],200)  # same mid through old shape
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)
        login=urlencode({'username':'admin','password':self.config['panel_password']}).encode()
        _,headers,_=self.request('/auth/login','POST',login,
            {'Content-Type':'application/x-www-form-urlencoded'})
        cookie=headers['Set-Cookie'].split(';',1)[0]
        _,_,page=self.request('/panel',headers={'Cookie':cookie})
        self.assertIn(event['message']['text'].encode(),page)
        self.assertIn(b'Mensagens armazenadas: 1',page)

    def test_unified_webhook_invalid_signature_is_not_parsed_or_stored(self):
        payload=json.loads(self.event());entry=payload['entry'][0]
        entry['changes']=[{'field':'messages','value':entry.pop('messaging')[0]}]
        with self.assertLogs(server.LOGGER,level='INFO') as logs:
            status,_,_=self.request('/webhook/instagram','POST',json.dumps(payload).encode(),
                {'X-Hub-Signature-256':'sha256='+'0'*64})
        self.assertEqual(status,403)
        self.assertIn('reason=invalid_signature','\n'.join(logs.output))
        self.assertNotIn('unified_events','\n'.join(logs.output))
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],0)

    def test_unified_unknown_recipient_is_acknowledged_without_primary_fallback(self):
        payload=json.loads(self.event());entry=payload['entry'][0]
        event=entry.pop('messaging')[0];event['recipient']['id']='other-business'
        entry['changes']=[{'field':'messages','value':event}]
        raw=json.dumps(payload).encode()
        sig='sha256='+hmac.new(self.config['meta_app_secret'].encode(),raw,hashlib.sha256).hexdigest()
        with self.assertLogs(server.LOGGER,level='INFO') as logs:
            status,_,body=self.request('/webhook/instagram','POST',raw,{'X-Hub-Signature-256':sig})
        self.assertEqual(status,200)
        self.assertEqual(json.loads(body)['new_text_messages'],0)
        log='\n'.join(logs.output)
        self.assertIn('unified_events=1 recipient_match=0 matched_text=0 stored=0',log)
        self.assertNotIn('other-business',log)
        self.assertEqual(server.list_pending(account_id='business-1'),[])

    def test_signed_message_updates_visible_panel_and_status(self):
        self.assertEqual(self.post_event()[0], 200)
        login = urlencode({"username": "admin", "password": self.config["panel_password"]}).encode()
        code, headers, _ = self.request("/auth/login", "POST", login,
            {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(code, 303)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, _, html = self.request("/panel", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn(b"Mensagens armazenadas: 1", html)
        self.assertIn(b"customer-1", html)
        status, _, body = self.request("/oauth/meta/status", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        result = json.loads(body)
        self.assertEqual(result["messagesStored"], 1)
        self.assertFalse(result["sendingEnabled"])

    def test_disabled_meta_webhook(self):
        self.config["ingress_enabled"] = False
        self.assertEqual(self.post_event()[0], 503)

    def test_panel_requires_login_and_escapes(self):
        self.assertEqual(self.post_event()[0], 200)
        status, headers, body = self.request("/panel")
        self.assertEqual(status, 200)
        self.assertIn(b'autocomplete="username"', body)
        self.assertIn(b'autocomplete="current-password"', body)
        self.assertNotIn("WWW-Authenticate", headers)
        self.assertIn("Content-Security-Policy", headers)
        login = urlencode({"username": "admin", "password": self.config["panel_password"]}).encode()
        status, headers, body = self.request("/auth/login", "POST", login,
                 {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "../panel")
        self.assertIn("HttpOnly; SameSite=Strict", headers["Set-Cookie"])
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        status, _, body = self.request("/panel", headers={"Cookie": cookie})
        self.assertEqual(status, 200)
        self.assertIn(b"Assumir", body)
        # Same approved visual language as Editorial; H07 login/logout contract unchanged.
        self.assertIn(b'class="topbar ui-app-header"', body)
        self.assertIn(b'class="sidebar ui-sidebar"', body)
        self.assertIn('aria-label="Editorial"'.encode("utf-8"), body)
        self.assertIn(b'--bg:#0c1520', body)
        self.assertIn(b'action="/auth/logout"', body)
        self.assertEqual(body.count(b'>Sair</button>'), 1)
        self.assertIn(b'action="panel/handoff"', body)
        self.assertNotIn(self.config["panel_password"].encode(), body)
        status, logout_headers, _ = self.request("/auth/logout", "POST",
                                               headers={"Cookie": cookie})
        self.assertEqual(status, 303)
        self.assertIn("Max-Age=0", logout_headers["Set-Cookie"])
        status, _, body = self.request("/panel", headers={"Cookie": cookie})
        self.assertIn(b'autocomplete="current-password"', body)

    def test_browser_session_cookie_secure_on_https_origin(self):
        body = urlencode({"username": "admin", "password": self.config["panel_password"]}).encode()
        status, headers, _ = self.request("/auth/login", "POST", body,
             {"Content-Type": "application/x-www-form-urlencoded",
              "Origin": "https://romeropi.duckdns.org:8443"})
        self.assertEqual(status, 303)
        self.assertIn("; Secure", headers["Set-Cookie"])
        self.assertIn("HttpOnly; SameSite=Strict", headers["Set-Cookie"])

    def test_browser_login_rejects_invalid_and_revokes_after_password_change(self):
        body = urlencode({"username": "admin", "password": "wrong"}).encode()
        status, headers, data = self.request("/auth/login", "POST", body,
                  {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 401)
        self.assertNotIn("WWW-Authenticate", headers)
        self.assertIn(b"incorretos", data)
        body = urlencode({"username": "admin", "password": self.config["panel_password"]}).encode()
        status, headers, _ = self.request("/auth/login", "POST", body,
                 {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        self.assertIn(b"Central Instagram", self.request("/panel", headers={"Cookie": cookie})[2])
        self.config["panel_password"] = "this-is-a-different-long-password"
        result = self.request("/panel", headers={"Cookie": cookie})
        self.assertIn(b'autocomplete="current-password"', result[2])
        self.assertNotIn("WWW-Authenticate", result[1])

    def test_browser_login_rejects_malformed_body(self):
        bad = b"username=admin&password=wrong&password=twice"
        status, _, _ = self.request("/auth/login", "POST", bad,
               {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 401)
        status, _, _ = self.request("/auth/login", "POST", bad,
               {"Content-Type": "application/json"})
        self.assertEqual(status, 415)

    def test_browser_session_allows_csrf_protected_handoff(self):
        self.assertEqual(self.post_event()[0], 200)
        form = urlencode({"username": "admin", "password": self.config["panel_password"]}).encode()
        status, headers, _ = self.request("/auth/login", "POST", form,
                        {"Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        cookie = headers["Set-Cookie"].split(";", 1)[0]
        csrf = token_for("business-1", "customer-1", "human", self.config["panel_password"])
        data = urlencode({"accountId": "business-1", "senderId": "customer-1",
                          "state": "human", "csrf": csrf}).encode()
        status, headers, _ = self.request("/panel/handoff", "POST", data,
                     {"Cookie": cookie, "Content-Type": "application/x-www-form-urlencoded"})
        self.assertEqual(status, 303)
        self.assertEqual(headers.get("Location"), "../panel")
        with server.database() as conn:
            self.assertEqual(conn.execute(
                "SELECT state FROM handoff WHERE sender_id='customer-1'"
            ).fetchone(), ("human",))

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

    def configure_oauth(self):
        self.config.update(meta_oauth_enabled=True, meta_app_id='12345678', meta_login_config_id='87654321',
                           meta_app_secret='SYNTHETIC_UNUSED_APP_SECRET', meta_graph_version='v27.0',
                           meta_oauth_redirect_uri='https://example.org/oauth/meta/callback')

    def test_old_ha_origin_cannot_start_or_consume_standalone_oauth(self):
        self.configure_oauth()
        self.config.update(public_base_url='https://example.org:9443',
                           meta_oauth_redirect_uri='https://example.org:9443/oauth/meta/callback')
        headers = {**self.admin_header(), 'Host': 'example.org:8443', 'X-Forwarded-Proto': 'https'}
        with patch.object(server.oauth_meta, 'start') as start, \
             patch.object(server.oauth_meta, 'consume_state') as consume:
            for route in ('/oauth/meta/start', '/oauth/meta/start?probe=1', '/oauth/meta/callback?state=old&code=old'):
                status, response_headers, _ = self.request(route, headers=headers)
                self.assertEqual(status, 421)
                self.assertNotIn('Location', response_headers)
                self.assertNotIn('Set-Cookie', response_headers)
            start.assert_not_called(); consume.assert_not_called()

    def test_dedicated_proxy_probe_uses_same_external_port_and_new_host(self):
        self.configure_oauth()
        self.config.update(public_base_url='https://central.test:8443',
                           meta_oauth_redirect_uri='https://central.test:8443/oauth/meta/callback')
        request_headers={**self.admin_header(),'Host':'central.test:8443','X-Forwarded-Proto':'https'}
        status, headers, _=self.request('/oauth/meta/start?probe=1',headers=request_headers)
        self.assertEqual(status,302)
        self.assertTrue(headers['Location'].startswith(self.config['public_base_url']+'/oauth/meta/callback?'))
        callback='/oauth/meta/callback?'+urlsplit(headers['Location']).query
        status, _, body=self.request(callback,headers={**request_headers,'Cookie':headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(status,200)
        self.assertIn(b'Teste aprovado',body)

    def test_proxy_origin_requires_forwarded_https(self):
        self.configure_oauth()
        self.config.update(public_base_url='https://central.test:8443',
                           meta_oauth_redirect_uri='https://central.test:8443/oauth/meta/callback')
        for proto in ('','http'):
            status, headers, _=self.request('/oauth/meta/start?probe=1',headers={
                **self.admin_header(),'Host':'central.test:8443','X-Forwarded-Proto':proto})
            self.assertEqual(status,421)
            self.assertNotIn('Set-Cookie',headers)

    def test_proxy_old_config_refused_before_state_or_exchange(self):
        self.configure_oauth()
        self.config['public_base_url']='https://central.test:8443'
        with patch.object(server.oauth_meta,'start') as start, patch.object(server.oauth_meta,'consume_state') as consume:
            for route in ('/oauth/meta/start','/oauth/meta/callback?state=old&code=old'):
                self.assertEqual(self.request(route,headers=self.admin_header())[0],503)
            start.assert_not_called(); consume.assert_not_called()

    def test_probe_screen_distinguishes_no_header_from_unrelated_cookie_safely(self):
        self.configure_oauth()
        with self.assertLogs(server.LOGGER, level='INFO') as emitted:
            _, headers, _ = self.request('/oauth/meta/start?probe=1', headers=self.admin_header())
        self.assertIn('OAuth cookie emitted:', '\n'.join(emitted.output))
        query = urlsplit(headers['Location']).query
        nonce = parse_qs(query)['probe'][0]
        for cookie, expected in (('', 'Nenhum cabeçalho Cookie'), ('unrelated=SYNTHETIC_PRIVATE_VALUE', 'Cookies chegaram')):
            with self.assertLogs(server.LOGGER, level='ERROR') as captured:
                status, _, body = self.request('/oauth/meta/callback?' + query,
                    headers={'Host': 'example.org', 'X-Forwarded-Proto': 'https', 'Cookie': cookie})
            self.assertEqual(status, 400)
            self.assertIn(expected.encode(), body)
            combined = '\n'.join(captured.output + emitted.output) + body.decode()
            for forbidden in (nonce, 'SYNTHETIC_PRIVATE_VALUE', self.config['meta_app_secret']):
                self.assertNotIn(forbidden, combined)
            self.assertIn('expected_cookie_present', combined)

    def test_exchange_http_details_only_in_logs_not_public_response(self):
        from urllib.error import HTTPError
        import io
        self.configure_oauth()
        _, headers, _ = self.request('/oauth/meta/start', headers=self.admin_header())
        state = parse_qs(urlsplit(headers['Location']).query)['state'][0]
        cookie = headers['Set-Cookie'].split(';', 1)[0]
        def fake(*_a, **_k):
            raise HTTPError('https://example.invalid/?code=PRIVATE_ERROR_BODY', 400, 'PRIVATE_ERROR_BODY', {},
                io.BytesIO(b'{"error":{"message":"PRIVATE_ERROR_BODY","code":100,"error_subcode":36008}}'))
        with patch.object(server.oauth_meta, 'urlopen', fake), self.assertLogs(server.LOGGER, level='ERROR') as captured:
            status, _, body = self.request('/oauth/meta/callback?'+urlencode({'state':state,'code':'PRIVATE_AUTH_CODE'}), headers={'Cookie':cookie})
        self.assertEqual(status, 400)
        log = '\n'.join(captured.output)
        self.assertIn('kind=http http_status=400 provider_code=100 provider_subcode=36008', log)
        self.assertNotIn('provider_code', body.decode())
        for forbidden in ('PRIVATE_ERROR_BODY', 'PRIVATE_AUTH_CODE', state, self.config['meta_app_secret']):
            self.assertNotIn(forbidden, log + body.decode())

    def split_cookie_request(self, path, fields):
        client = HTTPConnection("127.0.0.1", self.http.server_address[1], timeout=3)
        try:
            client.putrequest("GET", path, skip_host=True)
            client.putheader("Host", "example.org")
            client.putheader("X-Forwarded-Proto", "https")
            for value in fields: client.putheader("Cookie", value)
            client.endheaders()
            response = client.getresponse()
            return response.status, response.read()
        finally: client.close()

    def test_probe_expected_cookie_in_second_field_is_not_lost(self):
        self.configure_oauth()
        _, headers, _ = self.request('/oauth/meta/start?probe=1', headers=self.admin_header())
        query = urlsplit(headers['Location']).query
        pair = headers['Set-Cookie'].split(';', 1)[0]
        status, body = self.split_cookie_request('/oauth/meta/callback?' + query, ['unrelated=synthetic', pair])
        self.assertEqual(status, 200)
        self.assertIn(b'Teste aprovado', body)

    def test_split_duplicate_expected_cookie_still_fails_closed(self):
        self.configure_oauth()
        _, headers, _ = self.request('/oauth/meta/start?probe=1', headers=self.admin_header())
        query = urlsplit(headers['Location']).query
        pair = headers['Set-Cookie'].split(';', 1)[0]
        with self.assertLogs(server.LOGGER, level='ERROR') as captured:
            status, body = self.split_cookie_request('/oauth/meta/callback?' + query, [pair, pair])
        self.assertEqual(status, 400)
        self.assertIn('duplicated', '\n'.join(captured.output))
        self.assertIn("'cookie_header_fields': 2", '\n'.join(captured.output))
        self.assertNotIn(parse_qs(query)['probe'][0], body.decode() + '\n'.join(captured.output))

    def test_real_callback_accepts_expected_cookie_in_second_field_with_mock_provider(self):
        self.configure_oauth()
        _, headers, _ = self.request('/oauth/meta/start', headers=self.admin_header())
        state = parse_qs(urlsplit(headers['Location']).query)['state'][0]
        pair = headers['Set-Cookie'].split(';', 1)[0]
        credential = {'access_token': 'SYNTHETIC_TOKEN_' * 3, 'expires_in': 0}
        identity = {'account_id': self.config['instagram_account_id'], 'username': 'umdoislab', 'verified_at': 1}
        with patch.object(server.oauth_meta, 'exchange_code', return_value=credential) as exchange, \
             patch.object(server.instagram_connection, 'verify_access', return_value=identity):
            status, _ = self.split_cookie_request('/oauth/meta/callback?' + urlencode({'state':state,'code':'synthetic'}), ['unrelated=synthetic', pair])
        self.assertEqual(status, 200)
        self.assertEqual(exchange.call_count, 1)

    def test_admin_session_in_second_cookie_field_remains_authorized(self):
        with server.database() as db:
            token = server.panel_login.create_session(db, self.config['panel_password'])
        status, _ = self.split_cookie_request('/panel/account-context', ['unrelated=synthetic', 'ig_panel_session='+token])
        self.assertEqual(status, 200)


if __name__ == "__main__":
    unittest.main()
