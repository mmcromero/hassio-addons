"""Read-only receiving audit: provider contracts, privacy and visible HTTP results."""
import io
import json
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlencode, urlsplit
from unittest.mock import patch
import instagram_connection as ic
import panel_login
import test_http as contracts


CFG = {'instagram_account_id':'11111111','meta_app_id':'12345678',
       'business_id':'umdoislab','instagram_expected_username':'umdoislab',
       'meta_graph_version':'v27.0'}
CREDENTIAL = {'business_id':'umdoislab','account_id':'11111111','username':'umdoislab',
              'verified_at':1,'access_token':'SYNTHETIC_PRIVATE_TOKEN_'*3}
GOOD = {'checked_at':1795302000,'subscription':{'status':'confirmed','messages':True},
        'conversations':{'status':'confirmed','conversation_found':True}}


class ReceivingContracts(unittest.TestCase):
    def diagnose(self, subscription, conversations=None):
        with patch.object(ic,'request_graph',side_effect=[subscription, conversations or {'data':[]}]) as graph:
            result=ic.diagnose_receiving(CFG,CREDENTIAL)
        self.assertEqual(graph.call_count,2)
        for call in graph.call_args_list:
            self.assertEqual(call.args[0],'v27.0')
            self.assertEqual(call.args[2],CREDENTIAL['access_token'])
            self.assertEqual(call.kwargs.get('method','GET'),'GET')
            self.assertEqual(call.kwargs['timeout'],5)
        self.assertEqual(graph.call_args_list[0].args[1],'/11111111/subscribed_apps')
        self.assertEqual(graph.call_args_list[0].kwargs['fields'],{'fields':'app_id,subscribed_fields','limit':'100'})
        self.assertEqual(graph.call_args_list[1].kwargs['fields'],{'platform':'instagram','fields':'id','limit':'1'})
        return result

    def test_exact_app_id_messages_and_id_only_conversations(self):
        report=self.diagnose({'data':[
            {'app_id':'87654321','subscribed_fields':['messages']},
            {'app_id':'12345678','subscribed_fields':['comments','messages']}]},
            {'data':[{'id':'PRIVATE_CONVERSATION_ID','messages':{'data':['PRIVATE_TEXT']}}]})
        self.assertEqual(report['subscription'],{'status':'confirmed','messages':True})
        self.assertEqual(report['conversations'],{'status':'confirmed','conversation_found':True})
        for secret in ('PRIVATE_CONVERSATION','PRIVATE_TEXT','87654321',CREDENTIAL['access_token']):
            self.assertNotIn(secret,json.dumps(report))

    def test_unrelated_app_is_not_our_subscription(self):
        result=self.diagnose({'data':[{'app_id':'87654321','subscribed_fields':['messages']}]})
        self.assertEqual(result['subscription'],{'status':'absent'})
        self.assertEqual(result['conversations'],{'status':'confirmed','conversation_found':False})

    def test_existing_app_without_messages_is_reported(self):
        result=self.diagnose({'data':[{'app_id':'12345678','subscribed_fields':['comments']}]})
        self.assertEqual(result['subscription'],{'status':'confirmed','messages':False})

    def test_incomplete_or_malformed_list_cannot_prove_absence(self):
        for payload in ({'data':[],'paging':{'next':'https://untrusted.test/?token=PRIVATE'}},
                        {'data':[],'paging':[]},{'data':[{'id':'12345678'}]}, {'data':[None]}):
            with self.subTest(payload=payload):
                self.assertEqual(self.diagnose(payload)['subscription']['status'],'unknown')

    def test_invalid_or_duplicate_results_fail_closed(self):
        for payload in ({'data':{}},{'data':[{}]*101},
                        {'data':[{'app_id':'12345678','subscribed_fields':'messages'}]},
                        {'data':[{'app_id':'12345678','subscribed_fields':['messages']}]*2}):
            with self.subTest(payload=payload):
                self.assertEqual(self.diagnose(payload)['subscription']['reason'],'invalid_response')
        for payload in ({'data':[{}]},{'data':[{'id':'a'},{'id':'b'}]}):
            self.assertEqual(self.diagnose({'data':[]},payload)['conversations']['reason'],'invalid_response')

    def test_business_account_username_and_verification_binding_before_network(self):
        for changed in ({'business_id':'other'},{'account_id':'22222222'},{'username':'other'},
                        {'verified_at':0}):
            with patch.object(ic,'request_graph') as graph:
                result=ic.diagnose_receiving(CFG,{**CREDENTIAL,**changed})
                graph.assert_not_called()
                self.assertEqual(result['subscription']['reason'],'configuration_incomplete')

    def test_provider_errors_are_independent_and_sanitized(self):
        with patch.object(ic,'request_graph',side_effect=[ic.GraphError('permission_denied',403,200,99),{'data':[]}]):
            result=ic.diagnose_receiving(CFG,CREDENTIAL)
        self.assertEqual(result['subscription']['provider_code'],200)
        self.assertEqual(result['conversations']['status'],'confirmed')

    def test_output_allowlist_for_untrusted_stored_reports(self):
        report={**GOOD,'token':'SECRET','subscription':{'status':'error','reason':['SECRET'],
            'provider_code':True,'provider_subcode':-1,'http_status':403,'message':'<script>SECRET</script>'}}
        clean=ic.safe_diagnostics(report)
        self.assertEqual(clean['subscription'],{'status':'error','http_status':403})
        self.assertNotIn('SECRET',json.dumps(clean))
        for invalid in (None,{}, {'checked_at':True}, {'checked_at':2**63}):
            self.assertIsNone(ic.safe_diagnostics(invalid))

    def test_graph_uses_fixed_host_bearer_and_content_free_get(self):
        observed=[]
        def opener(req,timeout):
            observed.append((req,timeout));return io.BytesIO(b'{"data":[]}')
        fields={'platform':'instagram','fields':'id','limit':'1'}
        ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],fields=fields,opener=opener,timeout=5)
        req,timeout=observed[0]
        self.assertEqual(urlsplit(req.full_url).netloc,'graph.facebook.com')
        self.assertEqual(parse_qs(urlsplit(req.full_url).query),{key:[value] for key,value in fields.items()})
        self.assertEqual(req.get_header('Authorization'),'Bearer '+CREDENTIAL['access_token'])
        self.assertNotIn(CREDENTIAL['access_token'],req.full_url)
        self.assertIsNone(req.data)
        self.assertEqual(timeout,5)
        for path,method,params in (('/11111111/conversations','POST',fields),
            ('/11111111/conversations','GET',{'fields':'messages'}),('/11111111/messages','GET',{}),
            ('https://untrusted.test','GET',{})):
            with self.assertRaises(ic.ConnectionError):
                ic.request_graph('v27.0',path,CREDENTIAL['access_token'],method,params,opener=opener)
        self.assertEqual(len(observed),1)

    def test_http_error_categories_never_include_provider_message_url_or_token(self):
        for code,message,reason in ((190,'PRIVATE token','token_invalid'),(200,'PRIVATE','permission_denied'),
            (200,'The account owner has disabled access to instagram messages. PRIVATE','message_access_disabled'),
            (100,'PRIVATE','unsupported_request'),(1,'PRIVATE','provider_error')):
            body=io.BytesIO(json.dumps({'error':{'code':code,'error_subcode':42,'message':message}}).encode())
            def opener(req,timeout):raise HTTPError('https://PRIVATE/?token=SECRET',400,'PRIVATE',{},body)
            with self.assertRaises(ic.GraphError) as raised:
                ic.request_graph('v27.0','/me',CREDENTIAL['access_token'],opener=opener)
            self.assertTrue(body.closed)
            self.assertEqual(raised.exception.details,{'reason':reason,'http_status':400,'provider_code':code,'provider_subcode':42})
            self.assertNotIn('PRIVATE',str(raised.exception)+repr(raised.exception.details))

    def test_invalid_and_transport_responses_are_sanitized(self):
        for raw in (b'not json PRIVATE',b'[]',b'x'*(ic.MAX_GRAPH_RESPONSE+1)):
            with self.assertRaises(ic.GraphError):
                ic.request_graph('v27.0','/me',CREDENTIAL['access_token'],opener=lambda *args,**kw:io.BytesIO(raw))
        def opener(*args,**kwargs):raise OSError('PRIVATE_NETWORK_DETAILS')
        with self.assertRaises(ic.GraphError) as raised:
            ic.request_graph('v27.0','/me',CREDENTIAL['access_token'],opener=opener)
        self.assertEqual(raised.exception.details['reason'],'transport_error')
        self.assertNotIn('PRIVATE',str(raised.exception))


