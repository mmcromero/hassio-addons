"""Incoming API: synthetic accounts, loopback and simulated Meta only."""
from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import editorial_import as incoming
import editorial_core as core
import panel_login
import editorial_http as api
from test_editorial_http import EditorialHTTPTests, png, server
from test_editorial_publishing import PublishingTests


class IncomingHTTPTests(EditorialHTTPTests):
    # Reuse fixture helpers, not the entire inherited suite in this test class.
    def setUp(self):
        super().setUp()
        self.cfg['public_base_url']='https://central.example'
        self.store=server.editorial_store_for_business()
        self.secret=incoming.manage(self.store,'umdoislab','integration_create',{'label':'Synthetic editor','canPublish':False})
        self.key=incoming.authenticate(self.store,self.secret['token'])
        self.request_id='test_transfer_00001'

    def call(self,action,data=None,*,token=None,headers=None,path=None):
        hdr={'Authorization':'Bearer '+(token or self.secret['token']), 'X-Editorial-Action':'import_'+action,
             'Host':'central.example','X-Forwarded-Proto':'https','Content-Type':'application/json'}
        if headers:hdr.update(headers)
        if action=='upload':
            body=png() if data is None else data
            hdr.update({'Content-Type':(headers or {}).get('Content-Type','image/png'),'X-Import-Id':self.request_id,'X-Media-Index':(headers or {}).get('X-Media-Index','0')})
        else:body=json.dumps(data if data is not None else {'requestId':self.request_id})
        return self.request(path or ('/editorial/api/media' if action=='upload' else '/editorial/api/drafts'),
                            'POST',body,hdr,cookie=False)

    def transfer(self):
        status,_,body=self.call('upload');self.assertEqual(status,201,body)
        mid=json.loads(body)['id']
        payload={'schemaVersion':1,'requestId':self.request_id,'transferApproved':True,'format':'feed',
                 'caption':'Synthetic caption','mediaIds':[mid],'contentDigest':'a'*64}
        status,_,body=self.call('commit',payload);self.assertEqual(status,200,body)
        return payload,json.loads(body)

    def test_transfer_stays_private_until_explicit_commit_and_never_publishes(self):
        status,_,raw=self.call('upload');self.assertEqual(status,201)
        self.assertEqual(self.store.snapshot()['media'],[])
        self.assertEqual(self.store.snapshot()['posts'],[])
        mid=json.loads(raw)['id']
        payload={'schemaVersion':1,'requestId':self.request_id,'transferApproved':False,'format':'feed',
                 'caption':'Synthetic','mediaIds':[mid],'contentDigest':'a'*64}
        self.assertEqual(self.call('commit',payload)[0],422)
        self.assertEqual(self.store.snapshot()['posts'],[])
        payload['transferApproved']=True
        status,_,body=self.call('commit',payload);self.assertEqual(status,200,body)
        post=self.store.get_post(json.loads(body)['id']);self.assertEqual(post['state'],'draft')
        with self.store._db() as db:
            row=db.execute('SELECT * FROM posts').fetchone()
            self.assertEqual(row['publish_authorized'],0);self.assertIsNone(row['scheduled_at'])

    def test_retry_conflict_restart_and_deleted_receipt(self):
        payload,first=self.transfer()
        def retry(_):return self.call('commit',payload)
        with ThreadPoolExecutor(max_workers=4) as pool:
            results=list(pool.map(retry,range(4)))
        self.assertTrue(all(r[0]==200 for r in results))
        self.assertEqual(len(self.store.snapshot()['posts']),1)
        payload['caption']='Changed';self.assertEqual(self.call('commit',payload)[0],409)
        restarted=core.EditorialStore(self.store.root)
        self.assertTrue(incoming.receipt(restarted,self.key,self.request_id)['found'])
        self.store.delete_post(first['id'],expected_version=1,delete_unused_media=True)
        self.assertEqual(json.loads(self.call('receipt')[2])['status'],'deleted')

    def test_upload_retry_same_position_and_changed_bytes(self):
        first=self.call('upload');second=self.call('upload')
        self.assertEqual(first[2],second[2])
        with patch('editorial_import.hashlib.sha256',wraps=hashlib.sha256):
            status=self.call('upload',png()+b'ignored metadata')[0]
        # Normalization discards trailing bytes, therefore same normalized content.
        self.assertEqual(status,201)
        from io import BytesIO
        from PIL import Image
        altered=BytesIO();Image.new('RGB',(2,2),'blue').save(altered,'PNG')
        self.assertEqual(self.call('upload',altered.getvalue())[0],409)
        with self.store._db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM incoming_media').fetchone()[0],1)

    def test_auth_expiry_revocation_cross_account_and_no_ambient_cookie(self):
        for hdr in ({'X-Forwarded-Proto':'http'},{'Host':'wrong.example'}):
            self.assertEqual(self.call('receipt',headers=hdr)[0],421)
        self.assertEqual(self.call('receipt',token=self.secret['token']+'x')[0],403)
        # Header action cannot grant normal administrative/publishing routes.
        self.assertEqual(self.request('/editorial/api/state',headers={'Authorization':'Bearer '+self.secret['token']},cookie=False)[0],403)
        self.assertEqual(self.call('receipt',path='/accounts/synthetic/editorial/api/drafts')[0],404)
        forged=self.secret['token'].replace('.umdoislab.','.synthetic.')
        self.assertEqual(self.call('receipt',token=forged)[0],403)
        unknown=self.secret['token'].replace('.umdoislab.','.unknown_business.')
        self.assertEqual(self.call('receipt',token=unknown)[0],403)
        incoming.manage(self.store,'umdoislab','integration_revoke',{'id':self.secret['id']})
        self.assertEqual(self.call('receipt')[0],403)
        fresh=incoming.manage(self.store,'umdoislab','integration_create',{'label':'Expires','canPublish':False})
        with self.store._tx() as db:db.execute('UPDATE integration_keys SET expires=0 WHERE id=?',(fresh['id'],))
        self.assertEqual(self.call('receipt',token=fresh['token'])[0],403)

    def test_management_requires_session_and_action_scoped_csrf(self):
        self.assertEqual(self.request('/editorial/api/drafts','POST','{}',{'Content-Type':'application/json','X-Editorial-Action':'integration_create'},cookie=False)[0],403)
        csrf=panel_login.admin_csrf_token(self.cookie,self.cfg['panel_password'],api.csrf_action('integration_create'))
        result=self.request('/editorial/api/drafts','POST',json.dumps({'label':'Video tool','canPublish':False}),{'Content-Type':'application/json','X-Editorial-Action':'integration_create','X-CSRF-Token':csrf})
        self.assertEqual(result[0],200,result[2])
        listed=incoming.manage(self.store,'umdoislab','integration_list',{})
        self.assertNotIn('token',json.dumps(listed));self.assertNotIn('digest',json.dumps(listed))

    def test_receipts_and_staging_are_scoped_to_connection_and_quota(self):
        payload,result=self.transfer()
        other=incoming.manage(self.store,'umdoislab','integration_create',{'label':'Other tool','canPublish':False})
        self.assertFalse(json.loads(self.call('receipt',token=other['token'])[2])['found'])
        self.assertEqual(self.call('commit',payload,token=other['token'])[0],409)
        # Simulated staging occupancy counts against existing UI uploads too.
        with self.store._tx() as db:
            db.execute('INSERT INTO incoming_media VALUES(?,?,?,?,?,?,?,?)',
                       ('f'*32,self.key['id'],'quota_request_00001',0,'png','a'*64,1024**3,9999999999))
        with self.assertRaises(core.EditorialError):self.store.add_media(png(),'png')
        self.request_id='another_request_0001'
        self.assertEqual(self.call('upload')[0],422)

    def test_revocation_during_upload_prevents_staging_commit(self):
        original=api.validated_upload
        def revoke_then_validate(raw,mime):
            incoming.manage(self.store,'umdoislab','integration_revoke',{'id':self.key['id']})
            return original(raw,mime)
        with patch('editorial_http.validated_upload',side_effect=revoke_then_validate):
            self.assertEqual(self.call('upload')[0],422)
        with self.store._db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM incoming_media').fetchone()[0],0)

    def test_upload_expiration_and_invalid_manifest_are_atomic(self):
        status,_,body=self.call('upload');self.assertEqual(status,201)
        mid=json.loads(body)['id']
        payload={'schemaVersion':1,'requestId':self.request_id,'transferApproved':True,'format':'carousel',
                 'caption':'x','mediaIds':[mid,'0'*32],'contentDigest':'a'*64}
        self.assertEqual(self.call('commit',payload)[0],422)
        self.assertEqual(self.store.snapshot()['posts'],[]);self.assertEqual(self.store.snapshot()['media'],[])
        with self.store._tx() as db:db.execute('UPDATE incoming_media SET expires=0')
        incoming.cleanup(self.store)
        self.assertFalse((self.store.media_dir/(mid+'.png')).exists())
        self.assertEqual(self.call('upload',b'<svg/>')[0],422)

    def test_mp4_and_carousel_are_transferred_without_publication(self):
        video=(Path(__file__).parent/'fixtures'/'synthetic.mp4').read_bytes()
        self.request_id='synthetic_video_0001'
        status,_,body=self.call('upload',video,headers={'Content-Type':'video/mp4'})
        self.assertEqual(status,201,body)
        payload={'schemaVersion':1,'requestId':self.request_id,'transferApproved':True,'format':'reel',
                 'caption':'Synthetic Reel','mediaIds':[json.loads(body)['id']],'contentDigest':'b'*64}
        status,_,body=self.call('commit',payload);self.assertEqual(status,200,body)
        self.assertEqual(self.store.get_post(json.loads(body)['id'])['state'],'draft')
        self.request_id='synthetic_carousel_01';media=[]
        for index in range(2):
            status,_,body=self.request('/editorial/api/media','POST',png(),{
                'Authorization':'Bearer '+self.secret['token'],'Host':'central.example','X-Forwarded-Proto':'https',
                'Content-Type':'image/png','X-Editorial-Action':'import_upload',
                'X-Import-Id':self.request_id,'X-Media-Index':str(index)},cookie=False)
            self.assertEqual(status,201,body);media.append(json.loads(body)['id'])
        payload.update(requestId=self.request_id,format='carousel',mediaIds=media,contentDigest='c'*64)
        self.assertEqual(self.call('commit',payload)[0],200)
        self.assertEqual(len(self.store.snapshot()['posts']),2)
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT SUM(publish_authorized) FROM posts').fetchone()[0],0)

    def test_publish_scope_and_exact_account_and_authorization(self):
        _,result=self.transfer()
        payload={'requestId':self.request_id,'version':1,'instagramAccountId':'synthetic-1','publishApproved':True}
        self.assertEqual(self.call('publish',payload)[0],403)
        with self.store._tx() as db:db.execute('UPDATE integration_keys SET can_publish=1 WHERE id=?',(self.key['id'],))
        with patch.object(server,'PUBLICATIONS') as pub:
            pub.queue.return_value=None
            for field,value in [('publishApproved',False),('instagramAccountId','synthetic-2'),('version',True)]:
                wrong={**payload,field:value};self.assertEqual(self.call('publish',wrong)[0],422)
            pub.queue.assert_not_called()
            status,_,body=self.call('publish',payload);self.assertEqual(status,202,body)
            pub.queue.assert_called_once_with('umdoislab',result['id'],1,import_request=self.request_id,expected_account='synthetic-1')



