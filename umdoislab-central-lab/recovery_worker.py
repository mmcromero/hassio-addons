"""Orquestração isolada de recuperação; DESLIGADA por padrão.

Não cria thread, cron ou servidor. Exige autorização explícita do chamador e
transportes injetados. Nunca envia direto à Evolution/Gateway antigo.
"""
from datetime import datetime, timezone, timedelta

from evolution_history import collect_both
from n8n_outbox import deliver_one
from recovery_reconcile import evaluate, _stamp


def recover_one(db, *, enabled=False, fetch_pages=None, fetch_alt_pages=None, transport=None,
                policy_check=None, max_age_seconds=None, clock=None):
    """Tenta um item somente após prova completa e recente do histórico.

    fetch_pages(sender) -> fetch_page(page), apenas leitura autenticada Evolution.
    transport(item) -> HTTP status inteiro do receptor n8n ISOLADO.
    policy_check(db, sender) -> bool a partir da política real da Central.
    Os efeitos externos não devem ocorrer se alguma pré-condição faltar.
    """
    if enabled is not True:
        return {"outcome": "disabled"}
    if (not callable(fetch_pages) or not callable(fetch_alt_pages) or not callable(transport) or
            not callable(policy_check) or
            type(max_age_seconds) is not int or
            not 1 <= max_age_seconds <= 3600):
        return {"outcome": "blocked_configuration"}
    now = clock or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        return {"outcome": "blocked_clock"}
    now = now.astimezone(timezone.utc)

    def reconcile(item):
        sender, mid = item["senderId"], item["messageId"]
        refused = {"safe": False, "senderId": sender, "messageId": mid}
        row = db.execute("""SELECT created_at FROM n8n_outbox
                            WHERE sender_id=? AND message_id=?""",
                         (sender, mid)).fetchone()
        created = _stamp(row[0]) if row else None
        if created is None or created > now + timedelta(seconds=5):
            return {**refused, "reason": "invalid_queued_time"}
        if now - created > timedelta(seconds=max_age_seconds):
            return {**refused, "reason": "expired"}
        try:
            pages = fetch_pages(sender)
            alt_pages = fetch_alt_pages(sender)
        except Exception:
            return {**refused, "reason": "history_unavailable"}
        if not callable(pages) or not callable(alt_pages):
            return {**refused, "reason": "history_unavailable"}
        # Consulta TODAS as páginas do contato; a validação posterior exige
        # a mensagem original e impede respostas após qualquer saída posterior.
        since = (created - timedelta(seconds=max_age_seconds)).isoformat(timespec="seconds")
        snapshot = collect_both(sender, since, pages, alt_pages, clock=now)
        if snapshot is None:
            return {**refused, "reason": "history_unverified"}
        return evaluate(db, item, snapshot, policy_check=policy_check, clock=now)

    return deliver_one(db, transport, reconcile=reconcile)
