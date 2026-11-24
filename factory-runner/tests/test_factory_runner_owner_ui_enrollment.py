import re
import sys
import unittest
from email.message import Message
from urllib.parse import urlencode
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_consent_ui import OwnerConsentUI
from ha_ingress_server import dispatch_owner_consent

class FakeApprovalRPC:
    def __init__(self):
        self.enrolled = False
        self.calls = []
    def enrollment_status(self):
        return {"enrolled": self.enrolled}
    def request(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if action == "view":
            return {
                "consent_digest": "d" * 64,
                "binding": {"source_sha": "a" * 40, "target": "test"},
                "preview": {"files": []},
                "receipt": {"files": [], "state": "ready",
                            "tests": {"status": "PASS", "checks": []}},
            }
        if action == "consent":
            return {"consented": True}
        raise AssertionError("unexpected action")

class OwnerSettingsAndConsentTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakeApprovalRPC()
        self.ui = OwnerConsentUI(
            self.rpc, "https://ha.example.invalid",
            ingress_verifier=lambda context: "owner-fixed",
        )
        self.context = {
            "verified": True,
            "ingress_path": "/api/hassio_ingress/test-token",
        }

    def test_unenrolled_home_directs_to_addon_settings_not_ingress_form(self):
        page = self.ui.home_view(self.context)["html"]
        self.assertIn("Configurações deste add-on", page)
        self.assertIn("senha temporária", page)
        self.assertNotIn("owner-enroll", page)
        self.assertNotIn("<form", page)

    def test_publication_consent_does_not_request_password_again(self):
        view = self.ui.view("a" * 32, self.context)
        self.assertNotIn('type="password"', view["html"])
        self.assertNotIn('name="password"', view["html"])
        self.assertIn("PUBLICAR", view["html"])
        csrf = re.search(r'name="csrf" value="([a-f0-9]{64})"', view["html"]).group(1)
        result = self.ui.consent(
            view["session"],
            {"csrf": csrf, "confirmation": "PUBLICAR"},
            self.context,
            self.ui.origin,
        )
        self.assertEqual(result, {"consented": True})
        action, payload = self.rpc.calls[-1]
        self.assertEqual(action, "consent")
        self.assertEqual(set(payload), {"proposal", "consent_digest", "confirmation"})
        self.assertNotIn("password", payload)

    def test_http_consent_post_accepts_confirmation_without_password(self):
        headers = Message()
        headers["X-Remote-User-Id"] = "synthetic-ha-user"
        headers["X-Ingress-Path"] = "/api/hassio_ingress/synthetic-ingress-token"
        with patch("ha_ingress_server.verify_ha_ingress_context", return_value="owner-fixed"):
            get_result = dispatch_owner_consent(
                self.ui, method="GET", path="/owner-consent/" + "a" * 32,
                peer_ip="172.30.32.2", headers=headers,
                expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
            self.assertEqual(get_result[0], 200)
            csrf = re.search(rb'name="csrf" value="([a-f0-9]{64})"', get_result[2]).group(1).decode()
            post_headers = Message()
            post_headers["X-Remote-User-Id"] = "synthetic-ha-user"
            post_headers["X-Ingress-Path"] = headers["X-Ingress-Path"]
            post_headers["Origin"] = "https://ha.example.invalid"
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            post_headers["Cookie"] = get_result[1]["Set-Cookie"].split(";", 1)[0]
            legacy_body = urlencode({
                "csrf": csrf, "confirmation": "PUBLICAR", "password": "must-not-be-required"
            }).encode()
            rejected = dispatch_owner_consent(
                self.ui, method="POST", path="/owner-consent/consent",
                peer_ip="172.30.32.2", headers=post_headers, body=legacy_body,
                expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
            self.assertEqual(rejected[0], 400)
            body = urlencode({"csrf": csrf, "confirmation": "PUBLICAR"}).encode()
            accepted = dispatch_owner_consent(
                self.ui, method="POST", path="/owner-consent/consent",
                peer_ip="172.30.32.2", headers=post_headers, body=body,
                expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
        self.assertEqual(accepted[0], 200)
        action, payload = self.rpc.calls[-1]
        self.assertEqual(action, "consent")
        self.assertNotIn("password", payload)

    def test_ingress_enrollment_routes_are_not_exposed(self):
        with patch("ha_ingress_server.verify_ha_ingress_context", return_value="owner-fixed"):
            get_result = dispatch_owner_consent(
                self.ui, method="GET", path="/owner-enroll/", peer_ip="172.30.32.2",
                headers={}, expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
            post_result = dispatch_owner_consent(
                self.ui, method="POST", path="/owner-enroll/submit", peer_ip="172.30.32.2",
                headers={}, body=b"", expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
        self.assertEqual(get_result[0], 404)
        self.assertEqual(post_result[0], 404)

if __name__ == "__main__":
    unittest.main()
