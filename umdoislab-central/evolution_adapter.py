"""Adaptador puro Evolution messages.upsert -> evento canônico da Central.

Não recebe HTTP nem envia mensagens. Falha fechada para eventos não suportados.
A autenticação do webhook deve ser feita na borda, antes deste adaptador.
"""
import re

def normalize_evolution(payload, expected_instance="umdoislab"):
    if not isinstance(payload, dict):
        return None
    if payload.get("event") != "messages.upsert" or payload.get("instance") != expected_instance:
        return None
    data = payload.get("data")
    if not isinstance(data, dict):
        return None
    key = data.get("key")
    if not isinstance(key, dict) or key.get("fromMe") is not False:
        return None
    remote = key.get("remoteJid")
    if not isinstance(remote, str) or not re.fullmatch(r"[0-9]{10,15}@s\.whatsapp\.net", remote):
        return None
    message_id = key.get("id")
    if not isinstance(message_id, str) or not 1 <= len(message_id) <= 160:
        return None
    msg = data.get("message")
    if not isinstance(msg, dict):
        return None
    text = msg.get("conversation")
    if not isinstance(text, str):
        ext = msg.get("extendedTextMessage")
        text = ext.get("text") if isinstance(ext, dict) else None
    if not isinstance(text, str) or not text.strip():
        return None
    sender_name = data.get("pushName")
    if not isinstance(sender_name, str):
        sender_name = "Contato"
    return {
        "instance": expected_instance,
        "isClientMessage": True,
        "isGroup": False,
        "senderId": remote,
        "senderName": sender_name[:100],
        "messageId": message_id,
        "messageText": text[:500],
        "category": "outros",
        "summary": "",
        "handoffRequested": False,
    }
