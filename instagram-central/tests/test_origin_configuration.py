"""Configuration for a dedicated hostname behind the existing HTTPS proxy."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
import origin_configuration
import server

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('dedicated_proxy_generator', ROOT / 'tools/generate_proxy.py')
generator = importlib.util.module_from_spec(spec); spec.loader.exec_module(generator)


class OriginConfiguration(unittest.TestCase):
    def test_legacy_empty_origin_and_normalization(self):
        self.assertEqual(origin_configuration.public_origin({}), '')
        self.assertEqual(origin_configuration.public_origin({'public_base_url':'https://CENTRAL.test:8443/'}), 'https://central.test:8443')

    def test_invalid_origins_fail_closed(self):
        for value in ('http://central.test', 'https://u:p@central.test', 'https://central.test/panel',
                      'https://central.test?state=x', 'https://central.test#x', 'https://localhost',
                      'https://central.test:0', 'https://central.test:bad', 'https://central.test\n', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                origin_configuration.public_origin({'public_base_url': value})

    def test_old_origin_hides_oauth_links(self):
        cfg={'public_base_url':'https://central.test:8443','meta_oauth_redirect_uri':'https://ha.test:8443/oauth/meta/callback'}
        summary=dict(oauthReady=True,accountVerified=False,webhookEnabled=False,
                     subscriptionRequested=False,messagesStored=0,lastMessageReceived=None)
        page=server.render_connection_section(cfg,summary)
        self.assertIn('https://central.test:8443/panel',page)
        self.assertNotIn('/oauth/meta/start',page)

    def test_proxy_has_explicit_routes_and_no_other_service(self):
        text=generator.generate('https://central.test:8443','ha.test','actual-instagram')
        self.assertIn('server_name central.test;',text)
        self.assertIn('listen 443 ssl;',text)
        self.assertNotIn('listen 8443',text)
        self.assertNotIn('9443',text)
        self.assertIn('location / { return 404; }',text)
        self.assertIn('location = /auth/login',text)
        self.assertIn('limit_req_status 429;',text)
        self.assertIn('client_max_body_size 25m;',text)
        self.assertIn('X-Forwarded-Proto https;',text)
        self.assertIn('access_log off;',text)
        self.assertIn('error_log /dev/null;',text)
        for forbidden in ('/bridge','/health','/api/hassio','/webhook/instagram','homeassistant.local','sw-modern.js'):
            self.assertNotIn(forbidden,text)

    def test_generator_rejects_same_host_and_injection(self):
        for public,ha,upstream,cert in (
                ('https://ha.test:8443','ha.test','backend','fullchain.pem'),
                ('https://central.test:8443','ha.test','backend; evil','fullchain.pem'),
                ('https://central.test:8443','ha.test','backend','../privkey.pem'),
                ('https://central.test:8443','ha.test;','backend','fullchain.pem'),
                ('https://bad.test;:8443','ha.test','backend','fullchain.pem')):
            with self.subTest(public=public,ha=ha,upstream=upstream,cert=cert), self.assertRaises(ValueError):
                generator.generate(public,ha,upstream,cert)

    def test_candidate_matches_generator(self):
        self.assertEqual((ROOT/'proxy/instagram.conf').read_text(),generator.generate(
            'https://instagram.romeropi.duckdns.org:8443','romeropi.duckdns.org','45c28620-umdoislab-instagram'))

    def test_no_listener_key_mount_or_host_port_in_distribution(self):
        cfg=(ROOT/'config.yaml').read_text()
        for forbidden in ('ports:', 'type: ssl'):
            self.assertNotIn(forbidden,cfg)
        self.assertIn('ingress: false',cfg)
        self.assertIn('webui: "https://instagram.romeropi.duckdns.org:8443/panel"',cfg)
        code=(ROOT/'server.py').read_text()
        self.assertNotIn('create_server(',code)
        self.assertNotIn('9443',code)
        self.assertFalse((ROOT/'standalone_https.py').exists())

    def test_generator_never_overwrites(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest=Path(tmp)/'instagram.conf'
            args=[sys.executable,str(ROOT/'tools/generate_proxy.py'),'--public-url','https://central.test:8443',
                  '--ha-host','ha.test','--upstream-host','backend','--output',str(dest)]
            self.assertEqual(subprocess.run(args,capture_output=True).returncode,0)
            original=dest.read_bytes()
            self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
            self.assertEqual(dest.read_bytes(),original)
