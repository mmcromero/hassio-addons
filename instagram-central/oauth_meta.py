"""Meta Unified Login OAuth, disabled unless explicitly enabled in local HA options.

No Meta messaging, webhook activation, WooCommerce or n8n calls. All responses
and error messages are token-free. Credentials stay in /data, never in Git.
"""
import hashlib
import hmac
import json
import os
import re
import secrets
import socket
import ssl
import time
from pathlib import Path
from urllib.parse import urlencode, urlsplit, parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

from cryptography.fernet import Fernet

AUTHORIZE = "https://www.facebook.com/dialog/oauth"
MAX_TOKEN_BYTES = 32768
STATE_TTL = 600
KEY_FILENAME = "meta-oauth-fernet.key"
TOKEN_FILENAME = "meta-oauth-token.enc"


class OAuthError(Exception):
    """Safe user-facing error; never include provider data, code or token."""


class OAuthExchangeError(OAuthError):
    """Only enum reasons and bounded integers may cross the logging boundary."""
    def __init__(self, kind, *, http_status=None, provider_code=None, provider_subcode=None):
        super().__init__("Meta authorization exchange failed")
        allowed = {"http", "tls", "timeout", "dns", "network", "invalid_json", "provider", "response"}
        self.kind = kind if kind in allowed else "network"
        self.http_status = http_status if type(http_status) is int and 100 <= http_status <= 599 else None
        self.provider_code = _safe_number(provider_code)
        self.provider_subcode = _safe_number(provider_subcode)

    def safe_details(self):
        return (f"kind={self.kind} http_status={self.http_status} "
                f"provider_code={self.provider_code} provider_subcode={self.provider_subcode}")


def _safe_number(value):
    return value if type(value) is int and 0 <= value <= 2**31 - 1 else None


def _provider_numbers(obj):
    error = obj.get("error") if isinstance(obj, dict) else None
    if not isinstance(error, dict):
        return {}
    return {"provider_code": _safe_number(error.get("code")),
            "provider_subcode": _safe_number(error.get("error_subcode"))}


def _transport_kind(reason):
    if isinstance(reason, ssl.SSLError):
        return "tls"
    if isinstance(reason, (TimeoutError, socket.timeout)):
        return "timeout"
    if isinstance(reason, socket.gaierror):
        return "dns"
    return "network"


def is_ready(cfg):
    if cfg.get("meta_oauth_enabled") is not True:
        return False
    if not all(isinstance(cfg.get(k), str) and cfg[k].isdigit()
               and 8 <= len(cfg[k]) <= 30 for k in ("meta_app_id", "meta_login_config_id")):
        return False
    if not isinstance(cfg.get("meta_app_secret"), str) or len(cfg["meta_app_secret"]) < 16:
        return False
    uri = cfg.get("meta_oauth_redirect_uri")
    if not isinstance(uri, str) or len(uri) > 600:
        return False
    try:
        parts = urlsplit(uri)
        port = parts.port
    except ValueError:
        return False
    if not parts.hostname or parts.hostname in ("localhost",) or parts.hostname.endswith(".local"):
        return False
    if port is not None and not 1 <= port <= 65535:
        return False
    if (parts.scheme != "https" or not parts.hostname or parts.username or parts.password
            or parts.query or parts.fragment or parts.path != "/oauth/meta/callback"):
        return False
    if not re.fullmatch(r"[A-Za-z0-9.-]+", parts.hostname):
        return False
    version = cfg.get("meta_graph_version", "")
    return isinstance(version, str) and re.fullmatch(r"v[0-9]{1,2}\.0", version) is not None


def prepare_schema(conn):
    # Serialize additive upgrades when two tabs start immediately after update.
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("""CREATE TABLE IF NOT EXISTS meta_oauth_states (
            digest TEXT PRIMARY KEY, expires_at INTEGER NOT NULL,
            consumed_at INTEGER)""")
        columns = {row[1] for row in conn.execute("PRAGMA table_info(meta_oauth_states)")}
        for column, definition in (("business_id", "TEXT NOT NULL DEFAULT 'umdoislab'"),
                                   ("instagram_account_id", "TEXT NOT NULL DEFAULT ''"),
                                   ("authorization_context", "TEXT NOT NULL DEFAULT ''")):
            if column not in columns:
                conn.execute("ALTER TABLE meta_oauth_states ADD COLUMN " + column + " " + definition)
        if owns_transaction:
            conn.commit()
    except BaseException:
        if owns_transaction:
            conn.rollback()
        raise

