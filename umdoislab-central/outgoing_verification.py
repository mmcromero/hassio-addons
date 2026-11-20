"""Comprovação read-only de ecos enviados pela instância Evolution.

Nunca use fromMe ou o campo source do webhook como prova suficiente.
Antes de alterar o estado da conversa, verificar key.id e destinatário na
Evolution autenticada. Em ausência de prova, negar a classificação.
"""
import json
import re
from urllib.parse import quote
from urllib.request import Request, urlopen


def verify_outgoing(sender, message_id, *, base_url, instance, api_key,
                    timeout=8, opener=None, account=None):
    """Confere PN e, só após ausência comprovada, LID vinculado ao PN exato.

    Não consulta a alternativa quando há prova PN válida ou falha na principal.
    Não comprova autoria humana nem entrega ao WhatsApp.
    """
    if account is not None and (not account.enabled or instance != account.instance or
            base_url != account.config.get("evolution_url") or api_key != account.config.get("evolution_api_key")):
        return False
    if (not isinstance(sender, str) or
            not re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net", sender) or
            not isinstance(message_id, str) or
            not re.fullmatch(r"[-A-Za-z0-9_.:]{1,160}", message_id)):
        return False
    if (not isinstance(base_url, str) or not base_url.startswith(("http://", "https://")) or
            not isinstance(instance, str) or
            not re.fullmatch(r"[A-Za-z0-9_-]+", instance) or
            not isinstance(api_key, str) or not api_key):
        return False
    url = base_url.rstrip("/") + "/chat/findMessages/" + quote(instance, safe="")
    fetch = opener or urlopen

    def query(key_field):
        body = json.dumps({"where": {"key": {key_field: sender, "id": message_id}},
                           "page": 1, "offset": 10}).encode("utf-8")
        req = Request(url, data=body,
                      headers={"Content-Type": "application/json", "apikey": api_key},
                      method="POST")
        try:
            with fetch(req, timeout=timeout) as response:
                if not 200 <= response.status < 300:
                    return None
                raw = response.read(2_000_001)
                if len(raw) > 2_000_000:
                    return None
                result = json.loads(raw)
            return _verified_records(result, sender, message_id, key_field)
        except (OSError, ValueError, TypeError, RuntimeError, OverflowError):
            return None

    primary = query("remoteJid")
    if primary is None:
        return False  # Erro/dado inválido nunca vira ausência comprovada.
    if primary:
        return True
    # Somente uma página vazia e válida autoriza consultar a partição LID.
    alternate = query("remoteJidAlt")
    return alternate is not None and bool(alternate)


def _verified_records(result, sender, message_id, key_field):
    """None = inválido; set vazio = ausência comprovada; set unitário = prova.

    O filtro de ID limita a consulta a uma página completa de até 10 linhas.
    Remover somente o ID SQL na comparação: conteúdo, direção, identidade e
    timestamp contraditórios nunca podem ser ocultados por deduplicação.
    """
    if not isinstance(result, dict) or not isinstance(result.get("messages"), dict):
        return None
    m = result["messages"]
    total, pages, current = m.get("total"), m.get("pages"), m.get("currentPage")
    if (type(total) is not int or type(pages) is not int or type(current) is not int or
            not 0 <= total <= 10 or current != 1):
        return None
    records = m.get("records")
    if not isinstance(records, list) or len(records) != total:
        return None
    if total == 0:
        # APIs podem expressar a consulta vazia com zero ou uma página.
        return set() if pages in (0, 1) else None
    if pages != 1:
        return None
    fingerprints = set()
    for record in records:
        if not isinstance(record, dict):
            return None
        key = record.get("key")
        if (not isinstance(key, dict) or key.get("id") != message_id or
                key.get("fromMe") is not True):
            return None
        if key_field == "remoteJid":
            if key.get("remoteJid") != sender:
                return None
        elif (key.get("remoteJidAlt") != sender or
              not isinstance(key.get("remoteJid"), str) or
              not re.fullmatch(r"[0-9]{5,25}@lid", key["remoteJid"])):
            return None
        stamp = record.get("messageTimestamp")
        if type(stamp) is not int or not 1_000_000_000 <= stamp <= 4_000_000_000:
            return None
        fingerprints.add(json.dumps(
            {k: v for k, v in record.items() if k != "id"},
            sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return fingerprints if len(fingerprints) == 1 else None
