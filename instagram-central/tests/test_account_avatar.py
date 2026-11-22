"""No Meta traffic: identity isolation, bounded downloads, cache and HTTP auth."""
from io import BytesIO
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import Mock, patch
from PIL import Image

import account_avatar as avatars
import instagram_connection as meta
import interface_ui
import account_registry
import test_http as fixture_http
server = fixture_http.server
from urllib.parse import urlencode


def jpeg(color='red'):
    out = BytesIO(); Image.new('RGB', (180, 120), color).save(out, 'JPEG'); return out.getvalue()


class AvatarTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.cfg = {'business_id': 'umdoislab', 'instagram_account_id': '11111111',
                    'instagram_expected_username': 'umdoislab', 'meta_graph_version': 'v27.0'}
        self.credential = {'business_id': 'umdoislab', 'account_id': '11111111',
                           'username': 'umdoislab', 'verified_at': 1, 'access_token': 'synthetic-token-only-123456'}
        self.graph = Mock(return_value={'id': '11111111', 'username': 'umdoislab',
                                        'profile_picture_url': 'https://scontent.cdninstagram.com/photo.jpg'})
        self.fetch = Mock(return_value=jpeg())

    def get(self, cfg=None, credential=None):
        return avatars.get(self.root, cfg or self.cfg, credential or self.credential,
                           graph=self.graph, fetch=self.fetch)

    def test_cache_normalized_private_and_no_provider_url_or_token_on_disk(self):
        first = self.get(); self.assertEqual(self.get(), first)
        self.graph.assert_called_once_with('v27.0', '/11111111', self.credential['access_token'],
            fields={'fields': 'id,username,profile_picture_url'})
        self.fetch.assert_called_once()
        self.assertEqual(Image.open(BytesIO(first)).size, (96, 96))
        photo = next(self.root.rglob('*.jpg')); self.assertEqual(photo.stat().st_mode & 0o777, 0o600)
        for path in self.root.rglob('*'):
            if path.is_file():
                self.assertNotIn(b'scontent', path.read_bytes()); self.assertNotIn(b'synthetic-token', path.read_bytes())

    def test_failure_negative_cache_and_stale_image_preserved(self):
        first = self.get(); photo = next(self.root.rglob('*.jpg')); checked = next(self.root.rglob('*.checked'))
        os.utime(photo, (1, 1)); os.utime(checked, (1, 1))
        self.graph.side_effect = meta.ConnectionError('synthetic failure')
        self.assertEqual(self.get(), first); self.assertEqual(self.get(), first)
        self.assertEqual(self.graph.call_count, 2)

    def test_expired_cache_is_refreshed_after_success_and_missing_field_keeps_photo(self):
        first = self.get(); photo = next(self.root.rglob('*.jpg')); checked = next(self.root.rglob('*.checked'))
        os.utime(photo, (1, 1)); os.utime(checked, (1, 1))
        self.fetch.return_value = jpeg('blue')
        second = self.get(); self.assertNotEqual(second, first)
        os.utime(photo, (1, 1)); os.utime(checked, (1, 1))
        self.graph.return_value.pop('profile_picture_url')
        self.fetch.side_effect = ValueError('Missing URL')
        self.assertEqual(self.get(), second)

    def test_concurrent_request_does_not_start_another_graph_call(self):
        lock = avatars._LOCKS[sum(b'umdoislab') % len(avatars._LOCKS)]
        with lock:
            self.assertIsNone(self.get())
        self.graph.assert_not_called()

    def test_production_opener_refuses_redirects(self):
        self.assertIsNone(meta._NoGraphRedirect().redirect_request(None, None, 302, '', {}, 'https://evil.test'))

    def test_initial_failure_retries_are_bounded(self):
        self.graph.side_effect = meta.ConnectionError('failure')
        self.assertIsNone(self.get()); self.assertIsNone(self.get()); self.graph.assert_called_once()

    def test_mismatched_saved_credential_never_queries_or_returns_primary_photo(self):
        self.get(); self.graph.reset_mock()
        self.assertIsNone(self.get(credential={**self.credential, 'business_id': 'secondary'}))
        self.graph.assert_not_called()

    def test_provider_identity_mismatch_never_downloads(self):
        for field, value in [('id', '22222222'), ('username', 'someone_else')]:
            with self.subTest(field=field), tempfile.TemporaryDirectory() as directory:
                self.graph.return_value = {'id': '11111111', 'username': 'umdoislab', field: value}
                self.assertIsNone(avatars.get(directory, self.cfg, self.credential, graph=self.graph, fetch=self.fetch))
        self.fetch.assert_not_called()

    def test_accounts_have_distinct_cache_and_use_their_own_token(self):
        first = self.get()
        cfg = {**self.cfg, 'business_id': 'other', 'instagram_account_id': '22222222', 'instagram_expected_username': 'other'}
        credential = {**self.credential, 'business_id': 'other', 'account_id': '22222222', 'username': 'other', 'access_token': 'second-token'}
        self.graph.return_value = {'id': '22222222', 'username': 'other', 'profile_picture_url': 'https://s.fbcdn.net/a.jpg'}
        self.fetch.return_value = jpeg('blue')
        second = self.get(cfg, credential)
        self.assertNotEqual(first, second)
        self.assertEqual(self.get(), first)
        self.assertEqual(self.graph.call_args.args[2], 'second-token')

    def test_symlink_cache_is_refused(self):
        (self.root / 'profile-images').symlink_to(self.root, target_is_directory=True)
        self.assertIsNone(self.get()); self.graph.assert_not_called()

    def test_url_restrictions_no_redirect_or_authorization_and_bounded_body(self):
        for url in ['http://s.fbcdn.net/a','https://localhost/a','https://127.0.0.1/a',
                    'https://s.fbcdn.net.evil.test/a','https://u:p@s.fbcdn.net/a',
                    'https://s.fbcdn.net:444/a','https://evil.test/?s.fbcdn.net']:
            opener = Mock()
            with self.subTest(url=url), self.assertRaises(ValueError): avatars.download(url, opener)
            opener.assert_not_called()
        response = Mock(); response.__enter__ = Mock(return_value=response); response.__exit__ = Mock()
        response.read.return_value = jpeg(); opener = Mock(return_value=response)
        avatars.download('https://s.fbcdn.net/photo', opener)
        req = opener.call_args.args[0]
        self.assertNotIn('Authorization', req.headers); self.assertNotIn('Cookie', req.headers)
        response.read.assert_called_once_with(avatars.MAX_BYTES + 1)
        response.read.return_value = b'x' * (avatars.MAX_BYTES + 1)
        with self.assertRaises(ValueError): avatars.download('https://s.fbcdn.net/photo', opener)

    def test_rejects_non_image_and_oversized_dimensions(self):
        for raw in [b'<svg><script>bad</script></svg>', b'x' * (avatars.MAX_BYTES + 1)]:
            with self.assertRaises((ValueError, OSError)): avatars.thumbnail(raw)
        out = BytesIO(); Image.new('RGB', (4097, 1)).save(out, 'PNG')
        with self.assertRaises(ValueError): avatars.thumbnail(out.getvalue())

    def test_graph_profile_path_has_exact_field_allowlist(self):
        with self.assertRaises(meta.ConnectionError):
            meta.request_graph('v27.0', '/11111111', 'x'*30, fields={'fields': 'messages'}, opener=Mock())

    def test_header_escapes_labels_uses_local_urls_and_preserves_native_fallback(self):
        raw = interface_ui.header({**self.cfg, 'account_display_name': '<bad>', 'navigation_accounts': [
            {'business_id': 'umdoislab', 'display_name': '<bad>', 'username': 'umdoislab'},
            {'business_id': 'second', 'display_name': 'Second', 'username': 'second'}]}, 'Mensagens')
        self.assertIn('data-account-switch', raw); self.assertIn('data-native-account-picker', raw)
        self.assertIn('/accounts/second/panel?view=profile-image', raw)
        self.assertNotIn('<bad>', raw); self.assertNotIn('https://', raw)
        self.assertIn("img-src 'self'", interface_ui.policy("default-src 'none'"))


class AvatarHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture_http.HTTPContractTests(); self.fixture.setUp(); self.addCleanup(self.fixture.tearDown)
        self.fixture.config['instagram_account_id'] = '11111111'
        self.fixture.config['ingress_enabled'] = False
        status, headers, _ = self.fixture.request('/auth/login', 'POST', urlencode({
            'username': 'admin', 'password': self.fixture.config['panel_password']}),
            {'Content-Type': 'application/x-www-form-urlencoded', 'X-Forwarded-Proto': 'https'})
        self.assertEqual(status, 303); self.cookie = headers['Set-Cookie'].split(';')[0]
        with server.database() as conn:
            account_registry.ensure_primary(conn, '11111111')
            self.second = account_registry.provision(conn, 'second', 'Second')
            account_registry.bind_verified(conn, self.second, '22222222', 'second')

    def test_image_routes_require_session_scope_and_no_store(self):
        with patch.object(server.account_avatar, 'get', return_value=jpeg()) as get, patch.object(server, '_meta_credential', return_value={}):
            for prefix, business in [('', 'umdoislab'), ('/accounts/' + self.second, self.second)]:
                path = prefix + '/panel?view=profile-image'
                self.assertEqual(self.fixture.request(path)[0], 403)
                status, headers, body = self.fixture.request(path, headers={'Cookie': self.cookie})
                self.assertEqual(status, 200); self.assertEqual(headers['Content-Type'], 'image/jpeg')
                self.assertEqual(headers['Cache-Control'], 'no-store'); self.assertEqual(body, jpeg())
                self.assertEqual(get.call_args.args[1]['business_id'], business)
            self.assertEqual(get.call_count, 2)
            self.assertEqual(self.fixture.request('/accounts/unknown/panel?view=profile-image', headers={'Cookie': self.cookie})[0], 404)

    def test_no_photo_returns_404_without_provider_data(self):
        with patch.object(server.account_avatar, 'get', return_value=None):
            status, _, body = self.fixture.request('/panel?view=profile-image', headers={'Cookie': self.cookie})
        self.assertEqual(status, 404); self.assertEqual(body, b'')
