"""Vendor-neutral, account-bound incoming media API. No Meta credentials exposed."""
import hashlib
import json
import os
import re
import secrets
import socket
import time
from urllib.parse import urlsplit

import editorial_core as core
import account_registry

TOKEN = re.compile(r'cei1\.([a-z][a-z0-9_-]{1,39})\.([0-9a-f]{32})\.([A-Za-z0-9_-]{43})')
REQUEST = re.compile(r'[A-Za-z0-9_-]{16,100}')
ACTIONS = ('integration_list', 'integration_create', 'integration_revoke')
MULTI_LIMIT = 4 * 1024 * 1024


def prepare(store):
    with store._db() as db:
        db.executescript('''
        CREATE TABLE IF NOT EXISTS integration_keys (
          id TEXT PRIMARY KEY, label TEXT NOT NULL, digest TEXT NOT NULL,
          can_publish INTEGER NOT NULL, expires INTEGER NOT NULL, revoked INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS incoming_media (
          id TEXT PRIMARY KEY, key_id TEXT NOT NULL, request_id TEXT NOT NULL,
          position INTEGER NOT NULL, extension TEXT NOT NULL, digest TEXT NOT NULL,
          size INTEGER NOT NULL, expires INTEGER NOT NULL,
          UNIQUE(key_id,request_id,position));
        CREATE TABLE IF NOT EXISTS multi_incoming_sources (
          media_id TEXT PRIMARY KEY, size INTEGER NOT NULL, digest TEXT NOT NULL, mime TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS import_receipts (
          request_id TEXT PRIMARY KEY, key_id TEXT NOT NULL, fingerprint TEXT NOT NULL,
          post_id TEXT NOT NULL, imported_version INTEGER NOT NULL DEFAULT 1,
          publish_version INTEGER, publication_account TEXT, content_digest TEXT NOT NULL);
        ''')


def manage(store, business, action, data):
    prepare(store)
    if action == 'integration_list':
        if data: raise core.EditorialError('Pedido inválido.')
        with store._db() as db:
            return {'connections': [dict(r) for r in db.execute(
                'SELECT id,label,can_publish AS canPublish,expires,revoked FROM integration_keys ORDER BY rowid DESC')]}
    if action == 'integration_create':
        if (set(data) != {'label', 'canPublish'} or not isinstance(data['label'], str)
                or not 1 <= len(data['label'].strip()) <= 80 or type(data['canPublish']) is not bool):
            raise core.EditorialError('Nome e permissão da conexão inválidos.')
        key_id, secret = secrets.token_hex(16), secrets.token_urlsafe(32)
        token = f'cei1.{business}.{key_id}.{secret}'
        expires = int(time.time()) + 90 * 86400
        with store._tx() as db:
            if db.execute('SELECT COUNT(*) FROM integration_keys WHERE revoked=0 AND expires>?', (int(time.time()),)).fetchone()[0] >= 20:
                raise core.EditorialError('Limite de 20 conexões ativas.')
            db.execute('DELETE FROM integration_keys WHERE revoked=1 OR expires<=?', (int(time.time()),))
            db.execute('INSERT INTO integration_keys VALUES(?,?,?,?,?,0)',
                       (key_id, data['label'].strip(), hashlib.sha256(token.encode()).hexdigest(), int(data['canPublish']), expires))
        return {'id': key_id, 'token': token, 'expires': expires, 'canPublish': data['canPublish']}
    if action == 'integration_revoke':
        if set(data) != {'id'} or not isinstance(data['id'], str): raise core.EditorialError('Pedido inválido.')
        with store._tx() as db:
            db.execute('UPDATE integration_keys SET revoked=1 WHERE id=?', (data['id'],))
        return {'revoked': True}
    raise core.EditorialError('Ação inválida.')


def authenticate(store, token):
    prepare(store)
    match = TOKEN.fullmatch(token)
    if not match: return None
    with store._db() as db:
        row = db.execute('SELECT * FROM integration_keys WHERE id=? AND revoked=0 AND expires>?',
                         (match[2], int(time.time()))).fetchone()
    if row and secrets.compare_digest(row['digest'], hashlib.sha256(token.encode()).hexdigest()):
        return dict(row)
    return None


def require_active(db, key):
    active = db.execute('SELECT digest FROM integration_keys WHERE id=? AND revoked=0 AND expires>?',
                        (key['id'],int(time.time()))).fetchone()
    if active is None or not secrets.compare_digest(active['digest'],key['digest']):
        raise core.EditorialError('A conexão expirou ou foi revogada.')


