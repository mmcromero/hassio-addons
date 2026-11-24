"""Offline tests for the dormant HA owner-consent ingress handler."""
from http.server import BaseHTTPRequestHandler
from pathlib import Path
import sys
import unittest
from urllib.parse import urlencode
from unittest.mock import patch
from email.message import Message

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ha_ingress_server import (
    dispatch_owner_consent, dispatch_owner_ingress_disabled,
    make_owner_consent_handler,
)


class FakeOwnerUI:
    origin = "https://ha.example.invalid"

    def __init__(self):
        self.views = []
        self.consents = []
        self.enrollments = []

    def home_view(self, context):
        return {"html": "<h1>Factory Runner</h1>",
                "headers": {"Cache-Control": "no-store"}}

    def enroll_view(self, context):
        return {"session": "a" * 64,
                "html": "<form action='submit'></form>",
                "headers": {"Cache-Control": "no-store"}}

    def enroll(self, session, body, context, origin):
        self.enrollments.append((session, body, context, origin))
        if (session != "a" * 64 or origin != self.origin
                or set(body) != {"csrf", "password", "password_confirm", "confirmation"}):
            raise ValueError("denied")
        return {"enrolled": True}

    def view(self, proposal, context):
        self.views.append((proposal, context))
        return {
            "session": "a" * 64,
            "html": "<form action='consent'></form>",
            "headers": {
                "Cache-Control": "no-store",
                "Content-Security-Policy": "default-src 'none'; form-action 'self'",
            },
        }

    def consent(self, session, body, context, origin):
        self.consents.append((session, body, context, origin))
        if origin != self.origin or session != "a" * 64:
            raise ValueError("denied")
        return {"payload": {"nonce": "synthetic"}}


