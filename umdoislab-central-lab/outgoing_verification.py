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
                    timeout=8, opener=None):
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
    body = json.dumps({"where": {"key": {"remoteJid": sender, "id": message_id}},
                       "page": 1, "offset": 10}).encode("utf-8")
    req = Request(url, data=body,
                  headers={"Content-Type": "application/json", "apikey": api_key},
                  method="POST")
    fetch = opener or urlopen
    try:
        with fetch(req, timeout=timeout) as response:
            if not 200 <= response.status < 300:
                return False
            result = json.loads(response.read(2_000_000))
    except (OSError, ValueError, TypeError, RuntimeError, OverflowError):
        return False
    if not isinstance(result, dict):
        return False
    m = result.get("messages")
    if not isinstance(m, dict):
        return False
    total, pages, current = m.get("total"), m.get("pages"), m.get("currentPage")
    if (type(total) is not int or type(pages) is not int or type(current) is not int or
            not 1 <= total <= 10 or pages != 1 or current != 1):
        return False
    records = m.get("records")
    if not isinstance(records, list) or len(records) != total:
        return False
    fingerprints = set()
    for record in records:
        if not isinstance(record, dict):
            return False
        key = record.get("key")
        if (not isinstance(key, dict) or
                key.get("remoteJid") != sender or
                key.get("id") != message_id or
                key.get("fromMe") is not True):
            return False
        stamp = record.get("messageTimestamp")
        if type(stamp) is not int or not 1_000_000_000 <= stamp <= 4_000_000_000:
            return False
        fingerprints.add(json.dumps(
            {k: v for k, v in record.items() if k != "id"},
            sort_keys=True, ensure_ascii=False, separators=(",", ":")))
    return len(fingerprints) == 1
