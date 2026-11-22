#!/usr/bin/env python3
"""Instagram Central internal service behind the existing HTTPS reverse proxy. No Meta send API, n8n calls or WhatsApp access."""
import base64
import hashlib
import html
import hmac
import json
import logging
import os
import secrets
import re
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
import account_registry
import account_management
import editorial_core
import editorial_http
import panel_login
import origin_configuration
from urllib.parse import parse_qs, urlsplit
from zoneinfo import ZoneInfo

DATA_DIR = Path(os.environ.get("INSTAGRAM_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "instagram.sqlite3"
OPTIONS_PATH = Path(os.environ.get("INSTAGRAM_OPTIONS", "/data/options.json"))
MAX_BODY = 256 * 1024
LOGGER = logging.getLogger("instagram-central")
APP_VERSION = "0.1.22"


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
      PRIMARY KEY(recipient_id, sender_id, message_id))""")
    if "processed_at" not in {r[1] for r in conn.execute("PRAGMA table_info(inbound)")}:
        conn.execute("ALTER TABLE inbound ADD COLUMN processed_at TEXT")
    columns = {r[1] for r in conn.execute("PRAGMA table_info(inbound)")}
    for column in ("claim_token", "claim_until"):
        if column not in columns:
            conn.execute("ALTER TABLE inbound ADD COLUMN " + column + " TEXT")
    conn.execute("""CREATE TABLE IF NOT EXISTS handoff (
      recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL,
      state TEXT NOT NULL DEFAULT 'bot' CHECK(state IN ('bot','pending','human','done')),
      updated_at TEXT NOT NULL,
      PRIMARY KEY(recipient_id, sender_id))""")
    conn.execute("""CREATE TABLE IF NOT EXISTS handoff_audit (
      id INTEGER PRIMARY KEY AUTOINCREMENT, recipient_id TEXT NOT NULL,
      sender_id TEXT NOT NULL, old_state TEXT NOT NULL, new_state TEXT NOT NULL,
      changed_at TEXT NOT NULL, actor TEXT NOT NULL)""")
    conn.execute("""CREATE TABLE IF NOT EXISTS drafts (
      recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
      draft_text TEXT NOT NULL, draft_source TEXT NOT NULL DEFAULT 'lab',
      created_at TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending'
        CHECK(status IN ('pending','discarded')),
      PRIMARY KEY(recipient_id,sender_id,message_id))""")
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


def list_pending(limit=50, *, account_id=None):
    """Read-only queue for a single Meta recipient, never the whole database."""
    if account_id is None:
        account_id = primary_meta_id()
    with database() as conn:
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_id,
            i.message_text, i.received_at,
            COALESCE(h.state, 'bot') AS handoff_state
            FROM inbound i LEFT JOIN handoff h
              ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
            WHERE i.processed_at IS NULL AND i.recipient_id=?
            ORDER BY i.received_at, i.rowid LIMIT ?""",
            (account_id, min(max(int(limit), 1), 50))).fetchall()
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
        row = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_id,
          i.message_text, i.received_at, COALESCE(h.state, 'bot')
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          WHERE i.processed_at IS NULL AND i.recipient_id=?
            AND COALESCE(h.state, 'bot') = 'bot'
            AND (i.claim_until IS NULL OR i.claim_until <= ?)
          ORDER BY i.received_at, i.rowid LIMIT 1""",
          (account_id, now_iso)).fetchone()
        if row is None:
            return None
        conn.execute("""UPDATE inbound SET claim_token=?, claim_until=?
          WHERE recipient_id=? AND sender_id=? AND message_id=? AND processed_at IS NULL""",
          (token, until_iso, row[0], row[1], row[2]))
    return {"channel": "instagram", "accountId": row[0], "senderId": row[1],
            "messageId": row[2], "messageText": row[3], "receivedAt": row[4],
            "handoffState": row[5], "claimToken": token, "claimUntil": until_iso}


def acknowledge_message(data):
    """Only the owner of an unexpired claim can ACK; stale retries fail closed."""
    if not isinstance(data, dict) or set(data) != {"accountId", "senderId", "messageId", "claimToken"}:
        return False
    account, sender, mid, token = (data["accountId"], data["senderId"],
                                   data["messageId"], data["claimToken"])
    if not all(isinstance(v, str) and 1 <= len(v) <= 160 for v in (account, sender, mid)):
        return False
    if not isinstance(token, str) or len(token) < 32 or len(token) > 256:
        return False
    with database() as conn:
        cur = conn.execute("""UPDATE inbound SET processed_at=?, claim_token=NULL, claim_until=NULL
          WHERE recipient_id=? AND sender_id=? AND message_id=?
            AND processed_at IS NULL AND claim_token=? AND claim_until > ?""",
          (_utc_now().isoformat(), account, sender, mid, token, _utc_now().isoformat()))
        return cur.rowcount == 1


def evaluate_claim(data):
    """Classify only an active owned lease; never generate/send a response."""
    keys = {"accountId", "senderId", "messageId", "claimToken"}
    if not isinstance(data, dict) or set(data) != keys:
        return None
    values = [data[k] for k in ("accountId", "senderId", "messageId", "claimToken")]
    if not all(isinstance(v, str) and 1 <= len(v) <= 160 for v in values[:3]):
        return None
    if not isinstance(values[3], str) or not 32 <= len(values[3]) <= 256:
        return None
    with database() as conn:
        row = conn.execute("""SELECT i.message_text, COALESCE(h.state, 'bot')
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          WHERE i.recipient_id=? AND i.sender_id=? AND i.message_id=?
            AND i.claim_token=? AND i.claim_until>? AND i.processed_at IS NULL""",
          (*values, _utc_now().isoformat())).fetchone()
    if row is None:
        return None
    return prepare_decision({
        "channel": "instagram", "accountId": values[0], "senderId": values[1],
        "messageId": values[2], "claimToken": values[3],
        "messageText": row[0], "handoffState": row[1]})


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
            AND i.processed_at IS NULL AND COALESCE(h.state, 'bot')='bot'""",
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