class HAIngressServerTests(unittest.TestCase):
    OWNER_USER = "ha-user-123"
    OWNER_ID = "factory-owner"
    PROPOSAL = "b" * 32

    def headers(self, **extra):
        value = {
            "X-Remote-User-Id": self.OWNER_USER,
            "X-Ingress-Path": "/api/hassio_ingress/0123456789abcdef",
        }
        value.update(extra)
        return value

    def dispatch(self, ui, method, path, *, peer="172.30.32.2",
                 headers=None, body=b""):
        return dispatch_owner_consent(
            ui, method=method, path=path, peer_ip=peer,
            headers=self.headers() if headers is None else headers,
            body=body, expected_ha_user_id=self.OWNER_USER,
            owner_id=self.OWNER_ID,
        )

    def test_get_issues_secure_scoped_cookie_without_exposing_session(self):
        ui = FakeOwnerUI()
        status, headers, body = self.dispatch(
            ui, "GET", "/owner-consent/" + self.PROPOSAL
        )
        self.assertEqual(status, 200)
        self.assertIn("Secure; HttpOnly; SameSite=Strict", headers["Set-Cookie"])
        self.assertIn("Path=/api/hassio_ingress/0123456789abcdef/owner-consent/",
                      headers["Set-Cookie"])
        self.assertNotIn(("a" * 64).encode(), body)
        self.assertIn(b"form-action 'self'", headers["Content-Security-Policy"].encode())
        self.assertEqual(ui.views[0][0], self.PROPOSAL)

    def test_owner_home_and_enrollment_get_routes(self):
        ui = FakeOwnerUI()
        status, headers, body = self.dispatch(ui, "GET", "/")
        self.assertEqual(status, 200)
        self.assertIn(b"Factory Runner", body)

        status, headers, body = self.dispatch(ui, "GET", "/owner-enroll/")
        self.assertEqual(status, 200)
        self.assertIn("Path=/api/hassio_ingress/0123456789abcdef/owner-enroll/",
                      headers["Set-Cookie"])

    def test_owner_enrollment_short_route_redirects_to_slash(self):
        status, headers, body = self.dispatch(FakeOwnerUI(), "GET", "/owner-enroll")
        self.assertEqual(status, 303)
        self.assertEqual(headers["Location"],
                         "/api/hassio_ingress/0123456789abcdef/owner-enroll/")

    def test_owner_enrollment_post_uses_exact_fields_and_clears_cookie(self):
        ui = FakeOwnerUI()
        form = urlencode({
            "csrf": "csrf-token",
            "password": "strong-owner-password-123",
            "password_confirm": "strong-owner-password-123",
            "confirmation": "CADASTRAR",
        }).encode()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        status, response_headers, body = self.dispatch(
            ui, "POST", "/owner-enroll/submit", headers=headers, body=form
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Cadastro do propriet", body)
        self.assertIn("Max-Age=0", response_headers["Set-Cookie"])
        self.assertIn("/owner-enroll/", response_headers["Set-Cookie"])
        self.assertEqual(ui.enrollments[0][1]["confirmation"], "CADASTRAR")

    def test_owner_enrollment_post_rejects_extra_fields(self):
        ui = FakeOwnerUI()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        body = urlencode({
            "csrf": "x", "password": "strong-owner-password-123",
            "password_confirm": "strong-owner-password-123",
            "confirmation": "CADASTRAR", "extra": "unexpected",
        }).encode()
        self.assertEqual(self.dispatch(
            ui, "POST", "/owner-enroll/submit", headers=headers, body=body
        )[0], 400)
        self.assertEqual(ui.enrollments, [])

    def test_oversized_consent_page_is_rejected(self):
        class LargePageUI(FakeOwnerUI):
            def view(self, proposal, context):
                return {"session": "a" * 64, "html": "x" * (1024 * 1024 + 1), "headers": {}}
        self.assertEqual(self.dispatch(
            LargePageUI(), "GET", "/owner-consent/" + self.PROPOSAL
        )[0], 503)

    def test_wrong_origin_is_rejected_by_owner_ui(self):
        ui = FakeOwnerUI()
        body = urlencode({"csrf": "x", "password": "y", "confirmation": "PUBLICAR"}).encode()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin="https://evil.invalid",
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(self.dispatch(
            ui, "POST", "/owner-consent/consent", headers=headers, body=body
        )[0], 403)

    def test_wrong_peer_or_identity_is_denied_before_ui(self):
        ui = FakeOwnerUI()
        self.assertEqual(self.dispatch(
            ui, "GET", "/owner-consent/" + self.PROPOSAL, peer="192.168.1.10"
        )[0], 403)
        self.assertEqual(ui.views, [])

    def test_unknown_route_and_query_are_denied(self):
        ui = FakeOwnerUI()
        self.assertEqual(self.dispatch(ui, "GET", "/owner-consent/not-a-proposal")[0], 404)
        self.assertEqual(self.dispatch(
            ui, "GET", "/owner-consent/" + self.PROPOSAL + "?next=1"
        )[0], 400)
        self.assertEqual(ui.views, [])

    def test_post_uses_cookie_origin_and_exact_form(self):
        ui = FakeOwnerUI()
        form = urlencode({
            "csrf": "csrf-token",
            "password": "owner-password",
            "confirmation": "PUBLICAR",
        }).encode()
        headers = self.headers(
            Cookie="ingress_session=ha-session; factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        status, response_headers, body = self.dispatch(
            ui, "POST", "/owner-consent/consent", headers=headers, body=form
        )
        self.assertEqual(status, 200)
        self.assertIn(b"Nenhuma publica", body)
        self.assertIn("Max-Age=0", response_headers["Set-Cookie"])
        self.assertEqual(ui.consents[0][0], "a" * 64)
        self.assertEqual(ui.consents[0][1]["confirmation"], "PUBLICAR")
        self.assertEqual(ui.consents[0][3], ui.origin)

    def test_duplicate_cookie_or_missing_origin_is_denied(self):
        ui = FakeOwnerUI()
        body = urlencode({"csrf": "x", "password": "y", "confirmation": "PUBLICAR"}).encode()
        duplicate = self.headers(
            Cookie="factory_owner_session=" + "a" * 64 + "; factory_owner_session=" + "b" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(self.dispatch(ui, "POST", "/owner-consent/consent",
                                        headers=duplicate, body=body)[0], 403)
        missing_origin = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        self.assertEqual(self.dispatch(ui, "POST", "/owner-consent/consent",
                                        headers=missing_origin, body=body)[0], 403)
        self.assertEqual(ui.consents, [])

    def test_duplicate_fields_and_wrong_content_type_are_denied(self):
        ui = FakeOwnerUI()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        duplicate = b"csrf=x&csrf=y&password=z&confirmation=PUBLICAR"
        self.assertEqual(self.dispatch(ui, "POST", "/owner-consent/consent",
                                        headers=headers, body=duplicate)[0], 400)
        wrong_type = dict(headers)
        wrong_type["Content-Type"] = "application/json"
        self.assertEqual(self.dispatch(ui, "POST", "/owner-consent/consent",
                                        headers=wrong_type, body=b"{}")[0], 415)
        self.assertEqual(ui.consents, [])

    def test_http_handler_rejects_transfer_encoding_before_reading_body(self):
        handler_type = make_owner_consent_handler(
            ui=FakeOwnerUI(), expected_ha_user_id=self.OWNER_USER,
            owner_id=self.OWNER_ID,
        )
        handler = handler_type.__new__(handler_type)
        handler.client_address = ("172.30.32.2", 12345)
        handler.headers = Message()
        handler.headers["X-Remote-User-Id"] = self.OWNER_USER
        handler.headers["X-Ingress-Path"] = "/api/hassio_ingress/token"
        handler.headers["Content-Length"] = "1"
        handler.headers["Transfer-Encoding"] = "chunked"
        class MustNotRead:
            def read(self, size):
                raise AssertionError("body must not be read before framing validation")
        handler.rfile = MustNotRead()
        captured = []
        handler._send = captured.append
        with patch("ha_ingress_server.verify_ha_ingress_context", return_value=self.OWNER_ID):
            handler.do_POST()
        self.assertEqual(captured[0][0], 400)

    def test_transfer_encoding_is_rejected_even_with_content_length(self):
        ui = FakeOwnerUI()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": "1",
                "Transfer-Encoding": "chunked",
            },
        )
        body = urlencode({"csrf": "x", "password": "y", "confirmation": "PUBLICAR"}).encode()
        self.assertEqual(self.dispatch(
            ui, "POST", "/owner-consent/consent", headers=headers, body=body
        )[0], 400)
        self.assertEqual(ui.consents, [])

    def test_form_field_count_is_bounded(self):
        ui = FakeOwnerUI()
        headers = self.headers(
            Cookie="factory_owner_session=" + "a" * 64,
            Origin=ui.origin,
            **{"Content-Type": "application/x-www-form-urlencoded"},
        )
        body = urlencode({
            "csrf": "x", "password": "y", "confirmation": "PUBLICAR",
            "extra1": "1", "extra2": "2", "extra3": "3",
            "extra4": "4", "extra5": "5", "extra6": "6",
        }).encode()
        self.assertEqual(self.dispatch(
            ui, "POST", "/owner-consent/consent", headers=headers, body=body
        )[0], 400)
        self.assertEqual(ui.consents, [])

    def test_oversized_form_and_unsupported_method_are_denied(self):
        ui = FakeOwnerUI()
        self.assertEqual(self.dispatch(
            ui, "POST", "/owner-consent/consent",
            headers=self.headers(Cookie="factory_owner_session=" + "a" * 64,
                                 Origin=ui.origin,
                                 **{"Content-Type": "application/x-www-form-urlencoded"}),
            body=b"x" * 4097,
        )[0], 413)
        self.assertEqual(self.dispatch(ui, "DELETE", "/owner-consent/consent")[0], 405)

    def test_handler_factory_does_not_start_listener(self):
        handler = make_owner_consent_handler(
            ui=FakeOwnerUI(), expected_ha_user_id=self.OWNER_USER,
            owner_id=self.OWNER_ID,
        )
        self.assertTrue(issubclass(handler, BaseHTTPRequestHandler))

    def test_disabled_ingress_is_status_only_and_supervisor_only(self):
        status, headers, body = dispatch_owner_ingress_disabled(
            method="GET", path="/", peer_ip="172.30.32.2"
        )
        self.assertEqual(status, 200)
        self.assertIn("no-store", headers["Cache-Control"])
        self.assertIn(b"Autorização desativada", body)
        self.assertIn(b"owner_ingress_enabled", body)
        self.assertNotIn(b"PUBLICAR", body)
        self.assertIn("default-src 'none'", headers["Content-Security-Policy"])

        denied = dispatch_owner_ingress_disabled(
            method="GET", path="/", peer_ip="192.168.1.10"
        )
        self.assertEqual(denied[0], 403)

    def test_manifest_exposes_ingress_but_keeps_owner_opt_in_disabled(self):
        config = (ROOT / "config.yaml").read_text(encoding="utf-8")
        self.assertIn("\ningress: true\n", config)
        self.assertIn("owner_ingress_enabled: false", config)

    def test_disabled_ingress_rejects_mutation_and_unknown_routes(self):
        denied = dispatch_owner_ingress_disabled(
            method="POST", path="/owner-enroll/submit", peer_ip="172.30.32.2"
        )
        self.assertEqual(denied[0], 405)
        missing = dispatch_owner_ingress_disabled(
            method="GET", path="/owner-consent/" + self.PROPOSAL,
            peer_ip="172.30.32.2"
        )
        self.assertEqual(missing[0], 404)



if __name__ == "__main__":
    unittest.main()
