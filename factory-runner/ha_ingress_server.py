"""HA Ingress status and owner-consent adapters, isolated from the loopback API.

The service is separate from the loopback API. It verifies the Supervisor TCP
peer and HA user before reading identity headers; direct network peers fail closed.
"""
from __future__ import annotations

from http.server import BaseHTTPRequestHandler, HTTPServer
import re
import sys
from urllib.parse import parse_qs, urlsplit

from ha_ingress_identity import is_supervisor_ingress_peer, verify_ha_ingress_context
from publication_contract import PublicationError

COOKIE_NAME = "factory_owner_session"
MAX_FORM_BODY = 4096
MAX_PAGE_BYTES = 1024 * 1024
_PROPOSAL = re.compile(r"^([a-f0-9]{32})$")
_SESSION = re.compile(r"^[a-f0-9]{64}$")
_REASON_CODE = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_ALLOWED_FORM = frozenset(("csrf", "password", "confirmation"))
_ALLOWED_ENROLL_FORM = frozenset(("csrf", "password", "password_confirm", "confirmation"))


def _header_values(headers, wanted):
    if not hasattr(headers, "items"):
        return []
    return [
        str(value)
        for name, value in headers.items()
        if str(name).lower() == wanted.lower()
    ]


def _one_header(headers, wanted):
    values = _header_values(headers, wanted)
    if len(values) != 1:
        return None
    value = values[0]
    if not value or value != value.strip():
        return None
    return value


def _cookie_session(headers):
    # HTTP/2 and reverse proxies can split Cookie into several fields.
    # Accept exactly one owner cookie across all fields, never duplicates.
    values = _header_values(headers, "Cookie")
    if not values:
        return None
    matches = []
    for part in "; ".join(values).split(";"):
        name, separator, value = part.strip().partition("=")
        if separator and name == COOKIE_NAME:
            matches.append(value)
    if len(matches) != 1 or not _SESSION.fullmatch(matches[0]):
        return None
    return matches[0]


def _response(status, body, headers=None):
    payload = body.encode("utf-8") if isinstance(body, str) else body
    result_headers = {
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
        "Referrer-Policy": "no-referrer",
        "Content-Type": "text/html; charset=utf-8",
    }
    if headers:
        result_headers.update(headers)
    return status, result_headers, payload


def _owner_error_response(reason, *, enrollment):
    if enrollment and reason == "owner_enrollment_session_invalid":
        message = "A sessão do formulário expirou ou perdeu a validade. Volte à página inicial e abra um novo cadastro."
    elif enrollment and reason == "owner_enrollment_input_invalid":
        message = "Confira os campos: senha com pelo menos 16 caracteres, confirmação idêntica e a palavra CADASTRAR."
    elif enrollment and reason == "owner_already_enrolled":
        message = "O cadastro já foi concluído. Volte à página inicial e atualize."
    elif enrollment and reason == "invalid_request":
        message = "Os dados enviados não passaram na validação. Reabra o formulário e confira os campos."
    elif enrollment:
        message = "Falha técnica no cadastro. Não envie novamente até confirmar o estado do cadastro."
    else:
        message = "Não foi possível concluir a autorização. Reabra a proposta pelo Home Assistant."
    back = '<p><a href="./">Voltar ao cadastro</a></p>' if enrollment else ""
    page = (
        '<!doctype html><meta charset="utf-8"><title>Operação não concluída</title>'
        '<h1>Não foi possível concluir</h1><p>' + message + '</p>'
        '<p>Código: <code>' + reason + '</code></p>' + back
    )
    headers = {
        "Content-Security-Policy": "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'",
    }
    return _response(503 if reason == "internal_error" else 403, page, headers)


