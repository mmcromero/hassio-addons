"""Real HTTP + isolated storage/OAuth contracts for owner-managed multiple accounts."""
import io
import json
import re
import unittest
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch
from PIL import Image
import test_http as contracts
import account_registry
import panel_login
import instagram_connection

server = contracts.server


class OperationalAccounts(unittest.TestCase):
    def setUp(self):
        self.fixture = contracts.HTTPContractTests()
        self.fixture.setUp()
        self.fixture.configure_oauth()
        self.fixture.config.update(instagram_account_id='11111111', public_base_url='https://central.test:8443',
                                   meta_oauth_redirect_uri='https://central.test:8443/oauth/meta/callback')
        self.session = ''
        status, headers, _ = self.form('/auth/login', {'username':'admin','password':self.fixture.config['panel_password']})
        self.assertEqual(status,303)
        self.session=headers['Set-Cookie'].split(';')[0]
        server.oauth_meta.store_token(server.DATA_DIR, {'business_id':'umdoislab','account_id':'11111111',
             'username':'umdoislab','verified_at':1,'access_token':'SYNTHETIC_PRIMARY_TOKEN_'*3})
        self.primary_token=(server.DATA_DIR/server.oauth_meta.TOKEN_FILENAME).read_bytes()
        self.primary_key=(server.DATA_DIR/server.oauth_meta.KEY_FILENAME).read_bytes()

    def tearDown(self):
        self.assertEqual((server.DATA_DIR/server.oauth_meta.TOKEN_FILENAME).read_bytes(),self.primary_token)
        self.assertEqual((server.DATA_DIR/server.oauth_meta.KEY_FILENAME).read_bytes(),self.primary_key)
        self.fixture.tearDown()

    def request(self,path,method='GET',body=None,headers=None,authenticated=True):
        default={'Host':'central.test:8443','X-Forwarded-Proto':'https'}
        if authenticated and self.session:default['Cookie']=self.session
        return self.fixture.request(path,method,body,{**default,**(headers or {})})

    def form(self,path,data,**kwargs):
        return self.request(path,'POST',urlencode(data),{'Content-Type':'application/x-www-form-urlencoded'},**kwargs)

    def create(self,username,name='Account'):
        page=self.request('/accounts')[2].decode()
        token=re.search(r'name="csrf" value="([a-f0-9]{64})"',page).group(1)
        status,headers,_=self.form('/accounts',{'username':username,'display_name':name,'csrf':token})
        self.assertEqual(status,303)
        path=headers['Location'].removesuffix('/panel')
        return path,path.split('/')[2]

    def csrf(self,path):
        status,_,body=self.request(path+'/editorial/api/csrf')
        self.assertEqual(status,200)
        return json.loads(body)

    def test_registration_requires_session_and_csrf_and_does_not_duplicate_identity(self):
        self.assertEqual(self.request('/accounts',authenticated=False)[0],403)
        self.assertEqual(self.request('/accounts',headers=self.fixture.admin_header(),authenticated=False)[0],403)
        self.assertEqual(self.form('/accounts',{'username':'one','display_name':'One','csrf':'0'*64})[0],403)
        self.fixture.config['extra_integration_secret']='SYNTHETIC_NOT_INHERITED'
        path,business=self.create('@second_review','<script>unsafe</script>')
        other_cfg=server.meta_configuration_for_business(business)
        self.assertNotIn('extra_integration_secret',other_cfg)
        self.assertEqual(other_cfg['bridge_secret'],'')
        self.assertEqual(other_cfg['meta_verify_token'],'')
        self.assertEqual(other_cfg['meta_app_secret'],self.fixture.config['meta_app_secret'])
        page=self.request('/accounts')[2]
        self.assertIn(b'&lt;script&gt;unsafe&lt;/script&gt;',page)
        self.assertNotIn(b'<script>unsafe',page)
        token=re.search(rb'name="csrf" value="([a-f0-9]{64})"',page).group(1).decode()
        self.assertEqual(self.form('/accounts',{'username':'SECOND_REVIEW','display_name':'Duplicate','csrf':token})[0],409)
        with server.database() as conn:
            account=account_registry.operational_account(conn,business)
            self.assertIsNone(account['instagram_account_id'])
            self.assertEqual(len(account_registry.administrative_accounts(conn)),2)
        self.assertIn(b'@second_review',self.request(path+'/panel')[2])
        self.assertFalse(server.connection_summary(server.meta_configuration_for_business(business))['webhookEnabled'])

    def test_legacy_secondary_unknown_and_private_paths_stay_closed(self):
        with server.database() as conn:
            account_registry.register(conn,'internal_only','22222222','internal_only','Internal',enabled=True)
        self.assertEqual(self.request('/accounts/internal_only/panel')[0],404)
        self.assertNotIn(b'Internal',self.request('/accounts')[2])
        path,_=self.create('other')
        for suffix in ('/health','/bridge/pending','/webhook/instagram','/oauth/meta/callback?state=x','/auth/login'):
            self.assertEqual(self.request(path+suffix)[0],404)
        self.assertEqual(self.request(path+'/panel',authenticated=False)[0],403)
        self.assertEqual(self.request('/accounts/not_registered/panel')[0],404)

    def test_messages_and_handoff_are_bound_to_the_account_path(self):
        a,aid=self.create('first_review');b,bid=self.create('second_review')
        with server.database() as conn:
            for business,ig,user,text in ((aid,'22222222','first_review','ONLY FIRST'),(bid,'33333333','second_review','ONLY SECOND')):
                account_registry.bind_verified(conn,business,ig,user)
                conn.execute('INSERT INTO inbound(recipient_id,sender_id,message_id,message_text,received_at) VALUES (?,?,?,?,?)',
                             (ig,'same-sender','same-mid',text,'2026-11-21T00:00:00Z'))
        self.assertIn(b'ONLY FIRST',self.request(a+'/panel')[2]);self.assertNotIn(b'ONLY SECOND',self.request(a+'/panel')[2])
        self.assertIn(b'ONLY SECOND',self.request(b+'/panel')[2]);self.assertNotIn(b'ONLY FIRST',self.request(b+'/panel')[2])
        token=server.token_for('33333333','same-sender','human',self.fixture.config['panel_password'])
        self.assertEqual(self.form(a+'/panel/handoff',{'accountId':'33333333','senderId':'same-sender','state':'human','csrf':token})[0],403)
        self.assertEqual(self.form('/panel/handoff',{'accountId':'33333333','senderId':'same-sender','state':'human','csrf':token})[0],403)
        token=server.token_for('22222222','same-sender','human',self.fixture.config['panel_password'])
        self.assertEqual(self.form(a+'/panel/handoff',{'accountId':'22222222','senderId':'same-sender','state':'human','csrf':token})[0],303)
        with server.database() as conn:
            self.assertEqual(conn.execute('SELECT recipient_id FROM handoff').fetchall(),[('22222222',)])

    def test_editorial_media_and_csrf_do_not_cross_accounts(self):
        a,_=self.create('first_review');b,_=self.create('second_review')
        ca,cb=self.csrf(a),self.csrf(b)
        self.assertNotEqual(ca['upload'],cb['upload'])
        content=io.BytesIO();Image.new('RGB',(3,3),'blue').save(content,format='PNG')
        raw=content.getvalue()
        status,_,body=self.request(a+'/editorial/api/media','POST',raw,{'Content-Type':'image/png','X-CSRF-Token':ca['upload']})
        self.assertEqual(status,201);mid=json.loads(body)['id']
        self.assertEqual(self.request(b+'/editorial/api/media','POST',raw,{'Content-Type':'image/png','X-CSRF-Token':ca['upload']})[0],403)
        self.assertEqual(self.request(a+'/editorial/media/'+mid)[0],200)
        self.assertEqual(self.request(b+'/editorial/media/'+mid)[0],422)
        self.assertEqual(self.request('/editorial/media/'+mid)[0],422)
        self.assertEqual(json.loads(self.request(b+'/editorial/api/state')[2])['media'],[])
        self.assertNotIn(b'@umdoislab',self.request(a+'/editorial/')[2])

    def test_two_oauth_returns_resolve_their_original_accounts_and_preserve_primary(self):
        a,aid=self.create('first_review');b,bid=self.create('second_review')
        states=[];cookies=[]
        for path in (a,b):
            status,headers,_=self.request(path+'/oauth/meta/start')
            self.assertEqual(status,302)
            states.append(parse_qs(urlsplit(headers['Location']).query)['state'][0])
            cookies.append(headers['Set-Cookie'].split(';')[0])
        def identity(cfg,token):
            return {'business_id':cfg['business_id'],'account_id':'22222222' if cfg['business_id']==aid else '33333333',
                    'username':cfg['instagram_expected_username'],'client_business_id':'44444444','verified_at':1}
        def finish(state):
            status,_,body=self.request('/oauth/meta/callback?'+urlencode({'state':state,'code':'SYNTHETIC_CODE'}),headers={'Cookie':'; '.join(cookies)})
            if status==200:self.assertIn(((a if state==states[0] else b)+'/panel').encode(),body)
            return status
        with patch.object(server.oauth_meta,'exchange_code',return_value={'access_token':'SYNTHETIC_OTHER_TOKEN_'*3}), \
             patch.object(server.instagram_connection,'verify_access',side_effect=identity):
            with ThreadPoolExecutor(max_workers=2) as pool:
                self.assertEqual(list(pool.map(finish,reversed(states))),[200,200])
            self.assertEqual(finish(states[0]),400)
        for business,ig in ((aid,'22222222'),(bid,'33333333')):
            token=server._meta_credential(business)
            self.assertEqual(token['business_id'],business);self.assertEqual(token['account_id'],ig)
            self.assertTrue(server.connection_summary(server.meta_configuration_for_business(business))['accountVerified'])
        self.assertEqual(self.request(a+'/oauth/meta/callback?state=x&code=x')[0],404)
        self.assertNotEqual(account_registry.credential_root(server.DATA_DIR,aid),account_registry.credential_root(server.DATA_DIR,bid))

    def test_wrong_identity_cannot_bind_or_store_a_secondary_credential(self):
        path,business=self.create('first_review')
        _,headers,_=self.request(path+'/oauth/meta/start')
        state=parse_qs(urlsplit(headers['Location']).query)['state'][0]
        with patch.object(server.oauth_meta,'exchange_code',return_value={'access_token':'SYNTHETIC_OTHER_TOKEN_'*3}), \
             patch.object(server.instagram_connection,'verify_access',side_effect=instagram_connection.ConnectionError('Expected Instagram account was not granted')):
            status,_,_=self.request('/oauth/meta/callback?'+urlencode({'state':state,'code':'SYNTHETIC_CODE'}),headers={'Cookie':headers['Set-Cookie'].split(';')[0]})
        self.assertEqual(status,502)
        with server.database() as conn:self.assertIsNone(account_registry.operational_account(conn,business)['instagram_account_id'])
        self.assertIsNone(server._meta_credential(business))

    def test_simultaneous_registration_does_not_create_duplicate_usernames(self):
        token=panel_login.admin_csrf_token(self.session,self.fixture.config['panel_password'],'accounts:create')
        def register(_):return self.form('/accounts',{'username':'same_review','display_name':'Same','csrf':token})[0]
        with ThreadPoolExecutor(max_workers=2) as pool:self.assertEqual(sorted(pool.map(register,range(2))),[303,409])
        with server.database() as conn:self.assertEqual(len(account_registry.administrative_accounts(conn)),2)

    def test_meta_action_csrf_is_scoped_and_no_credential_fallback_occurs(self):
        path,business=self.create('first_review')
        primary_csrf=panel_login.admin_csrf_token(self.session,self.fixture.config['panel_password'],'check')
        secondary_csrf=panel_login.admin_csrf_token(self.session,self.fixture.config['panel_password'],'meta:'+business+':check')
        with patch.object(server.instagram_connection,'verify_access') as verify:
            self.assertEqual(self.form(path+'/panel/meta/check',{'csrf':primary_csrf})[0],403)
            self.assertEqual(self.form(path+'/panel/meta/check',{'csrf':secondary_csrf})[0],422)
            verify.assert_not_called()
        self.assertIsNone(server._meta_credential(business))
        with server.database() as conn:account_registry.bind_verified(conn,business,'22222222','first_review')
        root=account_registry.credential_root(server.DATA_DIR,business)
        credential={'business_id':business,'account_id':'22222222','username':'first_review','verified_at':1,'access_token':'SYNTHETIC_SCOPED_TOKEN_'*3}
        server.oauth_meta.store_token(root,credential)
        with patch.object(server.instagram_connection,'verify_access',return_value={'account_id':'22222222','username':'first_review','verified_at':2}) as verify:
            status,headers,_=self.form(path+'/panel/meta/check',{'csrf':secondary_csrf})
            self.assertEqual(status,303)
            self.assertEqual(headers['Location'],path+'/panel')
            self.assertEqual(verify.call_args.args[0]['business_id'],business)

    def test_callback_cannot_be_retargeted_by_query_and_disabled_account_is_refused(self):
        path,business=self.create('first_review')
        _,headers,_=self.request(path+'/oauth/meta/start')
        state=parse_qs(urlsplit(headers['Location']).query)['state'][0]
        query=urlencode({'state':state,'code':'SYNTHETIC_CODE','business_id':'umdoislab'})
        with patch.object(server.oauth_meta,'exchange_code') as exchange:
            self.assertEqual(self.request('/oauth/meta/callback?'+query,headers={'Cookie':headers['Set-Cookie'].split(';')[0]})[0],400)
            with server.database() as conn:conn.execute('UPDATE instagram_accounts SET enabled=0 WHERE business_id=?',(business,))
            query=urlencode({'state':state,'code':'SYNTHETIC_CODE'})
            self.assertEqual(self.request('/oauth/meta/callback?'+query,headers={'Cookie':headers['Set-Cookie'].split(';')[0]})[0],502)
            exchange.assert_not_called()

    def test_verified_mapping_cannot_take_primary_id_or_be_silently_changed(self):
        _,business=self.create('first_review')
        with server.database() as conn:
            with self.assertRaises(account_registry.RegistryError):account_registry.bind_verified(conn,business,'11111111','first_review')
            account_registry.bind_verified(conn,business,'22222222','first_review')
            with self.assertRaises(account_registry.RegistryError):account_registry.bind_verified(conn,business,'33333333','first_review')
        self.assertEqual(server.meta_configuration_for_business(business)['instagram_account_id'],'22222222')


