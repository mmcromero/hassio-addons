"""Expiring per-post media capabilities served by the existing HTTPS callback."""
from io import BytesIO
import hashlib
import json
import re
import secrets
import time
from urllib.parse import parse_qs, urlencode

from PIL import Image
import editorial_core as core

TOKEN = re.compile(r'[A-Za-z0-9_-]{43}\Z')


def image_for_meta(raw):
    try:
        with Image.open(BytesIO(raw)) as image:
            image.load()
            # JPEG has no alpha channel. Preserve dimensions; use white behind alpha.
            rgba = image.convert('RGBA')
            rgb = Image.new('RGB', rgba.size, 'white')
            rgb.paste(rgba, mask=rgba.getchannel('A'))
            output = BytesIO()
            rgb.save(output, format='JPEG', quality=92)
            data = output.getvalue()
        if len(data) > 8_000_000:
            raise core.EditorialError('A imagem convertida deve ter até 8 MB para o Instagram.')
        return data
    except (OSError, ValueError, Image.DecompressionBombError):
        raise core.EditorialError('Não foi possível preparar a imagem para o Instagram.') from None


class MediaDelivery:
    def __init__(self, database, store_factory):
        self.database = database
        self.store_factory = store_factory

    def issue(self, business, post, media, origin, *, now=None):
        clock = int(time.time()) if now is None else now
        token = secrets.token_urlsafe(32)
        store = self.store_factory(business)
        with store._db() as db:
            context = db.execute('SELECT revision,publication_data FROM posts WHERE id=?', (post,)).fetchone()
        if context is None:
            raise core.EditorialError('Publicação inexistente.')
        run_id = json.loads(context[1]).get('run_id', '')
        with self.database() as db:
            db.execute('DELETE FROM publication_downloads WHERE expires_at<=?', (clock,))
            db.execute('''INSERT INTO publication_downloads
                (token_hash,business_id,post_id,media_id,expires_at,revision,run_id) VALUES(?,?,?,?,?,?,?)''',
                (hashlib.sha256(token.encode()).hexdigest(), business, post, media, clock + 3600, context[0], run_id))
        return origin + '/webhook/instagram?' + urlencode({'editorial_media': token})

    def read(self, query, *, now=None):
        clock = int(time.time()) if now is None else now
        try:
            values = parse_qs(query, keep_blank_values=True, max_num_fields=1, strict_parsing=True)
        except ValueError:
            return None
        if set(values) != {'editorial_media'} or len(values['editorial_media']) != 1 or not TOKEN.fullmatch(values['editorial_media'][0]):
            return None
        digest = hashlib.sha256(values['editorial_media'][0].encode()).hexdigest()
        with self.database() as db:
            row = db.execute('''SELECT business_id,post_id,media_id,revision,run_id FROM publication_downloads
                                WHERE token_hash=? AND expires_at>?''', (digest, clock)).fetchone()
        if row is None:
            return None
        store = self.store_factory(row[0])  # Also checks this account remains enabled.
        with store._db() as db:
            allowed = db.execute('''SELECT p.publication_data FROM posts p JOIN attachments a ON a.post_id=p.id
                WHERE p.id=? AND a.media_id=? AND p.publish_authorized=1
                AND p.state IN ('scheduled','publishing') AND p.revision=p.approved_revision AND p.revision=?''',
                (row[1], row[2], row[3])).fetchone()
        if allowed is None or not row[4] or json.loads(allowed[0]).get('run_id') != row[4]:
            return None
        raw, mime = store.read_media(row[2])
        return (raw, mime) if mime == 'video/mp4' else (image_for_meta(raw), 'image/jpeg')


def serve(handler, route, delivery, *, head=False):
    if route.path != '/webhook/instagram' or not route.query.startswith('editorial_media='):
        return False
    try:
        item = delivery.read(route.query)
    except Exception:
        item = None
    if item is None:
        if head:
            handler.send_response(404)
            handler.send_header('Content-Length', '0')
            handler.end_headers()
        else:
            handler.respond(404, {'error': 'not found'})
        return True
    raw, mime = item
    start, end, status = 0, len(raw) - 1, 200
    requested = handler.headers.get('Range')
    if requested:
        match = re.fullmatch(r'bytes=([0-9]{0,9})-([0-9]{0,9})', requested)
        valid = bool(match and (match[1] or match[2]))
        if valid and match[1]:
            start, end = int(match[1]), min(int(match[2]) if match[2] else end, end)
            valid = start < len(raw) and end >= start
        elif valid:
            valid = int(match[2]) > 0
            start = max(0, len(raw) - int(match[2]))
        if not valid:
            handler.send_response(416)
            handler.send_header('Content-Range', 'bytes */' + str(len(raw)))
            handler.send_header('Content-Length', '0')
            handler.send_header('Cache-Control', 'no-store')
            handler.end_headers()
            return True
        status = 206
    handler.send_response(status)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(end - start + 1))
    handler.send_header('Cache-Control', 'no-store')
    handler.send_header('Referrer-Policy', 'no-referrer')
    handler.send_header('X-Content-Type-Options', 'nosniff')
    handler.send_header('Content-Security-Policy', "default-src 'none'; sandbox")
    handler.send_header('Accept-Ranges', 'bytes')
    if status == 206:
        handler.send_header('Content-Range', f'bytes {start}-{end}/{len(raw)}')
    handler.end_headers()
    if not head:
        handler.wfile.write(raw[start:end + 1])
    return True