def dispatch_owner_consent(
    ui,
    *,
    method,
    path,
    peer_ip,
    headers,
    body=b"",
    expected_ha_user_id,
    owner_id,
):
    """Handle one bounded request; never exposes the session or grant in body."""
    context = {"peer_ip": peer_ip, "headers": headers,
               "ingress_path": (_one_header(headers, "X-Ingress-Path") or "").rstrip("/")}
    owner = verify_ha_ingress_context(
        context,
        expected_ha_user_id=expected_ha_user_id,
        owner_id=owner_id,
    )
    if owner is None:
        return _response(403, "Acesso negado.")

    parsed = urlsplit(path)
    if parsed.query or parsed.fragment:
        return _response(400, "Requisição inválida.")

    if method == "GET":
        ingress_path = _one_header(headers, "X-Ingress-Path")
        if parsed.path == "/owner-enroll":
            return _response(303, "Redirecionando.", {
                "Location": ingress_path.rstrip("/") + "/owner-enroll/"
            })
        if parsed.path == "/":
            try:
                view = ui.home_view(context)
            except Exception:
                return _response(403, "Acesso negado.")
            page = view.get("html") if isinstance(view, dict) else None
            security_headers = view.get("headers", {}) if isinstance(view, dict) else {}
            if not isinstance(page, str) or len(page.encode("utf-8")) > MAX_PAGE_BYTES:
                return _response(503, "Interface indisponível.")
            return _response(200, page, security_headers)
        enrollment = parsed.path == "/owner-enroll/"
        if enrollment:
            try:
                view = ui.enroll_view(context)
            except Exception:
                return _response(404, "Cadastro indisponível.")
            cookie_suffix = "/owner-enroll/"
        else:
            match = _PROPOSAL.fullmatch(parsed.path.removeprefix("/owner-consent/")) if parsed.path.startswith("/owner-consent/") else None
            if not match:
                return _response(404, "Não encontrado.")
            try:
                view = ui.view(match.group(1), context)
            except Exception:
                return _response(404, "Proposta indisponível.")
            cookie_suffix = "/owner-consent/"
        session = view.get("session") if isinstance(view, dict) else None
        page = view.get("html") if isinstance(view, dict) else None
        security_headers = view.get("headers", {}) if isinstance(view, dict) else {}
        ingress_path = _one_header(headers, "X-Ingress-Path")
        if not isinstance(session, str) or not _SESSION.fullmatch(session) or not isinstance(page, str):
            return _response(503, "Interface de consentimento indisponível.")
        if len(page.encode("utf-8")) > MAX_PAGE_BYTES:
            return _response(503, "Conteúdo de consentimento excede o limite.")
        # Initial enrollment uses a one-time form nonce bound to the verified HA ingress.
        # Publication consent continues to require its separate HttpOnly cookie.
        if enrollment:
            return _response(200, page, security_headers)
        cookie_path = ingress_path.rstrip("/") + cookie_suffix
        cookie = (
            f"{COOKIE_NAME}={session}; Max-Age=120; Path={cookie_path}; "
            "Secure; HttpOnly; SameSite=Strict"
        )
        return _response(200, page, {
            **security_headers,
            "Set-Cookie": cookie,
        })

    if method == "POST":
        if parsed.path == "/owner-consent/consent":
            allowed_form = _ALLOWED_FORM
            enrollment = False
        elif parsed.path == "/owner-enroll/submit":
            allowed_form = _ALLOWED_ENROLL_FORM
            enrollment = True
        else:
            return _response(404, "Não encontrado.")
        if len(body) > MAX_FORM_BODY:
            return _response(413, "Requisição muito grande.")
        if _header_values(headers, "Transfer-Encoding"):
            return _response(400, "Transfer-Encoding não aceito.")
        content_type = _one_header(headers, "Content-Type")
        if not content_type or content_type.lower() != "application/x-www-form-urlencoded":
            return _response(415, "Formato não aceito.")
        origin = _one_header(headers, "Origin")
        session = _cookie_session(headers)
        if not origin or (not enrollment and not session):
            reason = "origin_missing" if not origin else "owner_session_cookie_missing_or_invalid"
            print("[OWNER-UI] DENIED: " + reason, flush=True)
            return _response(403, 
                "<!doctype html><meta charset=utf-8><h1>Sessão inválida</h1>"
                "<p>Abra novamente o formulário de autorização pelo Home Assistant.</p>"
                + ('<p><a href="./">Voltar ao cadastro</a></p>' if enrollment else ""),
                {"Content-Security-Policy": "default-src 'none'; base-uri 'none'; form-action 'none'; frame-ancestors 'self'"})
        try:
            decoded = body.decode("utf-8")
            form = parse_qs(decoded, keep_blank_values=True, strict_parsing=True,
                             max_num_fields=8)
        except (UnicodeDecodeError, ValueError):
            return _response(400, "Formulário inválido.")
        if set(form) != allowed_form or any(len(values) != 1 for values in form.values()):
            return _response(400, "Formulário inválido.")
        payload = {key: values[0] for key, values in form.items()}
        try:
            if enrollment:
                nonce = payload["csrf"]
                if not _SESSION.fullmatch(nonce):
                    return _response(403, "Sessão de cadastro inválida.")
                ui.enroll(nonce, payload, context, origin)
            else:
                ui.consent(session, payload, context, origin)
        except Exception as exc:
            action = "ENROLLMENT" if enrollment else "CONSENT"
            if isinstance(exc, PublicationError):
                reason = str(exc)
                if not _REASON_CODE.fullmatch(reason):
                    reason = "internal_error"
                print(f"[OWNER-UI] {action} REJECTED: {reason}", file=sys.stderr, flush=True)
            elif isinstance(exc, ValueError):
                reason = "invalid_request"
                print(f"[OWNER-UI] {action} REJECTED: invalid_request", file=sys.stderr, flush=True)
            else:
                reason = "internal_error"
                print(f"[OWNER-UI] {action} ERROR: {type(exc).__name__}", file=sys.stderr, flush=True)
            return _owner_error_response(reason, enrollment=enrollment)
        ingress_path = _one_header(headers, "X-Ingress-Path")
        cookie_path = ingress_path.rstrip("/") + ("/owner-enroll/" if enrollment else "/owner-consent/")
        clear_cookie = (
            f"{COOKIE_NAME}=; Max-Age=0; Path={cookie_path}; "
            "Secure; HttpOnly; SameSite=Strict"
        )
        message = ("Cadastro do proprietário concluído. Reinicie o add-on para concluir a preparação."
                   if enrollment else "Consentimento registrado. Nenhuma publicação foi executada.")
        return _response(200, message, {} if enrollment else {
            "Set-Cookie": clear_cookie,
        })

    return _response(405, "Método não permitido.", {"Allow": "GET, POST"})


