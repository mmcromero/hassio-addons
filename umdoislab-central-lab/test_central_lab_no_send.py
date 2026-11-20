"""LAB sem saída externa: teste HTTP isolado, sem rede nem WhatsApp."""
import importlib.util
import os
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import patch


class LabNoSendTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix="central-lab-test-")
        cls.saved = {key: os.environ.get(key) for key in ("CENTRAL_DATA_DIR", "CENTRAL_OPTIONS")}
        os.environ["CENTRAL_DATA_DIR"] = cls.temp.name
        os.environ["CENTRAL_OPTIONS"] = str(Path(cls.temp.name) / "options.json")
        spec = importlib.util.spec_from_file_location(
            "central_lab_guard_test", Path(__file__).with_name("server.py"))
        cls.central = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.central)

    @classmethod
    def tearDownClass(cls):
        for key, value in cls.saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        cls.temp.cleanup()

    def dummy(self, path):
        responses = []
        fake = SimpleNamespace(
            path=path,
            headers={"X-Requested-With": "UmdoislabCentral"},
            ingress=lambda: True,
            read_json=lambda: {"text": "Teste", "requestId": "00000000-0000-0000-0000-000000000001"},
            respond=lambda code, body: responses.append((code, body)) or (code, body),
        )
        return fake, responses

    def test_lab_blocks_automatic_send_before_external_io(self):
        fake, responses = self.dummy("/bridge/send-auto")
        with patch.dict(os.environ, {"CENTRAL_LAB_NO_WHATSAPP": "1"}):
            with patch.object(self.central.urllib.request, "urlopen", side_effect=AssertionError("network")):
                result = self.central.Handler.send_automated(fake, {})
        self.assertEqual(result[0], 403)
        self.assertIn("LAB", str(responses[0][1]))

    def test_lab_blocks_manual_reply_before_external_io(self):
        fake, responses = self.dummy("/api/conversations/5511999999999%40s.whatsapp.net/reply")
        with patch.dict(os.environ, {"CENTRAL_LAB_NO_WHATSAPP": "1"}):
            with patch.object(self.central.urllib.request, "urlopen", side_effect=AssertionError("network")):
                result = self.central.Handler.do_POST(fake)
        self.assertEqual(result[0], 403)
        self.assertIn("LAB", str(responses[0][1]))
