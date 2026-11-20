"""Validação preventiva de recuperação atrasada.

Função pura de decisão: o chamador deve obter a fotografia COMPLETA do
histórico Evolution por canal autenticado, sem inferir completude.
Nenhum serviço HTTP é chamado neste módulo.
"""
from accounts import require_database
from datetime import datetime, timezone, timedelta


def _stamp(value):
    if not isinstance(value, str):
        return None
    try:
        result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if result.tzinfo is None:
        return None
    return result.astimezone(timezone.utc)


def evaluate(db, item, snapshot, *, policy_check, clock=None, account=None):
    """Retorna evidência que deliver_one() aceita somente quando safe=True.

    snapshot: {
      senderId, complete: True, since: ISO8601, checkedAt: ISO8601,
      outbound: [{id, fromMe: True, timestamp: ISO8601}]
    }

    complete exige comprovação pela consulta integral (inclui paginação).
    A implementação de fetch/check da API instalada é uma dependência futura.
    """
    account = account or getattr(db, "account", None)
    require_database(db, account)
    sender = item.get("senderId") if isinstance(item, dict) else None
    mid = item.get("messageId") if isinstance(item, dict) else None
    result = {"safe": False, "senderId": sender, "messageId": mid}

    if account:
        result.update(account_id=account.account_id, instance=account.instance)

    def deny(reason):
        return {**result, "reason": reason}

    if account and (not isinstance(item, dict) or item.get("instance") != account.instance or
                    item.get("account_id", account.account_id) != account.account_id or
                    not isinstance(snapshot, dict) or snapshot.get("instance") != account.instance or
                    snapshot.get("account_id") != account.account_id):
        return deny("account_mismatch")
    if not isinstance(sender, str) or not isinstance(mid, str):
        return deny("invalid_identity")
    if not callable(policy_check):
        return deny("missing_policy")
    try:
        if policy_check(db, sender) is not True:
            return deny("policy_block")
    except Exception:
        return deny("policy_unavailable")
    queued = db.execute(
        "SELECT state,created_at FROM n8n_outbox WHERE sender_id=? AND message_id=?",
        (sender, mid)).fetchone()
    if not queued or queued[0] != "in_flight":
        return deny("not_claimed")
    created_at = _stamp(queued[1])
    if created_at is None:
        return deny("invalid_queue_clock")
    row = db.execute("SELECT status FROM conversations WHERE sender_id=?", (sender,)).fetchone()
    if row and row[0] not in ("none", "done"):
        return deny("operator_or_handoff")
    original = db.execute("SELECT 1 FROM inbound_ids WHERE sender_id=? AND message_id=?",
                          (sender, mid)).fetchone()
    if not original:
        return deny("inbound_not_recorded")
    newer = db.execute("""SELECT 1 FROM inbound_ids
        WHERE sender_id=? AND rowid > (
            SELECT rowid FROM inbound_ids WHERE sender_id=? AND message_id=?
        ) LIMIT 1""", (sender, sender, mid)).fetchone()
    if newer:
        return deny("newer_inbound")
    if not isinstance(snapshot, dict) or snapshot.get("complete") is not True or snapshot.get("senderId") != sender:
        return deny("history_unverified")
    since, checked = _stamp(snapshot.get("since")), _stamp(snapshot.get("checkedAt"))
    now = clock or datetime.now(timezone.utc)
    if since is None or checked is None or now.tzinfo is None:
        return deny("history_clock_missing")
    now = now.astimezone(timezone.utc)
    if since > created_at or checked < now-timedelta(seconds=60) or checked > now+timedelta(seconds=5):
        return deny("history_stale")
    incoming = snapshot.get("inbound")
    if not isinstance(incoming, list):
        return deny("history_missing_inbound")
    seen_original = False
    for event in incoming:
        if not isinstance(event, dict) or event.get("fromMe") is not False:
            return deny("history_invalid_inbound")
        xid = event.get("id")
        when = _stamp(event.get("timestamp"))
        if not isinstance(xid, str) or not xid or when is None:
            return deny("history_invalid_inbound")
        if xid == mid:
            seen_original = True
        elif when >= created_at:
            # Durante a queda, uma mensagem posterior pode não ter sido
            # registrada na fila local. A verificação completa ocorre abaixo,
            # usando o timestamp original da Evolution.
            pass
    if not seen_original:
        return deny("original_missing_from_history")
    # A referência é o instante do pedido recebido, não o da entrada na fila:
    # pode ter havido resposta manual entre as duas gravações.
    original_events = [event for event in incoming if event["id"] == mid]
    if len(original_events) != 1:
        return deny("original_ambiguous")
    original_at = _stamp(original_events[0]["timestamp"])
    if original_at is None or since > original_at:
        return deny("original_clock_unverified")
    if any(_stamp(ev["timestamp"]) >= original_at for ev in incoming if ev["id"] != mid):
        return deny("newer_inbound_history")
    unknown = db.execute("""SELECT 1 FROM outgoing_observations
        WHERE sender_id=? AND classification!='bot' AND created_at>=? LIMIT 1""",
        (sender, original_at.isoformat(timespec="seconds"))).fetchone()
    if unknown:
        return deny("outgoing_unclassified")
    outgoing = snapshot.get("outbound")
    if not isinstance(outgoing, list):
        return deny("history_missing_outgoing")
    for event in outgoing:
        if not isinstance(event, dict) or event.get("fromMe") is not True:
            return deny("history_invalid_event")
        xid = event.get("id")
        when = _stamp(event.get("timestamp"))
        if not isinstance(xid, str) or not xid or when is None:
            return deny("history_invalid_event")
        if when >= original_at:
            # Mesmo quando a saída veio do robô, ela pode ser a resposta já
            # entregue durante a indisponibilidade. Nunca repetir.
            return deny("outgoing_after_request")
    return {**result, "safe": True, "reason": "verified"}
