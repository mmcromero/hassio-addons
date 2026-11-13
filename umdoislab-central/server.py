#!/usr/bin/env python3
"""Umdoislab Central: Ingress UI + authenticated n8n ingest, SQLite state."""
import hmac
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
        row = db.execute("SELECT status FROM conversations WHERE sender_id=?", (sender,)).fetchone()
    status = row["status"] if row else "none"
    # Pending requires a separate, approved choice flow. Never resume unattended.
    permission = status in ("none", "done")
    return {"allowAutoReply": permission,
            "state": status,
            "reason": "allowed" if permission else "human_active" if status == "human" else "human_pending",
            "needsCustomerChoice": status == "pending"}


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

    def do_POST(self):
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
