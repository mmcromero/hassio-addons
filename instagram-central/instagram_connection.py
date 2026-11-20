"""Meta Unified Login Graph calls for an Instagram professional account.

Only the fixed graph.facebook.com host is used. No Direct send, n8n or
WhatsApp API exists here. Provider responses and authorization tokens are
never logged or reflected to the browser.
"""
import json
import re
import time
from urllib.parse import urlencode
from urllib.request import Request, urlopen

MAX_GRAPH_RESPONSE = 64 * 1024
GRAPH_VERSION = re.compile(r"v[0-9]{1,2}\.0\Z")
IG_ACCOUNT = re.compile(r"[0-9]{8,30}\Z")


class ConnectionError(Exception):
    """Sanitized provider error, without credentials or response content."""


def request_graph(version, path, token, method="GET", fields=None, opener=urlopen):
    if not GRAPH_VERSION.fullmatch(str(version or "")):
        raise ConnectionError("Invalid Meta Graph version")
    if not isinstance(token, str) or not 20 <= len(token) <= 8192:
        raise ConnectionError("Token not configured")
    # Never accept a caller-provided host, URL or arbitrary Graph path.
    if path in ("/me/assigned_instagram_accounts", "/me"):
        if method != "GET":
            raise ConnectionError("Graph method not permitted")
    elif not (re.fullmatch(r"/[0-9]{8,30}/subscribed_apps", path) and method == "POST"):
        raise ConnectionError("Graph request not permitted")
    if method not in ("GET", "POST"):
        raise ConnectionError("Graph method not permitted")
    if fields is None:
        fields = {}
    if not isinstance(fields, dict):
        raise ConnectionError("Invalid Graph fields")
    params = urlencode(fields)
    url = "https://graph.facebook.com/" + version + path
    data = None
    if method == "GET":
        if params:
            url += "?" + params
    else:
        data = params.encode("ascii")
    req = Request(url, data=data, method=method, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/json",
        "Content-Type": "application/x-www-form-urlencoded"})
    try:
        with opener(req, timeout=12) as response:
            raw = response.read(MAX_GRAPH_RESPONSE + 1)
        if len(raw) > MAX_GRAPH_RESPONSE:
            raise ConnectionError("Meta response too large")
        obj = json.loads(raw)
    except ConnectionError:
        raise
    except Exception:
        raise ConnectionError("Meta request failed") from None
    if not isinstance(obj, dict) or "error" in obj:
        raise ConnectionError("Meta declined the request")
    return obj


def verify_access(cfg, token, opener=urlopen):
    """Check exact IG asset assigned to a Unified Login system-user token."""
    expected_id = cfg.get("instagram_account_id")
    if not isinstance(expected_id, str) or not IG_ACCOUNT.fullmatch(expected_id):
        raise ConnectionError("Instagram account not configured")
    version = cfg.get("meta_graph_version")
    accounts = request_graph(version, "/me/assigned_instagram_accounts", token,
        fields={"fields": "id,username", "limit": "100"}, opener=opener)
    entries = accounts.get("data")
    if not isinstance(entries, list) or len(entries) > 100:
        raise ConnectionError("Invalid Meta account list")
    matches = [item for item in entries if isinstance(item, dict)
               and item.get("id") == expected_id]
    if len(matches) != 1:
        raise ConnectionError("Expected Instagram account was not granted")
    username = matches[0].get("username")
    if not isinstance(username, str) or username.lower().lstrip("@") != "umdoislab":
        raise ConnectionError("Instagram account name mismatch")
    business = request_graph(version, "/me", token,
        fields={"fields": "client_business_id"}, opener=opener)
    business_id = business.get("client_business_id")
    if not isinstance(business_id, str) or not IG_ACCOUNT.fullmatch(business_id):
        raise ConnectionError("Business portfolio access not verified")
    return {"account_id": expected_id, "username": username,
            "client_business_id": business_id, "verified_at": int(time.time())}


def subscribe_messages(cfg, credential, opener=urlopen):
    """Opt-in subscribe only to messages; never sends customer messages."""
    account_id = cfg.get("instagram_account_id")
    if not isinstance(account_id, str) or not IG_ACCOUNT.fullmatch(account_id):
        raise ConnectionError("Instagram account not configured")
    if not isinstance(credential, dict) or credential.get("account_id") != account_id:
        raise ConnectionError("Account must be verified")
    if not (isinstance(cfg.get("meta_verify_token"), str) and len(cfg["meta_verify_token"]) >= 24
            and isinstance(cfg.get("meta_app_secret"), str) and len(cfg["meta_app_secret"]) >= 16
            and cfg.get("ingress_enabled") is True):
        raise ConnectionError("Webhook not enabled or verified")
    data = request_graph(cfg.get("meta_graph_version"),
        "/" + account_id + "/subscribed_apps", credential.get("access_token"),
        method="POST", fields={"subscribed_fields": "messages"}, opener=opener)
    if data.get("success") is not True:
        raise ConnectionError("Meta subscription was not accepted")
    return int(time.time())


def credential_status(credential, cfg):
    """Never claim live webhooks or messaging from the mere existence of a token."""
    if not isinstance(credential, dict):
        return {"account_verified": False, "subscription_requested": False}
    account_id = cfg.get("instagram_account_id")
    username = credential.get("username")
    verified = (isinstance(account_id, str)
                and credential.get("account_id") == account_id
                and isinstance(username, str) and username.lower() == "umdoislab"
                and isinstance(credential.get("verified_at"), int)
                and credential["verified_at"] > 0)
    return {"account_verified": bool(verified),
            "subscription_requested": bool(verified and credential.get("subscribed_at"))}
