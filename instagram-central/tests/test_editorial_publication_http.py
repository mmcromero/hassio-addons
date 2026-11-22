import json
import unittest
from unittest.mock import patch
from urllib.parse import urlsplit

import test_editorial_http as existing
import editorial_http
from editorial_publishing import PublisherHub
from test_editorial_publishing import FakeMeta

server = existing.server


class PublicationHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = existing.EditorialHTTPTests(); self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.meta = FakeMeta(); self.meta.delivery = server.PUBLICATION_DELIVERY
        self.hub = PublisherHub(server.meta_configuration_for_business,
            lambda business: {'business_id': business,
                'account_id': server.meta_configuration_for_business(business)['instagram_account_id'],
                'username': server.meta_configuration_for_business(business)['instagram_expected_username'],
                'verified_at': 1, 'access_token': 'synthetic-only-access-token'},
            server.editorial_store_for_business, lambda: ['umdoislab'], server.PUBLICATION_DELIVERY,
            api_factory=self.meta.client,
            checker=lambda *a, **k: {'origin': 'https://callback.example:8443', 'stories': True})
        patcher = patch.object(server, 'PUBLICATIONS', self.hub);patcher.start();self.addCleanup(patcher.stop)

    def operation(self, post, action, data, *, business='umdoislab', token_action=None, cookie=True):
        token = server.panel_login.admin_csrf_token(self.fixture.cookie, self.fixture.cfg['panel_password'],
                                                   editorial_http.csrf_action(token_action or action, business))
        prefix = '' if business == 'umdoislab' else '/accounts/' + business
        path = prefix+'/editorial/api/'+('drafts' if action == 'check' else 'posts/'+post+'/approve')
        return self.fixture.request(path, 'POST', json.dumps(data), {
            'Content-Type': 'application/json', 'X-CSRF-Token': token, 'X-Editorial-Action': action}, cookie=cookie)

    def approved(self):
        post, media = self.fixture.draft()
        self.assertEqual(self.fixture.post('posts/'+post+'/approve', {'version': self.fixture.state()['posts'][0]['version']}, 'approve')[0], 200)
        return post, media, self.fixture.state()['posts'][0]['version']

    def test_existing_proxy_path_supports_publish_but_requires_own_csrf_and_session(self):
        post, _, version = self.approved()
        self.assertEqual(self.operation(post, 'publish', {'version': version}, cookie=False)[0], 403)
        self.assertEqual(self.operation(post, 'publish', {'version': version}, token_action='approve')[0], 403)
        self.assertEqual(self.operation(post, 'publish', {'version': version, 'businessId': 'other'})[0], 422)
        self.assertEqual(self.operation(post, 'publish', {'version': version})[0], 200)
        self.assertEqual(self.operation(post, 'publish', {'version': version})[0], 409)
        for _ in range(6): self.hub.step('umdoislab')
        self.assertEqual(self.fixture.state()['posts'][0]['status'], 'published')
        self.assertEqual(len(self.meta.published), 1)

    def test_check_is_read_only_and_does_not_authorize_old_material(self):
        self.approved()
        status, _, raw = self.operation(None, 'check', {})
        self.assertEqual(status, 200);self.assertTrue(json.loads(raw)['ready'])
        self.assertFalse(self.fixture.state()['posts'][0]['publishAuthorized'])
        self.assertEqual(self.meta.calls, [])

    def test_metrics_are_authenticated_scoped_and_cannot_publish_or_use_other_csrf(self):
        post, _, version = self.approved()
        self.assertEqual(self.operation(post, 'metrics', {'version': version})[0], 422)
        self.operation(post, 'publish', {'version': version})
        for _ in range(6): self.hub.step('umdoislab')
        version = self.fixture.state()['posts'][0]['version']
        self.assertEqual(self.operation(post, 'metrics', {'version': version}, cookie=False)[0], 403)
        self.assertEqual(self.operation(post, 'metrics', {'version': version}, token_action='publish')[0], 403)
        self.assertEqual(self.operation(post, 'metrics', {'version': version, 'remoteId': '18000000000009999'})[0], 422)
        status, _, raw = self.operation(post, 'metrics', {'version': version})
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw)['metrics']['likes'], 12)
        self.assertEqual(len(self.meta.published), 1)
        self.assertEqual(self.fixture.state()['posts'][0]['version'], version)
        with server.database() as db:
            business = server.account_registry.provision(db, 'other_account', 'Other')
            server.account_registry.bind_verified(db, business, '17841400000000002', 'other_account')
        self.assertEqual(self.operation(post, 'metrics', {'version': version}, business=business)[0], 422)
        self.assertEqual(len([call for call in self.meta.calls if call[0]=='metrics']), 1)

    def test_repeated_preflight_rejection_stays_specific_instead_of_becoming_503(self):
        import editorial_graph
        post, _, version = self.approved()
        def rejected(*args, **kwargs):
            raise editorial_graph.PublishingError('meta_rejected', code=100, stage='profile')
        self.hub.checker = rejected
        for _ in range(3):
            status, _, raw = self.operation(post, 'publish', {'version': version})
            self.assertEqual(status, 422)
            self.assertIn('Código Meta: 100', json.loads(raw)['error'])
            self.assertIn('identidade', json.loads(raw)['error'])
        self.assertEqual(self.meta.calls, [])

    def test_delete_uses_existing_proxy_routes_with_own_csrf_and_account_boundary(self):
        post, mid, version = self.approved()
        payload = {'version': version, 'deleteUnusedMedia': True}
        self.assertEqual(self.operation(post, 'delete_post', payload, cookie=False)[0], 403)
        self.assertEqual(self.operation(post, 'delete_post', payload, token_action='approve')[0], 403)
        with server.database() as db:
            business = server.account_registry.provision(db, 'other_account', 'Other')
            server.account_registry.bind_verified(db, business, '17841400000000002', 'other_account')
        self.assertEqual(self.operation(post, 'delete_post', payload, business=business)[0], 409)
        self.assertEqual(self.operation(post, 'delete_post', {**payload, 'deleteUnusedMedia': 'true'})[0], 422)
        status, _, raw = self.operation(post, 'delete_post', payload)
        self.assertEqual(status, 200); self.assertEqual(json.loads(raw)['deletedMedia'], 1)
        self.assertEqual(self.fixture.state()['posts'], [])
        self.assertEqual(self.fixture.request('/editorial/media/'+mid)[0], 422)
        self.assertEqual(self.operation(post, 'delete_post', payload)[0], 409)

    def test_library_delete_rejects_referenced_media_and_requires_delete_media_csrf(self):
        post, mid, version = self.approved()
        token = server.panel_login.admin_csrf_token(self.fixture.cookie, self.fixture.cfg['panel_password'], editorial_http.csrf_action('delete_media'))
        headers = {'Content-Type': 'application/json', 'X-CSRF-Token': token, 'X-Editorial-Action': 'delete_media'}
        self.assertEqual(self.fixture.request('/editorial/api/drafts', 'POST', json.dumps({'mediaId': mid}), headers)[0], 422)
        self.operation(post, 'delete_post', {'version': version, 'deleteUnusedMedia': False})
        self.assertEqual(self.fixture.request('/editorial/api/drafts', 'POST', json.dumps({'mediaId': mid}), headers)[0], 200)
        self.assertEqual(self.fixture.state()['media'], [])

    def test_public_media_capability_supports_head_range_expiry_without_opening_library(self):
        post, media, version = self.approved()
        self.operation(post, 'publish', {'version': version})
        self.hub.step('umdoislab'); self.hub.step('umdoislab')
        url = next(call[2]['image_url'] for call in self.meta.calls if call[0] == 'create')
        path = '/webhook/instagram?' + urlsplit(url).query
        status, headers, raw = self.fixture.request(path, cookie=False)
        self.assertEqual(status, 200);self.assertEqual(headers['Content-Type'], 'image/jpeg')
        self.assertEqual(raw[:3], b'\xff\xd8\xff');self.assertEqual(headers['Cache-Control'], 'no-store')
        self.assertEqual(self.fixture.request(path, 'HEAD', cookie=False)[2], b'')
        status, headers, part = self.fixture.request(path, headers={'Range': 'bytes=0-9'}, cookie=False)
        self.assertEqual(status, 206);self.assertEqual(part, raw[:10])
        self.assertEqual(self.fixture.request(path, headers={'Range': 'bytes=-10'}, cookie=False)[2], raw[-10:])
        self.assertEqual(self.fixture.request(path, headers={'Range': 'bytes=0-1,3-4'}, cookie=False)[0], 416)
        self.assertEqual(self.fixture.request('/editorial/media/'+media, cookie=False)[0], 403)
        self.assertEqual(self.fixture.request(path+'&extra=1', cookie=False)[0], 404)
        with server.database() as db: db.execute('UPDATE publication_downloads SET expires_at=0')
        self.assertEqual(self.fixture.request(path, cookie=False)[0], 404)

    def test_secondary_route_cannot_publish_primary_post_or_use_primary_csrf(self):
        post, _, version = self.approved()
        with server.database() as db:
            business = server.account_registry.provision(db, 'other_account', 'Other')
            server.account_registry.bind_verified(db, business, '17841400000000002', 'other_account')
        self.assertEqual(self.operation(post, 'publish', {'version': version}, business=business)[0], 422)
        token = server.panel_login.admin_csrf_token(self.fixture.cookie, self.fixture.cfg['panel_password'],
                                                   editorial_http.csrf_action('publish'))
        path = '/accounts/'+business+'/editorial/api/posts/'+post+'/approve'
        self.assertEqual(self.fixture.request(path, 'POST', json.dumps({'version': version}), {
            'Content-Type': 'application/json', 'X-CSRF-Token': token, 'X-Editorial-Action': 'publish'})[0], 403)
        self.assertEqual(self.meta.published, [])
