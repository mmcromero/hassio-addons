"""Optional HTTPS origin, sharing the existing Handler and persistent data."""
import logging
import ssl
from http.server import ThreadingHTTPServer
from pathlib import Path
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


def certificate_path(root, filename):
    if not isinstance(filename, str) or not filename or Path(filename).name != filename or filename in (".", ".."):
        raise ValueError("invalid certificate filename")
    return Path(root) / filename


class HTTPSServer(ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        logging.getLogger("instagram-central").warning("Standalone HTTPS request rejected")

    def get_request(self):
        connection, address = super().get_request()
        try:
            connection.settimeout(15)
            # The handshake runs in the request thread, so a slow client cannot
            # block accept or the internal HTTP listener. Reload on each accept
            # to pick up certificates renewed in the read-only /ssl volume.
            context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.minimum_version = ssl.TLSVersion.TLSv1_2
            context.load_cert_chain(self.certfile, self.keyfile)
            return context.wrap_socket(connection, server_side=True,
                                       do_handshake_on_connect=False), address
        except (OSError, ValueError):
            connection.close()
            raise OSError("HTTPS certificate unavailable") from None


def create_server(cfg, handler, *, address=("0.0.0.0", 9443), ssl_root="/ssl"):
    if not public_origin(cfg):
        return None
    if not isinstance(cfg.get("panel_password"), str) or len(cfg["panel_password"]) < 16:
        raise ValueError("panel password required for HTTPS")
    certfile = certificate_path(ssl_root, cfg.get("certfile", "fullchain.pem"))
    keyfile = certificate_path(ssl_root, cfg.get("keyfile", "privkey.pem"))
    # Validate before binding; never fall back to plaintext on the public port.
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile, keyfile)
    http = HTTPSServer(address, handler)
    http.certfile, http.keyfile = certfile, keyfile
    return http
