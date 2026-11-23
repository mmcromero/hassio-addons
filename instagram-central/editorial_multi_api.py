"""Multi-account incoming API. Only a separate cei2 grant can use these routes."""
import hashlib
import json
import re
import socket
from urllib.parse import urlsplit

import editorial_connections as grants
import editorial_core as core
import editorial_drive as drive
import editorial_import as incoming

_ACTIONS = ('accounts', 'resolve', 'receipt', 'upload', 'drive_validate', 'drive_stage', 'commit')


def manage(connections, action, data):
    try:
        if action == 'integration_multi_list' and not data:
            return {'connections': [{**row, 'canPublish': False} for row in connections.list()]}
        if action == 'integration_multi_create' and set(data) == {'label', 'scope', 'grants', 'driveRootId'}:
            return {**connections.create(data['label'], data['scope'], data['grants'], data['driveRootId']), 'canPublish': False}
        if action == 'integration_multi_revoke' and set(data) == {'id'}:
            return {'revoked': connections.revoke(data['id'])}
        if action == 'integration_multi_grants' and set(data) == {'id', 'grants'}:
            return connections.update_grants(data['id'], data['grants'])
        if action == 'integration_multi_drive' and set(data) == {'id', 'driveRootId'}:
            return connections.update_drive(data['id'], data['driveRootId'])
        raise grants.Denied('Pedido inválido.')
    except grants.Denied as exc:
        raise core.EditorialError(str(exc)) from None


def scoped_id(row, request):
    if not isinstance(request, str) or not incoming.REQUEST.fullmatch(request):
        raise core.EditorialError('Identificador inválido.')
    return 'm2_' + hashlib.sha256((row['id'] + ':' + request).encode()).hexdigest()


def selected(accounts, headers, expected=None):
    targets = headers.get_all('X-Editorial-Account', [])
    if len(targets) != 1 or not any(a['id'] == targets[0] for a in accounts):
        raise grants.Denied('Escolha uma conta autorizada.')
    if expected is not None and expected != targets[0]:
        raise grants.Denied('Destino alterado durante a transferência.')
    return targets[0]


def _index(value):
    if not isinstance(value, str) or not re.fullmatch(r'[0-9]{1,2}', value) or int(value) >= 20:
        raise core.EditorialError('Posição inválida.')
    return int(value)


def _single(headers, name):
    values = headers.get_all(name, [])
    if len(values) != 1:
        raise core.EditorialError('Cabeçalho inválido.')
    return values[0]


