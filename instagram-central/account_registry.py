"""Multi-account identity registry for one Instagram Central installation.

No network, tokens or Meta calls. The existing @umdoislab identity is bootstrapped
without changing existing message keys or SQLite records. Future account creation
is an internal operation only; there is deliberately no HTTP registration route.
"""
from pathlib import Path
import re
import sqlite3

PRIMARY_BUSINESS = "umdoislab"
_BUSINESS_ID = re.compile(r"[a-z][a-z0-9_-]{1,39}\Z")
# Meta IDs are numeric in production; synthetic IDs are allowed for offline tests.
_META_ID = re.compile(r"[A-Za-z0-9_-]{1,160}\Z")


class RegistryError(ValueError):
    """Invalid account, identity change or unauthorized account context."""


def valid_business_id(value):
    return isinstance(value, str) and _BUSINESS_ID.fullmatch(value) is not None


def valid_meta_id(value):
    return isinstance(value, str) and _META_ID.fullmatch(value) is not None


def prepare(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS instagram_accounts (
        business_id TEXT PRIMARY KEY,
        instagram_account_id TEXT UNIQUE,
        username TEXT NOT NULL,
        display_name TEXT NOT NULL,
        enabled INTEGER NOT NULL CHECK(enabled IN (0, 1)),
        connection_state TEXT NOT NULL DEFAULT 'pending',
        permissions_json TEXT NOT NULL DEFAULT '[]',
        created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )""")


def register(conn, business_id, instagram_account_id, username, display_name,
             *, enabled=False):
    """Internal-only provisioning; no public API or Meta account is created."""
    if (not valid_business_id(business_id) or
            not valid_meta_id(instagram_account_id) or
            not isinstance(username, str) or not 1 <= len(username) <= 80 or
            not isinstance(display_name, str) or not 1 <= len(display_name) <= 120 or
            not isinstance(enabled, bool)):
        raise RegistryError("Invalid account record")
    prepare(conn)
    try:
        conn.execute("""INSERT INTO instagram_accounts
          (business_id,instagram_account_id,username,display_name,enabled)
          VALUES (?,?,?,?,?)""", (business_id, instagram_account_id,
                                   username.lstrip("@"), display_name, int(enabled)))
    except sqlite3.IntegrityError:
        raise RegistryError("Account already registered") from None


def ensure_primary(conn, instagram_account_id=None):
    """Bind the legacy Umdoislab account once; never overwrite another IG ID.

    With an empty config, insert an unbound record; once a verified IG ID is
    configured, bind it. Existing messages continue using official recipient_id.
    """
    if instagram_account_id in (None, ""):
        instagram_account_id = None
    elif not valid_meta_id(instagram_account_id):
        raise RegistryError("Invalid Instagram account ID")
    prepare(conn)
    row = conn.execute("""SELECT instagram_account_id FROM instagram_accounts
             WHERE business_id=?""", (PRIMARY_BUSINESS,)).fetchone()
    if row is None:
        try:
            conn.execute("""INSERT INTO instagram_accounts
              (business_id,instagram_account_id,username,display_name,enabled)
              VALUES (?,?,?,?,1)""", (PRIMARY_BUSINESS, instagram_account_id,
                                       "umdoislab", "Umdoislab"))
        except sqlite3.IntegrityError:
            raise RegistryError("Instagram account already used by another business") from None
    elif row[0] is None and instagram_account_id is not None:
        try:
            conn.execute("""UPDATE instagram_accounts SET instagram_account_id=?
               WHERE business_id=? AND instagram_account_id IS NULL""",
               (instagram_account_id, PRIMARY_BUSINESS))
        except sqlite3.IntegrityError:
            raise RegistryError("Instagram account already used by another business") from None
    elif row[0] is not None and instagram_account_id is not None and row[0] != instagram_account_id:
        raise RegistryError("Legacy account remapping requires reviewed migration")


def resolve_meta(conn, instagram_account_id):
    if not valid_meta_id(instagram_account_id):
        return None
    prepare(conn)
    row = conn.execute("""SELECT business_id,instagram_account_id,username,
      display_name,enabled,connection_state,permissions_json FROM instagram_accounts
      WHERE instagram_account_id=? AND enabled=1""", (instagram_account_id,)).fetchone()
    if row is None:
        return None
    keys = ("business_id", "instagram_account_id", "username", "display_name",
            "enabled", "connection_state", "permissions_json")
    return dict(zip(keys, row))


def active_meta_ids(conn):
    prepare(conn)
    return frozenset(r[0] for r in conn.execute("""SELECT instagram_account_id
       FROM instagram_accounts WHERE enabled=1 AND instagram_account_id IS NOT NULL"""))


def require_business(conn, business_id):
    if not valid_business_id(business_id):
        raise RegistryError("Invalid business identifier")
    prepare(conn)
    row = conn.execute("""SELECT business_id,instagram_account_id,username,
       enabled FROM instagram_accounts WHERE business_id=? AND enabled=1""",
       (business_id,)).fetchone()
    if row is None:
        raise RegistryError("Business not enabled")
    return {"business_id": row[0], "instagram_account_id": row[1],
            "username": row[2], "enabled": bool(row[3])}


def editorial_root(data_root, business_id):
    """Preserve /data/editorial for Umdoislab, isolate future accounts."""
    if not valid_business_id(business_id):
        raise RegistryError("Invalid business identifier")
    base = Path(data_root) / "editorial"
    return base if business_id == PRIMARY_BUSINESS else base / "accounts" / business_id


def credential_root(data_root, business_id):
    """Keep pre-existing Umdoislab Fernet key/token paths unchanged."""
    if not valid_business_id(business_id):
        raise RegistryError("Invalid business identifier")
    base = Path(data_root)
    return base if business_id == PRIMARY_BUSINESS else base / "accounts" / business_id
