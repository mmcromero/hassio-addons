"""Offline Graph contract tests, no real Meta credentials or network."""
import json
import unittest
from urllib.parse import parse_qs, urlsplit

import instagram_connection as ic

CONFIG = {"instagram_account_id": "17841454345931235",
          "meta_graph_version": "v27.0",
          "meta_app_id": "1234567890123456",
          "meta_app_secret": "FAKE_APP_SECRET_REALLY_LONG",
          "meta_verify_token": "not-a-real-token-this-is-only-a-test",
          "ingress_enabled": True}

class Response:
    def __init__(self, obj):
        self.body = json.dumps(obj).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def read(self, size):
        return self.body[:size]

class ConnectionTests(unittest.TestCase):
    def test_exact_assigned_instagram_account(self):
        observed = []
        def fake(req, timeout):
            observed.append(req)
            if "/assigned_instagram_accounts" in req.full_url:
                return Response({"data": [
                    {"id": "17841454345931235", "username": "umdoislab"}]})
            return Response({"client_business_id": "338861439025441", "id": "9"})
        found = ic.verify_access(CONFIG, "X" * 50, opener=fake)
        self.assertEqual(found["account_id"], CONFIG["instagram_account_id"])
        self.assertEqual(found["username"], "umdoislab")
        self.assertEqual(found["client_business_id"], "338861439025441")
        self.assertEqual(len(observed), 3)
        self.assertTrue(all(x.get_header("Authorization") == "Bearer " + "X" * 50
                            for x in observed))
        self.assertTrue(all(urlsplit(x.full_url).netloc == "graph.facebook.com"
                            for x in observed))
        self.assertNotIn("X" * 50, observed[0].full_url)

    def test_verify_access_resolves_exact_linked_page_token(self):
        observed = []
        def fake(req, timeout):
            observed.append(req)
            path = urlsplit(req.full_url).path
            if path.endswith('/assigned_instagram_accounts'):
                return Response({"data": [{"id": CONFIG["instagram_account_id"], "username": "umdoislab"}]})
            if path.endswith('/me/accounts'):
                return Response({"data": [
                    {"id": "1122334455667788", "name": "Umdoislab Page",
                     "access_token": "P" * 50, "tasks": ["MESSAGING"],
                     "instagram_business_account": {"id": CONFIG["instagram_account_id"], "username": "umdoislab"}},
                    {"id": "9988776655443322", "name": "Other Page",
                     "access_token": "Q" * 50, "tasks": ["MESSAGING"],
                     "instagram_business_account": {"id": "12345678901234567", "username": "other"}}
                ]})
            return Response({"client_business_id": "338861439025441", "id": "9"})
        found = ic.verify_access(CONFIG, "X" * 50, opener=fake)
        self.assertEqual(found["page_id"], "1122334455667788")
        self.assertEqual(found["messaging_page_id"], found["page_id"])
        self.assertEqual(found["page_access_token"], "P" * 50)
        self.assertNotIn("P" * 50, observed[-1].full_url)

    def test_reject_wrong_account_even_if_token_is_valid(self):
        def wrong(req, timeout):
            return Response({"data": [{"id": "123456789012", "username": "umdoislab"}]})
        with self.assertRaises(ic.ConnectionError):
            ic.verify_access(CONFIG, "X" * 50, opener=wrong)

    def test_reject_wrong_username(self):
        def wrong(req, timeout):
            return Response({"data": [{"id": CONFIG["instagram_account_id"],
                                      "username": "impostor"}]})
        with self.assertRaises(ic.ConnectionError):
            ic.verify_access(CONFIG, "X" * 50, opener=wrong)

    def test_reject_malformed_business_response(self):
        def wrong(req, timeout):
            if "/assigned_instagram_accounts" in req.full_url:
                return Response({"data": [{"id": CONFIG["instagram_account_id"],
                                           "username": "umdoislab"}]})
            return Response({"client_business_id": None})
        with self.assertRaises(ic.ConnectionError):
            ic.verify_access(CONFIG, "X" * 50, opener=wrong)

    def test_reject_invalid_graph_path(self):
        with self.assertRaises(ic.ConnectionError):
            ic.request_graph("v27.0", "https://evil.test/", "X" * 50)
        with self.assertRaises(ic.ConnectionError):
            ic.request_graph("../", "/me", "X" * 50)

    def test_subscribe_messages_only_and_no_send(self):
        observed = {}
        def fake(req, timeout):
            observed["request"] = req
            return Response({"success": True})
        cred = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"]}
        value = ic.subscribe_messages(CONFIG, cred, opener=fake)
        self.assertGreater(value, 0)
        req = observed["request"]
        debug = observed["debug"]
        self.assertEqual(parse_qs(urlsplit(debug.full_url).query)["input_token"], ["P" * 50])
        self.assertNotIn("FAKE_APP_SECRET_REALLY_LONG", debug.full_url)
        self.assertEqual(debug.get_header("Authorization"), "Bearer 1234567890123456|FAKE_APP_SECRET_REALLY_LONG")
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(urlsplit(req.full_url).path,
                         "/v27.0/17841454345931235/subscribed_apps")
        self.assertEqual(parse_qs(req.data.decode())["subscribed_fields"], ["messages"])
        self.assertNotIn("send", req.full_url)
        self.assertEqual(req.get_header("Authorization"), "Bearer " + "T" * 50)

    def test_send_text_uses_fixed_meta_endpoint_and_verified_account(self):
        observed = {}
        def fake(req, timeout):
            path = urlsplit(req.full_url).path
            if path.endswith('/debug_token'):
                observed["debug"] = req
                return Response({"data": {"is_valid": True,
                    "scopes": ["pages_messaging", "instagram_manage_messages"]}})
            observed["request"] = req
            body = parse_qs(req.data.decode())
            observed["recipient"] = json.loads(body["recipient"][0])
            observed["message"] = json.loads(body["message"][0])
            return Response({"recipient_id": "12345678901234567", "message_id": "mid-123"})
        cred = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"],
                "business_id": "umdoislab", "username": "umdoislab", "verified_at": 10000,
                "page_id": "1122334455667788", "page_access_token": "P" * 50,
                "messaging_page_id": "1122334455667788"}
        result = ic.send_text_message(CONFIG, cred, "12345678901234567", "Olá, tudo bem?", opener=fake)
        req = observed["request"]
        self.assertEqual(req.get_method(), "POST")
        self.assertEqual(urlsplit(req.full_url).netloc, "graph.facebook.com")
        self.assertEqual(urlsplit(req.full_url).path, "/v27.0/me/messages")
        self.assertEqual(req.get_header("Authorization"), "Bearer " + "P" * 50)
        self.assertNotIn("P" * 50, req.full_url)
        self.assertEqual(observed["recipient"], {"id": "12345678901234567"})
        self.assertEqual(observed["message"], {"text": "Olá, tudo bem?"})
        self.assertEqual(result["message_id"], "mid-123")

    def test_send_text_requires_both_meta_messaging_permissions(self):
        observed = []
        def fake(req, timeout):
            observed.append(req)
            return Response({"data": {"is_valid": True, "scopes": ["instagram_manage_messages"]}})
        cred = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"],
                "business_id": "umdoislab", "username": "umdoislab", "verified_at": 10000,
                "page_id": "1122334455667788", "page_access_token": "P" * 50,
                "messaging_page_id": "1122334455667788"}
        with self.assertRaises(ic.GraphError):
            ic.send_text_message(CONFIG, cred, "12345678901234567", "Olá", opener=fake)
        self.assertEqual(len(observed), 1)
        self.assertTrue(urlsplit(observed[0].full_url).path.endswith('/debug_token'))

    def test_send_text_rejects_unverified_or_oversized_before_network(self):
        cred = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"]}
        def forbidden(*args, **kwargs):
            raise AssertionError("network must not be called")
        with self.assertRaises(ic.ConnectionError):
            ic.send_text_message(CONFIG, cred, "12345678901234567", "Oi", opener=forbidden)
        verified = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"],
                    "business_id": "umdoislab", "username": "umdoislab", "verified_at": 10000,
                    "page_id": "1122334455667788", "page_access_token": "P" * 50,
                    "messaging_page_id": "1122334455667788"}
        with self.assertRaises(ic.ConnectionError):
            ic.send_text_message(CONFIG, verified, "12345678901234567", "x" * 1001, opener=forbidden)
        with self.assertRaises(ic.ConnectionError):
            ic.send_text_message(CONFIG, verified, "not-an-id", "Oi", opener=forbidden)

    def test_reject_subscription_without_webhook_gate(self):
        cred = {"access_token": "T" * 50, "account_id": CONFIG["instagram_account_id"]}
        for change in ({"ingress_enabled": False},
                       {"meta_verify_token": ""}, {"meta_app_secret": ""}):
            with self.assertRaises(ic.ConnectionError):
                ic.subscribe_messages({**CONFIG, **change}, cred)

    def test_reject_subscription_for_other_account(self):
        with self.assertRaises(ic.ConnectionError):
            ic.subscribe_messages(CONFIG, {"access_token": "T" * 50,
                                          "account_id": "111222333444555"})

    def test_account_status_does_not_infer_webhook_delivery(self):
        self.assertFalse(ic.credential_status(None, CONFIG)["account_verified"])
        cred = {"account_id": CONFIG["instagram_account_id"], "username": "umdoislab",
                "verified_at": 10000, "access_token": "T" * 50}
        status = ic.credential_status(cred, CONFIG)
        self.assertTrue(status["account_verified"])
        self.assertFalse(status["subscription_requested"])
        self.assertTrue(ic.credential_status({**cred, "subscribed_at": 20000},
                                             CONFIG)["subscription_requested"])

if __name__ == "__main__":
    unittest.main()