def cleanup(store):
    # A durable deletion queue also recovers interruption between DB and unlink.
    with store._tx() as db:
        rows = db.execute('SELECT * FROM incoming_media WHERE expires<=?', (int(time.time()),)).fetchall()
        for row in rows:
            db.execute('INSERT OR IGNORE INTO media_deletions VALUES(?,?,?)', (row['id'], row['extension'], row['size']))
            db.execute('DELETE FROM incoming_media WHERE id=?', (row['id'],))
        db.execute('DELETE FROM multi_incoming_sources WHERE media_id NOT IN (SELECT id FROM incoming_media)')
    store.cleanup_deleted_media()


def stage(store, key, request, position, content, extension, *, check_active=None, source=None):
    if not isinstance(request, str) or not REQUEST.fullmatch(request) or not 0 <= position < 20:
        raise core.EditorialError('Identificador ou posição inválidos.')
    if source is not None:
        if (not isinstance(source, dict) or set(source) != {'size','digest','mime'}
                or type(source['size']) is not int or not 1 <= source['size'] <= MULTI_LIMIT
                or not isinstance(source['digest'],str) or not re.fullmatch(r'[0-9a-f]{64}',source['digest'])
                or {'jpg':'image/jpeg','png':'image/png','mp4':'video/mp4'}.get(extension) != source['mime']):
            raise core.EditorialError('Origem da mídia inválida.')
    digest = hashlib.sha256(content).hexdigest()
    cleanup(store)
    created_path = None
    try:
        with store._tx() as db:
            require_active(db,key) if check_active is None else check_active()
            existing = db.execute('SELECT * FROM incoming_media WHERE key_id=? AND request_id=? AND position=?',
                                  (key['id'], request, position)).fetchone()
            if existing:
                if existing['digest'] != digest: raise core.EditorialConflict('Esta posição já recebeu outro arquivo. Use uma nova transferência.')
                if source is not None:
                    original = db.execute('SELECT size,digest,mime FROM multi_incoming_sources WHERE media_id=?',(existing['id'],)).fetchone()
                    if original is None or dict(original) != source:
                        raise core.EditorialConflict('Os bytes originais mudaram. Use uma nova transferência.')
                return {'id': existing['id'], 'staged': True}
            receipt = db.execute('SELECT 1 FROM import_receipts WHERE request_id=?', (request,)).fetchone()
            if receipt: raise core.EditorialConflict('Transferência já concluída. Consulte o recibo.')
            count, size = db.execute('''SELECT COUNT(*),COALESCE(SUM(size),0) FROM (
              SELECT size FROM media UNION ALL SELECT size FROM media_deletions UNION ALL SELECT size FROM incoming_media)''').fetchone()
            if count >= 500 or size + len(content) > 1024**3: raise core.EditorialError('Limite da biblioteca atingido.')
            if source is not None:
                total = db.execute('SELECT COALESCE(SUM(s.size),0) FROM multi_incoming_sources s JOIN incoming_media m ON m.id=s.media_id WHERE m.key_id=? AND m.request_id=?',(key['id'],request)).fetchone()[0]
                if total + source['size'] > MULTI_LIMIT:
                    raise core.EditorialError('Limite de 4 MiB de mídia por transferência.')
            media_id = secrets.token_hex(16)
            path = store.media_dir / (media_id + '.' + extension)
            created_path = path
            try:
                fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                with os.fdopen(fd, 'wb') as handle:
                    handle.write(content); handle.flush(); os.fsync(handle.fileno())
                db.execute('INSERT INTO incoming_media VALUES(?,?,?,?,?,?,?,?)',
                           (media_id,key['id'],request,position,extension,digest,len(content),int(time.time())+86400))
                if source is not None:
                    db.execute('INSERT INTO multi_incoming_sources VALUES(?,?,?,?)',(media_id,source['size'],source['digest'],source['mime']))
                if check_active is not None: check_active()
            except BaseException:
                path.unlink(missing_ok=True)
                raise
    except BaseException:
        if created_path is not None:
            created_path.unlink(missing_ok=True)
        raise
    return {'id': media_id, 'staged': True}


