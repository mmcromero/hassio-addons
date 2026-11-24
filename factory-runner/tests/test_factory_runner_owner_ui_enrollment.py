import re
import sys
import unittest
from contextlib import redirect_stderr
from io import StringIO
from urllib.parse import urlencode
from email.message import Message
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_consent_ui import OwnerConsentUI
from ha_ingress_server import dispatch_owner_consent
from publication_contract import PublicationError

class FakeApprovalRPC:
    def __init__(self):
        self.enrolled=False
        self.calls=[]
    def enrollment_status(self):
        return {"enrolled":self.enrolled}
    def enroll(self,**kwargs):
        self.calls.append(kwargs)
        if self.enrolled:
            raise PublicationError("owner_already_enrolled")
        self.enrolled=True
        return {"enrolled":True,"owner_id":"owner-fixed"}

class OwnerUIEnrollmentTests(unittest.TestCase):
    def setUp(self):
        self.rpc=FakeApprovalRPC()
        self.ui=OwnerConsentUI(self.rpc,"https://ha.example.invalid",
                               ingress_verifier=lambda context:"owner-fixed")
        self.context={"verified":True,"ingress_path":"/api/hassio_ingress/test-token"}
    def test_one_time_enrollment_requires_csrf_origin_and_password_confirmation(self):
        view=self.ui.enroll_view(self.context)
        self.assertIn("minlength=\"16\"",view["html"])
        self.assertIn("expira em 2 minutos",view["html"])
        csrf=re.search(r'name="csrf" value="([a-f0-9]{64})"',view["html"]).group(1)
        result=self.ui.enroll(view["session"],{
            "csrf":csrf,"password":"strong-owner-password-123",
            "password_confirm":"strong-owner-password-123","confirmation":"CADASTRAR"
        },self.context,"https://ha.example.invalid")
        self.assertTrue(result["enrolled"])
        self.assertEqual(len(self.rpc.calls),1)
        self.assertNotIn("strong-owner-password-123",str(result))
        with self.assertRaises(PublicationError):
            self.ui.enroll_view(self.context)
    def test_wrong_origin_consumes_session_but_allows_a_fresh_session(self):
        view=self.ui.enroll_view(self.context)
        csrf=re.search(r'name="csrf" value="([a-f0-9]{64})"',view["html"]).group(1)
        body={"csrf":csrf,"password":"strong-owner-password-123",
              "password_confirm":"strong-owner-password-123","confirmation":"CADASTRAR"}
        with self.assertRaisesRegex(PublicationError,"session_invalid"):
            self.ui.enroll(view["session"],body,self.context,"https://evil.invalid")
        fresh=self.ui.enroll_view(self.context)
        self.assertNotEqual(fresh["session"],view["session"])
        with self.assertRaisesRegex(PublicationError,"session_invalid"):
            self.ui.enroll(view["session"],body,self.context,self.ui.origin)

    def test_session_failure_logs_only_a_safe_reason(self):
        view=self.ui.enroll_view(self.context)
        csrf=re.search(r'name="csrf" value="([a-f0-9]{64})"',view["html"]).group(1)
        body={"csrf":csrf,"password":"synthetic-owner-password-123",
              "password_confirm":"synthetic-owner-password-123","confirmation":"CADASTRAR"}
        captured=StringIO()
        with redirect_stderr(captured):
            with self.assertRaisesRegex(PublicationError,"session_invalid"):
                self.ui.enroll(view["session"],body,self.context,"https://evil.invalid")
        log=captured.getvalue()
        self.assertIn("reason=origin_mismatch",log)
        self.assertNotIn(csrf,log)
        self.assertNotIn("synthetic-owner-password-123",log)
        self.assertNotIn(self.context["ingress_path"],log)

    def test_full_supervisor_ingress_enrollment_round_trip(self):
        headers=Message()
        headers["X-Remote-User-Id"]="synthetic-ha-user"
        headers["X-Ingress-Path"]="/api/hassio_ingress/synthetic-ingress-token"
        get_result=dispatch_owner_consent(
            self.ui,method="GET",path="/owner-enroll/",peer_ip="172.30.32.2",
            headers=headers,expected_ha_user_id="synthetic-ha-user",owner_id="owner-fixed")
        self.assertEqual(get_result[0],200)
        csrf=re.search(rb'name="csrf" value="([a-f0-9]{64})"',get_result[2]).group(1).decode()
        post_headers=Message()
        for name,value in headers.items():
            post_headers[name]=value
        post_headers["Origin"]="https://ha.example.invalid"
        post_headers["Content-Type"]="application/x-www-form-urlencoded"
        body=urlencode({
            "csrf":csrf,
            "password":"synthetic-owner-password-123",
            "password_confirm":"synthetic-owner-password-123",
            "confirmation":"CADASTRAR",
        }).encode()
        post_result=dispatch_owner_consent(
            self.ui,method="POST",path="/owner-enroll/submit",peer_ip="172.30.32.2",
            headers=post_headers,body=body,
            expected_ha_user_id="synthetic-ha-user",owner_id="owner-fixed")
        self.assertEqual(post_result[0],200)
        self.assertTrue(self.rpc.enrolled)
        self.assertEqual(len(self.rpc.calls),1)

    def test_ingress_path_mismatch_is_diagnosed_without_logging_path(self):
        view=self.ui.enroll_view(self.context)
        csrf=re.search(r'name="csrf" value="([a-f0-9]{64})"',view["html"]).group(1)
        body={"csrf":csrf,"password":"synthetic-owner-password-123",
              "password_confirm":"synthetic-owner-password-123","confirmation":"CADASTRAR"}
        changed_context={**self.context,"ingress_path":"/api/hassio_ingress/other-token"}
        captured=StringIO()
        with redirect_stderr(captured):
            with self.assertRaisesRegex(PublicationError,"session_invalid"):
                self.ui.enroll(view["session"],body,changed_context,"https://ha.example.invalid")
        log=captured.getvalue()
        self.assertIn("reason=ingress_path_mismatch",log)
        self.assertNotIn("test-token",log)
        self.assertNotIn("other-token",log)

    def test_wrong_owner_cannot_use_existing_enrollment_session(self):
        view=self.ui.enroll_view(self.context)
        csrf=re.search(r'name="csrf" value="([a-f0-9]{64})"',view["html"]).group(1)
        self.ui.ingress_verifier=lambda context:"different-owner"
        with self.assertRaisesRegex(PublicationError,"session_invalid"):
            self.ui.enroll(view["session"],{
                "csrf":csrf,"password":"strong-owner-password-123",
                "password_confirm":"strong-owner-password-123","confirmation":"CADASTRAR"
            },self.context,self.ui.origin)
        self.assertFalse(self.rpc.enrolled)
    def test_home_page_never_offers_publication_action(self):
        page=self.ui.home_view(self.context)["html"]
        self.assertNotIn("PUBLICAR",page)
        self.assertIn("owner-enroll/",page)
