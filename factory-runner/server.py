#!/usr/bin/env python3
"""Factory Runner: authenticated, fail-closed API.

No Git publication or AI-supplied filesystem writes are exposed until an
independent authorization/publishing workflow has been reviewed and approved.
"""
import hmac
import http.server
import json
import os
import re
import threading
import time
import uuid
from pathlib import Path

HOST = os.environ.get("RUNNER_BIND_HOST", "127.0.0.1")
PORT = int(os.environ.get("RUNNER_PORT", "9876"))
MAX_BODY = 4096
LOCK = threading.Lock()
OPERATIONS = {"/api/fechar-pacote", "/api/corrigir-issue"}
ISSUE = re.compile(r"^[1-9][0-9]{0,7}$")
AUDIT_PATH = Path(os.environ.get("RUNNER_AUDIT_PATH", "/data/factory-runner/audit.jsonl"))

def authenticated(header):
    """Fail closed; never accept a missing, empty, or malformed bearer token."""
    expected = os.environ.get("RUNNER_AUTH_TOKEN", "")
    if not expected or not header or len(header) > 4096 or len(expected) < 32:
        return False
    scheme, sep, value = header.partition(" ")
    if scheme.lower() != "bearer" or sep != " " or not value or value != value.strip():
        return False
    return hmac.compare_digest(value.encode(), expected.encode())

def record(action, issue, status, request_id, actor="authenticated-client"):
    """Write only sanitized metadata. Never log secrets or request bodies."""
    event = {
        "time": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "operation_id": request_id,
        "action": action,
        "issue": issue,
        "status": status,
        "actor": actor,
    }
    try:
        AUDIT_PATH.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
        with AUDIT_PATH.open("a", encoding="utf-8") as log:
            log.write(json.dumps(event, separators=(",", ":")) + "\n")
        AUDIT_PATH.chmod(0o600)
    except OSError:
        # Do not silently accept privileged actions if audit storage is unavailable.
        raise RuntimeError("Audit storage unavailable")

class Handler(http.server.BaseHTTPRequestHandler):
    def respond(self, status, payload):
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def authorized(self):
        return authenticated(self.headers.get("Authorization", ""))

    def do_GET(self):
        if self.path not in ("/", "/api/status"):
            return self.respond(404, {"error": "not_found"})
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        return self.respond(200, {
            "service": "factory-runner",
            "status": "restricted",
            "publication": "disabled",
            "autonomous_changes": "disabled"
        })

    def do_POST(self):
        if self.path not in OPERATIONS:
            return self.respond(404, {"error": "not_found"})
        if not self.authorized():
            return self.respond(401, {"error": "unauthorized"})
        raw_length = self.headers.get("Content-Length", "")
        if not 1 <= len(raw_length) <= 5 or not raw_length.isascii() or not raw_length.isdecimal():
            return self.respond(400, {"error": "invalid_length"})
        length = int(raw_length)
        if not 0 < length <= MAX_BODY:
            return self.respond(413, {"error": "invalid_size"})
        try:
            body = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, ValueError):
            return self.respond(400, {"error": "invalid_json"})
        if not isinstance(body, dict):
            return self.respond(400, {"error": "invalid_payload"})
        issue = body.get("issue")
        if type(issue) is not int or not ISSUE.fullmatch(str(issue)):
            return self.respond(400, {"error": "invalid_issue"})
        request_id = str(uuid.uuid4())
        if not LOCK.acquire(blocking=False):
            return self.respond(409, {"error": "busy"})
        try:
            # A bearer token authenticates a client; it is NOT owner approval.
            # Until a canonical per-repo/issue/SHA authorization gate is integrated,
            # do not call any path that writes Git, executes model code or publishes.
            record(self.path, issue, "blocked_authorization", request_id)
            return self.respond(403, {
                "error": "owner_approval_required",
                "operation_id": request_id
            })
        except RuntimeError:
            return self.respond(503, {"error": "audit_unavailable"})
        finally:
            LOCK.release()

    def log_message(self, fmt, *args):
        # Suppress request headers, query strings, and PII from default logs.
        return

if __name__ == "__main__":
    if len(os.environ.get("RUNNER_AUTH_TOKEN", "")) < 32:
        raise SystemExit("RUNNER_AUTH_TOKEN required; refusing to start")
    server = http.server.ThreadingHTTPServer((HOST, PORT), Handler)
    server.daemon_threads = True
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()
