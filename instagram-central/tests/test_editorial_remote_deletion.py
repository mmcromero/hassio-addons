"""Synthetic DELETEs only: ownership, durable receipts, failure and retry boundaries."""
import io
import json
import unittest
from unittest.mock import patch
from urllib.error import URLError

import editorial_core as core
import editorial_graph as graph
import editorial_history as history
import test_editorial_publishing as fixtures


class RemoteDeletionTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.PublishingTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)
        self.store = self.fx.stores['umdoislab']; self.calls = []; self.failure = None
        self.preflight_failure = None; self.owner_failure = None; self.callback = None
        self.post = self.fx.draft(); self.fx.queue(self.post); self.fx.finish(self.post)
        self.snap = self.fx.snapshot(self.post)
        self.data = dict(version=self.snap['version'], deleteUnusedMedia=True,
            instagramAccountId=self.fx.cfg['umdoislab']['instagram_account_id'],
            remoteId=self.snap['remoteId'], confirmRemote=True, retryUncertain=False)
        test = self
        class API:
            def check_delete(self, cfg, credential):
                test.calls.append(('permission', cfg['instagram_account_id']))
                if test.preflight_failure: raise test.preflight_failure
            def check_media_owner(self, remote):
                test.calls.append(('owner', remote))
                if test.owner_failure: raise test.owner_failure
            def delete_media(self, remote):
                test.calls.append(('delete', remote))
                if test.callback: test.callback()
                if test.failure: raise test.failure
                return True
        self.fx.hub.api_factory = lambda cfg, cred: API()

    def delete(self, **updates):
        return self.fx.hub.delete_remote('umdoislab', self.post, {**self.data, **updates})

    def test_confirmed_delete_receipt_survives_restart_and_duplicate_does_not_call_meta(self):
        result = self.delete()
        self.assertTrue(result['deleted']); self.assertTrue(result['remoteDeleted'])
        self.assertEqual(self.store.snapshot(), {'posts': [], 'media': []})
        self.assertEqual([c[0] for c in self.calls], ['permission','owner','delete'])
        self.fx.stores['umdoislab'] = core.EditorialStore(self.store.root)
        self.assertTrue(self.delete()['deleted']); self.assertEqual(len(self.calls), 3)

    def test_local_only_calls_no_meta_and_retains_remote_post_semantics(self):
        self.store.delete_post(self.post, expected_version=self.data['version'], delete_unused_media=True)
        self.assertEqual(self.calls, [])

    def test_wrong_scope_or_confirmation_never_calls_meta(self):
        for value in ({'instagramAccountId':self.fx.cfg['second']['instagram_account_id']},
                      {'remoteId':'18000000000009999'}, {'version':1}, {'confirmRemote':False}, {'retryUncertain':'yes'}, {'extra':True}):
            with self.subTest(value=value), self.assertRaises((core.EditorialError,graph.PublishingError)):
                self.delete(**value)
        self.assertEqual(self.calls, [])
        with self.assertRaises(core.EditorialError): self.fx.hub.delete_remote('second',self.post,self.data)

    def test_permission_refusal_keeps_record_bytes_and_allows_local_choice(self):
        self.preflight_failure = graph.PublishingError('delete_permission_required')
        result = self.delete()
        self.assertIn('instagram_manage_contents', result['error']); self.assertFalse(result['deleted'])
        self.assertEqual([c[0] for c in self.calls], ['permission'])
        self.assertEqual(len(self.store.snapshot()['media']), 1)
        self.store.delete_post(self.post, expected_version=self.data['version'])

    def test_definite_meta_refusal_preserves_local_and_reports_code(self):
        self.failure = graph.PublishingError('meta_rejected',code=200,stage='delete')
        result = self.delete(); self.assertEqual(result['status'],'refused')
        self.assertIn('200',result['error']); self.assertEqual(len(self.store.snapshot()['posts']),1)
        self.assertEqual(self.fx.snapshot(self.post)['remoteDeletion']['status'],'refused')

    def test_uncertain_result_is_durable_and_requires_explicit_delayed_retry(self):
        self.failure = graph.PublishingError('network_unavailable',ambiguous=True)
        self.assertEqual(self.delete()['status'], 'unknown')
        with self.assertRaises(core.EditorialError):
            self.store.delete_post(self.post, expected_version=self.data['version'])
        self.failure = None
        for explicit, elapsed in ((False,100),(True,0)):
            old = self.fx.now; self.fx.now += elapsed
            self.assertEqual(self.delete(retryUncertain=explicit)['status'],'unknown'); self.fx.now = old
        self.assertEqual(sum(c[0]=='delete' for c in self.calls),1)
        self.fx.now += 61
        self.assertTrue(self.delete(retryUncertain=True)['deleted'])
        self.assertEqual(sum(c[0]=='delete' for c in self.calls),2)

    def test_pending_request_reloaded_is_not_automatically_repeated(self):
        with self.store._tx() as db:
            db.execute("INSERT INTO remote_deletions VALUES(?,?,?,?,?,'issued',?,'')",
                (self.post,self.data['remoteId'],self.data['instagramAccountId'],self.data['version'],'synthetic-operation',self.fx.now))
        self.assertEqual(self.delete()['status'],'unknown'); self.assertEqual(self.calls,[])

    def test_missing_remote_on_retry_does_not_prove_deletion(self):
        self.failure = graph.PublishingError('network_unavailable',ambiguous=True); self.delete()
        self.fx.now += 61; self.owner_failure = graph.PublishingError('meta_rejected',code=100)
        result = self.delete(retryUncertain=True)
        self.assertFalse(result['remoteDeleted']); self.assertEqual(len(self.store.snapshot()['posts']),1)
        self.assertEqual(sum(c[0]=='delete' for c in self.calls),1)

    def test_success_followed_by_local_failure_resumes_without_another_delete(self):
        with patch.object(self.store,'delete_post',side_effect=core.EditorialError('synthetic storage failure')):
            result = self.delete()
        self.assertTrue(result['remoteDeleted']); self.assertFalse(result['deleted'])
        self.assertEqual(self.fx.snapshot(self.post)['remoteDeletion']['status'],'confirmed')
        self.assertTrue(self.delete()['deleted']); self.assertEqual(sum(c[0]=='delete' for c in self.calls),1)

    def test_duplicate_click_and_local_delete_during_remote_request_are_blocked(self):
        def pending():
            with self.assertRaises(core.EditorialConflict): self.delete()
            with self.assertRaises(core.EditorialError):
                self.store.delete_post(self.post,expected_version=self.data['version'])
        self.callback = pending
        self.assertTrue(self.delete()['deleted']); self.assertEqual(sum(c[0]=='delete' for c in self.calls),1)

    def test_second_coordinator_winning_preflight_cannot_cause_a_duplicate_delete(self):
        original=self.fx.hub.api_factory
        other=self.fx.new_hub();other.api_factory=original
        def factory(cfg,credential):
            api=original(cfg,credential);read=api.check_media_owner
            def owner(remote):
                read(remote)
                self.assertTrue(other.delete_remote('umdoislab',self.post,self.data)['deleted'])
            api.check_media_owner=owner
            return api
        self.fx.hub.api_factory=factory
        with self.assertRaises(core.EditorialConflict):self.delete()
        self.assertEqual(sum(c[0]=='delete' for c in self.calls),1)

    def test_confirmed_receipt_blocks_stale_history_reimport(self):
        self.delete()
        h = history.HistoryHub(self.fx.hub)
        with self.store._tx() as db:
            db.execute("INSERT INTO history_jobs VALUES(1,'job','running','{}','lease',?)",(self.fx.now+100,))
        with patch.object(h,'_guard'):
            self.assertFalse(h._upsert(self.store,dict(id=self.data['remoteId'],caption='',timestamp=self.fx.now,kind='IMAGE',permalink=None),
                                      self.data['instagramAccountId'],'job','lease'))
        self.assertEqual(self.store.snapshot()['posts'], [])

    def test_remote_delete_preserves_shared_media_and_other_account(self):
        mid = self.snap['mediaIds'][0]
        other = self.store.save_draft('feed','Keep',[mid]); second = self.fx.draft('second')
        result = self.delete(); self.assertEqual(result['keptMedia'],1)
        self.assertEqual(self.store.snapshot()['posts'][0]['id'],other)
        self.assertEqual(self.fx.snapshot(second,'second')['status'],'approved')

    def test_feed_story_reel_and_entire_carousel_use_the_stored_parent_id(self):
        for index, kind in enumerate(('feed','story','reel','carousel')):
            post=self.fx.draft(format=kind)
            remote=str(18000000000001000+index)
            with self.store._tx() as db:
                db.execute("UPDATE posts SET state='published',remote_id=?,publication_account_id=? WHERE id=?",(remote,self.data['instagramAccountId'],post))
            snap=next(p for p in self.store.snapshot()['posts'] if p['id']==post)
            result=self.fx.hub.delete_remote('umdoislab',post,{**self.data,'version':snap['version'],'remoteId':remote})
            self.assertTrue(result['remoteDeleted'])
        self.assertEqual([c[1] for c in self.calls if c[0]=='delete'],[str(18000000000001000+i) for i in range(4)])


class DeleteGraphTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.PublishingTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)
        self.cfg = self.fx.cfg['umdoislab']; self.cred = self.fx.credentials['umdoislab']; self.requests=[]
        self.remote='18000000000000001'; self.response={'success':True,'deleted_id':self.remote}
        def opener(request,timeout):
            self.requests.append(request)
            if isinstance(self.response, Exception): raise self.response
            return io.BytesIO(json.dumps(self.response).encode())
        self.api=graph.PublishingAPI(self.cfg,self.cred,opener=opener)

    def test_delete_fixed_host_header_and_exact_response(self):
        self.assertTrue(self.api.delete_media(self.remote))
        r=self.requests[0];self.assertEqual(r.get_method(),'DELETE')
        self.assertEqual(r.full_url,'https://graph.facebook.com/v27.0/'+self.remote)
        self.assertNotIn(self.cred['access_token'],r.full_url);self.assertIsNone(r.data)
        for response in ({'success':False}, {'success':1}, {'success':True,'deleted_id':'99999999'}):
            self.response=response
            with self.assertRaises(graph.PublishingError) as error:self.api.delete_media(self.remote)
            self.assertTrue(error.exception.ambiguous)

    def test_unexpected_transport_failure_is_uncertain(self):
        self.response=URLError('synthetic private body')
        with self.assertRaises(graph.PublishingError) as error:self.api.delete_media(self.remote)
        self.assertTrue(error.exception.ambiguous);self.assertNotIn('private',str(error.exception))

    def test_live_ownership_never_accepts_another_account_or_missing_identity(self):
        self.response={'id':self.remote,'owner':{'id':self.api.account}}
        self.api.check_media_owner(self.remote)
        for owner in ('99999999',None):
            self.response={'id':self.remote,'owner':owner}
            with self.assertRaises(graph.PublishingError):self.api.check_media_owner(self.remote)
        self.assertTrue(all(r.get_method()=='GET' for r in self.requests))

    def test_required_permission_app_and_validity_are_checked_without_delete(self):
        good={'is_valid':True,'app_id':self.cfg['meta_app_id'],'scopes':['instagram_basic','instagram_manage_contents']}
        for info in (good,{**good,'is_valid':False},{**good,'app_id':'99999999'},{**good,'scopes':['instagram_basic']}):
            with patch.object(graph.connection,'request_graph',return_value={'data':info}):
                if info is good:self.api.check_delete(self.cfg,self.cred)
                else:
                    with self.assertRaises(graph.PublishingError):self.api.check_delete(self.cfg,self.cred)
        self.assertEqual(self.requests,[])

    def test_username_fallback_compares_the_live_bound_profile(self):
        def opener(request,timeout):
            value=({'id':self.remote,'username':'CURRENT_NAME'} if request.full_url.split('?')[0].endswith(self.remote)
                   else {'id':self.api.account,'username':'current_name'})
            return io.BytesIO(json.dumps(value).encode())
        self.api.opener=opener;self.api.check_media_owner(self.remote)
        self.api.opener=lambda request,timeout:io.BytesIO(json.dumps({'id':self.remote,'username':'other'}).encode())
        with self.assertRaises(graph.PublishingError):self.api.check_media_owner(self.remote)


if __name__=='__main__':unittest.main()
