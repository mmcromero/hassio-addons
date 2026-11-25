"""Contratos HTTP e isolamento multicontas, somente contas/dados sintéticos."""
import importlib.util
import io
import json
import os
import sqlite3
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timezone, timedelta
from pathlib import Path
from unittest.mock import patch

from accounts import Account, AccountRegistry, DEFAULT_ACCOUNT_ID, database_path
from evolution_history import make_page_reader, collect_both
from outgoing_verification import verify_outgoing
from n8n_outbox import counts, claim, put, cancel_for_manual, deliver_one
from recovery_worker import recover_one
from recovery_reconcile import evaluate

SENDER = '5511999999999@s.whatsapp.net'


class MultiAccountTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.base = Path(self.tmp.name)
        self.env = patch.dict(os.environ, {'CENTRAL_DATA_DIR': str(self.base),
                              'CENTRAL_OPTIONS': str(self.base/'options.json'),
                              'CENTRAL_LAB_NO_WHATSAPP': '0'})
        self.env.start()
        spec = importlib.util.spec_from_file_location('multi_test_server', Path(__file__).with_name('server.py'))
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        def account(ident, instance, secret):
            return Account(ident, instance, instance, 'business_' + ident,
                           database_path(self.base, ident), {
                               'bridge_secret': secret*32,
                               'evolution_webhook_secret': (secret.upper())*32,
                               'evolution_url': 'http://evolution.invalid',
                               'evolution_instance': instance,
                               'evolution_api_key': 'synthetic-' + ident,
                               'auto_test_sender': SENDER})
        self.a = account(DEFAULT_ACCOUNT_ID, 'umdoislab', 'a')
        self.b = account('synthetic_b', 'synthetic', 'b')
        self.mod.ACCOUNTS = AccountRegistry([self.a, self.b])
        self.mod.init(self.a)
        self.mod.init(self.b)
        self.network = patch.object(self.mod.urllib.request, 'urlopen', side_effect=AssertionError('Rede externa proibida no teste'))
        self.network.start()

    def tearDown(self):
        self.network.stop()
        self.env.stop()
        self.tmp.cleanup()

    def event(self, account=None, **extra):
        account = account or self.a
        return {'instance': account.instance, 'senderId': SENDER, 'messageId': 'same-id',
                'isClientMessage': True, 'isGroup': False, 'messageText': account.instance,
                'handoffRequested': False, **extra}

    def http(self, path, body=None, *, account=None, token=None, ingress=True, method='POST', xhr=True):
        handler = self.mod.Handler.__new__(self.mod.Handler)
        raw = json.dumps(body).encode() if body is not None else b''
        handler.path = path
        handler.headers = {'Authorization': token if token is not None else 'Bearer ' + (account or self.a).config['bridge_secret'],
                           'Content-Length': str(len(raw))}
        if xhr:
            handler.headers['X-Requested-With'] = 'UmdoislabCentral'
        handler.rfile = io.BytesIO(raw)
        handler.ingress = lambda: ingress
        handler.respond = lambda code, data: (code, data)
        return handler.do_GET() if method == 'GET' else handler.do_POST()

    def count(self, account, table):
        with self.mod.connect(account) as db:
            return db.execute('SELECT COUNT(*) FROM ' + table).fetchone()[0]

    def test_production_registers_only_umdoislab(self):
        self.mod.ACCOUNTS = None
        self.assertEqual(self.mod.account_registry().available(), [{
            'account_id': DEFAULT_ACCOUNT_ID, 'instance': 'umdoislab',
            'display_name': 'Umdoislab', 'business_id': 'business_001'}])

    def test_unknown_account_disabled_and_instance(self):
        for ident in ('unknown', '../data', '%2e%2e', '', 'a/b'):
            self.assertIsNone(self.mod.ACCOUNTS.resolve(account_id=ident))
        self.assertIsNone(self.mod.ACCOUNTS.resolve(instance='other'))
        self.assertIsNone(AccountRegistry([replace(self.b, enabled=False)]).resolve(instance='synthetic'))
        self.assertIsNone(self.mod.ACCOUNTS.resolve(instance=[]))

    def test_paths_and_symlinks_rejected(self):
        for ident in ('../x', '/tmp/x', 'a/b', 'a%2fb', '..', 'A'):
            with self.assertRaises(ValueError):
                database_path(self.base, ident)
        outside = self.base/'outside'
        outside.mkdir()
        (self.base/'accounts'/'evil').symlink_to(outside, target_is_directory=True)
        with self.assertRaises(ValueError):
            database_path(self.base, 'evil')
        with self.assertRaises(ValueError):
            self.mod.connect(replace(self.b, database=self.a.database))

    def test_registry_rejects_duplicate_identity_database_instance_and_secret(self):
        for bad in (replace(self.b, account_id=self.a.account_id),
                    replace(self.b, database=self.a.database),
                    replace(self.b, instance=self.a.instance, config={}),
                    replace(self.b, config={'bridge_secret': self.a.config['bridge_secret']})):
            with self.assertRaises(ValueError):
                AccountRegistry([self.a, bad])

    def test_config_is_immutable_and_secrets_never_public(self):
        with self.assertRaises(TypeError):
            self.a.config['bridge_secret'] = 'wrong'
        public = json.dumps(self.mod.ACCOUNTS.available()) + repr(self.a)
        for key in ('bridge_secret', 'evolution_api_key', self.a.config['bridge_secret'], str(self.a.database)):
            self.assertNotIn(key, public)

    def test_same_person_and_message_have_independent_context(self):
        for a in (self.a, self.b):
            self.assertEqual(self.mod.process_inbound(self.event(a), account=a)['action'], 'auto')
            self.assertEqual(self.mod.process_inbound(self.event(a), account=a)['action'], 'ignore')
        for a in (self.a, self.b):
            code, data = self.http('/bridge/context', self.event(a), account=a)
            self.assertEqual(code, 200)
            self.assertEqual(data['turns'], [{'role': 'client', 'text': a.instance}])

    def test_context_legacy_without_instance_only_original(self):
        self.mod.process_inbound(self.event())
        body = {'senderId': SENDER, 'messageId': 'same-id'}
        self.assertEqual(self.http('/bridge/context', body)[0], 200)
        self.assertEqual(self.http('/accounts/synthetic_b/bridge/context', body, account=self.b)[0], 422)
        self.assertEqual(self.http('/bridge/context', body, account=self.b)[0], 403)

    def test_no_default_for_ambiguous_or_unknown_events(self):
        for route in ('inbound', 'decision', 'send-auto', 'events', 'outgoing-observation'):
            for value in (None, '', 'unknown', [], 1):
                body = self.event(instance=value)
                self.assertIn(self.http('/bridge/' + route, body)[0], (403, 422))
        self.assertEqual(self.count(self.a, 'inbound_ids'), 0)
        self.assertEqual(self.count(self.b, 'inbound_ids'), 0)

    def test_foreign_secret_never_authorizes_other_account_routes(self):
        for route in ('inbound', 'decision', 'send-auto', 'events', 'context', 'outgoing-observation'):
            for a, other in ((self.a, self.b), (self.b, self.a)):
                self.assertEqual(self.http('/bridge/' + route, self.event(other), account=a)[0], 403)
                self.assertEqual(self.http('/accounts/' + other.account_id + '/bridge/' + route,
                                           self.event(other), account=a)[0], 403)

    def test_no_secret_never_authorizes(self):
        self.mod.ACCOUNTS = AccountRegistry([replace(self.a, config={})])
        self.assertEqual(self.http('/bridge/inbound', self.event(), token='Bearer ')[0], 403)
        self.assertEqual(self.count(self.a, 'inbound_ids'), 0)

    def test_payload_cannot_choose_arbitrary_account(self):
        body = self.event(account_id=self.b.account_id)
        self.assertEqual(self.http('/bridge/inbound', body)[0], 422)
        self.assertIsNone(self.mod.process_inbound(body, account=self.a))
        self.assertIsNone(self.mod.process_inbound(self.event(self.b), account=self.a))

    def test_policies_and_exclusions_are_independent(self):
        self.mod.update_contacts('excluded', [SENDER], self.a)
        self.assertFalse(self.mod.routing_decision(self.a.instance, SENDER, self.a)['allowAutoReply'])
        self.assertTrue(self.mod.routing_decision(self.b.instance, SENDER, self.b)['allowAutoReply'])
        for mode in ('all', 'tests', 'new'):
            self.assertEqual(self.http('/api/policy/mode', {'mode': mode})[0], 409 if mode == 'new' else 200)
        with self.mod.connect(self.b) as db:
            self.assertEqual(self.mod.get_policy(db)['mode'], 'tests')
            self.assertEqual(db.execute('SELECT COUNT(*) FROM known_contacts').fetchone()[0], 0)
        self.assertEqual(self.http('/api/policy/remove', {'number': SENDER, 'category': 'excluded'})[0], 200)
        self.assertTrue(self.mod.routing_decision(self.a.instance, SENDER, self.a)['allowAutoReply'])

    def test_all_ingress_data_and_mutations_scoped(self):
        for a in (self.a, self.b):
            self.mod.store_event(self.event(a, handoffRequested=True, summary=a.instance), account=a)
        for a in (self.a, self.b):
            prefix = '/accounts/' + a.account_id
            code, data = self.http(prefix + '/api/conversations', method='GET')
            self.assertEqual(code, 200)
            self.assertEqual([r['summary'] for r in data['items']], [a.instance])
            code, data = self.http(prefix + '/api/conversations/' + SENDER, method='GET')
            self.assertEqual(code, 200)
            self.assertEqual(data['item']['summary'], a.instance)
        for action, expected in (('assume', 'human'), ('resolve', 'done'), ('reopen', 'pending')):
            code, data = self.http('/api/conversations/' + SENDER + '/' + action, {})
            self.assertEqual((code, data['status']), (200, expected))
            self.assertEqual(self.mod.routing_decision(self.b.instance, SENDER, self.b)['state'], 'pending')

    def test_ingress_and_xhr_required_on_scoped_routes(self):
        for prefix in ('', '/accounts/synthetic_b'):
            for route in ('/api/conversations', '/api/policy', '/api/accounts'):
                self.assertEqual(self.http(prefix+route, method='GET', ingress=False)[0], 403)
            for route in ('/api/policy/mode', '/api/policy/contacts', '/api/policy/remove',
                          '/api/policy/baseline', '/api/conversations/'+SENDER+'/assume'):
                self.assertEqual(self.http(prefix+route, {}, xhr=False)[0], 403)

    def test_account_listing_only_safe_metadata(self):
        code, result = self.http('/api/accounts', method='GET')
        self.assertEqual(code, 200)
        self.assertEqual(result['items'], self.mod.ACCOUNTS.available())
        self.assertNotIn('secret', json.dumps(result))
        self.assertEqual(self.http('/accounts/unknown/api/accounts', method='GET')[0], 404)

    def test_scoped_route_rejects_conflicting_instance(self):
        self.assertEqual(self.http('/accounts/synthetic_b/bridge/inbound', self.event(), account=self.b)[0], 422)
        self.assertEqual(self.count(self.a, 'inbound_ids'), 0)
        self.assertEqual(self.count(self.b, 'inbound_ids'), 0)

    def test_same_request_id_and_automatic_output_independent(self):
        class Success:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, limit):
                return json.dumps({'key': {'id': 'same-bot-id', 'remoteJid': SENDER, 'fromMe': True}}).encode()
        with patch.object(self.mod.urllib.request, 'urlopen', return_value=Success()) as send:
            for a in (self.a, self.b):
                req = self.event(a, text='Resposta de teste')
                self.assertEqual(self.http('/bridge/send-auto', req, account=a)[0], 200)
                self.assertTrue(send.call_args.args[0].full_url.endswith('/message/sendText/'+a.instance))
                self.assertEqual(send.call_args.args[0].get_header('Apikey'), a.config['evolution_api_key'])
                self.assertEqual(self.http('/bridge/send-auto', req, account=a)[0], 409)
        for a in (self.a, self.b):
            self.assertEqual(self.count(a, 'replies'), 1)
            self.assertEqual(self.count(a, 'bot_outbound_ids'), 1)
        self.assertEqual(self.count(self.a, 'outgoing_observations'), 0)

    def test_manual_same_request_id_keeps_human_state_and_destination(self):
        reqid = '00000000-0000-0000-0000-000000000001'
        class Success:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return b'{}'
        with patch.object(self.mod.urllib.request, 'urlopen', return_value=Success()) as send:
            for a in (self.a, self.b):
                self.mod.store_event(self.event(a, handoffRequested=True), account=a)
                body = {'text': a.instance, 'requestId': reqid}
                path = '/accounts/' + a.account_id + '/api/conversations/' + SENDER + '/reply'
                self.assertEqual(self.http(path, body)[0], 200)
                self.assertTrue(send.call_args.args[0].full_url.endswith('/'+a.instance))
                self.assertEqual(self.http(path, body)[0], 409)
                self.assertEqual(self.mod.routing_decision(a.instance, SENDER, a)['state'], 'human')
        self.assertEqual(self.count(self.a, 'replies'), 1)
        self.assertEqual(self.count(self.b, 'replies'), 1)

    def test_outgoing_observation_isolated_and_authenticated_against_own_instance(self):
        with self.mod.connect(self.a) as db:
            db.execute('INSERT INTO bot_outbound_ids VALUES(?,?,?)', (SENDER, 'same-id', self.mod.now()))
        with patch.object(self.mod, 'verify_outgoing', return_value=True) as verify:
            for a, expected in ((self.a, 'bot'), (self.b, 'uncertain')):
                code, result = self.http('/bridge/outgoing-observation', self.event(a, fromMe=True), account=a)
                self.assertEqual((code, result['classification']), (200, expected))
                self.assertIs(verify.call_args.kwargs['account'], a)
                self.assertEqual(verify.call_args.kwargs['instance'], a.instance)
        self.assertEqual(self.mod.routing_decision(self.a.instance, SENDER, self.a)['state'], 'none')
        self.assertEqual(self.mod.routing_decision(self.b.instance, SENDER, self.b)['state'], 'human')

    def test_legacy_database_reused_after_restart(self):
        self.mod.process_inbound(self.event(handoffRequested=True))
        before = self.a.database.stat().st_ino
        self.mod.init(self.a)
        self.assertEqual(self.a.database, self.base/'central.sqlite3')
        self.assertEqual(self.a.database.stat().st_ino, before)
        self.assertEqual(self.mod.routing_decision(self.a.instance, SENDER, self.a)['state'], 'pending')
        self.assertEqual(self.mod.process_inbound(self.event())['action'], 'ignore')

    def test_parallel_identical_requests_and_human_other_account(self):
        self.mod.store_event(self.event(handoffRequested=True), account=self.a)
        barrier = threading.Barrier(3)
        def receive():
            barrier.wait()
            return self.mod.process_inbound(self.event(self.b), account=self.b)['action']
        def assume():
            barrier.wait()
            return self.http('/api/conversations/'+SENDER+'/assume', {})[0]
        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = [pool.submit(receive), pool.submit(receive), pool.submit(assume)]
            self.assertCountEqual([f.result(timeout=5) for f in futures], ['auto', 'ignore', 200])
        self.assertEqual(self.mod.routing_decision(self.a.instance, SENDER, self.a)['state'], 'human')
        self.assertEqual(self.mod.routing_decision(self.b.instance, SENDER, self.b)['state'], 'none')
        self.assertEqual(self.count(self.b, 'inbound_ids'), 1)

    def test_queue_payload_and_cancellation_belong_to_account(self):
        for a in (self.a, self.b):
            self.mod.process_inbound(self.event(a), enqueue=True, account=a)
        with self.mod.connect(self.a) as da, self.mod.connect(self.b) as db:
            cancel_for_manual(da, SENDER)
            self.assertEqual(counts(da), {'rejected': 1})
            item = claim(db, account=self.b)
            self.assertEqual((item['account_id'], item['instance']), (self.b.account_id, self.b.instance))
            with self.assertRaises(ValueError):
                claim(db, account=self.a)

    def test_poisoned_queue_never_dispatched_to_other_instance(self):
        self.mod.process_inbound(self.event(self.b), enqueue=True, account=self.b)
        with self.mod.connect(self.b) as db:
            db.execute('UPDATE n8n_outbox SET payload_json=?', (json.dumps(self.event()),))
            self.assertIsNone(claim(db, account=self.b))
            self.assertEqual(counts(db), {'uncertain': 1})
            with self.assertRaises(ValueError):
                put(db, self.event(), {'action': 'auto'}, account=self.b)

    def test_evolution_readers_reject_wrong_instance_key_and_context(self):
        cfg = self.b.config
        for changes in ({'instance': self.a.instance}, {'api_key': self.a.config['evolution_api_key']}):
            args = dict(base_url=cfg['evolution_url'], instance=self.b.instance,
                        api_key=cfg['evolution_api_key'], sender=SENDER, account=self.b)
            args.update(changes)
            with self.assertRaises(ValueError): make_page_reader(**args)
            args.pop('sender')
            self.assertFalse(verify_outgoing(SENDER, 'm1', **args))
        self.assertIsNone(collect_both(SENDER, self.mod.now(), lambda p: {}, lambda p: {}, account=self.b))

    def test_protocol_text_per_account(self):
        b = replace(self.b, config={'prompt_choice': 'Escolha sintética', 'prompt_handoff': 'Equipe B'})
        self.assertEqual(b.prompt('choice'), 'Escolha sintética')
        self.assertEqual(b.prompt('handoff'), 'Equipe B')
        self.assertIn('Umdoislab', self.a.prompt('handoff'))
        self.assertNotIn('Umdoislab', self.b.prompt('handoff'))

    def test_recovery_requires_bound_transport_and_foreign_evidence_fails(self):
        self.mod.process_inbound(self.event(self.b), enqueue=True, account=self.b)
        with self.mod.connect(self.b) as db:
            sent = []
            def transport(item): sent.append(item); return 200
            self.assertEqual(deliver_one(db, transport, lambda p: {'safe': True}, account=self.b)['outcome'], 'blocked_configuration')
            self.assertEqual(counts(db), {'pending': 1})
            transport.account = self.b
            def evidence(item):
                return {'safe': True, 'senderId': SENDER, 'messageId': 'same-id',
                        'account_id': self.a.account_id, 'instance': self.a.instance}
            self.assertEqual(deliver_one(db, transport, evidence, account=self.b)['outcome'], 'blocked_reconciliation')
            self.assertEqual(sent, [])
            self.assertEqual(counts(db), {'uncertain': 1})

    def test_worker_disabled_no_claim(self):
        self.mod.process_inbound(self.event(self.b), enqueue=True, account=self.b)
        with self.mod.connect(self.b) as db:
            self.assertEqual(recover_one(db, account=self.b), {'outcome': 'disabled'})
            self.assertEqual(counts(db), {'pending': 1})

    def test_recovery_on_bound_account_and_foreign_history_rejected(self):
        self.mod.process_inbound(self.event(self.b), enqueue=True, account=self.b)
        with self.mod.connect(self.b) as db:
            item = claim(db, account=self.b)
            stamp = db.execute('SELECT created_at FROM n8n_outbox').fetchone()[0]
            snapshot = {'complete': True, 'since': stamp, 'checkedAt': stamp,
                        'senderId': SENDER, 'inbound': [{'id': 'same-id', 'fromMe': False, 'timestamp': stamp}],
                        'outbound': [], 'account_id': self.b.account_id, 'instance': self.b.instance}
            self.assertTrue(evaluate(db, item, snapshot, policy_check=lambda d,s: True, account=self.b)['safe'])
            self.assertEqual(evaluate(db, item, {**snapshot, 'instance': self.a.instance},
                                     policy_check=lambda d,s: True, account=self.b)['reason'], 'account_mismatch')

    def test_http_server_with_loopback_ingress_and_bridge(self):
        import http.client
        from http.server import ThreadingHTTPServer
        server = ThreadingHTTPServer(('127.0.0.1', 0), self.mod.Handler)
        server.daemon_threads = True
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with patch.object(self.mod, 'SUPERVISOR_IP', '127.0.0.1'):
                for a in (self.a, self.b):
                    conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                    conn.request('POST', '/bridge/inbound', json.dumps(self.event(a)),
                                 {'Authorization': 'Bearer '+a.config['bridge_secret'],
                                  'Content-Type': 'application/json'})
                    result = conn.getresponse()
                    self.assertEqual(result.status, 200)
                    self.assertEqual(json.loads(result.read())['instance'], a.instance)
                    conn.close()
                conn = http.client.HTTPConnection('127.0.0.1', server.server_port, timeout=3)
                conn.request('GET', '/')
                result = conn.getresponse()
                self.assertEqual(result.status, 200)
                self.assertIn(b'Umdoislab', result.read())
                self.assertIn("frame-ancestors 'self'", result.getheader('Content-Security-Policy'))
                conn.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)

    def test_legacy_schema_data_preserved_without_manual_migration(self):
        legacy_base = self.base/'legacy'
        legacy_base.mkdir()
        path = legacy_base/'central.sqlite3'
        with sqlite3.connect(path) as db:
            db.execute('''CREATE TABLE conversations(
                sender_id TEXT PRIMARY KEY, sender_name TEXT NOT NULL DEFAULT '',
                subject TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
                last_message TEXT NOT NULL DEFAULT '', last_message_id TEXT NOT NULL DEFAULT '',
                status TEXT NOT NULL DEFAULT 'pending', updated_at TEXT NOT NULL, created_at TEXT NOT NULL,
                last_reply TEXT NOT NULL DEFAULT '', last_reply_at TEXT)''')
            db.execute('INSERT INTO conversations(sender_id,status,summary,updated_at,created_at) VALUES(?,?,?,?,?)',
                       (SENDER, 'human', 'Legado sintético', self.mod.now(), self.mod.now()))
        a = replace(self.a, database=path)
        with patch.object(self.mod, 'BASE', legacy_base):
            self.mod.init(a)
            with self.mod.connect(a) as db:
                row = db.execute('SELECT summary,status,choice_state FROM conversations').fetchone()
                self.assertEqual(tuple(row), ('Legado sintético', 'human', 'idle'))
                self.assertEqual(db.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table'").fetchone()[0], 13)
            self.assertFalse(self.mod.routing_decision(a.instance, SENDER, a)['allowAutoReply'])

    def test_preflight_scoped_auth_does_not_persist(self):
        for a in (self.a, self.b):
            body = {'event': 'messages.upsert', 'instance': a.instance, 'data': {
                'key': {'remoteJid': SENDER, 'id': 'preflight', 'fromMe': False},
                'message': {'conversation': 'Sintética'}}}
            path = '/accounts/' + a.account_id + '/evolution/ingress-check'
            code, result = self.http(path, body, token='Bearer '+a.config['evolution_webhook_secret'])
            self.assertEqual((code, result), (200, {'accepted': True, 'dispatch': False}))
            self.assertEqual(self.http(path, body, account=a)[0], 403)
            self.assertEqual(self.count(a, 'inbound_ids'), 0)

    def test_operator_activity_internal_helper_is_scoped_not_exposed(self):
        result = self.mod.record_operator_activity(self.event(self.b, fromMe=True, verifiedManual=True), self.b)
        self.assertTrue(result['manualActive'])
        self.assertEqual(self.mod.routing_decision(self.a.instance, SENDER, self.a)['state'], 'none')
        self.assertEqual(self.http('/bridge/operator-activity', self.event(self.b), account=self.b, ingress=False)[0], 403)

    def test_baseline_contacts_are_queried_and_saved_only_for_selected_account(self):
        class Contacts:
            status = 200
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return json.dumps([{'remoteJid': SENDER}]).encode()
        with patch.object(self.mod.urllib.request, 'urlopen', return_value=Contacts()) as fetch:
            self.assertEqual(self.http('/accounts/synthetic_b/api/policy/baseline', {})[0], 200)
            self.assertEqual(fetch.call_count, 2)
            self.assertTrue(fetch.call_args.args[0].full_url.endswith('/synthetic'))
            self.assertEqual(fetch.call_args.args[0].get_header('Apikey'), self.b.config['evolution_api_key'])
        self.assertEqual(self.count(self.a, 'known_contacts'), 0)
        self.assertEqual(self.count(self.b, 'known_contacts'), 1)
        self.assertEqual(self.http('/accounts/synthetic_b/api/policy/mode', {'mode': 'new'})[0], 200)
        self.assertFalse(self.mod.routing_decision(self.b.instance, SENDER, self.b)['allowAutoReply'])
        self.assertTrue(self.mod.routing_decision(self.a.instance, SENDER, self.a)['allowAutoReply'])

    def _lid_lookup(self, records=None):
        """Transporte simulado; exercita verify_outgoing real pela rota HTTP."""
        from test_outgoing_pn_lid import lid_record
        from test_outgoing_verification import Response, payload
        def read(request, timeout):
            account = self.a if request.full_url.endswith('/umdoislab') else self.b
            self.assertEqual(request.full_url, account.config['evolution_url']+'/chat/findMessages/'+account.instance)
            self.assertEqual(request.get_header('Apikey'), account.config['evolution_api_key'])
            key = json.loads(request.data)['where']['key']
            self.assertEqual(key['id'], 'same-id')
            if 'remoteJid' in key:
                self.assertEqual(key['remoteJid'], SENDER)
                return Response(payload([]))
            self.assertEqual(key['remoteJidAlt'], SENDER)
            return Response(payload([lid_record(mid='same-id')] if records is None else records))
        return patch('outgoing_verification.urlopen', side_effect=read)

    def test_pn_lid_http_bot_uncertain_and_no_replay_are_account_local(self):
        for account in (self.a, self.b):
            self.mod.process_inbound(self.event(account), enqueue=True, account=account)
        with self.mod.connect(self.a) as da, self.mod.connect(self.b) as db:
            da.execute('INSERT INTO bot_outbound_ids VALUES(?,?,?)', (SENDER, 'same-id', self.mod.now()))
            self.assertIsNotNone(claim(db, account=self.b))
        with self._lid_lookup() as lookup:
            for account, classification in ((self.a, 'bot'), (self.b, 'uncertain')):
                code, result = self.http('/bridge/outgoing-observation',
                                         self.event(account, fromMe=True, source='web'), account=account)
                self.assertEqual((code, result['classification']), (200, classification))
            self.assertEqual(lookup.call_count, 4)
        self.assertEqual(self.mod.routing_decision(self.a.instance, SENDER, self.a)['state'], 'none')
        self.assertEqual(self.mod.routing_decision(self.b.instance, SENDER, self.b)['state'], 'human')
        with self.mod.connect(self.a) as da, self.mod.connect(self.b) as db:
            self.assertEqual(counts(da), {'pending': 1})
            self.assertEqual(counts(db), {'uncertain': 1})
            calls = []
            def transport(item): calls.append(item); return 200
            transport.account = self.b
            self.assertIsNone(deliver_one(db, transport, lambda item: {'safe': True}, account=self.b))
            transport.account = self.a
            stamp = da.execute('SELECT created_at FROM n8n_outbox').fetchone()[0]
            snapshot = {'account_id': self.a.account_id, 'instance': self.a.instance,
                        'senderId': SENDER, 'complete': True, 'since': stamp, 'checkedAt': self.mod.now(),
                        'inbound': [{'id': 'same-id', 'fromMe': False, 'timestamp': stamp}],
                        'outbound': [{'id': 'same-id', 'fromMe': True, 'timestamp': stamp}]}
            def reconcile(item):
                result = evaluate(da, item, snapshot, policy_check=lambda d,s: True, account=self.a)
                self.assertEqual(result['reason'], 'outgoing_after_request')
                return result
            self.assertEqual(deliver_one(da, transport, reconcile, account=self.a)['outcome'], 'blocked_reconciliation')
            self.assertEqual(calls, [])
            self.assertEqual(counts(da), {'uncertain': 1})

    def test_pn_lid_http_wrong_bridge_secret_never_queries_or_classifies(self):
        with self._lid_lookup() as lookup:
            code, _ = self.http('/bridge/outgoing-observation', self.event(self.b, fromMe=True), account=self.a)
            self.assertEqual(code, 403)
            lookup.assert_not_called()
        for account in (self.a, self.b):
            self.assertEqual(self.count(account, 'outgoing_observations'), 0)
            self.assertEqual(self.count(account, 'conversations'), 0)

    def test_pn_lid_http_unverified_event_does_not_take_over_or_authorize_replay(self):
        from test_outgoing_pn_lid import lid_record
        bad = lid_record(mid='same-id')
        bad['key']['remoteJidAlt'] = '5511888888888@s.whatsapp.net'
        self.mod.process_inbound(self.event(self.b), enqueue=True, account=self.b)
        with self._lid_lookup([bad]):
            self.assertEqual(self.http('/bridge/outgoing-observation', self.event(self.b, fromMe=True), account=self.b)[0], 422)
        self.assertEqual(self.count(self.b, 'outgoing_observations'), 0)
        self.assertEqual(self.mod.routing_decision(self.b.instance, SENDER, self.b)['state'], 'none')
        with self.mod.connect(self.b) as db:
            sent = []
            def transport(item): sent.append(item); return 200
            transport.account = self.b
            result = deliver_one(db, transport,
                lambda item: evaluate(db, item, None, policy_check=lambda d,s: True, account=self.b), account=self.b)
            self.assertEqual(result['outcome'], 'blocked_reconciliation')
            self.assertEqual(counts(db), {'uncertain': 1})
            self.assertEqual(sent, [])

    def test_pn_lid_http_repeated_verified_echo_is_idempotent(self):
        with self._lid_lookup() as lookup:
            body = self.event(self.b, fromMe=True)
            code, first = self.http('/bridge/outgoing-observation', body, account=self.b)
            repeated_code, repeated = self.http('/bridge/outgoing-observation', body, account=self.b)
            self.assertEqual((code, repeated_code), (200, 200))
            self.assertFalse(first['duplicate'])
            self.assertTrue(repeated['duplicate'])
            self.assertEqual(repeated['classification'], 'uncertain')
            self.assertEqual(lookup.call_count, 4)
        self.assertEqual(self.count(self.b, 'outgoing_observations'), 1)
