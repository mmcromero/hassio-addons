"""Separate account settings and native HA launcher; loopback/synthetic only."""
import json
import re
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.parse import urlencode

import test_http as contracts

server = contracts.server


class SettingsNavigation(unittest.TestCase):
    def setUp(self):
        self.fixture = contracts.HTTPContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        _, headers, _ = self.fixture.request('/auth/login', 'POST', urlencode({
            'username': 'admin', 'password': self.fixture.config['panel_password']}),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        self.headers = {'Cookie': headers['Set-Cookie'].split(';')[0]}

    def request(self, path):
        return self.fixture.request(path, headers=self.headers)

    def test_settings_are_separate_cached_only_documents_without_message_content(self):
        self.assertEqual(self.fixture.post_event()[0], 200)
        cached = {'ready': True, 'message': 'Diagnóstico sintético', 'checkedAt': 1795317079}
        with patch.object(server.PUBLICATIONS, 'public_state', return_value=cached) as state, \
                patch.object(server.instagram_connection, 'request_graph') as graph:
            status, _, messages = self.request('/panel')
            self.assertEqual(status, 200)
            state.assert_not_called()
            self.assertIn(b'customer-1', messages)
            self.assertIn(b'id="messages"', messages)
            self.assertNotIn(b'id="meta-actions"', messages)
            self.assertNotIn(b'id="check-publication"', messages)
            for _ in range(2):
                status, headers, settings = self.request('/panel?view=settings')
                self.assertEqual(status, 200)
                self.assertIn(b'id="meta-actions"', settings)
                self.assertIn(b'id="check-publication"', settings)
                self.assertIn(b'customer-1', messages)
                self.assertNotIn(b'customer-1', settings)
                self.assertNotIn(b'id="messages"', settings)
                self.assertIn(b'Diagn\xc3\xb3stico sint\xc3\xa9tico', settings)
                self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
            self.assertEqual(state.call_count, 2)
            graph.assert_not_called()

    def test_secondary_settings_keep_identity_routes_and_login_boundaries(self):
        with server.database() as db:
            server.account_registry.ensure_primary(db, 'business-1')
            business = server.account_registry.provision(db, 'second_review', 'Segunda')
        path = '/accounts/' + business
        cached = {'ready': False, 'message': 'Sem consulta', 'checkedAt': None}
        with patch.object(server.PUBLICATIONS, 'public_state', return_value=cached) as state:
            status, _, body = self.request(path + '/panel?view=settings')
            self.assertEqual(status, 200)
            state.assert_called_once_with(business)
            self.assertIn(('data-publication-base="'+path+'/editorial/"').encode(), body)
            self.assertIn(('href="'+path+'/panel?view=settings" aria-current="page"').encode(), body)
        self.assertEqual(self.fixture.request(path+'/panel?view=settings')[0], 403)
        self.assertIn(b'autocomplete="current-password"', self.fixture.request('/panel?view=settings')[2])
        for suffix in ('?view=unknown', '?view=settings&view=settings', '?view=settings&other=1'):
            self.assertEqual(self.request('/panel'+suffix)[0], 404)

    def test_chat_link_attribution_preserves_login_and_panel(self):
        for path in ('/', '/panel'):
            for tracking in ('utm_source=chatgpt.com',
                             'utm_source=chatgpt.com&utm_medium=referral'):
                url = path + '?' + tracking
                with self.subTest(url=url):
                    status, _, body = self.fixture.request(url)
                    self.assertEqual(status, 200)
                    self.assertIn(b'autocomplete="current-password"', body)
                    self.assertNotIn(b'id="messages"', body)
                    status, _, body = self.request(url)
                    self.assertEqual(status, 200)
                    self.assertIn(b'id="messages"', body)
                    self.assertNotIn(b'autocomplete="current-password"', body)

    def test_chat_link_preserves_settings_and_rejects_unknown_parameters(self):
        for query in ('view=settings&utm_source=chatgpt.com',
                      'utm_source=chatgpt.com&view=settings'):
            status, _, body = self.request('/panel?' + query)
            self.assertEqual(status, 200)
            self.assertIn(b'id="meta-actions"', body)
        result = next(iter(server.META_RESULTS))
        query = urlencode({'view': 'settings', 'meta_result': result,
                           'utm_source': 'chatgpt.com'})
        self.assertEqual(self.request('/panel?' + query)[0], 200)
        for query in ('view=unknown&utm_source=chatgpt.com',
                      'view=settings&view=settings&utm_source=chatgpt.com',
                      'other=1&utm_source=chatgpt.com',
                      'next=https://evil.test&utm_source=chatgpt.com'):
            self.assertEqual(self.request('/panel?' + query)[0], 404)

    def test_attribution_does_not_relax_launcher_or_secondary_auth(self):
        self.fixture.config['public_base_url'] = 'https://central.test:8443'
        status, headers, _ = self.fixture.request(
            '/webhook/instagram?open=central&utm_source=chatgpt.com')
        self.assertEqual(status, 403)
        self.assertNotIn('Location', headers)
        self.assertEqual(self.fixture.request('/oauth/meta/start?utm_source=chatgpt.com')[0], 404)
        with server.database() as db:
            server.account_registry.ensure_primary(db, 'business-1')
            business = server.account_registry.provision(db, 'second_review', 'Segunda')
        url = '/accounts/' + business + '/panel?utm_source=chatgpt.com'
        self.assertEqual(self.fixture.request(url)[0], 403)
        self.assertEqual(self.request(url)[0], 200)

    def test_editorial_has_no_persistent_diagnostics_or_uptime_banner(self):
        status, _, body = self.request('/editorial/')
        self.assertEqual(status, 200)
        self.assertNotIn(b'id="check-publication"', body)
        self.assertNotIn(b'id="publication-status"', body)
        self.assertNotIn('Publicação sob seu controle'.encode(), body)
        self.assertNotIn('Central precisa permanecer ligada'.encode(), body)

    def test_native_launcher_redirects_only_to_configured_https_origin(self):
        self.fixture.config.update(public_base_url='https://central.test:8443', ingress_enabled=False)
        status, headers, body = self.fixture.request('/webhook/instagram?open=central')
        self.assertEqual(status, 303)
        self.assertEqual(headers['Location'], 'https://central.test:8443/panel')
        self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertNotIn('Set-Cookie', headers)
        self.assertEqual(body, b'')
        for origin in ('', 'http://central.test', 'https://user:secret@central.test', 'https://central.test/?next=evil'):
            self.fixture.config['public_base_url'] = origin
            status, headers, _ = self.fixture.request('/webhook/instagram?open=central')
            self.assertEqual(status, 503)
            self.assertNotIn('Location', headers)

    def test_launch_query_cannot_override_destination_or_webhook_verification(self):
        self.fixture.config['public_base_url'] = 'https://central.test:8443'
        for query in ('open=central&next=https://evil.test', 'open=central&open=central', 'open=other'):
            status, headers, _ = self.fixture.request('/webhook/instagram?'+query)
            self.assertEqual(status, 403)
            self.assertNotIn('Location', headers)
        query = urlencode({'hub.mode':'subscribe', 'hub.verify_token':self.fixture.config['meta_verify_token'], 'hub.challenge':'synthetic-challenge'})
        status, _, body = self.fixture.request('/webhook/instagram?'+query)
        self.assertEqual((status, body), (200, b'synthetic-challenge'))
        self.assertEqual(self.fixture.post_event()[0], 200)

    def test_manifest_uses_native_external_ui_without_port_exposure_or_sidebar(self):
        source = (Path(__file__).resolve().parents[1]/'config.yaml').read_text()
        self.assertRegex(source, r'(?m)^ingress: false$')
        self.assertNotRegex(source, r'(?m)^(ports|host_network|ingress_port|panel_title|panel_icon):')
        url = re.search(r'(?m)^webui: "([^"]+)"$', source)[1]
        # Supervisor validate.py Web UI grammar and App.webui port fallback.
        self.assertRegex(url, r'^(?:https?|\[PROTO:\w+\]):\/\/\[HOST\]:\[PORT:\d+\].*$')
        url = re.sub(r'\[PORT:(\d+)\]', lambda match: {}.get(match[1]+'/tcp', match[1]), url)
        self.assertEqual(url.replace('[HOST]', 'romeropi.duckdns.org'),
                         'https://romeropi.duckdns.org:8443/webhook/instagram?open=central')

    def test_accounts_preserve_selected_context_and_navigation_groups(self):
        with server.database() as db:
            server.account_registry.ensure_primary(db, 'business-1')
            business=server.account_registry.provision(db,'second_review','Segunda')
        status,_,body=self.request('/accounts?account='+business)
        self.assertEqual(status,200)
        self.assertIn(b'class="topbar ui-app-header"',body)
        self.assertNotIn(b'ui-account-context',body)
        self.assertIn(b'ui-breadcrumb',body)
        self.assertIn(b'aria-label="Conta selecionada"',body)
        self.assertEqual(re.findall(rb'<section class="ui-nav-group"><h2>(.*?)</h2>',body),
                         [b'Editorial',b'Atendimento','Gestão'.encode('utf-8')])
        self.assertIn(('/accounts/'+business+'/editorial/#calendar').encode(),body)
        for query in ('account=not_registered','account='+business+'&account=umdoislab','other=umdoislab','account='):
            self.assertEqual(self.request('/accounts?'+query)[0],404)
        self.assertEqual(self.fixture.request('/accounts?account='+business)[0],403)
