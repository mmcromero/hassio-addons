import io
import json
import socket
import ssl
import subprocess
import unittest
from unittest.mock import patch, Mock
from contextlib import redirect_stdout
from funnel_probe import classify, drain_daemon, serve_facts, probe_http, probe_tls, probe_cert, collect_probes

HOST = 'central-editorial-mcp.example.ts.net'


class FunnelProbeTests(unittest.TestCase):
    def test_daemon_never_emits_raw_secrets(self):
        raw = 'ACME certificate failed token secret123\nSetDNS failed https://example.com/private?sig=secret\ncertificate failed anothersecret\nTLS handshake error 10.0.0.2\nrandom secret\n'
        with redirect_stdout(io.StringIO()) as output:
            drain_daemon(io.StringIO(raw))
        self.assertEqual(output.getvalue().splitlines(), [
            'DIAG daemon_event=certificate_error', 'DIAG daemon_event=dns_challenge', 'DIAG daemon_event=tls_error'])

    def test_classify_known_errors(self):
        self.assertEqual(classify('ACME 429 rate limit'), 'rate_limit')
        self.assertEqual(classify('getCertPEM: no TailscaleVarRoot'), 'certificate_storage_missing')
        self.assertEqual(classify('certificate not allowed'), 'certificate_policy')
        self.assertEqual(classify('secret'), 'unclassified')

    def test_structured_funnel(self):
        endpoint = HOST + ':443'
        data = {'TCP': {'443': {'HTTPS': True}}, 'Web': {endpoint: {'Handlers': {'/': {'Proxy': 'http://127.0.0.1:8765'}}}}, 'AllowFunnel': {endpoint: True}}
        self.assertEqual(serve_facts(json.dumps(data), HOST, 8765), (True, True, True))
        data['AllowFunnel'][endpoint] = False
        self.assertEqual(serve_facts(json.dumps(data), HOST, 8765), (True, False, True))
        self.assertIsNone(serve_facts('bad', HOST, 8765))
        self.assertIsNone(serve_facts('[]', HOST, 8765))

    @patch('funnel_probe.http.client.HTTPConnection')
    def test_loopback_probe(self, connection):
        connection.return_value.getresponse.return_value.status = 405
        self.assertEqual(probe_http(HOST, 8765), 405)
        connection.return_value.request.assert_called_once_with('GET', '/mcp', headers={'Host': HOST})
        connection.return_value.close.assert_called_once()

    @patch('funnel_probe.socket.create_connection', side_effect=socket.gaierror())
    def test_dns_failure(self, connect):
        self.assertEqual(probe_tls(HOST), 'dns_error')

    @patch('funnel_probe.socket.create_connection')
    @patch('funnel_probe.ssl.create_default_context')
    def test_tls_failure(self, context, connect):
        context.return_value.wrap_socket.side_effect = ssl.SSLError('secret')
        self.assertEqual(probe_tls(HOST), 'tls_handshake_error')
        self.assertEqual(context.return_value.wrap_socket.call_args.kwargs['server_hostname'], HOST)
        connect.return_value.__enter__.return_value.settimeout.assert_called_once_with(75)

    def test_certificate_error_safe_and_files_removed(self):
        paths = []
        def cli(*args, **kwargs):
            from pathlib import Path
            paths.extend(Path(value.split('=', 1)[1]) for value in args[1:3])
            for path in paths:
                path.write_text('secret')
            return subprocess.CompletedProcess(args, 1, '', 'SetDNS failed secret')
        self.assertEqual(probe_cert(cli, HOST), 'failed_dns_challenge')
        self.assertTrue(all(not p.exists() for p in paths))

    @patch('funnel_probe.probe_cert')
    @patch('funnel_probe.probe_tls', return_value='verified')
    @patch('funnel_probe.socket.getaddrinfo', return_value=[])
    @patch('funnel_probe.probe_http', return_value=405)
    def test_no_certificate_request_when_tls_ok(self, http, dns, tls, cert):
        cli = Mock(return_value=subprocess.CompletedProcess([], 0, '{}', ''))
        with redirect_stdout(io.StringIO()):
            collect_probes(cli, HOST, 8765)
        cert.assert_not_called()


if __name__ == '__main__':
    unittest.main()