def _authorization_context(cfg):
    # No secrets in this fingerprint. Config changes cannot silently redirect an
    # already-issued authorization to another app, account, callback or version.
    fields = ("meta_app_id", "meta_login_config_id", "meta_oauth_redirect_uri",
              "meta_graph_version", "business_id", "instagram_account_id",
              "instagram_expected_username")
    public = {key: cfg.get(key) for key in fields}
    return hashlib.sha256(json.dumps(public, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def start(conn, cfg, now=None):
    if not is_ready(cfg):
        raise OAuthError("OAuth disabled or incomplete")
    now = int(time.time()) if now is None else int(now)
    state = secrets.token_urlsafe(32)
    digest = hashlib.sha256(state.encode()).hexdigest()
    prepare_schema(conn)
    conn.execute("DELETE FROM meta_oauth_states WHERE expires_at < ?", (now - 3600,))
    conn.execute("""INSERT INTO meta_oauth_states
        (digest,expires_at,business_id,instagram_account_id,authorization_context) VALUES (?,?,?,?,?)""",
        (digest, now + STATE_TTL, cfg.get("business_id", "umdoislab"),
         cfg.get("instagram_account_id") or "", _authorization_context(cfg)))
    query = urlencode({
        "client_id": cfg["meta_app_id"],
        "config_id": cfg["meta_login_config_id"],
        "redirect_uri": cfg["meta_oauth_redirect_uri"],
        "response_type": "code",
        "override_default_response_type": "true",
        "state": state,
    })
    cookie_name = _state_cookie_name(state)
    cookie = cookie_name + "=" + state + "; Max-Age=600; Path=/oauth/meta/callback; Secure; HttpOnly; SameSite=Lax"
    return AUTHORIZE + "?" + query, cookie


def _state_cookie_name(state):
    """Give each OAuth attempt its own cookie, so concurrent tabs cannot overwrite state."""
    digest = hashlib.sha256(state.encode("ascii")).hexdigest()
    return "ig_oauth_state_" + digest[:32]


def parse_callback(query, cookie_header):
    """Require the cookie bound to this exact state; concurrent flows stay isolated."""
    if not isinstance(query, str) or len(query) > 8192:
        raise OAuthError("Invalid OAuth callback")
    try:
        qs = parse_qs(query, keep_blank_values=True, max_num_fields=10)
    except ValueError:
        raise OAuthError("Invalid OAuth callback") from None
    if any(len(values) != 1 for values in qs.values()):
        raise OAuthError("Invalid OAuth callback")
    if "error" in qs:
        raise OAuthError("Authorization cancelled or refused")
    if set(qs) != {"state", "code"}:
        raise OAuthError("Invalid OAuth callback")
    state, code = qs["state"][0], qs["code"][0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{40,100}", state):
        raise OAuthError("Invalid OAuth state")
    if not isinstance(code, str) or not 1 <= len(code) <= 2048:
        raise OAuthError("Invalid authorization code")
    # Never use user-provided redirect_uri, app IDs or account IDs from callback.
    cookie_values = _state_cookie_values(state, cookie_header)
    if not cookie_values:
        raise OAuthError("OAuth state cookie missing")
    if len(cookie_values) > 1:
        raise OAuthError("OAuth state cookie duplicated")
    if not hmac.compare_digest(state, cookie_values[0]):
        raise OAuthError("OAuth browser state mismatch")
    return state, code



def _state_cookie_values(state, cookie_header):
    """Read only the cookie bound to this state; shared by OAuth and safe probe."""
    cookie_prefix = _state_cookie_name(state) + "="
    return [item.strip().split("=", 1)[1]
            for item in (cookie_header or "").split(";")
            if item.strip().startswith(cookie_prefix) and "=" in item]


def cookie_diagnostics(query, cookie_header, *, probe=False):
    """Static keys, booleans and capped counts only; never return cookie values/names."""
    header = cookie_header if isinstance(cookie_header, str) else ""
    pairs = [item.strip().partition("=")[0] for item in header.split(";") if "=" in item]
    expected_count = 0
    query_valid = False
    try:
        if isinstance(query, str) and len(query) <= 8192:
            values = parse_qs(query, keep_blank_values=True, max_num_fields=10)
            key = "probe" if probe else "state"
            candidates = values.get(key, [])
            pattern = r"[A-Za-z0-9_-]{43}" if probe else r"[A-Za-z0-9_-]{40,100}"
            if len(candidates) == 1 and re.fullmatch(pattern, candidates[0]):
                query_valid = True
                expected_count = min(3, len(_state_cookie_values(candidates[0], header)))
    except ValueError:
        pass
    return {"cookie_header_present": bool(header.strip()),
            "state_cookie_present": any(name.startswith("ig_oauth_state_") for name in pairs),
            "legacy_cookie_present": any(name in ("ig_oauth_state", "ig_oauth_probe") for name in pairs),
            "expected_cookie_present": expected_count > 0,
            "expected_cookie_count": expected_count,
            "query_state_valid": query_valid}


def start_cookie_probe(cfg):
    """Exercise the exact per-state cookie format without contacting Meta."""
    if not is_ready(cfg):
        raise OAuthError("OAuth disabled or incomplete")
    nonce = secrets.token_urlsafe(32)
    callback = cfg["meta_oauth_redirect_uri"] + "?probe=" + nonce
    cookie_name = _state_cookie_name(nonce)
    cookie = (cookie_name + "=" + nonce +
              "; Max-Age=60; Path=/oauth/meta/callback; Secure; HttpOnly; SameSite=Lax")
    return callback, cookie


def check_cookie_probe(query, cookie_header):
    """Check the same state-derived cookie name/value used by the OAuth callback."""
    if not isinstance(query, str) or len(query) > 128:
        raise OAuthError("OAuth cookie probe invalid")
    try:
        qs = parse_qs(query, keep_blank_values=True, max_num_fields=2)
    except ValueError:
        raise OAuthError("OAuth cookie probe invalid") from None
    if set(qs) != {"probe"} or len(qs["probe"]) != 1:
        raise OAuthError("OAuth cookie probe invalid")
    nonce = qs["probe"][0]
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}", nonce):
        raise OAuthError("OAuth cookie probe invalid")
    cookies = _state_cookie_values(nonce, cookie_header)
    if not cookies:
        raise OAuthError("OAuth cookie probe missing")
    if len(cookies) > 1:
        raise OAuthError("OAuth cookie probe duplicated")
    if not hmac.compare_digest(cookies[0], nonce):
        raise OAuthError("OAuth cookie probe mismatch")
    return True


def consume_state(conn, state, now=None, *, cfg=None):
    cfg = cfg or {}
    now = int(time.time()) if now is None else int(now)
    digest = hashlib.sha256(state.encode()).hexdigest()
    prepare_schema(conn)
    conn.execute("BEGIN IMMEDIATE")
    found = conn.execute("""UPDATE meta_oauth_states SET consumed_at=?
      WHERE digest=? AND consumed_at IS NULL AND expires_at>=?
        AND business_id=? AND instagram_account_id=? AND authorization_context=?""",
      (now, digest, now, cfg.get("business_id", "umdoislab"), cfg.get("instagram_account_id") or "",
       _authorization_context(cfg)))
    if found.rowcount != 1:
        raise OAuthError("OAuth state expired, already used or configuration changed")


def exchange_code(code, cfg, opener=None):
    """Only one fixed official Graph endpoint; no arbitrary callback URLs."""
    if not is_ready(cfg):
        raise OAuthError("OAuth disabled or incomplete")
    if opener is None:
        opener = urlopen
    # Unified Login documentation specifies GET for the Business Integration
    # System User token exchange. The URL is strictly server-side and never logged.
    params = urlencode({
        "client_id": cfg["meta_app_id"], "client_secret": cfg["meta_app_secret"],
        "redirect_uri": cfg["meta_oauth_redirect_uri"],
        "code": code
    })
    version = cfg["meta_graph_version"]
    req = Request("https://graph.facebook.com/" + version + "/oauth/access_token?" + params,
                  method="GET", headers={"Accept": "application/json"})
    try:
        with opener(req, timeout=12) as response:
            raw = response.read(MAX_TOKEN_BYTES + 1)
            if len(raw) > MAX_TOKEN_BYTES:
                raise OAuthExchangeError("response")
            obj = json.loads(raw)
    except HTTPError as error:
        numbers = {}
        try:
            raw = error.read(MAX_TOKEN_BYTES + 1)
            if len(raw) <= MAX_TOKEN_BYTES:
                numbers = _provider_numbers(json.loads(raw))
        except Exception:
            pass  # Never include the body, URL, message, headers or exception text.
        finally:
            error.close()
        raise OAuthExchangeError("http", http_status=error.code, **numbers) from None
    except OAuthError:
        raise
    except URLError as error:
        raise OAuthExchangeError(_transport_kind(error.reason)) from None
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise OAuthExchangeError("invalid_json") from None
    except Exception as error:
        raise OAuthExchangeError(_transport_kind(error)) from None
    if isinstance(obj, dict) and "error" in obj:
        raise OAuthExchangeError("provider", **_provider_numbers(obj))
    token = obj.get("access_token") if isinstance(obj, dict) else None
    if not isinstance(token, str) or not 20 <= len(token) <= 8192:
        raise OAuthError("Invalid Meta token response")
    # A token is not proof of access to the desired IG account.
    expiry = obj.get("expires_in")
    if expiry is not None and (not isinstance(expiry, int) or isinstance(expiry, bool)
                               or expiry < 0):
        raise OAuthError("Invalid Meta expiry response")
    return {"access_token": token, "expires_in": expiry, "received_at": int(time.time())}


def _private_key(folder):
    folder = Path(folder)
    folder.mkdir(mode=0o700, parents=True, exist_ok=True)
    path = folder / KEY_FILENAME
    if path.exists():
        if path.is_symlink() or not path.is_file():
            raise OAuthError("Invalid local key")
        if os.name == "posix" and (path.stat().st_mode & 0o077):
            raise OAuthError("Local key permissions too broad")
        raw = path.read_bytes()
        Fernet(raw)
        return raw
    key = Fernet.generate_key()
    try:
        fd = os.open(str(path), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return _private_key(folder)
    with os.fdopen(fd, "wb") as stream:
        stream.write(key)
    return key


def store_token(folder, credential):
    """Encrypted at rest with a separate local 0600 key; no plaintext writes."""
    key = _private_key(folder)
    encrypted = Fernet(key).encrypt(json.dumps(credential).encode("utf-8"))
    target = Path(folder) / TOKEN_FILENAME
    tmp = Path(folder) / (TOKEN_FILENAME + "." + secrets.token_hex(8) + ".tmp")
    fd = os.open(str(tmp), os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, target)
    finally:
        if tmp.exists():
            tmp.unlink()


def token_exists(folder):
    return (Path(folder) / TOKEN_FILENAME).is_file()


def load_token(folder):
    """Decrypt stored credential only inside the server, never via HTTP."""
    path = Path(folder) / TOKEN_FILENAME
    if not path.exists():
        return None
    try:
        if path.is_symlink() or not path.is_file():
            raise OAuthError("Invalid credential file")
        if os.name == "posix" and (path.stat().st_mode & 0o077):
            raise OAuthError("Credential permissions too broad")
        raw = path.read_bytes()
        obj = json.loads(Fernet(_private_key(folder)).decrypt(raw))
        if not isinstance(obj, dict) or not isinstance(obj.get("access_token"), str):
            raise OAuthError("Invalid credential")
        return obj
    except OAuthError:
        raise
    except Exception:
        raise OAuthError("Credential cannot be decrypted") from None
