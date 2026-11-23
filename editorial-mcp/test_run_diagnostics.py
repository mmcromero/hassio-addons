import contextlib
import io
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

import run


class DiagnosticOutput(unittest.TestCase):
    def capture(self, label, stdout, *args, stderr='', returncode=0):
        output = io.StringIO()
        result = SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)
        with patch('run.cli', return_value=result) as mocked, contextlib.redirect_stdout(output):
            run.diagnostic(label, *args)
        self.assertIs(mocked.call_args.kwargs.get('text'), True)
        return output.getvalue()

    def test_version_parses_text(self):
        self.assertIn('DIAG version=1.104.7 rc=0',
                      self.capture('version', 'tailscale v1.104.7\n', 'version'))

    def test_status_emits_only_allowlisted_counts(self):
        payload = {
            'BackendState': 'Running',
            'Self': {'Online': True, 'HostName': 'central-editorial-mcp',
                     'CapMap': {'funnel': {}}},
            'Peer': {
                'private-peer-id': {'Tags': ['tag:ingress'], 'Online': True,
                                    'DNSName': 'private-peer.example.ts.net'},
                'other-peer': {'Tags': ['tag:other'], 'Online': False}
            }
        }
        output = self.capture('status', json.dumps(payload), 'status', '--json')
        self.assertIn('backend=Running', output)
        self.assertIn('self_name_ok=True', output)
        self.assertIn('funnel_cap=True', output)
        self.assertIn('ingress_peers=1 ingress_online=1', output)
        self.assertNotIn('private-peer-id', output)
        self.assertNotIn('private-peer.example.ts.net', output)

    def test_funnel_and_serve_parse_text(self):
        output = self.capture('funnel', 'Funnel on: HTTPS:443 proxy\n',
                              'funnel', 'status', '--json')
        self.assertIn('says_funnel_on=True', output)
        self.assertIn('mentions_443=True', output)
        output = self.capture('serve', 'HTTPS:443 proxy\n', 'serve', 'status', '--json')
        self.assertIn('output_present=True', output)

    def test_netcheck_parses_text_without_ip(self):
        output = self.capture('netcheck',
            'UDP: true\nIPv4: yes, 203.0.113.9:41641\nIPv6: no\n'
            'Nearest DERP: Sao Paulo\nPortMapping: UPnP\n', 'netcheck')
        self.assertIn('UDP=true', output)
        self.assertIn('IPv4=yes', output)
        self.assertIn('Nearest DERP=Sao Paulo', output)
        self.assertNotIn('203.0.113.9', output)

    def test_cli_failure_is_sanitized(self):
        output = self.capture('version', '', 'version', stderr='private detail', returncode=1)
        self.assertIn('DIAG version=unparsed rc=1', output)
        self.assertNotIn('private detail', output)


if __name__ == '__main__':
    unittest.main()
