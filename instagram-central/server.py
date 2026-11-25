#!/usr/bin/env python3
"""Instagram Central behind HTTPS: scoped Editorial publishing, no Direct send, n8n or WhatsApp."""
import base64
import hashlib
import html
import hmac
import json
import logging
import os
import secrets
import re
import unicodedata
import socket
import threading
from contextlib import contextmanager
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from panel_actions import parse_action, token_for
from policy import prepare_decision
import oauth_meta
import instagram_connection
import account_avatar
import sender_profiles
import account_registry
import account_management
import editorial_core
import editorial_http
import editorial_import
import editorial_connections
import editorial_multi_api
import editorial_delivery
import editorial_publishing
import editorial_history
import interface_ui
import automation_policy
import panel_login
import origin_configuration
from urllib.parse import parse_qs, urlsplit, urlencode
from zoneinfo import ZoneInfo

DATA_DIR = Path(os.environ.get("INSTAGRAM_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "instagram.sqlite3"
OPTIONS_PATH = Path(os.environ.get("INSTAGRAM_OPTIONS", "/data/options.json"))
MAX_BODY = 256 * 1024
LOGGER = logging.getLogger("instagram-central")
APP_VERSION = "0.1.62"
HUMAN_OFFER_PROMPT = "Quer que eu encaminhe sua dúvida para um atendente? Responda SIM ou NÃO."
_INBOX_LOCK = threading.Lock()
_AUTOMATION_LOCK = threading.RLock()
META_RESULTS = {
    'authorization_missing': 'Esta conta ainda não tem uma autorização Meta utilizável. Clique em Conectar Instagram pela Meta para autorizar esta conta.',
    'oauth_incomplete': 'A conexão inicial ainda não está preparada. Confira a configuração de autorização abaixo.',
    'token_invalid': 'A Meta recusou a credencial salva ou informou que ela não é mais válida. Reconecte esta conta pela Meta.',
    'permission_denied': 'A Meta recusou o acesso solicitado. Confira as permissões desta conta; nenhuma autorização ou assinatura foi feita automaticamente.',
    'query_failed': 'Não foi possível concluir a consulta à Meta. A autorização anterior foi preservada. Confira o diagnóstico antes de tentar novamente.',
    'subscription_failed': 'Não foi possível confirmar a assinatura de mensagens nesta conta. A conexão existente foi preservada.',
    'storage_error': 'Não foi possível salvar o resultado da consulta. A autorização existente foi preservada.',
    'check_completed': 'Identidade verificada. Confira o token de Página, a tarefa MESSAGING e as permissões no diagnóstico abaixo.',
    'subscription_completed': 'Solicitação de assinatura concluída. Isso ainda não comprova entrega de mensagens reais.',
}

META_ACTION_SCRIPT = """(() => {
  const region = document.getElementById('meta-actions');
  if (!region) return;
  const notice = document.getElementById('meta-action-progress');
  const buttons = Array.from(region.querySelectorAll('button')).map(button =>
    ({button, text: button.textContent, disabled: button.disabled}));
  let busy = false;
  region.addEventListener('submit', event => {
    if (!(event.target instanceof HTMLFormElement)) return;
    if (busy) { event.preventDefault(); return; }
    if (event.defaultPrevented) return;
    busy = true;
    region.setAttribute('aria-busy', 'true');
    buttons.forEach(item => { item.button.disabled = true; });
    const checking = event.target.getAttribute('action').endsWith('/check');
    const button = event.submitter || event.target.querySelector('button');
    if (button) button.textContent = checking ? 'Verificando…' : 'Solicitando assinatura…';
    notice.textContent = checking ? 'Consultando a Meta. Aguarde a conclusão.' :
      'Solicitando assinatura na Meta. Aguarde a conclusão.';
    notice.hidden = false;
  });
  window.addEventListener('pageshow', event => {
    if (!event.persisted) return;
    busy = false;
    region.removeAttribute('aria-busy');
    buttons.forEach(item => {
      item.button.disabled = item.disabled;
      item.button.textContent = item.text;
    });
    notice.hidden = true;
    notice.textContent = '';
  });
})();"""
META_ACTION_CSP = ("default-src 'none'; style-src 'unsafe-inline'; script-src 'sha256-" +
                   base64.b64encode(hashlib.sha256(META_ACTION_SCRIPT.encode('utf-8')).digest()).decode('ascii') +
                   "'; form-action 'self'; base-uri 'none'; object-src 'none'")


def settings():
    try:
        data = json.loads(OPTIONS_PATH.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _open_database():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("PRAGMA busy_timeout=10000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("""CREATE TABLE IF NOT EXISTS inbound (
      recipient_id TEXT NOT NULL,
      sender_id TEXT NOT NULL,
      message_id TEXT NOT NULL,
      message_text TEXT NOT NULL,
      received_at TEXT NOT NULL,
      message_at TEXT,
      PRIMARY KEY(recipient_id, sender_id, message_id))""")
    if "processed_at" not in {r[1] for r in conn.execute("PRAGMA table_info(inbound)")}:
        conn.execute("ALTER TABLE inbound ADD COLUMN processed_at TEXT")
    columns = {r[1] for r in conn.execute("PRAGMA table_info(inbound)")}
    for column in ("claim_token", "claim_until", "message_at", "resume_skipped_at"):
        if column not in columns:
            conn.execute("ALTER TABLE inbound ADD COLUMN " + column + " TEXT")
    if 'source' not in columns:
        conn.execute("ALTER TABLE inbound ADD COLUMN source TEXT NOT NULL DEFAULT 'webhook' CHECK(source IN ('webhook','manual'))")
    conn.execute("""CREATE TABLE IF NOT EXISTS handoff (
      recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'bot' CHECK(state IN ('bot','pending','human','done')),
      updated_at TEXT NOT NULL,
      PRIMARY KEY(recipient_id, sender_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS handoff_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id TEXT NOT NULL,
      sender_id TEXT NOT NULL, old_state TEXT NOT NULL, new_state TEXT NOT NULL,
      changed_at TEXT NOT NULL, actor TEXT NOT NULL, reason TEXT)""")
    if "reason" not in {row[1] for row in conn.execute("PRAGMA table_info(handoff_audit)")}:
        conn.execute("ALTER TABLE handoff_audit ADD COLUMN reason TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS drafts (
      recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
      draft_text TEXT NOT NULL, draft_source TEXT NOT NULL DEFAULT 'lab',
      created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','discarded')),
      PRIMARY KEY(recipient_id,sender_id,message_id))""")
    conn.execute('''CREATE TABLE IF NOT EXISTS publication_downloads (
      token_hash TEXT PRIMARY KEY,business_id TEXT NOT NULL,post_id TEXT NOT NULL,
      media_id TEXT NOT NULL,expires_at INTEGER NOT NULL,revision INTEGER NOT NULL,run_id TEXT NOT NULL)''')
    automation_policy.ensure_schema(conn)
    conn.execute("""CREATE TABLE IF NOT EXISTS automation_sends (
      recipient_id TEXT NOT NULL,
      sender_id TEXT NOT NULL,
      message_id TEXT NOT NULL,
      status TEXT NOT NULL CHECK(status IN ('sending','sent','failed')),
      remote_message_id TEXT,
      error_reason TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      PRIMARY KEY(recipient_id,sender_id,message_id)
    )""")
    send_columns = {row[1] for row in conn.execute("PRAGMA table_info(automation_sends)")}
    if "reply_text" not in send_columns:
        conn.execute("ALTER TABLE automation_sends ADD COLUMN reply_text TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS human_offers (
      recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
      created_at TEXT NOT NULL, PRIMARY KEY(recipient_id,sender_id))""")
    return conn


@contextmanager
def database():
    """Commit/rollback and close SQLite handles after every operation."""
    conn = _open_database()
    try:
        with conn:
            yield conn
    finally:
        conn.close()


def bridge_authorized(headers, cfg):
    expected = str(cfg.get("bridge_secret") or "")
    provided = headers.get("X-Instagram-Bridge-Secret", "")
    return (isinstance(provided, str) and len(expected) >= 32 and
            hmac.compare_digest(provided.encode("utf-8"), expected.encode("utf-8")))


def _utc_now():
    return datetime.now(timezone.utc)


def primary_meta_id(cfg=None):
    """The legacy bridge may operate only the Umdoislab tenant."""
    current = settings() if cfg is None else cfg
    with database() as conn:
        account_registry.ensure_primary(conn, current.get("instagram_account_id"))
        return account_registry.require_business(
            conn, account_registry.PRIMARY_BUSINESS)["instagram_account_id"]


def within_messaging_window(received_at, now=None):
    try:
        received = datetime.fromisoformat(str(received_at).replace("Z", "+00:00"))
        current = now or _utc_now()
        if received.utcoffset() is None:
            return False
        age = current - received
        return timedelta(seconds=-60) <= age <= timedelta(hours=24)
    except (ValueError, TypeError, AttributeError, OverflowError):
        return False


def list_pending(limit=50, *, account_id=None):
    """Read-only queue for a single Meta recipient, never the whole database."""
    if account_id is None:
        account_id = primary_meta_id()
    with database() as conn:
        now = _utc_now()
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_id,
            i.message_text, i.received_at,
            COALESCE(h.state, 'bot') AS handoff_state
            FROM inbound i LEFT JOIN handoff h
              ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
            LEFT JOIN automation_policy ap ON ap.recipient_id=i.recipient_id
            LEFT JOIN automation_contacts ex ON ex.recipient_id=i.recipient_id
              AND ex.sender_id=i.sender_id AND ex.category='excluded'
            LEFT JOIN automation_contacts te ON te.recipient_id=i.recipient_id
              AND te.sender_id=i.sender_id AND te.category='test'
            WHERE i.processed_at IS NULL AND i.source='webhook' AND i.recipient_id=?
              AND ex.sender_id IS NULL
              AND (COALESCE(ap.mode,'tests')='all' OR te.sender_id IS NOT NULL)
              AND i.message_at IS NOT NULL
              AND datetime(i.message_at)>=datetime(?)
              AND datetime(i.message_at)<=datetime(?)
            ORDER BY i.received_at, i.rowid LIMIT ?""",
            (account_id, (now-timedelta(hours=24)).isoformat(),
             (now+timedelta(minutes=1)).isoformat(), min(max(int(limit), 1), 50))).fetchall()
        rows = [row for row in rows if automation_policy.allowed(conn, row[0], row[1])]
    return [{"channel": "instagram", "accountId": r[0],
             "senderId": r[1], "messageId": r[2], "messageText": r[3],
             "receivedAt": r[4], "handoffState": r[5]} for r in rows]


def claim_message(lease_seconds=120, *, account_id=None):
    """Reserve a message only within the authorized recipient queue."""
    if account_id is None:
        account_id = primary_meta_id()
    now = _utc_now()
    now_iso = now.isoformat()
    until_iso = (now + timedelta(seconds=lease_seconds)).isoformat()
    token = secrets.token_urlsafe(32)
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_id,
          i.message_text, i.received_at, i.message_at, COALESCE(h.state, 'bot')
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          LEFT JOIN automation_policy ap ON ap.recipient_id=i.recipient_id
          LEFT JOIN automation_contacts ex ON ex.recipient_id=i.recipient_id
            AND ex.sender_id=i.sender_id AND ex.category='excluded'
          LEFT JOIN automation_contacts te ON te.recipient_id=i.recipient_id
            AND te.sender_id=i.sender_id AND te.category='test'
          WHERE i.processed_at IS NULL AND i.source='webhook' AND i.recipient_id=?
            AND COALESCE(h.state, 'bot')='bot' AND ex.sender_id IS NULL
            AND (COALESCE(ap.mode,'tests')='all' OR te.sender_id IS NOT NULL)
            AND (i.claim_until IS NULL OR i.claim_until <= ?)
            AND NOT EXISTS (SELECT 1 FROM inbound active
              WHERE active.recipient_id=i.recipient_id AND active.sender_id=i.sender_id
                AND active.message_id<>i.message_id AND active.processed_at IS NULL
                AND active.claim_until>?)
            AND i.message_at IS NOT NULL
            AND datetime(i.message_at)>=datetime(?)
            AND datetime(i.message_at)<=datetime(?)
          ORDER BY i.received_at, i.rowid LIMIT 50""",
          (account_id, now_iso, now_iso, (now-timedelta(hours=24)).isoformat(),
           (now+timedelta(minutes=1)).isoformat())).fetchall()
        row = next((candidate for candidate in rows
                    if automation_policy.allowed(conn, candidate[0], candidate[1])
                    and within_messaging_window(candidate[5], now)), None)
        if row is None:
            return None
        conn.execute("""UPDATE inbound SET claim_token=?, claim_until=?
          WHERE recipient_id=? AND sender_id=? AND message_id=? AND processed_at IS NULL""",
          (token, until_iso, row[0], row[1], row[2]))
    return {"channel": "instagram", "accountId": row[0], "senderId": row[1],
            "messageId": row[2], "messageText": row[3], "receivedAt": row[4],
            "messageAt": row[5], "handoffState": row[6],
            "claimToken": token, "claimUntil": until_iso}


def send_automatic_reply(data, cfg, credential, sender=instagram_connection.send_text_message):
    """Send only a live, test-policy-authorized inbound reply; never retry an uncertain send."""
    keys = {"accountId", "senderId", "messageId", "claimToken", "text"}
    if not isinstance(data, dict) or set(data) not in (keys, keys | {"kind"}):
        return {"status": "rejected", "reason": "invalid_payload"}
    kind = data.get("kind", "normal")
    if kind not in ("normal", "human_offer"):
        return {"status": "rejected", "reason": "invalid_payload"}
    account, profile, mid, token, text = (data["accountId"], data["senderId"],
        data["messageId"], data["claimToken"], data["text"])
    if kind == "human_offer":
        if text != "":
            return {"status": "rejected", "reason": "invalid_payload"}
        text = HUMAN_OFFER_PROMPT
    if (not _valid_message_identity(account, profile, mid) or
            not isinstance(token, str) or not 32 <= len(token) <= 256 or
            not isinstance(text, str) or not 1 <= len(text.strip().encode("utf-8")) <= 1000):
        return {"status": "rejected", "reason": "invalid_payload"}
    if account != cfg.get("instagram_account_id"):
        return {"status": "rejected", "reason": "wrong_account"}
    now = _utc_now()
    now_iso = now.isoformat()
    with _AUTOMATION_LOCK:
        with database() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute("""SELECT i.message_at,COALESCE(h.state,'bot'),i.message_text
              FROM inbound i LEFT JOIN handoff h
                ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
              WHERE i.recipient_id=? AND i.sender_id=? AND i.message_id=?
                AND i.source='webhook' AND i.processed_at IS NULL
                AND i.message_at IS NOT NULL
                AND i.claim_token=? AND i.claim_until>?""",
              (account, profile, mid, token, now_iso)).fetchone()
            # Semantic classification is owned by the shared n8n core.
            # The Central retains the independent authorization/security gates.
            if (row is None or row[1] != "bot" or not isinstance(row[2], str)
                    or not row[2].strip()
                    or not automation_policy.allowed_test_send(conn, account, profile)):
                return {"status": "rejected", "reason": "claim_or_policy_invalid"}
            if not within_messaging_window(row[0], now):
                return {"status": "rejected", "reason": "outside_messaging_window"}
            if conn.execute("""SELECT 1 FROM automation_sends
                WHERE recipient_id=? AND sender_id=? AND message_id=?""",
                (account, profile, mid)).fetchone():
                return {"status": "rejected", "reason": "already_attempted"}
            conn.execute("""INSERT INTO automation_sends
                (recipient_id,sender_id,message_id,status,created_at,updated_at)
                VALUES(?,?,?,'sending',?,?)""", (account, profile, mid, now_iso, now_iso))
        try:
            result = sender(cfg, credential, profile, text.strip())
        except instagram_connection.GraphError as exc:
            reason = str(exc.details.get("reason") or "provider_error")
            failed = True
        except instagram_connection.ConnectionError:
            reason = "configuration_incomplete"
            failed = True
        except Exception:
            reason = "transport_error"
            failed = True
        else:
            failed = False
        completed = _utc_now().isoformat()
        if failed:
            with database() as conn:
                conn.execute("""UPDATE automation_sends SET status='failed',error_reason=?,updated_at=?
                    WHERE recipient_id=? AND sender_id=? AND message_id=? AND status='sending'""",
                    (reason, completed, account, profile, mid))
                conn.execute("""UPDATE inbound SET processed_at=?,claim_token=NULL,claim_until=NULL
                    WHERE recipient_id=? AND sender_id=? AND message_id=? AND claim_token=?""",
                    (completed, account, profile, mid, token))
            return {"status": "failed", "reason": reason}
        with database() as conn:
            conn.execute("""UPDATE automation_sends SET status='sent',remote_message_id=?,reply_text=?,updated_at=?
                WHERE recipient_id=? AND sender_id=? AND message_id=? AND status='sending'""",
                (result["message_id"], text.strip(), completed, account, profile, mid))
            # Keep only the eight most recent bot reply texts for this conversation.
            # Send receipts remain intact so idempotency is never weakened.
            conn.execute("""UPDATE automation_sends SET reply_text=NULL
                WHERE recipient_id=? AND sender_id=? AND status='sent' AND reply_text IS NOT NULL
                  AND message_id NOT IN (
                    SELECT message_id FROM automation_sends
                    WHERE recipient_id=? AND sender_id=? AND status='sent' AND reply_text IS NOT NULL
                    ORDER BY updated_at DESC LIMIT 8)""",
                (account, profile, account, profile))
            if kind == "human_offer":
                conn.execute("""INSERT INTO human_offers VALUES(?,?,?,?)
                  ON CONFLICT(recipient_id,sender_id) DO UPDATE SET
                  message_id=excluded.message_id,created_at=excluded.created_at""",
                  (account,profile,mid,completed))
            conn.execute("""UPDATE inbound SET processed_at=?,claim_token=NULL,claim_until=NULL
                WHERE recipient_id=? AND sender_id=? AND message_id=? AND claim_token=?""",
                (completed, account, profile, mid, token))
        return {"status": "sent", "messageId": result["message_id"]}


def conversation_context(data):
    """Return bounded, account-scoped turns for the shared conversation core."""
    keys = {"accountId", "senderId", "messageId", "claimToken"}
    if not isinstance(data, dict) or set(data) != keys:
        return None
    account, sender, message_id, claim = (data["accountId"], data["senderId"],
        data["messageId"], data["claimToken"])
    if (not _valid_message_identity(account, sender, message_id) or
            not isinstance(claim, str) or not 32 <= len(claim) <= 256):
        return None
    now = _utc_now()
    with database() as conn:
        current = conn.execute("""SELECT i.message_at,COALESCE(h.state,'bot'),i.rowid,i.message_text,i.received_at
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          WHERE i.recipient_id=? AND i.sender_id=? AND i.message_id=?
            AND i.source='webhook' AND i.processed_at IS NULL
            AND i.claim_token=? AND i.claim_until>?""",
          (account, sender, message_id, claim, now.isoformat())).fetchone()
        if (current is None or current[1] != "bot" or current[0] is None
                or not automation_policy.allowed_test_send(conn, account, sender)
                or not within_messaging_window(current[0], now)):
            return None
        inbound_rows = conn.execute("""SELECT message_text,message_at
          FROM inbound WHERE recipient_id=? AND sender_id=? AND source='webhook'
            AND message_at IS NOT NULL AND message_text<>''
          AND message_at<=? AND rowid<?
          ORDER BY message_at DESC,rowid DESC LIMIT 12""", (account, sender,current[0],current[2])).fetchall()
        reply_rows = conn.execute("""SELECT s.reply_text,s.updated_at
          FROM automation_sends s JOIN inbound i ON i.recipient_id=s.recipient_id
            AND i.sender_id=s.sender_id AND i.message_id=s.message_id
          WHERE s.recipient_id=? AND s.sender_id=? AND s.status='sent'
            AND s.reply_text IS NOT NULL AND s.reply_text<>''
            AND i.message_at<=? AND i.rowid<? AND s.updated_at<=?
          ORDER BY s.updated_at DESC LIMIT 12""", (account,sender,current[0],current[2],current[4])).fetchall()
    turns = ([{"role": "client", "text": row[0], "createdAt": row[1]}
              for row in inbound_rows] +
             [{"role": "assistant", "text": row[0], "createdAt": row[1]}
              for row in reply_rows])
    turns.sort(key=lambda turn: turn["createdAt"])
    return {"accountId": account, "senderId": sender, "messageId": message_id,
            "turns": turns[-7:] + [{"role": "client", "text": current[3],
                                    "createdAt": current[0]}]}


def acknowledge_message(data):
    """Only the owner of an unexpired claim can ACK; stale retries fail closed."""
    if not isinstance(data, dict) or set(data) != {"accountId", "senderId", "messageId", "claimToken"}:
        return False
    account, sender, mid, token = (data["accountId"], data["senderId"],
                                   data["messageId"], data["claimToken"])
    if not _valid_message_identity(account, sender, mid):
        return False
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        return False
    with database() as conn:
        cur = conn.execute("""UPDATE inbound SET processed_at=?, claim_token=NULL, claim_until=NULL
          WHERE recipient_id=? AND sender_id=? AND message_id=?
            AND source='webhook' AND processed_at IS NULL AND claim_token=? AND claim_until > ?""",
          (_utc_now().isoformat(), account, sender, mid, token, _utc_now().isoformat()))
        return cur.rowcount == 1


def confirmed_human_offer(conn, account, sender, mid, text, now):
    """Only the first new webhook after a successfully accepted offer may confirm it."""
    normalized = "".join(c for c in unicodedata.normalize("NFD", text.lower())
                         if unicodedata.category(c) != "Mn").strip(" .!?")
    if normalized not in ("sim", "s", "pode", "pode sim", "quero", "por favor", "sim por favor"):
        return False
    offer = conn.execute("""SELECT message_id,created_at FROM human_offers
      WHERE recipient_id=? AND sender_id=?""", (account,sender)).fetchone()
    if not offer:
        return False
    try:
        at = datetime.fromisoformat(offer[1])
        if not timedelta(0) <= now-at <= timedelta(hours=2):
            return False
    except (TypeError, ValueError):
        return False
    # A delayed or already queued message cannot become a confirmation.
    first = conn.execute("""SELECT i.message_id FROM inbound i
      JOIN inbound original ON original.recipient_id=i.recipient_id
        AND original.sender_id=i.sender_id AND original.message_id=?
      WHERE i.recipient_id=? AND i.sender_id=? AND i.source='webhook'
        AND i.rowid>original.rowid AND i.received_at>=? AND i.message_at>=?
      ORDER BY i.rowid LIMIT 1""", (offer[0],account,sender,offer[1],offer[1])).fetchone()
    return first is not None and first[0] == mid


def evaluate_claim(data):
    """Classify only an active owned lease; never generate/send a response."""
    keys = {"accountId", "senderId", "messageId", "claimToken"}
    if not isinstance(data, dict) or set(data) != keys:
        return None
    values = [data[k] for k in ("accountId", "senderId", "messageId", "claimToken")]
    if not _valid_message_identity(*values[:3]):
        return None
    if not isinstance(values[3], str) or not 32 <= len(values[3]) <= 256:
        return None
    with database() as conn:
        row = conn.execute("""SELECT i.message_text, COALESCE(h.state, 'bot'), i.message_at
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          WHERE i.recipient_id=? AND i.sender_id=? AND i.message_id=?
            AND i.source='webhook' AND i.message_at IS NOT NULL
            AND i.claim_token=? AND i.claim_until>? AND i.processed_at IS NULL""",
          (*values, _utc_now().isoformat())).fetchone()
        if (row is None or row[2] is None or
                not automation_policy.allowed(conn, values[0], values[1]) or
                not within_messaging_window(row[2])):
            return None
        test_send = automation_policy.allowed_test_send(conn, values[0], values[1])
        if (test_send and row[1] == "bot" and
                confirmed_human_offer(conn, values[0], values[1], values[2], row[0], _utc_now())):
            return {"action": "human_review", "maySend": False, "mayCallGemini": False,
                    "testSendAuthorized": False}
    if row is None:
        return None
    decision = prepare_decision({
        "channel": "instagram", "accountId": values[0], "senderId": values[1],
        "messageId": values[2], "claimToken": values[3],
        "messageText": row[0], "handoffState": row[1]})
    decision["maySend"] = test_send and decision["mayCallGemini"] is True
    decision["testSendAuthorized"] = decision["maySend"]
    return decision


def save_draft(data):
    """Save a review-only draft against a valid lease. NEVER sends a message."""
    keys = {"accountId", "senderId", "messageId", "claimToken", "draftText"}
    if not isinstance(data, dict) or set(data) != keys:
        return False
    text = data["draftText"]
    if not isinstance(text, str) or not 1 <= len(text.strip()) <= 1000:
        return False
    reference = {key: data[key] for key in ("accountId", "senderId", "messageId", "claimToken")}
    decision = evaluate_claim(reference)
    if decision is None or decision["action"] in ("reject", "hold_for_human"):
        return False
    now = _utc_now().isoformat()
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        eligible = conn.execute("""SELECT 1 FROM inbound i
          LEFT JOIN handoff h ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          WHERE i.recipient_id=? AND i.sender_id=? AND i.message_id=?
            AND i.claim_token=? AND i.claim_until>?
            AND i.source='webhook' AND i.processed_at IS NULL AND COALESCE(h.state, 'bot')='bot'""",
          (reference["accountId"], reference["senderId"], reference["messageId"],
           reference["claimToken"], now)).fetchone()
        if eligible is None:
            return False
        inserted = conn.execute("""INSERT OR IGNORE INTO drafts
          (recipient_id,sender_id,message_id,draft_text,draft_source,created_at)
          VALUES(?,?,?,?,?,?)""",
          (reference["accountId"], reference["senderId"], reference["messageId"],
           text.strip(), "lab", now))
        return inserted.rowcount == 1


def set_handoff(data, *, actor="system", reason=None, claim=None):
    if not isinstance(data, dict) or set(data) != {"accountId", "senderId", "state"}:
        return False
    account, sender, state = data["accountId"], data["senderId"], data["state"]
    if (not isinstance(account, str) or not 1 <= len(account) <= 160 or
        not isinstance(sender, str) or not 1 <= len(sender) <= 160 or
        state not in ("bot", "pending", "human", "done")):
        return False
    with _AUTOMATION_LOCK, database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        found = conn.execute("""SELECT 1 FROM inbound WHERE recipient_id=? AND sender_id=? LIMIT 1""",
                             (account, sender)).fetchone()
        if not found:
            return False
        prev = conn.execute("SELECT state FROM handoff WHERE recipient_id=? AND sender_id=?",
                            (account, sender)).fetchone()
        old_state = prev[0] if prev else "bot"
        if claim is not None:
            # New adapter effects are bound to the exact current live claim.
            # Legacy panel callers retain their existing contract.
            mid, token = claim
            now_dt = _utc_now()
            if (state != "pending" or old_state != "bot"
                    or not _valid_message_identity(account, sender, mid)
                    or not isinstance(token, str) or not 32 <= len(token) <= 256
                    or not automation_policy.allowed_test_send(conn, account, sender)):
                return False
            row = conn.execute("""SELECT message_at FROM inbound
              WHERE recipient_id=? AND sender_id=? AND message_id=? AND source='webhook'
                AND processed_at IS NULL AND claim_token=? AND claim_until>?""",
                (account, sender, mid, token, now_dt.isoformat())).fetchone()
            if not row or not within_messaging_window(row[0], now_dt):
                return False
        if old_state == state:
            return True
        now = _utc_now().isoformat()
        conn.execute("DELETE FROM human_offers WHERE recipient_id=? AND sender_id=?", (account,sender))
        conn.execute("""INSERT INTO handoff VALUES(?,?,?,?)
          ON CONFLICT(recipient_id,sender_id) DO UPDATE SET
          state=excluded.state, updated_at=excluded.updated_at""",
          (account, sender, state, now))
        conn.execute("""INSERT INTO handoff_audit
          (recipient_id,sender_id,old_state,new_state,changed_at,actor,reason)
          VALUES(?,?,?,?,?,?,?)""", (account, sender, old_state, state, now, actor, reason))
        # Resume only on new inbound. Close the historical queue atomically,
        # retaining the messages and an explicit reason separate from send receipts.
        if state == "bot":
            conn.execute("""UPDATE inbound SET processed_at=?, resume_skipped_at=?,
              claim_token=NULL, claim_until=NULL
              WHERE recipient_id=? AND sender_id=? AND source='webhook'
                AND processed_at IS NULL""", (now, now, account, sender))
        # Invalidate any active reservation before handing the conversation to a human.
        else:
            conn.execute("""UPDATE inbound SET claim_token=NULL, claim_until=NULL
              WHERE recipient_id=? AND sender_id=? AND processed_at IS NULL""", (account, sender))
    return True


def signature_valid(body, signature, app_secret):
    if not app_secret or not isinstance(signature, str) or len(signature) != 71:
        return False
    if not signature.startswith("sha256=") or any(c not in "0123456789abcdef" for c in signature[7:]):
        return False
    digest = hmac.new(app_secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest("sha256=" + digest, signature)


def _message_envelopes(payload):
    """Yield bounded message events from both documented Instagram envelopes."""
    if not isinstance(payload, dict) or payload.get("object") != "instagram":
        return
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return
    for entry in entries[:100]:
        if not isinstance(entry, dict):
            continue
        legacy = entry.get("messaging")
        for event in legacy[:100] if isinstance(legacy, list) else []:
            if isinstance(event, dict):
                yield "legacy", event
        changes = entry.get("changes")
        for change in changes[:100] if isinstance(changes, list) else []:
            if (isinstance(change, dict) and change.get("field") == "messages"
                    and isinstance(change.get("value"), dict)):
                yield "unified", change["value"]


def _valid_message_identity(account, sender, mid):
    return (all(isinstance(v, str) and 1 <= len(v) <= 160 for v in (account,sender)) and
            isinstance(mid, str) and 1 <= len(mid) <= instagram_connection.MAX_MESSAGE_ID and
            not any(ord(c)<32 for c in mid))


def normalized_messages(payload, account_id=None):
    """Only normal text messages, scoped to permitted Meta recipient IDs."""
    if not isinstance(payload, dict) or payload.get("object") != "instagram":
        return []
    allowed = (frozenset(value for value in account_id
                         if isinstance(value, str) and value)
               if isinstance(account_id, (list, set, frozenset, tuple))
               else frozenset((account_id,)) if isinstance(account_id, str) and account_id
               else frozenset())
    found = []
    for _, ev in _message_envelopes(payload):
        if not isinstance(ev, dict):
            continue
        msg = ev.get("message")
        sender = ev.get("sender")
        recipient = ev.get("recipient")
        if not isinstance(msg, dict) or not isinstance(sender, dict) or not isinstance(recipient, dict):
            continue
        if msg.get("is_echo") is True:
            continue
        sender_id = sender.get("id")
        recipient_id = recipient.get("id")
        mid = msg.get("mid")
        text = msg.get("text")
        if not isinstance(recipient_id, str) or recipient_id not in allowed:
            continue  # reject unknown/disabled recipients; preserve official accountId
        if sender_id == recipient_id:
            continue  # never treat business-originated content as a customer request
        if not _valid_message_identity(recipient_id, sender_id, mid):
            continue
        if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
            continue
        found.append((recipient_id, sender_id, mid, text.strip()))
    return found


def webhook_diagnostics(body, account_id):
    """Counts only; never log event fields, identifiers, text or credentials."""
    payload = json.loads(body)
    counts = {"legacy": 0, "unified": 0, "recipient_match": 0}
    for shape, event in _message_envelopes(payload):
        counts[shape] += 1
        recipient = event.get("recipient")
        if isinstance(recipient, dict) and recipient.get("id") == account_id:
            counts["recipient_match"] += 1
    counts["matched_text"] = len(normalized_messages(payload, account_id))
    return counts


def webhook_message_times(payload, account_id):
    """Map accepted incoming message identities to Meta event time (milliseconds)."""
    found = {}
    for _, event in _message_envelopes(payload):
        message = event.get("message")
        sender = event.get("sender")
        recipient = event.get("recipient")
        if (not isinstance(message, dict) or message.get("is_echo") is True or
                not isinstance(sender, dict) or not isinstance(recipient, dict) or
                recipient.get("id") != account_id):
            continue
        mid, sender_id, stamp = message.get("mid"), sender.get("id"), event.get("timestamp")
        if (not isinstance(mid, str) or not isinstance(sender_id, str) or
                type(stamp) not in (int, float) or stamp <= 0):
            continue
        try:
            moment = datetime.fromtimestamp(stamp / 1000, timezone.utc)
        except (ValueError, OverflowError, OSError):
            continue
        if moment <= _utc_now() + timedelta(minutes=1):
            found[(account_id, sender_id, mid)] = moment.isoformat()
    return found


def persist(body, account_id=None):
    """Route signed events by known recipient, never by caller-provided business_id."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    # Only a payload already matching the configured legacy recipient can
    # bootstrap the single existing account; arbitrary events cannot remap it.
    legacy_messages = normalized_messages(payload, account_id)
    event_times = webhook_message_times(payload, account_id)
    inserted = 0
    with database() as conn:
        conn.execute("BEGIN IMMEDIATE")
        account_registry.prepare(conn)
        if legacy_messages:
            account_registry.ensure_primary(conn, account_id)
        # Do not activate secondary tenants through the legacy single-account
        # webhook. Future multi-account webhook auth must explicitly authorize them.
        allowed = account_registry.active_meta_ids(conn).intersection((account_id,))
        messages = normalized_messages(payload, allowed)
        for rid, sid, mid, msg in messages:
            if account_registry.resolve_meta(conn, rid) is None:
                continue
            cursor = conn.execute(
                """INSERT INTO inbound
                (recipient_id,sender_id,message_id,message_text,received_at,message_at)
                VALUES(?,?,?,?,?,?) ON CONFLICT(recipient_id,sender_id,message_id) DO UPDATE SET
                source='webhook',message_text=excluded.message_text,received_at=excluded.received_at,
                message_at=excluded.message_at,processed_at=NULL,claim_token=NULL,claim_until=NULL,
                resume_skipped_at=NULL
                WHERE inbound.source='manual'""",
                (rid, sid, mid, msg, datetime.now(timezone.utc).isoformat(),
                 event_times.get((rid, sid, mid))))
            inserted += cursor.rowcount
            # A delayed webhook (including promotion of a manual import) must not
            # reopen a pre-resume message. The bot handoff timestamp is the cutoff.
            if cursor.rowcount:
                conn.execute("""UPDATE inbound SET processed_at=h.updated_at,
                    resume_skipped_at=h.updated_at,claim_token=NULL,claim_until=NULL
                    FROM handoff h
                    WHERE inbound.recipient_id=? AND inbound.sender_id=? AND inbound.message_id=?
                      AND inbound.recipient_id=h.recipient_id AND inbound.sender_id=h.sender_id
                      AND h.state='bot' AND inbound.source='webhook' AND inbound.processed_at IS NULL
                      AND (inbound.message_at IS NULL OR
                           julianday(inbound.message_at)<=julianday(h.updated_at))""",
                    (rid, sid, mid))
    return inserted


def refresh_inbox(cfg, credential):
    """Explicit owner request only. Imports cannot enter the automatic bridge queue."""
    if not _INBOX_LOCK.acquire(blocking=False):
        return {'status': 'error', 'reason': 'busy'}
    try:
        messages, report = instagram_connection.read_recent_inbox(cfg, credential)
        inserted = 0
        with database() as conn:
            conn.execute('BEGIN IMMEDIATE')
            business = account_registry.require_business(conn, cfg.get('business_id', account_registry.PRIMARY_BUSINESS))
            if business['instagram_account_id'] != cfg['instagram_account_id']:
                raise instagram_connection.GraphError('configuration_incomplete')
            manual_hold = _utc_now().isoformat()
            for row in messages:
                cursor = conn.execute('''INSERT OR IGNORE INTO inbound
                    (recipient_id,sender_id,message_id,message_text,received_at,source,processed_at)
                    VALUES(?,?,?,?,?,'manual',?)''', (*row, manual_hold))
                inserted += cursor.rowcount
        LOGGER.info('Meta manual inbox completed: version=%s conversations=%s scanned=%s stored=%s direct_reads=%s unavailable=%s expansion_shapes=%s unavailable_reasons=%s',
                    APP_VERSION, report['conversations'], report['scanned'], inserted,
                    report['fallback_requests'], report['unavailable_conversations'], report['expansion_shapes'], report['unavailable_reasons'])
        return {**report, 'status': 'confirmed', 'imported': inserted,
                'existing': len(messages) - inserted}
    except instagram_connection.GraphError as exc:
        LOGGER.info('Meta manual inbox failed: version=%s reason=%s conversations=%s direct_reads=%s expansion_shapes=%s',
                    APP_VERSION, exc.details['reason'], exc.details.get('conversations'),
                    exc.details.get('fallback_requests'), exc.details.get('expansion_shapes'))
        return {'status': 'error', **{k:v for k,v in exc.details.items() if v is not None}}
    except (instagram_connection.ConnectionError, account_registry.RegistryError):
        return {'status': 'error', 'reason': 'configuration_incomplete'}
    except (sqlite3.Error, OSError):
        return {'status': 'error', 'reason': 'storage_error'}
    finally:
        _INBOX_LOCK.release()


def panel_session_authorized(headers, cfg):
    """Browser authentication uses an opaque, expiring, revocable cookie."""
    password = cfg.get("panel_password")
    cookie = headers.get("Cookie", "")
    if panel_login.cookie_token(cookie) is None:
        return False
    try:
        with database() as conn:
            return panel_login.valid_session(conn, cookie, password)
    except (OSError, sqlite3.Error, ValueError):
        return False


def safe_login_return(value):
    """Allow only local, read-only UI destinations, never arbitrary redirects."""
    if not isinstance(value, str) or len(value) > 1024 or not value.startswith('/') or value.startswith('//'):
        return ''
    if any(ord(ch) < 33 or ord(ch) > 126 or ch == '\\' for ch in value):
        return ''
    try:
        route = urlsplit(value)
    except ValueError:
        return ''
    if route.scheme or route.netloc:
        return ''
    path, query, fragment = route.path, route.query, route.fragment
    account = r'/accounts/[a-z][a-z0-9_-]{1,39}'
    if path == '/accounts':
        if query and not re.fullmatch(r'account=[a-z][a-z0-9_-]{1,39}', query):
            return ''
        if fragment not in ('', 'add-account'):
            return ''
    elif re.fullmatch(r'(?:' + account + r')?/editorial/?', path):
        if query or fragment not in ('', 'overview', 'calendar', 'editor', 'library', 'approval', 'history'):
            return ''
    elif path in ('/', '/panel') or re.fullmatch(account + r'(?:/panel|/)?', path):
        query = panel_navigation_query(query)
        if query and settings_result(query) is None:
            return ''
        if fragment not in ('', 'connection'):
            return ''
    else:
        return ''
    return path + ('?' + query if query else '') + ('#' + fragment if fragment else '')


def login_return_query(query):
    try:
        fields = parse_qs(query, keep_blank_values=True, max_num_fields=1)
    except ValueError:
        return ''
    values = fields.get('return_to', [])
    return safe_login_return(values[0]) if len(values) == 1 else ''


def render_login(cfg=None, invalid=False, locked=False, return_to='', expired=False):
    """Own HTML form. Chrome can offer to save its standard username/password."""
    cfg = cfg or {}
    try:
        origin = origin_configuration.public_origin(cfg)
    except ValueError:
        origin = ""
    standalone_link = ('<p><a href="' + html.escape(origin + '/panel', quote=True) +
                       '" target="_blank" rel="noopener noreferrer">Abrir Central em janela própria</a></p>') if origin else ''
    instagram_mark = '''<div class="instagram-mark" aria-label="Instagram">
<svg viewBox="0 0 100 100" role="img" aria-label="Instagram">
<defs><linearGradient id="instagram-gradient" x1="0" y1="1" x2="1" y2="0"><stop offset="0" stop-color="#ffb900"/><stop offset=".35" stop-color="#ff3d55"/><stop offset=".68" stop-color="#c52bd4"/><stop offset="1" stop-color="#6542e8"/></linearGradient></defs>
<rect x="3" y="3" width="94" height="94" rx="27" fill="url(#instagram-gradient)"/>
<rect x="22" y="22" width="56" height="56" rx="17" fill="none" stroke="#fff" stroke-width="7"/>
<circle cx="50" cy="50" r="13" fill="none" stroke="#fff" stroke-width="7"/>
<circle cx="70" cy="30" r="4.5" fill="#fff"/>
</svg></div>'''
    configured = isinstance(cfg.get("panel_password"), str) and len(cfg["panel_password"]) >= 16
    if not configured:
        notice = '<p class="notice" role="alert">Configure uma senha de pelo menos 16 caracteres nas opções do aplicativo.</p>'
    elif locked:
        notice = '<p class="notice" role="alert">Muitas tentativas. Tente novamente em alguns minutos.</p>'
    elif invalid:
        notice = '<p class="notice" role="alert">Usuário ou senha incorretos.</p>'
    elif expired:
        notice = '<p class="notice" role="status">Sua sessão expirou. Entre novamente para continuar.</p>'
    else:
        notice = ''
    target = safe_login_return(return_to)
    hidden = ('<input type="hidden" name="return_to" value="' + html.escape(target, quote=True) + '">' if target else '')
    fields = ("""<form method="post" action="/auth/login" autocomplete="on">""" + hidden + """
      <input id="username" name="username" type="text" placeholder="Usuário"
        aria-label="Usuário" autocomplete="username" autocapitalize="off" spellcheck="false" required>
      <input id="password" name="password" type="password" placeholder="Senha"
        aria-label="Senha" autocomplete="current-password" required>
      <button type="submit">Entrar</button></form>""" if configured else "")
    return ("""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar — Central Instagram</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:1.2rem;
 font-family:system-ui,-apple-system,sans-serif;background:#0b1420;color:#17243b}
main{width:min(100%,430px);background:#fff;padding:clamp(1.5rem,5vw,2.3rem);
 border:1px solid #d7dfeb;border-radius:18px;box-shadow:0 18px 48px #0005}
.kicker{color:#a83e16;text-transform:uppercase;letter-spacing:.08em;font-size:.78rem;font-weight:800}
h1{color:#14243c;font-size:1.65rem;line-height:1.2;margin:.7rem 0 .3rem}
p{color:#33445b;line-height:1.5;font-size:.94rem}
.instagram-mark{display:grid;place-items:center;margin:1.1rem auto 1.35rem;width:76px;height:76px}
.instagram-mark svg{display:block;width:76px;height:76px;filter:drop-shadow(0 5px 9px #152f5628)}
form{display:grid;gap:.7rem;margin-top:1.2rem}
input{font:inherit;width:100%;min-height:48px;padding:.8rem .85rem;border:1px solid #8999ad;border-radius:9px;background:#fff;color:#14243c}
input::placeholder{color:#43536a;opacity:1}
input:focus-visible,button:focus-visible,a:focus-visible{outline:3px solid #2768c7;outline-offset:2px}
button{font:inherit;margin-top:.25rem;min-height:48px;padding:.8rem;cursor:pointer;border:0;border-radius:9px;
 background:#152f56;color:#fff;font-weight:750}
button:hover{background:#244978}
.notice{padding:.8rem;border-radius:9px;background:#fff1e8;color:#813613}
small{display:block;color:#33445b;margin-top:1.1rem}
@media(max-width:420px){body{padding:12px}main{padding:24px 20px}.instagram-mark{margin:.8rem auto 1rem}}
</style></head><body><main>
<div class="kicker">Umdoislab · acesso administrativo</div>
<h1>Central Instagram</h1>
<p>Entre para acessar as mensagens e a fila local.</p>
"""
        + notice + standalone_link + instagram_mark + fields +
        "<small>Use a senha cadastrada nas configurações da Central. "
        "O Chrome pode oferecer para salvá-la.</small></main></body></html>")


def _login_form_fields(raw):
    if not isinstance(raw, bytes) or len(raw) > 4096:
        return None
    try:
        fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=3)
    except (ValueError, UnicodeDecodeError):
        return None
    if not {"username", "password"} <= set(fields) or set(fields) - {"username", "password", "return_to"} or any(len(v) != 1 for v in fields.values()):
        return None
    return fields["username"][0], fields["password"][0], safe_login_return(fields.get("return_to", [""])[0])


def _external_https(headers):
    # Browsers send their external Origin on form POST; TLS proxies may set
    # X-Forwarded-Proto. These signals affect only the cookie Secure attribute.
    # For HTTP LAN access a Secure cookie cannot be used; prefer HTTPS HA.
    origin = headers.get("Origin", "")
    if isinstance(origin, str) and origin.startswith("https://"):
        return True
    return headers.get("X-Forwarded-Proto", "").split(",")[0].strip().lower() == "https"


def panel_authorized(headers, cfg):
    """Separate panel password; never trust client-supplied ingress headers as authentication."""
    if panel_session_authorized(headers, cfg):
        return True
    password = cfg.get("panel_password")
    header = headers.get("Authorization", "")
    if not isinstance(password, str) or len(password) < 16 or not header.startswith("Basic "):
        return False
    try:
        decoded = base64.b64decode(header[6:], validate=True).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False
    user, sep, candidate = decoded.partition(":")
    return bool(sep) and user == "admin" and hmac.compare_digest(
        candidate.encode("utf-8"), password.encode("utf-8"))



def _meta_credential(business_id=account_registry.PRIMARY_BUSINESS):
    """Read only this context's token directory; never fall back to primary."""
    try:
        cfg = meta_configuration_for_business(business_id)
        root = account_registry.credential_root(DATA_DIR, business_id).absolute()
        if any(parent.is_symlink() for parent in (root, *root.parents)):
            return None
        credential = oauth_meta.load_token(root)
        if credential is None:
            return None
        # Legacy unlabelled tokens belong only to Umdoislab.
        if credential.get("business_id", "umdoislab") != business_id:
            return None
        if credential.get("account_id") not in (None, cfg["instagram_account_id"]):
            return None
        return credential
    except (oauth_meta.OAuthError, account_registry.RegistryError):
        return None


def editorial_store_for_business(business_id=account_registry.PRIMARY_BUSINESS):
    """Account-scoped EditorialStore shared by UI and restricted incoming integration."""
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get("instagram_account_id"))
        account_registry.require_business(conn, business_id)
    return editorial_core.EditorialStore(
        account_registry.editorial_root(DATA_DIR, business_id))


def multi_connections():
    def registered(conn):
        account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
        rows = account_registry.administrative_accounts(conn)
        for row in rows:
            if row['business_id'] == account_registry.PRIMARY_BUSINESS:
                row['aliases'] = ['um2Lab', '1-2 Lab', '2Lab', 'um dois lab']
        return rows
    return editorial_connections.Connections(DB_PATH, account_reader=registered)


def multi_store(business_id):
    # Only called while the multi-grant transaction holds the registry lock.
    return editorial_core.EditorialStore(account_registry.editorial_root(DATA_DIR, business_id))


def meta_configuration_for_business(business_id=account_registry.PRIMARY_BUSINESS):
    """Return scoped settings; only owner-provisioned accounts share the Meta app."""
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get("instagram_account_id"))
        account = account_registry.require_business(conn, business_id)
        row = conn.execute('SELECT operational,display_name FROM instagram_accounts WHERE business_id=?', (business_id,)).fetchone()
    cfg = dict(settings())
    cfg["business_id"] = business_id
    cfg["instagram_account_id"] = account["instagram_account_id"]
    cfg["instagram_expected_username"] = account["username"]
    cfg['account_display_name'] = row[1]
    cfg['account_path'] = account_management.prefix(business_id)
    if business_id != account_registry.PRIMARY_BUSINESS and row[0] == 1:
        # Deliberate same-app onboarding by the installation owner, not inheritance
        # by legacy/internal records. Never share bridge or webhook activation.
        cfg = {key: cfg[key] for key in ('meta_app_id', 'meta_login_config_id', 'meta_app_secret',
               'meta_graph_version', 'meta_oauth_redirect_uri', 'public_base_url', 'meta_oauth_enabled',
               'panel_password', 'business_id', 'instagram_account_id', 'instagram_expected_username',
               'account_display_name', 'account_path') if key in cfg}
        cfg['bridge_secret'] = ''
        cfg['meta_verify_token'] = ''
        cfg['ingress_enabled'] = False
        cfg['drafts_enabled'] = False
        cfg['allow_account_discovery'] = account['instagram_account_id'] is None
    elif business_id != account_registry.PRIMARY_BUSINESS:
        # Never reuse Umdoislab's legacy bridge secret or active switches.
        # Secondary OAuth and webhooks require explicit per-tenant configuration.
        cfg = {key: cfg[key] for key in ("meta_app_id", "meta_login_config_id", "meta_graph_version",
               "business_id", "instagram_account_id", "instagram_expected_username") if key in cfg}
        cfg["bridge_secret"] = ""
        cfg["meta_oauth_enabled"] = False
        cfg["ingress_enabled"] = False
        cfg["drafts_enabled"] = False
    return cfg


