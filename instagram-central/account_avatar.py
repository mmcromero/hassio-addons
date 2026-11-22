"""Account-bound profile thumbnails. No provider URLs or tokens reach the browser."""
from io import BytesIO
import os
from pathlib import Path
import threading
import time
import warnings
from urllib.parse import urlsplit
from urllib.request import Request

from PIL import Image, ImageOps
import account_registry
import instagram_connection as meta

MAX_BYTES = 2 * 1024 * 1024
TTL = 24 * 60 * 60
RETRY = 15 * 60
# Fixed stripes bound synchronization memory even if many accounts are provisioned.
_LOCKS = [threading.Lock() for _ in range(32)]


def thumbnail(raw):
    if not isinstance(raw, bytes) or len(raw) > MAX_BYTES:
        raise ValueError('Invalid profile image')
    with warnings.catch_warnings():
        warnings.simplefilter('error', Image.DecompressionBombWarning)
        with Image.open(BytesIO(raw)) as image:
            if image.format not in ('JPEG', 'PNG', 'WEBP') or max(image.size) > 4096:
                raise ValueError('Invalid profile image')
            image.load()
            image = ImageOps.fit(ImageOps.exif_transpose(image).convert('RGB'), (96, 96))
            out = BytesIO()
            image.save(out, 'JPEG', quality=85)
            return out.getvalue()


def download(url, opener=None):
    """Only HTTPS Meta CDNs; no redirects, cookies or authorization headers."""
    if not isinstance(url, str) or len(url) > 8192:
        raise ValueError('Invalid profile URL')
    parts = urlsplit(url)
    host = (parts.hostname or '').lower()
    if (parts.scheme != 'https' or parts.username or parts.password or parts.port not in (None, 443)
            or parts.fragment or not any(host.endswith('.' + domain) for domain in ('fbcdn.net', 'cdninstagram.com'))):
        raise ValueError('Invalid profile URL')
    request = Request(url, headers={'Accept': 'image/jpeg,image/png,image/webp'})
    with (opener or meta._GRAPH_OPEN)(request, timeout=8) as response:
        raw = response.read(MAX_BYTES + 1)
    return thumbnail(raw)


def _root(data_dir, business):
    if not account_registry.valid_business_id(business):
        raise ValueError('Invalid account')
    root = Path(data_dir).absolute() / 'profile-images' / business
    if any(path.is_symlink() for path in (root, *root.parents)):
        raise ValueError('Invalid cache path')
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    return root


def get(data_dir, cfg, credential, *, clock=time.time, graph=None, fetch=None):
    """A failed optional photo never breaks login/identity checks or alters tokens.

    Identity-keyed cache survives restarts; negative cache bounds retries. Network
    runs only in the image request, never while rendering the application HTML.
    """
    if not meta.credential_status(credential, cfg)['account_verified']:
        return None
    business = cfg.get('business_id', 'umdoislab')
    identity = cfg.get('instagram_account_id')
    if not isinstance(identity, str) or not meta.IG_ACCOUNT.fullmatch(identity):
        return None
    try:
        root = _root(data_dir, business)
        photo, checked = root / (identity + '.jpg'), root / (identity + '.checked')
        if photo.is_symlink() or checked.is_symlink():
            return None
        cached = photo.read_bytes() if photo.exists() and photo.stat().st_size <= MAX_BYTES else None
        now = clock()
        if cached and now - photo.stat().st_mtime < TTL:
            return cached
        if checked.exists() and now - checked.stat().st_mtime < RETRY:
            return cached
        lock = _LOCKS[sum(business.encode()) % len(_LOCKS)]
        if not lock.acquire(blocking=False):
            return cached
        try:
            checked.touch(mode=0o600)
            result = (graph or meta.request_graph)(cfg.get('meta_graph_version'), '/' + identity,
                credential.get('access_token'), fields={'fields': 'id,username,profile_picture_url'})
            if (result.get('id') != identity or not isinstance(result.get('username'), str)
                    or result['username'].lower().lstrip('@') != cfg.get('instagram_expected_username', '').lower().lstrip('@')):
                return cached
            raw = (fetch or download)(result.get('profile_picture_url'))
            # Write only our own normalized JPEG; atomic replacement, no cached URLs.
            raw = thumbnail(raw)
            temporary = root / (identity + '.tmp')
            if temporary.is_symlink():
                return cached
            with open(temporary, 'wb') as stream:
                os.chmod(temporary, 0o600)
                stream.write(raw)
            temporary.replace(photo)
            return raw
        finally:
            lock.release()
    except Exception:
        # Optional decoration: no provider exception, response or secret in logs.
        return locals().get('cached')
