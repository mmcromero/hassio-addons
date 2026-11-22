"""Account-scoped Editorial routes, with explicit publishing authorization."""
from datetime import datetime
from io import BytesIO
from pathlib import Path
import json
import re
import socket
import struct
import threading
import warnings
from zoneinfo import ZoneInfo

from PIL import Image, UnidentifiedImageError
import editorial_core
import editorial_import
import editorial_graph
import editorial_publishing
import panel_login
import interface_ui

ASSETS = Path(__file__).parent / "editorial-ui"
ACTIONS = ("upload", "draft", "approve", "schedule", "cancel", "check", "publish", "activate", "reset", "reconcile", "retry", "delete_post", "delete_media", "metrics", "history_start", "history_cancel") + editorial_import.ACTIONS
UPLOAD_LIMIT = 25 * 1024 * 1024
_UPLOAD_SLOTS = threading.BoundedSemaphore(2)
_ID = r"[0-9a-f]{32}"
CSP = ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self'; "
       "media-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'none'; "
       "object-src 'none'; frame-ancestors 'self'")


def csrf_action(action, business_id="umdoislab"):
    return "editorial:" + business_id + ":" + action


def _boxes(raw):
    offset = 0
    boxes = []
    while offset < len(raw):
        if len(raw) - offset < 8:
            raise editorial_core.EditorialError("Contêiner MP4 inválido")
        size, kind = struct.unpack_from(">I4s", raw, offset)
        header = 8
        if size == 1:
            if len(raw) - offset < 16:
                raise editorial_core.EditorialError("Contêiner MP4 inválido")
            size = struct.unpack_from(">Q", raw, offset + 8)[0]
            header = 16
        if size < header or size > len(raw) - offset:
            raise editorial_core.EditorialError("Contêiner MP4 inválido")
        boxes.append((kind, raw[offset + header:offset + size]))
        if len(boxes) > 4096:
            raise editorial_core.EditorialError("Contêiner MP4 muito complexo")
        offset += size
    return boxes


def validated_upload(raw, content_type):
    """Re-encode images to discard metadata/polyglots; never accept SVG/HTML.

    MP4 validation is structural, not a codec decoder. Bytes remain private and
    are served as video/mp4 under sandbox + nosniff, never as a document.
    """
    if content_type not in ("image/png", "image/jpeg", "video/mp4"):
        raise editorial_core.EditorialError("Tipo de mídia não aceito")
    if not raw or len(raw) > UPLOAD_LIMIT:
        raise editorial_core.EditorialError("Arquivo vazio ou acima de 25 MiB")
    if content_type == "video/mp4":
        boxes = _boxes(raw)
        if (not boxes or boxes[0][0] != b"ftyp" or len(boxes[0][1]) < 8 or
                boxes[0][1][:4] not in (b"isom", b"iso2", b"mp41", b"mp42", b"avc1", b"M4V ") or
                not any(k == b"mdat" and v for k, v in boxes) or
                any(k not in (b"ftyp", b"moov", b"mdat", b"free", b"skip", b"wide") for k, _ in boxes)):
            raise editorial_core.EditorialError("Contêiner MP4 não aceito")
        moov = [v for k, v in boxes if k == b"moov"]
        if len(moov) != 1 or not {b"mvhd", b"trak"} <= {k for k, _ in _boxes(moov[0])}:
            raise editorial_core.EditorialError("Índice MP4 inválido")
        return raw, "mp4"
    expected = "PNG" if content_type == "image/png" else "JPEG"
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error", Image.DecompressionBombWarning)
            with Image.open(BytesIO(raw)) as image:
                if image.format != expected or image.width * image.height > 20_000_000:
                    raise editorial_core.EditorialError("Imagem inválida ou acima de 20 megapixels")
                image.verify()
            with Image.open(BytesIO(raw)) as image:
                image.load()
                normalized = image.convert("RGBA" if expected == "PNG" else "RGB")
                output = BytesIO()
                normalized.save(output, format=expected)
        result = output.getvalue()
        if len(result) > UPLOAD_LIMIT:
            raise editorial_core.EditorialError("Imagem acima do limite")
        return result, "png" if expected == "PNG" else "jpg"
    except (OSError, ValueError, SyntaxError, UnidentifiedImageError, Image.DecompressionBombError,
            Image.DecompressionBombWarning):
        raise editorial_core.EditorialError("Imagem inválida") from None


def _read(handler, limit):
    lengths = handler.headers.get_all("Content-Length", [])
    if handler.headers.get("Transfer-Encoding") or len(lengths) != 1 or not re.fullmatch(r"[0-9]{1,9}", lengths[0]):
        raise editorial_core.EditorialError("Comprimento inválido")
    length = int(lengths[0])
    if not 0 < length <= limit:
        raise editorial_core.EditorialError("Tamanho não permitido")
    handler.connection.settimeout(10)
    raw = handler.rfile.read(length)
    if len(raw) != length:
        raise editorial_core.EditorialError("Upload incompleto")
    return raw