def set_handoff(data):
    if not isinstance(data, dict) or set(data) != {"accountId", "senderId", "state"}:
        return False
    account, sender, state = data["accountId"], data["senderId"], data["state"]
    if (not isinstance(account, str) or not 1 <= len(account) <= 160 or
        not isinstance(sender, str) or not 1 <= len(sender) <= 160 or
        state not in ("bot", "pending", "human", "done")):
        return False
    with database() as conn:
        found = conn.execute("""SELECT 1 FROM inbound WHERE recipient_id=? AND sender_id=? LIMIT 1""",
                             (account, sender)).fetchone()
        if not found:
            return False
        prev = conn.execute("SELECT state FROM handoff WHERE recipient_id=? AND sender_id=?",
                            (account, sender)).fetchone()
        old_state = prev[0] if prev else "bot"
        if old_state == state:
            return True
        now = datetime.now(timezone.utc).isoformat()
        conn.execute("""INSERT INTO handoff VALUES(?,?,?,?)
          ON CONFLICT(recipient_id,sender_id) DO UPDATE SET
          state=excluded.state, updated_at=excluded.updated_at""",
          (account, sender, state, now))
        conn.execute("""INSERT INTO handoff_audit
          (recipient_id,sender_id,old_state,new_state,changed_at,actor)
          VALUES(?,?,?,?,?,?)""", (account, sender, old_state, state, now, "panel_or_bridge"))
        # Invalidate any active reservation before handing the conversation to a human.
        if state != "bot":
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
        if not all(isinstance(v, str) and 1 <= len(v) <= 160 for v in (sender_id, recipient_id, mid)):
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


