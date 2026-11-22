"""Sender profile cache and presentation: synthetic data, no external calls."""
from contextlib import contextmanager
import io
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock
from PIL import Image
import sender_profiles as profiles
import instagram_connection as meta


class SenderProfiles(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / 'test.sqlite3'
        self.cfg = {'business_id': 'umdoislab', 'instagram_account_id': '11111111',
                    'instagram_expected_username': 'umdoislab', 'meta_graph_version': 'v27.0'}
        self.credential = {'business_id': 'umdoislab', 'account_id': '11111111',
                           'username': 'umdoislab', 'verified_at': 1, 'access_token': 'synthetic-token-only-123456'}
        with self.database() as conn:
            conn.execute('CREATE TABLE inbound (recipient_id TEXT,sender_id TEXT,received_at TEXT)')
            conn.execute("INSERT INTO inbound VALUES('11111111','99999999','2026-11-22')")
        self.graph = Mock(return_value={'name':'Nome Teste', 'username':'teste.perfil',
                                      'profile_pic':'https://scontent.cdninstagram.com/sample.jpg'})
        image = io.BytesIO()
        Image.new('RGB', (96,96), 'blue').save(image, 'JPEG')
        self.photo = image.getvalue()
        self.fetch = Mock(return_value=self.photo)
        self.now = 10000

    @contextmanager
    def database(self):
        conn = sqlite3.connect(self.path)
        try:
            with conn:
                yield conn
        finally:
            conn.close()

    def get(self, sender='99999999', cfg=None, credential=None, **kwargs):
        return profiles.get(self.database, cfg or self.cfg, credential or self.credential,
                            sender, graph=self.graph, fetch=self.fetch, clock=lambda:self.now, **kwargs)

    def test_success_cached_photo_and_identity(self):
        expected={'name':'Nome Teste','username':'teste.perfil','has_photo':True,'status':'confirmed'}
        self.assertEqual(self.get(),expected)
        self.assertEqual(self.get(),expected)
        self.assertEqual(self.get(image_only=True),self.photo)
        self.graph.assert_called_once_with('v27.0','/99999999',self.credential['access_token'],
                                          fields={'fields':'name,username,profile_pic'},timeout=5)
        self.fetch.assert_called_once()
        self.assertNotIn(b'synthetic-token',self.path.read_bytes())
        self.assertNotIn(b'scontent.cdninstagram',self.path.read_bytes())

    def test_unknown_wrong_account_and_invalid_id_never_query(self):
        self.assertIsNone(self.get(sender='77777777'))
        self.assertIsNone(self.get(sender='../99999999'))
        self.assertIsNone(self.get(credential={**self.credential,'business_id':'other'}))
        self.assertIsNone(self.get(cfg={**self.cfg,'business_id':'other','instagram_account_id':'22222222'},
                                  credential={**self.credential,'business_id':'other','account_id':'22222222'}))
        self.assertIsNone(self.get(image_only=True))
        self.graph.assert_not_called()

    def test_provider_denial_is_negative_cached_and_message_preserved(self):
        self.graph.side_effect=meta.GraphError('permission_denied',403,200)
        self.assertEqual(self.get()['status'],'unavailable')
        self.assertEqual(self.get()['status'],'unavailable')
        self.graph.assert_called_once()
        self.assertIsNone(self.get(image_only=True))
        with self.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)
        self.now+=profiles.RETRY+1
        self.graph.side_effect=None
        self.assertEqual(self.get()['status'],'confirmed')

    def test_photo_failure_does_not_hide_valid_name(self):
        self.fetch.side_effect=ValueError('invalid CDN image')
        reply=self.get()
        self.assertEqual(reply['name'],'Nome Teste')
        self.assertFalse(reply['has_photo'])
        self.assertIsNone(self.get(image_only=True))

    def test_identity_mismatch_never_downloads(self):
        self.graph.return_value['id']='12345678'
        self.assertEqual(self.get()['status'],'unavailable')
        self.fetch.assert_not_called()

    def test_credential_epoch_and_expiration_invalidate_photo(self):
        self.get()
        self.assertIsNone(self.get(credential={**self.credential,'verified_at':2},image_only=True))
        self.now+=profiles.TTL+1
        self.assertIsNone(self.get(image_only=True))
        self.get()
        self.assertEqual(self.graph.call_count,2)

    def test_busy_does_not_duplicate_provider_lookup(self):
        with profiles._LOCK:
            self.assertEqual(self.get()['status'],'busy')
        self.graph.assert_not_called()

    def test_markup_escapes_and_scopes_identity(self):
        markup=profiles.identity_html('/accounts/secondary','99999999')
        self.assertIn('/accounts/secondary/panel?view=sender-profile&amp;sender=99999999',markup)
        self.assertIn('width="48"',markup)
        unsafe=profiles.identity_html('','<script>')
        self.assertNotIn('<script>',unsafe)
        self.assertNotIn('data-sender-profile=',unsafe)


if __name__ == '__main__':
    unittest.main()
