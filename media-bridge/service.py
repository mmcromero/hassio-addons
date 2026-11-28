"""Restricted FileBrowser Quantum bridge for the Umdoislab working copy.

The bridge never mounts the media filesystem. It talks to FileBrowser's REST API
using a dedicated, non-admin API token whose account scope is checked at startup.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import threading
import uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler


class BridgeError(Exception):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def safe_relative_path(value: object) -> str:
    """Accept a relative path inside the FileBrowser user's scoped root only."""
    if not isinstance(value, str) or not value or len(value) > 1024:
        raise BridgeError("Caminho inválido")
    if "\x00" in value or "\\" in value or value.startswith("/"):
        raise BridgeError("Use caminho relativo à raiz autorizada")
    parts = value.split("/")
    if any(part in ("", ".", "..") for part in parts):
        raise BridgeError("Caminho contém segmento inválido")
    if any(part.startswith(".") for part in parts):
        raise BridgeError("Caminhos ocultos não são permitidos pela ponte")
    return "/".join(parts)


def api_path(relative: str) -> str:
    return "/" + safe_relative_path(relative)


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise BridgeError("Redirecionamento recusado", 502)


class FileBrowserClient:
    def __init__(self, base_url: str, token: str, source: str = "default", timeout: int = 30):
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or
                parsed.hostname != "db21ed7f-filebrowser-quantum" or
                parsed.port != 8072 or parsed.username or parsed.password):
            raise ValueError("FILEBROWSER_URL deve apontar somente para o FileBrowser interno conhecido na porta interna 8072")
        if parsed.path not in ("", "/") or parsed.query or parsed.fragment:
            raise ValueError("FILEBROWSER_URL não pode conter caminho, query ou fragmento")
        if not token or len(token) < 32:
            raise ValueError("Token API do FileBrowser ausente ou inválido")
        if not source or not source.replace("_", "").isalnum():
            raise ValueError("Fonte FileBrowser inválida")
        self.base_url = base_url.rstrip("/")
        self.token = token
        self.source = source
        self.timeout = timeout
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.bootstrap_opener = build_opener(ProxyHandler({}))
        self.base_path = ""

    def discover_base_path(self):
        """Discover the current Supervisor Ingress prefix without Supervisor API access."""
        req = Request(self.base_url + "/", headers={"Accept": "text/html"}, method="GET")
        final_url = ""
        try:
            with self.bootstrap_opener.open(req, timeout=self.timeout) as response:
                final_url = response.geturl()
        except HTTPError as exc:
            status = exc.code
            final_url = exc.geturl()
            exc.close()
            if status not in (401, 403):
                raise BridgeError("Não foi possível descobrir o prefixo Ingress do FileBrowser", 502) from None
        except (URLError, TimeoutError, OSError):
            raise BridgeError("FileBrowser indisponível durante descoberta do prefixo Ingress", 502) from None
        parsed = urlsplit(final_url)
        if parsed.scheme != "http" or parsed.hostname != "db21ed7f-filebrowser-quantum" or parsed.port != 8072:
            raise BridgeError("Redirecionamento Ingress do FileBrowser apontou para destino inesperado", 502)
        parts = [part for part in parsed.path.split("/") if part]
        if (len(parts) < 3 or parts[0] != "api" or parts[1] != "hassio_ingress" or
                len(parts[2]) < 24 or not all(ch.isalnum() or ch in "-_" for ch in parts[2])):
            raise BridgeError("Prefixo Ingress do FileBrowser inválido ou ausente", 502)
        self.base_path = "/api/hassio_ingress/" + parts[2]
        return self.base_path

    def _api_url(self, route: str, query=None):
        if not self.base_path:
            raise BridgeError("Prefixo Ingress do FileBrowser ainda não foi descoberto", 503)
        url = self.base_url + self.base_path + route
        if query:
            url += "?" + urlencode(query, doseq=True)
        return url

    def request(self, method: str, route: str, *, query=None, body=None):
        if not route.startswith("/api/") or "://" in route:
            raise BridgeError("Rota interna não permitida", 400)
        url = self._api_url(route, query)
        data = None if body is None else json.dumps(body).encode("utf-8")
        headers = {"Authorization": "Bearer " + self.token, "Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = Request(url, data=data, headers=headers, method=method)
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                raw = response.read(2 * 1024 * 1024 + 1)
                if len(raw) > 2 * 1024 * 1024:
                    raise BridgeError("Resposta FileBrowser excedeu o limite", 502)
                if not raw:
                    return {}
                try:
                    return json.loads(raw.decode("utf-8"))
                except (UnicodeDecodeError, json.JSONDecodeError):
                    raise BridgeError("Resposta JSON inválida do FileBrowser", 502) from None
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status in (401, 403):
                raise BridgeError("FileBrowser recusou a identidade técnica ou o escopo", 502) from None
            if status == 404:
                raise BridgeError("Recurso não encontrado", 404) from None
            if status == 409:
                raise BridgeError("Conflito: o destino já existe ou a operação não é permitida", 409) from None
            raise BridgeError("Falha na API FileBrowser (HTTP %d)" % status, 502) from None
        except (URLError, TimeoutError, OSError):
            raise BridgeError("FileBrowser indisponível", 502) from None

    def verify_identity(self, username: str, expected_scope: str):
        user = self.request("GET", "/api/users", query={"username": "self"})
        if not isinstance(user, dict) or user.get("username") != username:
            raise BridgeError("Identidade técnica não corresponde ao usuário configurado", 503)
        global_permissions = user.get("permissions") or {}
        if (global_permissions.get("admin") is not False or
                global_permissions.get("api") is not True or
                global_permissions.get("share") is not False or
                global_permissions.get("realtime") is not False):
            raise BridgeError("Permissões globais da identidade técnica fora da política", 503)
        scopes = user.get("scopes")
        if not isinstance(scopes, list) or len(scopes) != 1:
            raise BridgeError("A identidade técnica deve ter exatamente um escopo", 503)
        scope = scopes[0]
        perms = scope.get("permissions") or {}
        if scope.get("scope") != expected_scope:
            raise BridgeError("Escopo FileBrowser não corresponde à cópia autorizada", 503)
        scope_parts = expected_scope.split("/") if isinstance(expected_scope, str) else []
        if (len(scope_parts) < 3 or scope_parts[0] != "" or scope_parts[1] != "MIDIAS2" or
                any(part in ("", ".", "..") for part in scope_parts[2:])):
            raise BridgeError("Escopo esperado deve ser uma pasta específica dentro de MIDIAS2", 503)
        if (perms.get("view") is not True or perms.get("download") is not True or
                perms.get("modify") is not True or perms.get("create") is not True or
                perms.get("delete") is not False):
            raise BridgeError("Permissões por escopo fora da política (delete deve permanecer false)", 503)
        return {"username": username, "scope": expected_scope, "delete": False}

    def list_items(self, path: str):
        return self.request("GET", "/api/resources/items",
                            query={"path": api_path(path) if path else "/", "source": self.source})

    def metadata(self, path: str):
        return self.request("GET", "/api/resources",
                            query={"path": api_path(path) if path else "/", "source": self.source})

    def create_folder(self, path: str):
        return self.request("POST", "/api/resources",
                            query={"path": api_path(path), "source": self.source, "isDir": "true"})

    def preview(self, path: str, size: str = "small"):
        if size not in ("small", "large"):
            raise BridgeError("Tamanho de preview inválido")
        url = self._api_url("/api/resources/preview", {
            "path": api_path(path), "size": size, "source": self.source})
        req = Request(url, headers={"Authorization": "Bearer " + self.token,
                                    "Accept": "image/jpeg,image/png"}, method="GET")
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                mime = response.headers.get_content_type()
                if mime not in ("image/jpeg", "image/png"):
                    raise BridgeError("FileBrowser retornou formato de preview não permitido", 502)
                raw = response.read(5 * 1024 * 1024 + 1)
                if not raw or len(raw) > 5 * 1024 * 1024:
                    raise BridgeError("Preview vazio ou excede 5 MiB", 502)
                return mime, raw
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise BridgeError("Preview não disponível (HTTP %d)" % status, 502) from None
        except (URLError, TimeoutError, OSError):
            raise BridgeError("FileBrowser indisponível para preview", 502) from None

    def sha256(self, path: str):
        """Stream a file through FileBrowser's authenticated download API and hash it."""
        url = self._api_url("/api/resources/download", {
            "source": self.source, "file": api_path(path)})
        req = Request(url, headers={"Authorization": "Bearer " + self.token,
                                    "Accept": "application/octet-stream"}, method="GET")
        digest = hashlib.sha256()
        try:
            with self.opener.open(req, timeout=self.timeout) as response:
                while True:
                    chunk = response.read(1024 * 1024)
                    if not chunk:
                        break
                    digest.update(chunk)
        except HTTPError as exc:
            status = exc.code
            exc.close()
            if status == 404:
                raise BridgeError("Arquivo não encontrado para cálculo SHA-256", 404) from None
            if status in (401, 403):
                raise BridgeError("FileBrowser recusou leitura para cálculo SHA-256", 502) from None
            raise BridgeError("Falha no download para SHA-256 (HTTP %d)" % status, 502) from None
        except (URLError, TimeoutError, OSError):
            raise BridgeError("FileBrowser indisponível durante cálculo SHA-256", 502) from None
        return digest.hexdigest()

    def move(self, source_path: str, destination_path: str):
        body = {"action": "move", "overwrite": False, "rename": False,
                "items": [{"fromSource": self.source, "fromPath": api_path(source_path),
                           "toSource": self.source, "toPath": api_path(destination_path)}]}
        return self.request("PATCH", "/api/resources", body=body)


class AuditLog:
    def __init__(self, path: str):
        self.path = path
        self.lock = threading.Lock()

    def write(self, event: dict):
        record = dict(event)
        record["at"] = datetime.now(timezone.utc).isoformat()
        line = json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n"
        os.makedirs(os.path.dirname(self.path) or ".", exist_ok=True)
        with self.lock:
            fd = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
            try:
                os.fchmod(fd, 0o600)
                payload = line.encode("utf-8")
                offset = 0
                while offset < len(payload):
                    offset += os.write(fd, payload[offset:])
                os.fsync(fd)
            finally:
                os.close(fd)


class MediaBridge:
    def __init__(self, client: FileBrowserClient, audit: AuditLog,
                 expected_scope: str, expected_username: str):
        self.client = client
        self.audit = audit
        self.expected_scope = expected_scope
        self.expected_username = expected_username

    def _verify_write_scope(self):
        self.client.verify_identity(self.expected_username, self.expected_scope)

    @staticmethod
    def _require_complete_move(result):
        if (not isinstance(result, dict) or result.get("failed") or
                not isinstance(result.get("succeeded"), list) or len(result["succeeded"]) != 1):
            raise BridgeError("FileBrowser não confirmou exatamente uma movimentação concluída", 502)
        return result

    def _file_sha256(self, path: str):
        metadata = self.client.metadata(path)
        if not isinstance(metadata, dict) or metadata.get("type") != "file":
            raise BridgeError("A ponte só move arquivos individuais nesta versão; pastas não são aceitas")
        return self.client.sha256(path)

    def _move_verified(self, source: str, destination: str, before_hash: str | None = None):
        if before_hash is None:
            before_hash = self._file_sha256(source)
        receipt = self._require_complete_move(self.client.move(source, destination))
        after_hash = self.client.sha256(destination)
        if not hmac.compare_digest(before_hash, after_hash):
            raise BridgeError("SHA-256 divergente após movimentação; arquivo mantido no destino para inspeção", 502)
        return receipt, before_hash

    def list(self, path: str = ""):
        if path:
            path = safe_relative_path(path)
        return self.client.list_items(path)

    def inspect(self, path: str):
        path = safe_relative_path(path)
        return self.client.metadata(path)

    def create_folder(self, path: str, *, apply=False, confirmation=None):
        if type(apply) is not bool:
            raise BridgeError("apply deve ser booleano")
        path = safe_relative_path(path)
        if not apply:
            return {"dry_run": True, "action": "create_folder", "path": path}
        if confirmation != "CRIAR_PASTA":
            raise BridgeError("Confirmação explícita CRIAR_PASTA obrigatória", 403)
        self._verify_write_scope()
        operation_id = uuid.uuid4().hex
        event = {"operation_id": operation_id, "action": "create_folder", "path": path}
        self.audit.write({**event, "result": "started"})
        try:
            result = self.client.create_folder(path)
        except Exception:
            self.audit.write({**event, "result": "failed"})
            raise
        self.audit.write({**event, "result": "success"})
        return {"dry_run": False, "operation_id": operation_id, "result": result}

    def move(self, source: str, destination: str, *, apply=False, confirmation=None):
        if type(apply) is not bool:
            raise BridgeError("apply deve ser booleano")
        source = safe_relative_path(source)
        destination = safe_relative_path(destination)
        if source == destination or destination.startswith(source + "/"):
            raise BridgeError("Destino inválido: origem e destino se sobrepõem")
        plan = {"operation_id": uuid.uuid4().hex, "action": "move",
                "source": source, "destination": destination}
        if not apply:
            return {"dry_run": True, **plan}
        if confirmation != "MOVER":
            raise BridgeError("Confirmação explícita MOVER obrigatória", 403)
        self._verify_write_scope()
        self.audit.write({**plan, "result": "started"})
        try:
            result, file_hash = self._move_verified(source, destination)
        except Exception:
            self.audit.write({**plan, "result": "failed"})
            raise
        self.audit.write({**plan, "sha256": file_hash, "result": "success"})
        return {"dry_run": False, "result": result, "sha256": file_hash, **plan}

    def quarantine(self, path: str, *, apply=False, confirmation=None):
        if type(apply) is not bool:
            raise BridgeError("apply deve ser booleano")
        path = safe_relative_path(path)
        operation_id = uuid.uuid4().hex
        destination = "_QUARENTENA/" + operation_id + "/" + path.rsplit("/", 1)[-1]
        plan = {"action": "quarantine", "source": path, "destination": destination,
                "operation_id": operation_id}
        if not apply:
            return {"dry_run": True, **plan}
        if confirmation != "QUARENTENA":
            raise BridgeError("Confirmação explícita QUARENTENA obrigatória", 403)
        self._verify_write_scope()
        self.audit.write({**plan, "result": "started"})
        parent = "_QUARENTENA/" + operation_id
        try:
            before_hash = self._file_sha256(path)
            try:
                root_info = self.client.metadata("_QUARENTENA")
                if root_info.get("type") != "directory":
                    raise BridgeError("A raiz de quarentena existe, mas não é diretório", 409)
            except BridgeError as exc:
                if exc.status != 404:
                    raise
                self.client.create_folder("_QUARENTENA")
            self.client.create_folder(parent)
            result, file_hash = self._move_verified(path, destination, before_hash=before_hash)
        except Exception:
            self.audit.write({**plan, "result": "failed"})
            raise
        self.audit.write({**plan, "sha256": file_hash, "result": "success"})
        return {"dry_run": False, "result": result, "sha256": file_hash, **plan}


def build_handler(bridge: MediaBridge, api_key: str):
    class Handler(BaseHTTPRequestHandler):
        server_version = "UmdoislabMediaBridge/0.1"

        def _authorized(self):
            supplied = self.headers.get("X-Bridge-Key", "")
            return bool(supplied) and hmac.compare_digest(supplied, api_key)

        def _send(self, status, payload):
            raw = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def do_GET(self):
            if self.path == "/health":
                self._send(200, {"ok": True, "service": "media-bridge",
                                 "configured": bridge is not None})
                return
            if bridge is None:
                self._send(503, {"error": "not_configured"})
                return
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            from urllib.parse import parse_qs, urlsplit
            parsed = urlsplit(self.path)
            params = parse_qs(parsed.query)
            try:
                if parsed.path == "/v1/items":
                    self._send(200, bridge.list(params.get("path", [""])[0]))
                elif parsed.path == "/v1/metadata":
                    self._send(200, bridge.inspect(params.get("path", [""])[0]))
                elif parsed.path == "/v1/preview":
                    import base64
                    path = safe_relative_path(params.get("path", [""])[0])
                    mime, raw = bridge.client.preview(path, params.get("size", ["small"])[0])
                    self._send(200, {"mime": mime, "bytes": len(raw),
                                     "base64": base64.b64encode(raw).decode("ascii")})
                else:
                    self._send(404, {"error": "not_found"})
            except BridgeError as exc:
                self._send(exc.status, {"error": str(exc)})

        def do_POST(self):
            if bridge is None:
                self._send(503, {"error": "not_configured"})
                return
            if not self._authorized():
                self._send(401, {"error": "unauthorized"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise BridgeError("Corpo ausente ou excede 64 KiB")
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise BridgeError("JSON deve ser um objeto")
                if self.path == "/v1/folders":
                    result = bridge.create_folder(body.get("path"), apply=body.get("apply", False),
                                                  confirmation=body.get("confirmation"))
                elif self.path == "/v1/move":
                    result = bridge.move(body.get("source"), body.get("destination"),
                                         apply=body.get("apply", False),
                                         confirmation=body.get("confirmation"))
                elif self.path == "/v1/quarantine":
                    result = bridge.quarantine(body.get("path"), apply=body.get("apply", False),
                                               confirmation=body.get("confirmation"))
                else:
                    self._send(404, {"error": "not_found"})
                    return
                self._send(200, result)
            except (UnicodeDecodeError, json.JSONDecodeError, ValueError):
                self._send(400, {"error": "JSON inválido"})
            except BridgeError as exc:
                self._send(exc.status, {"error": str(exc)})

        def log_message(self, fmt, *args):
            # Do not log headers, URLs with tokens, or request bodies.
            return

    return Handler


def main():
    required = {
        "FILEBROWSER_URL": os.environ.get("FILEBROWSER_URL", ""),
        "FILEBROWSER_API_TOKEN": os.environ.get("FILEBROWSER_API_TOKEN", ""),
        "FILEBROWSER_EXPECTED_USERNAME": os.environ.get("FILEBROWSER_EXPECTED_USERNAME", ""),
        "FILEBROWSER_EXPECTED_SCOPE": os.environ.get("FILEBROWSER_EXPECTED_SCOPE", ""),
        "BRIDGE_API_KEY": os.environ.get("BRIDGE_API_KEY", ""),
    }
    missing = [name for name, value in required.items() if not value]
    bridge = None
    api_key = ""
    if missing:
        print(json.dumps({"event": "not_configured", "missing": missing}), flush=True)
    else:
        url = required["FILEBROWSER_URL"]
        token = required["FILEBROWSER_API_TOKEN"]
        username = required["FILEBROWSER_EXPECTED_USERNAME"]
        scope = required["FILEBROWSER_EXPECTED_SCOPE"]
        api_key = required["BRIDGE_API_KEY"]
        if len(api_key) < 32:
            raise SystemExit("BRIDGE_API_KEY deve ter ao menos 32 caracteres")
        client = FileBrowserClient(url, token, os.environ.get("FILEBROWSER_SOURCE", "default"))
        client.discover_base_path()
        print(json.dumps({"event": "ingress_prefix_discovered"}), flush=True)
        identity = client.verify_identity(username, scope)
        print(json.dumps({"event": "identity_verified", **identity}), flush=True)
        audit = AuditLog(os.environ.get("AUDIT_LOG", "/data/audit.jsonl"))
        bridge = MediaBridge(client, audit, scope, username)
    port = int(os.environ.get("PORT", "8090"))
    server = ThreadingHTTPServer(("0.0.0.0", port), build_handler(bridge, api_key))
    server.serve_forever()


if __name__ == "__main__":
    main()
