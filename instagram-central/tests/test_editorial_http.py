"""Adversarial loopback checks. Only temporary SQLite/media and synthetic tenants."""
import base64
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from io import BytesIO
import importlib.util
import json
from pathlib import Path
import socket
import sqlite3
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("editorial_test_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)
import account_registry as accounts
import editorial_core as core
import editorial_http as api
import oauth_meta
import panel_login
from PIL import Image


def png():
    output = BytesIO()
    Image.new("RGB", (2, 2), "red").save(output, format="PNG")
    return output.getvalue()


class EditorialHTTPTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.old = server.DATA_DIR, server.DB_PATH, server.settings
        server.DATA_DIR = Path(self.tmp.name)
        server.DB_PATH = server.DATA_DIR / "instagram.sqlite3"
        self.cfg = {"instagram_account_id": "synthetic-1", "panel_password": "LOCAL_ONLY_panel_password_12345",
                    "meta_app_secret": "LOCAL_ONLY_SECRET", "bridge_secret": "LOCAL_ONLY_BRIDGE_" * 3,
                    "meta_verify_token": "LOCAL_ONLY_VERIFY_" * 2,
                    "ingress_enabled": False, "meta_oauth_enabled": False, "drafts_enabled": False}
        server.settings = lambda: self.cfg
        with server.database() as conn:
            accounts.ensure_primary(conn, "synthetic-1")
            accounts.register(conn, "synthetic", "synthetic-2", "synthetic", "Synthetic", enabled=True)
            self.cookie = "ig_panel_session=" + panel_login.create_session(conn, self.cfg["panel_password"])
            self.other_cookie = "ig_panel_session=" + panel_login.create_session(conn, self.cfg["panel_password"])
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()

    def tearDown(self):
        self.http.shutdown(); self.http.server_close(); self.thread.join(timeout=3)
        server.DATA_DIR, server.DB_PATH, server.settings = self.old
        self.tmp.cleanup()

    def request(self, path, method="GET", body=None, headers=None, *, cookie=True):
        conn = HTTPConnection("127.0.0.1", self.http.server_address[1], timeout=4)
        try:
            merged = {"Cookie": self.cookie} if cookie else {}
            merged.update(headers or {})
            conn.request(method, path, body=body, headers=merged)
            response = conn.getresponse()
            return response.status, dict(response.getheaders()), response.read()
        finally:
            conn.close()

    def state(self):
        status, _, body = self.request("/editorial/api/state")
        self.assertEqual(status, 200)
        return json.loads(body)

    def post(self, path, data, action, **kwargs):
        token = panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action(action))
        return self.request("/editorial/api/" + path, "POST", json.dumps(data),
                            {"Content-Type": "application/json", "X-CSRF-Token": token}, **kwargs)

    def upload(self, content=None, mime="image/png", **kwargs):
        token = panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("upload"))
        return self.request("/editorial/api/media", "POST", content if content is not None else png(),
                            {"Content-Type": mime, "X-CSRF-Token": token}, **kwargs)

    def draft(self):
        status, _, raw = self.upload()
        self.assertEqual(status, 201)
        mid = json.loads(raw)["id"]
        status, _, raw = self.post("drafts", {"format": "feed", "caption": "Local draft", "mediaIds": [mid]}, "draft")
        self.assertEqual(status, 200)
        return json.loads(raw)["id"], mid

    def test_every_resource_requires_session_even_with_bridge_or_basic(self):
        paths = ["/editorial", "/editorial/", "/editorial/editorial.js", "/editorial/editorial.css",
                 "/editorial/api/state", "/editorial/api/csrf", "/editorial/media/" + "0" * 32]
        basic = base64.b64encode(("admin:" + self.cfg["panel_password"]).encode()).decode()
        for path in paths:
            for headers in ({}, {"Authorization": "Basic " + basic}, {"X-Instagram-Bridge-Secret": self.cfg["bridge_secret"]}):
                self.assertEqual(self.request(path, headers=headers, cookie=False)[0], 403)
        with server.database() as conn:
            panel_login.revoke_session(conn, self.cookie, self.cfg["panel_password"])
        self.assertEqual(self.request("/editorial/api/state")[0], 403)

    def test_csrf_bound_to_action_session_time_and_business(self):
        good = panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("draft"))
        candidates = [None, "f" * 64,
                      panel_login.admin_csrf_token(self.other_cookie, self.cfg["panel_password"], api.csrf_action("draft")),
                      panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("upload")),
                      panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("draft"), bucket=1)]
        for candidate in candidates:
            headers = {"Content-Type": "application/json"}
            if candidate: headers["X-CSRF-Token"] = candidate
            self.assertEqual(self.request("/editorial/api/drafts", "POST", "{}", headers)[0], 403)
        self.assertFalse(panel_login.admin_csrf_valid(self.cookie, self.cfg["panel_password"], "editorial:synthetic:draft", good))
        self.assertEqual(len(self.state()["posts"]), 0)

    def test_assets_csp_and_existing_messages_navigation(self):
        status, headers, body = self.request("/editorial/")
        self.assertEqual(status, 200)
        self.assertIn("script-src 'self'", headers["Content-Security-Policy"])
        self.assertNotIn("unsafe-inline", headers["Content-Security-Policy"])
        self.assertIn(b'href="../"', body)
        self.assertIn(b'class="topbar"', body)
        self.assertIn(b'class="account">@umdoislab', body)
        self.assertIn(b'action="../auth/logout"', body)
        self.assertEqual(body.count(b'>Sair</button>'), 1)
        for asset in ("editorial.css", "editorial.js"):
            self.assertEqual(self.request("/editorial/" + asset)[0], 200)
        status, headers, body = self.request("/")
        self.assertEqual(status, 200)
        self.assertIn(b'href="editorial/"', body)
        self.assertIn("script-src 'sha256-", headers["Content-Security-Policy"])
        self.assertNotIn("script-src 'unsafe-inline'", headers["Content-Security-Policy"])
        self.assertTrue(json.loads(self.request("/panel/account-context")[2])["editorialUIIntegrated"])

    def test_editorial_logout_revokes_shared_session_without_changing_content(self):
        post_id, _ = self.draft()
        self.assertIn(b'action="../auth/logout"', self.request("/editorial/")[2])
        status, headers, _ = self.request("/auth/logout", "POST", headers={"Cookie": self.cookie})
        self.assertEqual(status, 303)
        self.assertIn("Max-Age=0", headers["Set-Cookie"])
        self.assertEqual(self.request("/editorial/api/state")[0], 403)
        self.assertEqual(self.request("/editorial/")[0], 403)
        # Session revocation never deletes local editorial data.
        stored = server.editorial_store_for_business()
        self.assertTrue(any(p["id"] == post_id for p in stored.snapshot()["posts"]))

    def test_tenant_query_body_path_and_ids_cannot_select_other_business(self):
        other = server.editorial_store_for_business("synthetic")
        other_mid = other.add_media(png(), "png")
        other_id = other.create_draft("feed", "TENANT TWO PRIVATE")
        for path in ("/editorial/api/state?business_id=synthetic", "/editorial/../server.py",
                     "/editorial/media/../../options.json", "/editorial/%2e%2e/server.py",
                     "/editorial/accounts/synthetic/api/state", "/editorial/media/" + other_mid + ".png"):
            self.assertEqual(self.request(path)[0], 404)
        self.assertEqual(self.request("/editorial/media/" + other_mid)[0], 422)
        status, _, body = self.post("drafts", {"format": "feed", "caption": "x", "mediaIds": [], "business_id": "synthetic"}, "draft")
        self.assertEqual(status, 422)
        self.assertEqual(self.post("posts/" + other_id + "/approve", {"version": 1}, "approve")[0], 409)
        self.assertNotIn("TENANT TWO PRIVATE", json.dumps(self.state()))
        self.assertEqual(other.get_post(other_id)["state"], "draft")

    def test_upload_decode_normalization_active_content_and_limits(self):
        for raw, mime in ((b"<svg onload='alert(1)'/>", "image/svg+xml"),
                          (b"<html>active</html>", "image/png"), (b"\x89PNG\r\n\x1a\nFAKE", "image/png"),
                          (png(), "image/jpeg"),
                          (base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jRZkAAAAASUVORK5CYII="), "image/png"),
                          (b"\0\0\0\x14ftypisomBAD", "video/mp4")):
            self.assertEqual(self.upload(raw, mime)[0], 422)
        status, _, body = self.upload(png() + b"<script>active tail</script>")
        self.assertEqual(status, 201)
        mid = json.loads(body)["id"]
        status, headers, content = self.request("/editorial/media/" + mid)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "image/png")
        self.assertIn("sandbox", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertNotIn(b"<script>", content)
        token = panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("upload"))
        self.assertEqual(self.request("/editorial/api/media", "POST", b"", {"Content-Length": str(api.UPLOAD_LIMIT + 1), "Content-Type": "image/png", "X-CSRF-Token": token})[0], 422)
        self.assertEqual(len(self.state()["media"]), 1)

    def test_framing_and_untrusted_json_fail_without_writes(self):
        token = panel_login.admin_csrf_token(self.cookie, self.cfg["panel_password"], api.csrf_action("draft"))
        for body in ("[]", "null", "{", '{"format":[],"caption":"x","mediaIds":[]}',
                     '{"format":"feed","caption":"x","mediaIds":[[]]}'):
            self.assertEqual(self.request("/editorial/api/drafts", "POST", body, {"Content-Type": "application/json", "X-CSRF-Token": token})[0], 422)
        # Transfer-Encoding is rejected even with a Content-Length.
        self.assertEqual(self.request("/editorial/api/drafts", "POST", "{}", {"Content-Type": "application/json", "X-CSRF-Token": token, "Transfer-Encoding": "chunked"})[0], 422)
        self.assertEqual(self.state()["posts"], [])

    def test_persist_approve_schedule_edit_invalidation_and_stale_writes(self):
        # Publishing now requires a verified account; keep this storage contract
        # offline and model only the already-checked connection prerequisites.
        for name, value in (('_ready', {'stories': True}), ('_identity', (self.cfg, {}, 'synthetic'))):
            patcher = patch.object(server.PUBLICATIONS, name, return_value=value)
            patcher.start(); self.addCleanup(patcher.stop)
        post_id, mid = self.draft()
        post = self.state()["posts"][0]
        self.assertEqual(self.post("posts/" + post_id + "/approve", {"version": post["version"]}, "approve")[0], 200)
        self.assertEqual(self.post("posts/" + post_id + "/approve", {"version": post["version"]}, "approve")[0], 409)
        approved = self.state()["posts"][0]
        local = (datetime.now(timezone.utc) + timedelta(days=2)).strftime("%Y-%m-%dT09:30")
        self.assertEqual(self.post("posts/" + post_id + "/schedule", {"version": approved["version"], "localTime": local}, "schedule")[0], 200)
        scheduled = self.state()["posts"][0]
        self.assertEqual(scheduled["scheduledAt"], int(api._schedule_time(local).timestamp()) * 1000)
        reopened = core.EditorialStore(Path(self.tmp.name) / "editorial")
        self.assertEqual(reopened.snapshot()["posts"][0], scheduled)
        self.assertEqual(reopened.read_media(mid)[1], "image/png")
        self.assertEqual(self.post("drafts", {"id": post_id, "version": scheduled["version"], "format": "story", "caption": "edited", "mediaIds": [mid]}, "draft")[0], 200)
        edited = self.state()["posts"][0]
        self.assertEqual(edited["status"], "draft")
        self.assertIsNone(edited["approvedRevision"]); self.assertIsNone(edited["scheduledAt"])
        self.assertEqual(edited["pendingScheduledAt"], scheduled["scheduledAt"])
        self.assertEqual(self.post("posts/" + post_id + "/schedule", {"version": edited["version"], "localTime": local}, "schedule")[0], 422)
        self.assertEqual(self.post("drafts", {"id": post_id, "version": scheduled["version"], "format": "feed", "caption": "stale", "mediaIds": [mid]}, "draft")[0], 409)
        self.assertEqual(self.post("posts/" + post_id + "/approve", {"version": edited["version"]}, "approve")[0], 200)
        restored = self.state()["posts"][0]
        self.assertEqual(restored["status"], "scheduled")
        self.assertEqual(restored["scheduledAt"], scheduled["scheduledAt"])
        self.assertIsNone(restored["pendingScheduledAt"])
        self.assertEqual(self.post("posts/" + post_id + "/cancel", {"version": restored["version"]}, "cancel")[0], 200)
        cancelled = self.state()["posts"][0]
        self.assertEqual(cancelled["status"], "approved")
        self.assertIsNone(cancelled["scheduledAt"])
        self.assertIsNone(cancelled["pendingScheduledAt"])

    def test_h10_past_schedule_is_rejected_in_json_without_mutating_post(self):
        post_id, _ = self.draft()
        initial = self.state()["posts"][0]
        self.assertEqual(self.post("posts/" + post_id + "/approve",
                                  {"version": initial["version"]}, "approve")[0], 200)
        approved = self.state()["posts"][0]
        old_time = (datetime.now(timezone.utc) - timedelta(days=3)).strftime("%Y-%m-%dT15:11")
        status, headers, raw = self.post("posts/" + post_id + "/schedule",
                                         {"version": approved["version"],
                                          "localTime": old_time}, "schedule")
        self.assertEqual(status, 422)
        self.assertIn("application/json", headers["Content-Type"])
        self.assertEqual(json.loads(raw)["error"], "Data deve ser futura")
        unchanged = self.state()["posts"][0]
        self.assertEqual(unchanged["status"], "approved")
        self.assertIsNone(unchanged["scheduledAt"])
        self.assertEqual(unchanged["version"], approved["version"])

    def test_two_concurrent_edits_only_one_succeeds(self):
        post_id, mid = self.draft()
        post = self.state()["posts"][0]
        def edit(caption):
            return self.post("drafts", {"id": post_id, "version": post["version"], "format": "feed", "caption": caption, "mediaIds": [mid]}, "draft")[0]
        with ThreadPoolExecutor(2) as pool:
            statuses = list(pool.map(edit, ["first", "second"]))
        self.assertEqual(sorted(statuses), [200, 409])
        self.assertEqual(self.state()["posts"][0]["revision"], post["revision"] + 1)

    def test_ambiguous_or_expired_result_cannot_be_edited_approved_or_reclaimed(self):
        post_id, _ = self.draft()
        store = server.editorial_store_for_business()
        store.approve(post_id)
        now = datetime.now(timezone.utc)
        store.schedule(post_id, now + timedelta(seconds=1), now=now)
        lease = store.claim_due(now=now + timedelta(seconds=2))
        store.mark_review_required(post_id, lease["lease_token"])
        post = self.state()["posts"][0]
        for action in ("approve", "cancel"):
            self.assertEqual(self.post("posts/" + post_id + "/" + action, {"version": post["version"]}, action)[0], 422)
        self.assertEqual(self.post("drafts", {"id": post_id, "version": post["version"], "format": "feed", "caption": "retry", "mediaIds": []}, "draft")[0], 422)
        self.assertIsNone(core.EditorialStore(store.root).claim_due(now=now + timedelta(days=2)))

    def test_media_symlink_tamper_and_storage_quota_fail_closed(self):
        _, mid = self.draft()
        store = server.editorial_store_for_business()
        path = store.media_dir / (mid + ".png")
        path.write_bytes(b"x" * path.stat().st_size)
        self.assertEqual(self.request("/editorial/media/" + mid)[0], 422)
        path.unlink(); path.symlink_to(server.DB_PATH)
        self.assertEqual(self.request("/editorial/media/" + mid)[0], 422)
        path.unlink()
        with store._tx() as db:
            db.execute("UPDATE media SET size=?", (1024 * 1024 * 1024,))
        self.assertEqual(self.upload()[0], 422)
        self.assertEqual(list(store.media_dir.iterdir()), [])

    def test_signed_webhook_never_admits_secondary_or_unknown_recipient(self):
        import hashlib
        import hmac
        self.cfg["ingress_enabled"] = True
        for recipient in ("synthetic-1", "synthetic-2", "unknown"):
            raw = json.dumps({"object": "instagram", "entry": [{"messaging": [{
                "sender": {"id": "same-customer"}, "recipient": {"id": recipient},
                "message": {"mid": "same-mid", "text": recipient}}]}]}).encode()
            signature = "sha256=" + hmac.new(self.cfg["meta_app_secret"].encode(), raw, hashlib.sha256).hexdigest()
            status, _, body = self.request("/webhook/instagram", "POST", raw,
                                           {"X-Hub-Signature-256": signature}, cookie=False)
            self.assertEqual(status, 200)
            self.assertEqual(json.loads(body)["new_text_messages"], int(recipient == "synthetic-1"))
        with server.database() as db:
            self.assertEqual(db.execute("SELECT recipient_id FROM inbound").fetchall(), [("synthetic-1",)])

    def test_credentials_separate_encrypted_files_no_fallback_and_no_secret_inheritance(self):
        one = {"business_id": "umdoislab", "account_id": "synthetic-1", "username": "umdoislab",
               "verified_at": 1, "access_token": "LOCAL_ONLY_PRIMARY_TOKEN"}
        two = {"business_id": "synthetic", "account_id": "synthetic-2", "username": "synthetic",
               "verified_at": 1, "access_token": "LOCAL_ONLY_SECONDARY_TOKEN"}
        oauth_meta.store_token(server.DATA_DIR, one)
        self.assertIsNone(server._meta_credential("synthetic"))
        self.assertFalse(server.connection_summary(server.meta_configuration_for_business("synthetic"))["tokenStored"])
        other_root = accounts.credential_root(server.DATA_DIR, "synthetic")
        oauth_meta.store_token(other_root, two)
        self.assertEqual(server._meta_credential()["access_token"], one["access_token"])
        self.assertEqual(server._meta_credential("synthetic")["access_token"], two["access_token"])
        self.assertNotIn(one["access_token"].encode(), (server.DATA_DIR / oauth_meta.TOKEN_FILENAME).read_bytes())
        self.assertNotEqual((server.DATA_DIR / oauth_meta.KEY_FILENAME).read_bytes(), (other_root / oauth_meta.KEY_FILENAME).read_bytes())
        self.cfg["new_unknown_secret"] = "MUST_NOT_INHERIT"
        secondary = server.meta_configuration_for_business("synthetic")
        for key in ("meta_app_secret", "meta_verify_token", "panel_password", "new_unknown_secret"):
            self.assertNotIn(key, secondary)
        self.assertFalse(secondary["meta_oauth_enabled"])
        oauth_meta.store_token(other_root, one)
        self.assertIsNone(server._meta_credential("synthetic"))
        wrong_context = {**one, "business_id": "synthetic"}
        self.assertFalse(server.instagram_connection.credential_status(wrong_context, self.cfg)["account_verified"])
        self.assertNotIn(one["access_token"], json.dumps(self.state()))

    def test_actual_mp4_upload_private_read_and_malformed_container_rejected(self):
        video = (ROOT / "tests" / "fixtures" / "synthetic.mp4").read_bytes()
        status, _, body = self.upload(video, "video/mp4")
        self.assertEqual(status, 201)
        mid = json.loads(body)["id"]
        status, headers, raw = self.request("/editorial/media/" + mid)
        self.assertEqual(status, 200)
        self.assertEqual(headers["Content-Type"], "video/mp4")
        self.assertEqual(raw, video)
        status, _, body = self.post("drafts", {"format": "feed", "caption": "video not allowed in feed", "mediaIds": [mid]}, "draft")
        self.assertEqual(status, 200)
        post_id = json.loads(body)["id"]
        self.assertEqual(self.post("posts/" + post_id + "/approve", {"version": 1}, "approve")[0], 422)
        self.assertEqual(self.request("/editorial/media/" + mid, cookie=False)[0], 403)
        for invalid in (video[:-1], video + b"<script>active</script>", video.replace(b"moov", b"xxxx", 1)):
            self.assertEqual(self.upload(invalid, "video/mp4")[0], 422)

    def test_expired_session_and_password_change_revoke_media(self):
        _, mid = self.draft()
        with server.database() as conn:
            conn.execute("UPDATE panel_sessions SET expires_at=1")
        self.assertEqual(self.request("/editorial/media/" + mid)[0], 403)
        self.cfg["panel_password"] += "changed"
        self.assertEqual(self.request("/editorial/api/state")[0], 403)


    def test_per_slide_api_persists_and_rejects_unsafe_payloads(self):
        media = []
        for _ in range(2):
            status, _, body = self.upload()
            self.assertEqual(status, 201)
            media.append(json.loads(body)["id"])
        payload = {"format": "carousel", "caption": "", "mediaIds": media,
                   "captionMode": "per_slide",
                   "slideCaptions": ["Imagem um", "Imagem dois"]}
        status, _, body = self.post("drafts", payload, "draft")
        self.assertEqual(status, 200)
        post_id = json.loads(body)["id"]
        entry = self.state()["posts"][0]
        self.assertEqual(entry["id"], post_id)
        self.assertEqual(entry["captionMode"], "per_slide")
        self.assertEqual(entry["slideCaptions"], ["Imagem um", "Imagem dois"])
        self.assertEqual(self.post("drafts", {**payload, "business_id": "other"}, "draft")[0], 422)
        self.assertEqual(self.post("drafts", {**payload, "slideCaptions": ["x"]}, "draft")[0], 422)
        self.assertEqual(self.post("drafts", {**payload, "slideCaptions": ["x" * 2201, "y"]}, "draft")[0], 422)
        self.assertEqual(self.post("drafts", {**payload, "captionMode": "bad"}, "draft")[0], 422)
        self.assertEqual(self.state()["posts"][0]["captionMode"], "per_slide")

    def test_large_bounded_carousel_caption_json_and_legacy_contract(self):
        media = []
        for _ in range(8):
            status, _, body = self.upload()
            self.assertEqual(status, 201)
            media.append(json.loads(body)["id"])
        captions = ["Descrição sintética "+str(i)+" "+("X" * 2100) for i in range(8)]
        payload = {"format": "carousel", "caption": "", "mediaIds": media,
                   "captionMode": "per_slide", "slideCaptions": captions}
        self.assertGreater(len(json.dumps(payload)), 16 * 1024)
        self.assertLess(len(json.dumps(payload)), 64 * 1024)
        self.assertEqual(self.post("drafts", payload, "draft")[0], 200)
        self.assertEqual(self.state()["posts"][0]["slideCaptions"], captions)
        # Previous API payloads remain valid, with implicit general caption.
        status, _, body = self.post("drafts", {"format": "feed", "caption": "Legado", "mediaIds": [media[0]]}, "draft")
        self.assertEqual(status, 200)
        post_id = json.loads(body)["id"]
        legacy = next(p for p in self.state()["posts"] if p["id"] == post_id)
        self.assertEqual(legacy["captionMode"], "general")
        self.assertEqual(legacy["slideCaptions"], [""])


