"""Local browser login for the Instagram Central panel.

Sessions are random bearer tokens. Only an HMAC digest of each token is
persisted in SQLite. Session validity is bound to panel_password, so changing
the password invalidates existing sessions. No Meta or n8n access.
"""
import hashlib
import hmac
from http.cookies import SimpleCookie
import re
import secrets
import threading
import time

COOKIE_NAME = "ig_panel_session"
SESSION_SECONDS = 12 * 60 * 60
TOKEN_PATTERN = re.compile(r"^[A-Za-z0-9_-]{43}$")
_ATTEMPTS = {}
_ATTEMPTS_LOCK = threading.Lock()
_MAX_FAILURES = 8
_FAILURE_WINDOW = 120


def _valid_password(password):
    return isinstance(password, str) and len(password) >= 16


def _digest(token, password):
    # Derived from password but never stores its raw value or plain session token.
    return hmac.new(password.encode("utf-8"),
                    ("instagram-panel-v1:" + token).encode("ascii"),
                    hashlib.sha256).hexdigest()


def prepare(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS panel_sessions (
        session_digest TEXT PRIMARY KEY,
        expires_at INTEGER NOT NULL
    )""")


def create_session(conn, password, now=None):
    if not _valid_password(password):
        raise ValueError("panel password is not configured")
    now = int(time.time()) if now is None else int(now)
    prepare(conn)
    conn.execute("DELETE FROM panel_sessions WHERE expires_at <= ?", (now,))
    token = secrets.token_urlsafe(32)
    conn.execute("INSERT INTO panel_sessions(session_digest,expires_at) VALUES(?,?)",
                 (_digest(token, password), now + SESSION_SECONDS))
    return token


def cookie_token(cookie_header):
    if not isinstance(cookie_header, str) or len(cookie_header) > 8192:
        return None
    try:
        cookies = SimpleCookie()
        cookies.load(cookie_header)
        morsel = cookies.get(COOKIE_NAME)
        token = morsel.value if morsel is not None else None
    except Exception:
        return None
    return token if isinstance(token, str) and TOKEN_PATTERN.fullmatch(token) else None


def valid_session(conn, cookie_header, password, now=None):
    if not _valid_password(password):
        return False
    token = cookie_token(cookie_header)
    if token is None:
        return False
    now = int(time.time()) if now is None else int(now)
    prepare(conn)
    found = conn.execute("""SELECT 1 FROM panel_sessions
      WHERE session_digest=? AND expires_at>?""", (_digest(token, password), now)).fetchone()
    return found is not None


def revoke_session(conn, cookie_header, password):
    token = cookie_token(cookie_header)
    if token is None or not _valid_password(password):
        return
    prepare(conn)
    conn.execute("DELETE FROM panel_sessions WHERE session_digest=?",
                 (_digest(token, password),))


def set_cookie_header(token, secure=False):
    if TOKEN_PATTERN.fullmatch(token) is None:
        raise ValueError("invalid session token")
    return (f"{COOKIE_NAME}={token}; Path=/; Max-Age={SESSION_SECONDS}; "
            "HttpOnly; SameSite=Strict" + ("; Secure" if secure else ""))


def clear_cookie_header(secure=False):
    return (f"{COOKIE_NAME}=; Path=/; Max-Age=0; "
            "HttpOnly; SameSite=Strict" + ("; Secure" if secure else ""))


def allowed_attempt(client_id, now=None):
    now = int(time.time()) if now is None else int(now)
    with _ATTEMPTS_LOCK:
        count, start = _ATTEMPTS.get(client_id, (0, now))
        if now - start >= _FAILURE_WINDOW:
            _ATTEMPTS.pop(client_id, None)
            return True
        return count < _MAX_FAILURES


def failed_attempt(client_id, now=None):
    now = int(time.time()) if now is None else int(now)
    with _ATTEMPTS_LOCK:
        count, start = _ATTEMPTS.get(client_id, (0, now))
        if now - start >= _FAILURE_WINDOW:
            count, start = 0, now
        _ATTEMPTS[client_id] = (count + 1, start)
        if len(_ATTEMPTS) > 2048:
            # Do not allow arbitrary requests to grow process memory forever.
            _ATTEMPTS.clear()


def successful_attempt(client_id):
    with _ATTEMPTS_LOCK:
        _ATTEMPTS.pop(client_id, None)
