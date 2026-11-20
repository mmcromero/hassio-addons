"""Leitura somente consulta da Evolution para decisão de recuperação.

Não habilitado na produção. A API /chat/findMessages da Evolution v2
precisa ter paginação e completude verificadas na imagem efetivamente instalada.
Se qualquer página/campo for incompatível, NÃO autorizar envio antigo.
"""
import json
import re
from datetime import datetime, timezone
from urllib.parse import quote
from urllib.request import Request, urlopen


def _timestamp(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        if isinstance(value, str) and not value.isdigit():
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                return None
        else:
            seconds = int(value)
            if seconds < 1_000_000_000 or seconds > 4_000_000_000:
                return None
            dt = datetime.fromtimestamp(seconds, tz=timezone.utc)
        return dt.astimezone(timezone.utc).isoformat(timespec="seconds")
    except (ValueError, OverflowError, OSError):
        return None


def collect(sender, since, fetch_page, *, clock=None, max_pages=100):
    """Monta snapshot seguro após validar TODAS as páginas e seus registros.

    fetch_page(page) deve consultar o mesmo contato, sem paginação parcial,
    usando API autenticada. Não confiar em snapshot de página única.
    O caller deve verificar o retorno da instalação real antes de ativar.
    """
    now = clock or datetime.now(timezone.utc)
    if (not isinstance(sender,str) or
            not re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net", sender) or
            not isinstance(since,str) or not callable(fetch_page)):
        return None
    try:
        start = datetime.fromisoformat(since.replace("Z","+00:00"))
    except ValueError:
        return None
    if start.tzinfo is None or now.tzinfo is None:
        return None
    if not isinstance(max_pages,int) or not 1 <= max_pages <= 200:
        return None
    total, pages, items, seen, raw_count = None, None, [], {}, 0
    for page in range(1, max_pages+1):
        try:
            response=fetch_page(page)
        except Exception:
            return None
        data=response.get("messages") if isinstance(response,dict) else None
        if not isinstance(data,dict):
            return None
        if not all(isinstance(data.get(k),int) and not isinstance(data.get(k),bool)
                   for k in ("total","pages","currentPage")):
            return None
        current_total, current_pages=data["total"],data["pages"]
        if (current_total<0 or not 1 <= current_pages <= max_pages or
                data["currentPage"]!=page):
            return None
        if total is None:
            total,pages=current_total,current_pages
        elif total!=current_total or pages!=current_pages:
            return None  # Histórico mudou enquanto paginávamos.
        records=data.get("records")
        if not isinstance(records,list):
            return None
        for record in records:
            if not isinstance(record,dict):
                return None
            key=record.get("key")
            if not isinstance(key,dict) or not isinstance(key.get("fromMe"),bool):
                return None
            if key.get("remoteJid")!=sender:
                return None  # LID ou outra conversa sem mapeamento comprovado.
            ident=key.get("id")
            if not isinstance(ident,str) or not re.fullmatch(r"[-A-Za-z0-9_.:]{1,160}",ident):
                return None
            stamp=_timestamp(record.get("messageTimestamp"))
            if stamp is None:
                return None
            raw_count += 1
            # A API instalada devolveu duas cópias de um mesmo evento (exec. LAB 2354).
            # Aceitar apenas cópia exatamente igual, nunca IDs que conflitem
            # quanto ao destino, direção, conteúdo ou timestamp.
            # A versão instalada pode persistir duas linhas com ID SQL
            # diferente para a mesma mensagem do WhatsApp. A coluna
            # 'id' de banco NÃO é o identificador key.id do protocolo.
            # Comparar todo o restante do registro, inclusive conteúdo.
            fingerprint = json.dumps(
                {k: v for k, v in record.items() if k != "id"},
                sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            if ident in seen:
                if seen[ident] != fingerprint:
                    return None
                continue
            seen[ident] = fingerprint
            items.append({"id":ident,"timestamp":stamp,"fromMe":key["fromMe"]})
        if page==pages:
            break
    if pages is None or raw_count!=total:
        return None
    stamp=now.astimezone(timezone.utc).isoformat(timespec="seconds")
    return {"senderId":sender,"complete":True,"since":start.astimezone(timezone.utc).isoformat(timespec="seconds"),
            "checkedAt":stamp,
            "outbound":[item for item in items if item["fromMe"]],
            "inbound":[item for item in items if not item["fromMe"]]}


def make_page_reader(base_url, instance, api_key, sender, *, timeout=8, offset=100, key_field="remoteJid"):
    """Cria transporte GET-free: POST /chat/findMessages sem alterar dados.

    Um caller em modo de leitura faz a consulta; nenhuma chamada ocorre aqui.
    """
    if (not isinstance(base_url,str) or not base_url.startswith(("http://","https://")) or
            not isinstance(instance,str) or not re.fullmatch(r"[A-Za-z0-9_-]+",instance) or
            not isinstance(api_key,str) or not api_key or
            not isinstance(sender,str) or not re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net",sender)):
        raise ValueError("Parâmetro de consulta inválido")
    if key_field not in ("remoteJid", "remoteJidAlt"):
        raise ValueError("Campo de identidade inválido")
    endpoint=base_url.rstrip("/")+"/chat/findMessages/"+quote(instance,safe="")
    def fetch(page):
        if not isinstance(page,int) or page<1:
            raise ValueError("Página inválida")
        body=json.dumps({"where":{"key":{key_field:sender}},
                         "page":page,"offset":offset}).encode("utf-8")
        req=Request(endpoint,data=body,headers={"Content-Type":"application/json",
                    "apikey":api_key},method="POST")
        with urlopen(req,timeout=timeout) as response:
            if not 200 <= response.status < 300:
                raise RuntimeError("Consulta Evolution recusada")
            return json.loads(response.read(3_000_000))
    return fetch


def _normalize_alt_page(sender, response):
    """Confere JID alternativo de cada registro ANTES de normalizar para a fila.

    Não mistura duas conversas ou aceita LID de outro contato.
    """
    if not isinstance(response, dict) or not isinstance(response.get("messages"), dict):
        return None
    records = response["messages"].get("records")
    if not isinstance(records, list):
        return None
    normalized = []
    for record in records:
        if not isinstance(record, dict):
            return None
        key = record.get("key")
        if not isinstance(key, dict) or key.get("remoteJidAlt") != sender:
            return None
        direct = key.get("remoteJid")
        if not isinstance(direct, str) or not (
                direct == sender or re.fullmatch(r"[0-9]{5,25}@lid", direct)):
            return None
        normalized.append({**record, "key": {**key, "remoteJid": sender}})
    return {**response, "messages": {**response["messages"], "records": normalized}}


def collect_both(sender, since, fetch_primary, fetch_alternate, *, clock=None, max_pages=100):
    """Consulta duas partições completas: remoteJid e remoteJidAlt.

    Se uma partição falhar ou a mesma mensagem tiver campos contraditórios,
    não fornece autorização de recuperação.
    """
    if not callable(fetch_primary) or not callable(fetch_alternate):
        return None
    primary = collect(sender, since, fetch_primary, clock=clock, max_pages=max_pages)
    if primary is None:
        return None
    def verified_alt(page):
        return _normalize_alt_page(sender, fetch_alternate(page))
    alternate = collect(sender, since, verified_alt, clock=clock, max_pages=max_pages)
    if alternate is None:
        return None
    observed = {}
    for snap in (primary, alternate):
        for direction in ("inbound", "outbound"):
            for item in snap[direction]:
                mid = item["id"]
                evidence = (item["timestamp"], item["fromMe"])
                if mid in observed and observed[mid] != evidence:
                    return None
                observed[mid] = evidence
    incoming = [{"id": mid, "timestamp": stamp, "fromMe": from_me}
                for mid, (stamp, from_me) in observed.items() if not from_me]
    outgoing = [{"id": mid, "timestamp": stamp, "fromMe": from_me}
                for mid, (stamp, from_me) in observed.items() if from_me]
    return {"senderId": sender, "complete": True, "since": primary["since"],
            "checkedAt": primary["checkedAt"],
            "inbound": incoming, "outbound": outgoing}
