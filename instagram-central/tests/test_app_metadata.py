"""App/token reads cannot mutate subscriptions or expose private metadata."""
import io
import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch
import instagram_connection as ic
import test_receiving_diagnostics as receiving

CFG={**receiving.CFG,'meta_app_secret':'SYNTHETIC_APP_SECRET_PRIVATE'}
TOKEN=receiving.CREDENTIAL
VALID={'data':{'is_valid':True,'app_id':CFG['meta_app_id'],
               'scopes':['instagram_basic','instagram_manage_messages'],
               'user_id':'PRIVATE_USER','metadata':{'auth_nonce':'PRIVATE_NONCE'}}}
SUBS={'data':[{'object':'instagram','active':True,
               'fields':[{'name':'messages','version':'v27.0'}],
               'callback_url':'https://callback.test:8443/webhook/instagram?secret=PRIVATE_QUERY#PRIVATE_FRAGMENT'}]}


class AppMetadata(unittest.TestCase):
    def read(self, token=VALID, subscriptions=SUBS):
        with patch.object(ic,'request_graph',side_effect=[token,subscriptions]) as graph:
            result=ic.diagnose_app_metadata(CFG,TOKEN)
        self.assertEqual(graph.call_count,2)
        self.assertEqual([call.args[1] for call in graph.call_args_list],['/debug_token','/12345678/subscriptions'])
        for call in graph.call_args_list:
            self.assertEqual(call.args[2],'12345678|'+CFG['meta_app_secret'])
            self.assertEqual(call.kwargs.get('method','GET'),'GET')
            self.assertEqual(call.kwargs['timeout'],5)
        self.assertEqual(graph.call_args_list[0].kwargs['fields'],{'input_token':TOKEN['access_token']})
        self.assertNotIn('PRIVATE',json.dumps(result))
        self.assertNotIn(TOKEN['access_token'],json.dumps(result))
        return result

    def test_valid_token_exact_app_scopes_and_sanitized_callback(self):
        result=self.read()
        self.assertEqual(result['token_metadata'],{'status':'confirmed','token_is_valid':True,
            'app_matches':True,'basic_granted':True,'messages_granted':True})
        self.assertEqual(result['app_subscription'],{'status':'confirmed','active':True,'messages':True,
            'callback_origin':'https://callback.test:8443','callback_https':True,
            'callback_path_matches':True,'callback_extra':True})

    def test_invalid_token_and_omitted_fields_are_not_claimed_valid_or_granted(self):
        result=self.read({'data':{'is_valid':False}})
        self.assertEqual(result['token_metadata'],{'status':'confirmed','token_is_valid':False})
        result=self.read({'data':{'is_valid':True,'app_id':'87654321','scopes':['instagram_business_manage_messages']}})
        self.assertFalse(result['token_metadata']['app_matches'])
        self.assertFalse(result['token_metadata']['basic_granted'])
        self.assertFalse(result['token_metadata']['messages_granted'])

    def test_generic_edge_absence_does_not_prove_dashboard_subscription_absent(self):
        for payload in ({'data':[]},{'data':[{'object':'page','active':True,'fields':['messages']}]},
                        {'data':[],'paging':{'next':'https://PRIVATE'}}):
            with self.subTest(payload=payload):
                self.assertEqual(self.read(subscriptions=payload)['app_subscription'],
                    {'status':'unknown','reason':'app_subscription_not_exposed'})

    def test_string_field_list_inactive_wrong_path_and_http_are_explicit(self):
        result=self.read(subscriptions={'data':[{'object':'instagram','active':False,
            'fields':['comments'],'callback_url':'http://callback.test/PRIVATE_PATH'}]})
        value=result['app_subscription']
        self.assertFalse(value['active']);self.assertFalse(value['messages'])
        self.assertFalse(value['callback_https']);self.assertFalse(value['callback_path_matches'])

    def test_invalid_provider_structures_are_independent_errors(self):
        for token in ({'data':{}},{'data':{'is_valid':1}},{'data':{'is_valid':True,'scopes':'PRIVATE'}},
                      {'data':{'is_valid':True,'app_id':['PRIVATE']}}):
            result=self.read(token=token)
            self.assertEqual(result['token_metadata']['reason'],'invalid_response')
            self.assertEqual(result['app_subscription']['status'],'confirmed')
        for subscriptions in ({'data':None},{'data':SUBS['data']*2},
            {'data':[{'object':'instagram','active':1}]},
            {'data':[{'object':'instagram','fields':[42]}]},
            {'data':[{'object':'instagram','callback_url':'https://user:PRIVATE@callback.test/'}]}):
            result=self.read(subscriptions=subscriptions)
            self.assertEqual(result['app_subscription']['reason'],'invalid_response')
            self.assertEqual(result['token_metadata']['status'],'confirmed')

    def test_provider_error_does_not_skip_second_read(self):
        result=self.read(token=ic.GraphError('permission_denied',403,200))
        self.assertEqual(result['token_metadata']['provider_code'],200)
        self.assertEqual(result['app_subscription']['status'],'confirmed')

    def test_context_and_missing_app_secret_prevent_reads(self):
        for cfg,credential in (({**CFG,'meta_app_secret':''},TOKEN),
            (CFG,{**TOKEN,'business_id':'other'}),(CFG,{**TOKEN,'account_id':'22222222'}),
            (CFG,{**TOKEN,'username':'other'}),(CFG,{**TOKEN,'verified_at':0})):
            with patch.object(ic,'request_graph') as graph:
                result=ic.diagnose_app_metadata(cfg,credential)
            graph.assert_not_called()
            self.assertEqual(result['token_metadata']['reason'],'configuration_incomplete')

    def test_stored_metadata_allowlist_rejects_full_callback_and_untrusted_values(self):
        clean=ic.safe_diagnostics({**receiving.GOOD,'token_metadata':{'status':'confirmed',
            'token_is_valid':True,'scopes':['PRIVATE'],'user_id':'PRIVATE','access_token':'PRIVATE'},
            'app_subscription':{'status':'confirmed','callback_origin':'https://callback.test/?secret=PRIVATE',
                                'active':'PRIVATE','callback_url':'PRIVATE'}})
        self.assertEqual(clean['token_metadata'],{'status':'confirmed','token_is_valid':True})
        self.assertEqual(clean['app_subscription'],{'status':'confirmed'})
        self.assertNotIn('PRIVATE',json.dumps(clean))

    def test_new_graph_edges_are_get_only_and_fixed_fields(self):
        calls=[]
        def opener(req,timeout):calls.append(req);return io.BytesIO(b'{"data":{}}')
        for path,fields in (('/debug_token',{'input_token':TOKEN['access_token']}),('/12345678/subscriptions',None)):
            ic.request_graph('v27.0',path,'12345678|'+CFG['meta_app_secret'],fields=fields,opener=opener)
            for method in ('POST','DELETE'):
                with self.assertRaises(ic.ConnectionError):
                    ic.request_graph('v27.0',path,'12345678|'+CFG['meta_app_secret'],method=method,fields=fields,opener=opener)
        self.assertEqual(len(calls),2)
        self.assertEqual(parse_qs(urlsplit(calls[0].full_url).query),{'input_token':[TOKEN['access_token']]})
        for req in calls:
            self.assertEqual(urlsplit(req.full_url).netloc,'graph.facebook.com')
            self.assertNotIn(CFG['meta_app_secret'],req.full_url)
            self.assertEqual(req.get_header('Authorization'),'Bearer 12345678|'+CFG['meta_app_secret'])
        for path,fields in (('/debug_token',{}),('/debug_token',{'input_token':'x','fields':'PRIVATE'}),
                            ('/12345678/subscriptions',{'callback_url':'PRIVATE'})):
            with self.assertRaises(ic.ConnectionError):
                ic.request_graph('v27.0',path,TOKEN['access_token'],fields=fields,opener=opener)

    def test_default_transport_is_no_redirect_and_errors_hide_sensitive_query(self):
        error=HTTPError('https://graph.facebook.com/debug_token?input_token=PRIVATE',302,
                        'PRIVATE',{'Location':'https://PRIVATE'},io.BytesIO(b'PRIVATE'))
        with patch.object(ic,'_GRAPH_OPEN',side_effect=error) as transport:
            with self.assertRaises(ic.GraphError) as raised:
                ic.request_graph('v27.0','/debug_token','12345678|'+CFG['meta_app_secret'],
                                 fields={'input_token':TOKEN['access_token']})
        transport.assert_called_once()
        self.assertNotIn('PRIVATE',str(raised.exception)+str(raised.exception.details))

    def test_real_redirect_cannot_forward_authorization(self):
        visited=[]
        class Handler(BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                visited.append(self.path)
                self.send_response(302 if self.path=='/source' else 200)
                if self.path=='/source':self.send_header('Location','/target')
                self.send_header('Content-Length','0');self.end_headers()
        http=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=http.serve_forever,daemon=True);thread.start()
        try:
            req=Request('http://127.0.0.1:'+str(http.server_address[1])+'/source',
                        headers={'Authorization':'Bearer SYNTHETIC_SECRET'})
            with self.assertRaises(HTTPError) as raised:ic._GRAPH_OPEN(req,timeout=2)
            raised.exception.close()
            self.assertEqual(visited,['/source'])
        finally:http.shutdown();http.server_close();thread.join(timeout=3)

    def test_visible_output_does_not_claim_advanced_access_or_print_private_parts(self):
        report={**receiving.GOOD,**self.read()}
        html=receiving.contracts.server.render_meta_diagnostics({'receivingDiagnostics':report})
        self.assertIn('instagram_manage_messages: Sim',html)
        self.assertIn('Destino: https://callback.test:8443',html)
        self.assertIn('não informam o nível Standard ou Advanced Access',html)
        self.assertNotIn('PRIVATE',html)