class MigrationAndContextTests(unittest.TestCase):
    def test_editorial_additive_migration_preserves_existing_data(self):
        with tempfile.TemporaryDirectory() as root:
            store = core.EditorialStore(root)
            post_id = store.create_draft("feed", "legacy")
            mid = store.add_media(png(), "png")
            store.attach_media(post_id, mid)
            store.approve(post_id)
            with store._db() as db:
                db.execute("ALTER TABLE posts DROP COLUMN version")
            reopened = core.EditorialStore(root)
            self.assertEqual(reopened.get_post(post_id)["state"], "approved")
            self.assertEqual(reopened.snapshot()["posts"][0]["mediaIds"], [mid])
            self.assertEqual(reopened.snapshot()["posts"][0]["version"], 1)
            self.assertEqual(reopened.read_media(mid)[0], png())

    def test_main_database_additive_migration_preserves_legacy_and_dedup(self):
        old = server.DATA_DIR, server.DB_PATH, server.settings
        with tempfile.TemporaryDirectory() as root:
            try:
                server.DATA_DIR = Path(root); server.DB_PATH = Path(root) / "instagram.sqlite3"
                server.settings = lambda: {"instagram_account_id": "synthetic-1"}
                with sqlite3.connect(server.DB_PATH) as db:
                    db.execute("CREATE TABLE inbound(recipient_id TEXT,sender_id TEXT,message_id TEXT,message_text TEXT,received_at TEXT,PRIMARY KEY(recipient_id,sender_id,message_id))")
                    db.execute("INSERT INTO inbound VALUES('synthetic-1','customer','same-mid','legacy','2026-11-20')")
                self.assertEqual(server.primary_meta_id(), "synthetic-1")
                with server.database() as db:
                    self.assertEqual(db.execute("SELECT message_text FROM inbound").fetchone()[0], "legacy")
                    self.assertIn("processed_at", {r[1] for r in db.execute("PRAGMA table_info(inbound)")})
                    self.assertEqual(db.execute("SELECT COUNT(*) FROM instagram_accounts").fetchone()[0], 1)
            finally:
                server.DATA_DIR, server.DB_PATH, server.settings = old

    def test_oauth_state_context_and_legacy_migration(self):
        cfg = {"meta_oauth_enabled": True, "meta_app_id": "123456789", "meta_login_config_id": "987654321",
               "meta_app_secret": "LOCAL_ONLY_SECRET_FOR_TESTS", "meta_oauth_redirect_uri": "https://example.org/oauth/meta/callback",
               "meta_graph_version": "v27.0", "business_id": "umdoislab", "instagram_account_id": "synthetic-1"}
        with sqlite3.connect(":memory:") as db:
            db.execute("CREATE TABLE meta_oauth_states(digest TEXT PRIMARY KEY,expires_at INTEGER NOT NULL,consumed_at INTEGER)")
            url, _ = oauth_meta.start(db, cfg); db.commit()
            state = parse_qs(urlsplit(url).query)["state"][0]
            for change in ({"business_id": "synthetic"}, {"instagram_account_id": "synthetic-2"}):
                with self.assertRaises(oauth_meta.OAuthError):
                    with db: oauth_meta.consume_state(db, state, cfg={**cfg, **change})
            with db: oauth_meta.consume_state(db, state, cfg=cfg)
            with self.assertRaises(oauth_meta.OAuthError):
                with db: oauth_meta.consume_state(db, state, cfg=cfg)

    def test_timezone_rules_and_nonexistent_or_ambiguous_times(self):
        self.assertEqual(api._schedule_time("2026-11-23T09:30").utcoffset(), timedelta(hours=-3))
        for local in ("2018-11-04T00:30", "2019-02-16T23:30", "2026-99-22T10:00", "2026-11-23T09:30-03:00"):
            with self.assertRaises((ValueError, core.EditorialError)):
                api._schedule_time(local)


if __name__ == "__main__":
    unittest.main()
