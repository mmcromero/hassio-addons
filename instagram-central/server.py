#!/usr/bin/env python3
"""Instagram Central isolated ingress. No Meta send API, n8n calls or WhatsApp access."""
import base64
import hashlib
import html
import hmac
import json
import os
import secrets
from contextlib import contextmanager
from datetime import timedelta
import sqlite3
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from panel_actions import parse_action, token_for
from policy import prepare_decision
import oauth_meta
import panel_login
from urllib.parse import parse_qs, urlsplit

DATA_DIR = Path(os.environ.get("INSTAGRAM_DATA_DIR", "/data"))
DB_PATH = DATA_DIR / "instagram.sqlite3"
OPTIONS_PATH = Path(os.environ.get("INSTAGRAM_OPTIONS", "/data/options.json"))
MAX_BODY = 256 * 1024


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


def list_pending(limit=50):
    """Read-only queue overview; does NOT reserve messages."""
    with database() as conn:
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_id,
            i.message_text, i.received_at,
            COALESCE(h.state, 'bot') AS handoff_state
            FROM inbound i LEFT JOIN handoff h
              ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
            WHERE i.processed_at IS NULL
            ORDER BY i.received_at, i.rowid LIMIT ?""", (min(max(int(limit), 1), 50),)).fetchall()
    return [{"channel": "instagram", "accountId": r[0],
             "senderId": r[1], "messageId": r[2], "messageText": r[3],
             "receivedAt": r[4], "handoffState": r[5]} for r in rows]


def claim_message(lease_seconds=120):
    """Reserve exactly one message atomically; no external request or send."""
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
          WHERE i.processed_at IS NULL AND COALESCE(h.state, 'bot') = 'bot'
            AND (i.claim_until IS NULL OR i.claim_until <= ?)
          ORDER BY i.received_at, i.rowid LIMIT 1""", (now_iso,)).fetchone()
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


def normalized_messages(payload, account_id=None):
    """Only normal text messages. Ignore echoes, unsupported media and malformed objects."""
    if not isinstance(payload, dict) or payload.get("object") != "instagram":
        return []
    found = []
    entries = payload.get("entry")
    if not isinstance(entries, list):
        return found
    for entry in entries[:100]:
        if not isinstance(entry, dict):
            continue
        for ev in entry.get("messaging", [])[:100] if isinstance(entry.get("messaging"), list) else []:
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
            if not isinstance(account_id, str) or not account_id or recipient_id != account_id:
                continue  # reject events from other Instagram business accounts
            if sender_id == recipient_id:
                continue  # never treat business-originated content as a customer request
            if not all(isinstance(v, str) and 1 <= len(v) <= 160 for v in (sender_id, recipient_id, mid)):
                continue
            if not isinstance(text, str) or not 1 <= len(text.strip()) <= 2000:
                continue
            found.append((recipient_id, sender_id, mid, text.strip()))
    return found


def persist(body, account_id=None):
    try:
        payload = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return None
    messages = normalized_messages(payload, account_id)
    inserted = 0
    with database() as conn:
        for rid, sid, mid, msg in messages:
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
        + notice + fields +
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


def render_panel(cfg=None):
    """Escaped local-only panel, with no Meta send or browser scripts."""
    with database() as conn:
        rows = conn.execute("""SELECT i.recipient_id, i.sender_id, i.message_text,
          i.received_at, i.processed_at, COALESCE(h.state, 'bot'),
          COALESCE(d.draft_text, ''), COALESCE(d.status, '')
          FROM inbound i LEFT JOIN handoff h
            ON i.recipient_id=h.recipient_id AND i.sender_id=h.sender_id
          LEFT JOIN drafts d ON i.recipient_id=d.recipient_id
            AND i.sender_id=d.sender_id AND i.message_id=d.message_id
          ORDER BY i.received_at DESC, i.rowid DESC LIMIT 50""").fetchall()
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
                       "</td>" for v in cells) + "<td>" + "".join(actions) + "</td></tr>")
    body = "".join(entries) if entries else '<tr><td colspan="7">Nenhuma mensagem recebida.</td></tr>'
    return ("""<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Central Instagram — laboratório</title>
<style>body{font:16px system-ui;margin:2rem;max-width:1100px;color:#182334}
table{border-collapse:collapse;width:100%}th,td{padding:.7rem;border-bottom:1px solid #ddd;text-align:left;overflow-wrap:anywhere}
th{background:#f1f4f7}small{color:#58657a}form{display:inline-block;margin:3px}button{padding:.4rem .6rem;cursor:pointer}</style></head><body>
<h1>Central Instagram</h1><p>Laboratório: ações alteram somente o estado local.</p>
<form method="post" action="auth/logout"><button type="submit">Sair</button></form>
<small>Últimas 50 mensagens. Não envia respostas ao Instagram.</small>
<table><thead><tr><th>Remetente</th><th>Mensagem</th><th>Estado</th><th>Recebida</th><th>Fila</th><th>Rascunho (sem envio)</th><th>Ações</th></tr></thead><tbody>"""
            + body + "</tbody></table></body></html>")


