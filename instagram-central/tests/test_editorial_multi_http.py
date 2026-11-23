"""Synthetic integrated HTTP/SQLite tests. Google download mocked."""
import hashlib
import json
import unittest
from unittest.mock import patch
import test_editorial_http as fixture
import editorial_import as incoming

server=fixture.server
RID='multi_synthetic_001'
ROOT='synthetic_root_001'


class MultiHTTP(unittest.TestCase):
    request=fixture.EditorialHTTPTests.request
    def setUp(self):
        fixture.EditorialHTTPTests.setUp(self)
        self.cfg['public_base_url']='https://central.example'
        with server.database() as db:
            db.execute("UPDATE instagram_accounts SET operational=1 WHERE business_id='synthetic'")
        self.grants=server.multi_connections()
        self.owner=self.grants.create('Owner fixture','owner_all',[],ROOT)
        self.delegate=self.grants.create('Delegate fixture','selected',['synthetic'])
        self.raw=fixture.png()
        self.item={'fileId':'synthetic_file_001','mime':'image/png','bytes':len(self.raw),
                   'sha256':hashlib.sha256(self.raw).hexdigest()}
    def tearDown(self):
        fixture.EditorialHTTPTests.tearDown(self)
    def call(self,action,data=None,*,key=None,account=None):
        h={'Authorization':'Bearer '+(key or self.owner)['token'],'Host':'central.example',
           'X-Forwarded-Proto':'https','X-Editorial-Action':'import_'+action,'Content-Type':'application/json'}
        if account is not None:h['X-Editorial-Account']=account
        if action=='upload':
            h.update({'Content-Type':'image/png','X-Import-Id':RID,'X-Media-Index':'0'})
        status,_,content=self.request('/editorial/api/'+('media' if action=='upload' else 'drafts'),'POST',
            self.raw if action=='upload' else json.dumps(data if data is not None else {}),h,cookie=False)
        return status,json.loads(content)
    def payload(self,mid):
        digest=hashlib.sha256(json.dumps({'format':'story','caption':'Test',
            'files':[{'sha256':self.item['sha256'],'mime':'image/png'}]},sort_keys=True).encode()).hexdigest()
        return {'schemaVersion':1,'requestId':RID,'transferApproved':True,'format':'story',
                'caption':'Test','mediaIds':[mid],'contentDigest':digest}
    def test_discovery_and_delegation(self):
        status,body=self.call('accounts')
        self.assertEqual(status,200,body)
        self.assertEqual({a['id'] for a in body['accounts']},{'umdoislab','synthetic'})
        self.assertEqual(self.call('resolve',{'destination':'1-2 Lab'})[1]['account'],'umdoislab')
        self.assertEqual(self.call('resolve',{})[0],403)
        self.assertEqual(self.call('resolve',{},key=self.delegate)[1]['account'],'synthetic')
        self.assertEqual(self.call('resolve',{'destination':'umdoislab'},key=self.delegate)[0],403)
        with server.database() as db:
            fixture.accounts.register(db,'futuretest','synthetic-3','futuretest','Future Test',enabled=True)
            db.execute("UPDATE instagram_accounts SET operational=1 WHERE business_id='futuretest'")
        self.assertEqual(self.call('resolve',{'destination':'Future Test'})[1]['account'],'futuretest')
        self.assertEqual(self.call('resolve',{'destination':'futuretest'},key=self.delegate)[0],403)
    def test_management_csrf(self):
        data={'label':'New fixture','scope':'selected','grants':['synthetic'],'driveRootId':''}
        h={'Content-Type':'application/json','X-Editorial-Action':'integration_multi_create'}
        self.assertEqual(self.request('/editorial/api/drafts','POST',json.dumps(data),h,cookie=False)[0],403)
        self.assertEqual(self.request('/editorial/api/drafts','POST',json.dumps(data),h)[0],403)
        status,_,raw=self.request('/editorial/api/csrf')
        self.assertEqual(status,200)
        h['X-CSRF-Token']=json.loads(raw)['integration_multi_create']
        status,_,raw=self.request('/editorial/api/drafts','POST',json.dumps(data),h)
        self.assertEqual(status,200,raw)
        new=json.loads(raw)
        self.assertTrue(new['token'].startswith('cei2.'))
        self.assertEqual(self.call('resolve',{},key=new)[1]['account'],'synthetic')
        self.assertEqual(self.call('publish',{},account='synthetic',key=new)[0],403)
    def test_receipts_and_original_digest(self):
        status,stage=self.call('upload',account='umdoislab')
        self.assertEqual(status,201,stage)
        payload=self.payload(stage['id'])
        self.assertEqual(self.call('commit',{**payload,'contentDigest':'a'*64},account='umdoislab')[0],422)
        status,first=self.call('commit',payload,account='umdoislab')
        self.assertEqual(status,200,first)
        self.assertEqual(first['status'],'draft')
        self.assertFalse(first['published'])
        self.assertFalse(first['publicationAuthorized'])
        self.assertEqual(self.call('commit',payload,account='umdoislab')[1]['id'],first['id'])
        self.assertFalse(self.call('receipt',{'requestId':RID},account='synthetic')[1]['found'])
        status,stage=self.call('upload',account='synthetic')
        self.assertEqual(status,201,stage)
        status,second=self.call('commit',self.payload(stage['id']),account='synthetic')
        self.assertEqual(status,200,second)
        self.assertNotEqual(first['id'],second['id'])
        self.assertFalse(self.call('receipt',{'requestId':RID},account='synthetic',key=self.delegate)[1]['found'])
        self.assertEqual(self.call('receipt',{'requestId':RID},account='umdoislab',key=self.delegate)[0],403)
        self.assertEqual(len(server.editorial_store_for_business('umdoislab').snapshot()['posts']),1)
        self.assertEqual(len(server.editorial_store_for_business('synthetic').snapshot()['posts']),1)
    def test_drive_validation_revocation_and_legacy(self):
        with patch.object(server.editorial_multi_api.drive,'download',return_value=self.raw) as read:
            status,verified=self.call('drive_validate',self.item,account='umdoislab')
            self.assertEqual(status,200,verified)
            self.assertTrue(verified['verified'])
            self.assertFalse(verified['persisted'])
            self.assertEqual(self.call('drive_validate',self.item,account='unknown')[0],403)
            read.assert_called_once()
        store=server.editorial_store_for_business('umdoislab')
        self.assertEqual(store.snapshot()['posts'],[])
        def revoke(*args):
            self.grants.revoke(self.owner['id'])
            return self.raw
        with patch.object(server.editorial_multi_api.drive,'download',side_effect=revoke):
            self.assertEqual(self.call('drive_stage',{'requestId':RID,'index':0,'media':self.item},account='umdoislab')[0],403)
        incoming.prepare(store)
        with store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM incoming_media').fetchone()[0],0)
        legacy=incoming.manage(store,'umdoislab','integration_create',{'label':'Legacy fixture','canPublish':False})
        self.assertEqual(self.call('receipt',{'requestId':RID},key=legacy)[0],200)
        self.assertEqual(self.call('receipt',{'requestId':RID},key=legacy,account='synthetic')[0],403)
        self.assertEqual(self.call('accounts',key=legacy)[0],404)


if __name__=='__main__':unittest.main()
