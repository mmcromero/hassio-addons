"""Read-only publication counts on synthetic per-account stores and Meta."""
import unittest
import editorial_core as core
import editorial_graph as graph
import test_editorial_publishing as fixtures


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.fx=fixtures.PublishingTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
    def published(self,business='umdoislab',fmt='feed'):
        post=self.fx.draft(business,format=fmt);self.fx.queue(post,business)
        self.fx.finish(post,business);return post
    def read(self,post,business='umdoislab'):
        return self.fx.hub.refresh_metrics(business,post,self.fx.snapshot(post,business)['version'])

    def test_counts_are_scoped_persistent_and_do_not_change_publication_or_version(self):
        posts={b:self.published(b) for b in self.fx.cfg}
        versions={b:self.fx.snapshot(p,b)['version'] for b,p in posts.items()}
        for business,post in posts.items():
            values=self.read(post,business)
            self.assertEqual(values['status'],'ready')
            self.assertEqual(values['likes'],12 if business=='umdoislab' else 24)
            snapshot=self.fx.snapshot(post,business)
            self.assertEqual(snapshot['version'],versions[business]);self.assertEqual(snapshot['status'],'published')
            self.assertIsNotNone(snapshot['publishedAt'])
            self.assertEqual(snapshot['metrics'],values)
            reopened=core.EditorialStore(self.fx.stores[business].root)
            self.assertEqual(reopened.snapshot()['posts'][0]['metrics'],values)
        self.assertEqual(len([c for c in self.fx.meta.calls if c[0]=='metrics']),2)
        self.assertEqual(len(self.fx.meta.published),2)

    def test_failed_read_preserves_last_success_and_does_not_claim_deleted(self):
        post=self.published();first=self.read(post);self.fx.now+=40
        self.fx.meta.metric_failure=graph.PublishingError('meta_rejected',code=100,subcode=33)
        failed=self.read(post)
        self.assertEqual(failed['status'],'error');self.assertEqual(failed['likes'],first['likes'])
        self.assertEqual(failed['checkedAt'],first['checkedAt']);self.assertGreater(failed['attemptedAt'],first['attemptedAt'])
        self.assertIn('não confirma exclusão',failed['error']);self.assertIn('100/33',failed['error'])
        self.assertEqual(self.fx.snapshot(post)['status'],'published');self.assertEqual(len(self.fx.meta.published),1)

    def test_missing_counts_are_not_replaced_with_zero(self):
        post=self.published(fmt='story');self.fx.meta.metric_values={'likes':None,'comments':0}
        values=self.read(post);self.assertIsNone(values['likes']);self.assertEqual(values['comments'],0)

    def test_unpublished_wrong_version_and_other_account_never_read_remote(self):
        post=self.fx.draft()
        with self.assertRaises(core.EditorialError):self.read(post)
        post=self.published()
        with self.assertRaises(core.EditorialConflict):self.fx.hub.refresh_metrics('umdoislab',post,0)
        with self.assertRaises(core.EditorialError):self.fx.hub.refresh_metrics('second',post,self.fx.snapshot(post)['version'])
        self.assertFalse(any(c[0]=='metrics' for c in self.fx.meta.calls))

    def test_account_rebinding_does_not_read_wrong_account(self):
        post=self.published();self.fx.cfg['umdoislab']['instagram_account_id']='17841400000000009'
        self.fx.credentials['umdoislab']['account_id']='17841400000000009'
        result=self.read(post)
        self.assertEqual(result['status'],'error');self.assertIn('identidade',result['error'])
        self.assertFalse(any(c[0]=='metrics' for c in self.fx.meta.calls))

    def test_inflight_duplicate_is_blocked_and_deletion_cascades_metric_cache(self):
        post=self.published()
        def duplicate():
            with self.assertRaises(core.EditorialConflict):self.read(post)
        self.fx.meta.metric_callback=duplicate
        self.assertEqual(self.read(post)['status'],'ready')
        store=self.fx.stores['umdoislab'];store.delete_post(post,expected_version=self.fx.snapshot(post)['version'])
        with store._db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM publication_metrics').fetchone()[0],0)
        self.assertEqual(len([c for c in self.fx.meta.calls if c[0]=='metrics']),1)

    def test_delete_while_reading_does_not_recreate_post_or_orphan_metrics(self):
        post=self.published();store=self.fx.stores['umdoislab']
        self.fx.meta.metric_callback=lambda:store.delete_post(post,expected_version=self.fx.snapshot(post)['version'])
        with self.assertRaises(core.EditorialConflict):self.read(post)
        self.assertEqual(store.snapshot()['posts'],[])
        with store._db() as db:self.assertEqual(db.execute('SELECT COUNT(*) FROM publication_metrics').fetchone()[0],0)
