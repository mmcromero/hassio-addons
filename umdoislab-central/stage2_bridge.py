"""Restricted-test bridge for the shared conversational adapter.

Legacy endpoints and their callers are untouched. Every operation is account scoped.
No second inbound is created by handoff; the stored original turn is reused.
"""
import hashlib
import secrets
import time

PREFIX = "/bridge/stage2/"
KINDS = ("normal", "fallback", "handoff", "choice", "human_offer")
ADMISSION_TTL_SECONDS = 300
SEND_KINDS = {"auto": ("normal", "human_offer"), "handoff": ("handoff",),
              "offer_choice": ("choice",), "resume": ("normal",)}


def ensure_admissions(db):
    db.execute("""CREATE TABLE IF NOT EXISTS stage2_admissions (
        sender_id TEXT PRIMARY KEY, message_id TEXT NOT NULL,
        ref_hash TEXT NOT NULL, action TEXT NOT NULL, expires_at REAL NOT NULL)""")


def revoke(db, sender=None):
    """Invalidate only temporary Stage 2 authorizations; never conversation history."""
    if not db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='stage2_admissions'").fetchone():
        return
    if sender is None:
        db.execute("DELETE FROM stage2_admissions")
    else:
        db.execute("DELETE FROM stage2_admissions WHERE sender_id=?", (sender,))


def ref_hash(value):
    return hashlib.sha256(value.encode()).hexdigest()
HANDOFF_REASONS = frozenset((
    "customer_requested_human", "catalog_error", "model_error",
    "invalid_model_response", "unconfirmed_price", "unconfirmed_link",
    "unvalidated_price_format", "invalid_handoff_claim", "unsafe_content",
    "dependency_failure",
))


