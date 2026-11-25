import re
import sys
import unittest
from email.message import Message
from pathlib import Path
from urllib.parse import urlencode
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_consent_ui import OwnerConsentUI
from ha_ingress_server import dispatch_owner_consent
from approval_ipc import ApprovalRPCServer, ApprovalRPCClient


class FakeRPC:
    def __init__(self, grant_state="active"):
        self.grant_state = grant_state
        self.calls = []

    def request(self, action, **kwargs):
        self.calls.append((action, kwargs))
        if action == "view":
            return {
                "consent_digest": "d" * 64,
                "state": "already_consented",
                "grant_nonce": "e" * 32,
                "grant_state": self.grant_state,
                "binding": {"project": "fixture", "source_sha": "a" * 40},
                "preview": [],
                "receipt": {
                    "files": [], "state": "ready",
                    "tests": {"status": "PASS", "checks": []},
                },
            }
        raise AssertionError("unexpected RPC action")

    def revoke(self, nonce, password):
        self.calls.append(("revoke", {"nonce": nonce, "password": password}))
        return {"revoked": True}


class OwnerGrantRevocationTests(unittest.TestCase):
    def setUp(self):
        self.rpc = FakeRPC()
        self.ui = OwnerConsentUI(
            self.rpc, "https://ha.example.invalid",
            ingress_verifier=lambda context: "owner-fixed",
        )

    def test_active_grant_exposes_single_use_revoke_form(self):
        page = self.ui.view("a" * 32, {"trusted": True})
        self.assertIn('name="password"', page["html"])
        self.assertIn("REVOGAR", page["html"])
        csrf = re.search(r'name="csrf" value="([a-f0-9]{64})"', page["html"]).group(1)
        result = self.ui.revoke(
            page["session"],
            {"csrf": csrf, "confirmation": "REVOGAR", "password": "owner-password"},
            {"trusted": True}, self.ui.origin,
        )
        self.assertEqual(result, {"revoked": True})
        self.assertEqual(self.rpc.calls[-1], (
            "revoke", {"nonce": "e" * 32, "password": "owner-password"}
        ))

    def test_reserved_revoked_or_expired_grant_has_no_revoke_form(self):
        for state in ("reserved", "revoked", "expired", "not_issued"):
            rpc = FakeRPC(state)
            ui = OwnerConsentUI(
                rpc, "https://ha.example.invalid",
                ingress_verifier=lambda context: "owner-fixed",
            )
            page = ui.view("a" * 32, {"trusted": True})
            self.assertNotIn('name="password"', page["html"])
            self.assertIn("Estado da autorização", page["html"])

    def test_approval_ipc_exposes_revoke_only_to_configured_owner_uid(self):
        import os
        import threading
        import tempfile
        from pathlib import Path
        from publication_contract import PublicationError

        class Issuer:
            def revoke(self, nonce, password):
                return {"revoked": True, "nonce": nonce}

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            root.chmod(0o2750)
            path = root / "approval.sock"
            server = ApprovalRPCServer(
                path, Issuer(), {os.geteuid(): {"revoke"}}, group_gid=os.getgid()
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                client = ApprovalRPCClient(path, os.geteuid())
                result = client.revoke("a" * 32, "owner-password")
                self.assertEqual(result, {"revoked": True, "nonce": "a" * 32})
            finally:
                server.shutdown()
                server.server_close()
                thread.join(timeout=2)

            denied_path = root / "denied.sock"
            denied_server = ApprovalRPCServer(
                denied_path, Issuer(), {}, group_gid=os.getgid()
            )
            denied_thread = threading.Thread(target=denied_server.serve_forever, daemon=True)
            denied_thread.start()
            try:
                denied = ApprovalRPCClient(denied_path, os.geteuid())
                with self.assertRaisesRegex(PublicationError, "peer_not_authorized"):
                    denied.revoke("a" * 32, "owner-password")
            finally:
                denied_server.shutdown()
                denied_server.server_close()
                denied_thread.join(timeout=2)

    def test_ingress_revocation_requires_verified_owner_session_csrf_and_password(self):
        headers = Message()
        headers["X-Remote-User-Id"] = "synthetic-ha-user"
        headers["X-Ingress-Path"] = "/api/hassio_ingress/synthetic-token"
        with patch("ha_ingress_server.verify_ha_ingress_context", return_value="owner-fixed"):
            page = dispatch_owner_consent(
                self.ui, method="GET", path="/owner-consent/" + "a" * 32,
                peer_ip="172.30.32.2", headers=headers,
                expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
            self.assertEqual(page[0], 200)
            csrf = re.search(rb'name="csrf" value="([a-f0-9]{64})"', page[2]).group(1).decode()
            post_headers = Message()
            post_headers["X-Remote-User-Id"] = "synthetic-ha-user"
            post_headers["X-Ingress-Path"] = headers["X-Ingress-Path"]
            post_headers["Origin"] = "https://ha.example.invalid"
            post_headers["Content-Type"] = "application/x-www-form-urlencoded"
            post_headers["Cookie"] = page[1]["Set-Cookie"].split(";", 1)[0]
            body = urlencode({
                "csrf": csrf, "confirmation": "REVOGAR", "password": "owner-password"
            }).encode()
            result = dispatch_owner_consent(
                self.ui, method="POST", path="/owner-consent/revoke",
                peer_ip="172.30.32.2", headers=post_headers, body=body,
                expected_ha_user_id="synthetic-ha-user", owner_id="owner-fixed",
            )
        self.assertEqual(result[0], 200)
        self.assertEqual(self.rpc.calls[-1], (
            "revoke", {"nonce": "e" * 32, "password": "owner-password"}
        ))


if __name__ == "__main__":
    unittest.main()
