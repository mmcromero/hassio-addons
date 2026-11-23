import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).parent / 'share'


class SharePwaTests(unittest.TestCase):
    def test_manifest_declares_android_file_share_target(self):
        manifest = json.loads((ROOT / 'manifest.webmanifest').read_text())
        target = manifest['share_target']
        self.assertEqual(target['method'], 'POST')
        self.assertEqual(target['enctype'], 'multipart/form-data')
        self.assertEqual(target['action'], '/share-inbox')
        self.assertEqual(target['params']['files'][0]['name'], 'files')
        self.assertEqual(set(target['params']['files'][0]['accept']),
                         {'image/jpeg', 'image/png', 'video/mp4'})

    def test_service_worker_stashes_shared_files_locally(self):
        worker = (ROOT / 'sw.js').read_text()
        self.assertIn("event.request.formData()", worker)
        self.assertIn("indexedDB.open", worker)
        self.assertIn("'/share?received=1'", worker)
        self.assertNotIn('fetch(', worker)

    def test_client_uses_authenticated_transfer_api_and_does_not_persist_key(self):
        client = (ROOT / 'app.js').read_text()
        self.assertIn("'/share-api/accounts'", client)
        self.assertIn("'/share-api/transfer'", client)
        self.assertIn("'X-API-Key'", client)
        self.assertNotIn("localStorage.setItem('editorial-api-key'", client)
        self.assertNotIn("localStorage.setItem('cei2'", client)
        self.assertIn("editorial-pending-transfer", client)

    def test_share_ui_exposes_destination_format_and_explicit_send(self):
        page = (ROOT / 'index.html').read_text()
        for value in ('id="account"', 'id="format"', 'id="caption"', 'id="send"', 'id="clear'):
            self.assertIn(value, page)


if __name__ == '__main__':
    unittest.main()