def make_owner_consent_handler(*, ui, expected_ha_user_id, owner_id):
    """Create a request handler; caller owns the decision to start the listener."""
    class OwnerConsentHandler(BaseHTTPRequestHandler):
        server_version = "FactoryRunnerOwnerIngress/1"

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            # Request paths, cookies, headers and bodies are deliberately not logged.
            return

        def _send(self, result):
            status, headers, body = result
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _trusted(self):
            return verify_ha_ingress_context(
                {"peer_ip": self.client_address[0], "headers": self.headers},
                expected_ha_user_id=expected_ha_user_id,
                owner_id=owner_id,
            ) is not None

        def do_GET(self):
            self._send(dispatch_owner_consent(
                ui, method="GET", path=self.path, peer_ip=self.client_address[0],
                headers=self.headers, expected_ha_user_id=expected_ha_user_id,
                owner_id=owner_id,
            ))

        def do_POST(self):
            if not self._trusted():
                self._send(_response(403, "Acesso negado."))
                return
            # Reject ambiguous HTTP framing before reading any request body.
            # dispatch_owner_consent repeats this check as defense in depth.
            if _header_values(self.headers, "Transfer-Encoding"):
                self._send(_response(400, "Transfer-Encoding não aceito."))
                return
            length = _one_header(self.headers, "Content-Length")
            if not length or not length.isdigit():
                self._send(_response(400, "Tamanho inválido."))
                return
            if len(length) > 4:
                self._send(_response(413, "Requisição muito grande."))
                return
            size = int(length)
            if size > MAX_FORM_BODY:
                self._send(_response(413, "Requisição muito grande."))
                return
            body = self.rfile.read(size)
            if len(body) != size:
                self._send(_response(400, "Requisição incompleta."))
                return
            self._send(dispatch_owner_consent(
                ui, method="POST", path=self.path, peer_ip=self.client_address[0],
                headers=self.headers, body=body,
                expected_ha_user_id=expected_ha_user_id, owner_id=owner_id,
            ))

    return OwnerConsentHandler


