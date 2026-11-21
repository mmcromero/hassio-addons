"""Public HTTPS origin behind the existing reverse proxy; no public listener."""
from urllib.parse import urlsplit


def public_origin(cfg):
    value = cfg.get("public_base_url", "")
    if value == "":
        return ""
    if not isinstance(value, str) or any(c.isspace() for c in value):
        raise ValueError("invalid public origin")
    try:
        url = urlsplit(value)
        port = url.port
        if (url.scheme != "https" or not url.hostname or url.username is not None
                or url.password is not None or url.path not in ("", "/")
                or url.query or url.fragment or url.hostname in ("localhost", "127.0.0.1", "::1")
                or url.hostname.endswith(".local") or port == 0):
            raise ValueError("invalid public origin")
    except ValueError:
        raise ValueError("invalid public origin") from None
    return "https://" + url.netloc.lower()


def oauth_origin_matches(cfg):
    origin = public_origin(cfg)
    return not origin or cfg.get("meta_oauth_redirect_uri") == origin + "/oauth/meta/callback"

