"""Temporary stores and simulated Meta: no real accounts or publications."""
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from io import BytesIO
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest
from urllib.parse import urlsplit

from PIL import Image
import editorial_core as core
import editorial_delivery as delivery
import editorial_graph as graph
from editorial_publishing import PublisherHub


def png():
    stream = BytesIO()
    Image.new('RGBA', (640, 800), (210, 80, 30, 160)).save(stream, 'PNG')
    return stream.getvalue()


class FakeMeta:
    def __init__(self):
        self.containers, self.calls, self.published = {}, [], []
        self.failure, self.before_failure, self.link_failure = None, False, False
        self.delivery = None

    def client(self, cfg, credential):
        backend, account = self, cfg['instagram_account_id']
        class Client:
            def profile(self): return {'id': account, 'username': cfg['instagram_expected_username'], 'account_type': 'BUSINESS'}
            def check_limit(self): pass
            def create(self, fields):
                if backend.before_failure:
                    raise graph.PublishingError('meta_rejected', code=100)
                container = str(19000000000000000 + len(backend.containers))
                for name in ('image_url', 'video_url'):
                    if name in fields and backend.delivery:
                        media = backend.delivery.read(urlsplit(fields[name]).query)
                        if media is None:
                            raise AssertionError('Meta could not download the scoped media')
                        if name == 'image_url':
                            assert media[1] == 'image/jpeg' and media[0].startswith(b'\xff\xd8\xff')
                backend.containers[container] = {'account': account, 'status': 'FINISHED'}
                backend.calls.append(('create', account, fields))
                return container
            def status(self, container):
                assert backend.containers[container]['account'] == account
                backend.calls.append(('status', account, container))
                return backend.containers[container]['status']
            def publish(self, container):
                assert backend.containers[container]['account'] == account
                backend.calls.append(('publish', account, container))
                if backend.failure == 'before':
                    raise graph.PublishingError('network_unavailable', ambiguous=True)
                backend.containers[container]['status'] = 'PUBLISHED'
                backend.published.append((account, container))
                if backend.failure == 'after':
                    raise graph.PublishingError('network_unavailable', ambiguous=True)
                return str(18000000000000000 + len(backend.published))
            def permalink(self, remote):
                if backend.link_failure:
                    raise graph.PublishingError('network_unavailable', ambiguous=True)
                return 'https://www.instagram.com/p/synthetic-post/'
        return Client()


class PublishingTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(); self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.now = 1800000000
        self.cfg = {business: {'business_id': business, 'instagram_account_id': account,
                    'instagram_expected_username': name, 'meta_app_id': '17830000000000000',
                    'meta_graph_version': 'v27.0', 'meta_app_secret': 'synthetic-only-app-secret'}
                    for business, account, name in [('umdoislab', '17841400000000001', 'umdoislab'),
                                                     ('second', '17841400000000002', 'second')]}
        self.credentials = {business: {'business_id': business, 'account_id': cfg['instagram_account_id'],
            'username': cfg['instagram_expected_username'], 'verified_at': 1,
            'access_token': 'synthetic-token-for-' + business} for business, cfg in self.cfg.items()}
        self.stores = {business: core.EditorialStore(self.root / business) for business in self.cfg}
        with self.database() as db:
            db.execute('''CREATE TABLE publication_downloads(token_hash TEXT PRIMARY KEY,
                business_id TEXT,post_id TEXT,media_id TEXT,expires_at INTEGER,revision INTEGER,run_id TEXT)''')
        self.delivery = delivery.MediaDelivery(self.database, lambda business: self.stores[business])
        self.meta = FakeMeta(); self.meta.delivery = self.delivery
        self.check_count = 0
        self.hub = self.new_hub()

    @contextmanager
    def database(self):
        db = sqlite3.connect(self.root / 'downloads.sqlite3')
        try:
            with db: yield db
        finally: db.close()

    def checker(self, cfg, credential, **kwargs):
        self.check_count += 1
        return {'origin': 'https://callback.example:8443', 'stories': True}

    def new_hub(self):
        return PublisherHub(lambda b: self.cfg[b], lambda b: self.credentials[b],
                            lambda b: self.stores[b], lambda: list(self.cfg), self.delivery,
                            api_factory=self.meta.client, checker=self.checker, clock=lambda: self.now)

    def draft(self, business='umdoislab', format='feed', caption='Legenda sintética'):
        store = self.stores[business]
        if format == 'story': caption = ''
        raw = (Path(__file__).parent/'fixtures/synthetic.mp4').read_bytes() if format == 'reel' else png()
        extension = 'mp4' if format == 'reel' else 'png'
        media = [store.add_media(raw, extension) for _ in range(2 if format == 'carousel' else 1)]
        post = store.save_draft(format, caption, media)
        store.approve(post)
        return post

    def snapshot(self, post, business='umdoislab'):
        return next(p for p in self.stores[business].snapshot()['posts'] if p['id'] == post)

    def queue(self, post, business='umdoislab', **kwargs):
        self.hub.queue(business, post, self.snapshot(post, business)['version'], **kwargs)

    def finish(self, post, business='umdoislab', *, hub=None):
        for _ in range(90):
            (hub or self.hub).step(business)
            result = self.snapshot(post, business)
            if result['status'] in ('published', 'failed', 'needs_review'): return result
            self.now += 2
        self.fail('Publication did not reach a bounded result')

    def test_all_supported_formats_complete_and_grants_are_revoked_after_publication(self):
        for format in ('feed', 'carousel', 'reel', 'story'):
            with self.subTest(format=format):
                post = self.draft(format=format); self.queue(post)
                result = self.finish(post)
                self.assertEqual(result['status'], 'published')
                self.assertTrue(result['remoteId'])
                for kind, _, fields in self.meta.calls:
                    if kind == 'create':
                        for key in ('image_url', 'video_url'):
                            if key in fields:
                                self.assertIsNone(self.delivery.read(urlsplit(fields[key]).query))
        self.assertEqual(len(self.meta.published), 4)
        types = [fields.get('media_type') for kind, _, fields in self.meta.calls if kind == 'create']
        for required in ('CAROUSEL', 'REELS', 'STORIES'): self.assertIn(required, types)

    def test_two_accounts_use_their_own_credential_media_and_state(self):
        first, second = self.draft(), self.draft('second')
        self.queue(first); self.queue(second, 'second')
        self.assertEqual(self.finish(first)['status'], 'published')
        self.assertEqual(self.finish(second, 'second')['status'], 'published')
        self.assertEqual({account for account, _ in self.meta.published},
                         {cfg['instagram_account_id'] for cfg in self.cfg.values()})
        self.assertEqual(len(self.stores['umdoislab'].snapshot()['posts']), 1)
        self.assertEqual(len(self.stores['second'].snapshot()['posts']), 1)

    def test_expired_primary_connection_does_not_block_second_account(self):
        first, second = self.draft(), self.draft('second')
        self.queue(first);self.queue(second, 'second')
        self.credentials['umdoislab'] = None
        self.assertEqual(self.finish(first)['status'], 'failed')
        self.assertIn('Conecte', self.snapshot(first)['publicationMessage'])
        self.assertEqual(self.finish(second, 'second')['status'], 'published')
        self.assertEqual({account for account, _ in self.meta.published}, {self.cfg['second']['instagram_account_id']})

    def test_schedule_survives_restart_and_waits_until_due(self):
        post = self.draft()
        self.queue(post, when=datetime.fromtimestamp(self.now + 120, timezone.utc))
        self.assertFalse(self.hub.step('umdoislab'))
        self.now += 121
        self.assertEqual(self.finish(post, hub=self.new_hub())['status'], 'published')

    def test_old_inert_schedule_requires_explicit_activation(self):
        post = self.draft(); store = self.stores['umdoislab']
        store.schedule(post, datetime.fromtimestamp(self.now + 120, timezone.utc),
                       now=datetime.fromtimestamp(self.now, timezone.utc))
        self.assertFalse(self.snapshot(post)['publishAuthorized'])
        self.assertFalse(self.hub.step('umdoislab'))
        self.queue(post, activate=True)
        self.now += 121
        self.assertEqual(self.finish(post)['status'], 'published')

    def test_cancellation_and_editing_revoke_scheduled_authorization(self):
        post = self.draft(); store = self.stores['umdoislab']
        self.queue(post, when=datetime.fromtimestamp(self.now + 120, timezone.utc))
        store.cancel_schedule(post)
        self.assertFalse(self.snapshot(post)['publishAuthorized'])
        self.queue(post, when=datetime.fromtimestamp(self.now + 120, timezone.utc))
        original = self.snapshot(post)
        store.save_draft('feed', 'Revisão alterada', original['mediaIds'], post_id=post,
                         expected_version=original['version'])
        store.approve(post, now=datetime.fromtimestamp(self.now, timezone.utc))
        self.now += 121
        self.assertFalse(self.hub.step('umdoislab'))
        self.assertEqual(self.meta.published, [])

    def test_duplicate_queue_and_concurrent_claim_do_not_duplicate(self):
        post = self.draft(); version = self.snapshot(post)['version']
        self.hub.queue('umdoislab', post, version)
        with self.assertRaises(core.EditorialConflict): self.hub.queue('umdoislab', post, version)
        with ThreadPoolExecutor(max_workers=2) as executor:
            claimed = list(executor.map(lambda _: self.hub._claim(self.stores['umdoislab'], self.now), range(2)))
        self.assertEqual(sum(item is not None for item in claimed), 1)

    def test_lost_publish_response_is_reconciled_without_second_post(self):
        self.meta.failure = 'after'
        post = self.draft(); self.queue(post)
        for _ in range(5): self.hub.step('umdoislab')
        self.assertEqual(len(self.meta.published), 1)
        self.now += 61
        self.assertEqual(self.finish(post, hub=self.new_hub())['status'], 'published')
        self.assertEqual(sum(call[0] == 'publish' for call in self.meta.calls), 1)

    def test_missing_permalink_does_not_invalidate_success(self):
        self.meta.link_failure = True
        post = self.draft(); self.queue(post)
        self.assertEqual(self.finish(post)['status'], 'published')
        self.assertEqual(len(self.meta.published), 1)

    def test_crash_after_attempt_marker_never_replays_publish(self):
        post = self.draft(); self.queue(post)
        for _ in range(3): self.hub.step('umdoislab')
        with self.stores['umdoislab']._tx() as db:
            row = db.execute('SELECT publication_data FROM posts WHERE id=?', (post,)).fetchone()
            data = json.loads(row[0]); data['issued'] = True
            db.execute("UPDATE posts SET publication_phase='confirm',publication_data=? WHERE id=?", (json.dumps(data), post))
        hub = self.new_hub()
        for _ in range(5): hub.step('umdoislab'); self.now += 61
        self.assertEqual(self.snapshot(post)['status'], 'needs_review')
        self.assertFalse(any(call[0] == 'publish' for call in self.meta.calls))

    def test_ambiguous_failure_requires_confirmation_and_reuses_container(self):
        self.meta.failure = 'before'
        post = self.draft(); self.queue(post)
        for _ in range(12): self.hub.step('umdoislab'); self.now += 61
        result = self.snapshot(post)
        self.assertEqual(result['status'], 'needs_review')
        with self.assertRaises(core.EditorialError):
            self.hub.recover('umdoislab', post, result['version'], 'reset')
        with self.assertRaises(core.EditorialError):
            self.hub.recover('umdoislab', post, result['version'], 'retry', confirmed=False)
        self.meta.failure = None
        self.hub.recover('umdoislab', post, result['version'], 'retry', confirmed=True)
        self.assertEqual(self.finish(post)['status'], 'published')
        self.assertEqual(len(self.meta.containers), 1)
        self.assertEqual(len(self.meta.published), 1)

    def test_failure_before_publish_can_return_to_draft(self):
        self.meta.before_failure = True
        post = self.draft(); self.queue(post)
        result = self.finish(post)
        self.assertEqual(result['status'], 'failed')
        self.assertIn('100', result['publicationMessage'])
        self.hub.recover('umdoislab', post, result['version'], 'reset')
        self.assertEqual(self.snapshot(post)['status'], 'draft')

    def test_account_binding_change_stops_the_job(self):
        post = self.draft(); self.queue(post)
        self.cfg['umdoislab']['instagram_account_id'] = '17841499999999999'
        self.credentials['umdoislab']['account_id'] = '17841499999999999'
        self.assertEqual(self.finish(post)['status'], 'failed')
        self.assertEqual(self.meta.calls, [])

    def test_missing_permission_and_wrong_token_never_authorize(self):
        post = self.draft()
        self.hub.checker = lambda *a, **k: (_ for _ in ()).throw(graph.PublishingError('permission_required'))
        with self.assertRaisesRegex(core.EditorialError, 'instagram_content_publish'): self.queue(post)
        self.assertFalse(self.snapshot(post)['publishAuthorized'])
        self.credentials['umdoislab'] = dict(self.credentials['second'])
        with self.assertRaises(core.EditorialError): self.queue(post)
        self.assertEqual(self.meta.calls, [])

    def test_unsupported_caption_semantics_are_not_silently_dropped(self):
        store = self.stores['umdoislab']
        mids = [store.add_media(png(), 'png') for _ in range(2)]
        post = store.save_draft('carousel', '', mids, caption_mode='per_slide', slide_captions=['um', 'dois'])
        store.approve(post)
        with self.assertRaisesRegex(core.EditorialError, 'legenda geral'): self.queue(post)
        story = self.draft(format='story')
        store.edit_caption(story, 'Não descartar esta legenda'); store.approve(story)
        with self.assertRaisesRegex(core.EditorialError, 'Story'): self.queue(story)

    def test_media_capability_expiry_scope_duplicates_and_revocation(self):
        post = self.draft(); other = self.draft('second')
        media = self.snapshot(post)['mediaIds'][0]
        url = self.delivery.issue('umdoislab', post, media, 'https://callback.example:8443', now=self.now)
        query = urlsplit(url).query
        self.assertIsNone(self.delivery.read(query, now=self.now))
        self.queue(post)
        self.assertIsNone(self.delivery.read(query, now=self.now))
        query = urlsplit(self.delivery.issue('umdoislab', post, media, 'https://callback.example:8443', now=self.now)).query
        self.assertEqual(self.delivery.read(query, now=self.now)[1], 'image/jpeg')
        self.assertIsNone(self.delivery.read(query, now=self.now + 3601))
        self.assertIsNone(self.delivery.read(query + '&' + query, now=self.now))
        wrong = self.delivery.issue('second', other, media, 'https://callback.example:8443', now=self.now)
        self.queue(other, 'second')
        self.assertIsNone(self.delivery.read(urlsplit(wrong).query, now=self.now))

    def test_old_media_grant_does_not_reactivate_after_reset_and_new_authorization(self):
        post = self.draft(); self.queue(post)
        media = self.snapshot(post)['mediaIds'][0]
        query = urlsplit(self.delivery.issue('umdoislab', post, media, 'https://callback.example', now=self.now)).query
        self.assertIsNotNone(self.delivery.read(query, now=self.now))
        self.meta.before_failure = True
        failed = self.finish(post)
        self.hub.recover('umdoislab', post, failed['version'], 'reset')
        self.stores['umdoislab'].approve(post);self.queue(post)
        self.assertIsNone(self.delivery.read(query, now=self.now))

    def test_feed_aspect_ratio_is_validated_without_silently_cropping(self):
        stream = BytesIO();Image.new('RGB', (640, 1600), 'red').save(stream, 'PNG')
        store = self.stores['umdoislab'];mid = store.add_media(stream.getvalue(), 'png')
        post = store.save_draft('feed', '', [mid]);store.approve(post)
        with self.assertRaisesRegex(core.EditorialError, 'proporção'): self.queue(post)
