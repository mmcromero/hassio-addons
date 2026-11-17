"""Offline regression for the separate administrative STATUS sender."""
import importlib.util
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch
import sqlite3

SERVER = Path(__file__).resolve().parents[1] / "server.py"


class FakeResponse:
    status = 200
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return False
    def read(self, n):
        return b'{}'


class TestAdminStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.env = patch.dict(os.environ, {"CENTRAL_DATA_DIR": self.tmp.name,
                                           "CENTRAL_OPTIONS": str(Path(self.tmp.name) / "options.json")})
        self.env.start()
        self.addCleanup(self.env.stop)
        spec = importlib.util.spec_from_file_location("central_admin_test", SERVER)
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        self.mod.init()
        self.owner = "5511999999999@s.whatsapp.net"
        self.cfg = {
            "admin_owner_jid": self.owner,
            "admin_reply_secret": "A" * 40,
            "bridge_secret": "B" * 40,
            "evolution_api_key": "C" * 40,
            "evolution_url": "http://127.0.0.1:8080",
            "evolution_instance": "umdoislab",
        }
        self.mock_options = patch.object(self.mod, "options", return_value=self.cfg)
        self.mock_options.start()
        self.addCleanup(self.mock_options.stop)
        self.handler = self.mod.Handler.__new__(self.mod.Handler)
        self.results = []
        self.handler.respond = lambda status, body: self.results.append((status, body))
        self.handler.headers = {"Authorization": "Bearer " + self.cfg["admin_reply_secret"]}
        self.payload = {"senderId": self.owner, "instance": "umdoislab",
                        "messageId": "MSG-1", "command": "status",
                        "text": "Avisaqui: quatro demandas consultadas"}

    def test_admin_secret_is_distinct_from_commercial_secret(self):
        self.assertTrue(self.handler.admin_bridge())
        self.handler.headers = {"Authorization": "Bearer " + self.cfg["bridge_secret"]}
        self.assertFalse(self.handler.admin_bridge())
        self.handler.headers = {"Authorization": "Bearer " + self.cfg["admin_reply_secret"]}
        self.cfg["admin_reply_secret"] = self.cfg["bridge_secret"]
        self.assertFalse(self.handler.admin_bridge())

    def test_owner_can_be_excluded_without_changing_commercial_policy(self):
        with self.mod.connect() as db:
            db.execute("INSERT INTO contact_rules VALUES(?,?)", (self.owner, "test"))
            db.execute("INSERT INTO contact_rules VALUES(?,?)", (self.owner, "excluded"))
            self.assertFalse(self.mod.contact_policy(db, self.owner)["allowed"])
        with patch.object(self.mod.urllib.request, "urlopen", return_value=FakeResponse()) as sent:
            self.handler.send_admin_status(self.payload)
            self.assertEqual(self.results[-1][0], 200)
            self.assertEqual(sent.call_count, 1)
            request = sent.call_args.args[0]
            self.assertEqual(json.loads(request.data)["number"], self.owner.split("@")[0])
        with self.mod.connect() as db:
            self.assertFalse(self.mod.contact_policy(db, self.owner)["allowed"])

    def test_duplicate_not_sent_again(self):
        with patch.object(self.mod.urllib.request, "urlopen", return_value=FakeResponse()) as sent:
            self.handler.send_admin_status(self.payload)
            self.handler.send_admin_status(self.payload)
        self.assertEqual(sent.call_count, 1)
        self.assertEqual([status for status, _ in self.results], [200, 409])

    def test_wrong_owner_or_command_fails_without_network(self):
        with patch.object(self.mod.urllib.request, "urlopen") as sent:
            for field, value in (("senderId", "5511888888888@s.whatsapp.net"),
                                 ("command", "liberar"), ("command", "testar 23"),
                                 ("instance", "outra")):
                bad = dict(self.payload)
                bad[field] = value
                self.handler.send_admin_status(bad)
                self.assertEqual(self.results[-1][0], 403)
        sent.assert_not_called()

    def test_failed_delivery_does_not_retry_same_message(self):
        with patch.object(self.mod.urllib.request, "urlopen", side_effect=OSError("offline")) as sent:
            self.handler.send_admin_status(self.payload)
            self.handler.send_admin_status(self.payload)
        self.assertEqual(sent.call_count, 1)
        self.assertEqual([status for status, _ in self.results], [502, 409])

    def test_invalid_message_id_and_fields(self):
        with patch.object(self.mod.urllib.request, "urlopen") as sent:
            for mid in ("", "bad id", "x" * 161):
                payload = dict(self.payload, messageId=mid)
                self.handler.send_admin_status(payload)
                self.assertEqual(self.results[-1][0], 422)
            extra = dict(self.payload, kind="normal")
            self.handler.send_admin_status(extra)
            self.assertEqual(self.results[-1][0], 403)
        sent.assert_not_called()


if __name__ == "__main__":
    unittest.main()