class AssignedAccountsPagination(unittest.TestCase):
    def cfg(self):
        return {'instagram_account_id':None,'instagram_expected_username':'wanted_review','allow_account_discovery':True,
                'meta_graph_version':'v27.0','business_id':'ig_review'}

    def test_discovery_uses_cursor_and_exact_username_not_first_account(self):
        responses=[{'data':[{'id':'11111111','username':'other'}],'paging':{'cursors':{'after':'SYNTHETIC_CURSOR'}}},
                   {'data':[{'id':'22222222','username':'wanted_review'}]}, {'client_business_id':'33333333'}]
        with patch.object(instagram_connection,'request_graph',side_effect=responses) as graph:
            identity=instagram_connection.verify_access(self.cfg(),'SYNTHETIC_TOKEN_'*3)
            self.assertEqual(identity['account_id'],'22222222')
            self.assertEqual(graph.call_args_list[1].kwargs['fields']['after'],'SYNTHETIC_CURSOR')

    def test_pagination_repetition_or_incomplete_results_fail_closed(self):
        page={'data':[{'id':'22222222','username':'wanted_review'}],'paging':{'cursors':{'after':'SYNTHETIC_CURSOR'}}}
        with patch.object(instagram_connection,'request_graph',return_value=page):
            with self.assertRaises(instagram_connection.ConnectionError):instagram_connection.verify_access(self.cfg(),'SYNTHETIC_TOKEN_'*3)
        page={'data':[{'id':'22222222','username':'wanted_review'}],'paging':{'next':'https://untrusted.invalid'}}
        with patch.object(instagram_connection,'request_graph',return_value=page):
            with self.assertRaises(instagram_connection.ConnectionError):instagram_connection.verify_access(self.cfg(),'SYNTHETIC_TOKEN_'*3)

    def test_unprovisioned_missing_id_cannot_discover(self):
        cfg=self.cfg();cfg.pop('allow_account_discovery')
        with patch.object(instagram_connection,'request_graph') as graph:
            with self.assertRaises(instagram_connection.ConnectionError):instagram_connection.verify_access(cfg,'SYNTHETIC_TOKEN_'*3)
            graph.assert_not_called()


