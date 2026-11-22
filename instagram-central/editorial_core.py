"""Núcleo editorial isolado. Não contém rede, endpoints ou publicação Meta.

O chamador deve autenticar e autorizar o administrador antes de invocar operações.
Dados pertencem a um volume persistente separado: /data/editorial.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import secrets
import re
import stat
import sqlite3
import time


class EditorialError(ValueError):
    pass


class EditorialConflict(EditorialError):
    pass


_FORMATS = {"feed", "carousel", "story", "reel"}
_EXTENSIONS = {"jpg", "png", "mp4"}
_MAX_BYTES = 25 * 1024 * 1024  # limite inicial de upload; videos maiores exigem streaming


def _timestamp(value=None):
    if value is None:
        return int(time.time())
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise EditorialError("Data deve conter fuso horário")
    return int(value.timestamp())


def _check_media(content, extension):
    if extension not in _EXTENSIONS or not isinstance(content, bytes):
        raise EditorialError("Formato de arquivo não aceito")
    if not content or len(content) > _MAX_BYTES:
        raise EditorialError("Arquivo vazio ou acima do limite")
    valid = {
        "jpg": content.startswith(b"\xff\xd8\xff"),
        "png": content.startswith(b"\x89PNG\r\n\x1a\n"),
        "mp4": len(content) >= 12 and content[4:8] == b"ftyp",
    }
    if not valid[extension]:
        raise EditorialError("Assinatura incompatível com a extensão")


class EditorialStore:
    def __init__(self, root):
        self.root = Path(root).absolute()
        for parent in (self.root, *self.root.parents):
            if parent.is_symlink():
                raise EditorialError("Caminho simbólico não permitido")
        self.media_dir = self.root / "media"
        for folder in (self.root, self.media_dir):
            if folder.is_symlink():
                raise EditorialError("Diretório simbólico não permitido")
            folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.db_path = self.root / "editorial.sqlite3"
        if self.db_path.is_symlink():
            raise EditorialError("Banco simbólico não permitido")
        with self._db() as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS media (
                    id TEXT PRIMARY KEY, extension TEXT NOT NULL,
                    digest TEXT NOT NULL, size INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS posts (
                    id TEXT PRIMARY KEY, format TEXT NOT NULL,
                    caption TEXT NOT NULL, revision INTEGER NOT NULL DEFAULT 1,
                    approved_revision INTEGER, state TEXT NOT NULL DEFAULT 'draft',
                    scheduled_at INTEGER, lease_token TEXT, lease_until INTEGER,
                    remote_id TEXT, created_at INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS attachments (
                    post_id TEXT NOT NULL REFERENCES posts(id),
                    media_id TEXT NOT NULL REFERENCES media(id),
                    position INTEGER NOT NULL,
                    PRIMARY KEY (post_id, position));
                CREATE TABLE IF NOT EXISTS audit (
                    id INTEGER PRIMARY KEY AUTOINCREMENT, post_id TEXT NOT NULL,
                    event TEXT NOT NULL, at INTEGER NOT NULL);
                CREATE INDEX IF NOT EXISTS posts_due ON posts(state, scheduled_at);
                CREATE INDEX IF NOT EXISTS attachments_media ON attachments(media_id);
                CREATE TABLE IF NOT EXISTS media_deletions (
                    id TEXT PRIMARY KEY, extension TEXT NOT NULL, size INTEGER NOT NULL);
                CREATE TABLE IF NOT EXISTS publication_metrics (
                    post_id TEXT PRIMARY KEY REFERENCES posts(id) ON DELETE CASCADE,
                    remote_id TEXT NOT NULL, status TEXT NOT NULL,
                    likes INTEGER, comments INTEGER, checked_at INTEGER,
                    attempted_at INTEGER NOT NULL, error TEXT NOT NULL DEFAULT '');
                CREATE TABLE IF NOT EXISTS history_jobs (
                    slot INTEGER PRIMARY KEY CHECK(slot=1), id TEXT NOT NULL, status TEXT NOT NULL,
                    data TEXT NOT NULL, lease TEXT, lease_until INTEGER NOT NULL DEFAULT 0);
                CREATE TABLE IF NOT EXISTS history_media (
                    remote_id TEXT PRIMARY KEY, post_id TEXT NOT NULL REFERENCES posts(id) ON DELETE CASCADE,
                    position INTEGER NOT NULL, data TEXT NOT NULL, state TEXT NOT NULL DEFAULT 'pending',
                    media_id TEXT REFERENCES media(id) ON DELETE SET NULL, error TEXT NOT NULL DEFAULT '');
                CREATE INDEX IF NOT EXISTS history_media_pending ON history_media(state,post_id);
            """)
            db.execute("BEGIN IMMEDIATE")
            columns = {r[1] for r in db.execute("PRAGMA table_info(posts)")}
            if "version" not in columns:
                db.execute("ALTER TABLE posts ADD COLUMN version INTEGER NOT NULL DEFAULT 1")
            if "caption_mode" not in columns:
                db.execute("ALTER TABLE posts ADD COLUMN caption_mode TEXT NOT NULL DEFAULT 'general'")
            if "pending_schedule_at" not in columns:
                db.execute("ALTER TABLE posts ADD COLUMN pending_schedule_at INTEGER")
            # Old schedules were explicitly non-executable. Only a new publishing
            # action can authorize them; an upgrade never publishes old material.
            publication_columns = {
                'publish_authorized': 'INTEGER NOT NULL DEFAULT 0',
                'publication_account_id': 'TEXT',
                'publication_phase': "TEXT NOT NULL DEFAULT ''",
                'publication_data': "TEXT NOT NULL DEFAULT '{}'",
                'publication_next': 'INTEGER',
                'publication_started': 'INTEGER',
                'publication_error': "TEXT NOT NULL DEFAULT ''",
                'remote_details': "TEXT NOT NULL DEFAULT '{}'",
                'source': "TEXT NOT NULL DEFAULT 'editorial'",
            }
            for name, declaration in publication_columns.items():
                if name not in columns:
                    db.execute('ALTER TABLE posts ADD COLUMN ' + name + ' ' + declaration)
            metric_columns = {r[1] for r in db.execute('PRAGMA table_info(publication_metrics)')}
            for name, declaration in {'extra_data': "TEXT NOT NULL DEFAULT '{}'", 'extra_checked_at': 'INTEGER', 'extra_error': "TEXT NOT NULL DEFAULT ''"}.items():
                if name not in metric_columns: db.execute('ALTER TABLE publication_metrics ADD COLUMN '+name+' '+declaration)
            attachment_columns = {r[1] for r in db.execute("PRAGMA table_info(attachments)")}
            if "slide_caption" not in attachment_columns:
                db.execute("ALTER TABLE attachments ADD COLUMN slide_caption TEXT NOT NULL DEFAULT ''")
            db.commit()
        os.chmod(self.db_path, 0o600)
        self.cleanup_deleted_media()

    @contextmanager
    def _db(self):
        db = sqlite3.connect(self.db_path, timeout=5, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
        finally:
            db.close()

    @contextmanager
    def _tx(self):
        with self._db() as db:
            db.execute("BEGIN IMMEDIATE")
            try:
                yield db
                db.commit()
            except BaseException:
                db.rollback()
                raise

    @staticmethod
    def _audit(db, post_id, event):
        if event != "created":
            db.execute("UPDATE posts SET version=version+1 WHERE id=?", (post_id,))
        db.execute("INSERT INTO audit(post_id,event,at) VALUES (?,?,?)",
                   (post_id, event, _timestamp()))

    def add_media(self, content: bytes, extension: str):
        _check_media(content, extension)
        media_id = secrets.token_hex(16)
        path = self.media_dir / f"{media_id}.{extension}"
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                with self._tx() as db:
                    count, total = db.execute("SELECT COUNT(*),COALESCE(SUM(size),0) FROM (SELECT size FROM media UNION ALL SELECT size FROM media_deletions)").fetchone()
                    if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='incoming_media'").fetchone():
                        staged_count, staged_size = db.execute('SELECT COUNT(*),COALESCE(SUM(size),0) FROM incoming_media').fetchone()
                        count += staged_count; total += staged_size
                    if count >= 500 or total + len(content) > 1024 * 1024 * 1024:
                        raise EditorialError("Limite da biblioteca atingido (500 arquivos / 1 GiB)")
                    db.execute("INSERT INTO media VALUES (?,?,?,?)",
                               (media_id, extension, hashlib.sha256(content).hexdigest(), len(content)))
            except BaseException:
                path.unlink(missing_ok=True)
                raise
        except BaseException:
            path.unlink(missing_ok=True)
            raise
        return media_id

    def cleanup_deleted_media(self, ids=None):
        """Durable unlink queue: commit references first, then remove bytes.

        Interrupted/failed cleanup is retried when opening the store; pending
        bytes still count against quota. A rollback cannot strand a live post
        without its file, and shared media never enters this queue.
        """
        with self._db() as db:
            rows = db.execute('SELECT * FROM media_deletions').fetchall()
        freed = pending = 0
        for row in rows:
            if ids is not None and row['id'] not in ids:
                continue
            if not re.fullmatch(r'[0-9a-f]{32}', row['id']) or row['extension'] not in _EXTENSIONS:
                raise EditorialError('Registro de exclusão inválido')
            try:
                (self.media_dir / (row['id'] + '.' + row['extension'])).unlink(missing_ok=True)
            except OSError:
                pending += row['size']
                continue
            with self._tx() as db:
                db.execute('DELETE FROM media_deletions WHERE id=?', (row['id'],))
            freed += row['size']
        return {'freedBytes': freed, 'pendingBytes': pending}

    @staticmethod
    def _remove_unused_media(db, media_id):
        row = db.execute('SELECT * FROM media WHERE id=?', (media_id,)).fetchone()
        if row is None:
            raise EditorialError('Mídia inexistente nesta conta.')
        if db.execute('SELECT 1 FROM attachments WHERE media_id=? LIMIT 1', (media_id,)).fetchone():
            return False
        db.execute('INSERT INTO media_deletions(id,extension,size) VALUES(?,?,?)',
                   (media_id, row['extension'], row['size']))
        db.execute('DELETE FROM media WHERE id=?', (media_id,))
        return True

    def delete_media(self, media_id):
        if not isinstance(media_id, str) or not re.fullmatch(r'[0-9a-f]{32}', media_id):
            raise EditorialError('Mídia inexistente nesta conta.')
        with self._tx() as db:
            if not self._remove_unused_media(db, media_id):
                raise EditorialError('Esta mídia está em uso. Exclua ou edite as publicações que a utilizam antes de apagar o arquivo.')
        return {'deletedMedia': 1, **self.cleanup_deleted_media({media_id})}

    def delete_post(self, post_id, *, expected_version, delete_unused_media=False):
        if type(expected_version) is not int or type(delete_unused_media) is not bool:
            raise EditorialError('Pedido de exclusão inválido.')
        removed, kept = set(), 0
        with self._tx() as db:
            self._check_version(db, post_id, expected_version)
            row = db.execute('SELECT * FROM posts WHERE id=?', (post_id,)).fetchone()
            if row['source']=='instagram' and db.execute("SELECT 1 FROM history_jobs WHERE status IN ('queued','running')").fetchone():
                raise EditorialError('Aguarde ou cancele a sincronização antes de excluir um registro importado.')
            if row['state'] not in ('draft', 'approved', 'scheduled', 'failed', 'published') or (
                    json.loads(row['publication_data']).get('issued') and row['state'] != 'published'):
                raise EditorialError('Esta publicação tem um envio em andamento ou resultado pendente. Confira o resultado antes de excluir.')
            mids = [item[0] for item in db.execute('SELECT media_id FROM attachments WHERE post_id=?', (post_id,))]
            db.execute('DELETE FROM attachments WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM audit WHERE post_id=?', (post_id,))
            db.execute('DELETE FROM posts WHERE id=?', (post_id,))
            if delete_unused_media:
                for mid in mids:
                    if self._remove_unused_media(db, mid): removed.add(mid)
                    else: kept += 1
        return {'deletedMedia': len(removed), 'keptMedia': kept, **self.cleanup_deleted_media(removed)}

    @staticmethod
    def _metrics_snapshot(row):
        return {'status': row['status'] if row else 'not_checked',
                'likes': row['likes'] if row else None, 'comments': row['comments'] if row else None,
                'checkedAt': row['checked_at'] * 1000 if row and row['checked_at'] is not None else None,
                'attemptedAt': row['attempted_at'] * 1000 if row else None,
                'error': row['error'] if row else '',
                'extra': json.loads(row['extra_data']) if row else {},
                'extraCheckedAt': row['extra_checked_at'] * 1000 if row and row['extra_checked_at'] is not None else None,
                'extraError': row['extra_error'] if row else ''}

    def save_metrics(self, post_id, remote_id, *, values=None, error='', now=None):
        if values is not None and (not {'likes', 'comments'} <= set(values) or set(values)-{'likes','comments','extra','extraError'} or any(
                value is not None and (type(value) is not int or not 0 <= value <= 2**63-1)
                for value in (values['likes'],values['comments']))):
            raise EditorialError('Contagens inválidas')
        if values is not None and 'extra' in values:
            if (not isinstance(values['extra'],dict) or set(values['extra']) != {'shares','saves'} or any(
                    v is not None and (type(v) is not int or not 0<=v<=2**63-1) for v in values['extra'].values())):
                raise EditorialError('Contagens adicionais inválidas')
        if not isinstance(error, str) or len(error) > 500:
            raise EditorialError('Diagnóstico inválido')
        timestamp = int(time.time() if now is None else now)
        ready = values is not None
        with self._tx() as db:
            row = db.execute('SELECT state,remote_id FROM posts WHERE id=?', (post_id,)).fetchone()
            if row is None or row['state'] != 'published' or row['remote_id'] != remote_id:
                raise EditorialConflict('A publicação mudou durante a consulta. Atualize a lista.')
            db.execute('''INSERT INTO publication_metrics
                (post_id,remote_id,status,likes,comments,checked_at,attempted_at,error) VALUES(?,?,?,?,?,?,?,?)
                ON CONFLICT(post_id) DO UPDATE SET status=excluded.status,
                likes=CASE WHEN excluded.status='ready' THEN excluded.likes ELSE publication_metrics.likes END,
                comments=CASE WHEN excluded.status='ready' THEN excluded.comments ELSE publication_metrics.comments END,
                checked_at=CASE WHEN excluded.status='ready' THEN excluded.checked_at ELSE publication_metrics.checked_at END,
                attempted_at=excluded.attempted_at,error=excluded.error''',
                (post_id, remote_id, 'ready' if ready else 'error', values['likes'] if ready else None,
                 values['comments'] if ready else None, timestamp if ready else None, timestamp, error))
            if values is not None:
                if 'extra' in values:
                    db.execute('UPDATE publication_metrics SET extra_data=?,extra_checked_at=?,extra_error=? WHERE post_id=?',
                               (json.dumps(values['extra']),timestamp,'',post_id))
                elif values.get('extraError'):
                    db.execute('UPDATE publication_metrics SET extra_error=? WHERE post_id=?',
                               ('A Meta não disponibilizou compartilhamentos e salvamentos nesta consulta.',post_id))
            result = db.execute('SELECT * FROM publication_metrics WHERE post_id=?', (post_id,)).fetchone()
            return self._metrics_snapshot(result)

    def create_draft(self, format: str, caption: str):
        if format not in _FORMATS or not isinstance(caption, str) or len(caption) > 2200:
            raise EditorialError("Formato ou legenda inválidos")
        post_id = secrets.token_hex(16)
        with self._tx() as db:
            db.execute("INSERT INTO posts(id,format,caption,created_at) VALUES(?,?,?,?)",
                       (post_id, format, caption, _timestamp()))
            self._audit(db, post_id, "created")
        return post_id

    @staticmethod
    def _editable(db, post_id):
        row = db.execute("SELECT state,revision FROM posts WHERE id=?", (post_id,)).fetchone()
        if row is None or row["state"] not in ("draft", "approved", "scheduled"):
            raise EditorialError("Publicação inexistente ou bloqueada para edição")
        return row

    @staticmethod
    def _invalidate(db, post_id, revision):
        # Editing a scheduled publication preserves its time as a non-executable
        # reservation. The scheduler only claims state='scheduled'.
        db.execute("""UPDATE posts SET state='draft', revision=?, approved_revision=NULL,publish_authorized=0,
                      pending_schedule_at=CASE WHEN state='scheduled'
                          THEN scheduled_at ELSE pending_schedule_at END,
                      scheduled_at=NULL WHERE id=?""", (revision + 1, post_id))

    def edit_caption(self, post_id, caption):
        if not isinstance(caption, str) or len(caption) > 2200:
            raise EditorialError("Legenda inválida")
        with self._tx() as db:
            row = self._editable(db, post_id)
            db.execute("UPDATE posts SET caption=? WHERE id=?", (caption, post_id))
            self._invalidate(db, post_id, row["revision"])
            self._audit(db, post_id, "edited")

    def attach_media(self, post_id, media_id, position=0):
        if not isinstance(position, int) or not 0 <= position < 20:
            raise EditorialError("Posição inválida")
        with self._tx() as db:
            row = self._editable(db, post_id)
            if not db.execute("SELECT 1 FROM media WHERE id=?", (media_id,)).fetchone():
                raise EditorialError("Mídia inexistente")
            db.execute("""INSERT INTO attachments(post_id,media_id,position) VALUES(?,?,?)
                         ON CONFLICT(post_id,position) DO UPDATE SET media_id=excluded.media_id""",
                       (post_id, media_id, position))
            self._invalidate(db, post_id, row["revision"])
            self._audit(db, post_id, "media_changed")

    def approve(self, post_id, *, expected_version=None, now=None):
        with self._tx() as db:
            self._check_version(db, post_id, expected_version)
            row = db.execute(
                "SELECT format,revision,state,pending_schedule_at FROM posts WHERE id=?",
                (post_id,)).fetchone()
            if row is None or row["state"] not in ("draft", "approved"):
                raise EditorialError("Só rascunhos podem ser aprovados")
            count = db.execute("SELECT COUNT(*) FROM attachments WHERE post_id=?", (post_id,)).fetchone()[0]
            required = 2 <= count <= 20 if row["format"] == "carousel" else count == 1
            if not required:
                raise EditorialError("Quantidade de mídias incompatível com a publicação")
            if row["format"] in ("feed", "carousel", "reel"):
                invalid = db.execute("""SELECT 1 FROM attachments a JOIN media m ON m.id=a.media_id
                    WHERE a.post_id=? AND (m.extension='mp4') != ?""",
                    (post_id, int(row["format"] == "reel"))).fetchone()
                if invalid:
                    raise EditorialError("Mídia incompatível com o formato")
            pending = row["pending_schedule_at"]
            if pending is not None and pending > _timestamp(now):
                # Only future reservations resume after the new revision is approved.
                db.execute("""UPDATE posts SET state='scheduled',approved_revision=revision,
                              scheduled_at=pending_schedule_at,pending_schedule_at=NULL
                              WHERE id=?""", (post_id,))
                self._audit(db, post_id, "approved_schedule_restored")
            else:
                # Past reservations remain visible for review, not runnable.
                db.execute(
                    "UPDATE posts SET state='approved',approved_revision=revision WHERE id=?",
                    (post_id,))
                self._audit(db, post_id, "approved")

    def schedule(self, post_id, when: datetime, *, now=None, expected_version=None):
        utc_when = _timestamp(when)
        if utc_when <= _timestamp(now):
            raise EditorialError("Data deve ser futura")
        with self._tx() as db:
            self._check_version(db, post_id, expected_version)
            row = db.execute("SELECT state,revision,approved_revision FROM posts WHERE id=?", (post_id,)).fetchone()
            if row is None or row["state"] != "approved" or row["revision"] != row["approved_revision"]:
                raise EditorialError("A versão atual precisa de aprovação")
            db.execute("""UPDATE posts SET state='scheduled', scheduled_at=?,
                          pending_schedule_at=NULL WHERE id=?""", (utc_when, post_id))
            self._audit(db, post_id, "scheduled")

    def cancel_schedule(self, post_id, *, expected_version=None):
        with self._tx() as db:
            self._check_version(db, post_id, expected_version)
            cur = db.execute("""UPDATE posts SET state='approved', scheduled_at=NULL,publish_authorized=0,
                                pending_schedule_at=NULL
                                WHERE id=? AND state='scheduled'""", (post_id,))
            if cur.rowcount != 1:
                raise EditorialError("Agenda indisponível para cancelamento")
            self._audit(db, post_id, "schedule_cancelled")

    def claim_due(self, *, now=None, lease_seconds=120):
        """Reserva para futuro executor. NÃO chama API e NÃO publica."""
        if not isinstance(lease_seconds, int) or not 30 <= lease_seconds <= 300:
            raise EditorialError("Lease inválido")
        clock = _timestamp(now)
        with self._tx() as db:
            row = db.execute("""SELECT id FROM posts WHERE state='scheduled'
                                AND scheduled_at<=? ORDER BY scheduled_at,id LIMIT 1""",
                             (clock,)).fetchone()
            if row is None:
                return None
            token = secrets.token_urlsafe(32)
            db.execute("""UPDATE posts SET state='leased',lease_token=?,lease_until=?
                          WHERE id=? AND state='scheduled'""",
                       (token, clock + lease_seconds, row["id"]))
            self._audit(db, row["id"], "claimed")
            return {"id": row["id"], "lease_token": token}

    def mark_review_required(self, post_id, lease_token):
        """Ambiguidade não reenvia conteúdo automaticamente."""
        with self._tx() as db:
            cur = db.execute("""UPDATE posts SET state='needs_review',lease_token=NULL,lease_until=NULL
                                WHERE id=? AND state='leased' AND lease_token=?""",
                             (post_id, lease_token))
            if cur.rowcount != 1:
                raise EditorialError("Reserva inválida")
            self._audit(db, post_id, "needs_review")

    def expire_leases(self, *, now=None):
        clock = _timestamp(now)
        with self._tx() as db:
            rows = db.execute("""SELECT id FROM posts WHERE state='leased' AND lease_until<=?""",
                              (clock,)).fetchall()
            for row in rows:
                db.execute("""UPDATE posts SET state='needs_review',lease_token=NULL,lease_until=NULL
                              WHERE id=?""", (row["id"],))
                self._audit(db, row["id"], "lease_expired_review")
            return len(rows)

    def get_post(self, post_id):
        with self._db() as db:
            row = db.execute("""SELECT id,format,caption,revision,approved_revision,state,
                                scheduled_at,pending_schedule_at,remote_id FROM posts WHERE id=?""", (post_id,)).fetchone()
            return dict(row) if row else None


    @staticmethod
    def _check_version(db, post_id, expected_version):
        if expected_version is None:  # existing internal API compatibility
            return
        row = db.execute("SELECT version FROM posts WHERE id=?", (post_id,)).fetchone()
        if type(expected_version) is not int or row is None or row[0] != expected_version:
            raise EditorialConflict("Conteúdo mudou. Recarregue antes de tentar novamente.")

    def save_draft(self, format, caption, media_ids, *, post_id=None, expected_version=None,
                   caption_mode="general", slide_captions=None):
        """HTTP edit is one transaction: no partial attachment/caption updates."""
        if (not isinstance(format, str) or format not in _FORMATS or
                not isinstance(caption, str) or len(caption) > 2200 or
                not isinstance(media_ids, list) or len(media_ids) > 20 or
                any(not isinstance(mid, str) or not re.fullmatch(r"[0-9a-f]{32}", mid)
                    for mid in media_ids) or len(set(media_ids)) != len(media_ids)):
            raise EditorialError("Rascunho inválido")
        if slide_captions is None:
            slide_captions = [""] * len(media_ids)
        if (caption_mode not in ("general", "per_slide") or
                not isinstance(slide_captions, list) or len(slide_captions) != len(media_ids) or
                any(not isinstance(text, str) or len(text) > 2200 for text in slide_captions) or
                (caption_mode == "per_slide" and (format != "carousel" or len(media_ids) < 2 or caption)) or
                (caption_mode == "general" and any(slide_captions))):
            raise EditorialError("Legendas individuais inválidas")
        with self._tx() as db:
            for mid in media_ids:
                if not db.execute("SELECT 1 FROM media WHERE id=?", (mid,)).fetchone():
                    raise EditorialError("Mídia inexistente")
            if post_id is None:
                if db.execute("SELECT COUNT(*) FROM posts").fetchone()[0] >= 1000:
                    raise EditorialError("Limite de 1000 publicações atingido")
                post_id = secrets.token_hex(16)
                db.execute("INSERT INTO posts(id,format,caption,caption_mode,created_at) VALUES(?,?,?,?,?)",
                           (post_id, format, caption, caption_mode, _timestamp()))
                event = "created"
            else:
                self._check_version(db, post_id, expected_version)
                row = self._editable(db, post_id)
                self._invalidate(db, post_id, row["revision"])
                db.execute("UPDATE posts SET format=?,caption=?,caption_mode=? WHERE id=?",
                           (format, caption, caption_mode, post_id))
                db.execute("DELETE FROM attachments WHERE post_id=?", (post_id,))
                event = "edited"
            db.executemany(
                "INSERT INTO attachments(post_id,media_id,position,slide_caption) VALUES(?,?,?,?)",
                [(post_id, mid, i, slide_captions[i]) for i, mid in enumerate(media_ids)])
            self._audit(db, post_id, event)
        return post_id

    def snapshot(self):
        with self._db() as db:
            db.execute("BEGIN")
            metrics = {row['post_id']: row for row in db.execute('SELECT * FROM publication_metrics')}
            published = {row['post_id']: row['at'] for row in db.execute(
                "SELECT post_id,MIN(at) AS at FROM audit WHERE event='publication_published' GROUP BY post_id")}
            posts = []
            for row in db.execute("SELECT * FROM posts ORDER BY created_at DESC,id"):
                remote = json.loads(row['remote_details'])
                warnings=[item[0] for item in db.execute("SELECT DISTINCT error FROM history_media WHERE post_id=? AND error!=''",(row['id'],))]
                if warnings: remote['mediaWarnings']=warnings
                descriptions=[json.loads(item[0]).get('alt','') for item in db.execute('SELECT data FROM history_media WHERE post_id=? ORDER BY position',(row['id'],))]
                if descriptions: remote['altTexts']=descriptions
                attachment_rows = db.execute(
                    "SELECT media_id,slide_caption FROM attachments WHERE post_id=? ORDER BY position",
                    (row["id"],)).fetchall()
                mids = [r["media_id"] for r in attachment_rows]
                posts.append({"id": row["id"], "format": row["format"], "caption": row["caption"],
                              "captionMode": row["caption_mode"],
                              "slideCaptions": [r["slide_caption"] for r in attachment_rows],
                              "revision": row["revision"], "approvedRevision": row["approved_revision"],
                              "version": row["version"], "status": row["state"], "mediaIds": mids,
                              "publishAuthorized": bool(row['publish_authorized']),
                              "publicationMessage": row['publication_error'],
                              "publicationPhase": row['publication_phase'],
                              "publicationAttempted": bool(json.loads(row['publication_data']).get('issued')),
                              "permalink": remote.get('permalink') or json.loads(row['publication_data']).get('permalink'),
                              "remoteId": row['remote_id'],
                              "source": row['source'], "remoteDetails": remote,
                              "metrics": self._metrics_snapshot(metrics.get(row['id'])),
                              "publishedAt": remote.get('timestamp', published.get(row['id'])) * 1000 if remote.get('timestamp', published.get(row['id'])) is not None else None,
                              "scheduledAt": row["scheduled_at"] * 1000 if row["scheduled_at"] else None,
                              "pendingScheduledAt": row["pending_schedule_at"] * 1000
                                  if row["pending_schedule_at"] else None,
                              "createdAt": row["created_at"] * 1000})
            media = [{"id": r["id"], "name": r["id"] + "." + r["extension"],
                      "size": r["size"], "type": {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4"}[r["extension"]],
                      "usageCount": r['uses'], "url": "media/" + r["id"]} for r in db.execute("SELECT m.*,(SELECT COUNT(*) FROM attachments a WHERE a.media_id=m.id) AS uses FROM media m ORDER BY m.rowid")]
            return {"posts": posts, "media": media}

    def read_media(self, media_id):
        if not isinstance(media_id, str) or not re.fullmatch(r"[0-9a-f]{32}", media_id):
            raise EditorialError("Mídia inexistente")
        with self._db() as db:
            row = db.execute("SELECT * FROM media WHERE id=?", (media_id,)).fetchone()
        if row is None:
            raise EditorialError("Mídia inexistente")
        path = self.media_dir / (media_id + "." + row["extension"])
        try:
            fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as handle:
                info = os.fstat(handle.fileno())
                if not stat.S_ISREG(info.st_mode) or info.st_size != row["size"] or info.st_size > _MAX_BYTES:
                    raise EditorialError("Mídia inválida")
                content = handle.read(_MAX_BYTES + 1)
        except OSError:
            raise EditorialError("Mídia indisponível") from None
        if hashlib.sha256(content).hexdigest() != row["digest"]:
            raise EditorialError("Integridade da mídia inválida")
        return content, {"png": "image/png", "jpg": "image/jpeg", "mp4": "video/mp4"}[row["extension"]]
