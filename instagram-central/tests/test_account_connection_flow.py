"""Account authorization guidance and safe native-form errors on the same account."""
import re
import unittest
from urllib.parse import urlencode
from unittest.mock import patch
import instagram_connection as ic
import panel_login
import account_registry
import test_receiving_diagnostics as receiving


class AccountConnectionFlow(unittest.TestCase):
    def setUp(self):
        self.f=receiving.ReceivingHTTP();self.f.setUp();self.addCleanup(self.f.tearDown)
        self.server=self.f.server

    def page(self,path='/panel?view=settings'):
        status,_,body=self.f.fixture.request(path,headers=self.f.headers)
        self.assertEqual(status,200);return body

    def post(self,business='umdoislab',kind='check'):
        path='' if business=='umdoislab' else '/accounts/'+business
        action=kind if business=='umdoislab' else 'meta:'+business+':'+kind
        csrf=panel_login.admin_csrf_token(self.f.session,self.f.fixture.config['panel_password'],action)
        return self.f.fixture.request(path+'/panel/meta/'+kind,'POST',urlencode({'csrf':csrf}),self.f.headers)

    def test_new_account_highlights_oauth_and_disables_check_without_requiring_webhook_fields(self):
        with self.server.database() as db:business=account_registry.provision(db,'second_review','Second')
        path='/accounts/'+business
        primary=self.server.DATA_DIR/self.server.oauth_meta.TOKEN_FILENAME;before=primary.read_bytes()
        with patch.object(ic,'request_graph') as graph,patch.object(self.server.oauth_meta,'exchange_code') as exchange:
            body=self.page(path+'/panel?view=settings')
            self.assertIn('Próximo passo: autorizar esta conta'.encode(),body)
            self.assertRegex(body,rb'<a class="btn primary"[^>]+/accounts/[^>]+/oauth/meta/start"[^>]*>Conectar Instagram pela Meta</a>')
            self.assertIn(b'<button disabled>Verificar acesso Meta</button>',body)
            self.assertIn('não é pré-requisito para iniciar a autorização'.encode(),body)
            status,headers,_=self.post(business)
            self.assertEqual(status,303)
            self.assertEqual(headers['Location'],path+'/panel?view=settings&meta_result=authorization_missing')
            self.assertIn('ainda não tem uma autorização Meta utilizável'.encode(),self.page(headers['Location']))
        graph.assert_not_called();exchange.assert_not_called();self.assertEqual(primary.read_bytes(),before)
        self.assertIsNone(self.server._meta_credential(business))

    def test_existing_token_can_be_checked_and_success_keeps_context(self):
        body=self.page();self.assertIn(b'<button>Verificar acesso Meta</button>',body)
        with patch.object(ic,'verify_access',return_value={k:receiving.CREDENTIAL[k] for k in ('business_id','account_id','username','verified_at')}), \
             patch.object(ic,'diagnose_receiving',return_value=receiving.GOOD),patch.object(ic,'subscribe_messages') as subscribe:
            status,headers,_=self.post()
        self.assertEqual(status,303);self.assertIn('meta_result=check_completed',headers['Location'])
        self.assertIn('Verificação concluída.'.encode(),self.page(headers['Location']));subscribe.assert_not_called()

    def test_expired_or_refused_token_shows_reconnect_without_raw_errors_or_replacing_token(self):
        with patch.object(ic,'verify_access',side_effect=ic.GraphError('token_invalid',400,190)), \
             patch.object(ic,'diagnose_receiving',return_value=receiving.GOOD),patch.object(ic,'subscribe_messages') as subscribe:
            status,headers,_=self.post()
        self.assertEqual(status,303);self.assertIn('meta_result=token_invalid',headers['Location'])
        body=self.page(headers['Location']);self.assertIn(b'Reconectar Instagram pela Meta',body)
        saved=self.server._meta_credential();self.assertEqual(saved['access_token'],receiving.CREDENTIAL['access_token'])
        self.assertEqual(saved['verified_at'],receiving.CREDENTIAL['verified_at']);subscribe.assert_not_called()
        self.assertNotIn(receiving.CREDENTIAL['access_token'].encode(),body)
        self.assertNotIn(b'Meta diagnostic request failed',body)

    def test_saved_token_without_identity_still_has_check_available(self):
        self.server.oauth_meta.store_token(self.server.DATA_DIR,{**receiving.CREDENTIAL,'verified_at':0})
        body=self.page();self.assertIn(b'<button>Verificar acesso Meta</button>',body)
        self.assertIn('Há uma credencial salva.'.encode(),body)

    def test_query_permission_and_subscription_errors_have_distinct_feedback(self):
        with patch.object(ic,'verify_access',side_effect=ic.GraphError('transport_error')), \
             patch.object(ic,'diagnose_receiving',return_value=receiving.GOOD):
            status,headers,_=self.post()
        self.assertEqual(status,303);self.assertIn('meta_result=query_failed',headers['Location'])
        self.assertIn('autorização anterior foi preservada'.encode(),self.page(headers['Location']))
        with patch.object(ic,'subscribe_messages',side_effect=ic.GraphError('permission_denied',403,200)):
            status,headers,_=self.post(kind='subscribe')
        self.assertEqual(status,303);self.assertIn('meta_result=permission_denied',headers['Location'])
        self.assertIn('recusou o acesso solicitado'.encode(),self.page(headers['Location']))
        with patch.object(ic,'subscribe_messages',side_effect=ic.GraphError('transport_error')):
            status,headers,_=self.post(kind='subscribe')
        self.assertEqual(status,303);self.assertIn('meta_result=subscription_failed',headers['Location'])
        self.assertIn('confirmar a assinatura de mensagens'.encode(),self.page(headers['Location']))

    def test_result_query_is_allowlisted_and_credential_mismatch_does_not_use_primary(self):
        for query in ('view=settings&meta_result=PRIVATE','view=settings&meta_result=check_completed&meta_result=token_invalid',
                      'view=settings&meta_result=<script>', 'view=settings&unknown=1'):
            self.assertEqual(self.f.fixture.request('/panel?'+query,headers=self.f.headers)[0],404)
        with self.server.database() as db:
            business=account_registry.provision(db,'second_review','Second')
            account_registry.bind_verified(db,business,'22222222','second_review')
        root=account_registry.credential_root(self.server.DATA_DIR,business)
        self.server.oauth_meta.store_token(root,{**receiving.CREDENTIAL,'business_id':'umdoislab'})
        with patch.object(ic,'request_graph') as graph:
            status,headers,_=self.post(business)
        graph.assert_not_called();self.assertEqual(status,303)
        self.assertEqual(headers['Location'],'/accounts/'+business+'/panel?view=settings&meta_result=authorization_missing')


if __name__=='__main__':unittest.main()
