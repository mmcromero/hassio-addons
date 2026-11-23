"""Explicit multi-account grants; independent of legacy per-account keys."""
import hashlib
import hmac
import json
import re
import secrets
import sqlite3
import time
import unicodedata
from contextlib import contextmanager

TOKEN = re.compile(r'cei2\.([0-9a-f]{32})\.([A-Za-z0-9_-]{43})')
BUSINESS = re.compile(r'[a-z][a-z0-9_-]{1,39}')
DRIVE_ID = re.compile(r'[A-Za-z0-9_-]{10,200}')
ADMIN_ACTIONS = ('integration_multi_list', 'integration_multi_create', 'integration_multi_revoke', 'integration_multi_drive', 'integration_multi_grants')


class Denied(ValueError):
    pass


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', value.casefold())
                   if c.isalnum())


def eligible(accounts):
    result = []
    for a in accounts:
        bid = a.get('business_id')
        if (isinstance(bid, str) and BUSINESS.fullmatch(bid)
                and a.get('enabled') is True and a.get('instagram_account_id')):
            result.append({'id': bid, 'name': a.get('display_name') or bid,
                           'username': a.get('username') or '',
                           'aliases': list(a.get('aliases', []))})
    return result


class Connections:
    def __init__(self, path, accounts=None, clock=time.time, *, account_reader=None):
        self.path, self.accounts, self.clock = path, accounts, clock
        self.account_reader = account_reader

    def current_accounts(self, db):
        return eligible(self.account_reader(db) if self.account_reader is not None else self.accounts())

    @contextmanager
    def transaction(self):
        db = sqlite3.connect(self.path, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        try:
            db.execute('BEGIN IMMEDIATE')
            db.execute('''CREATE TABLE IF NOT EXISTS editorial_connections (
                id TEXT PRIMARY KEY, label TEXT NOT NULL, digest TEXT NOT NULL,
                scope TEXT NOT NULL, grants TEXT NOT NULL, expires INTEGER NOT NULL,
                revoked INTEGER NOT NULL DEFAULT 0)''')
            if 'drive_root' not in {r[1] for r in db.execute('PRAGMA table_info(editorial_connections)')}:
                db.execute("ALTER TABLE editorial_connections ADD COLUMN drive_root TEXT NOT NULL DEFAULT ''")
            yield db
            db.commit()
        except BaseException:
            db.rollback()
            raise
        finally:
            db.close()

    def create(self, label, scope, grants, drive_root=''):
        # Call only from an authenticated, CSRF-protected owner action.
        if not isinstance(label, str) or not 1 <= len(label.strip()) <= 80:
            raise Denied('Nome inválido.')
        if scope not in ('selected', 'owner_all') or not isinstance(grants, list):
            raise Denied('Escopo inválido.')
        if any(not isinstance(x, str) or not BUSINESS.fullmatch(x) for x in grants):
            raise Denied('Conta inválida.')
        with self.transaction() as db:
            ids = {a['id'] for a in self.current_accounts(db)}
            self.check_root(db, drive_root)
            if (scope == 'selected' and (not grants or not set(grants) <= ids)
                    or scope == 'owner_all' and grants):
                raise Denied('Concessões inválidas.')
            now = int(self.clock())
            if db.execute('SELECT COUNT(*) FROM editorial_connections WHERE revoked=0 AND expires>?', (now,)).fetchone()[0] >= 20:
                raise Denied('Limite de conexões ativas.')
            cid = secrets.token_hex(16)
            token = 'cei2.' + cid + '.' + secrets.token_urlsafe(32)
            expiry = now + 90 * 86400
            db.execute('INSERT INTO editorial_connections(id,label,digest,scope,grants,expires,revoked,drive_root) VALUES(?,?,?,?,?,?,0,?)',
                       (cid, label.strip(), hashlib.sha256(token.encode()).hexdigest(),
                        scope, json.dumps(sorted(set(grants))), expiry, drive_root))
            return {'id': cid, 'token': token, 'expires': expiry, 'scope': scope}

    def list(self):
        with self.transaction() as db:
            return [dict(r) for r in db.execute('SELECT id,label,scope,grants,expires,revoked,drive_root FROM editorial_connections ORDER BY rowid DESC')]

    def check_root(self, db, root, cid=''):
        if not isinstance(root, str) or (root and not DRIVE_ID.fullmatch(root)):
            raise Denied('ID da pasta privada inválido.')
        if root and db.execute('SELECT 1 FROM editorial_connections WHERE drive_root=? AND id<>? AND revoked=0 AND expires>?',
                               (root, cid, int(self.clock()))).fetchone():
            raise Denied('Use uma pasta exclusiva para esta conexão.')

    def update_drive(self, cid, root):
        if not isinstance(cid, str) or not re.fullmatch(r'[0-9a-f]{32}', cid):
            raise Denied('Conexão inválida.')
        with self.transaction() as db:
            self.check_root(db, root, cid)
            if db.execute('UPDATE editorial_connections SET drive_root=? WHERE id=? AND revoked=0 AND expires>?',
                          (root, cid, int(self.clock()))).rowcount != 1:
                raise Denied('Conexão expirada ou revogada.')
        return {'updated': True}

    def update_grants(self, cid, grants):
        if (not isinstance(cid, str) or not re.fullmatch(r'[0-9a-f]{32}', cid)
                or not isinstance(grants, list) or not grants
                or any(not isinstance(x, str) or not BUSINESS.fullmatch(x) for x in grants)):
            raise Denied('Concessões inválidas.')
        with self.transaction() as db:
            allowed = {a['id'] for a in self.current_accounts(db)}
            if not set(grants) <= allowed:
                raise Denied('Conta não autorizada.')
            if db.execute("UPDATE editorial_connections SET grants=? WHERE id=? AND scope='selected' AND revoked=0 AND expires>?",
                          (json.dumps(sorted(set(grants))), cid, int(self.clock()))).rowcount != 1:
                raise Denied('Conexão delegada indisponível.')
        return {'updated': True}

    def revoke(self, cid):
        if not isinstance(cid, str) or not re.fullmatch(r'[0-9a-f]{32}', cid):
            raise Denied('Conexão inválida.')
        with self.transaction() as db:
            return db.execute('UPDATE editorial_connections SET revoked=1 WHERE id=?', (cid,)).rowcount == 1

    @contextmanager
    def authorize(self, token):
        # Keep the grant transaction open through the protected operation.
        # A revoke and an authorized operation are serialized across processes.
        match = TOKEN.fullmatch(token) if isinstance(token, str) else None
        if not match:
            raise Denied('Conexão não autorizada.')
        with self.transaction() as db:
            row = db.execute('SELECT * FROM editorial_connections WHERE id=? AND revoked=0 AND expires>?',
                             (match[1], int(self.clock()))).fetchone()
            if not row or not hmac.compare_digest(row['digest'], hashlib.sha256(token.encode()).hexdigest()):
                raise Denied('Conexão não autorizada.')
            accounts = self.current_accounts(db)
            if row['scope'] == 'selected':
                allowed = set(json.loads(row['grants']))
                accounts = [a for a in accounts if a['id'] in allowed]
            elif row['scope'] != 'owner_all':
                raise Denied('Conexão não autorizada.')
            yield dict(row), accounts


def resolve(accounts, destination=None):
    if destination is None:
        if len(accounts) == 1:
            return accounts[0]['id']
        raise Denied('Escolha uma conta autorizada antes de continuar.')
    if not isinstance(destination, str) or not destination.strip() or len(destination) > 160:
        raise Denied('Destino inválido.')
    exact = [a['id'] for a in accounts if a['id'] == destination]
    if len(exact) == 1:
        return exact[0]
    name = normalize(destination)
    matches = [a['id'] for a in accounts if name and name in {
        normalize(v) for v in [a['id'], a['name'], a['username'], *a['aliases']] if isinstance(v, str)}]
    if len(matches) != 1:
        raise Denied('Destino não autorizado, desconhecido ou ambíguo. Escolha pelo ID.')
    return matches[0]
