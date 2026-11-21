"""Real local TLS, existing login/data and fail-closed public-origin gates."""
from datetime import datetime, timedelta, timezone
from http.client import HTTPSConnection, HTTPConnection
from pathlib import Path
import ssl
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import urlencode

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
import server
import standalone_https


class StandaloneHTTPS(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ssl_dir = tempfile.TemporaryDirectory()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'central-review.test')])
        cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject)
                .public_key(key.public_key()).serial_number(x509.random_serial_number())
                .not_valid_before(datetime.now(timezone.utc) - timedelta(days=1))
                .not_valid_after(datetime.now(timezone.utc) + timedelta(days=1))
                .sign(key, hashes.SHA256()))
        (Path(cls.ssl_dir.name) / 'fullchain.pem').write_bytes(cert.public_bytes(serialization.Encoding.PEM))
        keyfile = Path(cls.ssl_dir.name) / 'privkey.pem'
        keyfile.write_bytes(key.private_bytes(serialization.Encoding.PEM,
                            serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        keyfile.chmod(0o600)

    @classmethod
    def tearDownClass(cls):
        cls.ssl_dir.cleanup()

    def setUp(self):
        self.data = tempfile.TemporaryDirectory()
        self.cfg = {'public_base_url': 'https://central-review.test:9443',
                    'panel_password': 'SYNTHETIC_PANEL_PASSWORD_123',
                    'instagram_account_id': '11111111', 'meta_app_id': '12345678',
                    'meta_login_config_id': '87654321', 'meta_app_secret': 'SYNTHETIC_META_SECRET',
                    'meta_graph_version': 'v27.0', 'meta_oauth_enabled': True}
        self.patches = [patch.object(server, 'settings', lambda: self.cfg),
                        patch.object(server, 'DATA_DIR', Path(self.data.name)),
                        patch.object(server, 'DB_PATH', Path(self.data.name) / 'instagram.sqlite3')]
        for p in self.patches: p.start()
        self.http = standalone_https.create_server(self.cfg, server.Handler,
                address=('127.0.0.1', 0), ssl_root=self.ssl_dir.name)
        self.cfg['public_base_url'] = 'https://central-review.test:' + str(self.http.server_port)
        self.cfg['meta_oauth_redirect_uri'] = self.cfg['public_base_url'] + '/oauth/meta/callback'
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(3)
        for p in reversed(self.patches): p.stop()
        self.data.cleanup()

    def request(self, path, method='GET', body=None, headers=None):
        context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        context.check_hostname = False; context.verify_mode = ssl.CERT_NONE
        connection = HTTPSConnection('127.0.0.1', self.http.server_port, context=context, timeout=3)
        try:
            connection.request(method, path, body, {'Host': self.cfg['public_base_url'][8:], **(headers or {})})
            response = connection.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            connection.close()

    def login(self):
        status, headers, _ = self.request('/auth/login', 'POST',
                urlencode({'username': 'admin', 'password': self.cfg['panel_password']}),
                {'Content-Type': 'application/x-www-form-urlencoded'})
        self.assertEqual(status, 303)
        for attribute in ('Secure', 'HttpOnly', 'SameSite=Strict'):
            self.assertIn(attribute, headers['Set-Cookie'])
        return headers['Set-Cookie'].split(';')[0]

    def test_native_tls_login_panel_editorial_and_probe_share_session(self):
        self.assertEqual(self.request('/health')[0], 200)
        self.assertIn(b'Entrar', self.request('/panel')[2])
        self.assertEqual(self.request('/oauth/meta/start?probe=1')[0], 401)
        session = self.login()
        self.assertIn(b'Conex', self.request('/panel', headers={'Cookie': session})[2])
        self.assertEqual(self.request('/editorial/', headers={'Cookie': session})[0], 200)
        status, headers, _ = self.request('/oauth/meta/start?probe=1', headers={'Cookie': session})
        self.assertEqual(status, 302)
        callback = headers['Location'].split(self.cfg['public_base_url'])[1]
        status, _, body = self.request(callback, headers={'Cookie': headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(status, 200)
        self.assertIn(b'Teste aprovado', body)
        with server.database() as conn:
            self.assertTrue(server.panel_login.valid_session(conn, session, self.cfg['panel_password']))

    def test_wrong_host_rejected_even_with_forwarded_headers(self):
        status, headers, _ = self.request('/panel', headers={'Host': 'old-ha.test:8443',
                                                            'X-Forwarded-Host': self.cfg['public_base_url'][8:]})
        self.assertEqual(status, 421)
        self.assertNotIn('Set-Cookie', headers)

    def test_old_callback_blocks_start_and_exchange(self):
        self.cfg['meta_oauth_redirect_uri'] = 'https://central-review.test:8443/oauth/meta/callback'
        with patch.object(server.oauth_meta, 'start_cookie_probe') as probe, \
             patch.object(server.oauth_meta, 'exchange_code') as exchange:
            for path in ('/oauth/meta/start?probe=1', '/oauth/meta/start', '/oauth/meta/callback?state=old&code=old'):
                status, headers, _ = self.request(path)
                self.assertEqual(status, 503)
                self.assertNotIn('Set-Cookie', headers)
                self.assertNotIn('Location', headers)
            probe.assert_not_called(); exchange.assert_not_called()

    def test_public_port_never_speaks_plain_http(self):
        connection = HTTPConnection('127.0.0.1', self.http.server_port, timeout=3)
        try:
            with self.assertRaises((OSError, ConnectionError)):
                connection.request('GET', '/health'); connection.getresponse()
        finally:
            connection.close()

    def test_certificate_is_reloaded_without_plaintext_fallback(self):
        self.http.certfile = Path(self.ssl_dir.name) / 'missing.pem'
        with self.assertRaises(OSError): self.request('/health')
        self.http.certfile = Path(self.ssl_dir.name) / 'fullchain.pem'
        self.assertEqual(self.request('/health')[0], 200)


class HTTPSConfiguration(unittest.TestCase):
    def test_empty_origin_does_not_bind_or_load_certificates(self):
        self.assertIsNone(standalone_https.create_server({}, server.Handler))

    def test_invalid_origins_and_certificate_paths(self):
        for origin in ('http://central.test:9443', 'https://user:pass@central.test',
                       'https://central.test/path', 'https://central.test?state=x',
                       'https://central.test#fragment', 'https://localhost', 'https://central.test:0',
                       'https://central.test:invalid', 'https://central.test\n', None):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                standalone_https.public_origin({'public_base_url': origin})
        for filename in ('../privkey.pem', '/ssl/privkey.pem', '..', '', None):
            with self.subTest(filename=filename), self.assertRaises(ValueError):
                standalone_https.certificate_path('/ssl', filename)

    def test_password_and_certificates_required_before_binding(self):
        with self.assertRaises(ValueError):
            standalone_https.create_server({'public_base_url': 'https://central.test:9443'}, server.Handler)
        with self.assertRaises(OSError):
            standalone_https.create_server({'public_base_url': 'https://central.test:9443',
                'panel_password': 'SYNTHETIC_PANEL_PASSWORD'}, server.Handler, ssl_root='/nonexistent')

    def test_old_origin_does_not_render_oauth_links(self):
        cfg = {'public_base_url': 'https://central.test:9443',
               'meta_oauth_redirect_uri': 'https://central.test:8443/oauth/meta/callback'}
        summary = dict(oauthReady=True, accountVerified=False, webhookEnabled=False,
                       subscriptionRequested=False, messagesStored=0, lastMessageReceived=None)
        page = server.render_connection_section(cfg, summary)
        self.assertIn('https://central.test:9443/panel', page)
        self.assertNotIn('/oauth/meta/start', page)
