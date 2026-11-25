"""Testes de borda HTTP isolada, sem HA/Evolution/n8n.
Não altera o banco nem envia mensagens.
"""
import importlib.util
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

class IngressCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.old = {k: os.environ.get(k) for k in ("CENTRAL_DATA_DIR", "CENTRAL_OPTIONS")}
        os.environ["CENTRAL_DATA_DIR"] = cls.tmp.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(cls.tmp.name) / "options.json")
        spec = importlib.util.spec_from_file_location("central_ingress_test", Path(__file__).parent / "server.py")
        cls.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.mod)
        Path(os.environ["CENTRAL_OPTIONS"]).write_text(json.dumps({"evolution_webhook_secret": "x"*32}))

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        for k, v in cls.old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v

    def send(self, payload, auth="Bearer " + "x"*32):
        raw = json.dumps(payload).encode()
        handler = self.mod.Handler.__new__(self.mod.Handler)
        handler.path = "/evolution/ingress-check"
        handler.headers = {"Authorization": auth, "Content-Length": str(len(raw))}
        handler.rfile = io.BytesIO(raw)
        responses = []
        handler.respond = lambda status, data: responses.append((status, data))
        handler.do_POST()
        return responses[0]

    def event(self):
        return {"event": "messages.upsert", "instance": "umdoislab", "data": {
            "key": {"fromMe": False, "remoteJid": "5511999999999@s.whatsapp.net", "id": "mid"},
            "message": {"conversation": "Olá"}}}

    def test_valid_preflight_does_not_dispatch(self):
        status, result = self.send(self.event())
        self.assertEqual(status, 200)
        self.assertEqual(result, {"accepted": True, "dispatch": False})

    def test_wrong_secret_fails_closed(self):
        self.assertEqual(self.send(self.event(), "Bearer wrong")[0], 403)

    def test_no_secret_fails_closed(self):
        self.assertEqual(self.send(self.event(), "")[0], 403)

    def test_own_message_rejected(self):
        payload = self.event()
        payload["data"]["key"]["fromMe"] = True
        self.assertEqual(self.send(payload)[0], 422)

    def test_oversized_payload_rejected(self):
        payload = self.event()
        payload["data"]["message"]["conversation"] = "a" * 20000
        self.assertEqual(self.send(payload)[0], 422)

    def test_missing_message_rejected(self):
        payload = self.event()
        payload["data"].pop("message")
        self.assertEqual(self.send(payload)[0], 422)

    def test_empty_options_secret_rejected(self):
        with patch.object(self.mod, "options", return_value={}):
            self.assertEqual(self.send(self.event())[0], 403)

    def test_wrong_instance_rejected(self):
        payload = self.event()
        payload["instance"] = "other"
        self.assertEqual(self.send(payload)[0], 422)

if __name__ == "__main__":
    unittest.main()