class AccountRegistryMigration(unittest.TestCase):
    def test_additive_upgrade_preserves_records_and_keeps_legacy_secondaries_nonoperational(self):
        import sqlite3
        conn=sqlite3.connect(':memory:')
        try:
            conn.execute('''CREATE TABLE instagram_accounts (business_id TEXT PRIMARY KEY,
              instagram_account_id TEXT UNIQUE,username TEXT NOT NULL,display_name TEXT NOT NULL,
              enabled INTEGER NOT NULL,connection_state TEXT DEFAULT 'pending',
              permissions_json TEXT DEFAULT '[]',created_at TEXT DEFAULT CURRENT_TIMESTAMP)''')
            conn.execute("INSERT INTO instagram_accounts(business_id,instagram_account_id,username,display_name,enabled) VALUES ('umdoislab','11111111','umdoislab','Umdoislab',1)")
            conn.execute("INSERT INTO instagram_accounts(business_id,instagram_account_id,username,display_name,enabled) VALUES ('legacy_other','22222222','legacy_other','Legacy',1)")
            conn.commit()
            account_registry.prepare(conn);account_registry.prepare(conn)
            self.assertEqual(conn.execute('SELECT business_id,instagram_account_id FROM instagram_accounts ORDER BY business_id').fetchall(),[('legacy_other','22222222'),('umdoislab','11111111')])
            self.assertEqual([a['business_id'] for a in account_registry.administrative_accounts(conn)],['umdoislab'])
            with self.assertRaises(account_registry.RegistryError):account_registry.operational_account(conn,'legacy_other')
        finally:conn.close()