def persist(body, account_id=None):
    """Route signed events by known recipient, never by caller-provided business_id."""
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    # Only a payload already matching the configured legacy recipient can
    # bootstrap the single existing account; arbitrary events cannot remap it.
    legacy_messages = normalized_messages(payload, account_id)
    inserted = 0
    with database() as conn:
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
                "INSERT OR IGNORE INTO inbound (recipient_id,sender_id,message_id,message_text,received_at) VALUES(?,?,?,?,?)",
                (rid, sid, mid, msg, datetime.now(timezone.utc).isoformat()))
            inserted += cursor.rowcount
    return inserted


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


def render_login(cfg=None, invalid=False, locked=False):
    """Own HTML form. Chrome can offer to save its standard username/password."""
    cfg = cfg or {}
    try:
        origin = origin_configuration.public_origin(cfg)
    except ValueError:
        origin = ""
    standalone_link = ('<p><a href="' + html.escape(origin + '/panel', quote=True) +
                       '" target="_blank" rel="noopener noreferrer">Abrir Central em janela própria</a></p>') if origin else ''
    configured = isinstance(cfg.get("panel_password"), str) and len(cfg["panel_password"]) >= 16
    if not configured:
        notice = '<p class="notice" role="alert">Configure uma senha de pelo menos 16 caracteres nas opções do aplicativo.</p>'
    elif locked:
        notice = '<p class="notice" role="alert">Muitas tentativas. Tente novamente em alguns minutos.</p>'
    elif invalid:
        notice = '<p class="notice" role="alert">Usuário ou senha incorretos.</p>'
    else:
        notice = ''
    fields = ("""<form method="post" action="auth/login" autocomplete="on">
      <label for="username">Usuário</label>
      <input id="username" name="username" type="text" value="admin"
        autocomplete="username" autocapitalize="off" spellcheck="false" required>
      <label for="password">Senha</label>
      <input id="password" name="password" type="password"
        autocomplete="current-password" required>
      <button type="submit">Entrar</button></form>""" if configured else "")
    return ("""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Entrar — Central Instagram</title>
<style>
:root{color-scheme:light}*{box-sizing:border-box}
body{margin:0;min-height:100vh;display:grid;place-items:center;padding:1.2rem;
 font-family:system-ui,-apple-system,sans-serif;background:#f3f5fa;color:#17243b}
main{width:min(100%,410px);background:white;padding:clamp(1.5rem,5vw,2.3rem);
 border:1px solid #e1e5ee;border-radius:18px;box-shadow:0 12px 40px #13264214}
.kicker{color:#a24321;text-transform:uppercase;letter-spacing:.08em;font-size:.78rem;font-weight:700}
h1{font-size:1.5rem;margin:.7rem 0 .3rem}
p{color:#526078;line-height:1.5;font-size:.94rem}
form{display:grid;gap:.45rem;margin-top:1.5rem}
label{font-size:.9rem;font-weight:650;margin-top:.6rem}
input{font:inherit;width:100%;padding:.8rem .85rem;border:1px solid #a9b4c5;border-radius:9px;background:white;color:#14243c}
input:focus-visible,button:focus-visible{outline:3px solid #6e99e7;outline-offset:2px}
button{font:inherit;margin-top:1rem;padding:.8rem;cursor:pointer;border:0;border-radius:9px;
 background:#152f56;color:white;font-weight:650}
button:hover{background:#244978}
.notice{padding:.8rem;border-radius:9px;background:#fff1e8;color:#813613}
small{display:block;color:#59697d;margin-top:1.3rem}
</style></head><body><main>
<div class="kicker">Umdoislab · acesso administrativo</div>
<h1>Central Instagram</h1>
<p>Entre para acessar as mensagens e a fila local.</p>"""
        + notice + standalone_link + fields +
        "<small>Use a senha cadastrada nas configurações da Central. "
        "O Chrome pode oferecer para salvá-la.</small></main></body></html>")


