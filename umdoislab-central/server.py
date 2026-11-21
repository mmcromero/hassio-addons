#!/usr/bin/env python3
"""Umdoislab Central: Ingress UI + authenticated n8n ingest, SQLite state."""
import hashlib
import json
import os
import re
import sqlite3
import threading
import urllib.error
import urllib.request
import uuid
from accounts import (Account, AccountRegistry, DEFAULT_ACCOUNT_ID, database_path,
                      CHOICE_PROMPT, HUMAN_OFFER_PROMPT, HANDOFF_PROMPT)
from evolution_adapter import normalize_evolution
from n8n_outbox import ensure_outbox, put as queue_decision, cancel_for_manual
from outgoing_verification import verify_outgoing
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

BASE = Path(os.environ.get("CENTRAL_DATA_DIR", "/data"))
BASE.mkdir(parents=True, exist_ok=True)
OPTIONS = Path(os.environ.get("CENTRAL_OPTIONS", "/data/options.json"))
UI = Path(__file__).parent / "static" / "index.html"
SUPERVISOR_IP = os.environ.get("CENTRAL_INGRESS_IP", "172.30.32.2")
LOCK = threading.RLock()


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def options():
    try:
        data = json.loads(OPTIONS.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


# Registro de produção contém somente Umdoislab. Injeção explícita para testes;
# não existe configuração HTTP/Ingress para provisionar outra conta.
ACCOUNTS = None


def account_registry():
    if ACCOUNTS is not None:
        return ACCOUNTS
    raw = options()
    cfg = {key: raw[key] for key in (
        "bridge_secret", "evolution_webhook_secret", "evolution_url",
        "evolution_instance", "evolution_api_key", "auto_test_sender") if key in raw}
    # Nome/telefone não definem o identificador persistente acct_001.
    if cfg.get("evolution_instance", "umdoislab") != "umdoislab":
        return AccountRegistry([])  # configuração divergente nunca muda o destino
    account = Account(DEFAULT_ACCOUNT_ID, "umdoislab", "Umdoislab", "business_001",
                      database_path(BASE, DEFAULT_ACCOUNT_ID), cfg, lock=LOCK)
    return AccountRegistry([account])


def default_account():
    account = account_registry().resolve(account_id=DEFAULT_ACCOUNT_ID)
    if account is None:
        raise ValueError("Conta padrão indisponível")
    return account


def event_account(ev, account=None):
    if not isinstance(ev, dict):
        return None
    resolved = account or account_registry().resolve(instance=ev.get("instance"))
    if (resolved is None or not resolved.enabled or ev.get("instance") != resolved.instance or
            ("account_id" in ev and ev["account_id"] != resolved.account_id)):
        return None
    return resolved


# Políticas são armazenadas na Central, nunca embutidas no workflow.
POLICY_MODES = ("tests", "new", "all")


def canonical_number(raw):
    value = str(raw or "").strip()
    if value.endswith("@s.whatsapp.net"):
        value = value[:-len("@s.whatsapp.net")]
    # Aceitar número colado com +, espaços, parênteses ou hífen.
    if not re.fullmatch(r"[+0-9()\s-]+", value):
        return None
    value = re.sub(r"[^0-9]", "", value)
    if not re.fullmatch(r"[0-9]{10,15}", value):
        return None
    return value + "@s.whatsapp.net"


def get_policy(db):
    rows = db.execute("SELECT key,value FROM policy_settings").fetchall()
    values = {r["key"]: r["value"] for r in rows}
    return {"mode": values.get("mode", "tests"),
            "baseline_ready": values.get("baseline_ready", "0") == "1",
            "baseline_count": int(values.get("baseline_count", "0")),
            "baseline_at": values.get("baseline_at", "")}


def contact_policy(db, sender):
    if not valid_sender_for_send(sender):
        return {"allowed": False, "reason": "invalid_sender"}
    exclusion = db.execute(
        "SELECT 1 FROM contact_rules WHERE sender_id=? AND category='excluded'", (sender,)).fetchone()
    if exclusion:
        return {"allowed": False, "reason": "excluded"}
    policy = get_policy(db)
    test = db.execute(
        "SELECT 1 FROM contact_rules WHERE sender_id=? AND category='test'", (sender,)).fetchone()
    if policy["mode"] == "tests":
        # Retrocompatibilidade de um único remetente no add-on, enquanto o painel migra.
        old_test = str(db.account.config.get("auto_test_sender") or "")
        return {"allowed": bool(test or sender == old_test), "reason": "test" if test or sender == old_test else "not_in_test_list"}
    if policy["mode"] == "all":
        return {"allowed": True, "reason": "all"}
    if not policy["baseline_ready"]:
        return {"allowed": False, "reason": "baseline_unavailable"}
    known = db.execute("SELECT 1 FROM known_contacts WHERE sender_id=?", (sender,)).fetchone()
    return {"allowed": not bool(known), "reason": "known_contact" if known else "new_contact"}


def update_contacts(category, submitted, account=None):
    account = account or default_account()
    if category not in ("test", "excluded") or not isinstance(submitted, list) or len(submitted) > 300:
        return None
    unique = []
    for item in submitted:
        number = canonical_number(item)
        if number is None:
            return None
        if number not in unique:
            unique.append(number)
    with account.lock, connect(account) as db:
        for number in unique:
            db.execute("INSERT OR IGNORE INTO contact_rules(sender_id,category) VALUES(?,?)",
                       (number,category))
    return unique


def historical_baseline(account=None):
    """Fetch contacts and chats BEFORE enabling 'new'. No guesses on API failures."""
    cfg = (account or default_account()).config
    base = str(cfg.get("evolution_url") or "").rstrip("/")
    key = str(cfg.get("evolution_api_key") or "")
    instance = str(cfg.get("evolution_instance") or "")
    if not key or not base.startswith(("http://", "https://")) or not re.fullmatch(r"[A-Za-z0-9_-]+", instance):
        raise ValueError("Evolution não configurada")
    found = set()
    for endpoint in ("findContacts", "findChats"):
        url = base + "/chat/" + endpoint + "/" + instance
        request = urllib.request.Request(url,data=b'{"where":{}}',
            headers={"Content-Type":"application/json","apikey":key},method="POST")
        with urllib.request.urlopen(request,timeout=20) as response:
            if not 200 <= response.status < 300:
                raise ValueError("Consulta à Evolution falhou")
            result = json.loads(response.read(5_000_000))
        # API pode responder lista ou objeto com múltiplos formatos; sem confirmar
        # lista completa não ativamos os contatos novos.
        if not isinstance(result,list):
            raise ValueError("Resposta de contatos/chats incompatível")
        if len(result) >= 10000:
            raise ValueError("Histórico excede o limite de consulta")
        for item in result:
            if not isinstance(item,dict):
                raise ValueError("Registro histórico inesperado")
            jid = item.get("remoteJid") or item.get("id")
            if isinstance(jid,str) and valid_sender_for_send(jid):
                found.add(jid)
    if not found:
        raise ValueError("Histórico vazio; não liberar modo novos")
    return found


def valid_sender_for_send(sender):
    # Apenas chats individuais com número explícito, nunca grupos, status ou @lid.
    return bool(re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net", sender))


class AccountConnection(sqlite3.Connection):
    """A configuração acompanha a conexão; nenhuma conta global é selecionada."""


def connect(account=None):
    account = account or default_account()
    if not account.enabled:
        raise ValueError("Conta desabilitada")
    # Verificar também no uso para rejeitar symlink introduzido após o registro.
    expected = database_path(BASE, account.account_id)
    if account.database.resolve() != expected.resolve():
        raise ValueError("Banco fora do diretório da conta")
    account.database.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(account.database, timeout=10, factory=AccountConnection)
    db.account = account
    db.row_factory = sqlite3.Row
    return db


def init(account=None):
    account = account or default_account()
    with connect(account) as db:
        ensure_outbox(db)
        db.execute("""CREATE TABLE IF NOT EXISTS bot_outbound_ids (
            sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY(sender_id,message_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS outgoing_observations (
            sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
            classification TEXT NOT NULL CHECK(classification IN ('bot','manual','uncertain')),
            created_at TEXT NOT NULL, PRIMARY KEY(sender_id,message_id)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS operator_activity (
            sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
            created_at TEXT NOT NULL, PRIMARY KEY(sender_id,message_id)
        )""")
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
        db.execute("""CREATE TABLE IF NOT EXISTS conversation_turns(
            sender_id TEXT NOT NULL, message_id TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('client','assistant')),
            text TEXT NOT NULL, created_at TEXT NOT NULL,
            PRIMARY KEY(sender_id,message_id,role)
        )""")
        db.execute("CREATE INDEX IF NOT EXISTS idx_turns_sender_time ON conversation_turns(sender_id,created_at)")

        db.execute("""CREATE TABLE IF NOT EXISTS policy_settings(
            key TEXT PRIMARY KEY,value TEXT NOT NULL
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS contact_rules(
            sender_id TEXT NOT NULL,category TEXT NOT NULL CHECK(category IN ('test','excluded')),
            PRIMARY KEY(sender_id,category)
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS known_contacts(
            sender_id TEXT PRIMARY KEY
        )""")
        db.execute("""CREATE TABLE IF NOT EXISTS handoff_offers(
            sender_id TEXT PRIMARY KEY,
            message_id TEXT NOT NULL,
            created_at TEXT NOT NULL
        )""")



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


def is_handoff_yes(message):
    """Aceita apenas confirmação explícita de uma oferta anterior registrada."""
    return normalized(message).strip(" .!?") in ("sim", "s", "pode", "pode sim", "quero", "por favor", "sim por favor")


def is_handoff_no(message):
    return normalized(message).strip(" .!?") in ("nao", "n", "nao obrigado", "nao obrigada", "prefiro nao")


def valid_event(ev, account=None):
    return (event_account(ev, account) is not None
            and ev.get("isClientMessage") is True
            and ev.get("isGroup") is False
            and valid_sender_for_send(str(ev.get("senderId") or ""))
            and isinstance(ev.get("messageId"), str)
            and 1 <= len(ev["messageId"]) <= 160)


def process_inbound(ev, enqueue=False, account=None):
    """Atomic finite-state processing; returns only bounded actions.

    Intentionally no LLM inference here. Explicit opt-in is a strict command.
    Multiple deliveries of one incoming event return 'ignore'.
    """
    account = event_account(ev, account)
    if account is None or not valid_event(ev, account):
        return None
    sender, mid = ev["senderId"], ev["messageId"]
    ts = now()
    message = str(ev.get("messageText") or "")[:500]
    name = str(ev.get("senderName") or "Contato")[:100]
    subject = str(ev.get("category") or "Atendimento")[:100]
    summary = str(ev.get("summary") or "")[:500]
    handoff = ev.get("handoffRequested") is True
    with account.lock, connect(account) as db:
        eligibility = contact_policy(db, sender)
        if not eligibility["allowed"]:
            return {"action": "ignore", "state": "policy_blocked",
                    "reason": eligibility["reason"], "messageId": mid}
        seen = db.execute("SELECT 1 FROM inbound_ids WHERE sender_id=? AND message_id=?",
                          (sender, mid)).fetchone()
        if seen:
            return {"action": "ignore", "state": "duplicate", "messageId": mid}
        old = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
        offer = db.execute("SELECT message_id,created_at FROM handoff_offers WHERE sender_id=?", (sender,)).fetchone()
        if offer:
            # Oferta só vale para a próxima mensagem, até duas horas depois; não
            # transforma 'sim' genérico de conversas futuras em encaminhamento.
            from datetime import timedelta
            try:
                age = datetime.now(timezone.utc) - datetime.fromisoformat(offer["created_at"])
                valid_offer = timedelta(0) <= age <= timedelta(hours=2)
            except (ValueError, TypeError):
                valid_offer = False
            confirmed_offer = valid_offer and is_handoff_yes(message)
            handoff = handoff or confirmed_offer
            if confirmed_offer:
                previous = db.execute("""SELECT text FROM conversation_turns
                    WHERE sender_id=? AND role='client'
                    ORDER BY rowid DESC LIMIT 1""", (sender,)).fetchone()
                subject = "atendimento"
                summary = ("Cliente confirmou atendimento humano. Dúvida anterior: "
                           + previous["text"][:280]) if previous else "Cliente confirmou atendimento humano"
            db.execute("DELETE FROM handoff_offers WHERE sender_id=?", (sender,))
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
            elif choice == "origin_review":
                # Origem nao comprovada nao equivale a atendimento humano.
                # Quarentena: sem responder, oferecer escolha ou reativar bot.
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
        if message.strip():
            db.execute("""INSERT OR IGNORE INTO conversation_turns(sender_id,message_id,role,text,created_at)
                          VALUES(?,?,?,?,?)""",(sender,mid,"client",message,ts))
        if enqueue:
            # Registro e decisão na MESMA transação SQLite. Nenhum envio aqui.
            queue_decision(db, ev, {"action": action}, account=account)

    return {"action": action, "state": routing_decision(account.instance,sender, account)["state"],
            "messageId": mid, "senderId": sender, "instance": account.instance}


def evolution_outbound_id(raw, expected_sender):
    """Retorna ID só se a Evolution confirmar destino e autoria do envio.

    Aceita PN direto ou LID numérico com PN alternativo idêntico ao destino.
    Campos ausentes ou LID sem vínculo explícito nunca são inferidos.
    """
    if not isinstance(raw, dict) or not isinstance(expected_sender, str) or not valid_sender_for_send(expected_sender):
        return None
    key = raw.get("key")
    if not isinstance(key, dict) or key.get("fromMe") is not True:
        return None
    remote = key.get("remoteJid")
    if remote != expected_sender:
        if (not isinstance(remote, str) or
                re.fullmatch(r"[0-9]{5,25}@lid", remote) is None or
                key.get("remoteJidAlt") != expected_sender):
            return None
    ident = key.get("id")
    if not isinstance(ident, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", ident):
        return None
    return ident


def observe_outgoing(ev, account=None):
    """Trata eco fromMe pela Central, correlacionando ID com saída do robô.

    Evento sem ID de saída comprovado não pode autorizar recuperação.
    Quando a origem é incerta, bloqueia o envio até revisão manual.
    """
    account = event_account(ev, account)
    if (account is None
            or ev.get("fromMe") is not True or ev.get("isGroup") is not False):
        return None
    sender, mid = ev.get("senderId"), ev.get("messageId")
    if not isinstance(sender, str) or not valid_sender_for_send(sender):
        return None
    if not isinstance(mid, str) or not re.fullmatch(r"[A-Za-z0-9_.:-]{1,160}", mid):
        return None
    # Não confiar no webhook: conferir a existência e autoria do ID na API
    # autenticada da Evolution antes de alterar a Central ou cancelar a fila.
    cfg = account.config
    if not verify_outgoing(sender, mid,
            base_url=str(cfg.get("evolution_url") or ""),
            instance=str(cfg.get("evolution_instance") or ""),
            api_key=str(cfg.get("evolution_api_key") or ""), account=account):
        return None
    with account.lock, connect(account) as db:
        previous = db.execute("""SELECT classification FROM outgoing_observations
            WHERE sender_id=? AND message_id=?""", (sender, mid)).fetchone()
        if previous:
            return {"ok": True, "classification": previous["classification"], "duplicate": True}
        bot = db.execute("""SELECT 1 FROM bot_outbound_ids
            WHERE sender_id=? AND message_id=?""", (sender, mid)).fetchone()
        if bot:
            classification = "bot"
        else:
            # Não inferir que é manual só porque fromMe=true.
            # Em resultado incerto da Evolution, o eco pode ser do próprio robô.
            classification = "uncertain"
            # fromMe=true prova apenas que a conta enviou, nao que um humano assumiu.
            # Quarentena bloqueia o bot sem inventar um atendimento humano.
            # Preservar human quando ja foi assumido de forma confirmada.
            db.execute("""INSERT INTO conversations(sender_id,sender_name,subject,summary,
                last_message,last_message_id,status,updated_at,created_at,
                choice_state,choice_message_id)
                VALUES(?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(sender_id) DO UPDATE SET
                  status=CASE WHEN conversations.status='human' THEN 'human' ELSE 'pending' END,
                  choice_state=CASE WHEN conversations.status='human'
                    THEN conversations.choice_state ELSE 'origin_review' END,
                  choice_message_id=CASE WHEN conversations.status='human'
                    THEN conversations.choice_message_id ELSE excluded.choice_message_id END,
                  updated_at=excluded.updated_at""",
                (sender, "Contato", "Revisao de origem",
                 "Saida sem autoria confirmada; requer revisao",
                 "", mid, "pending", now(), now(), "origin_review", mid))
            cancel_for_manual(db, sender)
        db.execute("""INSERT INTO outgoing_observations
            (sender_id,message_id,classification,created_at) VALUES(?,?,?,?)""",
            (sender, mid, classification, now()))
    return {"ok": True, "classification": classification, "duplicate": False}


def record_operator_activity(ev, account=None):
    """Registra mensagem manual enviada pelo operador via Evolution.

    Exige evento confirmado fromMe=true, chat individual e número explícito.
    Ignora corpo da mensagem: só o ID e o destinatário são persistidos.
    """
    # fromMe=true também identifica mensagens do robô na Evolution.
    # Nunca ativar este endpoint para eventos crus: somente origem manual
    # comprovada por correlação de ID ou ato explícito do operador.
    account = event_account(ev, account)
    if (account is None
            or ev.get("fromMe") is not True or ev.get("isGroup") is not False
            or ev.get("verifiedManual") is not True):
        return None
    sender, mid = ev.get("senderId"), ev.get("messageId")
    if not isinstance(sender, str) or not valid_sender_for_send(sender):
        return None
    if not isinstance(mid, str) or not 1 <= len(mid) <= 160:
        return None
    stamp = now()
    with account.lock, connect(account) as db:
        added = db.execute("INSERT OR IGNORE INTO operator_activity(sender_id,message_id,created_at) VALUES(?,?,?)",
                           (sender, mid, stamp)).rowcount == 1
        if not added:
            return {"ok": True, "duplicate": True, "manualActive": True}
        existing = db.execute("SELECT sender_id FROM conversations WHERE sender_id=?", (sender,)).fetchone()
        if existing:
            db.execute("""UPDATE conversations SET status='human',choice_state='idle',
                          choice_message_id='',updated_at=? WHERE sender_id=?""", (stamp, sender))
        else:
            db.execute("""INSERT INTO conversations(sender_id,sender_name,subject,summary,
                          last_message,last_message_id,status,updated_at,created_at,choice_state)
                          VALUES(?,?,?,?,?,?,?,?,?,?)""",
                       (sender, "Contato", "Atendimento manual", "Operador respondeu pelo WhatsApp",
                        "", mid, "human", stamp, stamp, "idle"))
        canceled = cancel_for_manual(db, sender)
        db.execute("DELETE FROM handoff_offers WHERE sender_id=?", (sender,))
    return {"ok": True, "duplicate": False, "manualActive": True, "queue": canceled}


def store_event(ev, account=None):
    account = event_account(ev, account)
    if account is None or ev.get("isClientMessage") is not True or ev.get("isGroup") is True:
        return False
    sender = str(ev.get("senderId") or "")[:160]
    mid = str(ev.get("messageId") or "")[:160]
    if not sender or not mid or not re.fullmatch(r"[0-9A-Za-z_.:@+-]+", sender):
        return False
    name = str(ev.get("senderName") or "Contato")[:100]
    subject = str(ev.get("category") or "Atendimento")[:100]
    summary = str(ev.get("summary") or "")[:500]
    message = str(ev.get("messageText") or "")[:500]
    with account.lock, connect(account) as db:
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


def routing_decision(instance, sender, account=None):
    """Read authoritative state for n8n. No state lookup error may imply permission."""
    account = event_account({"instance": instance}, account)
    if account is None or not valid_sender_for_send(sender):
        return None
    with account.lock, connect(account) as db:
        row = db.execute("SELECT status,choice_state FROM conversations WHERE sender_id=?", (sender,)).fetchone()
        eligibility = contact_policy(db, sender)
    status = row["status"] if row else "none"
    choice = row["choice_state"] if row else "idle"
    permission = eligibility["allowed"] and (status in ("none", "done") or (status == "pending" and choice == "opted_in"))
    return {"allowAutoReply": permission, "state": status, "choiceState": choice,
            "reason": ("allowed" if permission else eligibility["reason"] if not eligibility["allowed"]
                       else "human_active" if status == "human"
                       else "origin_unverified" if choice == "origin_review" else "human_pending"),
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
        return self.account.authenticate(self.headers.get("Authorization", ""))

    def read_json(self):
        if hasattr(self, "_json_body"):
            return self._json_body
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 16384:
                return None
            data = json.loads(self.rfile.read(length))
            return data if isinstance(data, dict) else None
        except (ValueError, UnicodeError):
            return None

    def dispatch_account(self, method):
        self.account = None
        self._json_body = None
        registry = account_registry()
        original_path = self.path
        path = self.path
        selected = None
        if path.startswith("/accounts/"):
            match = re.fullmatch(r"/accounts/([^/]+)(/.*)", path)
            if match is None:
                return self.respond(404, {"error": "Conta não encontrada"})
            selected = registry.resolve(account_id=match[1])
            if selected is None:
                return self.respond(404, {"error": "Conta não encontrada"})
            path = match[2]
        if method == "POST":
            # Limpar cache antes da única leitura; reuso de conexão HTTP não vaza contexto.
            del self._json_body
            self._json_body = self.read_json()
        payload = self._json_body
        is_bridge = path.startswith("/bridge/")
        is_evolution = path == "/evolution/ingress-check"
        if is_bridge or is_evolution:
            legacy_context = path == "/bridge/context" and selected is None
            instance = payload.get("instance") if isinstance(payload, dict) else None
            if selected is None:
                selected = registry.resolve(instance=instance) if instance is not None else (
                    registry.resolve(account_id=DEFAULT_ACCOUNT_ID) if legacy_context else None)
            # Auth inválida/missing não deve revelar conta ou ler banco.
            if selected is None:
                default = registry.resolve(account_id=DEFAULT_ACCOUNT_ID)
                key = "evolution_webhook_secret" if is_evolution else "bridge_secret"
                if default is None or not default.authenticate(self.headers.get("Authorization", ""), key):
                    return self.respond(403, {"error": "Acesso negado"})
                if not isinstance(payload, dict):
                    return self.respond(422 if is_evolution else 400, {"error": "JSON inválido"})
                return self.respond(422, {"error": "Instância obrigatória ou desconhecida"})
            key = "evolution_webhook_secret" if is_evolution else "bridge_secret"
            if not selected.authenticate(self.headers.get("Authorization", ""), key):
                return self.respond(403, {"error": "Acesso negado"})
            if not isinstance(payload, dict):
                return self.respond(422 if is_evolution else 400, {"error": "JSON inválido"})
            if instance != selected.instance and not (legacy_context and instance is None):
                return self.respond(422, {"error": "Instância incompatível"})
        else:
            selected = selected or registry.resolve(account_id=DEFAULT_ACCOUNT_ID)
        if selected is None:
            return self.respond(404, {"error": "Conta não encontrada"})
        if isinstance(payload, dict) and "account_id" in payload and payload["account_id"] != selected.account_id:
            return self.respond(422, {"error": "Conta incompatível"})
        self.account = selected
        self.path = path
        try:
            if method == "GET":
                return Handler.get_account(self)
            return Handler.post_account(self)
        finally:
            self.path = original_path

    def do_GET(self):
        return Handler.dispatch_account(self, "GET")

    def do_POST(self):
        return Handler.dispatch_account(self, "POST")

    def get_account(self):
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
        if self.path == "/api/accounts":
            return self.respond(200, {"items": account_registry().available()})
        if self.path == "/api/policy":
            with self.account.lock, connect(self.account) as db:
                policy = get_policy(db)
                policy["test"] = [r[0] for r in db.execute(
                    "SELECT sender_id FROM contact_rules WHERE category='test' ORDER BY sender_id")]
                policy["excluded"] = [r[0] for r in db.execute(
                    "SELECT sender_id FROM contact_rules WHERE category='excluded' ORDER BY sender_id")]
            return self.respond(200, policy)
        if self.path == "/api/conversations":
            with connect(self.account) as db:
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
            with connect(self.account) as db:
                row = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
            return self.respond(200, {"item": dict(row)}) if row else self.respond(404, {"error": "Não encontrado"})
        return self.respond(404, {"error": "Não encontrado"})

    def send_automated(self, data):
        """Safe outbound dispatch: atomic with operator actions, dedupe per inbound ID."""
        if os.environ.get("CENTRAL_LAB_NO_WHATSAPP") == "1":
            return self.respond(403, {"error": "LAB: saída WhatsApp desativada"})
        account = event_account(data, getattr(self, "account", None))
        if account is None:
            return self.respond(422, {"error": "Instância inválida"})
        sender = data.get("senderId")
        instance = data.get("instance")
        message_id = data.get("messageId")
        kind = data.get("kind", "normal")
        if not all(isinstance(x, str) for x in (sender, instance, message_id)):
            return self.respond(422, {"error": "Campos obrigatórios ausentes"})
        if kind not in ("normal", "fallback", "handoff", "choice", "human_offer"):
            return self.respond(422, {"error": "Tipo de envio inválido"})
        if not 1 <= len(message_id) <= 160:
            return self.respond(422, {"error": "messageId inválido"})
        cfg = account.config
        if not valid_sender_for_send(sender):
            return self.respond(403, {"error": "Destino inválido"})
        key = str(cfg.get("evolution_api_key") or "")
        base = str(cfg.get("evolution_url") or "").rstrip("/")
        configured_instance = str(cfg.get("evolution_instance") or "")
        if not key or not base.startswith(("http://", "https://")) or not re.fullmatch(r"[A-Za-z0-9_-]+", configured_instance):
            return self.respond(503, {"error": "Evolution API não configurada"})
        if instance != configured_instance:
            return self.respond(422, {"error": "Instância inválida"})
        message = (account.prompt(kind) if kind in ("choice", "handoff", "human_offer") else data.get("text"))
        if not isinstance(message, str) or not 0 < len(message.strip()) <= 1500:
            return self.respond(422, {"error": "Texto inválido"})
        message = message.strip()
        if kind in ("normal", "fallback"):
            normalized_out = normalized(message)
            # Gemini nunca pode confirmar operação que o backend não registrou.
            if re.search(r"\b(encaminhei|foi encaminhad[oa]|ja encaminh|avisei (um |o )?colega|colega (ja )?recebeu)\b", normalized_out):
                return self.respond(422, {"error": "Confirmação de encaminhamento sem registro bloqueada"})
            if (("encaminh" in normalized_out or "atendente" in normalized_out or "colega" in normalized_out)
                    and ("quer" in normalized_out or "posso" in normalized_out or "pode" in normalized_out)):
                return self.respond(422, {"error": "Oferta de atendimento deve usar tipo human_offer"})
        delivery_key = "auto-" + hashlib.sha256(
            (sender + "|" + message_id + "|" + kind).encode()).hexdigest()
        with account.lock:
            decision = routing_decision(instance, sender, account)
            with connect(account) as db:
                row = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
                guard = db.execute("SELECT * FROM bot_guard WHERE sender_id=?", (sender,)).fetchone()
                # Exclusão e modo de autorização valem também para mensagens protocolares.
                if not contact_policy(db, sender)["allowed"]:
                    return self.respond(403, {"error": "Contato bloqueado pela política da Central"})
                if kind == "human_offer":
                    allowed = decision is not None and decision["allowAutoReply"] and (
                        row is None or row["status"] == "done")
                elif kind == "choice":
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
                    reply_raw = response.read(8192)
                    if not 200 <= response.status < 300:
                        raise ValueError("Evolution rejected request")
                try:
                    bot_id = evolution_outbound_id(json.loads(reply_raw), sender)
                except (ValueError, UnicodeError, TypeError):
                    bot_id = None
                with connect(account) as db:
                    db.execute("UPDATE replies SET outcome='accepted' WHERE request_id=?", (delivery_key,))
                    if bot_id:
                        db.execute("""INSERT OR IGNORE INTO bot_outbound_ids
                            (sender_id,message_id,created_at) VALUES(?,?,?)""",
                            (sender,bot_id,now()))
                    db.execute("""INSERT OR IGNORE INTO conversation_turns(sender_id,message_id,role,text,created_at)
                                  VALUES(?,?,?,?,?)""",(sender,delivery_key,"assistant",message[:1500],now()))

                    if kind == "human_offer":
                        db.execute("""INSERT INTO handoff_offers(sender_id,message_id,created_at)
                                      VALUES(?,?,?)
                                      ON CONFLICT(sender_id) DO UPDATE SET
                                      message_id=excluded.message_id,created_at=excluded.created_at""",
                                   (sender,message_id,now()))
                    if kind == "handoff":
                        db.execute("DELETE FROM handoff_offers WHERE sender_id=?", (sender,))
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
                with connect(account) as db:
                    db.execute("UPDATE replies SET outcome='uncertain' WHERE request_id=?", (delivery_key,))
                return self.respond(502, {"error":"Envio incerto. Não repetir sem conferir WhatsApp"})

    def post_account(self):
        if self.path == "/evolution/ingress-check":
            # Isolated preflight: does NOT persist, dispatch, or send.
            if not self.account.authenticate(self.headers.get("Authorization", ""), "evolution_webhook_secret"):
                return self.respond(403, {"error": "Acesso negado"})
            payload = self.read_json()
            event = normalize_evolution(payload, expected_instance=self.account.instance)
            if event is None:
                return self.respond(422, {"error": "Evento não suportado"})
            return self.respond(200, {"accepted": True, "dispatch": False})
        if self.path == "/bridge/context":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            payload = self.read_json()
            if not isinstance(payload,dict):
                return self.respond(400, {"error": "JSON inválido"})
            sender = payload.get("senderId")
            message_id = payload.get("messageId")
            if not valid_sender_for_send(str(sender or "")) or not isinstance(message_id,str):
                return self.respond(422, {"error": "Identificador inválido"})
            with self.account.lock, connect(self.account) as db:
                current = db.execute("""SELECT 1 FROM inbound_ids
                                        WHERE sender_id=? AND message_id=?""",
                                     (sender,message_id)).fetchone()
                policy = contact_policy(db,sender)
                if not current or not policy["allowed"]:
                    return self.respond(403, {"error": "Mensagem não autorizada"})
                # Apenas as últimas 12 falas, e nunca dados de outro contato.
                turns = db.execute("""SELECT role,text FROM conversation_turns
                    WHERE sender_id=? ORDER BY created_at DESC, rowid DESC LIMIT 12""",(sender,)).fetchall()
            return self.respond(200, {"turns":[dict(t) for t in reversed(turns)]})
        if self.path in ("/api/policy/mode", "/api/policy/contacts", "/api/policy/remove", "/api/policy/baseline"):
            if not self.ingress() or self.headers.get("X-Requested-With") != "UmdoislabCentral":
                return self.respond(403, {"error": "Acesso negado"})
            body = self.read_json()
            if body is None:
                return self.respond(400, {"error": "JSON inválido"})
            if self.path == "/api/policy/contacts":
                result = update_contacts(body.get("category"), body.get("numbers"), self.account)
                if result is None:
                    return self.respond(422, {"error": "Número inválido; use DDI + DDD + número, só dígitos"})
                return self.respond(200, {"ok": True, "added": len(result)})
            if self.path == "/api/policy/remove":
                category, sender = body.get("category"), canonical_number(body.get("number"))
                if category not in ("test", "excluded") or not sender:
                    return self.respond(422, {"error": "Contato inválido"})
                with self.account.lock, connect(self.account) as db:
                    db.execute("DELETE FROM contact_rules WHERE sender_id=? AND category=?", (sender, category))
                return self.respond(200, {"ok": True})
            if self.path == "/api/policy/mode":
                mode = body.get("mode")
                if mode not in POLICY_MODES:
                    return self.respond(422, {"error": "Modo inválido"})
                with self.account.lock, connect(self.account) as db:
                    if mode == "new" and not get_policy(db)["baseline_ready"]:
                        return self.respond(409, {"error": "Sincronize o histórico antes de ativar contatos novos"})
                    db.execute("""INSERT INTO policy_settings VALUES('mode',?)
                                  ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(mode,))
                return self.respond(200, {"ok": True, "mode": mode})
            try:
                found = historical_baseline(self.account)
            except (ValueError, OSError, urllib.error.URLError, json.JSONDecodeError):
                return self.respond(503, {"error": "Não foi possível verificar o histórico completo na Evolution"})
            with self.account.lock, connect(self.account) as db:
                for sender in found:
                    db.execute("INSERT OR IGNORE INTO known_contacts VALUES(?)", (sender,))
                for key, value in (("baseline_ready", "1"), ("baseline_count", str(len(found))), ("baseline_at", now())):
                    db.execute("""INSERT INTO policy_settings VALUES(?,?)
                                  ON CONFLICT(key) DO UPDATE SET value=excluded.value""",(key,value))
            return self.respond(200, {"ok": True, "count": len(found)})
        if self.path == "/bridge/outgoing-observation":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            ev = self.read_json()
            if ev is None:
                return self.respond(400, {"error": "JSON inválido"})
            result = observe_outgoing(ev, account=self.account)
            if result is None:
                return self.respond(422, {"error": "Evento de saída inválido"})
            return self.respond(200, result)
        if self.path == "/bridge/inbound":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            ev = self.read_json()
            if ev is None:
                return self.respond(400, {"error": "JSON inválido"})
            result = process_inbound(ev, account=self.account)
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
            decision = routing_decision(instance, sender, self.account)
            if decision is None:
                return self.respond(422, {"error": "Instância ou destinatário incompatível"})
            return self.respond(200, decision)
        if self.path == "/bridge/events":
            if not self.bridge():
                return self.respond(403, {"error": "Acesso negado"})
            event = self.read_json()
            if event is None:
                return self.respond(400, {"error": "JSON inválido"})
            return self.respond(200, {"recorded": store_event(event, account=self.account)})
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
            if os.environ.get("CENTRAL_LAB_NO_WHATSAPP") == "1":
                return self.respond(403, {"error": "LAB: saída WhatsApp desativada"})
            cfg = self.account.config
            api_key = str(cfg.get("evolution_api_key") or "")
            endpoint = str(cfg.get("evolution_url") or "").rstrip("/")
            instance = str(cfg.get("evolution_instance") or "")
            if not api_key or not endpoint.startswith(("http://", "https://")) or not re.fullmatch(r"[A-Za-z0-9_-]+", instance):
                return self.respond(503, {"error": "Evolution API não configurada"})
            if not valid_sender_for_send(sender):
                return self.respond(422, {"error": "Identificador do contato incompatível com envio seguro; confira o JID recebido"})
        with self.account.lock, connect(self.account) as db:
            existing = db.execute("SELECT * FROM conversations WHERE sender_id=?", (sender,)).fetchone()
            if not existing:
                return self.respond(404, {"error": "Conversa não encontrada"})
            if action != "reply":
                status = {"assume": "human", "resolve": "done", "reopen": "pending"}[action]
                db.execute("UPDATE conversations SET status=?, updated_at=? WHERE sender_id=?",
                           (status, now(), sender))
                if action == "assume":
                    cancel_for_manual(db, sender)
                if action == "resolve":
                    db.execute("""UPDATE conversations SET choice_state='idle',
                                  last_bot_text='',fallback_count=0,bot_repeat_count=0,
                                  choice_message_id='' WHERE sender_id=?""", (sender,))
                    db.execute("DELETE FROM bot_guard WHERE sender_id=?", (sender,))
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
            cancel_for_manual(db, sender)
        url = endpoint + "/message/sendText/" + instance
        body = json.dumps({"number":sender.split("@")[0], "text":message}).encode()
        req = urllib.request.Request(url, data=body,
            headers={"Content-Type":"application/json","apikey":api_key}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=12) as res:
                payload = res.read(8192)
                if not 200 <= res.status < 300:
                    raise urllib.error.HTTPError(url,res.status,"HTTP failure",{},None)
            # Resposta pela própria Central já marca o contato como humano.
            # Acompanhamos o ID para classificar o eco como conhecido.
            try:
                human_id = evolution_outbound_id(json.loads(payload), sender)
            except (ValueError, UnicodeError, TypeError):
                human_id = None
            if human_id:
                with self.account.lock, connect(self.account) as db:
                    db.execute("""INSERT OR IGNORE INTO outgoing_observations
                        (sender_id,message_id,classification,created_at)
                        VALUES(?,?,?,?)""", (sender,human_id,"manual",now()))
            # HTTP success = request accepted by Evolution, NOT delivery proof
            with self.account.lock, connect(self.account) as db:
                db.execute("UPDATE replies SET outcome='accepted' WHERE request_id=?", (req_id,))
                db.execute("""UPDATE conversations SET last_reply=?,last_reply_at=?,status='human',
                              updated_at=? WHERE sender_id=?""",(message[:1500],now(),now(),sender))
            return self.respond(200, {"ok":True,"detail":"Evolution API aceitou o envio; entrega não confirmada"})
        except Exception:
            with self.account.lock, connect(self.account) as db:
                db.execute("UPDATE replies SET outcome='uncertain' WHERE request_id=?", (req_id,))
            return self.respond(502, {"error":"Envio sem confirmação. Confira o WhatsApp antes de tentar novamente."})


if __name__ == "__main__":
    for account in account_registry().by_id.values():
        if account.enabled:
            init(account)
    ThreadingHTTPServer(("0.0.0.0", 8099), Handler).serve_forever()
