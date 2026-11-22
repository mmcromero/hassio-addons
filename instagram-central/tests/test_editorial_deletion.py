"""Deletion of local synthetic records/bytes, with leases and shared media."""
from pathlib import Path
import unittest
from unittest.mock import patch
import editorial_core as core
import test_editorial_publishing as fixtures


class EditorialDeletionTests(unittest.TestCase):
    def setUp(self):
        self.fx = fixtures.PublishingTests(); self.fx.setUp(); self.addCleanup(self.fx.doCleanups)
        self.store = self.fx.stores['umdoislab']

    def remove(self, post, **kwargs):
        return self.store.delete_post(post, expected_version=self.fx.snapshot(post)['version'], **kwargs)

    def test_delete_post_removes_exclusive_bytes_but_preserves_shared_and_other_account(self):
        post = self.fx.draft(); snapshot = self.fx.snapshot(post); shared = snapshot['mediaIds'][0]
        second = self.store.save_draft('feed', 'Keep shared', [shared])
        exclusive = self.store.add_media(self.store.read_media(shared)[0], 'png')
        self.store.save_draft('carousel', '', [shared, exclusive], post_id=post, expected_version=snapshot['version'])
        other = self.fx.draft('second')
        result = self.remove(post, delete_unused_media=True)
        self.assertEqual(result['deletedMedia'], 1); self.assertEqual(result['keptMedia'], 1)
        self.assertGreater(result['freedBytes'], 0); self.assertEqual(result['pendingBytes'], 0)
        self.assertTrue((self.store.media_dir/(shared+'.png')).exists())
        self.assertFalse((self.store.media_dir/(exclusive+'.png')).exists())
        self.assertEqual(self.store.snapshot()['media'][0]['usageCount'], 1)
        self.assertEqual(self.store.snapshot()['posts'][0]['id'], second)
        self.assertEqual(self.fx.snapshot(other, 'second')['status'], 'approved')
        with self.store._db() as db:
            self.assertEqual(db.execute('SELECT COUNT(*) FROM audit WHERE post_id=?', (post,)).fetchone()[0], 0)
            self.assertEqual(db.execute('PRAGMA foreign_key_check').fetchall(), [])

    def test_keep_files_then_delete_from_library(self):
        post = self.fx.draft(); mid = self.fx.snapshot(post)['mediaIds'][0]
        with self.assertRaisesRegex(core.EditorialError, 'em uso'): self.store.delete_media(mid)
        result = self.remove(post)
        self.assertEqual(result['deletedMedia'], 0)
        self.assertEqual(self.store.snapshot()['media'][0]['usageCount'], 0)
        result = self.store.delete_media(mid)
        self.assertEqual(result['deletedMedia'], 1); self.assertGreater(result['freedBytes'], 0)
        self.assertEqual(self.store.snapshot(), {'posts': [], 'media': []})
        self.assertEqual(list(self.store.media_dir.iterdir()), [])

    def test_future_authorized_schedule_is_cancelled_atomically_without_remote_call(self):
        post = self.fx.draft(); self.fx.queue(post)
        self.remove(post, delete_unused_media=True)
        self.assertFalse(self.fx.hub.step('umdoislab'))
        self.assertEqual(self.fx.meta.calls, [])

    def test_worker_lease_and_unknown_remote_result_cannot_be_deleted(self):
        post = self.fx.draft(); self.fx.queue(post); self.fx.hub._claim(self.store, self.fx.now)
        with self.assertRaisesRegex(core.EditorialError, 'andamento'): self.remove(post, delete_unused_media=True)
        with self.store._tx() as db: db.execute("UPDATE posts SET state='needs_review',publication_data='{\"issued\":true}' WHERE id=?", (post,))
        with self.assertRaises(core.EditorialError): self.remove(post, delete_unused_media=True)
        self.assertEqual(len(self.store.snapshot()['media']), 1)

    def test_stale_version_cross_account_and_invalid_ids_cannot_delete(self):
        post = self.fx.draft(); version = self.fx.snapshot(post)['version']
        self.store.edit_caption(post, 'Changed')
        with self.assertRaises(core.EditorialConflict): self.store.delete_post(post, expected_version=version)
        with self.assertRaises(core.EditorialConflict):
            self.fx.stores['second'].delete_post(post, expected_version=self.fx.snapshot(post)['version'])
        for mid in ('../outside', 'f'*32, None):
            with self.assertRaises(core.EditorialError): self.store.delete_media(mid)
        self.assertEqual(len(self.store.snapshot()['posts']), 1)

    def test_failed_unlink_is_durable_and_retried_on_store_open(self):
        post = self.fx.draft(); mid = self.fx.snapshot(post)['mediaIds'][0]
        with patch.object(Path, 'unlink', side_effect=PermissionError('synthetic failure')):
            result = self.remove(post, delete_unused_media=True)
        self.assertEqual(result['freedBytes'], 0); self.assertGreater(result['pendingBytes'], 0)
        self.assertTrue((self.store.media_dir/(mid+'.png')).exists())
        self.assertEqual(self.store.snapshot()['media'], [])
        reopened = core.EditorialStore(self.store.root)
        self.assertEqual(list(reopened.media_dir.iterdir()), [])
        with reopened._db() as db: self.assertEqual(db.execute('SELECT COUNT(*) FROM media_deletions').fetchone()[0], 0)