def connection_summary(cfg, credential=None):
    """Local evidence only. A saved token is NOT proof of webhook delivery."""
    if credential is None:
        credential = _meta_credential(cfg.get("business_id", account_registry.PRIMARY_BUSINESS))
    state = instagram_connection.credential_status(credential, cfg)
    account_id = cfg.get("instagram_account_id", "")
    with database() as conn:
        if isinstance(account_id, str) and account_id:
            row = conn.execute(
                "SELECT COUNT(*), MAX(received_at) FROM inbound WHERE recipient_id=? AND source='webhook'",
                (account_id,)).fetchone()
        else:
            row = (0, None)
    diagnostics = instagram_connection.safe_diagnostics(credential.get('receiving_diagnostics')) if state['account_verified'] else None
    last_action = credential.get('last_meta_action') if isinstance(credential, dict) else None
    reauth = (isinstance(last_action, dict) and last_action.get('reason') == 'token_invalid') or (
        isinstance(diagnostics, dict) and any(
            isinstance(part, dict) and (part.get('reason') == 'token_invalid' or part.get('token_is_valid') is False)
            for part in diagnostics.values()))
    return {
        "oauthReady": oauth_meta.is_ready(cfg),
        "tokenStored": bool(credential),
        "accountVerified": state["account_verified"],
        "messagingPageReady": bool(
            isinstance(credential, dict) and isinstance(credential.get("page_id"), str) and
            credential.get("page_id") == credential.get("messaging_page_id") and
            isinstance(credential.get("page_access_token"), str) and
            20 <= len(credential["page_access_token"]) <= 8192),
        "subscriptionRequested": state["subscription_requested"],
        "webhookEnabled": cfg.get("ingress_enabled") is True,
        "webhookConfigReady": (isinstance(cfg.get("meta_verify_token"), str)
             and len(cfg["meta_verify_token"]) >= 24
             and isinstance(cfg.get("meta_app_secret"), str)
             and len(cfg["meta_app_secret"]) >= 16),
        "messagesStored": int(row[0]),
        "lastMessageReceived": row[1],
        "verifiedAt": credential.get("verified_at") if state["account_verified"] else None,
        "receivingDiagnostics": diagnostics,
        "lastMetaAction": last_action if state['account_verified'] else None,
        "reauthRequired": bool(reauth),
    }