def _login_form_fields(raw):
    if not isinstance(raw, bytes) or len(raw) > 4096:
        return None
    try:
        fields = parse_qs(raw.decode("utf-8"), keep_blank_values=True, max_num_fields=2)
    except (ValueError, UnicodeDecodeError):
        return None
    if set(fields) != {"username", "password"} or any(len(v) != 1 for v in fields.values()):
        return None
    return fields["username"][0], fields["password"][0]


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
    """Internal-only scoped EditorialStore, same add-on, no alternate login/API."""
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get("instagram_account_id"))
        account_registry.require_business(conn, business_id)
    return editorial_core.EditorialStore(
        account_registry.editorial_root(DATA_DIR, business_id))


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
                "SELECT COUNT(*), MAX(received_at) FROM inbound WHERE recipient_id=?",
                (account_id,)).fetchone()
        else:
            row = (0, None)
    return {
        "oauthReady": oauth_meta.is_ready(cfg),
        "tokenStored": bool(credential),
        "accountVerified": state["account_verified"],
        "subscriptionRequested": state["subscription_requested"],
        "webhookEnabled": cfg.get("ingress_enabled") is True,
        "webhookConfigReady": (isinstance(cfg.get("meta_verify_token"), str)
             and len(cfg["meta_verify_token"]) >= 24
             and isinstance(cfg.get("meta_app_secret"), str)
             and len(cfg["meta_app_secret"]) >= 16),
        "messagesStored": int(row[0]),
        "lastMessageReceived": row[1],
        "verifiedAt": credential.get("verified_at") if state["account_verified"] else None,
        "receivingDiagnostics": instagram_connection.safe_diagnostics(
            credential.get('receiving_diagnostics')) if state['account_verified'] else None,
        "lastMetaAction": credential.get('last_meta_action') if state['account_verified'] else None,
    }


def render_meta_diagnostics(summary):
    """Visible result from stored, account-bound evidence, never provider text."""
    action = summary.get('lastMetaAction')
    feedback = ''
    if isinstance(action, dict) and action.get('kind') in ('check', 'subscribe'):
        text = (('Não foi possível confirmar novamente a identidade na Meta. Confira o diagnóstico abaixo; a verificação anterior não foi renovada.'
                 if action.get('identity_verified') is False else
                 'Verificação de identidade concluída. Confira o diagnóstico de recebimento abaixo.')
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
        'request_unavailable': 'A consulta não pôde ser concluída.'}
    parts = []
    for key, title in (('subscription', 'Assinatura consultada na Meta'),
                       ('conversations', 'Acesso às conversas')):
        value = report[key]
        if value['status'] == 'confirmed' and key == 'subscription':
            text = ('Aplicativo encontrado, campo messages presente.' if value.get('messages') is True else
                    'Aplicativo encontrado, campo messages ausente.' if value.get('messages') is False else
                    'Aplicativo encontrado; campo messages não confirmado.')
        elif value['status'] == 'confirmed':
            text = ('Acesso aceito; há conversa visível, sem consultar seu conteúdo.' if value.get('conversation_found') else
                    'Acesso aceito; a amostra retornou vazia.')
        elif value['status'] == 'absent':
            text = 'O aplicativo não consta na assinatura desta conta.'
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
            '<p>Estas consultas não enviam mensagens nem comprovam a entrega de eventos reais.</p></div>')