def receipt(store, key, request):
    if not isinstance(request, str) or not REQUEST.fullmatch(request): raise core.EditorialError('Identificador inválido.')
    with store._db() as db:
        row = db.execute('SELECT * FROM import_receipts WHERE request_id=? AND key_id=?', (request,key['id'])).fetchone()
        if row is None: return {'found': False}
        post = db.execute('SELECT version,state,remote_id,publish_authorized FROM posts WHERE id=?', (row['post_id'],)).fetchone()
    return {'found': True, 'id': row['post_id'], 'version': post['version'] if post else None,
            'importedVersion': row['imported_version'], 'contentDigest': row['content_digest'], 'status': post['state'] if post else 'deleted',
            'publicationAuthorized': row['publish_version'] is not None,
            'published': bool(post and post['state']=='published'), 'remoteId': post['remote_id'] if post else None}


def commit(store, key, data, *, check_active=None, verify_sources=False):
    required = {'schemaVersion','requestId','transferApproved','format','caption','mediaIds','contentDigest'}
    if (set(data) != required or type(data['schemaVersion']) is not int or data['schemaVersion'] != 1
        or not isinstance(data['contentDigest'],str) or not re.fullmatch(r'[0-9a-f]{64}',data['contentDigest'])
        or data['transferApproved'] is not True or not isinstance(data['requestId'],str) or not REQUEST.fullmatch(data['requestId'])
        or not isinstance(data['format'],str) or data['format'] not in ('feed','carousel','story','reel')
        or not isinstance(data['caption'],str) or len(data['caption']) > 2200
        or not isinstance(data['mediaIds'],list) or not 1 <= len(data['mediaIds']) <= 20
        or any(not isinstance(mid,str) or not re.fullmatch(r'[0-9a-f]{32}',mid) for mid in data['mediaIds'])
        or len(set(data['mediaIds'])) != len(data['mediaIds'])):
        raise core.EditorialError('Manifesto inválido ou transferência não autorizada.')
    if not (2 <= len(data['mediaIds']) <= 20 if data['format']=='carousel' else len(data['mediaIds'])==1):
        raise core.EditorialError('Quantidade de arquivos incompatível com o formato.')
    fingerprint = hashlib.sha256(json.dumps(data,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    cleanup(store)
    with store._tx() as db:
        require_active(db,key) if check_active is None else check_active()
        existing = db.execute('SELECT * FROM import_receipts WHERE request_id=?', (data['requestId'],)).fetchone()
        if existing:
            if existing['key_id'] != key['id'] or existing['fingerprint'] != fingerprint:
                raise core.EditorialConflict('Identificador já utilizado com outro conteúdo ou conexão.')
        else:
            if db.execute('SELECT COUNT(*) FROM posts').fetchone()[0] >= 1000 or db.execute('SELECT COUNT(*) FROM import_receipts').fetchone()[0] >= 10000:
                raise core.EditorialError('Limite de publicações ou recibos atingido.')
            rows, sources = [], []
            for position, mid in enumerate(data['mediaIds']):
                row = db.execute('SELECT * FROM incoming_media WHERE id=? AND key_id=? AND request_id=? AND position=?',
                                 (mid,key['id'],data['requestId'],position)).fetchone()
                if not row: raise core.EditorialError('Arquivo ausente, expirado ou de outra transferência.')
                if (data['format'] in ('feed','carousel') and row['extension']=='mp4' or data['format']=='reel' and row['extension']!='mp4'):
                    raise core.EditorialError('Tipo de mídia incompatível com o formato.')
                rows.append(row)
                if verify_sources:
                    source = db.execute('SELECT size,digest,mime FROM multi_incoming_sources WHERE media_id=?',(mid,)).fetchone()
                    if source is None: raise core.EditorialError('Origem da mídia ausente.')
                    sources.append(source)
            if verify_sources:
                expected = hashlib.sha256(json.dumps({'format':data['format'],'caption':data['caption'],
                    'files':[{'sha256':src['digest'],'mime':src['mime']} for src in sources]},sort_keys=True).encode()).hexdigest()
                if sum(src['size'] for src in sources) > MULTI_LIMIT or expected != data['contentDigest']:
                    raise core.EditorialError('Manifesto não confere com os bytes recebidos.')
            post_id = secrets.token_hex(16)
            db.execute('INSERT INTO posts(id,format,caption,created_at) VALUES(?,?,?,?)', (post_id,data['format'],data['caption'],int(time.time())))
            for position,row in enumerate(rows):
                db.execute('INSERT INTO media VALUES(?,?,?,?)', (row['id'],row['extension'],row['digest'],row['size']))
                db.execute('INSERT INTO attachments(post_id,media_id,position) VALUES(?,?,?)', (post_id,row['id'],position))
                db.execute('DELETE FROM incoming_media WHERE id=?', (row['id'],))
                if verify_sources: db.execute('DELETE FROM multi_incoming_sources WHERE media_id=?',(row['id'],))
            store._audit(db,post_id,'created')
            db.execute('INSERT INTO audit(post_id,event,at) VALUES(?,?,?)', (post_id,'integration_transferred',int(time.time())))
            db.execute('INSERT INTO import_receipts(request_id,key_id,fingerprint,post_id,content_digest) VALUES(?,?,?,?,?)',
                       (data['requestId'],key['id'],fingerprint,post_id,data['contentDigest']))
        if check_active is not None: check_active()
    return receipt(store,key,data['requestId'])


def handle(handler, store_for, configuration_for, publisher):
    """Only root routes already allowed by the deployed proxy; no browser session."""
    route = urlsplit(handler.path)
    action = handler.headers.get('X-Editorial-Action','')
    if not action.startswith('import_'): return False
    def reply(status,body):
        handler.respond(status,body)
        return True
    if route.query or route.path not in ('/editorial/api/media','/editorial/api/drafts'):
        return reply(404,{'error':'Rota de integração indisponível.'})
    authorization = handler.headers.get('Authorization','')
    match = TOKEN.fullmatch(authorization[7:] if authorization.startswith('Bearer ') else '')
    if not match or len(handler.headers.get_all('Authorization',[])) != 1 or handler.headers.get_all('X-Editorial-Account',[]): return reply(403,{'error':'Conexão não autorizada.'})
    try:
        try:
            cfg = configuration_for(match[1])
            store = store_for(match[1])
        except account_registry.RegistryError:
            return reply(403,{'error':'Conexão não autorizada.'})
        key = authenticate(store,authorization[7:])
        if not key: return reply(403,{'error':'Conexão não autorizada.'})
        origin = urlsplit(cfg.get('public_base_url',''))
        if origin.scheme != 'https' or handler.headers.get('Host','').lower() != origin.netloc.lower() or not handler.transport_https():
            return reply(421,{'error':'Use o endereço HTTPS configurado.'})
        import editorial_http as http
        if route.path == '/editorial/api/media' and action=='import_upload':
            if not http._UPLOAD_SLOTS.acquire(blocking=False): return reply(429,{'error':'Uploads ocupados.'})
            try:
                position = handler.headers.get('X-Media-Index','')
                if not re.fullmatch(r'[0-9]{1,2}',position): raise core.EditorialError('Posição inválida.')
                raw = http._read(handler,http.UPLOAD_LIMIT)
                content,ext = http.validated_upload(raw,handler.headers.get('Content-Type'))
                return reply(201,stage(store,key,handler.headers.get('X-Import-Id'),int(position),content,ext))
            finally: http._UPLOAD_SLOTS.release()
        if route.path != '/editorial/api/drafts': return reply(404,{'error':'Rota indisponível.'})
        if handler.headers.get('Content-Type') != 'application/json': return reply(415,{'error':'JSON obrigatório.'})
        data = json.loads(http._read(handler,256*1024))
        if not isinstance(data,dict): raise core.EditorialError('Objeto JSON obrigatório.')
        if action=='import_commit': return reply(200,commit(store,key,data))
        if action=='import_receipt' and set(data)=={'requestId'}: return reply(200,receipt(store,key,data['requestId']))
        if action=='import_publish':
            if not key['can_publish']: return reply(403,{'error':'Esta conexão não pode publicar.'})
            if (set(data)!={'requestId','version','instagramAccountId','publishApproved'} or data['publishApproved'] is not True
                or type(data['version']) is not int or not isinstance(data['instagramAccountId'],str)
                or data['instagramAccountId'] != cfg.get('instagram_account_id')):
                raise core.EditorialError('Confirme a publicação e a conta de destino.')
            found = receipt(store,key,data['requestId'])
            if not found['found']: raise core.EditorialError('Transferência não encontrada.')
            if publisher is None: raise core.EditorialError('Publicação indisponível.')
            publisher.queue(match[1],found['id'],data['version'],import_request=data['requestId'], expected_account=data['instagramAccountId'])
            return reply(202,receipt(store,key,data['requestId']))
        return reply(404,{'error':'Operação indisponível.'})
    except core.EditorialConflict as exc: return reply(409,{'error':str(exc)})
    except core.EditorialError as exc: return reply(422,{'error':str(exc)})
    except (ValueError,TypeError,OverflowError,RecursionError): return reply(422,{'error':'Dados inválidos.'})
    except (TimeoutError,socket.timeout): return reply(408,{'error':'Tempo de leitura excedido.'})
    except Exception: return reply(503,{'error':'Integração temporariamente indisponível.'})
