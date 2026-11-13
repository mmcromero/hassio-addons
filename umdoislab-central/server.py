#!/usr/bin/env python3
"""Umdoislab Central: Ingress UI + authenticated n8n ingest, SQLite state."""
import hmac
import hashlib
import json
import os
import re
import sqlite3
import threading
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(os.environ.get("CENTRAL_DATA_DIR", "/data"))
BASE.mkdir(parents=True, exist_ok=True)
DB = BASE / "central.sqlite3"
OPTIONS = Path(os.environ.get("CENTRAL_OPTIONS", "/data/options.json"))
UI = Path(__file__).parent / "static" / "index.html"
SUPERVISOR_IP = os.environ.get("CENTRAL_INGRESS_IP", "172.30.32.2")
LOCK = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def options():
    try:
        return json.loads(OPTIONS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def valid_sender_for_send(sender):
    # Apenas chats individuais com número explícito, nunca grupos, status ou @lid.
    return bool(re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net", sender))


def connect():
    db = sqlite3.connect(DB, timeout=10)
    db.row_factory = sqlite3.Row
    return db


def init():
    with connect() as db:
        db.execute("""CREATE TABLE IF NOT EXISTS conversations(
          sender_id TEXT PRIMARY KEY, sender_name TEXT NOT NULL DEFAULT '',
          subject TEXT NOT NULL DEFAULT '', summary TEXT NOT NULL DEFAULT '',
          last_message TEXT NOT NULL DEFAULT '', last_message_id TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','human','done')),
          updated_at TEXT NOT NULL, created_at TEXT NOT NULL,
          last_reply TEXT NOT NULL DEFAULT '', last_reply_at TEXT
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS replies(
          request_id TEXT PRIMARY KEY, sender_id TEXT NOT NULL,
          created_at TEXT NOT NULL, outcome TEXT NOT NULL, detail TEXT NOT NULL DEFAULT ''
        )""")
        for col, ddl in (
            ("choice_state", "TEXT NOT NULL DEFAULT 'idle'"),
            ("choice_message_id", "TEXT NOT NULL DEFAULT ''"),
            ("last_bot_text", "TEXT NOT NULL DEFAULT ''"),
            ("bot_repeat_count", "INTEGER NOT NULL DEFAULT 0"),
            ("fallback_count", "INTEGER NOT NULL DEFAULT 0"),
        ):
            names = {row[1] for row in db.execute("PRAGMA table_info(conversations)")}
            if col not in names:
                db.execute("ALTER TABLE conversations ADD COLUMN " + col + " " + ddl)
        db.execute("""CREATE TABLE IF NOT EXISTS inbound_ids(
            sender_id TEXT NOT NULL, message_id TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(sender_id,message_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS bot_guard(
            sender_id TEXT PRIMARY KEY,last_text TEXT NOT NULL DEFAULT '',
            fallback_count INTEGER NOT NULL DEFAULT 0, updated_at TEXT NOT NULL
        )""")


# Textos de protocolo: não permitir que o n8n substitua essas mensagens.
CHOICE_PROMPT = ("Ainda não conseguimos iniciar o atendimento pessoal. "
                 "Você prefere aguardar ou quer continuar com o atendimento automático? "
                 "Responda 1 para aguardar ou 2 para continuar.")
HANDOFF_PROMPT = ("Não consegui resolver sua solicitação agora. "
                  "Vou encaminhar seu atendimento para uma pessoa da Umdoislab. "
                  "Assim que possível, alguém entra em contato. 😊")


def normalized(text):
    import unicodedata
    value = unicodedata.normalize("NFD", str(text or "").lower())
    return re.sub(r"\s+", " ", "".join(c for c in value if unicodedata.category(c) != "Mn")).strip()


def classify_choice(message):
    """Strict deterministic choice; never treat a generic 'sim' as opt-in."""
    msg = re.sub(r"\s+", " ", re.sub(r"[^a-z0-9 ]+", " ", normalized(message))).strip()
    if msg.startswith("ah "):
        msg = msg[3:]
    if msg in ("1", "aguardar", "vou aguardar", "prefiro aguardar", "esperar",
               "vou esperar", "quero aguardar", "atendimento humano", "pessoa"):
        return "wait"
    if msg in ("2", "continuar", "continuar com robo", "continuar com o robo",
               "atendimento automatico", "quero continuar com o automatico",
               "quero continuar com o robo", "voltar ao robo", "robo"):
        return "resume"
    if msg in ("ok", "obrigado", "obrigada", "obg", "blz", "ok obrigado", "ok obrigada",
               "tudo bem", "beleza", "certo", "entendi", "ta bom", "valeu"):
        return "ack"
    return "other"


def valid_event(ev):
    return (ev.get("instance") == "umdoislab"
            and ev.get("isClientMessage") is True
            and ev.get("isGroup") is False
            and valid_sender_for_send(str(ev.get("senderId") or ""))
            and isinstance(ev.get("messageId"), str)
            and 1 <= len(ev["messageId"]) <= 160)


def process_inbound(ev):
    """Atomic finite-state processing; returns only bounded actions.

    Intentionally no LLM inference here. Explicit opt-in is a strict command.
    Multiple deliveries of one incoming event return 'ignore'.
    """
    if not isinstance(ev, dict) or not valid_event(ev):
        return None
    sender, mid = ev["senderId"], ev["messageId"]
    ts = now()
    message = str(ev.get("messageText") or "")[:500]
    name = str(ev.get("senderName") or "Contato")[:100]
    subject = str(ev.get("category") or "Atendimento")[:100]
    summary = str(ev.get("summary") or "")[:500]
    handoff = ev.get("handoffRequested") is True
    with LOCK, connect() as db:
        seen = db.execute("SELECT 1 FROM inbound_ids WHERE sender_id=? AND message_id=?",
                          (sender, mid)).fetchone()
        if seen:
            return {"action": "ignore", "state": "duplicate", "messageId": mid}
        old = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
        guard = db.execute("SELECT fallback_count FROM bot_guard WHERE sender_id=?", (sender,)).fetchone()
        # Two vague requests in sequence become a human handoff, not a generic answer loop.
        if old is None and not handoff and subject == "outros" and guard and guard["fallback_count"] >= 1:
            handoff = True
        action = "auto"
        if old is None:
            if handoff:
                db.execute("""INSERT INTO conversations(sender_id,sender_name,subject,summary,last_message,
                          last_message_id,status,updated_at,created_at,choice_state)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""",
                           (sender, name, subject, summary, message, mid, "pending", ts, ts, "idle"))
                action = "handoff"
        else:
            status, choice = old["status"], old["choice_state"]
            if status == "done" and handoff:
                db.execute("""UPDATE conversations SET status='pending', choice_state='idle',
                     last_bot_text='', bot_repeat_count=0, fallback_count=0,
                     choice_message_id='' WHERE sender_id=?""", (sender,))
                status, choice, action = "pending", "idle", "handoff"
            elif status == "done":
                action = "auto"
            elif status == "human":
                action = "silent"
            elif handoff:
                # Already pending: don't repeat transfer notification.
                action = "silent"
            elif choice == "opted_in":
                action = "auto"
            elif choice == "exhausted":
                action = "silent"
            else:
                classification = classify_choice(message)
                if classification == "ack" or classification == "wait":
                    action = "silent"
                    if classification == "wait":
                        db.execute("UPDATE conversations SET choice_state='waiting' WHERE sender_id=?", (sender,))
                elif classification == "resume" and choice in ("offered", "waiting"):
                    db.execute("""UPDATE conversations SET choice_state='opted_in',
                                  last_bot_text='',bot_repeat_count=0,fallback_count=0
                                  WHERE sender_id=?""", (sender,))
                    action = "resume"
                elif choice == "idle":
                    db.execute("""UPDATE conversations SET choice_state='offered',
                                 choice_message_id=? WHERE sender_id=?""", (mid, sender))
                    action = "offer_choice"
                else:
                    # No second offer in this pending episode: prevents a prompt loop.
                    action = "silent"
            db.execute("""UPDATE conversations SET sender_name=?,subject=?,summary=?,
                      last_message=?,last_message_id=?,updated_at=? WHERE sender_id=?""",
                       (name,subject,summary or old["summary"],message,mid,ts,sender))
        db.execute("INSERT INTO inbound_ids(sender_id,message_id,created_at) VALUES(?,?,?)",
                   (sender,mid,ts))
    return {"action": action, "state": routing_decision("umdoislab",sender)["state"],
            "messageId": mid, "senderId": sender, "instance": "umdoislab"}


def store_event(ev):
    if ev.get("instance") != "umdoislab" or ev.get("isClientMessage") is not True or ev.get("isGroup") is True:
        return False
    sender = str(ev.get("senderId") or "")[:160]
    mid = str(ev.get("messageId") or "")[:160]
    if not sender or not mid or not re.fullmatch(r"[0-9A-Za-z_.:@+-]+", sender):
        return False
    name = str(ev.get("senderName") or "Contato")[:100]
    subject = str(ev.get("category") or "Atendimento")[:100]
    summary = str(ev.get("summary") or "")[:500]
    message = str(ev.get("messageText") or "")[:500]
    with LOCK, connect() as db:
        old = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
        if old is None and ev.get("handoffRequested") is not True:
            return False  # no ticket without explicit human handoff
        if old and old["last_message_id"] == mid:
            return True
        ts = now()
        if old:
            status = "pending" if old["status"] == "done" and ev.get("handoffRequested") is True else old["status"]
            db.execute("""UPDATE conversations SET sender_name=?, subject=?, summary=?, last_message=?,
                      last_message_id=?, status=?, updated_at=? WHERE sender_id=?""",
                       (name, subject, summary or old["summary"], message, mid, status, ts, sender))
        else:
            db.execute("""INSERT INTO conversations(sender_id,sender_name,subject,summary,last_message,
                      last_message_id,status,updated_at,created_at) VALUES(?,?,?,?,?,?,?,?,?)""",
                       (sender, name, subject, summary, message, mid, "pending", ts, ts))
    return True


def routing_decision(instance, sender):
    """Read authoritative state for n8n. No state lookup error may imply permission."""
    if instance != "umdoislab" or not valid_sender_for_send(sender):
        return None
    with LOCK, connect() as db:
        row = db.execute("SELECT status,choice_state FROM conversations WHERE sender_id=?", (sender,)).fetchone()
    status = row["status"] if row else "none"
    choice = row["choice_state"] if row else "idle"
    permission = status in ("none", "done") or (status == "pending" and choice == "opted_in")
    return {"allowAutoReply": permission, "state": status, "choiceState": choice,
            "reason": "allowed" if permission else "human_active" if status == "human" else "human_pending",
            "needsCustomerChoice": status == "pending" and choice == "idle"}


def public_row(r, detail=False):
    out = dict(r)
    if not detail:
        out.pop("sender_id", None)  # list uses opaque stable id from indexed sequence
    return out


class Handler(BaseHTTPRequestHandler):
    server_version = "UmdoislabCentral/0.1"
    def log_message(self, fmt, *args):
        # No access-log body/headers/token/phone
        print("central-request", self.command, self.path.split("?")[0].split("/")[1:2], flush=True)

    def respond(self, status, data):
        raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "default-src 'none'")
        self.end_headers()
        self.wfile.write(raw)

    def ingress(self):
        return self.client_address[0] == SUPERVISOR_IP

    def bridge(self):
        secret = str(options().get("bridge_secret") or "")
        auth = self.headers.get("Authorization", "")
        return len(secret) >= 24 and hmac.compare_digest(auth, "Bearer " + secret)

    def read_json(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                return None
            data = json.loads(self.rfile.read(length))
            return data if isinstance(data, dict) else None
        except (ValueError, UnicodeError):
            return None

    def do_GET(self):
        if not self.ingress():
            return self.respond(403, {"error": "Somente Ingress"})
        if self.path in ("/", "/index.html"):
            raw = UI.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Security-Policy",
                "default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; "
                "connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'self'")
            self.end_headers()
            return self.wfile.write(raw)
        if self.path == "/api/conversations":
            with connect() as db:
                # Nunca ocultar pendências por causa de muitos atendimentos resolvidos.
                active = db.execute("""SELECT sender_id,sender_name,subject,summary,last_message,status,
                       updated_at,created_at,last_reply_at FROM conversations
                       WHERE status != 'done' ORDER BY updated_at DESC""").fetchall()
                resolved = db.execute("""SELECT sender_id,sender_name,subject,summary,last_message,status,
                       updated_at,created_at,last_reply_at FROM conversations
                       WHERE status = 'done' ORDER BY updated_at DESC LIMIT 50""").fetchall()
                rows = sorted([*active, *resolved], key=lambda item: item["updated_at"], reverse=True)
            return self.respond(200, {"items": [dict(r) for r in rows]})
        if self.path.startswith("/api/conversations/"):
            sender = self.path.removeprefix("/api/conversations/")
            from urllib.parse import unquote
            sender = unquote(sender)
            with connect() as db:
                row = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
            return self.respond(200, {"item": dict(row)}) if row else self.respond(404, {"error": "Não encontrado"})
        return self.respond(404, {"error": "Não encontrado"})

    def send_automated(self, data):
        """Safe outbound dispatch: atomic with operator actions, dedupe per inbound ID."""
        sender = data.get("senderId")
        instance = data.get("instance")
        message_id = data.get("messageId")
        kind = data.get("kind", "normal")
        if not all(isinstance(x, str) for x in (sender, instance, message_id)):
            return self.respond(422, {"error": "Campos obrigatórios ausentes"})
        if kind not in ("normal", "fallback", "handoff", "choice"):
            return self.respond(422, {"error": "Tipo de envio inválido"})
        if not 1 <= len(message_id) <= 160:
            return self.respond(422, {"error": "messageId inválido"})
        cfg = options()
        if sender != str(cfg.get("auto_test_sender") or "") or not valid_sender_for_send(sender):
            return self.respond(403, {"error": "Fora do contato de teste autorizado"})
        key = str(cfg.get("evolution_api_key") or "")
        base = str(cfg.get("evolution_url") or "").rstrip("/")
        configured_instance = str(cfg.get("evolution_instance") or "")
        if not key or not base.startswith(("http://", "https://")) or not re.fullmatch(r"[A-Za-z0-9_-]+", configured_instance):
            return self.respond(503, {"error": "Evolution API não configurada"})
        if instance != configured_instance:
            return self.respond(422, {"error": "Instância inválida"})
        message = CHOICE_PROMPT if kind == "choice" else HANDOFF_PROMPT if kind == "handoff" else data.get("text")
        if not isinstance(message, str) or not 0 < len(message.strip()) <= 1500:
            return self.respond(422, {"error": "Texto inválido"})
        message = message.strip()
        delivery_key = "auto-" + hashlib.sha256(
            (sender + "|" + message_id + "|" + kind).encode()).hexdigest()
        with LOCK:
            decision = routing_decision(instance, sender)
            with connect() as db:
                row = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
                guard = db.execute("SELECT * FROM bot_guard WHERE sender_id=?", (sender,)).fetchone()
                if kind == "choice":
                    allowed = bool(row and row["status"] == "pending"
                        and row["choice_state"] == "offered"
                        and row["choice_message_id"] == message_id)
                elif kind == "handoff":
                    allowed = bool(row and row["status"] == "pending"
                        and row["choice_state"] == "idle"
                        and row["last_message_id"] == message_id)
                else:
                    allowed = decision is not None and decision["allowAutoReply"]
                    if row and row["status"] == "pending":
                        allowed = allowed and row["choice_state"] == "opted_in"
                    if allowed and ((guard and normalized(guard["last_text"]) == normalized(message))
                                    or (row and normalized(row["last_bot_text"]) == normalized(message))):
                        if row:
                            db.execute("""UPDATE conversations SET choice_state='exhausted'
                                          WHERE sender_id=? AND status='pending'""", (sender,))
                        return self.respond(409, {"error": "Resposta repetida bloqueada; atendimento humano precisa avaliar",
                                                  "state": "loop_blocked"})
                    if allowed and kind == "fallback" and row and row["fallback_count"] >= 1:
                        db.execute("""UPDATE conversations SET choice_state='exhausted'
                                      WHERE sender_id=? AND status='pending'""", (sender,))
                        return self.respond(409, {"error": "Limite de incompreensão; atendimento humano mantido",
                                                  "state": "fallback_limit"})
                if not allowed:
                    return self.respond(409, {"error": "Estado não autoriza envio automático",
                                              "state": decision["state"] if decision else "invalid"})
                if db.execute("SELECT 1 FROM replies WHERE request_id=?", (delivery_key,)).fetchone():
                    return self.respond(409, {"error": "Mensagem já solicitada; não reenviar"})
                db.execute("INSERT INTO replies VALUES(?,?,?,?,?)",
                           (delivery_key, sender, now(), "requested", kind))
            url = base + "/message/sendText/" + configured_instance
            payload = json.dumps({"number":sender.split("@")[0], "text":message}).encode("utf-8")
            request = urllib.request.Request(url, data=payload,
                headers={"Content-Type":"application/json", "apikey":key}, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=12) as response:
                    response.read(8192)
                    if not 200 <= response.status < 300:
                        raise ValueError("Evolution rejected request")
                with connect() as db:
                    db.execute("UPDATE replies SET outcome='accepted' WHERE request_id=?", (delivery_key,))
                    if kind in ("normal", "fallback"):
                        db.execute("""INSERT INTO bot_guard(sender_id,last_text,fallback_count,updated_at)
                                      VALUES(?,?,?,?)
                                      ON CONFLICT(sender_id) DO UPDATE SET
                                        last_text=excluded.last_text,
                                        fallback_count=CASE WHEN excluded.fallback_count=0 THEN 0 ELSE bot_guard.fallback_count+1 END,
                                        updated_at=excluded.updated_at""",
                                   (sender, message[:1500], 1 if kind == "fallback" else 0, now()))
                        if row:
                            db.execute("""UPDATE conversations
                                          SET last_bot_text=?,fallback_count=fallback_count+?
                                          WHERE sender_id=?""",
                                       (message[:1500], 1 if kind == "fallback" else 0, sender))
                return self.respond(200, {"ok":True, "delivery":"accepted_not_confirmed", "kind":kind})
            except Exception:
                with connect() as db:
                    db.execute("UPDATE replies SET outcome='uncertain' WHERE request_id=?", (delivery_key,))
                return self.respond(502, {"error":"Envio incerto. Não repetir sem conferir WhatsApp"})

    def do_POST(self):
        if self.path == "/bridge/inbound":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            ev = self.read_json()
            if ev is None:
                return self.respond(400, {"error": "JSON inválido"})
            result = process_inbound(ev)
            if result is None:
                return self.respond(422, {"error": "Evento inválido ou destino não suportado"})
            return self.respond(200, result)
        if self.path == "/bridge/send-auto":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            payload = self.read_json()
            if payload is None:
                return self.respond(400, {"error": "JSON inválido"})
            return self.send_automated(payload)
        if self.path == "/bridge/decision":
            # This gate is checked before all automatic outgoing messages.
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            request = self.read_json()
            if request is None:
                return self.respond(400, {"error": "JSON inválido"})
            instance = request.get("instance")
            sender = request.get("senderId")
            if not isinstance(instance, str) or not isinstance(sender, str):
                return self.respond(422, {"error": "Instância e destinatário obrigatórios"})
            decision = routing_decision(instance, sender)
            if decision is None:
                return self.respond(422, {"error": "Instância ou destinatário incompatível"})
            return self.respond(200, decision)
        if self.path == "/bridge/events":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            event = self.read_json()
            if event is None:
                return self.respond(400, {"error": "JSON inválido"})
            return self.respond(200, {"recorded": store_event(event)})
        if not self.ingress() or self.headers.get("X-Requested-With") != "UmdoislabCentral":
            return self.respond(403, {"error": "Acesso negado"})
        from urllib.parse import unquote
        match = re.fullmatch(r"/api/conversations/([^/]+)/(assume|resolve|reopen|reply)", self.path)
        if not match:
            return self.respond(404, {"error": "Não encontrado"})
        sender, action = unquote(match.group(1)), match.group(2)
        data = self.read_json()
        if data is None:
            return self.respond(400, {"error": "JSON inválido"})
        # Validar configuração/destino ANTES de reservar a chave de idempotência.
        # Uma configuração ausente não pode impedir uma futura tentativa corrigida.
        if action == "reply":
            cfg = options()
            api_key = str(cfg.get("evolution_api_key") or "")
            endpoint = str(cfg.get("evolution_url") or "").rstrip("/")
            instance = str(cfg.get("evolution_instance") or "")
            if not api_key or not endpoint.startswith(("http://", "https://")) or not re.fullmatch(r"[A-Za-z0-9_-]+", instance):
                return self.respond(503, {"error": "Evolution API não configurada"})
            if not valid_sender_for_send(sender):
                return self.respond(422, {"error": "Identificador do contato incompatível com envio seguro; confira o JID recebido"})
        with LOCK, connect() as db:
            existing = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
            if not existing:
                return self.respond(404, {"error": "Conversa não encontrada"})
            if action != "reply":
                status = {"assume": "human", "resolve": "done", "reopen": "pending"}[action]
                db.execute("UPDATE conversations SET status=?, updated_at=? WHERE sender_id=?",
                           (status, now(), sender))
                return self.respond(200, {"ok": True, "status": status})
            message = str(data.get("text") or "").strip()
            req_id = str(data.get("requestId") or "")
            if not message or len(message) > 1500 or not re.fullmatch(r"[a-f0-9-]{36}", req_id):
                return self.respond(400, {"error": "Texto ou identificador inválido"})
            if existing["status"] == "done":
                return self.respond(409, {"error": "Reabra antes de responder"})
            duplicate = db.execute("SELECT outcome FROM replies WHERE request_id=?", (req_id,)).fetchone()
            if duplicate:
                return self.respond(409, {"error": "Envio já solicitado; consulte a conversa antes de repetir"})
            db.execute("INSERT INTO replies VALUES(?,?,?,?,?)",(req_id,sender,now(),"requested",""))
            # Assumir antes do envio: se a rede demorar, o robô já fica bloqueado.
            # Em resultado incerto, manter estado humano até decisão do responsável.
            db.execute("UPDATE conversations SET status='human', updated_at=? WHERE sender_id=?",
                       (now(), sender))
        url = endpoint + "/message/sendText/" + instance
        body = json.dumps({"number":sender.split("@")[0], "text":message}).encode()
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type":"application/json","apikey":api_key}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as res:
                payload = res.read(8192)
                if not 200 <= res.status < 300:
                    raise urllib.error.HTTPError(url,res.status,"HTTP failure",{},None)
            # HTTP success = request accepted by Evolution, NOT delivery proof
            with LOCK, connect() as db:
                db.execute("UPDATE replies SET outcome='accepted' WHERE request_id=?", (req_id,))
                db.execute("""UPDATE conversations SET last_reply=?,last_reply_at=?,status='human',
                              updated_at=? WHERE sender_id=?""",(message[:1500],now(),now(),sender))
            return self.respond(200, {"ok":True,"detail":"Evolution API aceitou o envio; entrega não confirmada"})
        except Exception:
            with LOCK, connect() as db:
                db.execute("UPDATE replies SET outcome='uncertain' WHERE request_id=?", (req_id,))
            return self.respond(502, {"error":"Envio sem confirmação. Confira o WhatsApp antes de tentar novamente."})


if __name__ == "__main__":
    init()
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
