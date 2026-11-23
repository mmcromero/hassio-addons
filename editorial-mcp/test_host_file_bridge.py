import hashlib
import json
import unittest
from datetime import datetime, timedelta, timezone
from urllib.error import HTTPError
from unittest.mock import patch

import server


TOKEN = 'cei1.umdoislab.' + 'a' * 32 + '.' + 'b' * 43
PNG = b'\x89PNG\r\n\x1a\n' + b'\x00' * 8
REQUEST_ID = 'host_file_transfer_001'


def signed_url(expiry=None, host='sdmntprbrazilsouth.oaiusercontent.com'):
    expiry = expiry or (datetime.now(timezone.utc) + timedelta(minutes=5))
    return ('https://' + host + '/files/fixture/raw?se=' +
            expiry.isoformat(timespec='seconds').replace('+00:00', 'Z') +
            '&sp=r&sr=b&sig=synthetic-signature')


class FakeResponse:
    status = 200

    def __init__(self, data):
        self.data = data
        self.headers = {'Content-Length': str(len(data))}

    def read(self, size=-1):
        return self.data[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeOpener:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def open(self, request, timeout):
        self.calls.append((request, timeout))
        return FakeResponse(self.data)


class FakeCentral:
    def __init__(self):
        self.calls = []
        self.records = {}

    def call(self, token, action, data, **kwargs):
        self.calls.append((token, action, data, kwargs))
        if action == 'receipt':
            return self.records.get((token, data['requestId']), {'found': False})
        if action == 'upload':
            return {'id': format(kwargs['index'] + 1, '032x')}
        if action == 'commit':
            result = {'found': True, 'id': 'a' * 32, 'contentDigest': data['contentDigest'],
                      'status': 'draft', 'published': False, 'publicationAuthorized': False}
            self.records[(token, data['requestId'])] = result
            return result
        raise AssertionError(action)


def manifest(data=PNG, url=None, request_id=REQUEST_ID, fmt='story'):
    return {
        'requestId': request_id,
        'transferApproved': True,
        'format': fmt,
        'caption': 'Teste privado',
        'media': [{
            'mime': 'image/png',
            'url': url or signed_url(),
            'bytes': len(data),
            'sha256': hashlib.sha256(data).hexdigest()
        }]
    }


class HostFileBridgeTests(unittest.TestCase):
    def test_fetch_valid_signed_host_file_in_memory(self):
        args = manifest()
        opener = FakeOpener(PNG)
        with patch('server.build_opener', return_value=opener):
            result = server.fetch_host_file(args['media'][0]['url'], 'image/png',
                                            len(PNG), hashlib.sha256(PNG).hexdigest())
        self.assertEqual(result, PNG)
        self.assertEqual(len(opener.calls), 1)
        request, timeout = opener.calls[0]
        self.assertEqual(request.get_method(), 'GET')
        self.assertEqual(timeout, 15)
        self.assertEqual(request.get_header('Authorization'), None)

    def test_rejects_non_host_public_and_expired_urls_before_network(self):
        invalid = [
            'https://drive.google.com/files/a/raw?se=x&sp=r&sr=b&sig=x',
            signed_url(host='evil.example'),
            signed_url().replace('&sp=r&', '&sp=rw&'),
            signed_url().replace('/files/fixture/raw', '/files/%2e%2e/other/raw'),
            'http://sdmntprbrazilsouth.oaiusercontent.com/files/a/raw?se=x&sp=r&sr=b&sig=x',
            signed_url(expiry=datetime.now(timezone.utc) - timedelta(minutes=1)),
            'https://sdmntprbrazilsouth.oaiusercontent.com/files/a/raw?sp=r&sr=b'
        ]
        with patch('server.build_opener') as opener:
            for url in invalid:
                with self.subTest(url=url), self.assertRaises(server.Refused):
                    server.fetch_host_file(url, 'image/png', len(PNG), hashlib.sha256(PNG).hexdigest())
            opener.assert_not_called()

    def test_rejects_redirect_without_following_it(self):
        args = manifest()
        error = HTTPError(args['media'][0]['url'], 302, 'Found', {}, None)

        class RedirectOpener:
            def open(self, request, timeout):
                raise error

        with patch('server.build_opener', return_value=RedirectOpener()):
            with self.assertRaisesRegex(server.Refused, 'Redirecionamento'):
                server.fetch_host_file(args['media'][0]['url'], 'image/png',
                                       len(PNG), hashlib.sha256(PNG).hexdigest())

    def test_rejects_size_hash_and_signature_mismatch(self):
        args = manifest()
        opener = FakeOpener(PNG)
        with patch('server.build_opener', return_value=opener):
            with self.assertRaisesRegex(server.Refused, 'Tamanho'):
                server.fetch_host_file(args['media'][0]['url'], 'image/png',
                                       len(PNG) + 1, hashlib.sha256(PNG).hexdigest())
            with self.assertRaisesRegex(server.Refused, 'SHA-256'):
                server.fetch_host_file(args['media'][0]['url'], 'image/png',
                                       len(PNG), '0' * 64)
            bad = b'not-a-png-file'
            bad_opener = FakeOpener(bad)
            with patch('server.build_opener', return_value=bad_opener):
                with self.assertRaisesRegex(server.Refused, 'Assinatura PNG'):
                    server.fetch_host_file(args['media'][0]['url'], 'image/png',
                                           len(bad), hashlib.sha256(bad).hexdigest())

    def test_transfer_uploads_only_after_verified_download_and_never_publishes(self):
        central = FakeCentral()
        args = manifest()
        opener = FakeOpener(PNG)
        with patch('server.build_opener', return_value=opener):
            result = server.transfer_host_files(central, TOKEN, args)
        self.assertEqual(result['status'], 'draft')
        self.assertFalse(result['published'])
        self.assertFalse(result['publicationAuthorized'])
        actions = [call[1] for call in central.calls]
        self.assertEqual(actions, ['receipt', 'upload', 'commit'])
        self.assertEqual(central.calls[1][2], PNG)
        self.assertEqual(len(opener.calls), 1)

    def test_same_request_is_idempotent_without_refetch(self):
        central = FakeCentral()
        args = manifest()
        digest = hashlib.sha256(json.dumps({
            'format': args['format'], 'caption': args['caption'],
            'files': [{'sha256': args['media'][0]['sha256'], 'mime': 'image/png'}]
        }, sort_keys=True).encode()).hexdigest()
        central.records[(TOKEN, REQUEST_ID)] = {
            'found': True, 'id': 'a' * 32, 'contentDigest': digest,
            'status': 'draft', 'published': False
        }
        with patch('server.build_opener') as opener:
            result = server.transfer_host_files(central, TOKEN, args)
        self.assertTrue(result['found'])
        opener.assert_not_called()
        self.assertEqual([call[1] for call in central.calls], ['receipt'])

    def test_requires_explicit_approval_and_rejects_drive_public_url(self):
        central = FakeCentral()
        args = manifest(url='https://drive.google.com/uc?id=not-publicly-accepted')
        args['transferApproved'] = False
        with self.assertRaises(server.Refused):
            server.transfer_host_files(central, TOKEN, args)
        args['transferApproved'] = True
        with patch('server.build_opener') as opener:
            with self.assertRaises(server.Refused):
                server.transfer_host_files(central, TOKEN, args)
            opener.assert_not_called()
        self.assertEqual([call[1] for call in central.calls], ['receipt'])

    def test_rejects_aggregate_limit_and_wrong_media_count(self):
        central = FakeCentral()
        args = manifest()
        args['format'] = 'carousel'
        args['media'] = [
            {'mime': 'image/png', 'url': signed_url(), 'bytes': 3 * 1024 * 1024, 'sha256': 'a' * 64},
            {'mime': 'image/png', 'url': signed_url(), 'bytes': 2 * 1024 * 1024, 'sha256': 'b' * 64}
        ]
        with self.assertRaisesRegex(server.Refused, '4 MiB'):
            server.transfer_host_files(central, TOKEN, args)
        self.assertEqual(central.calls, [])

    def test_read_only_validation_tool_never_calls_central(self):
        central = FakeCentral()
        args = manifest()
        opener = FakeOpener(PNG)
        payload = {'jsonrpc': '2.0', 'id': 1, 'method': 'tools/call', 'params': {
            'name': 'validar_arquivo_temporario', 'arguments': {
                'mime': 'image/png', 'url': args['media'][0]['url'],
                'bytes': len(PNG), 'sha256': hashlib.sha256(PNG).hexdigest()}}}
        with patch('server.build_opener', return_value=opener):
            status, response = server.dispatch(central, TOKEN, payload)
        self.assertEqual(status, 200)
        result = json.loads(response['result']['content'][0]['text'])
        self.assertTrue(result['verified'])
        self.assertFalse(result['persisted'])
        self.assertEqual(result['bytes'], len(PNG))
        self.assertEqual(result['sha256'], hashlib.sha256(PNG).hexdigest())
        self.assertEqual(central.calls, [])
    def test_new_mcp_tool_is_listed(self):
        status, response = server.dispatch(FakeCentral(), TOKEN, {
            'jsonrpc': '2.0', 'id': 1, 'method': 'tools/list', 'params': {}
        })
        self.assertEqual(status, 200)
        names = [item['name'] for item in response['result']['tools']]
        self.assertIn('enviar_arquivo_temporario_para_revisao', names)
        self.assertIn('validar_arquivo_temporario', names)


if __name__ == '__main__':
    unittest.main()
