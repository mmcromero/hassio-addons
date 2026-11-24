"""Shared HTML/CSP and account navigation boundaries; no network or real data."""
from html.parser import HTMLParser
import base64
import hashlib
import unittest
import interface_ui as ui


class Assets(HTMLParser):
    def __init__(self):
        super().__init__(); self.kind = None; self.values = {'script': [], 'style': []}
    def handle_starttag(self, tag, attrs):
        if tag in self.values: self.kind = tag
    def handle_data(self, text):
        if self.kind: self.values[self.kind].append(text)
    def handle_endtag(self, tag):
        if tag == self.kind: self.kind = None


class SharedInterfaceTests(unittest.TestCase):
    def test_enhancement_is_idempotent_and_every_added_asset_is_authorized_by_exact_hash(self):
        raw = b'<!doctype html><html><body><h1>Login</h1></body></html>'
        result = ui.enhance(raw)
        self.assertEqual(ui.enhance(result), result)
        parsed = Assets(); parsed.feed(result.decode())
        policy = ui.policy("default-src 'none'; script-src 'none'; style-src 'self'; form-action 'self'; frame-ancestors 'self'")
        self.assertNotIn('unsafe-inline', policy)
        self.assertIn("frame-ancestors 'self'", policy)
        for kind, values in parsed.values.items():
            self.assertEqual(len(values), 1)
            digest = base64.b64encode(hashlib.sha256(values[0].encode()).digest()).decode()
            self.assertIn("'sha256-"+digest+"'", policy)

    def test_existing_server_styles_are_hashed_without_unsafe_inline(self):
        style = 'body{background:#123;color:#fff}'
        raw = ui.enhance(('<html><head><style>'+style+'</style></head><body>Accounts</body></html>').encode())
        policy = ui.policy("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'", raw)
        digest = base64.b64encode(hashlib.sha256(style.encode()).digest()).decode()
        self.assertIn("'sha256-"+digest+"'", policy)
        self.assertNotIn('unsafe-inline', policy)

    def test_global_header_keeps_account_switcher_and_uses_compact_location(self):
        html = ui.header({'business_id': 'umdoislab', 'account_display_name': 'Umdoislab',
                          'instagram_expected_username': 'umdoislab'}, 'Mensagens')
        self.assertIn('<nav class="ui-breadcrumb" aria-label="Localização">', html)
        self.assertIn('<span id="current-section" aria-current="page">Mensagens</span>', html)
        self.assertIn('aria-label="Conta selecionada"', html)
        self.assertIn('Trocar conta. Conta selecionada:', html)
        self.assertNotIn('Umdoislab <span>/</span>', html)

    def test_secondary_navigation_is_scoped_and_untrusted_account_labels_are_text(self):
        html = ui.sidebar({'business_id': 'ig_0000000000000001', 'account_display_name': '<script>bad</script>',
                           'instagram_expected_username': 'secondary'}, active='messages')
        self.assertNotIn('script>bad', html)
        header = ui.header({'business_id': 'ig_0000000000000001',
                            'navigation_accounts': [{'business_id': 'ig_0000000000000001',
                                'display_name': '<script>bad</script>', 'username': 'secondary'}]}, 'Mensagens')
        self.assertNotIn('<script>bad', header)
        self.assertIn('&lt;script&gt;bad&lt;/script&gt;', header)
        for route in ('/panel', '/panel?view=settings', '/editorial/#editor'):
            self.assertIn('href="/accounts/ig_0000000000000001'+route+'"', html)
        self.assertIn('href="/accounts?account=ig_0000000000000001"', html)
        self.assertNotIn('href="/panel', html)
        self.assertNotIn('ui-account-context', html)
        self.assertIn('<h2>Editorial</h2>', html)
        self.assertIn('<h2>Atendimento</h2>', html)
        self.assertIn('<h2>Gestão</h2>', html)
        editorial = ui.sidebar({'business_id': 'ig_0000000000000001'}, editorial=True)
        self.assertIn('data-view="editor"', editorial)
        self.assertIn('data-view="approval"', editorial)
        self.assertIn('Revisão e envios', editorial)
