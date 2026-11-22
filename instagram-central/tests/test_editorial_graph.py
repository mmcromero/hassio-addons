from io import BytesIO
import json
import unittest
from urllib.error import HTTPError, URLError

import editorial_graph as graph


CFG = {'instagram_account_id': '17841400000000001', 'instagram_expected_username': 'umdoislab',
       'meta_app_id': '17830000000000000', 'meta_app_secret': 'synthetic-only-secret', 'meta_graph_version': 'v27.0'}
CREDENTIAL = {'account_id': CFG['instagram_account_id'], 'username': 'umdoislab',
              'verified_at': 1, 'access_token': 'synthetic-only-access-token'}


class Response(BytesIO):
    def __init__(self, data): super().__init__(json.dumps(data).encode())


class GraphPublishingTests(unittest.TestCase):
    def test_account_path_host_and_bearer_are_fixed(self):
        requests = []
        def open_request(req, **kwargs):
            requests.append(req)
            return Response({'id': '19000000000000001'})
        api = graph.PublishingAPI(CFG, CREDENTIAL, opener=open_request)
        self.assertEqual(api.create({'image_url': 'https://callback.example/webhook/instagram?editorial_media=synthetic'}), '19000000000000001')
        self.assertEqual(api.publish('19000000000000001'), '19000000000000001')
        for req in requests:
            self.assertTrue(req.full_url.startswith('https://graph.facebook.com/v27.0/'+CFG['instagram_account_id']+'/'))
            self.assertNotIn(CREDENTIAL['access_token'], req.full_url)
            self.assertEqual(req.get_header('Authorization'), 'Bearer '+CREDENTIAL['access_token'])
        with self.assertRaises(graph.PublishingError): api.status('https://attacker.invalid')
        with self.assertRaises(graph.PublishingError): api.create({'access_token': 'override'})

    def test_remote_error_is_reduced_to_fixed_reason_and_numeric_code(self):
        def rejected(req, **kwargs):
            raise HTTPError(req.full_url, 400, 'PRIVATE', {}, BytesIO(json.dumps({
                'error': {'code': 100, 'error_subcode': 2207052, 'message': 'PRIVATE_TOKEN_AND_CAPTION'}}).encode()))
        api = graph.PublishingAPI(CFG, CREDENTIAL, opener=rejected)
        with self.assertRaises(graph.PublishingError) as caught: api.publish('19000000000000001')
        self.assertEqual(caught.exception.code, 100)
        self.assertEqual(caught.exception.subcode, 2207052)
        self.assertNotIn('PRIVATE', str(caught.exception))

    def test_transport_and_bad_json_are_ambiguous_and_redirects_are_not_followed(self):
        for failure in (URLError('PRIVATE'), HTTPError('https://graph.facebook.com', 504, 'PRIVATE', {}, BytesIO(b'PRIVATE'))):
            def fail(req, **kwargs): raise failure
            with self.assertRaises(graph.PublishingError) as caught:
                graph.PublishingAPI(CFG, CREDENTIAL, opener=fail).publish('19000000000000001')
            self.assertTrue(caught.exception.ambiguous)
            self.assertNotIn('PRIVATE', str(caught.exception))
        api = graph.PublishingAPI(CFG, CREDENTIAL, opener=lambda *a, **k: BytesIO(b'not-json'))
        with self.assertRaises(graph.PublishingError) as caught: api.publish('19000000000000001')
        self.assertTrue(caught.exception.ambiguous)
        self.assertIsNone(graph.connection._NoGraphRedirect().redirect_request(None, None, 302, '', {}, 'https://attacker.invalid'))

    def test_content_permission_check_does_not_require_messaging_permission(self):
        scopes = ['instagram_basic', 'instagram_content_publish']
        def read(version, path, token, **kwargs):
            if path == '/debug_token':
                return {'data': {'is_valid': True, 'app_id': CFG['meta_app_id'], 'scopes': scopes}}
            return {'data': [{'object': 'instagram', 'callback_url': 'https://callback.example:8443/webhook/instagram'}]}
        class API:
            def __init__(self, *a): pass
            def profile(self): return {'id': CFG['instagram_account_id'], 'username': 'umdoislab', 'account_type': 'BUSINESS'}
        result = graph.check_connection(CFG, CREDENTIAL, api_factory=API, graph=read)
        self.assertTrue(result['stories'])
        scopes.remove('instagram_content_publish')
        with self.assertRaises(graph.PublishingError) as caught:
            graph.check_connection(CFG, CREDENTIAL, api_factory=API, graph=read)
        self.assertEqual(caught.exception.reason, 'permission_required')

    def test_token_for_another_account_cannot_create_a_client(self):
        with self.assertRaises(graph.PublishingError):
            graph.PublishingAPI(CFG, {**CREDENTIAL, 'account_id': '17841400000000002'})

    def test_permalink_allows_only_instagram_publication_links(self):
        for link, expected in [('https://www.instagram.com/p/abc123/', True),
                               ('https://attacker.invalid/p/abc123/', False),
                               ('https://www.instagram.com/p/abc123/?secret=private', False)]:
            api = graph.PublishingAPI(CFG, CREDENTIAL, opener=lambda *a, **k: Response({'permalink': link}))
            self.assertEqual(bool(api.permalink('19000000000000001')), expected)
