"""Privileged publisher reference component for LOCAL SYNTHETIC Git only.

Not shipped in the HA runtime, not reachable through HTTP. No URL/push support.
Independent grant authority is supplied by the embedding trusted executor, NEVER
by API body/Bearer/WhatsApp. HMAC key provisioning and production isolation are
external prerequisites; this module makes no claim to establish either.
"""
import hashlib
import hmac
import os
from pathlib import Path
import re
import sqlite3
import subprocess
import tempfile
import time
import uuid

from release_receipt import (ReceiptError, canonical, digest, verify_receipt,
                             safe_directory)
from declarative_export import safe_path

class PublishBlocked(Exception):
    pass


BINDING = ('project', 'source_repository', 'source_ref', 'source_sha',
           'distribution_repository', 'distribution_ref', 'expected_distribution_sha',
           'package_id', 'version', 'profile_sha256', 'scope', 'allowed_shared_paths')


def grant_payload(receipt, *, issue, authority, nonce, expires_at):
    """Binding specification, NOT an approval or signing API."""
    return {**{key: receipt[key] for key in BINDING},
            'receipt_sha256': digest(receipt), 'action': 'publish',
            'issue': issue, 'authority': authority, 'nonce': nonce,
            'expires_at': expires_at}


class LocalPublisher:
    def __init__(self, state_dir, *, authorities):
        self.root = safe_directory(state_dir)
        if self.root.stat().st_mode & 0o077:
            raise PublishBlocked('state_permissions')
        self.authorities = dict(authorities)
        if not self.authorities or any(not isinstance(key, bytes) or len(key) < 32
                                       for key in self.authorities.values()):
            raise PublishBlocked('independent_authority_unavailable')
        db = self.root / 'publisher.sqlite3'
        if db.is_symlink() or (db.exists() and db.stat().st_nlink != 1):
            raise PublishBlocked('unsafe_state')
        self.db = sqlite3.connect(db, timeout=1, isolation_level=None)
        db.chmod(0o600)
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS revoked (nonce TEXT PRIMARY KEY);
            CREATE TABLE IF NOT EXISTS operations (
                nonce TEXT PRIMARY KEY, binding TEXT NOT NULL,
                state TEXT NOT NULL, expected TEXT NOT NULL, commit_sha TEXT);
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY, nonce TEXT, state TEXT, at INTEGER);
        ''')

    def close(self):
        self.db.close()

    def revoke(self, nonce):
        # Trusted authority side only; no HTTP method can call this component.
        self.db.execute('INSERT OR IGNORE INTO revoked VALUES (?)', (nonce,))

    def _event(self, nonce, state):
        self.db.execute('INSERT INTO events(nonce,state,at) VALUES (?,?,?)',
                        (nonce, state, int(time.time())))

    def status(self):
        return [{'operation_id': row[0], 'state': row[1]}
                for row in self.db.execute('''SELECT e.nonce,e.state FROM events e
                    JOIN (SELECT nonce,MAX(sequence) last FROM events GROUP BY nonce) latest
                    ON e.sequence=latest.last ORDER BY e.sequence DESC LIMIT 20''')]

    def _authorize(self, receipt, grant, *, issue, now):
        if not isinstance(grant, dict) or set(grant) != {'payload', 'signature'}:
            raise PublishBlocked('independent_grant_required')
        payload = grant['payload']
        if not isinstance(payload, dict):
            raise PublishBlocked('invalid_grant')
        authority = payload.get('authority')
        key = self.authorities.get(authority) if isinstance(authority, str) else None
        if (key is None or not isinstance(grant['signature'], str)
                or not hmac.compare_digest(hmac.new(key, canonical(payload), hashlib.sha256).hexdigest(),
                                           grant['signature'])):
            raise PublishBlocked('invalid_authority_signature')
        nonce, expiry = payload.get('nonce'), payload.get('expires_at')
        if (not isinstance(nonce, str) or not re.fullmatch('[a-f0-9]{32}', nonce)
                or type(expiry) is not int or expiry <= now or expiry > now + 86400
                or type(issue) is not int or issue <= 0):
            raise PublishBlocked('expired_or_invalid_grant')
        if payload != grant_payload(receipt, issue=issue, authority=authority,
                                    nonce=nonce, expires_at=expiry):
            raise PublishBlocked('grant_binding_mismatch')
        if self.db.execute('SELECT 1 FROM revoked WHERE nonce=?', (nonce,)).fetchone():
            raise PublishBlocked('grant_revoked')
        return nonce, digest(payload)

    @staticmethod
    def _git(repo, *args, data=None, index=None):
        env = {'PATH': '/usr/bin:/bin', 'HOME': '/nonexistent', 'LANG': 'C',
               'GIT_CONFIG_NOSYSTEM': '1', 'GIT_CONFIG_GLOBAL': os.devnull,
               'GIT_TERMINAL_PROMPT': '0', 'GIT_NO_REPLACE_OBJECTS': '1',
               'GIT_AUTHOR_NAME': 'Factory Local Test',
               'GIT_AUTHOR_EMAIL': 'fixture@example.invalid',
               'GIT_COMMITTER_NAME': 'Factory Local Test',
               'GIT_COMMITTER_EMAIL': 'fixture@example.invalid'}
        if index is not None:
            env['GIT_INDEX_FILE'] = str(index)
        try:
            result = subprocess.run(
                ['git', '-c', 'core.hooksPath=/dev/null', '-c', 'core.fsmonitor=false',
                 '-C', str(repo), *args], input=data, capture_output=True,
                env=env, timeout=30, check=False)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise PublishBlocked('git_timeout_or_unavailable') from exc
        if result.returncode:
            raise PublishBlocked('git_conflict_or_failure')
        return result.stdout

    def _target(self, target, receipt):
        target = safe_directory(target)
        # Only a bare repository within the disposable state root can be written.
        # Requiring no remotes prevents accidental use as a production transport.
        if self.root not in target.parents:
            raise PublishBlocked('local_fixture_target_required')
        if self._git(target, 'rev-parse', '--is-bare-repository').strip() != b'true':
            raise PublishBlocked('bare_fixture_required')
        if self._git(target, 'remote').strip():
            raise PublishBlocked('remote_transport_disabled')
        ref = receipt['distribution_ref']
        if (not isinstance(ref, str) or not re.fullmatch(r'refs/heads/[A-Za-z0-9_/-]+', ref)
                or '..' in ref or '//' in ref):
            raise PublishBlocked('invalid_destination_ref')
        return target, ref

    def _validate(self, bundle, expected_digest):
        receipt = verify_receipt(bundle, expected_digest)
        for field in ('source_sha', 'expected_distribution_sha'):
            if not isinstance(receipt.get(field), str) or not re.fullmatch('[0-9a-f]{40}', receipt[field]):
                raise PublishBlocked('invalid_sha')
        scope = receipt['scope']
        if not isinstance(scope, str) or not scope.endswith('/'):
            raise PublishBlocked('invalid_scope')
        safe_path(scope[:-1])
        shared = receipt['allowed_shared_paths']
        if not isinstance(shared, list) or any(not safe_path(path) for path in shared):
            raise PublishBlocked('invalid_shared_scope')
        tests = receipt['tests']
        if (not isinstance(tests, dict) or tests.get('status') != 'PASS'
                or not tests.get('checks') or tests.get('source_sha') != receipt['source_sha']
                or any(not isinstance(check, dict) or check.get('exit_code') != 0
                       or type(check.get('passed')) is not int or check['passed'] < 1
                       for check in tests['checks'])):
            raise PublishBlocked('verified_tests_required')
        paths = receipt['artifacts']
        if (not isinstance(paths, list) or not paths or len(set(paths)) != len(paths)
                or any(not safe_path(path).startswith(scope) and path not in shared for path in paths)
                or set(paths) != {item['path'] for item in receipt['files']
                                  if item['path'] != 'DECLARATIVE_BUNDLE_MANIFEST.json'}):
            raise PublishBlocked('invalid_artifact_scope')
        return receipt

    def _verify_commit(self, target, ref, commit, receipt):
        if self._git(target, 'rev-parse', ref).decode().strip() != commit:
            raise PublishBlocked('remote_verification_conflict')
        changed = self._git(target, 'diff-tree', '--no-commit-id', '--name-only', '-r', '-z',
                            receipt['expected_distribution_sha'], commit).split(b'\0')
        if any(path and not path.decode().startswith(receipt['scope'])
               and path.decode() not in receipt['allowed_shared_paths'] for path in changed):
            raise PublishBlocked('published_scope_mismatch')
        records = {item['path']: item for item in receipt['files']}
        for path in receipt['artifacts']:
            payload = self._git(target, 'show', commit + ':' + path)
            if hashlib.sha256(payload).hexdigest() != records[path]['sha256']:
                raise PublishBlocked('published_integrity_mismatch')
            entry = self._git(target, 'ls-tree', commit, '--', path)
            if entry.split(b' ', 1)[0].decode() != records[path]['mode']:
                raise PublishBlocked('published_mode_mismatch')

    def preview(self, bundle, expected_digest, target):
        """Read-only exact file/mode preview. It neither approves nor writes Git."""
        receipt = self._validate(bundle, expected_digest)
        target, ref = self._target(target, receipt)
        if self._git(target, 'rev-parse', ref).decode().strip() != receipt['expected_distribution_sha']:
            raise PublishBlocked('distribution_cas_conflict')
        snapshot = receipt['expected_distribution_sha']
        raw = self._git(target, 'ls-tree', '-r', '-z', snapshot, '--',
                        receipt['scope'], *receipt['allowed_shared_paths'])
        previous = {}
        for entry in raw.split(b'\0'):
            if entry:
                header, path = entry.split(b'\t', 1)
                previous[path.decode()] = header.split(b' ')[0].decode()
        current = {item['path']: item for item in receipt['files'] if item['path'] in receipt['artifacts']}
        changes = []
        for path in sorted(set(previous) | set(current)):
            if path not in current:
                if path.startswith(receipt['scope']):
                    changes.append({'path': path, 'change': 'delete'})
            elif path not in previous:
                changes.append({'path': path, 'change': 'add'})
            else:
                body = self._git(target, 'show', snapshot + ':' + path)
                if (hashlib.sha256(body).hexdigest() != current[path]['sha256']
                        or previous[path] != current[path]['mode']):
                    changes.append({'path': path, 'change': 'modify'})
        return {'state': 'PREVIEW_NOT_AUTHORIZATION', 'receipt_sha256': expected_digest,
                'expected_distribution_sha': receipt['expected_distribution_sha'], 'changes': changes}

    def publish(self, bundle, expected_digest, grant, target, *, issue, cancel=None):
        operation_id = uuid.uuid4().hex
        self._event(operation_id, 'requested')
        try:
            result = self._publish(bundle, expected_digest, grant, target, issue=issue, cancel=cancel)
            self._event(operation_id, 'completed_local_fixture')
            return {**result, 'operation_id': operation_id}
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            self._event(operation_id, 'failed_no_automatic_rollback')
            raise

    def _publish(self, bundle, expected_digest, grant, target, *, issue, cancel=None):
        started = time.monotonic()
        def check_cancel():
            if time.monotonic() - started > 240:
                raise PublishBlocked('publication_time_budget_exceeded')
            if cancel is not None and cancel():
                raise PublishBlocked('operation_cancelled')
        receipt = self._validate(bundle, expected_digest)
        target, ref = self._target(target, receipt)
        nonce = None
        try:
            self.db.execute('BEGIN IMMEDIATE')
            nonce, binding = self._authorize(receipt, grant, issue=issue, now=int(time.time()))
            old = self.db.execute('SELECT binding,state,commit_sha FROM operations WHERE nonce=?', (nonce,)).fetchone()
            if old and old[0] != binding:
                raise PublishBlocked('grant_replay')
            if old and old[1] == 'published':
                self._verify_commit(target, ref, old[2], receipt)
                self.db.execute('COMMIT')
                return {'state': 'PUBLISHED_LOCAL_FIXTURE', 'commit': old[2], 'idempotent': True}
            if old and old[1] == 'intent':
                check_cancel()
                actual = self._git(target, 'rev-parse', ref).decode().strip()
                if actual == old[2]:
                    # Crash after Git CAS, before SQLite completion. Reconcile
                    # the exact intended commit without writing a second one.
                    self._verify_commit(target, ref, old[2], receipt)
                    self.db.execute('UPDATE operations SET state=? WHERE nonce=?', ('published', nonce))
                    self._event(nonce, 'published_pending_homologation')
                    self.db.execute('COMMIT')
                    return {'state': 'PUBLISHED_LOCAL_FIXTURE', 'commit': old[2], 'idempotent': True}
                if actual != receipt['expected_distribution_sha']:
                    raise PublishBlocked('distribution_cas_conflict')
                self._authorize(receipt, grant, issue=issue, now=int(time.time()))
                self._git(target, 'update-ref', ref, old[2], actual)
                self._verify_commit(target, ref, old[2], receipt)
                self.db.execute('UPDATE operations SET state=? WHERE nonce=?', ('published', nonce))
                self._event(nonce, 'published_pending_homologation')
                self.db.execute('COMMIT')
                return {'state': 'PUBLISHED_LOCAL_FIXTURE', 'commit': old[2], 'idempotent': True}
            if old:
                raise PublishBlocked('operation_previously_failed')
            self.db.execute('INSERT INTO operations VALUES (?,?,?,?,NULL)',
                            (nonce, binding, 'running', receipt['expected_distribution_sha']))
            self._event(nonce, 'running')
            check_cancel()
            actual = self._git(target, 'rev-parse', ref).decode().strip()
            if actual != receipt['expected_distribution_sha']:
                raise PublishBlocked('distribution_cas_conflict')
            records = {item['path']: item for item in receipt['files']}
            with tempfile.TemporaryDirectory(dir=self.root, prefix='index-') as tmp:
                index = Path(tmp) / 'index'
                self._git(target, 'read-tree', actual, index=index)
                # Replace the entire approved prefix; obsolete project files are removed.
                previous = self._git(target, 'ls-tree', '-r', '--name-only', '-z', actual, '--', receipt['scope'])
                if previous:
                    removals = b''.join(b'0 ' + b'0' * 40 + b'\t' + path + b'\0'
                                        for path in previous.split(b'\0') if path)
                    self._git(target, 'update-index', '-z', '--index-info', data=removals, index=index)
                for path in receipt['artifacts']:
                    check_cancel()
                    data = (Path(bundle) / path).read_bytes()
                    if hashlib.sha256(data).hexdigest() != records[path]['sha256']:
                        raise PublishBlocked('artifact_changed_during_publication')
                    blob = self._git(target, 'hash-object', '-w', '--stdin', data=data).decode().strip()
                    self._git(target, 'update-index', '--add', '--cacheinfo', records[path]['mode'], blob, path, index=index)
                tree = self._git(target, 'write-tree', index=index).decode().strip()
                commit = self._git(target, 'commit-tree', tree, '-p', actual,
                                   data=('Synthetic gated package ' + expected_digest + '\n').encode()).decode().strip()
            check_cancel()
            # Recheck expiry/revocation and artifact bytes immediately before CAS.
            self._authorize(receipt, grant, issue=issue, now=int(time.time()))
            self._validate(bundle, expected_digest)
            # Durable intent precedes Git CAS: ref/SQLite cannot share one
            # transaction. A retry can reconcile both sides after a crash.
            self.db.execute('UPDATE operations SET state=?,commit_sha=? WHERE nonce=?', ('intent', commit, nonce))
            self._event(nonce, 'intent')
            self.db.execute('COMMIT')
            self.db.execute('BEGIN IMMEDIATE')
            self._authorize(receipt, grant, issue=issue, now=int(time.time()))
            self._git(target, 'update-ref', ref, commit, actual)
            self._verify_commit(target, ref, commit, receipt)
            self.db.execute('UPDATE operations SET state=?,commit_sha=? WHERE nonce=?', ('published', commit, nonce))
            self._event(nonce, 'published_pending_homologation')
            self.db.execute('COMMIT')
            return {'state': 'PUBLISHED_LOCAL_FIXTURE', 'commit': commit, 'idempotent': False}
        except Exception:
            if self.db.in_transaction:
                self.db.execute('ROLLBACK')
            # Never roll back a Git ref: another writer may already have advanced it.
            # Durable intent allows reconciliation after CAS on the next retry.
            raise
