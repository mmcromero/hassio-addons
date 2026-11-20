"""Testes offline do núcleo editorial: sem Meta, HA, HTTP ou rede."""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from editorial_core import EditorialError, EditorialStore

PNG = b"\x89PNG\r\n\x1a\n" + b"fake-png-for-storage-test"
JPEG = b"\xff\xd8\xff" + b"fake-jpeg-for-storage-test"
MP4 = b"\x00\x00\x00\x14ftypisom" + b"fake-mp4-for-storage-test"
NOW = datetime(2026, 11, 20, 12, 0, tzinfo=timezone.utc)


class EditorialStoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = EditorialStore(Path(self.tmp.name) / "editorial")

    def _ready(self, kind="feed", count=1):
        post = self.store.create_draft(kind, "Legenda de teste")
        for index in range(count):
            binary, ext = (MP4, "mp4") if kind == "reel" else (JPEG, "jpg")
            media = self.store.add_media(binary, ext)
            self.store.attach_media(post, media, position=index)
        self.store.approve(post)
        return post

    def test_storage_and_different_database(self):
        m = self.store.add_media(PNG, "png")
        self.assertEqual(len(m), 32)
        self.assertTrue((self.store.media_dir / (m + ".png")).exists())
        self.assertEqual(self.store.db_path.name, "editorial.sqlite3")
        self.assertNotEqual(self.store.db_path.name, "instagram.sqlite3")
        self.assertEqual((self.store.media_dir / (m + ".png")).stat().st_mode & 0o777, 0o600)

    def test_mismatched_extension_rejected(self):
        with self.assertRaises(EditorialError):
            self.store.add_media(PNG, "jpg")
        with self.assertRaises(EditorialError):
            self.store.add_media(JPEG, "../../etc/passwd")

    def test_carousel_requires_two_items(self):
        post = self.store.create_draft("carousel", "Teste")
        self.store.attach_media(post, self.store.add_media(JPEG, "jpg"))
        with self.assertRaises(EditorialError):
            self.store.approve(post)
        self.store.attach_media(post, self.store.add_media(PNG, "png"), 1)
        self.store.approve(post)

    def test_reel_requires_video(self):
        post = self.store.create_draft("reel", "Teste")
        self.store.attach_media(post, self.store.add_media(JPEG, "jpg"))
        with self.assertRaises(EditorialError):
            self.store.approve(post)
        self.store.attach_media(post, self.store.add_media(MP4, "mp4"))
        self.store.approve(post)

    def test_date_must_have_timezone_and_be_future(self):
        post = self._ready()
        with self.assertRaises(EditorialError):
            self.store.schedule(post, datetime(2026, 11, 21), now=NOW)
        with self.assertRaises(EditorialError):
            self.store.schedule(post, NOW, now=NOW)
        local_time = datetime(2026, 11, 21, 9, 0, tzinfo=timezone(timedelta(hours=-3)))
        self.store.schedule(post, local_time, now=NOW)
        self.assertEqual(self.store.get_post(post)["scheduled_at"], int(local_time.timestamp()))

    def test_edit_after_approval_invalidates_schedule_and_approval(self):
        post = self._ready()
        self.store.schedule(post, NOW + timedelta(hours=1), now=NOW)
        self.store.edit_caption(post, "Novo conteúdo")
        snapshot = self.store.get_post(post)
        self.assertEqual(snapshot["state"], "draft")
        self.assertIsNone(snapshot["approved_revision"])
        self.assertIsNone(snapshot["scheduled_at"])
        with self.assertRaises(EditorialError):
            self.store.schedule(post, NOW + timedelta(hours=2), now=NOW)

    def test_claim_is_atomic_and_not_duplicated(self):
        post = self._ready()
        self.store.schedule(post, NOW + timedelta(seconds=1), now=NOW)
        self.assertIsNone(self.store.claim_due(now=NOW))
        lease = self.store.claim_due(now=NOW + timedelta(seconds=1))
        self.assertEqual(lease["id"], post)
        self.assertIsNone(self.store.claim_due(now=NOW + timedelta(seconds=2)))
        self.assertEqual(self.store.get_post(post)["state"], "leased")

    def test_expired_lease_requires_review_without_republication(self):
        post = self._ready()
        self.store.schedule(post, NOW + timedelta(seconds=1), now=NOW)
        lease = self.store.claim_due(now=NOW + timedelta(seconds=1), lease_seconds=30)
        self.assertEqual(self.store.expire_leases(now=NOW + timedelta(seconds=30)), 0)
        self.assertEqual(self.store.expire_leases(now=NOW + timedelta(seconds=31)), 1)
        self.assertEqual(self.store.get_post(post)["state"], "needs_review")
        self.assertIsNone(self.store.claim_due(now=NOW + timedelta(days=1)))
        with self.assertRaises(EditorialError):
            self.store.mark_review_required(post, lease["lease_token"])

    def test_cancel_only_scheduled(self):
        post = self._ready()
        self.store.schedule(post, NOW + timedelta(days=1), now=NOW)
        self.store.cancel_schedule(post)
        self.assertEqual(self.store.get_post(post)["state"], "approved")
        with self.assertRaises(EditorialError):
            self.store.cancel_schedule(post)

    def test_wrong_lease_token_cannot_change_state(self):
        post = self._ready()
        self.store.schedule(post, NOW + timedelta(seconds=1), now=NOW)
        lease = self.store.claim_due(now=NOW + timedelta(seconds=1))
        with self.assertRaises(EditorialError):
            self.store.mark_review_required(post, "invalid")
        self.store.mark_review_required(post, lease["lease_token"])
        self.assertEqual(self.store.get_post(post)["state"], "needs_review")

    def test_media_file_not_overwritten_and_database_survives_reopen(self):
        post = self._ready()
        reopened = EditorialStore(self.store.root)
        self.assertEqual(reopened.get_post(post)["state"], "approved")
        self.assertEqual(len(list(reopened.media_dir.glob("*.jpg"))), 1)


if __name__ == "__main__":
    unittest.main()
