"""Authenticated local state transitions for the Instagram laboratory panel."""
import hashlib
import hmac
import json
import time
from urllib.parse import parse_qs

STATES = ("bot", "pending", "human", "done")


def token_for(account, sender, state, password, bucket=None):
    """Action-scoped CSRF token, valid for a 5-minute time bucket."""
    if not isinstance(password, str) or len(password) < 16 or state not in STATES:
        return ""
    if bucket is None:
        bucket = int(time.time() // 300)
    raw = json.dumps([account, sender, state, bucket], separators=(",", ":")).encode("utf-8")
    return hmac.new(password.encode("utf-8"), raw, hashlib.sha256).hexdigest()


def token_valid(account, sender, state, token, password):
    if not isinstance(token, str) or len(token) != 64:
        return False
    bucket = int(time.time() // 300)
    return any(hmac.compare_digest(token, token_for(account, sender, state, password, b))
               for b in (bucket, bucket - 1))


def parse_action(body, password):
    """Validate a form; caller must authenticate the Basic user first."""
    if not isinstance(body, bytes) or len(body) > 4096:
        return None
    try:
        fields = parse_qs(body.decode("utf-8"), keep_blank_values=True, max_num_fields=4)
    except (ValueError, UnicodeDecodeError):
        return None
    if set(fields) != {"accountId", "senderId", "state", "csrf"}:
        return None
    if any(len(values) != 1 for values in fields.values()):
        return None
    account, sender, state, csrf = (fields[k][0] for k in ("accountId", "senderId", "state", "csrf"))
    if not (1 <= len(account) <= 160 and 1 <= len(sender) <= 160):
        return None
    if account == sender or state not in STATES:
        return None
    if not token_valid(account, sender, state, csrf, password):
        return None
    return {"accountId": account, "senderId": sender, "state": state}
