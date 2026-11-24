"""Account-scoped allow/exclude policy for Instagram automatic assistance."""
import re
from datetime import datetime, timezone

_ID = re.compile(r"^[0-9]{1,30}$")
_MODES = {"tests", "all"}


class PolicyError(ValueError):
    pass


def ensure_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS automation_policy (
      recipient_id TEXT PRIMARY KEY,
      mode TEXT NOT NULL DEFAULT 'tests' CHECK(mode IN ('tests','all')),
      updated_at TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS automation_contacts (
      recipient_id TEXT NOT NULL,
      sender_id TEXT NOT NULL,
      category TEXT NOT NULL CHECK(category IN ('test','excluded')),
      created_at TEXT NOT NULL,
      PRIMARY KEY(recipient_id,sender_id,category)
    )""")


def normalize_ids(values):
    if isinstance(values, str):
        values = re.split(r"[,;\s]+", values)
    if not isinstance(values, (list, tuple, set)):
        raise PolicyError("invalid profile list")
    result = []
    for raw in values:
        value = str(raw).strip()
        if not value:
            continue
        if not _ID.fullmatch(value):
            raise PolicyError("profile IDs must be numeric Instagram-scoped IDs")
        if value not in result:
            result.append(value)
    if len(result) > 300:
        raise PolicyError("profile list limit exceeded")
    return result


def snapshot(conn, recipient_id):
    if not isinstance(recipient_id, str) or not recipient_id:
        raise PolicyError("invalid account")
    row = conn.execute(
        "SELECT mode,updated_at FROM automation_policy WHERE recipient_id=?",
        (recipient_id,)).fetchone()
    mode = row[0] if row else "tests"
    contacts = {"test": [], "excluded": []}
    for sender_id, category in conn.execute(
        "SELECT sender_id,category FROM automation_contacts WHERE recipient_id=? ORDER BY sender_id",
        (recipient_id,)):
        contacts[category].append(sender_id)
    return {"mode": mode, "test": contacts["test"], "excluded": contacts["excluded"],
            "updatedAt": row[1] if row else None}


def allowed(conn, recipient_id, sender_id):
    if (not isinstance(recipient_id, str) or not recipient_id or
            not isinstance(sender_id, str) or not _ID.fullmatch(sender_id) or
            sender_id == recipient_id):
        return False
    policy = snapshot(conn, recipient_id)
    if sender_id in policy["excluded"]:
        return False
    if policy["mode"] == "all":
        return True
    return sender_id in policy["test"]


def save(conn, recipient_id, mode, test_ids, excluded_ids):
    if not isinstance(recipient_id, str) or not recipient_id:
        raise PolicyError("invalid account")
    if mode not in _MODES:
        raise PolicyError("invalid mode")
    tests = normalize_ids(test_ids)
    excluded = normalize_ids(excluded_ids)
    if recipient_id in tests or recipient_id in excluded:
        raise PolicyError("business account cannot be a test or excluded sender")
    now = datetime.now(timezone.utc).isoformat()
    conn.execute("""INSERT INTO automation_policy(recipient_id,mode,updated_at)
      VALUES(?,?,?) ON CONFLICT(recipient_id) DO UPDATE SET
      mode=excluded.mode,updated_at=excluded.updated_at""", (recipient_id, mode, now))
    conn.execute("DELETE FROM automation_contacts WHERE recipient_id=?", (recipient_id,))
    conn.executemany("""INSERT INTO automation_contacts
      (recipient_id,sender_id,category,created_at) VALUES(?,?,?,?)""",
      [(recipient_id, sender, category, now)
       for category, values in (("test", tests), ("excluded", excluded))
       for sender in values])
    return snapshot(conn, recipient_id)
