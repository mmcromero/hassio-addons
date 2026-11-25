import hashlib
import hmac
import importlib.util
import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "server.py"
sys.path.insert(0, str(SOURCE.parent))
spec = importlib.util.spec_from_file_location("instagram_server", SOURCE)
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)


class InstagramIngressTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        server.DATA_DIR = Path(self.tmp.name)
        server.DB_PATH = server.DATA_DIR / "instagram.sqlite3"
        with server.database() as conn:
            server.automation_policy.save(conn, "business-1", "tests", "12345678", "")

    def tearDown(self):
        self.tmp.cleanup()

    def sample(self, mid="message-1", text="oi"):
        return {"object": "instagram", "entry": [{"id": "business-1",
            "messaging": [{"sender": {"id": "12345678"},
                            "recipient": {"id": "business-1"},
                            "timestamp": int(time.time() * 1000),
                            "message": {"mid": mid, "text": text}}]}]}

    def test_signed_payload(self):
        body = b'{"object":"instagram"}'
        sig = "sha256=" + hmac.new(b"secret", body, hashlib.sha256).hexdigest()
        self.assertTrue(server.signature_valid(body, sig, "secret"))
        self.assertFalse(server.signature_valid(body + b" ", sig, "secret"))
        self.assertFalse(server.signature_valid(body, sig, ""))
        self.assertFalse(server.signature_valid(body, "sha256=" + "é" * 64, "secret"))
        self.assertFalse(server.signature_valid(body, "sha256=" + "G" * 64, "secret"))
        self.assertFalse(server.signature_valid(body, "sha256=" + "1" * 10, "secret"))

    def test_text_only(self):
        self.assertEqual(len(server.normalized_messages(self.sample(), 'business-1')), 1)
        event = self.sample()
        event["entry"][0]["messaging"][0]["message"]["is_echo"] = True
        self.assertEqual(server.normalized_messages(event, 'business-1'), [])
        event["entry"][0]["messaging"][0]["message"] = {"mid": "x", "attachments": []}
        self.assertEqual(server.normalized_messages(event, 'business-1'), [])

    def test_meta_event_time_controls_automatic_reply_window(self):
        import copy
        fresh = self.sample()
        current = server.webhook_message_times(fresh, "business-1")
        self.assertIn(("business-1", "12345678", "message-1"), current)
        stale = copy.deepcopy(fresh)
        stale["entry"][0]["messaging"][0]["timestamp"] = int((time.time() - 25 * 3600) * 1000)
        self.assertEqual(server.persist(json.dumps(stale).encode(), "business-1"), 1)
        self.assertEqual(server.list_pending(account_id="business-1"), [])
        self.assertIsNone(server.claim_message())

    def test_missing_meta_timestamp_fails_closed_for_automation(self):
        event = self.sample()
        del event["entry"][0]["messaging"][0]["timestamp"]
        self.assertEqual(server.persist(json.dumps(event).encode(), "business-1"), 1)
        self.assertEqual(server.list_pending(account_id="business-1"), [])
        self.assertIsNone(server.claim_message())

    def test_idempotency(self):
        raw = json.dumps(self.sample()).encode()
        self.assertEqual(server.persist(raw, 'business-1'), 1)
        self.assertEqual(server.persist(raw, 'business-1'), 0)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbound").fetchone()[0], 1)

    def test_unified_messages_preserve_identity_and_cross_format_idempotency(self):
        legacy = self.sample()
        entry = legacy['entry'][0]
        unified = {'object': 'instagram', 'entry': [{'id': entry['id'],
            'changes': [{'field': 'messages', 'value': entry['messaging'][0]}]}]}
        self.assertEqual(server.normalized_messages(unified, 'business-1'),
                         [('business-1', '12345678', 'message-1', 'oi')])
        self.assertEqual(server.persist(json.dumps(unified).encode(), 'business-1'), 1)
        self.assertEqual(server.persist(json.dumps(legacy).encode(), 'business-1'), 0)
        self.assertEqual(server.list_pending(account_id='business-1')[0]['messageText'], 'oi')

    def test_unified_changes_reject_unknown_fields_recipients_and_nonmessages(self):
        import copy
        event = self.sample()['entry'][0]['messaging'][0]
        rejected = []
        for path, value in [(('recipient','id'),'other-business'), (('recipient','id'),None),
                            (('sender','id'),'business-1'), (('message','is_echo'),True),
                            (('message','text'),''), (('message','text'),'x'*2001),
                            (('message','mid'),None)]:
            item=copy.deepcopy(event);item[path[0]][path[1]]=value;rejected.append(item)
        for item in rejected:
            payload={'object':'instagram','entry':[{'id':'business-1',
                'changes':[{'field':'messages','value':item}]}]}
            with self.subTest(event=item):
                self.assertEqual(server.normalized_messages(payload,'business-1'),[])
        for field in ('comments','message_edit','message_reactions','messaging_seen',None):
            payload={'object':'instagram','entry':[{'changes':[{'field':field,'value':event}]}]}
            self.assertEqual(server.normalized_messages(payload,'business-1'),[])
        for malformed in (None, {}, [None, {'field':'messages','value':[]},
                                     {'field':'messages','value':'not-an-event'}]):
            self.assertEqual(server.normalized_messages({'object':'instagram',
                'entry':[{'changes':malformed}]},'business-1'),[])

    def test_unified_envelopes_are_bounded_and_do_not_fallback_to_entry_id(self):
        event = self.sample()['entry'][0]['messaging'][0]
        changes = [{'field':'messages','value':event}]*101
        payload={'object':'instagram','entry':[{'id':'other-business','changes':changes}]*101}
        self.assertEqual(len(server.normalized_messages(payload,'business-1')),10000)
        self.assertEqual(server.normalized_messages(payload,'other-business'),[])
        self.assertEqual(server.normalized_messages(payload),[])

    def test_database_context_closes_connection(self):
        with server.database() as conn:
            self.assertIsNotNone(conn.execute("SELECT 1").fetchone())
        with self.assertRaises(Exception) as caught:
            conn.execute("SELECT 1")
        self.assertIn("closed", str(caught.exception).lower())

    def test_unicode_credentials_fail_without_crashing(self):
        secret = "strong-example-secret-with-32-characters"
        self.assertFalse(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": "é"}, {"bridge_secret": secret}))
        self.assertTrue(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": secret}, {"bridge_secret": secret}))
        import base64
        password = "password-with-accents-é-and-length"
        header = "Basic " + base64.b64encode(("admin:" + password).encode("utf-8")).decode("ascii")
        self.assertTrue(server.panel_authorized({"Authorization": header}, {"panel_password": password}))
        other = "Basic " + base64.b64encode("admin:á".encode("utf-8")).decode("ascii")
        self.assertFalse(server.panel_authorized({"Authorization": other}, {"panel_password": password}))

    def test_inbound_schema_migration_and_insert(self):
        """Regression: INSERT must name columns after adding lease/ACK fields."""
        with server.database() as conn:
            names = {row[1] for row in conn.execute("PRAGMA table_info(inbound)")}
            self.assertTrue({"processed_at", "claim_token", "claim_until", "source", "message_at"}.issubset(names))
            send_names = {row[1] for row in conn.execute("PRAGMA table_info(automation_sends)")}
            self.assertIn("reply_text", send_names)
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        with server.database() as conn:
            row = conn.execute("""SELECT message_text, processed_at, claim_token, claim_until
                                  FROM inbound WHERE message_id=?""", ("message-1",)).fetchone()
        self.assertEqual(row, ("oi", None, None, None))

    def test_sender_isolation(self):
        one = self.sample("same")
        two = self.sample("same")
        two["entry"][0]["messaging"][0]["sender"]["id"] = "87654321"
        self.assertEqual(server.persist(json.dumps(one).encode(), 'business-1'), 1)
        self.assertEqual(server.persist(json.dumps(two).encode(), 'business-1'), 1)

    def test_handoff_transitions_and_isolation(self):
        self.assertFalse(server.set_handoff({"accountId": "b", "senderId": "c", "state": "human"}))
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "pending"}))
        self.assertEqual(server.list_pending()[0]["handoffState"], "pending")
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertEqual(server.list_pending()[0]["handoffState"], "human")
        self.assertFalse(server.set_handoff({
            "accountId": "business-1", "senderId": "87654321", "state": "human"}))
        self.assertFalse(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "unknown"}))

    def test_claim_ack_and_no_duplicate(self):
        raw = json.dumps(self.sample()).encode()
        self.assertEqual(server.persist(raw, 'business-1'), 1)
        first = server.claim_message()
        self.assertIsNotNone(first)
        self.assertEqual(first["messageId"], "message-1")
        self.assertIsNone(server.claim_message())  # reserved
        ack = {"accountId": first["accountId"], "senderId": first["senderId"],
               "messageId": first["messageId"], "claimToken": first["claimToken"]}
        self.assertFalse(server.acknowledge_message({**ack, "senderId": "other"}))
        self.assertFalse(server.acknowledge_message({**ack, "claimToken": "x" * 43}))
        self.assertTrue(server.acknowledge_message(ack))
        self.assertFalse(server.acknowledge_message(ack))  # no double ACK
        self.assertIsNone(server.claim_message())
        self.assertEqual(server.list_pending(), [])

    def test_expired_claim_is_recoverable(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        first = server.claim_message()
        with server.database() as conn:
            conn.execute("UPDATE inbound SET claim_until='2000-01-01T00:00:00+00:00'")
        second = server.claim_message()
        self.assertIsNotNone(second)
        self.assertNotEqual(first["claimToken"], second["claimToken"])
        before = {"accountId": first["accountId"], "senderId": first["senderId"],
                  "messageId": first["messageId"], "claimToken": first["claimToken"]}
        after = {**before, "claimToken": second["claimToken"]}
        self.assertFalse(server.acknowledge_message(before))
        self.assertTrue(server.acknowledge_message(after))

    def test_claim_does_not_erase_history(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        self.assertTrue(server.acknowledge_message({
            "accountId": item["accountId"], "senderId": item["senderId"],
            "messageId": item["messageId"], "claimToken": item["claimToken"]}))
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM inbound").fetchone()[0], 1)
            self.assertIsNotNone(conn.execute("SELECT processed_at FROM inbound").fetchone()[0])
            self.assertIsNone(conn.execute("SELECT claim_token FROM inbound").fetchone()[0])

    def test_claim_requires_exact_schema(self):
        self.assertFalse(server.acknowledge_message(None))
        self.assertFalse(server.acknowledge_message({
            "accountId": "x", "senderId": "y", "messageId": "z", "extra": 1}))

    def test_decision_requires_live_claim(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        self.assertEqual(server.evaluate_claim(claim)["action"], "auto")
        self.assertTrue(server.evaluate_claim(claim)["maySend"])
        self.assertTrue(server.evaluate_claim(claim)["testSendAuthorized"])
        self.assertTrue(server.evaluate_claim(claim)["mayCallGemini"])
        self.assertIsNone(server.evaluate_claim({**claim, "claimToken": "x" * 43}))
        self.assertTrue(server.acknowledge_message(claim))
        self.assertIsNone(server.evaluate_claim(claim))

    def test_decision_is_blocked_after_handoff(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertIsNone(server.evaluate_claim(claim))

    def test_decision_rejects_unknown_message_and_extra_fields(self):
        self.assertIsNone(server.evaluate_claim({"accountId": "a", "senderId": "b", "messageId": "m",
                                                "claimToken": "x"*43}))
        self.assertIsNone(server.evaluate_claim({"accountId": "a", "senderId": "b",
                                               "messageId": "m", "claimToken": "x"*43, "extra": True}))

    def test_semantic_classification_is_delegated_to_shared_core(self):
        for mid, text in (("message-price", "Quanto custa o produto?"),
                          ("message-free", "teste 2")):
            self.assertEqual(server.persist(json.dumps(self.sample(mid=mid, text=text)).encode(),
                                            'business-1'), 1)
            item = server.claim_message()
            claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
            decision = server.evaluate_claim(claim)
            self.assertEqual(decision["action"], "auto")
            self.assertTrue(decision["mayCallGemini"])
            self.assertTrue(decision["maySend"])
            self.assertTrue(decision["testSendAuthorized"])
            self.assertTrue(server.acknowledge_message(claim))

    def test_free_text_send_is_allowed_only_for_authorized_test_contact(self):
        self.assertEqual(server.persist(json.dumps(self.sample(text="teste 2")).encode(),
                                        'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        calls = []
        def fake_sender(cfg, credential, recipient, text):
            calls.append((cfg["instagram_account_id"], recipient, text))
            return {"message_id": "outbound-1"}
        result = server.send_automatic_reply(
            {**claim, "text": "Claro! Como posso ajudar?"},
            {"instagram_account_id": "business-1"}, {}, sender=fake_sender)
        self.assertEqual(result, {"status": "sent", "messageId": "outbound-1"})
        self.assertEqual(calls, [("business-1", "12345678", "Claro! Como posso ajudar?")])
        with server.database() as conn:
            row = conn.execute("SELECT status,reply_text FROM automation_sends").fetchone()
        self.assertEqual(row, ("sent", "Claro! Como posso ajudar?"))

    def test_context_returns_same_conversation_turns_in_order(self):
        self.assertEqual(server.persist(json.dumps(self.sample(text="teste 2")).encode(),
                                        'business-1'), 1)
        first = server.claim_message()
        first_claim = {k: first[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        def fake_sender(cfg, credential, recipient, text):
            return {"message_id": "outbound-1"}
        sent = server.send_automatic_reply(
            {**first_claim, "text": "Vamos conferir isso juntos."},
            {"instagram_account_id": "business-1"}, {}, sender=fake_sender)
        self.assertEqual(sent["status"], "sent")
        self.assertEqual(server.persist(json.dumps(self.sample(mid="message-2", text="E quanto custa?")).encode(),
                                        'business-1'), 1)
        # A different sender's text must never enter this conversation context.
        other = self.sample(mid="other-sender", text="TEXTO DE OUTRA CONVERSA")
        other["entry"][0]["messaging"][0]["sender"]["id"] = "87654321"
        self.assertEqual(server.persist(json.dumps(other).encode(), 'business-1'), 1)
        second = server.claim_message()
        second_claim = {k: second[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        context = server.conversation_context(second_claim)
        self.assertIsNotNone(context)
        self.assertEqual([turn["role"] for turn in context["turns"]],
                         ["client", "assistant", "client"])
        self.assertEqual([turn["text"] for turn in context["turns"]],
                         ["teste 2", "Vamos conferir isso juntos.", "E quanto custa?"])
        self.assertNotIn("TEXTO DE OUTRA CONVERSA", repr(context))

    def _stage4_offer(self, fail=False):
        self.assertEqual(server.persist(json.dumps(self.sample(mid="offer-in", text="produto desconhecido")).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        captured = []
        def sender(cfg, credential, recipient, text):
            captured.append(text)
            if fail:
                raise RuntimeError("synthetic uncertain")
            return {"message_id": "offer-out"}
        result = server.send_automatic_reply({**claim, "kind":"human_offer","text":""},
            {"instagram_account_id":"business-1"}, {}, sender=sender)
        self.assertEqual(result["status"], "failed" if fail else "sent")
        self.assertEqual(captured, [server.HUMAN_OFFER_PROMPT])
        self.assertEqual(server.send_automatic_reply({**claim, "kind":"human_offer","text":""},
            {"instagram_account_id":"business-1"}, {}, sender=sender)["status"], "rejected")
        self.assertEqual(len(captured),1)

    def _stage4_next(self, mid, text):
        time.sleep(0.004)
        self.assertEqual(server.persist(json.dumps(self.sample(mid=mid,text=text)).encode(), 'business-1'),1)
        item=server.claim_message()
        return {k:item[k] for k in ("accountId","senderId","messageId","claimToken")}

    def _stage5_handoff(self, fail=False):
        self.assertEqual(server.persist(json.dumps(self.sample(mid="handoff-in",text="Quero falar com alguém")).encode(),'business-1'),1)
        item=server.claim_message()
        pair=(item["messageId"],item["claimToken"])
        data={"accountId":item["accountId"],"senderId":item["senderId"],"state":"pending"}
        calls=[]
        def sender(cfg, credential, recipient, text):
            with server.database() as conn:
                self.assertEqual(conn.execute("SELECT state FROM handoff").fetchone()[0],"pending")
                self.assertEqual(conn.execute("SELECT status FROM automation_sends").fetchone()[0],"sending")
            calls.append((recipient,text))
            if fail:
                raise RuntimeError("synthetic uncertainty")
            return {"message_id":"notice-out"}
        cfg={"instagram_account_id":"business-1"}
        self.assertFalse(server.handoff_and_notify(data,cfg,{},reason="human_review",claim=(pair[0],"x"*43),sender=sender)["saved"])
        self.assertFalse(calls)
        result=server.handoff_and_notify(data,cfg,{},reason="human_review",claim=pair,sender=sender)
        self.assertTrue(result["saved"])
        self.assertEqual(result["notified"],not fail)
        self.assertEqual(calls,[(item["senderId"],server.HANDOFF_NOTICE)])
        self.assertFalse(server.handoff_and_notify(data,cfg,{},reason="human_review",claim=pair,sender=sender)["saved"])
        self.assertEqual(len(calls),1)
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT state FROM handoff").fetchone()[0],"pending")
            self.assertEqual(conn.execute("SELECT status FROM automation_sends").fetchone()[0],"failed" if fail else "sent")
        self.assertIsNone(server.claim_message())

    def test_stage5_handoff_notification_saved_first_and_once(self):
        self._stage5_handoff()

    def test_stage5_uncertain_notice_preserves_handoff_no_retry(self):
        self._stage5_handoff(fail=True)

    def test_stage5_handoff_after_offer_confirmation(self):
        self._stage4_offer()
        claim=self._stage4_next("yes","SIM")
        self.assertEqual(server.evaluate_claim(claim)["action"],"human_review")
        calls=[]
        def send(cfg, credential, recipient, text):
            calls.append(text)
            return {"message_id":"confirmation-out"}
        result=server.handoff_and_notify({"accountId":claim["accountId"],"senderId":claim["senderId"],"state":"pending"},
            {"instagram_account_id":"business-1"}, {}, reason="human_review",
            claim=(claim["messageId"],claim["claimToken"]),sender=send)
        self.assertTrue(result["saved"] and result["notified"])
        self.assertEqual(calls,[server.HANDOFF_NOTICE])
        self.assertIsNone(server.claim_message())

    def test_stage4_offer_yes_is_claim_bound(self):
        self._stage4_offer()
        claim=self._stage4_next("yes","SIM")
        self.assertEqual(server.evaluate_claim(claim)["action"],"human_review")
        self.assertTrue(server.set_handoff({"accountId":claim["accountId"],"senderId":claim["senderId"],"state":"pending"},
            actor="bridge",reason="human_review",claim=(claim["messageId"],claim["claimToken"])))
        self.assertIsNone(server.evaluate_claim(claim))

    def test_stage4_offer_no_then_generic_yes_does_not_handoff(self):
        self._stage4_offer()
        claim=self._stage4_next("no","NÃO")
        self.assertEqual(server.evaluate_claim(claim)["action"],"auto")
        self.assertTrue(server.acknowledge_message(claim))
        later=self._stage4_next("later","SIM")
        self.assertEqual(server.evaluate_claim(later)["action"],"auto")

    def test_stage4_uncertain_offer_not_confirmable(self):
        self._stage4_offer(fail=True)
        claim=self._stage4_next("yes","SIM")
        self.assertEqual(server.evaluate_claim(claim)["action"],"auto")

    def test_stage4_expired_offer_not_confirmable(self):
        self._stage4_offer()
        with server.database() as conn:
            conn.execute("UPDATE human_offers SET created_at='2000-01-01T00:00:00+00:00'")
        claim=self._stage4_next("yes","SIM")
        self.assertEqual(server.evaluate_claim(claim)["action"],"auto")

    def test_stage4_only_one_live_claim_per_conversation(self):
        self.assertEqual(server.persist(json.dumps(self.sample(mid="first")).encode(),'business-1'),1)
        self.assertEqual(server.persist(json.dumps(self.sample(mid="second")).encode(),'business-1'),1)
        item=server.claim_message()
        self.assertIsNotNone(item)
        self.assertIsNone(server.claim_message())
        claim={k:item[k] for k in ("accountId","senderId","messageId","claimToken")}
        self.assertTrue(server.acknowledge_message(claim))
        self.assertIsNotNone(server.claim_message())

    def test_stage3_context_excludes_future_and_binds_current(self):
        self.assertEqual(server.persist(json.dumps(self.sample(mid="current", text="texto atual")).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        self.assertEqual(server.persist(json.dumps(self.sample(mid="later", text="texto posterior")).encode(), 'business-1'), 1)
        ctx = server.conversation_context(claim)
        self.assertEqual({k: ctx[k] for k in ("accountId", "senderId", "messageId")},
                         {k: claim[k] for k in ("accountId", "senderId", "messageId")})
        self.assertEqual(ctx["turns"], [{"role": "client", "text": "texto atual", "createdAt": item["messageAt"]}])

    def test_stage3_handoff_cannot_override_human_or_replay_claim(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        data = {"accountId": item["accountId"], "senderId": item["senderId"], "state": "pending"}
        pair = (item["messageId"], item["claimToken"])
        self.assertFalse(server.set_handoff(data, actor="bridge", reason="human_review", claim=(item["messageId"], "x"*43)))
        self.assertTrue(server.set_handoff({**data, "state": "human"}))
        self.assertFalse(server.set_handoff(data, actor="bridge", reason="human_review", claim=pair))
        self.assertEqual(server.list_pending()[0]["handoffState"], "human")
        self.assertTrue(server.set_handoff({**data, "state": "bot"}))
        self.assertFalse(server.set_handoff(data, actor="bridge", reason="human_review", claim=pair))

    def test_stage3_valid_claim_handoff_once(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        data = {"accountId": item["accountId"], "senderId": item["senderId"], "state": "pending"}
        pair = (item["messageId"], item["claimToken"])
        self.assertTrue(server.set_handoff(data, actor="bridge", reason="human_review", claim=pair))
        self.assertFalse(server.set_handoff(data, actor="bridge", reason="human_review", claim=pair))
        self.assertEqual(server.list_pending()[0]["handoffState"], "pending")

    def test_context_requires_live_test_claim_and_bot_control(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        self.assertIsNotNone(server.conversation_context(claim))
        self.assertIsNone(server.conversation_context({**claim, "claimToken": "x" * 43}))
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertIsNone(server.conversation_context(claim))

    def test_context_rejects_expired_claim(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        with server.database() as conn:
            conn.execute("""UPDATE inbound SET claim_until=?
                WHERE recipient_id=? AND sender_id=? AND message_id=?""",
                ("2000-01-01T00:00:00+00:00", claim["accountId"], claim["senderId"], claim["messageId"]))
        self.assertIsNone(server.conversation_context(claim))

    def test_draft_requires_live_claim_and_never_sends(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        payload = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        payload["draftText"] = "Olá! Como posso ajudar?"
        self.assertTrue(server.save_draft(payload))
        self.assertFalse(server.save_draft(payload))
        with server.database() as conn:
            rows = conn.execute("SELECT draft_text,status FROM drafts").fetchall()
        self.assertEqual(rows, [("Olá! Como posso ajudar?", "pending")])
        self.assertIsNone(server.evaluate_claim({**payload, "claimToken": "x"*43}))

    def test_draft_is_blocked_after_handoff(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        payload = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
        payload["draftText"] = "Resposta ainda não enviada"
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertFalse(server.save_draft(payload))
        with server.database() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM drafts").fetchone()[0], 0)

    def test_draft_rejects_untrusted_text_and_oversize(self):
        self.assertFalse(server.save_draft(None))
        self.assertFalse(server.save_draft({
            "accountId": "a", "senderId": "b", "messageId": "m",
            "claimToken": "x"*43, "draftText": " "}))
        self.assertFalse(server.save_draft({
            "accountId": "a", "senderId": "b", "messageId": "m",
            "claimToken": "x"*43, "draftText": "x"*1001}))

    def test_human_handoff_blocks_bot_queue(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        self.assertIsNotNone(item)
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertIsNone(server.claim_message())
        self.assertFalse(server.acknowledge_message({
            "accountId": item["accountId"], "senderId": item["senderId"],
            "messageId": item["messageId"], "claimToken": item["claimToken"]}))
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "bot"}))
        self.assertIsNone(server.claim_message())
        with server.database() as conn:
            row = conn.execute("SELECT processed_at,resume_skipped_at,claim_token,claim_until FROM inbound").fetchone()
        self.assertIsNotNone(row[0])
        self.assertEqual(row[0], row[1])
        self.assertEqual(row[2:], (None, None))

    def test_resume_does_not_replay_history_and_claims_only_new_message(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch
        resumed = datetime(2026, 11, 24, 22, 30, tzinfo=timezone.utc)
        def event(mid, stamp, sender="12345678"):
            payload = self.sample(mid=mid)
            message = payload["entry"][0]["messaging"][0]
            message["timestamp"] = int(stamp.timestamp() * 1000)
            message["sender"]["id"] = sender
            return json.dumps(payload).encode()
        conversation = {"accountId": "business-1", "senderId": "12345678"}
        with patch.object(server, "_utc_now", return_value=resumed):
            with server.database() as conn:
                server.automation_policy.save(conn, "business-1", "tests", "12345678\n87654321", "")
            self.assertEqual(server.persist(event("old", resumed - timedelta(minutes=3)), "business-1"), 1)
            self.assertTrue(server.set_handoff({**conversation, "state": "pending"}))
            self.assertEqual(server.persist(event("held", resumed - timedelta(minutes=2)), "business-1"), 1)
            self.assertTrue(server.set_handoff({**conversation, "state": "bot"}))
            # Old deliveries, including duplicates and late webhooks, cannot reopen the queue.
            self.assertEqual(server.persist(event("old", resumed - timedelta(minutes=3)), "business-1"), 0)
            self.assertEqual(server.persist(event("late", resumed - timedelta(minutes=1)), "business-1"), 1)
            self.assertEqual(server.persist(event("boundary", resumed), "business-1"), 1)
            self.assertIsNone(server.claim_message(account_id="business-1"))
            self.assertIn("Encerrada na retomada", server.render_panel())
            self.assertEqual(server.persist(event("new", resumed + timedelta(seconds=1)), "business-1"), 1)
            # Repeating a bot action does not discard new work.
            self.assertTrue(server.set_handoff({**conversation, "state": "bot"}))
            item = server.claim_message(account_id="business-1")
            self.assertEqual(item["messageId"], "new")
            claim = {k: item[k] for k in ("accountId", "senderId", "messageId", "claimToken")}
            self.assertEqual(server.evaluate_claim(claim)["action"], "auto")
            self.assertTrue(server.acknowledge_message(claim))
            self.assertIsNone(server.claim_message(account_id="business-1"))
            # A different sender is not affected by the cutoff.
            self.assertEqual(server.persist(event("other", resumed - timedelta(minutes=2), "87654321"), "business-1"), 1)
            self.assertEqual(server.claim_message(account_id="business-1")["messageId"], "other")
            with server.database() as conn:
                rows = dict(conn.execute("SELECT message_id,resume_skipped_at FROM inbound"))
                self.assertEqual(len(rows), 6)
                self.assertTrue(all(rows[mid] for mid in ("old", "held", "late", "boundary")))
                self.assertIsNone(rows["new"])
                self.assertIsNone(rows["other"])
                self.assertEqual(conn.execute("SELECT COUNT(*) FROM automation_sends").fetchone()[0], 0)

    def test_resume_rejects_delayed_promotion_of_manual_import(self):
        from datetime import datetime, timedelta, timezone
        from unittest.mock import patch
        resumed = datetime(2026, 11, 24, 22, 30, tzinfo=timezone.utc)
        conversation = {"accountId": "business-1", "senderId": "12345678"}
        with patch.object(server, "_utc_now", return_value=resumed):
            with server.database() as conn:
                conn.execute("""INSERT INTO inbound (recipient_id,sender_id,message_id,message_text,received_at,source,processed_at)
                    VALUES (?,?,?,?,?,'manual',?)""",
                    ("business-1", "12345678", "manual-old", "oi", resumed.isoformat(), resumed.isoformat()))
            self.assertTrue(server.set_handoff({**conversation, "state": "human"}))
            self.assertTrue(server.set_handoff({**conversation, "state": "bot"}))
            payload = self.sample(mid="manual-old")
            payload["entry"][0]["messaging"][0]["timestamp"] = int((resumed - timedelta(minutes=1)).timestamp()*1000)
            self.assertEqual(server.persist(json.dumps(payload).encode(), "business-1"), 1)
            self.assertIsNone(server.claim_message(account_id="business-1"))
            with server.database() as conn:
                row = conn.execute("SELECT source,processed_at,resume_skipped_at FROM inbound WHERE message_id='manual-old'").fetchone()
            self.assertEqual(row[0], "webhook")
            self.assertIsNotNone(row[1])
            self.assertEqual(row[1], row[2])

    def test_pending_handoff_blocks_bot_queue(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "pending"}))
        self.assertIsNone(server.claim_message())

    def test_bridge_requires_secret(self):
        self.assertFalse(server.bridge_authorized({}, {"bridge_secret": ""}))
        self.assertFalse(server.bridge_authorized({}, {"bridge_secret": "one"}))
        secret = "local-test-secret-at-least-32-characters"
        self.assertFalse(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": "one"}, {"bridge_secret": "one"}))
        self.assertTrue(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": secret}, {"bridge_secret": secret}))
        self.assertFalse(server.bridge_authorized(
            {"X-Instagram-Bridge-Secret": "other"}, {"bridge_secret": secret}))

    def test_business_originated_echo_ignored(self):
        event = self.sample()
        event["entry"][0]["messaging"][0]["sender"]["id"] = "business-1"
        self.assertEqual(server.normalized_messages(event, 'business-1'), [])

    def test_reject_other_business_account(self):
        self.assertEqual(server.normalized_messages(self.sample(), 'business-2'), [])
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-2'), 0)
        self.assertEqual(server.list_pending(), [])

    def test_handoff_audit(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "human"}))
        self.assertTrue(server.set_handoff({
            "accountId": "business-1", "senderId": "12345678", "state": "done"}))
        with server.database() as conn:
            rows = conn.execute("SELECT old_state,new_state FROM handoff_audit ORDER BY id").fetchall()
        self.assertEqual(rows, [("bot", "human"), ("human", "done")])

    def test_conversation_control_groups_messages_and_records_reason(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        self.assertEqual(server.persist(json.dumps(self.sample(mid="message-2")).encode(), 'business-1'), 1)
        self.assertTrue(server.set_handoff({"accountId":"business-1","senderId":"12345678","state":"pending"}, actor="bridge", reason="human_review"))
        page = server.render_panel({"panel_password":"strong-test-password-12345"})
        self.assertEqual(page.count('aria-label="Ações da conversa"'), 1)
        self.assertIn("Bot bloqueado", page)
        self.assertIn("Revisão humana necessária", page)
        self.assertIn("2 mensagens", page)
        self.assertIn("Voltar ao bot", page)

    def test_delivery_failure_visible_without_handoff(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        with server.database() as conn:
            conn.execute("""INSERT INTO automation_sends
              (recipient_id,sender_id,message_id,status,error_reason,created_at,updated_at)
              VALUES(?,?,?,'failed','configuration_incomplete',?,?)""",
              ('business-1','12345678','message-1','2026-11-24T12:00:00+00:00','2026-11-24T12:00:00+00:00'))
        page = server.render_panel()
        self.assertIn("Falha de envio registrada", page)
        self.assertIn("Automação selecionada", page)
        self.assertNotIn("Bot bloqueado", page)

    def test_panel_forms_have_scoped_csrf(self):
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        page = server.render_panel({"panel_password": "strong-test-password-12345"})
        self.assertIn('action="panel/handoff"', page)
        self.assertIn('name="csrf"', page)
        self.assertIn('Assumir', page)
        self.assertNotIn('<script>', page)

    def test_panel_draft_is_escaped_and_not_sent(self):
        from html import escape
        self.assertEqual(server.persist(json.dumps(self.sample()).encode(), 'business-1'), 1)
        item = server.claim_message()
        payload = {key: item[key] for key in ("accountId", "senderId", "messageId", "claimToken")}
        payload["draftText"] = '<img src=x onerror=alert(1)>'
        self.assertTrue(server.save_draft(payload))
        page = server.render_panel({"panel_password": "strong-test-password-12345"})
        self.assertIn(escape(payload["draftText"], quote=True), page)
        self.assertNotIn(payload["draftText"], page)
        self.assertIn("Rascunho (sem envio)", page)
        self.assertNotIn('action="/bridge/send"', page)

    def test_panel_password(self):
        import base64
        cfg = {"panel_password": "a-strong-test-password"}
        auth = "Basic " + base64.b64encode(b"admin:a-strong-test-password").decode()
        self.assertTrue(server.panel_authorized({"Authorization": auth}, cfg))
        self.assertFalse(server.panel_authorized({}, cfg))
        self.assertFalse(server.panel_authorized({"Authorization": auth}, {"panel_password": ""}))
        self.assertFalse(server.panel_authorized({"Authorization": "Basic !!!"}, cfg))

    def test_panel_html_escaped(self):
        from html import escape
        evil = '<script>alert("x")</script>'
        self.assertEqual(server.persist(json.dumps(self.sample(text=evil)).encode(), 'business-1'), 1)
        page = server.render_panel()
        self.assertNotIn(evil, page)
        self.assertIn(escape(evil, quote=True), page)

    def test_reject_wrong_object(self):
        self.assertEqual(server.normalized_messages({"object": "page", "entry": []}), [])

    def test_invalid_json(self):
        self.assertIsNone(server.persist(b"{broken", 'business-1'))


if __name__ == "__main__":
    unittest.main()