def _schedule_time(value):
    # Civil São Paulo time is converted by IANA tzdata, never a fixed UTC offset.
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d\d-\d\dT\d\d:\d\d", value):
        raise editorial_core.EditorialError("Horário inválido")
    naive = datetime.fromisoformat(value)
    zone = ZoneInfo("America/Sao_Paulo")
    first, second = naive.replace(tzinfo=zone, fold=0), naive.replace(tzinfo=zone, fold=1)
    if first.utcoffset() != second.utcoffset():
        raise editorial_core.EditorialError("Horário local inexistente ou ambíguo")
    return first


def handle(handler, method, route, cfg, authorized, store_factory, *, business_id="umdoislab", publisher=None, history=None):
    if route.path != "/editorial" and not route.path.startswith("/editorial/"):
        return False
    def reply(status, body, mime="application/json"):
        handler.respond(status, body, mime, csp=CSP)
        return True
    if not authorized:
        return reply(403, {"error": "Entre na Central Instagram para acessar o Editorial."})
    if route.query:
        return reply(404, {"error": "Rota indisponível"})
    try:
        # Handler authenticates the installation owner and resolves an explicit
        # enabled account path; query/body fields never choose the store.
        store = store_factory(business_id)
        if method == "GET":
            if route.path == "/editorial":
                handler.send_response(303)
                handler.send_header("Location", "editorial/")
                handler.send_header("Cache-Control", "no-store")
                handler.send_header("Content-Length", "0")
                handler.end_headers()
                return True
            static = {"/editorial/": ("index.html", "text/html"),
                      "/editorial/editorial.js": ("editorial.js", "text/javascript"),
                      "/editorial/editorial.css": ("editorial.css", "text/css")}
            if route.path in static:
                filename, mime = static[route.path]
                raw = (ASSETS / filename).read_bytes()
                if mime == 'text/html':
                    import html
                    username = html.escape(str(cfg.get('instagram_expected_username') or 'umdoislab'))
                    display = html.escape(str(cfg.get('account_display_name') or 'Umdoislab'))
                    raw = (raw.decode().replace('@umdoislab', '@' + username)
                           .replace('<strong>umdoislab</strong>', '<strong>' + username + '</strong>')
                           .replace('<strong>UMDOISLAB</strong>', '<strong>' + display + '</strong>')
                           .replace('<div class="crumb">Umdoislab ', '<div class="crumb">' + display + ' ').encode())
                    raw = raw.decode().replace('<!--CENTRAL_SIDEBAR-->', interface_ui.sidebar(cfg, editorial=True))
                    raw = raw.replace('<!--CENTRAL_HEADER-->', interface_ui.header(cfg, 'Visão geral', editorial=True))
                    raw = raw.replace('<!--INITIAL_SKELETON-->', interface_ui.INITIAL_SKELETON).encode()
                return reply(200, raw, mime)
            if route.path == "/editorial/api/csrf":
                return reply(200, {a: panel_login.admin_csrf_token(handler.headers.get("Cookie", ""),
                    cfg.get("panel_password"), csrf_action(a, business_id)) for a in ACTIONS})
            if route.path == "/editorial/api/state":
                publication = publisher.public_state(business_id) if publisher else {'ready': False, 'message': 'Publicação não configurada.'}
                return reply(200, {**store.snapshot(), "businessId": business_id,
                    'accountUsername': cfg.get('instagram_expected_username'),
                    "publishingEnabled": publication['ready'], 'publication': publication,
                    'history':history.public_state(business_id) if history else {'status':'idle'}})
            if re.fullmatch("/editorial/media/" + _ID, route.path):
                raw, mime = store.read_media(route.path.rsplit("/", 1)[1])
                return reply(200, raw, mime)
            return reply(404, {"error": "Rota indisponível"})
        if method != "POST":
            return reply(405, {"error": "Método não permitido"})
        action = None
        post_id = None
        if route.path == "/editorial/api/media":
            action = "upload"
        elif route.path == "/editorial/api/drafts":
            action = "draft"
        elif route.path == '/editorial/api/publication/check':
            action = 'check'
        else:
            match = re.fullmatch("/editorial/api/posts/(" + _ID + ")/(approve|schedule|cancel|publish|activate|reset|reconcile|retry)", route.path)
            if match:
                post_id, action = match.groups()
        if action is None:
            return reply(404, {"error": "Rota indisponível"})
        # Preserve the deployed proxy's exact route allowlist. New operations
        # use existing POST paths and remain bound to their own account CSRF.
        requested_action = handler.headers.get('X-Editorial-Action')
        if requested_action:
            if route.path == '/editorial/api/drafts' and requested_action in ('check', 'delete_media', 'history_start', 'history_cancel') + editorial_import.ACTIONS:
                action = requested_action
            elif post_id and action == 'approve' and requested_action in ('publish', 'activate', 'reset', 'reconcile', 'retry', 'delete_post', 'metrics'):
                action = requested_action
            else:
                return reply(422, {'error': 'Ação indisponível nesta rota.'})
        if not panel_login.admin_csrf_valid(handler.headers.get("Cookie", ""), cfg.get("panel_password"),
                                           csrf_action(action, business_id), handler.headers.get("X-CSRF-Token")):
            return reply(403, {"error": "Sessão ou proteção CSRF inválida"})
        if action == "upload":
            if not _UPLOAD_SLOTS.acquire(blocking=False):
                return reply(429, {"error": "Uploads ocupados. Tente novamente."})
            try:
                raw = _read(handler, UPLOAD_LIMIT)
                content, extension = validated_upload(raw, handler.headers.get("Content-Type"))
                media_id = store.add_media(content, extension)
            finally:
                _UPLOAD_SLOTS.release()
            return reply(201, {"id": media_id})
        if handler.headers.get("Content-Type") != "application/json":
            return reply(415, {"error": "JSON obrigatório"})
        data = json.loads(_read(handler, 256 * 1024 if action == "draft" else 16 * 1024))
        if not isinstance(data, dict):
            raise editorial_core.EditorialError("Objeto JSON obrigatório")
        if action in editorial_import.ACTIONS:
            return reply(200, editorial_import.manage(store, business_id, action, data))
        if action in ('history_start','history_cancel'):
            if history is None: raise editorial_core.EditorialError('Sincronização não configurada.')
            if action=='history_start':
                if set(data)!={'downloadMedia'} or type(data['downloadMedia']) is not bool: raise editorial_core.EditorialError('Pedido inválido.')
                return reply(200,{'history':history.start(business_id,download_media=data['downloadMedia'])})
            if data: raise editorial_core.EditorialError('Pedido inválido.')
            return reply(200,{'history':history.cancel(business_id)})
        if action == 'delete_media':
            if set(data) != {'mediaId'}:
                raise editorial_core.EditorialError('Campos inválidos')
            return reply(200, {'deleted': True, **store.delete_media(data['mediaId'])})
        if action == 'delete_post':
            if set(data) != {'version', 'deleteUnusedMedia'}:
                raise editorial_core.EditorialError('Campos inválidos')
            result = store.delete_post(post_id, expected_version=data['version'], delete_unused_media=data['deleteUnusedMedia'])
            return reply(200, {'deleted': True, **result})
        if action == 'check':
            if data or publisher is None:
                raise editorial_core.EditorialError('Pedido inválido.')
            publisher.check(business_id)
            return reply(200, publisher.public_state(business_id))
        if action == "draft":
            required = {"format", "caption", "mediaIds"}
            if "id" in data:
                required |= {"id", "version"}
            allowed = required | {"captionMode", "slideCaptions"}
            if not required.issubset(data) or not set(data).issubset(allowed):
                raise editorial_core.EditorialError("Campos inválidos")
            if "id" in data and (not isinstance(data["id"], str) or not re.fullmatch(_ID, data["id"]) or type(data["version"]) is not int):
                raise editorial_core.EditorialError("Identificador ou versão inválidos")
            post_id = store.save_draft(
                data["format"], data["caption"], data["mediaIds"],
                post_id=data.get("id"), expected_version=data.get("version"),
                caption_mode=data.get("captionMode", "general"),
                slide_captions=data.get("slideCaptions"))
        else:
            required = {"version", "localTime"} if action == "schedule" else {"version"}
            if action == 'retry':
                required.add('confirmNotPublished')
            if set(data) != required or type(data.get("version")) is not int:
                raise editorial_core.EditorialError("Campos ou versão inválidos")
            if action == "approve":
                store.approve(post_id, expected_version=data["version"])
            elif action == "schedule":
                if publisher is None:
                    raise editorial_core.EditorialError('Publicação não configurada.')
                publisher.queue(business_id, post_id, data['version'], when=_schedule_time(data['localTime']))
            elif action == 'cancel':
                store.cancel_schedule(post_id, expected_version=data["version"])
            elif action in ('publish', 'activate'):
                if publisher is None:
                    raise editorial_core.EditorialError('Publicação não configurada.')
                publisher.queue(business_id, post_id, data['version'], activate=action == 'activate')
            elif action == 'metrics':
                if publisher is None:
                    raise editorial_core.EditorialError('Conexão não configurada.')
                return reply(200, {'metrics': publisher.refresh_metrics(business_id, post_id, data['version'])})
            else:
                if publisher is None:
                    raise editorial_core.EditorialError('Publicação não configurada.')
                publisher.recover(business_id, post_id, data['version'], action,
                                  confirmed=data.get('confirmNotPublished') is True)
        return reply(200, {"id": post_id, "saved": True, "published": False})
    except editorial_graph.PublishingError as error:
        return reply(422, {'error': editorial_publishing.message(error)})
    except editorial_core.EditorialConflict as error:
        return reply(409, {"error": str(error)})
    except (editorial_core.EditorialError, ValueError, TypeError, OverflowError, RecursionError) as error:
        message = str(error) if isinstance(error, editorial_core.EditorialError) else "Dados inválidos"
        return reply(422, {"error": message})
    except (TimeoutError, socket.timeout):
        return reply(408, {"error": "Tempo de leitura excedido"})
    except Exception:
        # Never expose paths, database contents, configuration or credentials.
        return reply(503, {"error": "Editorial temporariamente indisponível"})
