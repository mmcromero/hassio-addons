"""Offline tenant isolation tests: only synthetic accounts, no Meta network."""
import sqlite3
import tempfile
from pathlib import Path
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import account_registry as accounts


class AccountRegistryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.conn = sqlite3.connect(':memory:')

    def tearDown(self):
        self.conn.close()
        self.temp.cleanup()

    def test_primary_registered_once_and_legacy_id_unchanged(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        accounts.ensure_primary(self.conn, 'test-umdois')
        resolved = accounts.resolve_meta(self.conn, 'test-umdois')
        self.assertEqual(resolved['business_id'], 'umdoislab')
        self.assertEqual(resolved['instagram_account_id'], 'test-umdois')
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM instagram_accounts').fetchone()[0], 1)

    def test_primary_can_wait_for_real_meta_account(self):
        accounts.ensure_primary(self.conn)
        self.assertEqual(accounts.active_meta_ids(self.conn), frozenset())
        accounts.ensure_primary(self.conn, 'test-umdois')
        self.assertIn('test-umdois', accounts.active_meta_ids(self.conn))

    def test_primary_rebind_is_denied(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        with self.assertRaises(accounts.RegistryError):
            accounts.ensure_primary(self.conn, 'test-other')
        self.assertIsNone(accounts.resolve_meta(self.conn, 'test-other'))

    def test_second_business_disabled_by_default(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        accounts.register(self.conn, 'avisaqui', 'test-avisaqui', 'avisaqui', 'Avisaqui')
        self.assertIsNone(accounts.resolve_meta(self.conn, 'test-avisaqui'))
        self.assertEqual(accounts.active_meta_ids(self.conn), frozenset({'test-umdois'}))

    def test_two_enabled_synthetic_accounts_isolated(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        accounts.register(self.conn, 'avisaqui', 'test-avisaqui', 'avisaqui', 'Avisaqui', enabled=True)
        self.assertEqual(accounts.resolve_meta(self.conn, 'test-avisaqui')['business_id'], 'avisaqui')
        self.assertEqual(accounts.resolve_meta(self.conn, 'test-umdois')['business_id'], 'umdoislab')
        self.assertEqual(accounts.active_meta_ids(self.conn), frozenset({'test-umdois', 'test-avisaqui'}))

    def test_unknown_recipient_refused(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        self.assertIsNone(accounts.resolve_meta(self.conn, 'unknown-123'))
        self.assertNotIn('unknown-123', accounts.active_meta_ids(self.conn))

    def test_duplicate_instagram_mapping_refused(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        with self.assertRaises(accounts.RegistryError):
            accounts.register(self.conn, 'avisaqui', 'test-umdois', 'avisaqui', 'Avisaqui')

    def test_business_slug_rejects_path_and_separators(self):
        for bad in ('../data', 'a/b', '/root', 'Avisaqui', ' a', 'a..', '', 'a', 'á', 'a\\b'):
            with self.subTest(bad=bad):
                with self.assertRaises(accounts.RegistryError):
                    accounts.editorial_root(self.temp.name, bad)

    def test_editorial_roots_separate_and_backward_compatible(self):
        legacy = accounts.editorial_root(self.temp.name, 'umdoislab')
        other = accounts.editorial_root(self.temp.name, 'avisaqui')
        self.assertEqual(legacy, Path(self.temp.name) / 'editorial')
        self.assertEqual(other, legacy / 'accounts' / 'avisaqui')
        self.assertNotEqual(legacy / 'editorial.sqlite3', other / 'editorial.sqlite3')
        self.assertNotEqual(legacy / 'media', other / 'media')

    def test_credentials_scoped_and_legacy_paths_preserved(self):
        self.assertEqual(accounts.credential_root(self.temp.name, 'umdoislab'), Path(self.temp.name))
        self.assertEqual(accounts.credential_root(self.temp.name, 'avisaqui'),
                         Path(self.temp.name) / 'accounts' / 'avisaqui')

    def test_disabled_business_denied(self):
        accounts.ensure_primary(self.conn, 'test-umdois')
        accounts.register(self.conn, 'avisaqui', 'test-avisaqui', 'avisaqui', 'Avisaqui')
        with self.assertRaises(accounts.RegistryError):
            accounts.require_business(self.conn, 'avisaqui')
        self.assertEqual(accounts.require_business(self.conn, 'umdoislab')['username'], 'umdoislab')

    def test_existing_messages_schema_untouched(self):
        self.conn.execute('CREATE TABLE inbound(recipient_id TEXT,sender_id TEXT,message_id TEXT, PRIMARY KEY(recipient_id,sender_id,message_id))')
        self.conn.execute('INSERT INTO inbound VALUES (?,?,?)', ('test-umdois','user-1','id-1'))
        accounts.ensure_primary(self.conn, 'test-umdois')
        accounts.register(self.conn,'avisaqui','test-avisaqui','avisaqui','Avisaqui', enabled=True)
        self.conn.execute('INSERT INTO inbound VALUES (?,?,?)',('test-avisaqui','user-1','id-1'))
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],2)
        self.assertEqual(self.conn.execute('SELECT COUNT(*) FROM inbound WHERE recipient_id=?',('test-umdois',)).fetchone()[0],1)


if __name__ == '__main__':
    unittest.main()