def handle(handler, payload, *, connect, get_policy, contact_policy,
           valid_event, valid_sender, process_inbound, routing_decision, now):
    account = handler.account
    respond = handler.respond
    if not handler.bridge():
        return respond(403, {"error": "access_denied"})
    if not isinstance(payload, dict) or payload.get("instance") != account.instance:
        return respond(422, {"error": "invalid_account"})
    sender, mid = payload.get("senderId"), payload.get("messageId")
    if (not isinstance(sender, str) or not valid_sender(sender)
            or not isinstance(mid, str) or not 1 <= len(mid) <= 160):
        return respond(422, {"error": "invalid_identity"})
    identity = {"instance": account.instance, "senderId": sender, "messageId": mid}
    operation = handler.path.removeprefix(PREFIX)
    if operation not in ("inbound", "context", "handoff", "send-auto"):
        return respond(404, {"error": "unknown_operation"})
    with account.lock:
        with connect(account) as db:
            policy = get_policy(db)
            eligibility = contact_policy(db, sender)
            authorized = (policy["mode"] == "tests" and eligibility["allowed"]
                          and eligibility["reason"] == "test")
            if not authorized:
                if operation == "inbound":
                    return respond(200, dict(identity, action="ignore",
                                   policyMode=policy["mode"], testSendAuthorized=False))
                return respond(403, {"error": "test_not_authorized"})
            if operation != "inbound":
                ensure_admissions(db)
                ref = payload.get("admissionRef")
                admission = db.execute("""SELECT message_id,ref_hash,action,expires_at
                    FROM stage2_admissions WHERE sender_id=?""", (sender,)).fetchone()
                if (not isinstance(ref, str) or not 32 <= len(ref) <= 128 or not admission
                        or admission["message_id"] != mid or admission["expires_at"] <= time.time()
                        or not secrets.compare_digest(admission["ref_hash"], ref_hash(ref))):
                    return respond(409, {"error": "invalid_or_expired_admission"})
                admitted_action = admission["action"]
                if operation in ("context", "handoff") and admitted_action != "auto":
                    return respond(409, {"error": "action_not_authorized"})
                turn = db.execute("""SELECT message_id,text FROM conversation_turns
                    WHERE sender_id=? AND role='client' ORDER BY rowid DESC LIMIT 1""",
                    (sender,)).fetchone()
                registered = db.execute("""SELECT 1 FROM inbound_ids
                    WHERE sender_id=? AND message_id=?""", (sender, mid)).fetchone()
                if not registered or not turn or turn["message_id"] != mid:
                    return respond(409, {"error": "not_current_inbound"})
                keys = ["auto-" + hashlib.sha256(
                    (sender + "|" + mid + "|" + kind).encode()).hexdigest()
                    for kind in KINDS]
                if db.execute("SELECT 1 FROM replies WHERE request_id IN (?,?,?,?,?)",
                              keys).fetchone():
                    return respond(409, {"error": "outbound_already_requested"})
                original_text = turn["text"]

        if operation == "inbound":
            if not valid_event(payload, account) or not isinstance(payload.get("messageText"), str) or not payload["messageText"].strip():
                return respond(422, {"error": "invalid_inbound"})
            decision = process_inbound(payload, account=account)
            if not isinstance(decision, dict):
                return respond(422, {"error": "invalid_decision"})
            # Only a NEW admitted event can obtain a short-lived authorization.
            result = dict(decision, **identity, policyMode="tests", testSendAuthorized=True)
            if decision.get("action") in SEND_KINDS:
                ref = secrets.token_urlsafe(32)
                with connect(account) as db:
                    ensure_admissions(db)
                    db.execute("DELETE FROM stage2_admissions WHERE expires_at<=?", (time.time(),))
                    db.execute("""INSERT INTO stage2_admissions VALUES(?,?,?,?,?)
                        ON CONFLICT(sender_id) DO UPDATE SET message_id=excluded.message_id,
                        ref_hash=excluded.ref_hash,action=excluded.action,expires_at=excluded.expires_at""",
                        (sender, mid, ref_hash(ref), decision["action"], time.time()+ADMISSION_TTL_SECONDS))
                result["admissionRef"] = ref
            return respond(200, result)

        if operation == "send-auto":
            if payload.get("kind") not in KINDS:
                return respond(422, {"error": "invalid_kind"})
            if payload["kind"] not in SEND_KINDS.get(admitted_action, ()):
                return respond(409, {"error": "send_kind_not_authorized"})
            # Consume before any external attempt. Uncertain outcomes are never retried.
            with connect(account) as db:
                revoke(db, sender)
            # Legacy sender rechecks state and delivery key under the same account lock.
            return handler.send_automated({k: v for k, v in payload.items() if k != "admissionRef"})

        decision = routing_decision(account.instance, sender, account)
        if not decision or decision.get("allowAutoReply") is not True:
            return respond(409, {"error": "bot_not_authorized"})

        if operation == "context":
            with connect(account) as db:
                turns = db.execute("""SELECT role,text FROM conversation_turns
                    WHERE sender_id=? ORDER BY rowid DESC LIMIT 8""",
                    (sender,)).fetchall()
            return respond(200, dict(identity, authorization={
                "allowed": True, "maySend": True, "testSendAuthorized": True,
                "handoffState": "bot", "mode": "tests"},
                turns=[dict(t) for t in reversed(turns)]))

        reason = payload.get("reason")
        if not isinstance(reason, str) or reason not in HANDOFF_REASONS:
            return respond(422, {"error": "invalid_handoff_reason"})
        with connect(account) as db:
            timestamp = now()
            # Same inbound ID and original text; no process_inbound call or extra turn.
            db.execute("""INSERT INTO conversations
                (sender_id,sender_name,subject,summary,last_message,last_message_id,
                 status,updated_at,created_at,choice_state)
                VALUES(?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(sender_id) DO UPDATE SET
                  subject=excluded.subject,summary=excluded.summary,
                  last_message=excluded.last_message,last_message_id=excluded.last_message_id,
                  status='pending',choice_state='idle',choice_message_id='',
                  last_bot_text='',bot_repeat_count=0,fallback_count=0,
                  updated_at=excluded.updated_at""",
                (sender, "Contato", "atendimento", "Nucleo: " + reason,
                 original_text, mid, "pending", timestamp, timestamp, "idle"))
            db.execute("UPDATE stage2_admissions SET action='handoff' WHERE sender_id=? AND message_id=?",
                       (sender, mid))
        return respond(200, dict(identity, action="handoff", recorded=True))