def handle(handler, connections, settings, store_for, *, drive_download=None):
    # Never intercept/upgrade legacy cei1 credentials.
    auth = handler.headers.get('Authorization', '')
    if not isinstance(auth, str) or not auth.startswith('Bearer cei2.'):
        return False
    def reply(status, body):
        handler.respond(status, body)
        return True
    route = urlsplit(handler.path)
    action = handler.headers.get('X-Editorial-Action', '')
    if not action.startswith('import_'):
        return False
    action = action[7:]
    if route.query or route.path not in ('/editorial/api/media', '/editorial/api/drafts'):
        return reply(404, {'error': 'Rota de integração indisponível.'})
    if action not in _ACTIONS or (action == 'upload') != (route.path == '/editorial/api/media'):
        return reply(403, {'error': 'Operação não autorizada.'})
    if (len(handler.headers.get_all('Authorization', [])) != 1
            or len(handler.headers.get_all('X-Editorial-Action', [])) != 1
            or not grants.TOKEN.fullmatch(auth[7:])):
        return reply(403, {'error': 'Conexão não autorizada.'})
    token = auth[7:]
    drive_download = drive.download if drive_download is None else drive_download
    acquired = False
    try:
        cfg = settings()
        origin = urlsplit(cfg.get('public_base_url', ''))
        if (origin.scheme != 'https' or len(handler.headers.get_all('Host', [])) != 1
                or handler.headers.get('Host', '').lower() != origin.netloc.lower()
                or not handler.transport_https()):
            return reply(421, {'error': 'Use o endereço HTTPS configurado.'})
        import editorial_http as http
        # Authenticate before reading any media. Do not hold the main SQLite lock
        # across network I/O or image normalization.
        with connections.authorize(token) as (row, accounts):
            if action in ('accounts', 'resolve'):
                if handler.headers.get_all('X-Editorial-Account', []):
                    raise grants.Denied('Destino inválido.')
                account, root = None, row['drive_root']
            else:
                account, root = selected(accounts, handler.headers), row['drive_root']
        if action in ('upload', 'drive_stage', 'drive_validate'):
            acquired = http._UPLOAD_SLOTS.acquire(blocking=False)
            if not acquired:
                return reply(429, {'error': 'Uploads ocupados.'})
        if action == 'upload':
            mime = _single(handler.headers, 'Content-Type')
            raw = http._read(handler, drive.MAX_BYTES)
            content, extension = http.validated_upload(raw, mime)
            request = _single(handler.headers, 'X-Import-Id')
            position = _index(_single(handler.headers, 'X-Media-Index'))
            data = None
        else:
            if _single(handler.headers, 'Content-Type') != 'application/json':
                return reply(415, {'error': 'JSON obrigatório.'})
            data = json.loads(http._read(handler, 256 * 1024))
            if not isinstance(data, dict):
                raise core.EditorialError('Objeto JSON obrigatório.')
            if action == 'drive_validate':
                drive.manifest(data)
                raw = drive_download(cfg.get('drive_service_account_json', ''), root, account, data)
                # Confirm MIME decodes using the same checks as a real upload,
                # but do not stage, persist or create an EditorialStore.
                http.validated_upload(raw, data['mime'])
            if action == 'drive_stage':
                if set(data) != {'requestId', 'index', 'media'} or type(data['index']) is not int:
                    raise core.EditorialError('Manifesto de arquivo Drive inválido.')
                request, position = data['requestId'], _index(str(data['index']))
                scoped_id(row, request)
                drive.manifest(data['media'])
                raw = drive_download(cfg.get('drive_service_account_json', ''), root, account, data['media'])
                content, extension = http.validated_upload(raw, data['media']['mime'])
        # The grant is stored in the same SQLite DB as the account registry.
        # The immediate transaction serializes account/grant changes with stage
        # and commit; never call a helper that reopens that DB inside this lock.
        with connections.authorize(token) as (row, accounts):
            def active():
                if row['expires'] <= int(connections.clock()):
                    raise core.EditorialError('A conexão expirou.')
            active()
            if action == 'accounts':
                if data: raise core.EditorialError('Pedido inválido.')
                return reply(200, {'accounts': accounts, 'driveRootId': row['drive_root'] or None,
                                   'driveConfigured': bool(row['drive_root'] and cfg.get('drive_service_account_json')),
                                   'publishingAvailable': False})
            if action == 'resolve':
                if set(data) - {'destination'}: raise core.EditorialError('Pedido inválido.')
                bid = grants.resolve(accounts, data.get('destination'))
                return reply(200, {'connected': True, 'account': bid, 'publishingAvailable': False})
            account = selected(accounts, handler.headers, account)
            if action in ('drive_stage', 'drive_validate') and root != row['drive_root']:
                raise grants.Denied('Pasta Drive alterada durante a transferência.')
            if action == 'drive_validate':
                active()
                return reply(200, {'verified': True, 'mime': data['mime'], 'bytes': len(raw),
                                   'sha256': hashlib.sha256(raw).hexdigest(), 'persisted': False,
                                   'account': account, 'publishingAvailable': False})
            store = store_for(account)
            incoming.prepare(store)
            key = {'id': 'multi:' + row['id'], 'can_publish': 0}
            if action in ('upload', 'drive_stage'):
                source = {'size':len(raw),'digest':hashlib.sha256(raw).hexdigest(),'mime':mime if action == 'upload' else data['media']['mime']}
                result = incoming.stage(store, key, scoped_id(row, request), position, content, extension, check_active=active, source=source)
                status = 201
            elif action == 'receipt':
                if set(data) != {'requestId'}: raise core.EditorialError('Pedido inválido.')
                result = incoming.receipt(store, key, scoped_id(row, data['requestId']))
                active()
                status = 200
            elif action == 'commit':
                data = {**data, 'requestId': scoped_id(row, data.get('requestId'))}
                result = incoming.commit(store, key, data, check_active=active, verify_sources=True)
                status = 200
            else:
                raise grants.Denied('Operação não autorizada.')
        return reply(status, result)
    except grants.Denied:
        return reply(403, {'error': 'Conexão, destino ou arquivo não autorizado; confira o escopo e a pasta privada.'})
    except core.EditorialConflict as exc:
        return reply(409, {'error': str(exc)})
    except core.EditorialError as exc:
        return reply(422, {'error': str(exc)})
    except (TimeoutError, socket.timeout):
        return reply(408, {'error': 'Tempo de leitura excedido.'})
    except (ValueError, TypeError, OverflowError, RecursionError):
        return reply(422, {'error': 'Dados inválidos.'})
    except Exception:
        return reply(503, {'error': 'Integração temporariamente indisponível.'})
    finally:
        if acquired: http._UPLOAD_SLOTS.release()
