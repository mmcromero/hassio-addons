import hashlib
import json
import os
import tempfile
import threading
import unittest
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen
from http.server import ThreadingHTTPServer

from service import AuditLog, BridgeError, FileBrowserClient, MediaBridge, build_handler, safe_relative_path


class FakeClient:
    source = "default"

    def __init__(self):
        self.calls = []

    def verify_identity(self, username, expected_scope):
        self.calls.append(("verify_identity", username, expected_scope))
        return {"username": username, "scope": expected_scope, "delete": False}

    def list_items(self, path):
        self.calls.append(("list", path))
        return {"items": []}

    def metadata(self, path):
        self.calls.append(("metadata", path))
        return {"path": path, "type": "directory" if path == "_QUARENTENA" else "file"}

    def sha256(self, path):
        self.calls.append(("sha256", path))
        return "a" * 64

    def create_folder(self, path):
        self.calls.append(("mkdir", path))
        return {"created": path}

    def move(self, source, destination):
        self.calls.append(("move", source, destination))
        return {"succeeded": [{"fromPath": source, "toPath": destination}]}


class PathPolicyTests(unittest.TestCase):
    def test_accepts_relative_paths(self):
        self.assertEqual(safe_relative_path("Fotos/2025"), "Fotos/2025")

    def test_rejects_escape_and_absolute_paths(self):
        for value in ("../secret", "Fotos/../../secret", "/MIDIAS2", "a\\b", "a//b", ".hidden"):
            with self.subTest(value=value), self.assertRaises(BridgeError):
                safe_relative_path(value)

    def test_rejects_empty_and_non_string(self):
        for value in ("", None, 42):
            with self.subTest(value=value), self.assertRaises(BridgeError):
                safe_relative_path(value)


class OperationTests(unittest.TestCase):
    def setUp(self):
        self.client = FakeClient()
        self.tmp = tempfile.TemporaryDirectory()
        self.audit_path = os.path.join(self.tmp.name, "audit.jsonl")
        self.bridge = MediaBridge(self.client, AuditLog(self.audit_path), "/MIDIAS2/Copia", "catalogo-operador")

    def tearDown(self):
        self.tmp.cleanup()

    def test_move_is_dry_run_by_default(self):
        result = self.bridge.move("Fotos/a.jpg", "Produtos/Pracinha/a.jpg")
        self.assertTrue(result["dry_run"])
        self.assertEqual(self.client.calls, [])

    def test_move_requires_explicit_confirmation(self):
        with self.assertRaises(BridgeError):
            self.bridge.move("Fotos/a.jpg", "Produtos/a.jpg", apply=True)
        self.assertEqual(self.client.calls, [])

    def test_move_applies_and_audits(self):
        result = self.bridge.move("Fotos/a.jpg", "Produtos/a.jpg",
                                  apply=True, confirmation="MOVER")
        self.assertFalse(result["dry_run"])
        self.assertEqual(self.client.calls, [
            ("verify_identity", "catalogo-operador", "/MIDIAS2/Copia"),
            ("metadata", "Fotos/a.jpg"),
            ("sha256", "Fotos/a.jpg"),
            ("move", "Fotos/a.jpg", "Produtos/a.jpg"),
            ("sha256", "Produtos/a.jpg"),
        ])
        with open(self.audit_path, encoding="utf-8") as handle:
            started = json.loads(handle.readline())
            completed = json.loads(handle.readline())
        self.assertEqual(started["action"], "move")
        self.assertEqual(started["result"], "started")
        self.assertEqual(completed["result"], "success")
        self.assertEqual(completed["sha256"], "a" * 64)
        self.assertNotIn("token", started)
        self.assertNotIn("token", completed)

    def test_quarantine_dry_run_does_not_mutate(self):
        result = self.bridge.quarantine("Fora-do-catalogo/a.jpg")
        self.assertTrue(result["dry_run"])
        self.assertEqual(self.client.calls, [])
        self.assertTrue(result["destination"].startswith("_QUARENTENA/"))

    def test_quarantine_apply_moves_only_after_confirmation(self):
        result = self.bridge.quarantine("Fora/a.jpg", apply=True, confirmation="QUARENTENA")
        self.assertFalse(result["dry_run"])
        self.assertEqual(self.client.calls, [
            ("verify_identity", "catalogo-operador", "/MIDIAS2/Copia"),
            ("metadata", "Fora/a.jpg"),
            ("sha256", "Fora/a.jpg"),
            ("metadata", "_QUARENTENA"),
            ("mkdir", "_QUARENTENA/" + result["operation_id"]),
            ("move", "Fora/a.jpg", result["destination"]),
            ("sha256", result["destination"]),
        ])

    def test_create_folder_is_dry_run_by_default(self):
        result = self.bridge.create_folder("Produtos/Pracinha")
        self.assertTrue(result["dry_run"])
        self.assertEqual(self.client.calls, [])

    def test_move_rejects_non_boolean_apply(self):
        with self.assertRaises(BridgeError):
            self.bridge.move("Fotos/a.jpg", "Produtos/a.jpg", apply="false")

    def test_move_rejects_incomplete_receipt(self):
        with self.assertRaises(BridgeError):
            self.bridge._require_complete_move({"succeeded": [], "failed": []})

    def test_move_rejects_nested_destination(self):
        with self.assertRaises(BridgeError):
            self.bridge.move("Fotos", "Fotos/2025/a.jpg")

    def test_move_rejects_directory_before_mutation(self):
        self.client.metadata = lambda path: {"path": path, "type": "directory"}
        with self.assertRaises(BridgeError):
            self.bridge.move("Fotos/2025", "Produtos/2025", apply=True, confirmation="MOVER")
        self.assertNotIn(("move", "Fotos/2025", "Produtos/2025"), self.client.calls)

    def test_move_rejects_hash_mismatch_after_mutation(self):
        hashes = iter(["a" * 64, "b" * 64])
        self.client.sha256 = lambda path: next(hashes)
        with self.assertRaises(BridgeError):
            self.bridge.move("Fotos/a.jpg", "Produtos/a.jpg", apply=True, confirmation="MOVER")
        self.assertIn(("move", "Fotos/a.jpg", "Produtos/a.jpg"), self.client.calls)
        with open(self.audit_path, encoding="utf-8") as handle:
            records = [json.loads(line) for line in handle]
        self.assertEqual(records[-1]["result"], "failed")

    def test_expected_scope_must_be_a_specific_working_subfolder(self):
        permissions = {"view": True, "download": True, "modify": True,
                       "create": True, "delete": False}
        for scope in ("/", "/MIDIAS2", "/MIDIAS2/../system", "/media/MIDIAS2/Copia"):
            with self.subTest(scope=scope):
                client = FileBrowserClient(
                    "http://db21ed7f-filebrowser-quantum:8072", "x" * 40
                )
                client.request = lambda *args, _scope=scope, **kwargs: {
                    "username": "catalogo-operador",
                    "permissions": {"admin": False, "api": True,
                                    "share": False, "realtime": False},
                    "scopes": [{"scope": _scope, "permissions": permissions}],
                }
                with self.assertRaises(BridgeError):
                    client.verify_identity("catalogo-operador", scope)

    def test_specific_midias2_subfolder_scope_is_accepted(self):
        permissions = {"view": True, "download": True, "modify": True,
                       "create": True, "delete": False}
        client = FileBrowserClient(
            "http://db21ed7f-filebrowser-quantum:8072", "x" * 40
        )
        client.request = lambda *args, **kwargs: {
            "username": "catalogo-operador",
            "permissions": {"admin": False, "api": True,
                            "share": False, "realtime": False},
            "scopes": [{"scope": "/MIDIAS2/CopiaFinal",
                        "permissions": permissions}],
        }
        result = client.verify_identity("catalogo-operador", "/MIDIAS2/CopiaFinal")
        self.assertEqual(result["scope"], "/MIDIAS2/CopiaFinal")


