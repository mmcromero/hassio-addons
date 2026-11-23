import unittest
import run
from run import sanitize_netcheck


class NetcheckSanitization(unittest.TestCase):
    def test_only_coarse_states_are_emitted(self):
        output = """UDP: true
IPv4: yes (203.0.113.42:41641)
IPv6: no
MappingVariesByDestIP: false
PortMapping: UPnP
Nearest DERP: Sao Paulo
"""
        facts = sanitize_netcheck(output)
        self.assertEqual(facts, [
            'UDP=yes', 'IPv4=yes', 'IPv6=no',
            'MappingVariesByDestIP=no', 'PortMapping=yes'
        ])
        rendered = ' '.join(facts)
        self.assertNotIn('203.0.113.42', rendered)
        self.assertNotIn('41641', rendered)
        self.assertNotIn('Sao Paulo', rendered)

    def test_unknown_and_empty(self):
        self.assertEqual(sanitize_netcheck('UDP: pending\n'), ['UDP=unknown'])
        self.assertEqual(sanitize_netcheck('Nearest DERP: Frankfurt\n'), [])


class DiagnosticsOptionCompatibility(unittest.TestCase):
    def test_missing_option_is_disabled_for_existing_installations(self):
        self.assertFalse(run.diagnostics_enabled({'central_url': 'https://central.example', 'funnel_enabled': True}))
        self.assertFalse(run.diagnostics_enabled({'diagnostics_enabled': False}))
        self.assertTrue(run.diagnostics_enabled({'diagnostics_enabled': True}))


class DedicatedDaemonConfiguration(unittest.TestCase):
    def test_explicit_var_root_preserves_existing_node(self):
        self.assertEqual(run.daemon_command(), [
            'tailscaled', '--tun=userspace-networking',
            '--socket=/run/editorial-mcp/tailscaled.sock',
            '--state=/data/editorial-mcp-tailnet/tailscaled.state',
            '--statedir=/data/editorial-mcp-tailnet',
        ])


if __name__ == '__main__':
    unittest.main()