def serve_owner_consent(ui, *, expected_ha_user_id, owner_id, port=8099):
    """Serve on the container network; the handler rejects every non-Supervisor peer."""
    handler = make_owner_consent_handler(
        ui=ui,
        expected_ha_user_id=expected_ha_user_id,
        owner_id=owner_id,
    )
    # One owner UI session at a time: keep the in-memory session map serialized.
    server = HTTPServer(("0.0.0.0", int(port)), handler)
    server.serve_forever()



def dispatch_owner_ingress_disabled(*, method, path, peer_ip):
    """Serve a harmless setup status while owner consent remains disabled."""
    if not is_supervisor_ingress_peer(peer_ip):
        return _response(403, "Acesso negado.")
    if method == "GET" and path == "/":
        page = (
            "<!doctype html><html lang='pt-BR'><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width,initial-scale=1'>"
            "<title>Factory Runner</title><h1>Autorização desativada</h1>"
            "<p>A interface de autorização do proprietário está desativada.</p>"
            "<p>Para habilitar o cadastro e o consentimento, configure as opções "
            "do add-on no Home Assistant:</p><ul>"
            "<li><code>owner_ingress_enabled</code>: true</li>"
            "<li><code>owner_ha_user_id</code>: ID da conta HA do proprietário</li>"
            "<li><code>owner_ingress_origin</code>: origem HTTPS do HA, sem caminho</li>"
            "</ul><p>Salve e reinicie o add-on para aplicar.</p>"
            "<p>A publicação de pacotes continua bloqueada até aprovação "
            "independente. Esta página não executa ações.</p></html>"
        )
        return _response(200, page, {
            "Content-Security-Policy": "default-src 'none'; base-uri 'none'; "
                                       "form-action 'none'; frame-ancestors 'self'",
        })
    if method == "POST":
        return _response(405, "Método não permitido.", {"Allow": "GET"})
    return _response(404, "Não encontrado.")


def make_disabled_owner_ingress_handler():
    """Create a status-only handler; no identity, consent, or write operation."""
    class DisabledOwnerIngressHandler(BaseHTTPRequestHandler):
        server_version = "FactoryRunnerOwnerIngress/1"

        def setup(self):
            super().setup()
            self.connection.settimeout(5)

        def log_message(self, format, *args):
            return

        def _send(self, result):
            status, headers, body = result
            self.send_response(status)
            for name, value in headers.items():
                self.send_header(name, value)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(dispatch_owner_ingress_disabled(
                method="GET", path=self.path, peer_ip=self.client_address[0]
            ))

        def do_POST(self):
            self._send(dispatch_owner_ingress_disabled(
                method="POST", path=self.path, peer_ip=self.client_address[0]
            ))

    return DisabledOwnerIngressHandler


def serve_owner_ingress_disabled(port=8099):
    """Serve a status-only page through Supervisor ingress; never accepts writes."""
    server = HTTPServer(("0.0.0.0", int(port)), make_disabled_owner_ingress_handler())
    server.serve_forever()