def render_connection_section(cfg, summary):
    """Show precise progress. Never print tokens, app secrets, verify tokens."""
    name = html.escape(str(cfg.get("instagram_account_id") or "não configurada"), quote=True)
    items = (
        ("OAuth preparado", summary["oauthReady"]),
        ("Conta verificada na Meta", summary["accountVerified"]),
        ("Webhook habilitado", summary["webhookEnabled"]),
        ("Assinatura solicitada", summary["subscriptionRequested"]),
    )
    flags = "".join("<li>" + html.escape(label) + ": <strong>" +
                    ("Sim" if value else "Não") + "</strong></li>"
                    for label, value in items)
    last = summary["lastMessageReceived"] or "Nenhuma"
    url = cfg.get("meta_oauth_redirect_uri", "")
    actions = []
    try:
        origin = origin_configuration.public_origin(cfg)
        origin_matches = origin_configuration.oauth_origin_matches(cfg)
    except ValueError:
        origin, origin_matches = "", False
    if origin:
        actions.append('<a href="' + html.escape(origin + cfg.get("account_path", "") + "/panel", quote=True)
                       + '" target="_blank" rel="noopener noreferrer">Abrir Central em janela própria</a>')
    if not origin_matches:
        actions.append('<p>Configure o retorno OAuth na mesma URL pública HTTPS da Central antes de conectar.</p>')
    if summary["oauthReady"] and not summary["accountVerified"] and origin_matches:
        # A browser session established via the same HTTPS hostname is required
        # for the public proxy route to recognize the session cookie.
        start_url = url[:-len("/oauth/meta/callback")] + cfg.get("account_path", "") + "/oauth/meta/start"
        actions.append('<a href="' + html.escape(start_url + "?probe=1", quote=True)
                       + '" target="_blank" rel="noopener noreferrer">Testar navegador e proxy (sem Meta)</a>')
        actions.append('<a href="' + html.escape(start_url, quote=True)
                       + '" target="_blank" rel="noopener noreferrer">Conectar Instagram pela Meta</a>')
    setup = (
        ("App Meta", bool(str(cfg.get("meta_app_id") or "").isdigit())),
        ("Login unificado", bool(str(cfg.get("meta_login_config_id") or "").isdigit())),
        ("Conta Instagram", bool(str(cfg.get("instagram_account_id") or "").isdigit())),
        ("Retorno HTTPS", oauth_meta.is_ready(cfg)),
        ("Segredo Meta", isinstance(cfg.get("meta_app_secret"), str)
          and len(cfg.get("meta_app_secret", "")) >= 16),
        ("Token de verificação", isinstance(cfg.get("meta_verify_token"), str)
          and len(cfg.get("meta_verify_token", "")) >= 24),
    )
    checklist = "".join("<li>" + label + ": " + ("configurado" if ready else "pendente")
                        + "</li>" for label, ready in setup)
    return ("""<section class="panel connection-panel" aria-label="Conexão com Instagram">
       <h2>Conexão com o Instagram</h2><p>Conta: <strong>@""" + html.escape(str(cfg.get("instagram_expected_username") or "umdoislab")) + """</strong>
       · ID: <code>""" + name + """</code></p>
       <ul>""" + flags + """</ul>
       <details><summary>Configuração necessária</summary><ul>""" + checklist + """</ul>
       <p>As credenciais são configuradas nas opções do aplicativo no Home Assistant.
       Não compartilhe segredos por mensagem.</p></details>
       <p><strong>Mensagens armazenadas: """ + str(summary["messagesStored"]) +
       """</strong> · Última entrada: """ + html.escape(str(last)) + """</p>
       <p><small>Uma assinatura aceita pela Meta não comprova que mensagens já chegam.
       O primeiro recebimento assinado é a confirmação.</small></p>""" +
        " ".join(actions) + render_meta_diagnostics(summary) +
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


def render_panel(cfg=None):
    """Escaped local-only panel, with no Meta send or browser scripts."""
    cfg = cfg or {}
    with database() as conn:
        account_registry.ensure_primary(conn, settings().get('instagram_account_id'))
        account_id = account_registry.require_business(conn, cfg.get('business_id', account_registry.PRIMARY_BUSINESS))['instagram_account_id']
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_text,
          i.received_at, i.processed_at, COALESCE(h.state, 'bot'),
          COALESCE(d.draft_text, ''), COALESCE(d.status, '')
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          LEFT JOIN drafts d ON i.recipient_id=d.recipient_id
            AND i.sender_id=d.sender_id AND i.message_id=d.message_id
          WHERE i.recipient_id=?
          ORDER BY i.received_at DESC, i.rowid DESC LIMIT 50""", (account_id,)).fetchall()
    entries = []
    cfg = cfg or {}
    for account, sender, message, received, processed, state, draft, draft_status in rows:
        cells = (sender, message, state, received, "Processada" if processed else "Pendente", draft or "—")
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
                actions.append('<form method="post" action="panel/handoff">' + inputs +
                               '<button type="submit">' + label + '</button></form>')
        entries.append("<tr>" + "".join("<td>" + html.escape(str(v), quote=True) +
                       "</td>" for v in cells) + '<td><div class="item-actions">' + "".join(actions) + "</div></td></tr>")
    body = "".join(entries) if entries else '<tr><td colspan="7">Nenhuma mensagem recebida.</td></tr>'
    summary = connection_summary(cfg)
    connection_section = render_connection_section(cfg, summary)
    return ("""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="theme-color" content="#111c29">
<meta name="robots" content="noindex,nofollow">
<title>Mensagens · Central Instagram Umdoislab</title>
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
.connection-panel ul{line-height:1.9;display:grid;gap:3px;padding-left:22px}
.connection-panel li{overflow-wrap:anywhere}
.connection-panel strong{color:#eaf1f8}
.connection-panel details{background:var(--surface2);border:1px solid var(--edge);border-radius:10px;padding:12px 15px;margin:15px 0}
.connection-panel summary{cursor:pointer;font-weight:700}
.connection-panel a{color:var(--orange)}
.connection-panel code{color:#d0e4ff;overflow-wrap:anywhere}
.connection-panel small{color:var(--muted)}
#meta-actions{display:flex;flex-wrap:wrap;gap:10px;margin-top:16px}
#meta-actions form{margin:0}
#meta-actions button{border:1px solid var(--orange);background:var(--orange);color:#161b23;border-radius:10px;padding:10px 15px;font-weight:700}
#meta-actions button:hover{filter:brightness(1.09)}
.panel-title{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}
.table-wrap{width:100%;overflow-x:auto;border:1px solid var(--edge);border-radius:11px}
table{border-collapse:collapse;min-width:870px;width:100%;table-layout:fixed}
th,td{padding:14px 12px;border-bottom:1px solid var(--edge);text-align:left;overflow-wrap:anywhere;vertical-align:top;line-height:1.45}
th{background:var(--surface2);color:#c7d8e6;font-size:12px;letter-spacing:.1px}
tr:last-child td{border-bottom:0}
tbody tr:hover{background:#1a2c3b}
.item-actions{display:flex;flex-wrap:wrap;gap:7px}
.item-actions form{margin:0;display:inline-flex}
th:nth-child(1){width:12%}th:nth-child(2){width:20%}th:nth-child(3){width:9%}th:nth-child(4){width:13%}
th:nth-child(5){width:11%}th:nth-child(6){width:16%}th:nth-child(7){width:19%}
.note{border:1px solid #465538;background:#222c23;border-radius:12px;padding:15px 18px;color:#c5d5bf;line-height:1.6}
@media(max-width:760px){
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
<aside class="sidebar">
 <div class="brand"><span class="brand-icon">U<span class="dot">.</span></span><div><strong>UMDOISLAB</strong><small>Central de mídia</small></div></div>
 <div class="section-label">CENTRAL INSTAGRAM</div>
 <nav class="nav" aria-label="Módulos">
  <a class="nav-link active" aria-current="page" href="./"><span aria-hidden="true">◉</span> Mensagens</a>
  <a class="nav-link" href="editorial/"><span aria-hidden="true">✎</span> Editorial</a>
  <a class="nav-link" href="/accounts"><span aria-hidden="true">◎</span> Contas</a>
 </nav>
 <div class="sidebar-foot"><span class="status-led"></span><div><strong>Atendimento local</strong><small>Sem envio automático</small></div></div>
</aside>
<main id="principal" class="main">
 <header class="topbar">
  <div class="crumb">""" + html.escape(str(cfg.get("account_display_name") or "Umdoislab")) + """ <span>/</span> <strong>Mensagens</strong></div>
  <div class="top-actions"><span class="account">@""" + html.escape(str(cfg.get("instagram_expected_username") or "umdoislab")) + """</span>
  <form class="logout-form" method="post" action="auth/logout"><button type="submit" class="btn quiet">Sair</button></form>
  </div>
 </header>
 <div class="content">
  <div class="heading"><span class="eyebrow">CENTRAL DE ATENDIMENTO</span>
   <h1>Mensagens e conexão</h1><p>Acompanhe o estado da conexão e as mensagens recebidas.</p>
  </div>
  """ + connection_section + """
  <section class="panel" aria-label="Últimas mensagens">
   <div class="panel-title"><h2>Mensagens recebidas</h2></div>
   <p><small>Últimas 50 mensagens. Nenhuma resposta é enviada ao Instagram.</small></p>
   <div class="table-wrap">
    <table><thead><tr><th>Remetente</th><th>Mensagem</th><th>Estado</th><th>Recebida</th><th>Fila</th><th>Rascunho (sem envio)</th><th>Ações</th></tr></thead><tbody>"""
            + body + """</tbody></table></div></section>
   <div class="note">ⓘ Todo conteúdo permanece sob controle do administrador. Nenhum envio automático está ativado.</div>
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
        self.send_response(status)
        self.send_header("Content-Type", content_type + ("; charset=utf-8" if content_type.startswith("text/") or content_type == "application/json" else ""))
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
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

    def request_business(self):
        return getattr(self, 'route_business', account_registry.PRIMARY_BUSINESS)

    def request_configuration(self):
        return meta_configuration_for_business(self.request_business())

    def meta_csrf_action(self, action):
        business = self.request_business()
        return action if business == account_registry.PRIMARY_BUSINESS else 'meta:' + business + ':' + action

    def account_route(self, method):
        """Authenticate explicit account paths before dispatch; no global selection."""
        self.route_business = account_registry.PRIMARY_BUSINESS
        self.account_prefix = ''
        route = urlsplit(self.path)
        if route.path == '/accounts' and not route.query:
            cfg = settings()
            if not panel_session_authorized(self.headers, cfg):
                self.respond(403, {'error': 'authentication required'})
                return False
            with database() as conn:
                account_registry.ensure_primary(conn, cfg.get('instagram_account_id'))
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
                    self.send_header('Location', account_management.prefix(business) + '/panel')
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
            page = account_management.render(accounts, cfg, self.headers.get('Cookie', ''),
                    lambda business: connection_summary(meta_configuration_for_business(business)), error=invalid)
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
                   else {'/panel/handoff', '/panel/meta/check', '/panel/meta/subscribe', '/auth/logout'})
        if suffix not in allowed and suffix != '/editorial' and not suffix.startswith('/editorial/'):
            self.respond(404, {'error': 'account route not found'})
            return False
        self.route_business = business
        self.account_prefix = account_management.prefix(business)
        self.path = suffix + ('?' + route.query if route.query else '')
        return True

    def do_GET(self):
        if not self.account_route('GET'):
            return
        route = urlsplit(self.path)
        if route.path.startswith("/editorial") and editorial_http.handle(self, "GET", route, self.request_configuration(),
                panel_session_authorized(self.headers, settings()), editorial_store_for_business,
                business_id=self.request_business()):
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
                "publishingEnabled": False
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
                    LOGGER.error(
                        "Meta OAuth callback rejected at stage=%s: %s "
                        "(redirect_authority_match=%s, forwarded_https=%s) transport=%s",
                        callback_stage, str(exc), authority_match, forwarded_https,
                        oauth_meta.cookie_diagnostics(route.query, self.headers.get("Cookie", "")))
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
                "Volte ao painel para configurar a assinatura de mensagens. "
                "Nenhuma mensagem foi enviada.<p><a href='" + account_management.prefix(cfg['business_id']) +
                "/panel'>Voltar ao painel da conta</a></p></body></html>", "text/html")
        if self.path in ("/", "/panel"):
            cfg = self.request_configuration()
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(200, render_login(cfg), "text/html")
            page = render_panel(cfg)
            csrf_check = panel_login.admin_csrf_token(
                self.headers.get("Cookie", ""), cfg.get("panel_password"), self.meta_csrf_action("check"))
            csrf_subscribe = panel_login.admin_csrf_token(
                self.headers.get("Cookie", ""), cfg.get("panel_password"), self.meta_csrf_action("subscribe"))
            if csrf_check:
                controls = '<form method="post" action="panel/meta/check"><input type="hidden" name="csrf" value="' + csrf_check + '"><button>Verificar acesso Meta</button></form>'
                if (connection_summary(cfg)["accountVerified"] and
                        connection_summary(cfg)["webhookEnabled"] and
                        connection_summary(cfg)["webhookConfigReady"]):
                    controls += '<form method="post" action="panel/meta/subscribe"><input type="hidden" name="csrf" value="' + csrf_subscribe + '"><button>Assinar mensagens na Meta</button></form>'
                page = page.replace('<div id="meta-actions"></div>',
                                    '<div id="meta-actions">' + controls + '</div>')
            return self.respond(200, page, "text/html")
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

    def do_POST(self):
        if not self.account_route('POST'):
            return
        route = urlsplit(self.path)
        if route.path.startswith("/editorial") and editorial_http.handle(self, "POST", route, self.request_configuration(),
                panel_session_authorized(self.headers, settings()), editorial_store_for_business,
                business_id=self.request_business()):
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
            candidate = _meta_action_body(self.rfile.read(size))
            if not panel_login.admin_csrf_valid(
                    self.headers.get("Cookie", ""), cfg.get("panel_password"),
                    self.meta_csrf_action(action), candidate):
                return self.respond(403, {"error": "invalid CSRF"})
            if not oauth_meta.is_ready(cfg):
                return self.respond(503, {"error": "OAuth disabled or incomplete"})
            try:
                credential = _meta_credential(self.request_business())
                if credential is None or credential.get("business_id", "umdoislab") != cfg["business_id"]:
                    raise instagram_connection.ConnectionError("No token available")
                if action == "check":
                    # Run the bounded read-only diagnosis alongside identity
                    # verification rather than extending the proxy's wait in series.
                    with ThreadPoolExecutor(max_workers=1) as pool:
                        receiving = pool.submit(instagram_connection.diagnose_receiving, cfg, credential)
                        try:
                            identity = instagram_connection.verify_access(cfg, credential["access_token"])
                        except instagram_connection.ConnectionError:
                            identity = None
                        diagnostics = instagram_connection.safe_diagnostics(receiving.result())
                    if identity is not None:
                        credential.update(identity)
                    credential['receiving_diagnostics'] = diagnostics
                    credential['last_meta_action'] = {'kind': 'check', 'identity_verified': identity is not None}
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
            except (instagram_connection.ConnectionError, oauth_meta.OAuthError,
                    OSError, ValueError):
                return self.respond(422, {"error": "Meta access or subscription not verified"})
            self.send_response(303)
            self.send_header("Location", account_management.prefix(self.request_business()) + "/panel")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
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
                return self.respond(401, render_login(cfg, invalid=True), "text/html")
            try:
                with database() as conn:
                    token = panel_login.create_session(conn, password)
            except (OSError, sqlite3.Error, ValueError):
                return self.respond(503, {"error": "session unavailable"})
            panel_login.successful_attempt(client_id)
            self.send_response(303)
            self.send_header("Location", "../panel")
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
            if not data or data["accountId"] != cfg.get("instagram_account_id") or not set_handoff(data):
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
        if self.path in ("/bridge/handoff", "/bridge/ack", "/bridge/decision", "/bridge/draft"):
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
                if not set_handoff(data):
                    return self.respond(422, {"error": "invalid handoff"})
                return self.respond(200, {"saved": True})
            if self.path == "/bridge/decision":
                decision = evaluate_claim(data)
                if decision is None:
                    return self.respond(409, {"error": "invalid or expired claim"})
                return self.respond(200, {"decision": decision})
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


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    with database():
        pass
    LOGGER.info("Central internal HTTP ready: port=8099 version=%s; public TLS belongs to reverse proxy", APP_VERSION)
    with ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8099"))), Handler) as internal:
        internal.serve_forever()
