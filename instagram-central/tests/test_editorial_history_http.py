import json
import unittest
from unittest.mock import patch
import editorial_http
import editorial_history
import test_editorial_publication_http as fixtures
from test_editorial_history import entry

server=fixtures.server


class HistoryHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.PublicationHTTPTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.calls=[];old=self.fx.hub.api_factory
        def factory(cfg,credential):
            api=old(cfg,credential)
            def page(*a,**kw):self.calls.append(True);return {'data':[entry(1)]}
            api.history_page=page;return api
        self.fx.hub.api_factory=factory;self.worker=editorial_history.HistoryHub(self.fx.hub)
        patched=patch.object(server,'HISTORY',self.worker);patched.start();self.addCleanup(patched.stop)
    def operation(self,action,data,business='umdoislab',token_business=None,token_action=None,cookie=True):
        fixture=self.fx.fixture
        token=server.panel_login.admin_csrf_token(fixture.cookie,fixture.cfg['panel_password'],editorial_http.csrf_action(token_action or action,token_business or business))
        prefix='' if business=='umdoislab' else '/accounts/'+business
        return fixture.request(prefix+'/editorial/api/drafts','POST',json.dumps(data),{'Content-Type':'application/json','X-CSRF-Token':token,'X-Editorial-Action':action},cookie=cookie)
    def test_start_cancel_are_authenticated_and_action_scoped_without_synchronous_graph(self):
        data={'downloadMedia':False}
        self.assertEqual(self.operation('history_start',data,cookie=False)[0],403)
        self.assertEqual(self.operation('history_start',data,token_action='draft')[0],403)
        self.assertEqual(self.operation('history_start',{'downloadMedia':'true'})[0],422)
        self.assertEqual(self.operation('history_start',{**data,'accountId':'other'})[0],422)
        status,_,body=self.operation('history_start',data)
        self.assertEqual(status,200);self.assertEqual(json.loads(body)['history']['status'],'queued')
        self.assertEqual(self.calls,[])
        self.assertEqual(self.operation('history_start',data)[0],409)
        self.assertEqual(self.operation('history_cancel',{},token_action='history_start')[0],403)
        self.assertEqual(self.operation('history_cancel',{})[0],200)
        self.worker.step('umdoislab');self.assertEqual(self.worker.public_state('umdoislab')['status'],'cancelled')
    def test_secondary_csrf_and_store_cannot_be_selected_by_primary_request(self):
        with server.database() as db:
            business=server.account_registry.provision(db,'other_account','Other')
            server.account_registry.bind_verified(db,business,'17841400000000002','other_account')
        self.assertEqual(self.operation('history_start',{'downloadMedia':False},business,token_business='umdoislab')[0],403)
        self.assertEqual(self.operation('history_start',{'downloadMedia':False},business)[0],200)
        self.assertEqual(self.worker.public_state('umdoislab')['status'],'idle')
        self.worker.step(business)
        primary=self.fx.fixture.state()['posts'];self.assertEqual(primary,[])
        secondary=server.editorial_store_for_business(business).snapshot()['posts']
        self.assertEqual(len(secondary),1);self.assertEqual(secondary[0]['source'],'instagram')