def render_meta_diagnostics(summary):
    """Visible result from stored, account-bound evidence, never provider text."""
    action = summary.get('lastMetaAction')
    feedback = ''
    if isinstance(action, dict) and action.get('kind') in ('check', 'subscribe'):
        text = (('Não foi possível confirmar novamente a identidade na Meta. Confira o diagnóstico abaixo; a verificação anterior não foi renovada.'
                 if action.get('identity_verified') is False else
                 'Verificação de identidade concluída. Confira também o token de Página para envio abaixo.')
                if action['kind'] == 'check' else
                'A Meta aceitou o pedido de assinatura. O recebimento de uma mensagem real ainda precisa ser confirmado.')
        feedback = '<p role="status"><strong>' + text + '</strong></p>'
    report = instagram_connection.safe_diagnostics(summary.get('receivingDiagnostics'))
    if report is None:
        return feedback
    labels = {
        'message_access_disabled': 'A Meta informa que o acesso externo às mensagens está desativado.',
        'permission_denied': 'A Meta recusou a permissão desta consulta.',
        'token_invalid': 'A Meta recusou o token salvo.',
        'unsupported_request': 'A Meta não aceitou esta consulta com o token atual.',
        'configuration_incomplete': 'Configuração ou identidade verificada incompleta.',
        'invalid_response': 'A resposta da consulta não permitiu uma confirmação.',
        'transport_error': 'Não foi possível concluir a comunicação com a Meta.',
        'provider_error': 'A Meta recusou esta consulta.',
        'request_unavailable': 'A consulta não pôde ser concluída.',
        'app_subscription_not_exposed': 'A consulta genérica não retornou a configuração Instagram; isso não comprova ausência no portal.',
        'linked_page_not_found': 'A Meta não retornou uma Página vinculada a esta conta Instagram.',
        'page_list_incomplete': 'A lista de Páginas está incompleta; não é possível confirmar ausência ou unicidade.'}
    parts = []
    def answer(value, key):
        return 'Sim' if value.get(key) is True else 'Não' if value.get(key) is False else 'Não confirmado'
    for key, title in (('subscription', 'Assinatura consultada na Meta'),
                       ('conversations', 'Acesso às conversas'),
                       ('messaging_page', 'Acesso à Página para envio'),
                       ('token_metadata', 'Token salvo'),
                       ('app_subscription', 'Webhook do aplicativo')):
        value = report[key]
        if value['status'] == 'confirmed' and key == 'subscription':
            text = ('Aplicativo encontrado, campo messages presente.' if value.get('messages') is True else
                    'Aplicativo encontrado, campo messages ausente.' if value.get('messages') is False else
                    'Aplicativo encontrado; campo messages não confirmado.')
        elif value['status'] == 'confirmed' and key == 'messaging_page':
            stored = 'Sim' if summary.get('messagingPageReady') is True else 'Não'
            text = ('Página vinculada: ' + answer(value, 'page_found') +
                    '; tarefa MESSAGING: ' + answer(value, 'messaging_task_granted') +
                    '; token de Página retornado pela Meta: ' + answer(value, 'page_token_available') +
                    '; token armazenado na Central: ' + stored + '.')
        elif value['status'] == 'confirmed' and key == 'token_metadata':
            text = ('Válido: ' + answer(value, 'token_is_valid') + '; pertence ao app configurado: ' +
                    answer(value, 'app_matches') + '; instagram_basic: ' + answer(value, 'basic_granted') +
                    '; instagram_manage_messages: ' + answer(value, 'messages_granted') +
                    '; pages_read_engagement: ' + answer(value, 'page_read_engagement_granted') +
                    '; pages_messaging: ' + answer(value, 'pages_messaging_granted') + '.')
        elif value['status'] == 'confirmed' and key == 'app_subscription':
            text = ('Objeto Instagram encontrado. Ativo: ' + answer(value, 'active') +
                    '; messages: ' + answer(value, 'messages') + '; HTTPS: ' + answer(value, 'callback_https') +
                    '; caminho /webhook/instagram: ' + answer(value, 'callback_path_matches') + '.')
            if 'callback_origin' in value:
                text += ' Destino: ' + html.escape(value['callback_origin']) + '.'
            if value.get('callback_extra') is True:
                text += ' O callback contém parâmetros ou fragmento; seus valores não são exibidos.'
        elif value['status'] == 'confirmed':
            text = ('Acesso aceito; há conversa visível, sem consultar seu conteúdo.' if value.get('conversation_found') else
                    'Acesso aceito; a amostra retornou vazia.')
        elif value['status'] == 'absent':
            text = ('A Meta não retornou uma Página vinculada à conta do Instagram.'
                    if key == 'messaging_page' else
                    'O aplicativo não consta na assinatura desta conta.')
        elif (value['status'] == 'error' and key == 'messaging_page'
              and value.get('reason') == 'permission_denied'):
            text = ('A Meta recusou listar as Páginas. Para tokens de usuário do sistema, '
                    'confirme pages_read_engagement na configuração do Login.')
        else:
            text = labels.get(value.get('reason'), 'Não foi possível confirmar.')
        codes = ['%s=%s' % (label, value[key]) for key, label in
                 (('http_status', 'HTTP'), ('provider_code', 'código Meta'),
                  ('provider_subcode', 'subcódigo')) if key in value]
        parts.append('<li><strong>' + title + ':</strong> ' + text +
                     (' <small>(' + ', '.join(codes) + ')</small>' if codes else '') + '</li>')
    checked = datetime.fromtimestamp(report['checked_at'], timezone.utc).astimezone(
        ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y %H:%M:%S')
    return (feedback + '<div aria-label="Diagnóstico de recebimento"><h3>Diagnóstico de recebimento</h3>'
            '<p>Última consulta: ' + checked + ' (Brasília).</p><ul>' + ''.join(parts) + '</ul>'
            '<p>Estas consultas não enviam mensagens nem comprovam a entrega de eventos reais. '
            'As permissões do token não informam o nível Standard ou Advanced Access do app.</p></div>')


def render_connection_section(cfg, summary):
    """Show precise progress. Never print tokens, app secrets, verify tokens."""
    name = html.escape(str(cfg.get("instagram_account_id") or "não configurada"), quote=True)
    items = (
        ("OAuth preparado", summary["oauthReady"]),
        ("Conta verificada na Meta", summary["accountVerified"]),
        ("Webhook habilitado", summary["webhookEnabled"]),
        ("Assinatura solicitada", summary["subscriptionRequested"]),
    )
    def flags(values):
        return ''.join('<li>' + html.escape(label) + ': <strong>' + ('Sim' if value else 'Não') + '</strong></li>'
                       for label, value in values)
    last = summary["lastMessageReceived"] or "Nenhuma"
    url = cfg.get("meta_oauth_redirect_uri", "")
    actions = []
    if not summary.get('tokenStored'):
        actions.append('<p><strong>Próximo passo: autorizar esta conta na Meta.</strong> Cadastrar nome e @ cria o cadastro local; '
                       'a autorização só acontece em Conectar Instagram pela Meta.</p>')
    elif summary.get('reauthRequired'):
        actions.append('<p role="alert">A credencial salva foi recusada pela Meta. Reconecte esta conta para renovar a autorização.</p>')
    elif not summary['accountVerified']:
        actions.append('<p>Há uma credencial salva. Use Verificar acesso Meta para confirmar a identidade desta conta.</p>')
    try:
        origin = origin_configuration.public_origin(cfg)
        origin_matches = origin_configuration.oauth_origin_matches(cfg)
    except ValueError:
        origin, origin_matches = "", False
    if origin:
        actions.append('<a href="' + html.escape(origin + cfg.get("account_path", "") + "/panel?view=settings", quote=True)
                       + '" target="_blank" rel="noopener noreferrer">Abrir Central em janela própria</a>')
    if not origin_matches:
        actions.append('<p>Configure o retorno OAuth na mesma URL pública HTTPS da Central antes de conectar.</p>')
    if summary['oauthReady'] and origin_matches:
        # A browser session established via the same HTTPS hostname is required
        # for the public proxy route to recognize the session cookie.
        start_url = url[:-len("/oauth/meta/callback")] + cfg.get("account_path", "") + "/oauth/meta/start"
        actions.append('<a href="' + html.escape(start_url + "?probe=1", quote=True)
                       + '" target="_blank" rel="noopener noreferrer">Testar navegador e proxy (sem Meta)</a>')
        authorize = ('<p><a class="btn primary" href="' + html.escape(start_url, quote=True)
                       + '" target="_blank" rel="noopener noreferrer">' +
                       ('Reconectar Instagram pela Meta' if summary.get('reauthRequired') else 'Conectar Instagram pela Meta') + '</a></p>')
        if not summary['accountVerified'] or summary.get('reauthRequired'):
            actions.insert(1, authorize)
        else:
            actions.append('<details><summary>Atualizar permissões da conta</summary><p>Para excluir publicações no Instagram, inclua instagram_manage_contents no app Meta e na configuração do Login do Facebook para Empresas. Depois renove a autorização desta conta.</p>' +
                authorize.replace('Conectar Instagram pela Meta', 'Renovar autorização da conta') + '</details>')
    setup = (
        ("App Meta", bool(str(cfg.get("meta_app_id") or "").isdigit())),
        ("Login unificado", bool(str(cfg.get("meta_login_config_id") or "").isdigit())),
        ("Conta Instagram", bool(str(cfg.get("instagram_account_id") or "").isdigit())),
        ("Retorno HTTPS", oauth_meta.is_ready(cfg)),
        ("Segredo Meta", isinstance(cfg.get("meta_app_secret"), str)
          and len(cfg.get("meta_app_secret", "")) >= 16),
    )
    checklist = "".join("<li>" + label + ": " + ("configurado" if ready else "pendente")
                        + "</li>" for label, ready in setup)
    webhook_setup = '<li>Token de verificação: ' + ('configurado' if
        isinstance(cfg.get('meta_verify_token'), str) and len(cfg['meta_verify_token']) >= 24 else 'pendente') + '</li>'
    return ("""<section class="panel connection-panel" aria-label="Conexão com Instagram">
       <h2>Conexão com o Instagram</h2><p>Conta: <strong>@""" + html.escape(str(cfg.get("instagram_expected_username") or "umdoislab")) + """</strong>
       · ID: <code>""" + name + """</code></p>
       <h3>Autorização da conta</h3><ul>""" + flags(items[:2]) + """</ul>""" + ' '.join(actions) + """
       <details><summary>Configuração necessária</summary><ul>""" + checklist + """</ul>
       <p>Em contas novas, a Meta preenche o ID do Instagram depois da autorização.</p>
       <p>As credenciais são configuradas nas opções do aplicativo no Home Assistant.
       Não compartilhe segredos por mensagem.</p></details>
       </section>""")


def render_receiving_settings(cfg, summary):
    flags = ''.join('<li>' + label + ': <strong>' + ('Sim' if value else 'Não') + '</strong></li>'
                    for label, value in (("Webhook habilitado", summary['webhookEnabled']),
                                         ("Assinatura solicitada", summary['subscriptionRequested'])))
    webhook_setup = '<li>Token de verificação: ' + ('configurado' if summary['webhookConfigReady'] else 'pendente') + '</li>'
    last = summary['lastMessageReceived'] or 'Nenhuma'
    return ("""<section class="panel" aria-label="Diagnóstico de mensagens"><h2>Recebimento de mensagens</h2><ul>""" + flags + """</ul>
       <p>Autorizar a conta e receber eventos são etapas distintas. A configuração do webhook não é pré-requisito para iniciar a autorização da conta.</p>
       <details><summary>Configuração do webhook</summary><ul>""" + webhook_setup + """</ul></details>
       <p><strong>Mensagens recebidas por webhook: """ + str(summary["messagesStored"]) +
       """</strong> · Última entrada por webhook: """ + html.escape(str(last)) + """</p>
       <p><small>Uma assinatura aceita pela Meta não comprova que mensagens já chegam.
       O primeiro recebimento assinado é a confirmação.</small></p>""" +
        render_meta_diagnostics(summary) +
       """<div id="meta-actions"></div></section>""")


def _meta_action_body(raw):
    if not isinstance(raw, bytes) or len(raw) > 512:
        return None
    try:
        values = parse_qs(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=1)
    except (ValueError, UnicodeDecodeError):
        return None
    if set(values) != {"csrf"} or len(values["csrf"]) != 1:
        return None
    return values["csrf"][0]


def panel_navigation_query(query):
    """Ignore known attribution fields on UI navigation only; retain functional fields."""
    tracking = {'utm_source', 'utm_medium', 'utm_campaign', 'utm_term',
                'utm_content', 'utm_id', 'utm_source_platform'}
    return '&'.join(field for field in query.split('&')
                    if field.partition('=')[0] not in tracking)


def settings_result(query):
    if query == 'view=settings':
        return ''
    try:
        fields = parse_qs(query, keep_blank_values=True, max_num_fields=3)
    except ValueError:
        return None
    if fields.get('view') != ['settings'] or set(fields) - {'view', 'meta_result', 'automation_result'}:
        return None
    if ('automation_result' in fields and
            (len(fields['automation_result']) != 1 or
             fields['automation_result'][0] not in ('saved', 'invalid'))):
        return None
    if ('meta_result' in fields and
            (len(fields['meta_result']) != 1 or fields['meta_result'][0] not in META_RESULTS)):
        return None
    return fields.get('meta_result', [''])[0]


def navigation_configuration(cfg):
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
        accounts = account_registry.administrative_accounts(conn)
    return {**cfg, 'navigation_accounts': accounts}


def render_publication_settings(cfg):
    result = PUBLICATIONS.public_state(cfg.get('business_id', 'umdoislab'))
    message = result.get('message', '')
    if message == 'Verifique o acesso de publicação desta conta.':
        message = 'Sem consulta manual recente. O acesso será conferido automaticamente ao publicar.'
    endpoint = html.escape(account_management.prefix(cfg.get('business_id', 'umdoislab')) + '/editorial/', quote=True)
    return ('<section class="panel publication-settings" aria-label="Diagnóstico de publicação">'
            '<h2>Publicação no Instagram</h2><p>O acesso é conferido automaticamente quando necessário para enviar uma publicação. '
            'Use esta consulta manual após alterar a conexão ou para investigar um erro.</p>'
            '<p id="publication-status" role="status" aria-live="polite">' + html.escape(message) + '</p>'
            '<p id="publication-checked-at" data-checked-at="' + str(result.get('checkedAt') or '') + '"></p>'
            '<button type="button" class="btn quiet" id="check-publication" data-publication-base="' + endpoint + '">Verificar publicação</button>'
            '<p id="publication-check-feedback" role="status" aria-live="polite"></p></section>')


def render_integration_settings(cfg):
    endpoint = html.escape(account_management.prefix(cfg.get('business_id', 'umdoislab')) + '/editorial/', quote=True)
    choices = ''.join('<label><input type="checkbox" name="multi-account" value="' + html.escape(a['business_id'], quote=True) + '"> ' + html.escape(a['display_name']) + '</label>' for a in cfg.get('navigation_accounts', []) if a.get('instagram_account_id'))
    return ('''<section class="panel integration-settings" aria-label="Ferramentas de criação" data-integration-base="''' + endpoint + '''">
      <h2>Conectar ferramentas de criação</h2>
      <p>Conecte uma ferramenta de criação. Para o Claude, escolha uma conexão multi-conta, sem publicação direta.</p>
      <label for="integration-label">Nome da ferramenta</label>
      <input id="integration-label" maxlength="80" placeholder="Minha ferramenta de vídeo" autocomplete="off">
      <label for="integration-scope">Contas autorizadas</label>
      <select id="integration-scope"><option value="legacy">Somente esta conta (compatibilidade)</option>
      <option value="owner_all">Todas as contas atuais e futuras (proprietário)</option>
      <option value="selected">Somente contas selecionadas (acesso delegado)</option></select>
      <div id="integration-grants" hidden>''' + choices + '''</div>
      <div id="integration-drive-fields" hidden><label for="integration-drive">ID da pasta privada exclusiva no Drive (opcional)</label>
      <input id="integration-drive" maxlength="200" autocomplete="off">
      <p>A ferramenta deve colocar os arquivos em uma subpasta com o ID da conta. Compartilhe a pasta apenas com a identidade técnica de leitura.</p></div>
      <label id="integration-publish-row"><input id="integration-publish" type="checkbox"> Permitir publicação direta quando eu autorizar</label>
      <div class="integration-actions"><button id="integration-create" class="btn primary" type="button">Criar conexão</button>
      <button id="integration-list" class="btn quiet" type="button">Ver conexões</button></div>
      <div id="integration-secret" hidden><p>A chave aparece somente agora e vence em 90 dias. Guarde-a apenas na configuração privada da ferramenta.</p>
        <label for="integration-token">Chave da conexão</label><input id="integration-token" type="password" readonly autocomplete="off" spellcheck="false">
        <div class="integration-actions"><button id="integration-copy" class="btn quiet" type="button">Copiar chave</button>
        <button id="integration-hide" class="btn quiet" type="button">Fechar e ocultar chave</button></div></div>
      <p id="integration-feedback" role="status" aria-live="polite"></p>
      <div id="integration-connections" aria-live="polite"></div></section>''')


def render_routing_settings(cfg):
    endpoint = html.escape(account_management.prefix(cfg.get('business_id', 'umdoislab')) + '/panel/meta/check', quote=True)
    return ('<section class="panel" aria-label="Controle e atividade das conversas">'
            '<h2>Controle e atividade das conversas</h2>'
            '<p>Consulta até cinco conversas usando somente metadados: controle pelo nosso aplicativo e horário da última atividade. '
            'Não lê textos ou participantes, não envia mensagens e não altera o encaminhamento.</p>'
            '<button type="button" class="btn quiet" id="check-routing" data-routing-url="' + endpoint + '" data-routing-csrf="">Consultar controle e atividade</button>'
            '<div id="routing-result" role="status" aria-live="polite"></div>'
            '<p id="routing-feedback" role="status" aria-live="polite">Nenhuma consulta realizada nesta página.</p></section>')


def inbox_received_label(value):
    """Display local time without changing the stored timestamp."""
    try:
        date = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if date.utcoffset() is None:
            raise ValueError()
        return date.isoformat(), date.astimezone(ZoneInfo('America/Sao_Paulo')).strftime('%d/%m/%Y às %H:%M')
    except (ValueError, TypeError, AttributeError, OverflowError):
        return '', 'Horário não informado'


def render_automation_settings(cfg, result='', messaging_ready=False, receiving_diagnostics=None):
    account_id = str(cfg.get('instagram_account_id') or '')
    primary = cfg.get('business_id', account_registry.PRIMARY_BUSINESS) == account_registry.PRIMARY_BUSINESS
    with database() as conn:
        policy = automation_policy.snapshot(conn, account_id) if account_id else {
            'mode': 'tests', 'test': [], 'excluded': [], 'updatedAt': None}
    status = ''
    if result == 'saved':
        status = '<p class="automation-feedback" role="status">Configurações salvas. O filtro já vale para as próximas mensagens.</p>'
    elif result == 'invalid':
        status = '<p class="automation-feedback" role="alert">Não foi possível salvar. Confira os IDs numéricos e tente novamente. Nenhuma configuração anterior foi alterada.</p>'
    disabled = ' disabled' if not primary or not account_id else ''
    mode = policy['mode']
    bridge_ready = isinstance(cfg.get('bridge_secret'), str) and len(cfg['bridge_secret']) >= 32
    page_diagnostic = (receiving_diagnostics.get('messaging_page')
                       if isinstance(receiving_diagnostics, dict) else None)
    if not isinstance(page_diagnostic, dict):
        page_diagnostic = {}
    if messaging_ready:
        messaging_status = '<p role="status">Página vinculada e token de mensagens armazenado. As permissões Meta são revalidadas antes de cada envio.</p>'
    elif page_diagnostic.get('status') == 'error' and page_diagnostic.get('reason') == 'permission_denied':
        messaging_status = '<p role="alert">A Meta recusou listar as Páginas. Confira se <code>pages_read_engagement</code> foi concedida na configuração do Login.</p>'
    elif page_diagnostic.get('status') == 'confirmed' and page_diagnostic.get('messaging_task_granted') is False:
        messaging_status = '<p role="alert">A Página está vinculada, mas falta a tarefa <code>MESSAGING</code> no acesso à Página.</p>'
    elif page_diagnostic.get('status') == 'confirmed' and page_diagnostic.get('page_token_available') is False:
        messaging_status = '<p role="alert">A Meta encontrou a Página, mas não retornou o token de Página. Confira <code>pages_read_engagement</code> e a autorização.</p>'
    elif page_diagnostic.get('status') == 'confirmed' and page_diagnostic.get('page_token_available') is True:
        messaging_status = '<p role="alert">A Meta retornou um token de Página, mas ele ainda não está armazenado na Central. Execute Verificar acesso Meta.</p>'
    elif page_diagnostic.get('status') == 'absent':
        messaging_status = '<p role="alert">A Meta não retornou uma Página vinculada à conta Instagram.</p>'
    elif page_diagnostic.get('status') == 'unknown' and page_diagnostic.get('reason') == 'page_list_incomplete':
        messaging_status = '<p role="alert">A lista de Páginas está incompleta; não foi possível confirmar o vínculo e o token.</p>'
    else:
        messaging_status = '<p role="alert">Envio Meta pendente: falta um token de Página vinculado com tarefa MESSAGING. O filtro funciona, mas o envio permanece bloqueado.</p>'
    return ('''<section class="panel automation-policy" aria-label="Controle de atendimento automático">
      <div class="panel-title"><div><h2>Atendimento automático</h2>
      <p>Controle quais perfis podem chegar ao n8n e receber respostas automáticas.</p></div>
      <span class="automation-mode">''' + ('Somente testes' if mode == 'tests' else 'Produção') + '''</span></div>
      ''' + messaging_status +
      ('<p role="status">Segredo da ponte n8n configurado (valor oculto).</p>' if bridge_ready else
       '<p role="alert">Ponte n8n não configurada: falta um segredo próprio com pelo menos 32 caracteres nas opções da Central. Não reutilize o segredo do WhatsApp.</p>') + status + ('''<p role="status">Este controle está disponível somente para a conta principal Umdoislab. As demais contas permanecem isoladas.</p>''' if not primary else '') + '''
      <form method="post" action="panel/automation/policy" class="automation-policy-form">
        <input type="hidden" name="csrf" value="" data-automation-csrf>
        <fieldset''' + disabled + '''><legend>Modo de operação</legend>
          <label><input type="radio" name="mode" value="tests"''' + (' checked' if mode == 'tests' else '') + '''> Testes — somente perfis autorizados</label>
          <label><input type="radio" name="mode" value="all"''' + (' checked' if mode == 'all' else '') + '''> Produção — todos, exceto perfis excluídos</label>
        </fieldset>
        <div class="automation-lists">
          <label for="automation-test-ids"><strong>Perfis autorizados para teste</strong>
            <small>Um ID técnico do Instagram por linha. Copie o ID no detalhe da conversa na Caixa de entrada.</small></label>
          <textarea id="automation-test-ids" name="test_ids" rows="4" maxlength="10000"''' + disabled + '''>''' + html.escape('\n'.join(policy['test'])) + '''</textarea>
          <label for="automation-excluded-ids"><strong>Perfis sempre excluídos</strong>
            <small>Esses perfis nunca recebem resposta automática, inclusive em produção.</small></label>
          <textarea id="automation-excluded-ids" name="excluded_ids" rows="4" maxlength="10000"''' + disabled + '''>''' + html.escape('\n'.join(policy['excluded'])) + '''</textarea>
        </div>
        <p class="automation-safety">A exclusão sempre prevalece. IDs são identificadores estáveis; @nomes de usuário podem mudar. No modo de testes, nenhum perfil fora da lista autorizada é encaminhado ao n8n.</p>
        <button class="btn primary" type="submit"''' + disabled + '''>Salvar controle de atendimento</button>
      </form>
    </section>''')

def render_panel(cfg=None, *, settings_page=False, meta_result='', automation_result=''):
    """Account-scoped messages or settings, rendered as separate documents."""
    cfg = navigation_configuration(cfg or {})
    rows, message_count, audits, failures = [], 0, {}, {}
    if not settings_page:
        with database() as conn:
            account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
            account_id = account_registry.require_business(conn, cfg.get('business_id', account_registry.PRIMARY_BUSINESS))['instagram_account_id']
            message_count = conn.execute('SELECT COUNT(*) FROM inbound WHERE recipient_id=?', (account_id,)).fetchone()[0]
            rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_text,
              i.received_at, i.processed_at, COALESCE(h.state, 'bot'),
              COALESCE(d.draft_text, ''), COALESCE(d.status, ''), i.source, i.resume_skipped_at
              FROM inbound i LEFT JOIN handoff h
                ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
              LEFT JOIN drafts d ON i.recipient_id=d.recipient_id
                AND i.sender_id=d.sender_id AND i.message_id=d.message_id
              WHERE i.recipient_id=?
              ORDER BY i.received_at DESC, i.rowid DESC""", (account_id,)).fetchall()
            for sender, changed, actor, reason in conn.execute("""SELECT sender_id, changed_at, actor, reason FROM handoff_audit WHERE recipient_id=? ORDER BY id DESC""", (account_id,)):
                audits.setdefault(sender, []).append((changed, actor, reason))
            for sender, reason, stamp in conn.execute("""SELECT sender_id,error_reason,updated_at FROM automation_sends
              WHERE recipient_id=? AND status='failed' ORDER BY updated_at DESC""", (account_id,)):
                failures.setdefault(sender, (reason, stamp))
    groups = {}
    for row in rows:
        groups.setdefault(row[1], []).append(row)
    entries = []
    cfg = cfg or {}
    for messages in sorted(groups.values(), key=lambda group: group[0][5] not in ('pending','human') and group[0][1] not in failures):
        account, sender, message, received, processed, state, draft, draft_status, source, resume_skipped = messages[0]
        queue = 'Fora da fila automática' if source == 'manual' else 'Encerrada na retomada — sem resposta automática' if resume_skipped else 'Processada' if processed else 'Pendente'
        origin = 'Consulta manual à Meta' if source == 'manual' else 'Webhook'
        control = {'bot':'Automação', 'human':'Atendimento humano', 'pending':'Aguardando', 'done':'Concluída'}.get(state,'Não informado')
        iso, date = inbox_received_label(received)
        date_attr = ' datetime="' + html.escape(iso, quote=True) + '"' if iso else ''
        actions = []
        pwd = cfg.get("panel_password", "")
        if isinstance(pwd, str) and len(pwd) >= 16:
            for target, label in (("human", "Assumir"), ("pending", "Aguardar"), ("done", "Concluir"), ("bot", "Voltar ao bot")):
                if target == state:
                    continue
                values = (("accountId", account), ("senderId", sender),
                          ("state", target), ("csrf", token_for(account, sender, target, pwd)))
                inputs = "".join('<input type="hidden" name="' + key + '" value="' +
                                 html.escape(value, quote=True) + '">' for key, value in values)
                primary = target == ('bot' if state == 'pending' else 'done' if state == 'human' else 'human')
                actions.append('<form method="post" action="panel/handoff">' + inputs +
                               '<button class="btn ' + ('primary' if primary else 'quiet') + '" type="submit">' + label + '</button></form>')
        history = []
        for _, _, msg, stamp, done, _, saved_draft, saved_status, msg_source, skipped in messages:
            _, label = inbox_received_label(stamp)
            queue_label = 'Fora da fila automática' if msg_source == 'manual' else 'Encerrada na retomada — sem resposta automática' if skipped else 'Processada' if done else 'Pendente'
            history.append('<li><time>' + html.escape(label) + '</time><p class="inbox-message-text">' + html.escape(msg) +
                           '</p><small>' + queue_label + '</small>' +
                           ('<p>Rascunho (sem envio): ' + html.escape(saved_draft) + '</p>' if saved_draft else '') + '</li>')
        audit = audits.get(sender, [])
        origin_labels = {'panel':'Operador', 'bridge':'Automação', 'system':'Servidor'}
        reason_labels = {'manual_action':'Ação manual', 'human_review':'Revisão humana necessária',
                         'unsafe_content':'Conteúdo não autorizado', 'model_requested_handoff':'Revisão solicitada pelo modelo',
                         'meta_send_failed':'Falha de envio à Meta'}
        def audit_label(item):
            changed, actor, reason = item
            return html.escape(reason_labels.get(reason, 'Motivo não registrado') + ' · ' +
                               origin_labels.get(actor, 'Origem não registrada') + ' · ' + inbox_received_label(changed)[1])
        status = ('Bot bloqueado — ' if state != 'bot' else '') + control
        detail = ('<p role="status"><strong>' + html.escape(status) + '</strong><br>' +
                  (audit_label(audit[0]) if audit else 'Motivo não registrado') + '</p>') if state != 'bot' else '<p><strong>Automação selecionada</strong></p>'
        if sender in failures:
            failure, stamp = failures[sender]
            failure_label = {'configuration_incomplete':'Configuração de envio Meta incompleta',
                             'permission_denied':'Permissão de envio recusada',
                             'token_invalid':'Token Meta inválido',
                             'transport_error':'Falha de comunicação com a Meta'}.get(failure, 'Falha de envio à Meta')
            detail += '<p role="status"><strong>Falha de envio registrada</strong> — ' + html.escape(failure_label + ' · ' + inbox_received_label(stamp)[1]) + '</p>'
        entries.append('<li><article class="inbox-message"><header class="inbox-message-head">' +
            sender_profiles.identity_html(account_management.prefix(cfg.get('business_id', 'umdoislab')), sender) +
            '<time' + date_attr + ' title="Horário de Brasília">' + html.escape(date) + '</time></header>' +
            detail + '<p>' + str(len(messages)) + ' mensagens · ' + str(sum(not m[4] and m[8] == 'webhook' for m in messages)) + ' não processadas</p>' +
            '<p class="inbox-message-text">' + html.escape(message) + '</p>' +
            '<div class="inbox-message-actions" role="group" aria-label="Ações da conversa">' + ''.join(actions) + '</div>' +
            '<details class="inbox-message-details"><summary>Histórico de mensagens</summary><ul>' + ''.join(history) + '</ul></details>' +
            '<details class="inbox-message-details"><summary>Histórico de controle</summary><ul>' +
            ''.join('<li>' + audit_label(item) + '</li>' for item in audit) + '</ul></details></article></li>')
    overview = '<section class="inbox-message" aria-label="Controle de atendimento"><h2>Controle de atendimento</h2><div class="inbox-message-status">' + ''.join(
        '<span>' + label + ': <strong>' + str(sum(group[0][5] == state for group in groups.values())) + '</strong></span>' for state, label in
        (('pending','Aguardando ação'),('human','Atendimento humano'),('bot','Automação selecionada'),('done','Concluídas'))) + '</div></section>'
    overview += '<p role="status">Conversas com falhas de envio registradas: ' + str(len(failures)) + '</p>'
    body = overview + (('<ul class="inbox-message-list" aria-label="Conversas desta conta">' + ''.join(entries) + '</ul>') if entries else '<p class="inbox-empty">Nenhuma mensagem recebida.</p>')
    page_name = 'Configurações Meta' if settings_page else 'Mensagens'
    count_label = ('Nenhuma mensagem' if message_count == 0 else
                   '1 mensagem' if message_count == 1 else str(message_count) + ' mensagens')
    content = ('''<section class="inbox-page-section" aria-label="Caixa de entrada">
      <div class="inbox-page-header" id="messages">
        <div class="inbox-page-title"><h1>Caixa de entrada</h1>
          <span class="inbox-count">''' + count_label + '''</span></div>
        <button type="button" class="btn quiet" id="refresh-inbox" data-inbox-url="''' +
      html.escape(account_management.prefix(cfg.get('business_id', 'umdoislab')) + '/panel/meta/check', quote=True) +
      '''" data-inbox-csrf="">Atualizar mensagens</button>
      </div>
      <details class="inbox-source-note"><summary>Como funciona a busca</summary>
        <p>A busca é manual: consulta até 5 conversas recentes e 10 mensagens de cada na Meta. Somente textos recebidos; não há consulta periódica nem envio automático. Os horários dos cartões são de Brasília.</p>
      </details>
      <p id="inbox-feedback" role="status" aria-live="polite"></p>
      <div id="inbox-messages">''' + body + '''</div>
      </section>''')
    if settings_page:
        summary = connection_summary(cfg)
        if meta_result == 'token_invalid':
            summary['reauthRequired'] = True
        feedback = ('<p id="meta-feedback" role="' + ('status' if meta_result.endswith('_completed') else 'alert') + '">' +
                    META_RESULTS[meta_result] + '</p>') if meta_result in META_RESULTS else ''
        content = ('<div class="heading"><span class="eyebrow">CONFIGURAÇÃO DA CONTA</span>'
                   '<h1>Configurações Meta</h1><p>Conexão e diagnósticos desta conta do Instagram.</p></div>' + feedback +
                   interface_ui.settings_tabs(render_connection_section(cfg, summary),
                       render_receiving_settings(cfg, summary) + render_routing_settings(cfg) + render_publication_settings(cfg),
                       render_integration_settings(cfg), automation=render_automation_settings(
                           cfg, automation_result, summary.get('messagingPageReady') is True,
                           summary.get('receivingDiagnostics')),
                       default='automation' if automation_result else 'diagnostics' if meta_result and not summary.get('reauthRequired')
                           and summary.get('tokenStored') else 'connection'))
    return ("""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#111c29">
<meta name="robots" content="noindex,nofollow">
<title>""" + page_name + """ · Central Instagram</title>
<style>
:root{color-scheme:dark;--bg:#0c1520;--sidebar:#0e1722;--surface:#152231;--surface2:#1b2b3a;--edge:#2b4051;--text:#f3f5f7;--muted:#a3b5c5;--orange:#ff8e40;--green:#57cba2;font-family:Inter,ui-sans-serif,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--text);font-size:14px}
button,a,input,summary{font:inherit}
button,a{cursor:pointer}
button:focus-visible,a:focus-visible,summary:focus-visible{outline:2px solid var(--orange);outline-offset:3px}
.skip{position:absolute;top:-100px;background:#fff;color:#111;padding:12px;z-index:10}.skip:focus{top:0}
.shell{min-height:100vh;display:grid;grid-template-columns:244px minmax(0,1fr)}
.sidebar{background:var(--sidebar);border-right:1px solid var(--edge);display:flex;flex-direction:column;padding:30px 16px 18px;position:sticky;top:0;height:100vh}
.brand{display:flex;align-items:center;gap:11px;padding:0 10px 34px}
.brand-icon{font-size:26px;font-weight:900;letter-spacing:-3px;color:#fff}
.dot{color:var(--orange)}
.brand strong{display:block;font-weight:800;letter-spacing:2px;font-size:12px}
.brand small{display:block;font-size:11px;color:var(--muted);margin-top:4px}
.section-label{font-size:10px;font-weight:700;letter-spacing:2px;color:#7b94a8;padding:5px 14px 13px}
.nav{display:grid;gap:6px}
.nav-link{width:100%;display:flex;align-items:center;gap:13px;text-decoration:none;background:transparent;color:#becbd7;border:1px solid transparent;border-radius:10px;padding:14px 15px;font-weight:650}
.nav-link span{display:inline-grid;place-items:center;width:18px;font-size:19px}
.nav-link.active{background:#263546;color:#fff;border-color:#354b60;box-shadow:inset 3px 0 var(--orange)}
.sidebar-foot{margin-top:auto;background:#192a38;border:1px solid var(--edge);border-radius:11px;padding:15px 12px;display:flex;align-items:center;gap:11px}
.sidebar-foot strong,.sidebar-foot small{display:block}
.sidebar-foot small{font-size:11px;color:var(--muted);margin-top:4px}
.status-led{width:9px;height:9px;border-radius:50%;background:var(--green);box-shadow:0 0 0 4px #57cba219}
.main{min-width:0}
.topbar{min-height:82px;border-bottom:1px solid var(--edge);display:flex;justify-content:space-between;align-items:center;padding:16px 40px;gap:16px}
.crumb{color:var(--muted)}
.crumb span{color:#647d90;padding:0 10px}
.crumb strong{color:#fff}
.top-actions{display:flex;align-items:center;gap:12px;flex-wrap:wrap;justify-content:flex-end}
.account{color:#d5e0ec;font-weight:650}
.logout-form{display:inline-flex;margin:0}
.btn,.item-actions button{border:1px solid var(--edge);color:var(--text);background:var(--surface2);border-radius:10px;padding:11px 17px;font-weight:700}
.btn.quiet{background:transparent}
.item-actions button{padding:8px 11px;font-size:12px}
.btn:hover,.item-actions button:hover{filter:brightness(1.1)}
.content{padding:38px 40px 60px;max-width:1450px;margin:auto}
.heading{margin-bottom:26px}
.eyebrow{display:block;color:var(--orange);font-weight:800;font-size:11px;letter-spacing:2px;margin-bottom:12px}
.heading h1{font-size:clamp(25px,3vw,36px);margin:0 0 10px;letter-spacing:-1.2px}
.heading p,.panel p{color:var(--muted);line-height:1.5}
.panel{background:var(--surface);border:1px solid var(--edge);border-radius:14px;padding:25px;margin-bottom:22px;min-width:0}
.panel h2{font-size:18px;margin:0 0 13px}
.integration-settings label{display:block;margin:14px 0 7px;line-height:1.6}
.integration-settings input:not([type=checkbox]){display:block;width:100%;max-width:440px;padding:12px;border:1px solid var(--edge);border-radius:8px;color:var(--text);background:var(--surface2)}
.integration-settings .primary{background:var(--orange);color:#161b23;border-color:var(--orange)}
.integration-actions,.integration-row{display:flex;flex-wrap:wrap;align-items:center;gap:10px;margin-top:14px}
.integration-row{justify-content:space-between;border-top:1px solid var(--edge);padding-top:14px}
.integration-row span{overflow-wrap:anywhere;min-width:0;flex:1}
.connection-panel ul{line-height:1.9;display:grid;gap:3px;padding-left:22px}
.connection-panel li{overflow-wrap:anywhere}
.connection-panel strong{color:#eaf1f8}
.connection-panel details{background:var(--surface2);border:1px solid var(--edge);border-radius:10px;padding:12px 15px;margin:15px 0}
.connection-panel summary{cursor:pointer;font-weight:700}
.connection-panel a{color:var(--orange)}
.connection-panel a.btn.primary{display:inline-block;min-height:44px;background:var(--orange);border-color:var(--orange);color:#161b23;text-decoration:none}
.connection-panel code{color:#d0e4ff;overflow-wrap:anywhere}
.connection-panel small{color:var(--muted)}
#meta-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
#meta-actions form{margin:0}
#meta-actions button{min-height:44px;border:1px solid var(--orange);background:var(--orange);color:#161b23;border-radius:10px;padding:10px 15px;font-weight:700}
#meta-actions button:hover{filter:brightness(1.09)}
#meta-actions button:disabled{opacity:.65;cursor:progress}
#meta-action-progress{width:100%;margin:0;color:var(--text)}
.panel-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
#refresh-inbox{min-height:44px}
.note{border:1px solid #465538;background:#222c23;border-radius:12px;padding:15px 18px;color:#c5d5bf;line-height:1.6}
.automation-policy .automation-mode{display:inline-flex;align-items:center;border:1px solid var(--orange);border-radius:999px;padding:6px 11px;color:var(--orange);font-size:12px;font-weight:800;white-space:nowrap}
.automation-policy-form fieldset{display:grid;gap:12px;border:1px solid var(--edge);border-radius:10px;padding:15px;margin:18px 0}
.automation-policy-form legend{padding:0 6px;font-weight:750;color:var(--text)}
.automation-policy-form fieldset label{display:flex;align-items:center;gap:9px;color:var(--text)}
.automation-policy-form input[type=radio]{accent-color:var(--orange);width:18px;height:18px}
.automation-lists{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
.automation-lists label{display:block;min-width:0}
.automation-lists strong,.automation-lists small{display:block}
.automation-lists small{color:var(--muted);line-height:1.45;margin:6px 0 10px}
.automation-lists textarea{display:block;width:100%;min-height:116px;resize:vertical;border:1px solid var(--edge);border-radius:9px;background:var(--surface2);color:var(--text);padding:12px;font:inherit;line-height:1.5}
.automation-policy .automation-safety{border-left:3px solid var(--orange);padding:10px 13px;background:var(--surface2);border-radius:0 8px 8px 0}
.automation-policy .btn.primary{background:var(--orange);border-color:var(--orange);color:#161b23}
.automation-feedback{border:1px solid var(--edge);border-radius:8px;padding:10px 12px}
@media(max-width:760px){
.automation-lists{grid-template-columns:minmax(0,1fr)}
.automation-policy .panel-title{align-items:flex-start;flex-wrap:wrap}
.shell{grid-template-columns:minmax(0,1fr);grid-template-rows:auto 1fr}
.sidebar{position:static;height:auto;border-right:0;border-bottom:1px solid var(--edge);padding:13px}
.brand{padding-bottom:12px}.section-label,.sidebar-foot{display:none}
.nav{display:flex;overflow-x:auto;gap:5px;padding-bottom:4px}
.nav-link{white-space:nowrap;width:auto;padding:10px 12px;flex-shrink:0}
.nav-link span{display:none}
.topbar{padding:12px 17px;flex-wrap:wrap;min-height:70px}
.top-actions{width:100%}
.content{padding:27px 16px}
.panel{padding:17px}
}
</style></head><body>
<a class="skip" href="#principal">Pular para conteúdo</a>
<div class="shell">
""" + interface_ui.sidebar(cfg, active='settings' if settings_page else 'messages') + """
<main id="principal" class="main">
""" + interface_ui.header(cfg, page_name) + '\n<div class="content' + ('' if settings_page else ' ui-inbox-page') + '">' + content + """
  </div>
 </main>
</div></body></html>""")


def render_probe_failure(diagnostic, host_ok, https_ok):
    if not host_ok or not https_ok:
        explanation = "O host ou o encaminhamento HTTPS recebido não corresponde ao esperado."
    elif not diagnostic["query_state_valid"]:
        explanation = "O retorno deste teste está inválido. Abra um novo teste sem Meta pelo painel."
    elif diagnostic["expected_cookie_count"] > 1:
        explanation = "Mais de um cookie desta tentativa chegou à Central."
    elif not diagnostic["cookie_header_present"]:
        explanation = "Nenhum cabeçalho Cookie chegou à Central neste retorno."
    elif not diagnostic["expected_cookie_present"]:
        explanation = "Cookies chegaram à Central, mas o cookie desta tentativa não foi encontrado."
    else:
        explanation = "O cookie desta tentativa chegou, mas a verificação não foi aprovada."
    facts = (("Cabeçalho Cookie recebido", diagnostic["cookie_header_present"]),
             ("Cookie desta tentativa recebido", diagnostic["expected_cookie_present"]),
             ("Algum cookie de estado OAuth recebido", diagnostic["state_cookie_present"]),
             ("Vários cabeçalhos Cookie recebidos", diagnostic.get("cookie_header_fields", 0) > 1),
             ("Cookie de teste antigo recebido", diagnostic["legacy_cookie_present"]),
             ("Host esperado no retorno", host_ok), ("HTTPS informado pelo proxy", https_ok))
    rows = "".join("<li>" + label + ": <strong>" + ("Sim" if value else "Não") + "</strong></li>"
                   for label, value in facts)
    return ("<!doctype html><html lang='pt-BR'><meta charset='utf-8'><title>Teste de navegador</title>"
            "<body><h1>Cookie não confirmado</h1><p>" + explanation + "</p><ul>" + rows +
            "</ul><p>Versão " + APP_VERSION + ". Nenhuma autorização foi enviada à Meta.</p>"
            "<p>Este resultado não identifica sozinho em qual salto o cookie deixou de chegar. "
            "Compartilhe somente esta tela e as linhas de diagnóstico do aplicativo, sem cookies ou URLs de retorno.</p>"
            "</body></html>")


class Handler(BaseHTTPRequestHandler):
    def parse_request(self):
        if not super().parse_request():
            return False
        # HTTP/2 intermediaries may forward split Cookie fields. HTTPMessage.get
        # returns only the first field; coalesce before ALL auth/CSRF/OAuth paths.
        # Keep every pair, so duplicated state cookies still fail closed.
        fields = self.headers.get_all("Cookie", [])
        self.cookie_header_fields = min(len(fields), 10)
        if len(fields) > 1:
            del self.headers["Cookie"]
            self.headers["Cookie"] = "; ".join(fields)
        return True

    def transport_https(self):
        return self.headers.get("X-Forwarded-Proto", "").strip().lower() == "https"

    def oauth_origin_allowed(self, cfg):
        try:
            origin = origin_configuration.public_origin(cfg)
            matches = origin_configuration.oauth_origin_matches(cfg)
        except ValueError:
            origin, matches = "", False
        if not matches:
            LOGGER.error("OAuth refused: standalone public origin and callback mismatch version=%s", APP_VERSION)
            self.respond(503, {"error": "configure OAuth callback on the public HTTPS origin"})
            return False
        if origin and (self.headers.get("Host", "").lower() != urlsplit(origin).netloc
                       or not self.transport_https()):
            self.respond(421, {"error": "use configured public HTTPS origin"})
            return False
        return True

    def respond(self, status, body, content_type="application/json", *, csp=None):
        raw = body if isinstance(body, bytes) else body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        if content_type == 'text/html':
            raw = interface_ui.enhance(raw)
            csp = interface_ui.policy(csp or "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; object-src 'none'", raw)
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else ""))
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if getattr(self, "ui_session_missing", False) and (status in (401, 403) or (status == 200 and content_type == 'text/html')):
            self.send_header("X-Central-Session-Required", "1")
        if csp:
            self.send_header("Content-Security-Policy", csp if content_type == "text/html" else "default-src 'none'; sandbox")
            if content_type in ("image/png", "image/jpeg", "video/mp4"):
                self.send_header("Content-Disposition", "inline")
                self.send_header("Cross-Origin-Resource-Policy", "same-origin")
        elif content_type == "text/html":
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "form-action 'self'; base-uri 'none'; object-src 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def login_redirect(self, destination):
        self.send_response(303)
        self.send_header("Location", "/panel?" + urlencode({"return_to": safe_login_return(destination) or "/panel"}))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Length", "0")
        self.end_headers()

    def browser_navigation(self):
        mode = self.headers.get("Sec-Fetch-Mode", "")
        return mode == "navigate" or (not mode and "text/html" in self.headers.get("Accept", ""))

    def browser_session_gate(self, method):
        """Do not change machine API status codes or authorize any operation."""
        route = urlsplit(self.path)
        path = route.path
        account = re.match(r'^(/accounts/[a-z][a-z0-9_-]{1,39})(?=/|$)', path)
        prefix = account[1] if account else ''
        suffix = path[len(prefix):]
        page = safe_login_return(self.path) if method == 'GET' else ''
        ui_api = (suffix.startswith('/editorial/') or suffix == '/panel/account-context'
                  or suffix == '/panel' or path == '/accounts'
                  or suffix in ('/panel/meta/check', '/panel/meta/subscribe', '/panel/automation/policy', '/panel/handoff'))
        oauth_navigation = (method == 'GET' and suffix == '/oauth/meta/start' and not route.query
                            and self.browser_navigation()
                            and not self.headers.get('Authorization', '').startswith('Basic '))
        if not page and not ui_api and not oauth_navigation:
            return True
        if panel_session_authorized(self.headers, settings()):
            return True
        # Preserve the existing Basic-auth handoff contract.
        if suffix == '/panel/handoff' and self.headers.get('Authorization', '').startswith('Basic '):
            return True
        self.ui_session_missing = True
        if self.browser_navigation():
            if oauth_navigation:
                self.login_redirect(prefix + '/panel?view=settings')
                return False
            if method == 'GET' and page and path not in ('/', '/panel'):
                self.login_redirect(page)
                return False
            if method == 'POST' and (path == '/accounts' or suffix in (
                    '/panel/meta/check', '/panel/meta/subscribe', '/panel/automation/policy', '/panel/handoff')):
                target = '/accounts' if path == '/accounts' else prefix + '/panel'
                if suffix != '/panel/handoff' and path != '/accounts':
                    target += '?view=settings'
                self.login_redirect(target)
                return False
        return True

    def request_business(self):
        return getattr(self, 'route_business', account_registry.PRIMARY_BUSINESS)

    def request_configuration(self):
        return meta_configuration_for_business(self.request_business())

    def meta_csrf_action(self, action):
        business = self.request_business()
        return action if business == account_registry.PRIMARY_BUSINESS else 'meta:' + business + ':' + action

    def meta_redirect(self, result):
        assert result in META_RESULTS
        self.send_response(303)
        self.send_header('Location', account_management.prefix(self.request_business()) + '/panel?view=settings&meta_result=' + result)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', '0')
        self.end_headers()

    def account_route(self, method):
        """Authenticate explicit account paths before dispatch; no global selection."""
        self.route_business = account_registry.PRIMARY_BUSINESS
        self.account_prefix = ''
        route = urlsplit(self.path)
        if route.path == '/accounts':
            cfg = settings()
            if not panel_session_authorized(self.headers, cfg):
                self.respond(403, {'error': 'authentication required'})
                return False
            with database() as conn:
                account_registry.ensure_primary(conn, cfg.get('instagram_account_id'))
            selected_business = account_registry.PRIMARY_BUSINESS
            if route.query:
                try:
                    selection = parse_qs(route.query, keep_blank_values=True, max_num_fields=1)
                    if method != 'GET' or set(selection) != {'account'} or len(selection['account']) != 1:
                        raise ValueError()
                    selected_business = selection['account'][0]
                    with database() as conn:
                        account_registry.operational_account(conn, selected_business)
                except (ValueError, account_registry.RegistryError):
                    self.respond(404, {'error': 'account context unavailable'})
                    return False
            invalid = False
            if method == 'POST':
                try:
                    lengths = self.headers.get_all('Content-Length', [])
                    if self.headers.get('Transfer-Encoding') or len(lengths) != 1:
                        raise ValueError()
                    size = int(lengths[0])
                    if not 0 < size <= 4096 or self.headers.get('Content-Type', '').split(';')[0] != 'application/x-www-form-urlencoded':
                        raise ValueError()
                    fields = account_management.parse_registration(self.rfile.read(size))
                    if fields is None or not panel_login.admin_csrf_valid(self.headers.get('Cookie', ''), cfg.get('panel_password'), 'accounts:create', fields['csrf']):
                        self.respond(403, {'error': 'invalid account action or CSRF'})
                        return False
                    with database() as conn:
                        business = account_registry.provision(conn, fields['username'], fields['display_name'])
                    self.send_response(303)
                    self.send_header('Location', account_management.prefix(business) + '/panel?view=settings')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Content-Length', '0')
                    self.end_headers()
                    return False
                except account_registry.RegistryError:
                    invalid = True
                except (ValueError, OSError):
                    self.respond(400, {'error': 'invalid account form'})
                    return False
            with database() as conn:
                accounts = account_registry.administrative_accounts(conn)
            page_cfg = {**meta_configuration_for_business(selected_business), 'navigation_accounts': accounts}
            page = account_management.render(accounts, page_cfg, self.headers.get('Cookie', ''),
                    lambda business: connection_summary(meta_configuration_for_business(business)), error=invalid,
                    values=fields if invalid else None)
            self.respond(409 if invalid else 200, page, 'text/html')
            return False
        if not route.path.startswith('/accounts/'):
            return True
        if not panel_session_authorized(self.headers, settings()):
            self.respond(403, {'error': 'authentication required'})
            return False
        match = re.fullmatch(r'/accounts/([a-z][a-z0-9_-]{1,39})(/.*)?', route.path)
        if not match:
            self.respond(404, {'error': 'account route not found'})
            return False
        business, suffix = match.groups()
        try:
            with database() as conn:
                account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
                account_registry.operational_account(conn, business)
        except account_registry.RegistryError:
            self.respond(404, {'error': 'account unavailable'})
            return False
        if suffix is None:
            self.send_response(303)
            self.send_header('Location', account_management.prefix(business) + '/panel')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return False
        allowed = ({'/', '/panel', '/panel/account-context', '/oauth/meta/status', '/oauth/meta/start'} if method == 'GET'
                   else {'/panel/handoff', '/panel/meta/check', '/panel/meta/subscribe', '/panel/automation/policy', '/auth/logout'})
        if suffix not in allowed and suffix != '/editorial' and not suffix.startswith('/editorial/'):
            self.respond(404, {'error': 'account route not found'})
            return False
        self.route_business = business
        self.account_prefix = account_management.prefix(business)
        self.path = suffix + ('?' + route.query if route.query else '')
        return True

    def do_GET(self):
        original = urlsplit(self.path)
        if original.path == '/panel' and original.query.partition('=')[0] == 'return_to':
            destination = login_return_query(original.query) or '/panel'
            if destination:
                cfg = settings()
                if panel_session_authorized(self.headers, cfg):
                    self.send_response(303)
                    self.send_header("Location", destination)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("Content-Length", "0")
                    self.end_headers()
                    return
                return self.respond(200, render_login(cfg, return_to=destination, expired=True), "text/html")
        if not self.browser_session_gate('GET'):
            return
        if not self.account_route('GET'):
            return
        route = urlsplit(self.path)
        sender_route = re.fullmatch(r'view=(sender-profile|sender-image)&sender=([0-9]{8,30})', route.query)
        if route.path == '/panel' and sender_route:
            if not panel_session_authorized(self.headers, settings()):
                return self.respond(403, {'error': 'authentication required'})
            cfg = self.request_configuration()
            image_only = sender_route[1] == 'sender-image'
            result = sender_profiles.get(database, cfg, _meta_credential(self.request_business()),
                                         sender_route[2], image_only=image_only)
            if image_only:
                return self.respond(200 if result else 404, result or b'', 'image/jpeg', csp="default-src 'none'")
            return self.respond(200, result) if result is not None else self.respond(404, {'error': 'profile unavailable'})
        if route.path == '/panel' and route.query == 'view=profile-image':
            if not panel_session_authorized(self.headers, settings()):
                return self.respond(403, {'error': 'authentication required'})
            cfg = self.request_configuration()
            raw = account_avatar.get(DATA_DIR, cfg, _meta_credential(self.request_business()))
            return self.respond(200 if raw else 404, raw or b'', 'image/jpeg', csp="default-src 'none'")
        if self.path == '/webhook/instagram?open=central':
            # Native HA Web UI launcher: reuse the existing GET proxy route.
            # The destination comes only from validated local configuration.
            try:
                origin = origin_configuration.public_origin(settings())
            except ValueError:
                origin = ''
            if not origin:
                return self.respond(503, {'error': 'public Central address unavailable'})
            self.send_response(303)
            self.send_header('Location', origin + '/panel')
            self.send_header('Content-Length', '0')
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.end_headers()
            return
        if editorial_delivery.serve(self, route, PUBLICATION_DELIVERY):
            return
        if route.path.startswith("/editorial") and editorial_http.handle(self, "GET", route,
                navigation_configuration(self.request_configuration()) if route.path in ("/editorial", "/editorial/") else self.request_configuration(),
                panel_session_authorized(self.headers, settings()), editorial_store_for_business,
                business_id=self.request_business(), publisher=PUBLICATIONS, history=HISTORY, connections=multi_connections()):
            return
        if route.path == "/panel/account-context" and not route.query:
            cfg = self.request_configuration()
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            account_id = cfg.get('instagram_account_id')
            return self.respond(200, {
                "businessId": self.request_business(),
                "instagramAccountId": account_id,
                "editorialCorePrepared": True,
                "editorialUIIntegrated": True,
                "sendingEnabled": False,
                "publishingEnabled": PUBLICATIONS.public_state(self.request_business())['ready']
            })
        if route.path == "/oauth/meta/status" and not route.query:
            try:
                cfg = self.request_configuration()
            except account_registry.RegistryError:
                return self.respond(503, {"error": "account context unavailable"})
            if not panel_authorized(self.headers, cfg):
                return self.respond(401, {"error": "authentication required"})
            summary = connection_summary(cfg)
            # Keep existing status contract for older integration consumers.
            summary["enabled"] = summary["oauthReady"]
            summary["credentialStored"] = summary["tokenStored"]
            summary["connectionVerified"] = summary["accountVerified"]
            summary["sendingEnabled"] = False
            return self.respond(200, summary)
        if route.path == "/oauth/meta/start" and route.query in ("", "probe=1"):
            try:
                cfg = self.request_configuration()
            except account_registry.RegistryError:
                return self.respond(503, {"error": "account context unavailable"})
            if not self.oauth_origin_allowed(cfg):
                return
            if not panel_authorized(self.headers, cfg):
                return self.respond(401, {"error": "authentication required"})
            try:
                if route.query == "probe=1":
                    url, cookie = oauth_meta.start_cookie_probe(cfg)
                else:
                    with database() as conn:
                        url, cookie = oauth_meta.start(conn, cfg)
            except oauth_meta.OAuthError:
                return self.respond(503, {"error": "OAuth disabled or incomplete"})
            expected = urlsplit(cfg["meta_oauth_redirect_uri"]).netloc.lower()
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", "0")
            self.end_headers()
            LOGGER.info("OAuth cookie emitted: mode=%s version=%s start_authority_match=%s forwarded_https=%s "
                        "secure=True httponly=True samesite_lax=True callback_path=True max_age=%s",
                        "probe" if route.query == "probe=1" else "oauth", APP_VERSION,
                        self.headers.get("Host", "").strip().lower() == expected,
                        self.transport_https(),
                        60 if route.query == "probe=1" else 600)
            return
        if route.path == "/oauth/meta/callback":
            try:
                cfg = self.request_configuration()
            except account_registry.RegistryError:
                return self.respond(503, {"error": "account context unavailable"})
            if not self.oauth_origin_allowed(cfg):
                return
            if not oauth_meta.is_ready(cfg):
                return self.respond(503, {"error": "OAuth disabled or incomplete"})
            if route.query.startswith("probe="):
                expected = urlsplit(cfg["meta_oauth_redirect_uri"]).netloc.lower()
                host_ok = bool(expected and self.headers.get("Host", "").strip().lower() == expected)
                https_ok = self.transport_https()
                diagnostic = oauth_meta.cookie_diagnostics(route.query, self.headers.get("Cookie", ""), probe=True)
                diagnostic["cookie_header_fields"] = self.cookie_header_fields
                try:
                    oauth_meta.check_cookie_probe(route.query, self.headers.get("Cookie", ""))
                except oauth_meta.OAuthError as exc:
                    LOGGER.error("OAuth cookie probe failed: %s (host_ok=%s, https_ok=%s) version=%s transport=%s",
                                 str(exc), host_ok, https_ok, APP_VERSION, diagnostic)
                    return self.respond(400, render_probe_failure(diagnostic, host_ok, https_ok), "text/html")
                if not host_ok or not https_ok:
                    LOGGER.error("OAuth cookie probe failed: proxy authority or HTTPS mismatch "
                                 "version=%s host_ok=%s https_ok=%s transport=%s",
                                 APP_VERSION, host_ok, https_ok, diagnostic)
                    return self.respond(400, render_probe_failure(diagnostic, host_ok, https_ok), "text/html")
                LOGGER.info("OAuth cookie probe passed: version=%s host_ok=True https_ok=True transport=%s",
                            APP_VERSION, diagnostic)
                return self.respond(200,
                    "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
                    "<title>Teste de conexão</title><body>Teste aprovado: cookie de estado OAuth, "
                    "domínio público e encaminhamento HTTPS. Versão " + APP_VERSION + ". Nenhuma autorização "
                    "foi enviada à Meta.</body></html>", "text/html")
            callback_stage = "parse_callback"
            try:
                state, code = oauth_meta.parse_callback(
                    route.query, self.headers.get("Cookie", ""))
                callback_stage = "consume_state"
                with database() as conn:
                    business = oauth_meta.business_for_state(conn, state)
                cfg = meta_configuration_for_business(business)
                with database() as conn:
                    oauth_meta.consume_state(conn, state, cfg=cfg)
                callback_stage = "exchange_code"
                credential = oauth_meta.exchange_code(code, cfg)
                callback_stage = "verify_instagram_account"
                identity = instagram_connection.verify_access(
                    cfg, credential["access_token"])
                if cfg['business_id'] != account_registry.PRIMARY_BUSINESS:
                    with database() as conn:
                        account_registry.bind_verified(conn, cfg['business_id'], identity['account_id'], identity['username'])
                credential.update(identity)
                credential["business_id"] = cfg["business_id"]
                callback_stage = "store_credential"
                root = account_registry.credential_root(
                    DATA_DIR, cfg.get("business_id", account_registry.PRIMARY_BUSINESS))
                oauth_meta.store_token(root, credential)
            except oauth_meta.OAuthError as exc:
                # Only fixed internal reason strings and boolean proxy context are logged.
                # Never log callback query, authorization code, cookies, tokens or secrets.
                if callback_stage == "parse_callback":
                    expected_authority = urlsplit(cfg["meta_oauth_redirect_uri"]).netloc.lower()
                    received_authority = self.headers.get("Host", "").strip().lower()
                    authority_match = bool(
                        expected_authority and received_authority == expected_authority)
                    forwarded_https = self.transport_https()
                    try:
                        callback_values = parse_qs(route.query, keep_blank_values=True, max_num_fields=10)
                        state_values = callback_values.get("state", [])
                        callback_state = state_values[0] if len(state_values) == 1 else ""
                        with database() as conn:
                            state_status = oauth_meta.state_diagnostics(conn, callback_state)
                    except (ValueError, sqlite3.Error):
                        state_status = {"registered": False, "expired": False, "seconds_remaining": None}
                    transport = oauth_meta.cookie_diagnostics(route.query, self.headers.get("Cookie", ""))
                    transport["cookie_header_fields"] = self.cookie_header_fields
                    LOGGER.error(
                        "Meta OAuth callback rejected at stage=%s: %s "
                        "(redirect_authority_match=%s, forwarded_https=%s) transport=%s state=%s",
                        callback_stage, str(exc), authority_match, forwarded_https,
                        transport, state_status)
                elif isinstance(exc, oauth_meta.OAuthExchangeError):
                    LOGGER.error("Meta OAuth callback rejected at stage=%s: %s %s",
                                 callback_stage, str(exc), exc.safe_details())
                else:
                    LOGGER.error("Meta OAuth callback rejected at stage=%s: %s",
                                 callback_stage, str(exc))
                return self.respond(400, {"error": "OAuth refused or expired"})
            except instagram_connection.ConnectionError as exc:
                LOGGER.error("Meta OAuth callback failed at stage=%s: %s",
                             callback_stage, str(exc))
                return self.respond(502, {"error": "OAuth unavailable"})
            except Exception as exc:
                LOGGER.error("Meta OAuth callback failed at stage=%s (%s)",
                             callback_stage, type(exc).__name__)
                return self.respond(502, {"error": "OAuth unavailable"})
            # No token, authorization code, client ID, or secret is reflected to the client.
            return self.respond(200, "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
                "<title>Instagram</title><body>Conta @" + html.escape(cfg['instagram_expected_username']) + " verificada e autorizada. "
                "A conexão e as verificações estão em Configurações Meta. "
                "Nenhum conteúdo foi enviado.<p><a href='" + account_management.prefix(cfg['business_id']) +
                "/editorial/'>Abrir Editorial desta conta</a></p><p><a href='" + account_management.prefix(cfg['business_id']) +
                "/panel?view=settings'>Abrir Configurações Meta desta conta</a></p></body></html>", "text/html")
        # Chat clients can append attribution to links. This normalization is
        # confined to UI navigation, after all OAuth/launcher routing.
        panel_path = route.path in ('/', '/panel')
        panel_query = panel_navigation_query(route.query) if panel_path else route.query
        meta_result = settings_result(panel_query) if panel_path else None
        settings_page = panel_path and meta_result is not None
        messages_page = self.path in ('/', '/panel') or (
            panel_path and bool(route.query) and not panel_query)
        if messages_page or settings_page:
            cfg = self.request_configuration()
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(200, render_login(cfg, return_to=safe_login_return(self.path),
                    expired=bool(self.headers.get("Cookie"))), "text/html")
            query_fields = parse_qs(route.query, keep_blank_values=True, max_num_fields=3)
            automation_result = query_fields.get('automation_result', [''])[0]
            if automation_result not in ('', 'saved', 'invalid'):
                automation_result = ''
            page = render_panel(cfg, settings_page=settings_page, meta_result=meta_result or '', automation_result=automation_result)
            if not settings_page:
                csrf_inbox = panel_login.admin_csrf_token(
                    self.headers.get('Cookie', ''), cfg.get('panel_password'), self.meta_csrf_action('inbox_refresh'))
                page = page.replace('data-inbox-csrf=""', 'data-inbox-csrf="' + csrf_inbox + '"')
            csrf_check = panel_login.admin_csrf_token(
                self.headers.get("Cookie", ""), cfg.get("panel_password"), self.meta_csrf_action("check"))
            csrf_subscribe = panel_login.admin_csrf_token(
                self.headers.get("Cookie", ""), cfg.get("panel_password"), self.meta_csrf_action("subscribe"))
            if settings_page and csrf_check:
                csrf_automation = panel_login.admin_csrf_token(
                    self.headers.get('Cookie', ''), cfg.get('panel_password'), self.meta_csrf_action('automation'))
                page = page.replace('data-automation-csrf', 'data-automation-csrf')
                page = page.replace('name="csrf" value="" data-automation-csrf',
                                    'name="csrf" value="' + csrf_automation + '" data-automation-csrf')
                csrf_routing = panel_login.admin_csrf_token(
                    self.headers.get('Cookie', ''), cfg.get('panel_password'), self.meta_csrf_action('routing'))
                page = page.replace('data-routing-csrf=""', 'data-routing-csrf="' + csrf_routing + '"')
                saved = connection_summary(cfg)['tokenStored']
                controls = '<form method="post" action="panel/meta/check"><input type="hidden" name="csrf" value="' + csrf_check + '"><button' + ('' if saved else ' disabled') + '>Verificar acesso Meta</button></form>'
                if not saved:
                    controls += '<p>Verificar acesso Meta fica disponível depois de autorizar esta conta em Conectar Instagram pela Meta.</p>'
                if (connection_summary(cfg)["accountVerified"] and
                        connection_summary(cfg)["webhookEnabled"] and
                        connection_summary(cfg)["webhookConfigReady"]):
                    controls += '<form method="post" action="panel/meta/subscribe"><input type="hidden" name="csrf" value="' + csrf_subscribe + '"><button>Assinar mensagens na Meta</button></form>'
                page = page.replace('<div id="meta-actions"></div>',
                                    '<div id="meta-actions">' + controls +
                                    '<p id="meta-action-progress" role="status" aria-live="polite" hidden></p>' +
                                    '</div><script>' + META_ACTION_SCRIPT + '</script>')
            return self.respond(200, page, "text/html", csp=META_ACTION_CSP + "; connect-src 'self'")
        if self.path == "/bridge/pending":
            cfg = settings()
            if not bridge_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            return self.respond(200, {"messages": list_pending(account_id=primary_meta_id(cfg))})
        if self.path == "/health":
            return self.respond(200, {"ok": True, "service": "instagram-central", "mode": "isolated", "version": APP_VERSION})
        if self.path.startswith("/webhook/instagram?"):
            cfg = settings()
            if cfg.get("ingress_enabled") is not True:
                return self.respond(503, {"error": "webhook disabled"})
            q = parse_qs(urlsplit(self.path).query)
            mode = q.get("hub.mode", [""])[0]
            token = q.get("hub.verify_token", [""])[0]
            challenge = q.get("hub.challenge", [""])[0]
            expected = str(cfg.get("meta_verify_token") or "")
            if mode == "subscribe" and expected and hmac.compare_digest(token.encode("utf-8"), expected.encode("utf-8")) and challenge:
                return self.respond(200, challenge, "text/plain")
            return self.respond(403, {"error": "verification refused"})
        return self.respond(404, {"error": "not found"})

    def do_HEAD(self):
        if editorial_delivery.serve(self, urlsplit(self.path), PUBLICATION_DELIVERY, head=True):
            return
        self.send_response(404)
        self.send_header('Content-Length', '0')
        self.end_headers()

    def do_POST(self):
        if self.path.partition('?')[0] == '/webhook/instagram':
            raw_length = self.headers.get('Content-Length')
            try:
                declared_length = int(raw_length) if raw_length is not None else 0
                length_state = ('missing' if raw_length is None else
                                'in_range' if 0 < declared_length <= MAX_BODY else 'out_of_range')
            except ValueError:
                length_state = 'invalid'
            # Arrival is not authenticity: only the later HMAC result verifies Meta.
            # Never log path/query, signature value, source IP, headers or body.
            LOGGER.info('Meta webhook request: version=%s exact_path=%s length=%s signature_present=%s transfer_encoding_present=%s',
                        APP_VERSION, self.path == '/webhook/instagram', length_state,
                        bool(self.headers.get('X-Hub-Signature-256')),
                        bool(self.headers.get('Transfer-Encoding')))
        if editorial_multi_api.handle(self, multi_connections(), settings, multi_store):
            return
        if editorial_import.handle(self, editorial_store_for_business, meta_configuration_for_business, PUBLICATIONS):
            return
        if not self.browser_session_gate('POST'):
            return
        if not self.account_route('POST'):
            return
        route = urlsplit(self.path)
        if route.path.startswith("/editorial") and editorial_http.handle(self, "POST", route, self.request_configuration(),
                panel_session_authorized(self.headers, settings()), editorial_store_for_business,
                business_id=self.request_business(), publisher=PUBLICATIONS, history=HISTORY, connections=multi_connections()):
            return
        if self.path in ("/panel/meta/check", "/panel/meta/subscribe"):
            try:
                cfg = self.request_configuration()
            except account_registry.RegistryError:
                return self.respond(503, {"error": "account context unavailable"})
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
                return self.respond(415, {"error": "invalid content type"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid length"})
            if size <= 0 or size > 512:
                return self.respond(413, {"error": "size not allowed"})
            action = "check" if self.path.endswith("/check") else "subscribe"
            diagnostics = self.headers.get_all('X-Meta-Diagnostic', [])
            inbox = self.headers.get_all('X-Meta-Inbox', [])
            if inbox:
                if inbox != ['refresh'] or diagnostics or action != 'check':
                    return self.respond(400, {'error': 'invalid inbox action'})
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    return self.respond(400, {'error': 'invalid inbox length'})
                action = 'inbox_refresh'
            if diagnostics:
                if diagnostics != ['routing'] or action != 'check':
                    return self.respond(400, {'error': 'invalid diagnostic'})
                if self.headers.get('Transfer-Encoding') or len(self.headers.get_all('Content-Length', [])) != 1:
                    return self.respond(400, {'error': 'invalid diagnostic length'})
                action = 'routing'
            candidate = _meta_action_body(self.rfile.read(size))
            if not panel_login.admin_csrf_valid(
                    self.headers.get("Cookie", ""), cfg.get("panel_password"),
                    self.meta_csrf_action(action), candidate):
                return self.respond(403, {"error": "invalid CSRF"})
            if not oauth_meta.is_ready(cfg):
                if action in ('routing', 'inbox_refresh'):
                    return self.respond(503, {"error": "OAuth disabled or incomplete"})
                return self.meta_redirect('oauth_incomplete')
            if action == 'inbox_refresh':
                return self.respond(200, refresh_inbox(cfg, _meta_credential(self.request_business())))
            if action == 'routing':
                # Read only; never replace/refresh credentials or run the other diagnostics.
                return self.respond(200, instagram_connection.diagnose_conversation_routing(
                    cfg, _meta_credential(self.request_business())))
            try:
                credential = _meta_credential(self.request_business())
                if credential is None or credential.get("business_id", "umdoislab") != cfg["business_id"]:
                    return self.meta_redirect('authorization_missing')
                result = 'check_completed' if action == 'check' else 'subscription_completed'
                if action == "check":
                    # Run the bounded read-only diagnosis alongside identity
                    # verification rather than extending the proxy's wait in series.
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        receiving = pool.submit(instagram_connection.diagnose_receiving, cfg, credential)
                        identity_reason = None
                        try:
                            identity = instagram_connection.verify_access(cfg, credential.get('access_token'))
                        except instagram_connection.GraphError as exc:
                            identity = None
                            identity_reason = exc.details.get('reason')
                        except instagram_connection.ConnectionError:
                            identity = None
                        diagnostics = instagram_connection.safe_diagnostics(receiving.result())
                    if identity is not None:
                        credential.update(identity)
                    credential['receiving_diagnostics'] = diagnostics
                    credential['last_meta_action'] = {'kind': 'check', 'identity_verified': identity is not None}
                    if identity is None:
                        if identity_reason in ('token_invalid', 'permission_denied'):
                            result = identity_reason
                            credential['last_meta_action']['reason'] = identity_reason
                        else:
                            result = 'query_failed'
                    LOGGER.info('Meta receiving diagnosis: version=%s summary=%s', APP_VERSION, diagnostics)
                else:
                    when = instagram_connection.subscribe_messages(cfg, credential)
                    credential["subscribed_at"] = when
                    credential['last_meta_action'] = {'kind': 'subscribe'}
                    # A previous read cannot certify the state after this write.
                    credential.pop('receiving_diagnostics', None)
                root = account_registry.credential_root(
                    DATA_DIR, cfg.get("business_id", account_registry.PRIMARY_BUSINESS))
                oauth_meta.store_token(root, credential)
                LOGGER.info('Meta action completed: version=%s action=%s', APP_VERSION, action)
            except instagram_connection.GraphError as exc:
                reason = exc.details.get('reason')
                return self.meta_redirect(reason if reason in ('token_invalid', 'permission_denied') else
                                          'subscription_failed' if action == 'subscribe' else 'query_failed')
            except instagram_connection.ConnectionError:
                return self.meta_redirect('subscription_failed' if action == 'subscribe' else 'query_failed')
            except (oauth_meta.OAuthError, OSError, ValueError):
                return self.meta_redirect('storage_error')
            return self.meta_redirect(result)
        if self.path == "/auth/login":
            cfg = settings()
            password = cfg.get("panel_password")
            if not isinstance(password, str) or len(password) < 16:
                return self.respond(503, render_login(cfg), "text/html")
            client_id = self.client_address[0]
            if not panel_login.allowed_attempt(client_id):
                return self.respond(429, render_login(cfg, locked=True), "text/html")
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
                return self.respond(415, {"error": "invalid content type"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid length"})
            if size <= 0 or size > 4096:
                return self.respond(413, {"error": "size not allowed"})
            fields = _login_form_fields(self.rfile.read(size))
            if (fields is None or fields[0] != "admin" or
                    not hmac.compare_digest(fields[1].encode("utf-8"), password.encode("utf-8"))):
                panel_login.failed_attempt(client_id)
                return self.respond(401, render_login(cfg, invalid=True, return_to=fields[2] if fields else ''), "text/html")
            try:
                with database() as conn:
                    token = panel_login.create_session(conn, password)
            except (OSError, sqlite3.Error, ValueError):
                return self.respond(503, {"error": "session unavailable"})
            panel_login.successful_attempt(client_id)
            self.send_response(303)
            self.send_header("Location", fields[2] or "../panel")
            self.send_header("Set-Cookie", panel_login.set_cookie_header(
                token, secure=_external_https(self.headers)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/auth/logout":
            cfg = settings()
            try:
                with database() as conn:
                    panel_login.revoke_session(conn, self.headers.get("Cookie", ""),
                                               cfg.get("panel_password"))
            except (OSError, sqlite3.Error, ValueError):
                pass  # Still clear the browser cookie.
            self.send_response(303)
            self.send_header("Location", "/panel" if self.account_prefix else "../panel")
            self.send_header("Set-Cookie", panel_login.clear_cookie_header(
                secure=_external_https(self.headers)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/panel/automation/policy":
            cfg = self.request_configuration()
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            if cfg.get('business_id', account_registry.PRIMARY_BUSINESS) != account_registry.PRIMARY_BUSINESS:
                return self.respond(403, {"error": "automation policy is restricted to the primary account"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
                return self.respond(415, {"error": "invalid content type"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid length"})
            if size <= 0 or size > 12000 or self.headers.get('Transfer-Encoding'):
                return self.respond(413, {"error": "size not allowed"})
            try:
                fields = parse_qs(self.rfile.read(size).decode('utf-8'), keep_blank_values=True, max_num_fields=8)
            except (ValueError, UnicodeDecodeError):
                fields = {}
            if (set(fields) != {'csrf', 'mode', 'test_ids', 'excluded_ids'} or
                    any(len(values) != 1 for values in fields.values()) or
                    not panel_login.admin_csrf_valid(self.headers.get('Cookie', ''), cfg.get('panel_password'),
                                                      self.meta_csrf_action('automation'), fields.get('csrf', [''])[0])):
                return self.respond(403, {"error": "invalid automation policy action or CSRF"})
            try:
                with _AUTOMATION_LOCK, database() as conn:
                    automation_policy.save(conn, cfg.get('instagram_account_id', ''),
                        fields['mode'][0], fields['test_ids'][0], fields['excluded_ids'][0])
                    conn.execute("DELETE FROM human_offers WHERE recipient_id=?", (cfg.get('instagram_account_id',''),))
            except automation_policy.PolicyError:
                result = 'invalid'
            else:
                result = 'saved'
            self.send_response(303)
            self.send_header('Location', account_management.prefix(self.request_business()) +
                             '/panel?view=settings&automation_result=' + result)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', '0')
            self.end_headers()
            return
        if self.path == "/panel/handoff":
            cfg = self.request_configuration()
            if not panel_authorized(self.headers, cfg):
                return self.respond(401, {"error": "authentication required"})
            if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/x-www-form-urlencoded":
                return self.respond(415, {"error": "invalid content type"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid length"})
            if size <= 0 or size > 4096:
                return self.respond(413, {"error": "size not allowed"})
            data = parse_action(self.rfile.read(size), cfg.get("panel_password", ""))
            if not data or data["accountId"] != cfg.get("instagram_account_id") or not set_handoff(data, actor="panel", reason="manual_action"):
                return self.respond(403, {"error": "invalid action or CSRF"})
            self.send_response(303)
            self.send_header("Location", "../panel")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/bridge/claim":
            cfg = settings()
            if not bridge_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            return self.respond(200, {"message": claim_message(account_id=primary_meta_id(cfg))})
        if self.path in ("/bridge/handoff", "/bridge/ack", "/bridge/context", "/bridge/decision", "/bridge/draft", "/bridge/reply"):
            cfg = settings()
            if not bridge_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            try:
                size = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self.respond(400, {"error": "invalid length"})
            if size <= 0 or size > 4096:
                return self.respond(413, {"error": "size not allowed"})
            try:
                data = json.loads(self.rfile.read(size))
            except (ValueError, UnicodeDecodeError):
                return self.respond(400, {"error": "invalid JSON"})
            # The existing bridge_secret belongs to Umdoislab only.
            # Per-account bridge secrets are a future feature, not enabled here.
            if not isinstance(data, dict) or data.get("accountId") != primary_meta_id(cfg):
                return self.respond(403, {"error": "wrong account scope"})
            if self.path == "/bridge/handoff":
                reason = data.pop("reason", None)
                if reason not in (None, "human_review", "unsafe_content", "model_requested_handoff"):
                    return self.respond(422, {"error": "invalid handoff reason"})
                claim = None
                if "messageId" in data or "claimToken" in data:
                    if "messageId" not in data or "claimToken" not in data:
                        return self.respond(422, {"error": "incomplete handoff claim"})
                    claim = (data.pop("messageId"), data.pop("claimToken"))
                if not set_handoff(data, actor="bridge", reason=reason, claim=claim):
                    return self.respond(409 if claim is not None else 422,
                                        {"error": "invalid handoff"})
                return self.respond(200, {"saved": True})
            if self.path == "/bridge/context":
                context = conversation_context(data)
                if context is None:
                    return self.respond(409, {"error": "invalid or expired claim"})
                return self.respond(200, context)
            if self.path == "/bridge/decision":
                decision = evaluate_claim(data)
                if decision is None:
                    return self.respond(409, {"error": "invalid or expired claim"})
                return self.respond(200, {"decision": decision})
            if self.path == "/bridge/reply":
                credential = _meta_credential(account_registry.PRIMARY_BUSINESS)
                result = send_automatic_reply(data, cfg, credential)
                if result["status"] == "sent":
                    return self.respond(200, {"sent": True, "messageId": result["messageId"]})
                if result["status"] == "failed":
                    return self.respond(502, {"sent": False, "reason": result["reason"]})
                return self.respond(409, {"sent": False, "reason": result["reason"]})
            if self.path == "/bridge/draft":
                if cfg.get("drafts_enabled") is not True:
                    return self.respond(503, {"error": "draft storage disabled"})
                if not save_draft(data):
                    return self.respond(409, {"error": "draft refused or already exists"})
                return self.respond(201, {"stored": True, "sent": False})
            if not acknowledge_message(data):
                return self.respond(422, {"error": "invalid acknowledgment"})
            return self.respond(200, {"acknowledged": True})
        if self.path != "/webhook/instagram":
            return self.respond(404, {"error": "not found"})
        cfg = settings()
        secret = str(cfg.get("meta_app_secret") or "")
        account_id = str(cfg.get("instagram_account_id") or "")
        if cfg.get("ingress_enabled") is not True or not secret or not account_id:
            LOGGER.info("Meta webhook rejected: version=%s reason=disabled_or_incomplete", APP_VERSION)
            return self.respond(503, {"error": "webhook disabled"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.respond(400, {"error": "invalid length"})
        if size <= 0 or size > MAX_BODY:
            return self.respond(413, {"error": "size not allowed"})
        body = self.rfile.read(size)
        if not signature_valid(body, self.headers.get("X-Hub-Signature-256"), secret):
            LOGGER.info("Meta webhook rejected: version=%s reason=invalid_signature", APP_VERSION)
            return self.respond(403, {"error": "invalid signature"})
        count = persist(body, account_id)
        if count is None:
            LOGGER.info("Meta webhook rejected: version=%s reason=invalid_json", APP_VERSION)
            return self.respond(400, {"error": "invalid JSON"})
        stats = webhook_diagnostics(body, account_id)
        LOGGER.info("Meta webhook accepted: version=%s legacy_events=%d unified_events=%d "
                    "recipient_match=%d matched_text=%d stored=%d", APP_VERSION,
                    stats["legacy"], stats["unified"], stats["recipient_match"],
                    stats["matched_text"], count)
        return self.respond(200, {"accepted": True, "new_text_messages": count})

    def log_message(self, fmt, *args):
        # Do not log client identifiers or message contents.
        return


class _DualStackHTTPServer(ThreadingHTTPServer):
    address_family = socket.AF_INET6

    def server_bind(self):
        # One internal port accepts IPv6 and IPv4-mapped connections.
        self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
        super().server_bind()


def create_internal_http_server(port):
    if socket.has_dualstack_ipv6():
        return _DualStackHTTPServer(("::", port), Handler)
    return ThreadingHTTPServer(("0.0.0.0", port), Handler)


def publication_businesses():
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
        return [item['business_id'] for item in account_registry.administrative_accounts(conn)]


PUBLICATION_DELIVERY = editorial_delivery.MediaDelivery(database, editorial_store_for_business)
PUBLICATIONS = editorial_publishing.PublisherHub(
    meta_configuration_for_business, _meta_credential, editorial_store_for_business,
    publication_businesses, PUBLICATION_DELIVERY)
HISTORY = editorial_history.HistoryHub(PUBLICATIONS)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with database():
        pass
    with create_internal_http_server(int(os.environ.get("PORT", "8099"))) as internal:
        transport = "ipv4_ipv6" if internal.address_family == socket.AF_INET6 else "ipv4"
        LOGGER.info("Central internal HTTP ready: port=%s version=%s transport=%s; public TLS belongs to reverse proxy",
                    internal.server_address[1], APP_VERSION, transport)
        worker = threading.Thread(target=PUBLICATIONS.run, name='editorial-publisher', daemon=True)
        worker.start()
        history_worker = threading.Thread(target=HISTORY.run, name="editorial-history", daemon=True)
        history_worker.start()
        try:
            internal.serve_forever()
        finally:
            PUBLICATIONS.stop.set()
            PUBLICATIONS.wake.set()
            HISTORY.stop.set()
            HISTORY.wake.set()
            worker.join(timeout=3)
            history_worker.join(timeout=3)
