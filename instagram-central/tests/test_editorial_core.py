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
        self.assertEqual(snapshot["pending_schedule_at"], int((NOW + timedelta(hours=1)).timestamp()))
        self.assertEqual(self.store.snapshot()["posts"][0]["status"], "draft")
        with self.assertRaises(EditorialError):
            self.store.schedule(post, NOW + timedelta(hours=2), now=NOW)
        # Direct reapproval restores the same reserved time, without a new schedule form.
        self.store.approve(post, now=NOW)
        restored=self.store.get_post(post)
        self.assertEqual(restored["state"], "scheduled")
        self.assertEqual(restored["scheduled_at"], int((NOW + timedelta(hours=1)).timestamp()))
        self.assertIsNone(restored["pending_schedule_at"])

    def test_edit_scheduled_twice_keeps_reserved_time_and_blocks_scheduler(self):
        post = self._ready()
        original = NOW + timedelta(days=2)
        self.store.schedule(post, original, now=NOW)
        self.store.edit_caption(post, "Revisão 1")
        self.store.edit_caption(post, "Revisão 2")
        saved = self.store.snapshot()["posts"][0]
        self.assertEqual(saved["pendingScheduledAt"], int(original.timestamp()) * 1000)
        self.assertIsNone(saved["scheduledAt"])
        self.assertIsNone(self.store.claim_due(now=original + timedelta(days=1)))
        reopened = EditorialStore(self.store.root)
        self.assertEqual(reopened.snapshot()["posts"][0]["pendingScheduledAt"], int(original.timestamp()) * 1000)
        reopened.approve(post, now=NOW)
        self.assertEqual(reopened.get_post(post)["state"], "scheduled")
        self.assertEqual(reopened.get_post(post)["scheduled_at"], int(original.timestamp()))
        reopened.cancel_schedule(post)
        self.assertIsNone(reopened.get_post(post)["pending_schedule_at"])

    def test_elapsed_reservation_is_visible_but_not_automatically_restored(self):
        post = self._ready()
        original = NOW + timedelta(hours=1)
        self.store.schedule(post, original, now=NOW)
        self.store.edit_caption(post, "Nova revisão")
        self.store.approve(post, now=NOW + timedelta(days=1))
        state = self.store.snapshot()["posts"][0]
        self.assertEqual(state["status"], "approved")
        self.assertIsNone(state["scheduledAt"])
        self.assertEqual(state["pendingScheduledAt"], int(original.timestamp()) * 1000)
        self.assertIsNone(self.store.claim_due(now=NOW + timedelta(days=2)))
        future = NOW + timedelta(days=3)
        self.store.schedule(post, future, now=NOW + timedelta(days=2))
        state = self.store.snapshot()["posts"][0]
        self.assertEqual(state["status"], "scheduled")
        self.assertEqual(state["scheduledAt"], int(future.timestamp()) * 1000)
        self.assertIsNone(state["pendingScheduledAt"])

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


    def test_carousel_slide_captions_survive_restart_and_edit_invalidates_approval(self):
        first = self.store.add_media(JPEG, "jpg")
        second = self.store.add_media(PNG, "png")
        post_id = self.store.save_draft(
            "carousel", "", [first, second],
            caption_mode="per_slide", slide_captions=["Primeira legenda", "Segunda legenda"])
        self.store.approve(post_id)
        before = self.store.snapshot()["posts"][0]
        self.assertEqual(before["captionMode"], "per_slide")
        self.assertEqual(before["slideCaptions"], ["Primeira legenda", "Segunda legenda"])
        self.store.save_draft("carousel", "", [first, second], post_id=post_id,
                              expected_version=before["version"], caption_mode="per_slide",
                              slide_captions=["Primeira legenda", "Legenda atualizada"])
        reopened = EditorialStore(self.store.root)
        after = reopened.snapshot()["posts"][0]
        self.assertEqual(after["captionMode"], "per_slide")
        self.assertEqual(after["slideCaptions"], ["Primeira legenda", "Legenda atualizada"])
        self.assertEqual(after["mediaIds"], [first, second])
        self.assertEqual(after["status"], "draft")
        self.assertIsNone(after["approvedRevision"])

    def test_per_slide_validation_rejects_invalid_inputs_without_side_effects(self):
        first = self.store.add_media(JPEG, "jpg")
        second = self.store.add_media(PNG, "png")
        invalid = [
            {"format": "feed", "mode": "per_slide", "captions": ["A"]},
            {"format": "carousel", "mode": "per_slide", "captions": ["A"]},
            {"format": "carousel", "mode": "per_slide", "captions": ["A", "B" * 2201]},
            {"format": "carousel", "mode": "general", "captions": ["A", ""]},
            {"format": "carousel", "mode": "wrong", "captions": ["", ""]},
            {"format": "carousel", "mode": "per_slide", "captions": ["A", None]}
        ]
        for case in invalid:
            with self.subTest(case=case["mode"], captions=str(case["captions"])[:22]):
                with self.assertRaises(EditorialError):
                    self.store.save_draft(case["format"], "", [first, second]
                                          if case["format"] == "carousel" else [first],
                                          caption_mode=case["mode"], slide_captions=case["captions"])
        self.assertEqual(self.store.snapshot()["posts"], [])

    def test_migration_from_previous_editorial_schema_retains_drafts(self):
        legacy_root = Path(self.tmp.name) / "legacy-0.1.7"
        legacy_root.mkdir()
        legacy_db = legacy_root / "editorial.sqlite3"
        with sqlite3.connect(legacy_db) as db:
            db.execute("""CREATE TABLE posts (
                id TEXT PRIMARY KEY, format TEXT NOT NULL, caption TEXT NOT NULL,
                revision INTEGER NOT NULL DEFAULT 1, approved_revision INTEGER,
                state TEXT NOT NULL DEFAULT 'draft', scheduled_at INTEGER,
                lease_token TEXT, lease_until INTEGER, remote_id TEXT,
                created_at INTEGER NOT NULL, version INTEGER NOT NULL DEFAULT 1)""")
            db.execute("""CREATE TABLE media (
                id TEXT PRIMARY KEY, extension TEXT NOT NULL,
                digest TEXT NOT NULL, size INTEGER NOT NULL)""")
            db.execute("""CREATE TABLE attachments (
                post_id TEXT NOT NULL REFERENCES posts(id),
                media_id TEXT NOT NULL REFERENCES media(id),
                position INTEGER NOT NULL, PRIMARY KEY(post_id,position))""")
            db.execute("INSERT INTO posts(id,format,caption,created_at) VALUES(?,?,?,?)",
                       ("a" * 32, "feed", "Rascunho anterior", 1))
            db.execute("INSERT INTO media VALUES(?,?,?,?)", ("b" * 32, "png", "digest", 10))
            db.execute("INSERT INTO attachments VALUES(?,?,?)", ("a" * 32, "b" * 32, 0))
        migrated = EditorialStore(legacy_root)
        post = migrated.snapshot()["posts"][0]
        self.assertEqual(post["caption"], "Rascunho anterior")
        self.assertEqual(post["mediaIds"], ["b" * 32])
        self.assertEqual(post["captionMode"], "general")
        self.assertEqual(post["slideCaptions"], [""])
        self.assertEqual(post["status"], "draft")
        self.assertEqual(EditorialStore(legacy_root).snapshot()["posts"][0]["id"], "a" * 32)


if __name__ == "__main__":
    unittest.main()
