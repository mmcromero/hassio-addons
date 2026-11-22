"""Explicit Graph inbox reads, tenant storage, and genuine webhook promotion."""
import io
import json
import sqlite3
import unittest
from datetime import datetime
from urllib.parse import urlencode, parse_qs, urlsplit
from unittest.mock import patch
import instagram_connection as ic
import panel_login
import account_registry
import test_receiving_diagnostics as receiving

CFG = receiving.CFG
CREDENTIAL = receiving.CREDENTIAL


def message(mid='manual-mid', text='Texto sintético <script>not_script()</script>', sender='99999999', target='11111111'):
    return {'id':mid, 'message':text, 'created_time':'2026-11-21T23:00:00-03:00',
            'from':{'id':sender},'to':{'data':[{'id':target}]}}


def payload(*messages):
    return {'data':[{'id':'PRIVATE_CONVERSATION', 'messages':{'data':list(messages)}}]}


class ManualRead(unittest.TestCase):
    def test_opaque_long_message_ids_are_preserved_and_oversized_ids_are_specific(self):
        mid='encoded-message-id-'+('a'*300)
        with patch.object(ic,'request_graph',return_value=payload(message(mid=mid))):
            rows,_=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(rows[0][2],mid)
        for bad in ('x'*(ic.MAX_MESSAGE_ID+1), 'line\nbreak'):
            with patch.object(ic,'request_graph',return_value=payload(message(mid=bad))):
                with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
            self.assertEqual(caught.exception.details['reason'],'inbox_message_id_shape')

    def test_specific_schema_categories_never_include_provider_values(self):
        cases=[({'data':None},'inbox_conversations_shape'),
               (payload('PRIVATE'),'inbox_message_shape'),
               (payload({**message(),'created_time':'PRIVATE'}),'inbox_timestamp_shape')]
        for value,reason in cases:
            with patch.object(ic,'request_graph',return_value=value):
                with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
            self.assertEqual(caught.exception.details['reason'],reason)
            self.assertNotIn('PRIVATE',json.dumps(caught.exception.details))

    def test_one_fixed_get_filters_direction_and_media_without_following_paging(self):
        value=payload(message(),message(),message(mid='out',sender='11111111',target='99999999'),
                      message(mid='other',target='22222222'),message(mid='media',text=''))
        value['paging']={'next':'https://PRIVATE_PAGING/?access_token=PRIVATE'}
        with patch.object(ic,'request_graph',return_value=value) as graph:
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        graph.assert_called_once_with('v27.0','/11111111/conversations',CREDENTIAL['access_token'],fields=ic.INBOX_FIELDS,timeout=8)
        self.assertEqual(len(rows),1);self.assertEqual(rows[0][:3],('11111111','99999999','manual-mid'))
        self.assertEqual(rows[0][4],'2026-11-22T02:00:00+00:00')
        self.assertEqual((report['conversations'],report['scanned'],report['skipped'],report['limited']),(1,5,3,True))
        self.assertNotIn('PRIVATE',json.dumps(report));self.assertNotIn(CREDENTIAL['access_token'],json.dumps(report))

    def test_invalid_binding_or_provider_shapes_cannot_produce_partial_results(self):
        for credential in (None,{**CREDENTIAL,'account_id':'22222222'},{**CREDENTIAL,'business_id':'other'}):
            with patch.object(ic,'request_graph') as graph:
                with self.assertRaises(ic.GraphError):ic.read_recent_inbox(CFG,credential)
            graph.assert_not_called()
        bad=message();bad['created_time']='2026-11-22T00:00:00'
        for value in ({'data':[{}]*6},payload(message(),bad),{'data':[{'id':'a'}]},payload({'id':'a'})):
            with patch.object(ic,'request_graph',return_value=value):
                with self.assertRaises(ic.GraphError):ic.read_recent_inbox(CFG,CREDENTIAL)

    def test_transport_allows_only_exact_bounded_manual_fields_and_no_post(self):
        seen=[]
        def opener(request,timeout):seen.append(request);return io.BytesIO(b'{"data":[]}')
        ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],fields=ic.INBOX_FIELDS,opener=opener)
        self.assertEqual(len(seen),1);self.assertIsNone(seen[0].data)
        self.assertEqual(parse_qs(urlsplit(seen[0].full_url).query)['limit'],['5'])
        self.assertNotIn(CREDENTIAL['access_token'],seen[0].full_url)
        for method,fields in (('POST',ic.INBOX_FIELDS),('GET',{**ic.INBOX_FIELDS,'limit':'100'}),
                              ('GET',{'fields':'messages,participants'})):
            with self.assertRaises(ic.ConnectionError):
                ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],method,fields,opener=opener)
        self.assertEqual(len(seen),1)
        with self.assertRaises(ic.GraphError):
            ic.request_graph('v27.0','/11111111/conversations',CREDENTIAL['access_token'],fields=ic.INBOX_FIELDS,
                opener=lambda *a,**kw:io.BytesIO(b'x'*(512*1024+1)))

    def test_withheld_identity_is_reported_instead_of_guessing_customer_or_direction(self):
        value=message();value.pop('from')
        with patch.object(ic,'request_graph',return_value=payload(value)):
            with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(caught.exception.details['reason'],'message_identity_unavailable')


