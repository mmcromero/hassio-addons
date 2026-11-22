"""Bounded conversation metadata and action-scoped read-only HTTP checks."""
import io
import json
import unittest
from urllib.parse import urlencode, urlsplit, parse_qs
from unittest.mock import patch
import instagram_connection as ic
import panel_login
import account_registry
from test_receiving_diagnostics import CFG, CREDENTIAL, ReceivingHTTP


class RoutingMetadata(unittest.TestCase):
    def read(self, value):
        with patch.object(ic,'request_graph',return_value=value) as graph:
            result=ic.diagnose_conversation_routing(CFG,CREDENTIAL)
        graph.assert_called_once_with('v27.0','/11111111/conversations',CREDENTIAL['access_token'],
                                      fields=ic.ROUTING_FIELDS,timeout=5)
        return result

    def test_one_get_returns_counts_and_activity_without_identifiers_or_content(self):
        report=self.read({'data':[
            {'id':'PRIVATE_A','is_owner':True,'updated_time':'2026-11-21T23:00:00-03:00','messages':'PRIVATE_TEXT'},
            {'id':'PRIVATE_B','is_owner':False,'updated_time':'2026-11-22T05:41:00-03:00','participants':'PRIVATE_PERSON'},
            {'id':'PRIVATE_C'}], 'paging':{'next':'https://PRIVATE_PAGING'}})
        self.assertEqual(report['status'],'confirmed')
        self.assertEqual([report[k] for k in ('sample_count','owned','other','unspecified')],[3,1,1,1])
        from datetime import datetime
        self.assertEqual(report['latest_activity'],int(datetime.fromisoformat('2026-11-22T05:41:00-03:00').timestamp()))
        self.assertNotIn('PRIVATE',json.dumps(report));self.assertNotIn(CREDENTIAL['access_token'],json.dumps(report))

    def test_missing_owner_and_empty_sample_are_not_claimed_to_be_other_owned(self):
        report=self.read({'data':[{'id':'PRIVATE'}]})
        self.assertEqual(report['unspecified'],1);self.assertEqual(report['other'],0)
        self.assertIsNone(report['latest_activity'])
        self.assertEqual(self.read({'data':[]})['sample_count'],0)

    def test_invalid_provider_shapes_and_dates_do_not_return_false_counts(self):
        for value in ({'data':None},{'data':[{'id':'a'}]*6},{'data':[{'id':False}]},
                      {'data':[{'id':'a','is_owner':1}]},{'data':[{'id':'a','updated_time':'2026-11-22T05:41:00'}]},
                      {'data':[{'id':'a','updated_time':'9999-12-31T00:00:00Z'}]}):
            report=self.read(value)
            self.assertEqual(report['status'],'error');self.assertEqual(report['reason'],'invalid_response')
            self.assertNotIn('sample_count',report)

    def test_wrong_context_prevents_request_and_provider_errors_are_sanitized(self):
        for credential in (None,{**CREDENTIAL,'business_id':'other'},{**CREDENTIAL,'account_id':'22222222'}):
            with patch.object(ic,'request_graph') as graph:
                self.assertEqual(ic.diagnose_conversation_routing(CFG,credential)['reason'],'configuration_incomplete')
            graph.assert_not_called()
        with patch.object(ic,'request_graph',side_effect=ic.GraphError('unsupported_request',400,100)):
            result=ic.diagnose_conversation_routing(CFG,CREDENTIAL)
        self.assertEqual(result['provider_code'],100);self.assertNotIn('owned',result)

    def test_transport_is_get_only_and_cannot_expand_to_text_or_participants(self):
        observed=[]
        def opener(req,timeout):observed.append(req);return io.BytesIO(b'{"data":[]}')
        ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],fields=dict(ic.ROUTING_FIELDS),opener=opener,timeout=5)
        self.assertEqual(len(observed),1)
        self.assertEqual(parse_qs(urlsplit(observed[0].full_url).query)['fields'],['id,is_owner,updated_time'])
        self.assertIsNone(observed[0].data);self.assertNotIn(CREDENTIAL['access_token'],observed[0].full_url)
        for method,fields in (('POST',ic.ROUTING_FIELDS),('DELETE',ic.ROUTING_FIELDS),
                              ('GET',{**ic.ROUTING_FIELDS,'fields':'id,messages,participants'}),
                              ('GET',{**ic.ROUTING_FIELDS,'limit':'100'})):
            with self.assertRaises(ic.ConnectionError):
                ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],method,fields,opener=opener)
        self.assertEqual(len(observed),1)