class ReceivingHTTP(unittest.TestCase):
    def setUp(self):
        self.fixture=contracts.HTTPContractTests();self.fixture.setUp();self.fixture.configure_oauth()
        self.server=contracts.server
        self.fixture.config.update(CFG,meta_verify_token='SYNTHETIC_VERIFY_TOKEN_'*2)
        status,headers,_=self.fixture.request('/auth/login','POST',urlencode({
            'username':'admin','password':self.fixture.config['panel_password']}),
            {'Content-Type':'application/x-www-form-urlencoded'})
        self.assertEqual(status,303)
        self.session=headers['Set-Cookie'].split(';')[0]
        self.headers={'Cookie':self.session,'Content-Type':'application/x-www-form-urlencoded'}
        self.server.oauth_meta.store_token(self.server.DATA_DIR,CREDENTIAL)

    def tearDown(self):self.fixture.tearDown()

    def action(self,kind,csrf=None):
        csrf=csrf or panel_login.admin_csrf_token(self.session,self.fixture.config['panel_password'],kind)
        return self.fixture.request('/panel/meta/'+kind,'POST',urlencode({'csrf':csrf}),self.headers)

    def test_check_stores_safe_evidence_and_get_only_renders_it(self):
        identity={key:CREDENTIAL[key] for key in ('business_id','account_id','username','verified_at')}
        with patch.object(ic,'verify_access',return_value=identity), patch.object(ic,'diagnose_receiving',return_value={**GOOD,'token':'SECRET'}), patch.object(ic,'subscribe_messages') as subscribe:
            with self.assertLogs(self.server.LOGGER,level='INFO') as logged:
                self.assertEqual(self.action('check')[0],303)
            subscribe.assert_not_called()
        with patch.object(ic,'request_graph') as graph:
            for _ in range(2):
                status,_,body=self.fixture.request('/panel',headers=self.headers)
                self.assertEqual(status,200)
                self.assertIn('campo messages presente.'.encode(),body)
                self.assertIn('Acesso aceito; há conversa visível'.encode(),body)
                self.assertIn(b'role="status"',body)
                self.assertIn(b'21/11/2026',body)
                self.assertNotIn(b'SECRET',body)
            graph.assert_not_called()
        saved=self.server._meta_credential()
        self.assertNotIn('token',saved['receiving_diagnostics'])
        self.assertNotIn(CREDENTIAL['access_token'],' '.join(logged.output))

    def test_error_result_is_visible_without_raw_provider_data(self):
        report={**GOOD,'conversations':{'status':'error','reason':'message_access_disabled',
            'http_status':403,'provider_code':200,'message':'PRIVATE_PROVIDER_TEXT'}}
        markup=self.server.render_meta_diagnostics({'receivingDiagnostics':report})
        self.assertIn('acesso externo às mensagens está desativado',markup)
        self.assertIn('HTTP=403, código Meta=200',markup)
        self.assertNotIn('PRIVATE',markup)

    def test_identity_failure_preserves_binding_and_shows_failed_read(self):
        report={**GOOD,'conversations':{'status':'error','reason':'token_invalid','provider_code':190}}
        with patch.object(ic,'verify_access',side_effect=ic.ConnectionError('PRIVATE_PROVIDER_TEXT')), patch.object(ic,'diagnose_receiving',return_value=report), patch.object(ic,'subscribe_messages') as subscribe:
            self.assertEqual(self.action('check')[0],303)
            subscribe.assert_not_called()
        saved=self.server._meta_credential()
        for key in CREDENTIAL:self.assertEqual(saved[key],CREDENTIAL[key])
        self.assertFalse(saved['last_meta_action']['identity_verified'])
        body=self.fixture.request('/panel',headers=self.headers)[2]
        self.assertIn('a verificação anterior não foi renovada'.encode(),body)
        self.assertIn('A Meta recusou o token salvo.'.encode(),body)
        self.assertNotIn(b'PRIVATE_PROVIDER_TEXT',body)

    def test_subscribe_has_visible_feedback_and_invalidates_stale_read(self):
        credential={**CREDENTIAL,'receiving_diagnostics':GOOD}
        self.server.oauth_meta.store_token(self.server.DATA_DIR,credential)
        with patch.object(ic,'subscribe_messages',return_value=2) as subscribe, patch.object(ic,'diagnose_receiving') as diagnose:
            self.assertEqual(self.action('subscribe')[0],303)
            subscribe.assert_called_once();diagnose.assert_not_called()
        saved=self.server._meta_credential()
        self.assertEqual(saved['subscribed_at'],2)
        self.assertNotIn('receiving_diagnostics',saved)
        body=self.fixture.request('/panel',headers=self.headers)[2]
        self.assertIn('A Meta aceitou o pedido de assinatura.'.encode(),body)

    def test_bad_csrf_and_missing_session_never_query_meta(self):
        with patch.object(ic,'verify_access') as verify,patch.object(ic,'diagnose_receiving') as diagnose:
            self.assertEqual(self.action('check','0'*64)[0],403)
            self.assertEqual(self.fixture.request('/panel/meta/check','POST',urlencode({'csrf':'0'*64}),{'Content-Type':'application/x-www-form-urlencoded'})[0],403)
            verify.assert_not_called();diagnose.assert_not_called()