class MissingExpansion(unittest.TestCase):
    def setUp(self):
        interval=patch.object(ic,'INBOX_INTERVAL',0);interval.start();self.addCleanup(interval.stop)

    def test_missing_expansion_reads_the_fixed_message_edge_for_the_returned_conversation(self):
        with patch.object(ic,'request_graph',side_effect=[{'data':[{'id':'PRIVATE_CONVERSATION'}]}, {'data':[message()]}]) as calls:
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(rows[0][2],'manual-mid');self.assertEqual(report['fallback_requests'],1)
        self.assertEqual(report['expansion_shapes']['missing'],1);self.assertEqual(report['unavailable_conversations'],0)
        self.assertEqual(calls.call_args_list[1].args,('v27.0','/PRIVATE_CONVERSATION/messages',CREDENTIAL['access_token']))
        self.assertEqual(calls.call_args_list[1].kwargs['fields'],ic.MESSAGE_FIELDS)
        self.assertLessEqual(calls.call_args_list[1].kwargs['timeout'],4)
        self.assertNotIn('PRIVATE',json.dumps(report))

    def test_one_unavailable_conversation_does_not_hide_readable_messages(self):
        result={'data':[{'id':'PRIVATE_UNAVAILABLE'}, {'id':'PRIVATE_READABLE','messages':{'data':[message()]}}]}
        with patch.object(ic,'request_graph',side_effect=[result,ic.GraphError('permission_denied',400,200)]):
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(len(rows),1);self.assertEqual(report['unavailable_conversations'],1)
        self.assertEqual(report['conversations'],2)

    def test_every_bad_expansion_shape_uses_at_most_one_direct_read(self):
        for content,shape in ((None,'not_object'),({},'data_missing'),({'data':None},'data_not_list')):
            result={'data':[{'id':'PRIVATE_CONVERSATION','messages':content}]}
            with patch.object(ic,'request_graph',side_effect=[result,{'data':[message()]}]) as calls:
                rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
            self.assertEqual(len(rows),1);self.assertEqual(calls.call_count,2);self.assertEqual(report['expansion_shapes'][shape],1)

    def test_provider_ignoring_nested_limits_is_trimmed_without_rejecting_valid_messages(self):
        value={'data':[{'id':'PRIVATE_CONVERSATION_'+str(i),'messages':{'data':[
            message(mid='synthetic-'+str(i)+'-'+str(j)) for j in range(11)]}} for i in range(6)]}
        with patch.object(ic,'request_graph',return_value=value) as calls:
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(len(rows),50);self.assertEqual(report['conversations'],5);self.assertEqual(report['scanned'],50)
        self.assertTrue(report['limited']);self.assertEqual(report['expansion_shapes']['too_many'],5);self.assertEqual(calls.call_count,1)

    def test_all_unavailable_is_an_error_with_only_safe_counts_not_an_empty_inbox(self):
        with patch.object(ic,'request_graph',side_effect=[{'data':[{'id':'PRIVATE_CONVERSATION'}]},{}]):
            with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
        info=caught.exception.details
        self.assertEqual(info['reason'],'inbox_message_edge_shape');self.assertEqual(info['fallback_requests'],1)
        self.assertEqual(info['unavailable_conversations'],1);self.assertNotIn('PRIVATE',json.dumps(info))

    def test_budget_stops_further_requests_without_guessing_absence(self):
        with patch.object(ic.time,'monotonic',side_effect=[0,20,20]),patch.object(ic,'request_graph',return_value={'data':[{'id':'PRIVATE_CONVERSATION'}]}) as calls:
            with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(calls.call_count,1);self.assertEqual(caught.exception.details['reason'],'inbox_read_budget')

    def test_direct_reads_are_paced_and_budget_is_rechecked_after_wait(self):
        first={'data':[{'id':'PRIVATE_CONVERSATION'}]}
        with patch.object(ic,'INBOX_INTERVAL',.55),patch.object(ic.time,'monotonic',return_value=0),patch.object(ic.time,'sleep') as pause:
            with patch.object(ic,'request_graph',side_effect=[first,{'data':[message()]}]):
                ic.read_recent_inbox(CFG,CREDENTIAL)
        pause.assert_called_once_with(.55)
        with patch.object(ic,'INBOX_INTERVAL',.55),patch.object(ic.time,'monotonic',side_effect=[0,0,0,19]),patch.object(ic.time,'sleep'):
            with patch.object(ic,'request_graph',return_value=first) as calls:
                with self.assertRaises(ic.GraphError):ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(calls.call_count,1)

    def test_direct_reply_still_filters_other_account_and_caps_messages(self):
        first={'data':[{'id':'PRIVATE_CONVERSATION'}]}
        with patch.object(ic,'request_graph',side_effect=[first,{'data':[message(mid='wrong',target='22222222')]+[
                message(mid='ok-'+str(i)) for i in range(15)]}]):
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(len(rows),9);self.assertEqual(report['scanned'],10);self.assertEqual(report['skipped'],1)
        self.assertTrue(report['limited']);self.assertTrue(all(row[0]=='11111111' for row in rows))

    def test_five_conversations_max_six_gets_no_paging(self):
        result={'data':[{'id':'PRIVATE_CONVERSATION_'+str(i)} for i in range(5)]}
        result['paging']={'next':'https://PRIVATE/?access_token=PRIVATE'}
        with patch.object(ic,'request_graph',side_effect=[result]+[{'data':[message(mid='synthetic-'+str(i))]} for i in range(5)]) as calls:
            rows,report=ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(len(rows),5);self.assertEqual(calls.call_count,6);self.assertTrue(report['limited'])
        self.assertTrue(all(c.args[1].startswith('/') and 'PRIVATE/?' not in c.args[1] for c in calls.call_args_list))

    def test_token_refusal_stops_the_whole_read_without_returning_partial_content(self):
        result={'data':[{'id':'PRIVATE_READABLE','messages':{'data':[message()]}},{'id':'PRIVATE_UNAVAILABLE'}]}
        with patch.object(ic,'request_graph',side_effect=[result,ic.GraphError('token_invalid',400,190)]):
            with self.assertRaises(ic.GraphError) as caught:ic.read_recent_inbox(CFG,CREDENTIAL)
        self.assertEqual(caught.exception.details['reason'],'token_invalid')

    def test_direct_transport_is_get_only_fixed_fields_and_encodes_opaque_ids(self):
        from urllib.parse import quote
        seen=[]
        def opener(request,timeout):seen.append(request);return io.BytesIO(b'{"data":[]}')
        path='/'+quote('t_encoded+id/value:part=',safe='')+'/messages'
        ic.request_graph('v27.0',path,CREDENTIAL['access_token'],fields=ic.MESSAGE_FIELDS,opener=opener)
        self.assertEqual(seen[0].get_method(),'GET');self.assertEqual(urlsplit(seen[0].full_url).hostname,'graph.facebook.com')
        self.assertNotIn(CREDENTIAL['access_token'],seen[0].full_url)
        for path,method,fields in (('/../messages','GET',ic.MESSAGE_FIELDS),('/PRIVATE_CONVERSATION/messages','POST',ic.MESSAGE_FIELDS),
                                   ('/PRIVATE_CONVERSATION/messages','GET',{'fields':'*'}),('/PRIVATE_CONVERSATION/messages?token=x','GET',ic.MESSAGE_FIELDS)):
            with self.assertRaises(ic.ConnectionError):ic.request_graph('v27.0',path,CREDENTIAL['access_token'],method,fields,opener=opener)
        self.assertEqual(len(seen),1)