class RoutingHTTP(unittest.TestCase):
    def setUp(self):
        self.fixture=ReceivingHTTP();self.fixture.setUp();self.addCleanup(self.fixture.tearDown)
        self.server=self.fixture.server

    def call(self, *, path='/panel/meta/check', scope='routing', session=True, diagnostic='routing'):
        action=scope if path.startswith('/panel') else 'meta:'+path.split('/')[2]+':'+scope
        token=panel_login.admin_csrf_token(self.fixture.session,self.fixture.fixture.config['panel_password'],action)
        headers={**self.fixture.headers,'X-Meta-Diagnostic':diagnostic}
        if not session:headers.pop('Cookie')
        return self.fixture.fixture.request(path,'POST',urlencode({'csrf':token}),headers)

    def test_reads_once_without_other_checks_credential_writes_or_message_storage(self):
        token_path=self.server.DATA_DIR/self.server.oauth_meta.TOKEN_FILENAME
        before=token_path.read_bytes()
        with patch.object(ic,'request_graph',return_value={'data':[{'id':'PRIVATE','is_owner':False}]}) as graph, \
             patch.object(ic,'verify_access') as verify,patch.object(ic,'diagnose_receiving') as other, \
             patch.object(ic,'subscribe_messages') as subscribe:
            status,_,body=self.call()
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['other'],1)
        graph.assert_called_once();verify.assert_not_called();other.assert_not_called();subscribe.assert_not_called()
        self.assertNotIn(b'PRIVATE',body);self.assertEqual(token_path.read_bytes(),before)
        with self.server.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],0)

    def test_action_csrf_session_and_headers_fail_before_meta(self):
        with patch.object(ic,'request_graph') as graph:
            self.assertEqual(self.call(scope='check')[0],403)
            self.assertEqual(self.call(session=False)[0],403)
            self.assertEqual(self.call(diagnostic='unsupported')[0],400)
            self.assertEqual(self.call(path='/panel/meta/subscribe')[0],400)
        graph.assert_not_called()

    def test_secondary_context_requires_own_csrf_and_credential(self):
        with self.server.database() as db:
            business=account_registry.provision(db,'second_review','Second')
            account_registry.bind_verified(db,business,'22222222','second_review')
        root=account_registry.credential_root(self.server.DATA_DIR,business)
        credential={**CREDENTIAL,'business_id':business,'account_id':'22222222','username':'second_review'}
        self.server.oauth_meta.store_token(root,credential)
        path='/accounts/'+business+'/panel/meta/check'
        with patch.object(ic,'request_graph',return_value={'data':[]}) as graph:
            self.assertEqual(self.call(path=path)[0],200)
        self.assertEqual(graph.call_args.args[1],'/22222222/conversations')
        token=panel_login.admin_csrf_token(self.fixture.session,self.fixture.fixture.config['panel_password'],'routing')
        with patch.object(ic,'request_graph') as graph:
            status=self.fixture.fixture.request(path,'POST',urlencode({'csrf':token}),
                {**self.fixture.headers,'X-Meta-Diagnostic':'routing'})[0]
        self.assertEqual(status,403);graph.assert_not_called()

    def test_only_settings_exposes_button_without_querying_meta_on_visit(self):
        with patch.object(ic,'request_graph') as graph:
            for path in ('/panel','/editorial/'):
                self.assertNotIn(b'id="check-routing"',self.fixture.fixture.request(path,headers=self.fixture.headers)[2])
            status,_,body=self.fixture.fixture.request('/panel?view=settings',headers=self.fixture.headers)
        self.assertEqual(status,200);self.assertIn(b'id="check-routing"',body)
        self.assertNotIn(b'data-routing-csrf=""',body);graph.assert_not_called()
