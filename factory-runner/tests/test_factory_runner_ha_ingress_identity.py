"""Offline tests for the HA ingress identity trust boundary."""
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ha_ingress_identity import verify_ha_ingress_context


class HAIngressIdentityTests(unittest.TestCase):
    OWNER_USER = "ha-user-123"
    OWNER_ID = "factory-owner"

    def context(self, *, peer="172.30.32.2", user=OWNER_USER,
                path="/api/hassio_ingress/0123456789abcdef/"):
        return {"peer_ip": peer, "headers": {
            "X-Remote-User-Id": user,
            "X-Ingress-Path": path,
        }}

    def verify(self, context=None, *, expected=OWNER_USER, owner=OWNER_ID):
        return verify_ha_ingress_context(
            self.context() if context is None else context,
            expected_ha_user_id=expected,
            owner_id=owner,
        )

    def test_trusted_supervisor_and_exact_owner(self):
        self.assertEqual(self.verify(), self.OWNER_ID)

    def test_header_names_are_case_insensitive(self):
        context = {"peer_ip": "172.30.32.2", "headers": {
            "x-remote-user-id": self.OWNER_USER,
            "x-ingress-path": "/api/hassio_ingress/token_123/",
        }}
        self.assertEqual(self.verify(context), self.OWNER_ID)

    def test_wrong_peer_cannot_spoof_identity_headers(self):
        self.assertIsNone(self.verify(self.context(peer="192.168.1.20")))

    def test_loopback_and_ipv6_peers_are_denied(self):
        for peer in ("127.0.0.1", "::1", "::ffff:172.30.32.2", "172.30.32.3"):
            with self.subTest(peer=peer):
                self.assertIsNone(self.verify(self.context(peer=peer)))

    def test_missing_or_wrong_user_is_denied(self):
        for user in (None, "", "other-user", " ha-user-123", "ha-user-123 "):
            headers = {"X-Ingress-Path": "/api/hassio_ingress/token/"}
            if user is not None:
                headers["X-Remote-User-Id"] = user
            context = {"peer_ip": "172.30.32.2", "headers": headers}
            with self.subTest(user=user):
                self.assertIsNone(self.verify(context))

    def test_missing_or_malformed_ingress_path_is_denied(self):
        for path in (None, "", "/", "/api/hassio_ingress/",
                     "/api/hassio_ingress/token/extra",
                     "/api/hassio_ingress/../token",
                     "/api/hassio_ingress/token?x=1",
                     "/api/hassio_ingress/token#fragment",
                     "/api/hassio_ingress/token with space"):
            headers = {"X-Remote-User-Id": self.OWNER_USER}
            if path is not None:
                headers["X-Ingress-Path"] = path
            context = {"peer_ip": "172.30.32.2", "headers": headers}
            with self.subTest(path=path):
                self.assertIsNone(self.verify(context))

    def test_duplicate_identity_headers_fail_closed(self):
        class Headers:
            def items(self):
                return [
                    ("X-Remote-User-Id", HAIngressIdentityTests.OWNER_USER),
                    ("x-remote-user-id", "attacker"),
                    ("X-Ingress-Path", "/api/hassio_ingress/token/"),
                ]
        context = {"peer_ip": "172.30.32.2", "headers": Headers()}
        self.assertIsNone(self.verify(context))

    def test_forwarded_and_bearer_headers_never_replace_peer_identity(self):
        context = self.context(peer="10.0.0.8")
        context["headers"].update({
            "X-Forwarded-For": "172.30.32.2",
            "X-Forwarded-Proto": "https",
            "Authorization": "Bearer " + "x" * 40,
        })
        self.assertIsNone(self.verify(context))

    def test_invalid_owner_configuration_fails_closed(self):
        for expected, owner in (("", self.OWNER_ID), ("user id", self.OWNER_ID),
                                (self.OWNER_USER, ""), (self.OWNER_USER, "owner id")):
            with self.subTest(expected=expected, owner=owner):
                self.assertIsNone(self.verify(expected=expected, owner=owner))

    def test_non_mapping_context_fails_closed(self):
        for context in ("trusted", [], 123):
            with self.subTest(context=context):
                self.assertIsNone(self.verify(context))
        self.assertIsNone(verify_ha_ingress_context(
            None, expected_ha_user_id=self.OWNER_USER, owner_id=self.OWNER_ID
        ))


if __name__ == "__main__":
    unittest.main()
