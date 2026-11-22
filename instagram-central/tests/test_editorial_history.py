"""Synthetic 69-post imports, scoped metadata/files and bounded downloads."""
from io import BytesIO
from datetime import datetime, timezone
import json
import time
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

import editorial_core as core
import editorial_history as history
import editorial_graph as graph
import test_editorial_publishing as fixtures


def entry(i):
    return {'id':str(18100000000000000+i),'caption':'Publicação antiga '+str(i),
            'timestamp':f'2024-06-{i%28+1:02}T12:30:00+0000','media_type':'IMAGE','media_product_type':'FEED',
            'permalink':'https://www.instagram.com/p/synthetic'+str(i)+'/',
            'media_url':'https://scontent.cdninstagram.com/synthetic/'+str(i)+'.png',
            'like_count':i,'comments_count':0,'alt_text':'Descrição '+str(i)}


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.PublishingTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.calls=[];self.downloads=[];self.rows=[entry(i) for i in range(69)];self.deny_extra=False;self.fail_media=False
        old=self.fx.hub.api_factory
        def factory(cfg,credential):
            api=old(cfg,credential)
            def page(after=None,*,expanded=False):
                self.calls.append((cfg['instagram_account_id'],after,expanded))
                if expanded and self.deny_extra:raise graph.PublishingError('meta_rejected',code=200)
                offset=int(after or '0');rows=[dict(r) for r in self.rows[offset:offset+25]]
                if expanded:
                    for row in rows:row.update(shares_count=2,saved_count=0)
                result={'data':rows}
                if offset+25<len(self.rows):result['paging']={'next':'https://untrusted.invalid/?access_token=PRIVATE','cursors':{'after':str(offset+25)}}
                return result
            api.history_page=page;return api
        self.fx.hub.api_factory=factory
        def fetch(url):
            self.downloads.append(url)
            if self.fail_media:raise core.EditorialError('Synthetic download failure with PRIVATE URL')
            return fixtures.png(),'png'
        self.worker=history.HistoryHub(self.fx.hub,downloader=fetch)
    def finish(self,business='umdoislab',worker=None):
        worker=worker or self.worker
        for _ in range(200):
            worker.step(business);result=worker.public_state(business)
            if result['status'] not in history.ACTIVE:return result
        self.fail('History did not complete')

    def test_69_posts_paginate_download_and_reimport_without_duplicates_or_publication(self):
        self.worker.start('umdoislab');result=self.finish()
        self.assertEqual(result['status'],'completed');self.assertEqual(result['seen'],69)
        self.assertEqual(result['files'],69);self.assertEqual(len(self.calls),3)
        posts=self.fx.stores['umdoislab'].snapshot()['posts'];self.assertEqual(len(posts),69)
        self.assertTrue(all(p['status']=='published' and p['source']=='instagram' and not p['publishAuthorized'] for p in posts))
        self.assertTrue(all(len(p['mediaIds'])==1 and p['publishedAt']<1700000000000+400*86400000 for p in posts))
        self.assertTrue(all(p['metrics']['extra']=={'shares':2,'saves':0} for p in posts))
        self.assertTrue(all(p['remoteDetails']['altTexts'][0].startswith('Descrição ') for p in posts))
        self.assertNotIn('cdninstagram',json.dumps(posts));self.assertNotIn('PRIVATE',json.dumps(result))
        self.worker.start('umdoislab');again=self.finish()
        self.assertEqual(again['imported'],0);self.assertEqual(again['updated'],69)
        self.assertEqual(len(self.downloads),69);self.assertEqual(len(self.fx.stores['umdoislab'].snapshot()['posts']),69)
        self.assertEqual(self.fx.meta.published,[])
        self.assertFalse(self.worker.step('umdoislab'))

    def test_optional_permission_denial_preserves_base_history_and_zero_counts(self):
        self.deny_extra=True;self.worker.start('umdoislab',download_media=False);result=self.finish()
        self.assertEqual(result['status'],'completed');self.assertEqual(len(self.calls),4)
        self.assertIn('não disponibilizados',result['message']);self.assertEqual(self.downloads,[])
        posts=self.fx.stores['umdoislab'].snapshot()['posts'];self.assertEqual(len(posts),69)
        self.assertTrue(all(p['metrics']['comments']==0 and p['metrics']['extra']=={} for p in posts))

    def test_cancel_keeps_partial_data_and_new_job_resumes_missing_downloads(self):
        self.worker.start('umdoislab');self.worker.step('umdoislab')
        with self.assertRaises(core.EditorialConflict):self.worker.start('umdoislab')
        post=self.fx.stores['umdoislab'].snapshot()['posts'][0]
        with self.assertRaises(core.EditorialError):self.fx.stores['umdoislab'].delete_post(post['id'],expected_version=post['version'])
        self.worker.cancel('umdoislab');self.assertEqual(self.finish()['status'],'cancelled')
        self.assertEqual(len(self.fx.stores['umdoislab'].snapshot()['posts']),25)
        replacement=history.HistoryHub(self.fx.hub,downloader=self.worker.downloader)
        replacement.start('umdoislab');self.assertEqual(self.finish(worker=replacement)['seen'],69)
        self.assertEqual(len(self.fx.stores['umdoislab'].snapshot()['posts']),69)

    def test_media_failure_or_quota_keeps_history_and_can_retry_without_losing_data(self):
        self.rows=self.rows[:2];self.fail_media=True;self.worker.start('umdoislab')
        result=self.finish();self.assertEqual(result['skipped'],2)
        posts=self.fx.stores['umdoislab'].snapshot()['posts'];self.assertTrue(all(not p['mediaIds'] for p in posts))
        self.assertNotIn('PRIVATE',json.dumps(posts)+json.dumps(result))
        self.fail_media=False;self.worker.start('umdoislab');self.assertEqual(self.finish()['files'],2)
        self.assertTrue(all(p['mediaIds'] for p in self.fx.stores['umdoislab'].snapshot()['posts']))

    def test_library_quota_preserves_metadata_and_records_file_warning(self):
        self.rows=self.rows[:1];self.worker.start('umdoislab')
        with patch.object(core.EditorialStore,'add_media',side_effect=core.EditorialError('Limite da biblioteca')):
            result=self.finish()
        self.assertEqual(result['status'],'completed');self.assertEqual(result['skipped'],1)
        post=self.fx.stores['umdoislab'].snapshot()['posts'][0]
        self.assertEqual(post['mediaIds'],[]);self.assertTrue(post['remoteDetails']['mediaWarnings'])

    def test_large_video_can_use_thumbnail_with_explicit_warning(self):
        self.rows=[{**entry(1),'media_type':'VIDEO','media_product_type':'REELS',
                    'media_url':'https://scontent.cdninstagram.com/full.mp4','thumbnail_url':'https://scontent.cdninstagram.com/thumb.png'}]
        def fetch(url):
            if url.endswith('mp4'):raise core.EditorialError('Mídia acima do limite')
            return fixtures.png(),'png'
        self.worker.downloader=fetch;self.worker.start('umdoislab');self.finish()
        post=self.fx.stores['umdoislab'].snapshot()['posts'][0]
        self.assertEqual(post['format'],'reel');self.assertEqual(len(post['mediaIds']),1)
        self.assertIn('Miniatura importada',post['remoteDetails']['mediaWarnings'][0])

    def test_metadata_job_is_isolated_and_connection_change_stops_before_graph(self):
        self.worker.start('umdoislab',download_media=False)
        self.fx.credentials['umdoislab']['access_token']+='changed'
        self.assertEqual(self.finish()['status'],'failed');self.assertEqual(self.calls,[])
        self.rows=self.rows[:1];self.worker.start('second',download_media=False)
        self.assertEqual(self.finish('second')['seen'],1)
        self.assertEqual(self.fx.stores['umdoislab'].snapshot()['posts'],[])
        self.assertEqual(self.calls[0][0],self.fx.cfg['second']['instagram_account_id'])

    def test_local_publication_same_remote_id_is_not_duplicated_or_caption_overwritten(self):
        post=self.fx.draft();self.fx.queue(post);self.fx.finish(post)
        remote=self.fx.snapshot(post)['remoteId'];row=entry(1);row['id']=remote
        self.rows=[row];self.worker.start('umdoislab',download_media=False);self.finish()
        posts=self.fx.stores['umdoislab'].snapshot()['posts'];self.assertEqual(len(posts),1)
        self.assertEqual(posts[0]['caption'],'Legenda sintética');self.assertEqual(posts[0]['remoteDetails']['caption'],row['caption'])
        self.assertEqual(posts[0]['source'],'editorial')

    def test_delete_imported_record_removes_metadata_files_and_metrics_locally(self):
        self.rows=self.rows[:1];self.worker.start('umdoislab');self.finish()
        store=self.fx.stores['umdoislab'];post=store.snapshot()['posts'][0]
        store.delete_post(post['id'],expected_version=post['version'],delete_unused_media=True)
        self.assertEqual(store.snapshot()['posts'],[])
        with store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM history_media').fetchone()[0],0)
            self.assertEqual(db.execute('SELECT COUNT(*) FROM publication_metrics').fetchone()[0],0)
        self.assertEqual(self.fx.meta.published,[])

    def test_expired_lease_is_resumed_and_unexpired_lease_is_not_stolen(self):
        self.rows=self.rows[:1];self.worker.start('umdoislab',download_media=False);store=self.fx.stores['umdoislab']
        with store._tx() as db:db.execute('UPDATE history_jobs SET lease=?,lease_until=?',('other',int(time.time())+60))
        self.assertFalse(self.worker.step('umdoislab'))
        with store._tx() as db:db.execute('UPDATE history_jobs SET lease_until=0')
        self.assertEqual(self.finish()['status'],'completed')

    def test_record_rejects_missing_date_and_sanitizes_permalink(self):
        raw=entry(0);del raw['timestamp']
        with self.assertRaises(graph.PublishingError):history.record(raw,int(time.time()))
        raw=entry(0);raw['permalink']='https://attacker.invalid/p/synthetic/'
        self.assertIsNone(history.record(raw,int(time.time()))['permalink'])