class DirectPublicationTests(PublishingTests):
    def imported(self):
        store=self.stores['umdoislab'];info=incoming.manage(store,'umdoislab','integration_create',{'label':'test','canPublish':True})
        key=incoming.authenticate(store,info['token'])
        request='synthetic_publish_001'
        content,ext=__import__('editorial_http').validated_upload(__import__('test_editorial_publishing').png(),'image/png')
        mid=incoming.stage(store,key,request,0,content,ext)['id']
        result=incoming.commit(store,key,{'schemaVersion':1,'requestId':request,'transferApproved':True,
            'format':'feed','caption':'caption','mediaIds':[mid],'contentDigest':'b'*64})
        return store,key,request,result

    def test_direct_publication_atomic_authorization_and_duplicate_request(self):
        store,key,request,result=self.imported()
        self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account=self.cfg['umdoislab']['instagram_account_id'])
        self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account=self.cfg['umdoislab']['instagram_account_id'])
        current=incoming.receipt(store,key,request)
        self.assertTrue(current['publicationAuthorized']);self.assertFalse(current['published'])
        self.assertEqual(current['status'],'scheduled')
        with store._db() as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM audit WHERE event='publication_authorized'").fetchone()[0],1)
        # Existing publishing worker performs remote operations, not the import HTTP handler.
        for _ in range(12):self.hub.step('umdoislab');self.now+=20
        self.assertEqual(len(self.meta.published),1)
        self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account=self.cfg['umdoislab']['instagram_account_id'])
        self.assertEqual(len(self.meta.published),1)

    def test_direct_wrong_destination_is_refused_before_authorization(self):
        store,key,request,result=self.imported()
        with self.assertRaises(core.EditorialError):
            self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account='wrong-account')
        self.assertEqual(store.get_post(result['id'])['state'],'draft')
        self.assertFalse(incoming.receipt(store,key,request)['publicationAuthorized'])

    def test_direct_refuses_edited_content_and_failed_preflight_leaves_draft(self):
        store,key,request,result=self.imported()
        with patch.object(self.hub,'_ready',side_effect=core.EditorialError('Not ready')):
            with self.assertRaises(core.EditorialError):self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account=self.cfg['umdoislab']['instagram_account_id'])
        self.assertEqual(store.get_post(result['id'])['state'],'draft')
        mid=store.snapshot()['media'][0]['id']
        store.save_draft('feed','new caption',[mid],post_id=result['id'],expected_version=1)
        with self.assertRaises(core.EditorialConflict):self.hub.queue('umdoislab',result['id'],1,import_request=request,expected_account=self.cfg['umdoislab']['instagram_account_id'])
        self.assertFalse(incoming.receipt(store,key,request)['publicationAuthorized'])

    def test_direct_refuses_latest_edited_version_even_when_supplied_explicitly(self):
        store,key,request,result=self.imported()
        mid=store.snapshot()['media'][0]['id']
        store.save_draft('feed','Changed after transfer',[mid],post_id=result['id'],expected_version=1)
        latest=next(post['version'] for post in store.snapshot()['posts'] if post['id']==result['id'])
        self.assertGreater(latest,result['importedVersion'])
        with self.assertRaises(core.EditorialConflict):
            self.hub.queue('umdoislab',result['id'],latest,import_request=request,
                expected_account=self.cfg['umdoislab']['instagram_account_id'])
        self.assertFalse(incoming.receipt(store,key,request)['publicationAuthorized'])
        self.assertEqual(self.meta.published,[])


def load_tests(loader, tests, pattern):
    return unittest.TestSuite(cls(name) for cls in (IncomingHTTPTests,DirectPublicationTests)
        for name in cls.__dict__ if name.startswith('test_'))
