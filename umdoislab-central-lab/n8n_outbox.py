"""Fila SQLite isolada para decisões da Central.

Sem I/O de rede. Uma confirmação HTTP do n8n não é prova de entrega WhatsApp.
Resultados de envio incertos NÃO são reenviados automaticamente.
"""
import json
import sqlite3
from datetime import datetime, timezone


def utc_now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def ensure_outbox(db):
    db.execute("""CREATE TABLE IF NOT EXISTS n8n_outbox (
        sender_id TEXT NOT NULL,
        message_id TEXT NOT NULL,
        action TEXT NOT NULL,
        payload_json TEXT NOT NULL,
        state TEXT NOT NULL CHECK (state IN
            ('pending','in_flight','accepted','uncertain','rejected')),
        attempts INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY (sender_id,message_id)
    )""")
    db.execute("CREATE INDEX IF NOT EXISTS idx_n8n_outbox_state ON n8n_outbox(state,created_at)")


def put(db, event, decision):
    """Grava exatamente uma decisão por mensagem. Usar dentro da transação de entrada."""
    if not isinstance(event, dict) or not isinstance(decision, dict):
        raise ValueError("Evento ou decisão inválida")
    sender = event.get("senderId")
    mid = event.get("messageId")
    action = decision.get("action")
    if (not isinstance(sender, str) or not sender or
            not isinstance(mid, str) or not mid or
            action not in ("auto", "resume", "handoff", "offer_choice", "silent", "ignore")):
        raise ValueError("Identificadores ou ação inválidos")
    payload = {
        "instance": "umdoislab", "senderId": sender, "messageId": mid,
        "messageText": str(event.get("messageText") or "")[:500],
        "senderName": str(event.get("senderName") or "Contato")[:100],
        "action": action,
    }
    # As decisões sem processamento externo permanecem auditáveis, sem envio.
    state = "pending" if action in ("auto", "resume", "handoff", "offer_choice") else "rejected"
    stamp = utc_now()
    cur = db.execute(
        """INSERT OR IGNORE INTO n8n_outbox
        (sender_id,message_id,action,payload_json,state,created_at,updated_at)
        VALUES(?,?,?,?,?,?,?)""",
        (sender, mid, action, json.dumps(payload, ensure_ascii=False), state, stamp, stamp))
    return cur.rowcount == 1


def cancel_for_manual(db, sender):
    """Marca pendências como rejeitadas e tentativas em andamento como incertas.

    Uma chamada em voo pode já ter alcançado o receptor; nunca reenviar
    automaticamente esse resultado depois que o operador assumiu.
    """
    if not isinstance(sender, str) or not sender:
        raise ValueError("Remetente inválido")
    rejected = db.execute(
        "UPDATE n8n_outbox SET state='rejected',updated_at=? "
        "WHERE sender_id=? AND state='pending'", (utc_now(), sender)).rowcount
    uncertain = db.execute(
        "UPDATE n8n_outbox SET state='uncertain',updated_at=? "
        "WHERE sender_id=? AND state='in_flight'", (utc_now(), sender)).rowcount
    return {"rejected": rejected, "uncertain": uncertain}


def _manual_active(db, sender):
    exists = db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='conversations'").fetchone()
    if not exists:
        return False  # Teste isolado da fila; produção sempre cria conversations.
    row = db.execute("SELECT status FROM conversations WHERE sender_id=?", (sender,)).fetchone()
    return bool(row and row[0] == "human")


def claim(db):
    """Reserva um item pendente. Não reaproveita itens em voo após falhas/crash."""
    row = db.execute(
        """SELECT sender_id,message_id,payload_json FROM n8n_outbox
        WHERE state='pending' ORDER BY created_at,sender_id,message_id LIMIT 1"""
    ).fetchone()
    if row is None:
        return None
    sender, mid, payload = row
    if _manual_active(db, sender):
        cancel_for_manual(db, sender)
        return None
    updated = db.execute(
        """UPDATE n8n_outbox SET state='in_flight',attempts=attempts+1,updated_at=?
        WHERE sender_id=? AND message_id=? AND state='pending'""",
        (utc_now(), sender, mid))
    if updated.rowcount != 1:
        return None
    return json.loads(payload)


def settle(db, sender, mid, outcome):
    """Após tentativa de entrega: accepted=HTTP 2xx; uncertain=rede/timeout/5xx."""
    if outcome not in ("accepted", "uncertain", "rejected"):
        raise ValueError("Resultado inválido")
    updated = db.execute(
        """UPDATE n8n_outbox SET state=?,updated_at=?
        WHERE sender_id=? AND message_id=? AND state='in_flight'""",
        (outcome, utc_now(), sender, mid))
    return updated.rowcount == 1


def counts(db):
    return dict(db.execute(
        "SELECT state,COUNT(*) FROM n8n_outbox GROUP BY state").fetchall())


def deliver_one(db, transport, reconcile=None):
    """Uma tentativa por evento. transport(payload) retorna status HTTP inteiro.

    IMPORTANTE: transport deve enviar ao receptor n8n isolado, nunca ao Gateway
    antigo. Uma resposta incerta permanece bloqueada para análise humana.
    O chamador deve usar SQLite transacional (BEGIN IMMEDIATE) no claim e commit
    ANTES de executar I/O. Não faz HTTP automaticamente.
    """
    # Não liberar recuperação sem comprovar estado atual do WhatsApp.
    # Uma tomada humana pode ter ocorrido enquanto Evolution/n8n estavam offline.
    if reconcile is None:
        return {"outcome": "blocked_reconciliation"}
    item = claim(db)
    if item is None:
        return None
    # Conserva a reserva antes de qualquer efeito externo.
    db.commit()
    try:
        evidence = reconcile(item)
    except Exception:
        evidence = None
    if not isinstance(evidence, dict) or evidence.get("safe") is not True or evidence.get("senderId") != item["senderId"] or evidence.get("messageId") != item["messageId"]:
        with db:
            settle(db, item["senderId"], item["messageId"], "uncertain")
        return {"messageId": item["messageId"], "outcome": "blocked_reconciliation"}
    # Revalidar após a reserva; a intervenção manual pode ter ocorrido neste intervalo.
    row = db.execute("SELECT state FROM n8n_outbox WHERE sender_id=? AND message_id=?",
                     (item["senderId"], item["messageId"])).fetchone()
    if not row or row[0] != "in_flight" or _manual_active(db, item["senderId"]):
        with db:
            cancel_for_manual(db, item["senderId"])
        return {"messageId": item["messageId"], "outcome": "canceled_manual"}
    try:
        status = transport(item)
        if not isinstance(status, int):
            outcome = "uncertain"
        elif 200 <= status < 300:
            outcome = "accepted"
        elif 400 <= status < 500:
            outcome = "rejected"
        else:
            outcome = "uncertain"
    except Exception:
        outcome = "uncertain"
    with db:
        committed = settle(db, item["senderId"], item["messageId"], outcome)
    # O operador pode assumir durante a chamada externa; o estado cancelado
    # nunca deve virar accepted nem entrar em repetição automática.
    if not committed:
        return {"messageId": item["messageId"], "outcome": "uncertain"}
    return {"messageId": item["messageId"], "outcome": outcome}
