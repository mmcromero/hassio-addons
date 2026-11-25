"""Integration regressions for the actual Central Handler/SQLite; transport mocked."""
import http.client
import json
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import test_accounts


class Stage2ServerTests(unittest.TestCase):
    def setUp(self):
        self.fixture = test_accounts.MultiAccountTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        self.central = self.fixture.mod
        self.a = self.fixture.a
        self.b = self.fixture.b
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.central.Handler)
        self.worker = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.worker.start()
        self.addCleanup(self.close_http)

    def close_http(self):
        self.server.shutdown()
        self.server.server_close()
        self.worker.join(timeout=5)

    def request(self, operation, payload, *, account=None, secret=None):
        account = account or self.a
        conn = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=5)
        try:
            token = secret if secret is not None else account.config["bridge_secret"]
            conn.request("POST", "/bridge/stage2/" + operation, json.dumps(payload),
                         {"Content-Type": "application/json", "Authorization": "Bearer " + token})
            res = conn.getresponse()
            return res.status, json.loads(res.read())
        finally:
            conn.close()

    def event(self, mid="stage2-1", account=None, **extra):
        return self.fixture.event(account or self.a, messageId=mid, **extra)

    def admit(self, mid="stage2-1", account=None, **extra):
        event = self.event(mid, account, **extra)
        status, body = self.request("inbound", event, account=account)
        self.assertEqual(status, 200, body)
        self.assertEqual(body["action"], "auto")
        self.assertTrue(body["testSendAuthorized"])
        self.assertEqual(len(body["admissionRef"]), 43)
        return {**event, "admissionRef": body["admissionRef"]}

    def count(self, table, account=None):
        return self.fixture.count(account or self.a, table)

    class Accepted:
        status = 200
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def read(self, *_):
            return b'{}'

    def test_actual_http_auth_and_legacy_duplicate(self):
        ev = self.event()
        self.assertEqual(self.request("inbound", ev, secret="wrong")[0], 403)
        self.assertEqual(self.count("inbound_ids"), 0)
        self.assertEqual(self.central.process_inbound(ev, account=self.a)["action"], "auto")
        status, body = self.request("inbound", ev)
        self.assertEqual((status, body["action"]), (200, "ignore"))
        self.assertNotIn("admissionRef", body)
        self.assertEqual(self.request("context", dict(ev, admissionRef="A"*43))[0], 409)
        self.assertEqual(self.count("inbound_ids"), 1)

    def test_actual_http_context_account_isolation(self):
        first = self.admit(account=self.a)
        other = self.admit(account=self.b)
        self.assertEqual(self.request("context", first)[1]["turns"],
                         [{"role": "client", "text": self.a.instance}])
        self.assertEqual(self.request("context", other, account=self.b)[1]["turns"],
                         [{"role": "client", "text": self.b.instance}])
        self.assertEqual(self.request("context", dict(other, admissionRef=first["admissionRef"]),
                                      account=self.b)[0], 409)
        self.assertEqual(self.request("context", other, account=self.a)[0], 403)

    def test_actual_http_handoff_persists_original_and_one_send(self):
        admitted = self.admit()
        status, body = self.request("handoff", dict(admitted, reason="model_error"))
        self.assertEqual((status, body["recorded"]), (200, True))
        self.assertEqual(self.count("inbound_ids"), 1)
        self.assertEqual(self.count("conversation_turns"), 1)
        with self.central.connect(self.a) as db:
            row = db.execute("SELECT status,last_message_id FROM conversations").fetchone()
            self.assertEqual((row["status"], row["last_message_id"]), ("pending", admitted["messageId"]))
        with patch.object(self.central.urllib.request, "urlopen", return_value=self.Accepted()) as send:
            self.assertEqual(self.request("send-auto", dict(admitted, kind="normal", text="wrong"))[0], 409)
            status, result = self.request("send-auto", dict(admitted, kind="handoff", text=""))
            self.assertEqual((status, result["delivery"]), (200, "accepted_not_confirmed"))
            self.assertEqual(self.request("send-auto", dict(admitted, kind="handoff"))[0], 409)
            send.assert_called_once()

    def test_actual_http_new_inbound_revokes_previous(self):
        old = self.admit("old")
        new = self.admit("new")
        self.assertEqual(self.request("context", old)[0], 409)
        self.assertEqual(self.request("context", new)[0], 200)
        self.assertEqual(self.count("inbound_ids"), 2)

    def test_actual_http_policy_round_trip_revokes_admission(self):
        admitted = self.admit()
        for mode in ("all", "tests"):
            self.assertEqual(self.fixture.http("/api/policy/mode", {"mode": mode})[0], 200)
        self.assertEqual(self.request("context", admitted)[0], 409)
        self.assertEqual(self.request("send-auto", dict(admitted, kind="normal", text="no"))[0], 409)
        self.assertEqual(self.count("inbound_ids"), 1)

    def test_actual_http_concurrent_send_and_uncertainty(self):
        admitted = self.admit()
        payload = dict(admitted, kind="normal", text="Resposta sintetica")
        with patch.object(self.central.urllib.request, "urlopen", side_effect=OSError("uncertain")) as send:
            with ThreadPoolExecutor(max_workers=2) as pool:
                results = list(pool.map(lambda _: self.request("send-auto", payload)[0], range(2)))
            self.assertEqual(sorted(results), [409, 502])
            send.assert_called_once()
        self.assertEqual(self.count("replies"), 1)


if __name__ == "__main__":
    unittest.main()
