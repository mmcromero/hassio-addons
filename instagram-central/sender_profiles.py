"""Optional, account-scoped sender enrichment. Never called by the webhook."""
import html
import logging
import re
import sqlite3
import threading
import time
from urllib.parse import urlencode

import account_avatar
import instagram_connection as meta

TTL = 24 * 60 * 60
RETRY = 15 * 60
MAX_CACHE = 500
_FIELDS = {'fields': 'name,username,profile_pic'}
_LOCK = threading.Lock()  # A single optional provider lookup at a time.
_LOG = logging.getLogger('instagram-central')


def identity_html(prefix, sender):
    attr = ''
    if meta.IG_ACCOUNT.fullmatch(sender):
        url = prefix + '/panel?' + urlencode({'view': 'sender-profile', 'sender': sender})
        attr = ' data-sender-profile="' + html.escape(url, quote=True) + '"'
    return ('<div class="inbox-sender"' + attr + '><span class="inbox-sender-avatar" aria-hidden="true">'
            '<span>👤</span><img alt="" width="48" height="48" hidden></span>'
            '<div class="inbox-sender-label"><span class="inbox-label">Remetente</span>'
            '<strong data-sender-name>' + html.escape(sender) + '</strong>'
            '<small data-sender-username hidden></small></div></div>')


def _cache(database, key, epoch, now):
    with database() as conn:
        # Only the optional profile route creates this table, not the webhook.
        conn.execute('''CREATE TABLE IF NOT EXISTS sender_profiles (
            business_id TEXT NOT NULL, recipient_id TEXT NOT NULL, sender_id TEXT NOT NULL,
            credential_epoch INTEGER NOT NULL, name TEXT NOT NULL, username TEXT NOT NULL,
            photo BLOB, checked_at INTEGER NOT NULL, expires_at INTEGER NOT NULL,
            PRIMARY KEY(business_id,recipient_id,sender_id))''')
        if not conn.execute('''SELECT 1 FROM (SELECT sender_id FROM inbound WHERE recipient_id=?
                ORDER BY received_at DESC,rowid DESC LIMIT 50) WHERE sender_id=? LIMIT 1''', key[1:]).fetchone():
            return False, None
        row = conn.execute('''SELECT name,username,photo FROM sender_profiles
            WHERE business_id=? AND recipient_id=? AND sender_id=? AND credential_epoch=?
            AND checked_at<=? AND expires_at>?''', (*key, epoch, now, now)).fetchone()
        return True, row


def _save(database, key, epoch, now, row, ttl):
    with database() as conn:
        conn.execute('''DELETE FROM sender_profiles WHERE business_id=? AND recipient_id=?
            AND (expires_at<=? OR credential_epoch!=?)''', (*key[:2], now, epoch))
        conn.execute('''INSERT INTO sender_profiles VALUES(?,?,?,?,?,?,?,?,?)
            ON CONFLICT(business_id,recipient_id,sender_id) DO UPDATE SET
            credential_epoch=excluded.credential_epoch,name=excluded.name,username=excluded.username,
            photo=excluded.photo,checked_at=excluded.checked_at,expires_at=excluded.expires_at''',
            (*key, epoch, *row, now, now + ttl))
        conn.execute('''DELETE FROM sender_profiles WHERE business_id=? AND recipient_id=? AND sender_id IN
            (SELECT sender_id FROM sender_profiles WHERE business_id=? AND recipient_id=?
             ORDER BY checked_at DESC,rowid DESC LIMIT -1 OFFSET ?)''', (*key[:2], *key[:2], MAX_CACHE))


def _reply(row):
    name, username, photo = row
    return {'name': name, 'username': username, 'has_photo': bool(photo),
            'status': 'confirmed' if name or username or photo else 'unavailable'}


def get(database, cfg, credential, sender, *, image_only=False, graph=None, fetch=None, clock=time.time):
    account = cfg.get('instagram_account_id')
    business = cfg.get('business_id', 'umdoislab')
    if not (meta.IG_ACCOUNT.fullmatch(str(account or '')) and meta.IG_ACCOUNT.fullmatch(str(sender or ''))
            and sender != account and meta.credential_status(credential, cfg)['account_verified']):
        return None
    key = (business, account, sender)
    epoch, now = credential['verified_at'], int(clock())
    try:
        visible, row = _cache(database, key, epoch, now)
        if not visible:
            return None
        if image_only:
            return row[2] if row else None
        if row is not None:
            return _reply(row)
        if not _LOCK.acquire(blocking=False):
            return {'name': '', 'username': '', 'has_photo': False, 'status': 'busy'}
        try:
            visible, row = _cache(database, key, epoch, now)
            if not visible:
                return None
            if row is not None:
                return _reply(row)
            row, ttl = ('', '', None), RETRY
            try:
                result = (graph or meta.request_graph)(cfg.get('meta_graph_version'), '/' + sender,
                    credential['access_token'], fields=_FIELDS, timeout=5)
                if not isinstance(result, dict) or result.get('id', sender) != sender:
                    raise meta.GraphError('invalid_response')
                name, username, photo = result.get('name'), result.get('username'), None
                name = ' '.join(name.split()) if isinstance(name, str) and len(name) <= 160 else ''
                if any(ord(char) < 32 or 127 <= ord(char) < 160 for char in name):
                    name = ''
                username = username if isinstance(username, str) and re.fullmatch(r'[A-Za-z0-9._]{1,30}', username) else ''
                ttl = TTL if name or username else RETRY
                if result.get('profile_pic'):
                    try:
                        photo = (fetch or account_avatar.download)(result['profile_pic'])
                        if not isinstance(photo, bytes) or not 0 < len(photo) <= account_avatar.MAX_BYTES:
                            raise ValueError('Invalid thumbnail')
                    except Exception:
                        photo, ttl = None, RETRY
                row = (name, username, photo)
                _LOG.info('Meta sender profile: available=%s photo=%s', bool(name or username), bool(photo))
            except meta.GraphError as exc:
                _LOG.info('Meta sender profile unavailable: provider_code=%s', exc.details.get('provider_code'))
            except Exception:
                _LOG.info('Meta sender profile unavailable: request_failed')
            _save(database, key, epoch, now, row, ttl)
            return _reply(row)
        finally:
            _LOCK.release()
    except (sqlite3.Error, OSError):
        _LOG.info('Meta sender profile unavailable: storage_error')
        return None