class FileBrowserClientTests(unittest.TestCase):
    def test_rejects_ingress_port_and_non_internal_hostname(self):
        for url in ("http://db21ed7f-filebrowser-quantum:8071",
                    "http://db21ed7f-filebrowser-quantum.local.hass.io:8072"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                FileBrowserClient(url, "x" * 40)

    def test_discovers_dynamic_supervisor_ingress_prefix(self):
        class Response:
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def geturl(self):
                return "http://db21ed7f-filebrowser-quantum:8072/api/hassio_ingress/" + "a" * 32 + "/"

        class Opener:
            def open(self, request, timeout):
                self.request = request
                return Response()

        client = FileBrowserClient(
            "http://db21ed7f-filebrowser-quantum:8072", "x" * 40
        )
        opener = Opener()
        client.bootstrap_opener = opener
        base_path = client.discover_base_path()
        self.assertEqual(base_path, "/api/hassio_ingress/" + "a" * 32)
        self.assertTrue(opener.request.full_url.endswith(":8072/"))

    def test_sha256_streams_authenticated_download_endpoint(self):
        payload = b"umdoislab-media-bridge-test-payload"

        class Response:
            def __init__(self):
                self.offset = 0
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size):
                chunk = payload[self.offset:self.offset + min(size, 7)]
                self.offset += len(chunk)
                return chunk

        class Opener:
            def __init__(self):
                self.request = None
            def open(self, request, timeout):
                self.request = request
                return Response()

        client = FileBrowserClient(
            "http://db21ed7f-filebrowser-quantum:8072", "x" * 40
        )
        client.base_path = "/api/hassio_ingress/" + "t" * 32
        opener = Opener()
        client.opener = opener

        digest = client.sha256("Fotos/Produto A.jpg")

        self.assertEqual(digest, hashlib.sha256(payload).hexdigest())
        self.assertEqual(opener.request.get_method(), "GET")
        self.assertEqual(opener.request.get_header("Authorization"), "Bearer " + "x" * 40)
        parsed = urlsplit(opener.request.full_url)
        self.assertEqual(parsed.path, client.base_path + "/api/resources/download")
        query = parse_qs(parsed.query)
        self.assertEqual(query["source"], ["default"])
        self.assertEqual(query["file"], ["/Fotos/Produto A.jpg"])


class SafeModeHandlerTests(unittest.TestCase):
    def test_health_only_when_bridge_is_not_configured(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), build_handler(None, ""))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = "http://127.0.0.1:%d" % server.server_address[1]
        try:
            with urlopen(base + "/health", timeout=3) as response:
                health = json.loads(response.read().decode("utf-8"))
            self.assertTrue(health["ok"])
            self.assertFalse(health["configured"])
            with self.assertRaises(HTTPError) as raised:
                urlopen(base + "/v1/items", timeout=3)
            self.assertEqual(raised.exception.code, 503)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == "__main__":
    unittest.main(verbosity=2)
