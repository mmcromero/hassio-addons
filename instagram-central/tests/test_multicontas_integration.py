"""Cross-module tenant regression tests. Loopback/local SQLite only."""
import hmac
import hashlib
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path
from urllib.parse import urlencode
from http.server import ThreadingHTTPServer
from http.client import HTTPConnection
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location('multicontas_test_server', ROOT / 'server.py')
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
import account_registry as accounts
import panel_login


class CrossModuleIsolationTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old_data, self.old_db, self.old_settings = server.DATA_DIR, server.DB_PATH, server.settings
        server.DATA_DIR = Path(self.tmp.name)
        server.DB_PATH = server.DATA_DIR / 'instagram.sqlite3'
        self.cfg = {
            'instagram_account_id': 'business-1',
            'panel_password': 'test-only-password-long-enough',
            'meta_app_secret': 'test-only-secret-for-webhooks',
            'bridge_secret': 'test-only-bridge-secret-long-enough-123',
            'ingress_enabled': True, 'drafts_enabled': False,
            'meta_oauth_enabled': False,
        }
        server.settings = lambda: self.cfg

    def tearDown(self):
        server.DATA_DIR, server.DB_PATH, server.settings = (self.old_data, self.old_db,
                                                            self.old_settings)
        self.tmp.cleanup()

    @staticmethod
    def event(recipient, sender='person-1', mid='same-mid', text='hello'):
        return json.dumps({'object':'instagram', 'entry':[{'id':recipient,
            'messaging':[{'sender':{'id':sender},'recipient':{'id':recipient},
                          'message':{'mid':mid,'text':text}}]}]}).encode()

    def test_unknown_and_second_account_not_enabled_by_existing_webhook(self):
        self.assertEqual(server.persist(self.event('business-1'), 'business-1'), 1)
        with server.database() as conn:
            accounts.register(conn,'avisaqui','business-2','avisaqui','Avisaqui',enabled=True)
        self.assertEqual(server.persist(self.event('business-2'), 'business-1'), 0)
        self.assertEqual(server.persist(self.event('unknown-3'), 'business-1'), 0)
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0], 1)
            self.assertEqual(accounts.active_meta_ids(conn), frozenset({'business-1','business-2'}))

    def test_same_sender_mid_across_accounts_do_not_cross_queue_or_panel(self):
        self.assertEqual(server.persist(self.event('business-1', text='one account'), 'business-1'), 1)
        with server.database() as conn:
            accounts.register(conn,'avisaqui','business-2','avisaqui','Avisaqui',enabled=True)
            conn.execute('''INSERT INTO inbound(recipient_id,sender_id,message_id,message_text,received_at)
                            VALUES (?,?,?,?,?)''', ('business-2','person-1','same-mid','other account',
                                                      '2026-11-20T00:00:00+00:00'))
        items=server.list_pending()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]['accountId'], 'business-1')
        claim=server.claim_message()
        self.assertEqual(claim['accountId'], 'business-1')
        self.assertIsNone(server.claim_message())
        html=server.render_panel(self.cfg)
        self.assertIn('one account', html)
        self.assertNotIn('other account', html)
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0], 2)

    def test_editorial_core_isolated_per_account_and_legacy_paths_retained(self):
        with server.database() as conn:
            accounts.ensure_primary(conn, 'business-1')
            accounts.register(conn,'avisaqui','business-2','avisaqui','Avisaqui',enabled=True)
        a=server.editorial_store_for_business('umdoislab')
        b=server.editorial_store_for_business('avisaqui')
        self.assertEqual(a.db_path, Path(self.tmp.name)/'editorial'/'editorial.sqlite3')
        self.assertEqual(b.db_path, Path(self.tmp.name)/'editorial'/'accounts'/'avisaqui'/'editorial.sqlite3')
        one=a.create_draft('feed','caption for Umdoislab')
        two=b.create_draft('feed','caption for Avisaqui')
        self.assertIsNone(a.get_post(two))
        self.assertIsNone(b.get_post(one))
        self.assertEqual(a.get_post(one)['caption'], 'caption for Umdoislab')
        self.assertEqual(b.get_post(two)['caption'], 'caption for Avisaqui')

    def test_meta_configuration_is_account_bound_without_secrets_duplication(self):
        with server.database() as conn:
            accounts.ensure_primary(conn,'business-1')
            accounts.register(conn,'avisaqui','business-2','avisaqui','Avisaqui',enabled=True)
        # Secondary tenant must not inherit global active flags or legacy bridge key.
        self.cfg['meta_oauth_enabled'] = True
        self.cfg['drafts_enabled'] = True
        primary=server.meta_configuration_for_business('umdoislab')
        other=server.meta_configuration_for_business('avisaqui')
        self.assertEqual(primary['instagram_account_id'],'business-1')
        self.assertEqual(other['instagram_account_id'],'business-2')
        self.assertEqual(other['instagram_expected_username'],'avisaqui')
        self.assertNotEqual(accounts.credential_root(server.DATA_DIR,'umdoislab'),
                            accounts.credential_root(server.DATA_DIR,'avisaqui'))
        self.assertFalse(other['meta_oauth_enabled'])
        self.assertFalse(other['ingress_enabled'])
        self.assertFalse(other['drafts_enabled'])
        self.assertEqual(other['bridge_secret'],'')
        self.assertTrue(primary['meta_oauth_enabled'])

    def test_public_account_context_requires_existing_browser_session(self):
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        def request(path,headers=None):
            client=HTTPConnection('127.0.0.1',http.server_address[1],timeout=4)
            try:
                client.request('GET',path,headers=headers or {})
                response=client.getresponse()
                return response.status,response.read()
            finally:
                client.close()
        try:
            self.assertEqual(request('/panel/account-context')[0],403)
            with server.database() as conn:
                token=panel_login.create_session(conn,self.cfg['panel_password'])
            status,body=request('/panel/account-context',{'Cookie':'ig_panel_session='+token})
            self.assertEqual(status,200)
            result=json.loads(body)
            self.assertEqual(result['businessId'],'umdoislab')
            self.assertEqual(result['instagramAccountId'],'business-1')
            self.assertFalse(result['sendingEnabled'])
            self.assertFalse(result['publishingEnabled'])
            self.assertNotIn('panel_password',result)
            self.assertEqual(request('/panel/account-context?business_id=avisaqui')[0],404)
        finally:
            http.shutdown();http.server_close();thread.join(timeout=3)

    def test_legacy_bridge_secret_never_exposes_second_business(self):
        self.assertEqual(server.persist(self.event('business-1'), 'business-1'), 1)
        with server.database() as conn:
            accounts.register(conn,'avisaqui','business-2','avisaqui','Avisaqui',enabled=True)
            conn.execute('''INSERT INTO inbound(recipient_id,sender_id,message_id,message_text,received_at)
                            VALUES (?,?,?,?,?)''', ('business-2','person-1','same-mid','other account',
                                                      '2026-11-20T00:00:00+00:00'))
        http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        def request(path,method='GET',body=None,headers=None):
            client=HTTPConnection('127.0.0.1',http.server_address[1],timeout=4)
            try:
                client.request(method,path,body=body,headers=headers or {})
                res=client.getresponse()
                return res.status,res.read()
            finally:
                client.close()
        token={'X-Instagram-Bridge-Secret':self.cfg['bridge_secret']}
        try:
            status,body=request('/bridge/pending',headers=token)
            self.assertEqual(status,200)
            result=json.loads(body)
            self.assertEqual(len(result['messages']),1)
            self.assertEqual(result['messages'][0]['accountId'],'business-1')
            bad=json.dumps({'accountId':'business-2','senderId':'person-1','state':'human'}).encode()
            status,_=request('/bridge/handoff','POST',bad,{**token,'Content-Type':'application/json'})
            self.assertEqual(status,403)
            with server.database() as conn:
                self.assertIsNone(conn.execute(
                    "SELECT state FROM handoff WHERE recipient_id='business-2'").fetchone())
        finally:
            http.shutdown();http.server_close();thread.join(timeout=3)

    def test_token_bound_to_legacy_account_cannot_verify_other_account(self):
        import instagram_connection
        credential={'account_id':'business-1','username':'umdoislab',
                    'verified_at':1234,'subscribed_at':1235}
        other={'instagram_account_id':'business-2',
               'instagram_expected_username':'avisaqui'}
        state=instagram_connection.credential_status(credential,other)
        self.assertFalse(state['account_verified'])
        self.assertFalse(state['subscription_requested'])

    def test_malformed_recipient_does_not_raise(self):
        payload={'object':'instagram','entry':[{'messaging':[{
            'sender':{'id':'customer'}, 'recipient':{'id':['business-1']},
            'message':{'mid':'x','text':'hello'}}]}]}
        self.assertEqual(server.normalized_messages(payload,{'business-1'}),[])


if __name__=='__main__':
    unittest.main()