class DownloadTests(unittest.TestCase):
    def test_only_fixed_https_cdn_hosts_without_credentials_are_allowed(self):
        calls=[]
        for url in ('http://scontent.cdninstagram.com/a','https://127.0.0.1/a','https://fbcdn.net.attacker.invalid/a',
                    'https://user:pass@scontent.cdninstagram.com/a','https://scontent.cdninstagram.com:25/a',
                    'https://scontent.cdninstagram.com/a?access_token=PRIVATE','https://scontent.cdninstagram.com:bad/a'):
            with self.assertRaises(core.EditorialError):history.download(url,opener=lambda *a,**k:calls.append(a))
        self.assertEqual(calls,[])
    def test_download_reuses_validation_and_never_sends_meta_bearer(self):
        raw=fixtures.png();requests=[]
        class Response(BytesIO):
            headers={'Content-Length':str(len(raw))}
        def fetch(req,**kw):requests.append(req);return Response(raw)
        content,ext=history.download('https://scontent.cdninstagram.com/synthetic.png?sig=test',opener=fetch)
        self.assertEqual(ext,'png');self.assertTrue(content.startswith(b'\x89PNG'))
        self.assertIsNone(requests[0].get_header('Authorization'));self.assertEqual(requests[0].get_method(),'GET')
        def redirect(req,**kw):raise HTTPError(req.full_url,302,'PRIVATE',{},BytesIO(b'PRIVATE'))
        with self.assertRaises(core.EditorialError):history.download('https://scontent.cdninstagram.com/a',opener=redirect)