class ManualHTTP(unittest.TestCase):
    def setUp(self):
        self.f=receiving.ReceivingHTTP();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.server=self.f.server

    def refresh(self,path='/panel/meta/check',scope='inbox_refresh',extra=None):
        action=scope if path.startswith('/panel') else 'meta:'+path.split('/')[2]+':'+scope
        csrf=panel_login.admin_csrf_token(self.f.session,self.f.fixture.config['panel_password'],action)
        return self.f.fixture.request(path,'POST',urlencode({'csrf':csrf}),
            {**self.f.headers,'X-Meta-Inbox':'refresh',**(extra or {})})

    def test_partial_direct_read_stores_valid_text_reports_unavailable_and_preserves_queue(self):
        value={'data':[{'id':'PRIVATE_UNAVAILABLE'},{'id':'PRIVATE_READABLE'}]}
        with patch.object(ic,'INBOX_INTERVAL',0),patch.object(ic,'request_graph',side_effect=[value,
                ic.GraphError('permission_denied',400,200),{'data':[message()]}]):
            status,_,body=self.refresh()
        report=json.loads(body)
        self.assertEqual(status,200);self.assertEqual(report['status'],'confirmed')
        self.assertEqual(report['imported'],1);self.assertEqual(report['unavailable_conversations'],1)
        self.assertEqual(report['fallback_requests'],2);self.assertNotIn(b'PRIVATE',body);self.assertNotIn(b'Texto',body)
        self.assertEqual(self.server.list_pending(account_id='11111111'),[])
        with patch.object(ic,'INBOX_INTERVAL',0),patch.object(ic,'request_graph',side_effect=[
                {'data':[{'id':'PRIVATE_UNAVAILABLE'}]},ic.GraphError('permission_denied',400,200)]):
            status,_,body=self.refresh()
        self.assertEqual(json.loads(body)['status'],'error')
        with self.server.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)

    def test_long_id_manual_import_then_real_webhook_claim_and_ack(self):
        mid='encoded-message-id-'+('a'*300)
        with patch.object(ic,'request_graph',return_value=payload(message(mid=mid))):
            self.assertEqual(json.loads(self.refresh()[2])['imported'],1)
        import hmac,hashlib
        event={'object':'instagram','entry':[{'messaging':[{'sender':{'id':'99999999'},'recipient':{'id':'11111111'},'message':{'mid':mid,'text':'oi'}}]}]}
        raw=json.dumps(event).encode()
        signature='sha256='+hmac.new(self.f.fixture.config['meta_app_secret'].encode(),raw,hashlib.sha256).hexdigest()
        self.assertEqual(json.loads(self.f.fixture.request('/webhook/instagram','POST',raw,{'X-Hub-Signature-256':signature})[2])['new_text_messages'],1)
        claim=self.server.claim_message(account_id='11111111')
        self.assertEqual(claim['messageId'],mid)
        self.assertIsNotNone(self.server.evaluate_claim({k:claim[k] for k in ('accountId','senderId','messageId','claimToken')}))
        self.assertTrue(self.server.acknowledge_message({k:claim[k] for k in ('accountId','senderId','messageId','claimToken')}))

    def test_manual_click_stores_and_displays_safely_but_never_enters_queue_or_confirms_webhook(self):
        token_path=self.server.DATA_DIR/self.server.oauth_meta.TOKEN_FILENAME
        token_before=token_path.read_bytes()
        with patch.object(ic,'request_graph',return_value=payload(message())) as graph:
            status,_,body=self.refresh()
        self.assertEqual(status,200);report=json.loads(body);self.assertEqual(report['imported'],1)
        self.assertEqual(graph.call_count,1);self.assertNotIn(b'manual-mid',body);self.assertNotIn(b'Texto',body)
        self.assertEqual(token_path.read_bytes(),token_before)
        self.assertEqual(self.server.list_pending(account_id='11111111'),[])
        self.assertIsNone(self.server.claim_message(account_id='11111111'))
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound WHERE processed_at IS NULL').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT source FROM inbound').fetchone()[0],'manual')
        cfg=self.server.meta_configuration_for_business('umdoislab')
        self.assertEqual(self.server.connection_summary(cfg)['messagesStored'],0)
        with patch.object(ic,'request_graph') as graph:
            for _ in range(2):
                status,_,body=self.f.fixture.request('/panel',headers=self.f.headers)
                self.assertIn(b'Consulta manual',body);self.assertIn(b'&lt;script&gt;',body);self.assertNotIn(b'<script>not_script()',body)
            self.f.fixture.request('/panel?view=settings',headers=self.f.headers)
        graph.assert_not_called()

    def test_repeated_import_then_real_webhook_promotes_once_without_replaying_acks(self):
        with patch.object(ic,'request_graph',return_value=payload(message())):
            self.assertEqual(json.loads(self.refresh()[2])['imported'],1)
            self.assertEqual(json.loads(self.refresh()[2])['existing'],1)
        raw=json.dumps({'object':'instagram','entry':[{'messaging':[{'sender':{'id':'99999999'},
            'recipient':{'id':'11111111'},'message':{'mid':'manual-mid','text':'Webhook original'}}]}]}).encode()
        import hmac,hashlib
        signature='sha256='+hmac.new(self.f.fixture.config['meta_app_secret'].encode(),raw,hashlib.sha256).hexdigest()
        headers={'X-Hub-Signature-256':signature}
        self.assertEqual(json.loads(self.f.fixture.request('/webhook/instagram','POST',raw,headers)[2])['new_text_messages'],1)
        self.assertEqual(json.loads(self.f.fixture.request('/webhook/instagram','POST',raw,headers)[2])['new_text_messages'],0)
        claim=self.server.claim_message(account_id='11111111');self.assertIsNotNone(claim)
        self.assertTrue(self.server.acknowledge_message({key:claim[key] for key in ('accountId','senderId','messageId','claimToken')}))
        with patch.object(ic,'request_graph',return_value=payload(message())):
            self.assertEqual(json.loads(self.refresh()[2])['existing'],1)
        self.assertIsNone(self.server.claim_message(account_id='11111111'))
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)
            self.assertEqual(db.execute('SELECT source,message_text FROM inbound').fetchone(),('webhook','Webhook original'))

    def test_csrf_session_and_header_guards_precede_content_read(self):
        with patch.object(ic,'request_graph') as graph:
            self.assertEqual(self.refresh(scope='check')[0],403)
            self.assertEqual(self.refresh(extra={'Cookie':''})[0],403)
            self.assertEqual(self.refresh(extra={'X-Meta-Diagnostic':'routing'})[0],400)
            self.assertEqual(self.refresh(extra={'X-Meta-Inbox':'unsupported'})[0],400)
            self.assertEqual(self.refresh('/panel/meta/subscribe')[0],400)
        graph.assert_not_called()

    def test_provider_failure_invalid_data_and_busy_preserve_inbox(self):
        with patch.object(ic,'request_graph',return_value=payload(message())):self.refresh()
        with patch.object(ic,'request_graph',side_effect=ic.GraphError('token_invalid',400,190)):
            report=json.loads(self.refresh()[2]);self.assertEqual(report['reason'],'token_invalid');self.assertEqual(report['provider_code'],190)
        bad=message(mid='bad');bad['created_time']='bad'
        with patch.object(ic,'request_graph',return_value=payload(message(mid='new'),bad)):
            self.assertEqual(json.loads(self.refresh()[2])['reason'],'inbox_timestamp_shape')
        with self.server.database() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],1)
        self.server._INBOX_LOCK.acquire()
        try:
            with patch.object(ic,'request_graph') as graph:self.assertEqual(json.loads(self.refresh()[2])['reason'],'busy')
            graph.assert_not_called()
        finally:self.server._INBOX_LOCK.release()

    def test_account_scoping_and_migration_default_for_existing_webhook_rows(self):
        with self.server.database() as db:
            business=account_registry.provision(db,'second_review','Second')
            account_registry.bind_verified(db,business,'22222222','second_review')
        root=account_registry.credential_root(self.server.DATA_DIR,business)
        self.server.oauth_meta.store_token(root,{**CREDENTIAL,'business_id':business,'account_id':'22222222','username':'second_review'})
        with patch.object(ic,'request_graph',return_value=payload(message())):self.refresh()
        path='/accounts/'+business+'/panel/meta/check'
        with patch.object(ic,'request_graph',return_value=payload(message(target='22222222'))) as graph:
            self.assertEqual(json.loads(self.refresh(path)[2])['imported'],1)
        self.assertEqual(graph.call_args.args[1],'/22222222/conversations')
        with self.server.database() as db:
            self.assertEqual(db.execute('SELECT COUNT(DISTINCT recipient_id) FROM inbound').fetchone()[0],2)
        csrf=panel_login.admin_csrf_token(self.f.session,self.f.fixture.config['panel_password'],'inbox_refresh')
        with patch.object(ic,'request_graph') as graph:
            result=self.f.fixture.request(path,'POST',urlencode({'csrf':csrf}),{**self.f.headers,'X-Meta-Inbox':'refresh'})
        self.assertEqual(result[0],403);graph.assert_not_called()
        self.assertEqual(self.server.list_pending(account_id='22222222'),[])


if __name__=='__main__':unittest.main()
