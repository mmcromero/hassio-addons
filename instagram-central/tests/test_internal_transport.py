"""Exercise the actual listener factory without Meta or Home Assistant."""
import hashlib
import hmac
from http.client import HTTPConnection
import json
from pathlib import Path
import socket
import tempfile
import threading
import unittest
from unittest.mock import patch

import server


class InternalTransportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.cfg = {
            'instagram_account_id': 'business-1',
            'meta_app_secret': 'synthetic-listener-secret',
            'ingress_enabled': True,
        }
        for name, value in (('DATA_DIR', Path(self.tmp.name)),
                            ('DB_PATH', Path(self.tmp.name) / 'instagram.sqlite3'),
                            ('settings', lambda: self.cfg)):
            patcher = patch.object(server, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def start(self, http):
        thread = threading.Thread(target=http.serve_forever, daemon=True)
        thread.start()
        def stop():
            http.shutdown()
            http.server_close()
            thread.join(timeout=3)
        self.addCleanup(stop)
        return http.server_address[1]

    def request(self, host, port, path='/health', body=None, headers=None):
        conn = HTTPConnection(host, port, timeout=3)
        try:
            conn.request('POST' if body is not None else 'GET', path, body, headers or {})
            response = conn.getresponse()
            return response.status, json.loads(response.read())
        finally:
            conn.close()

    @unittest.skipUnless(socket.has_dualstack_ipv6(), 'dual-stack unavailable on test host')
    def test_both_families_share_handler_validation_and_database(self):
        http = server.create_internal_http_server(0)
        port = self.start(http)
        self.assertEqual(http.address_family, socket.AF_INET6)
        self.assertEqual(http.socket.getsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY), 0)
        raw = json.dumps({'object': 'instagram', 'entry': [{'changes': [{
            'field': 'messages', 'value': {'sender': {'id': 'customer-1'},
                'recipient': {'id': 'business-1'},
                'message': {'mid': 'transport-1', 'text': 'synthetic transport message'}}}]}]}).encode()
        signature = 'sha256=' + hmac.new(self.cfg['meta_app_secret'].encode(), raw, hashlib.sha256).hexdigest()
        for index, host in enumerate(('127.0.0.1', '::1')):
            with self.subTest(host=host):
                self.assertEqual(self.request(host, port)[1]['version'], server.APP_VERSION)
                with self.assertLogs(server.LOGGER, level='INFO') as refused:
                    self.assertEqual(self.request(host, port, '/webhook/instagram', b'{}')[0], 403)
                self.assertIn('Meta webhook request:', refused.output[0])
                self.assertIn('reason=invalid_signature', refused.output[1])
                with self.assertLogs(server.LOGGER, level='INFO'):
                    status, result = self.request(host, port, '/webhook/instagram', raw,
                        {'X-Hub-Signature-256': signature})
                self.assertEqual(status, 200)
                self.assertEqual(result['new_text_messages'], 1 if index == 0 else 0)
        with server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound').fetchone()[0], 1)

    def test_ipv4_remains_available_without_dual_stack(self):
        with patch.object(server.socket, 'has_dualstack_ipv6', return_value=False), \
                patch.object(server, '_DualStackHTTPServer') as dual:
            http = server.create_internal_http_server(0)
            dual.assert_not_called()
        port = self.start(http)
        self.assertEqual(http.address_family, socket.AF_INET)
        self.assertEqual(self.request('127.0.0.1', port)[0], 200)