class Handler(BaseHTTPRequestHandler):
    def respond(self, status, body, content_type="application/json"):
        raw = body.encode("utf-8") if isinstance(body, str) else json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", content_type + "; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        if content_type == "text/html":
            self.send_header("Content-Security-Policy",
                             "default-src 'none'; style-src 'unsafe-inline'; "
                             "form-action 'self'; base-uri 'none'; object-src 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def do_GET(self):
        route = urlsplit(self.path)
        if route.path == "/oauth/meta/status" and not route.query:
            cfg = settings()
            if not panel_authorized(self.headers, cfg):
                return self.respond(401, {"error": "authentication required"})
            return self.respond(200, {
                "enabled": oauth_meta.is_ready(cfg),
                "credentialStored": oauth_meta.token_exists(DATA_DIR),
                "connectionVerified": False,
                "sendingEnabled": False
            })
        if route.path == "/oauth/meta/start" and not route.query:
            cfg = settings()
            if not panel_authorized(self.headers, cfg):
                return self.respond(401, {"error": "authentication required"})
            try:
                with database() as conn:
                    url, cookie = oauth_meta.start(conn, cfg)
            except oauth_meta.OAuthError:
                return self.respond(503, {"error": "OAuth disabled or incomplete"})
            self.send_response(302)
            self.send_header("Location", url)
            self.send_header("Set-Cookie", cookie)
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if route.path == "/oauth/meta/callback":
            cfg = settings()
            if not oauth_meta.is_ready(cfg):
                return self.respond(503, {"error": "OAuth disabled or incomplete"})
            try:
                state, code = oauth_meta.parse_callback(
                    route.query, self.headers.get("Cookie", ""))
                with database() as conn:
                    oauth_meta.consume_state(conn, state)
                credential = oauth_meta.exchange_code(code, cfg)
                oauth_meta.store_token(DATA_DIR, credential)
            except oauth_meta.OAuthError:
                return self.respond(400, {"error": "OAuth refused or expired"})
            except Exception:
                return self.respond(502, {"error": "OAuth unavailable"})
            # No token, authorization code, client ID, or secret is reflected to the client.
            return self.respond(200, "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
                "<title>Instagram</title><body>Autorização recebida e armazenada. "
                "Mensagens e automações continuam desativadas.</body></html>", "text/html")
        if self.path in ("/", "/panel"):
            cfg = settings()
            if not panel_session_authorized(self.headers, cfg):
                return self.respond(200, render_login(cfg), "text/html")
            return self.respond(200, render_panel(cfg), "text/html")
        if self.path == "/bridge/pending":
            cfg = settings()
            if not bridge_authorized(self.headers, cfg):
                return self.respond(403, {"error": "access denied"})
            return self.respond(200, {"messages": list_pending()})
        if self.path == "/health":
            return self.respond(200, {"ok": True, "service": "instagram-central", "mode": "isolated"})
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
            self.send_header("Location", "../panel")
            self.send_header("Set-Cookie", panel_login.clear_cookie_header(
                secure=_external_https(self.headers)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/panel/handoff":
            cfg = settings()
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
            if not data or not set_handoff(data):
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
            return self.respond(200, {"message": claim_message()})
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
            return self.respond(503, {"error": "webhook disabled"})
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            return self.respond(400, {"error": "invalid length"})
        if size <= 0 or size > MAX_BODY:
            return self.respond(413, {"error": "size not allowed"})
        body = self.rfile.read(size)
        if not signature_valid(body, self.headers.get("X-Hub-Signature-256"), secret):
            return self.respond(403, {"error": "invalid signature"})
        count = persist(body, account_id)
        if count is None:
            return self.respond(400, {"error": "invalid JSON"})
        return self.respond(200, {"accepted": True, "new_text_messages": count})

    def log_message(self, fmt, *args):
        # Do not log client identifiers or message contents.
        return


if __name__ == "__main__":
    with database():
        pass
    ThreadingHTTPServer(("0.0.0.0", int(os.environ.get("PORT", "8099"))), Handler).serve_forever()
