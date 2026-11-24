import re
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_consent_ui import OwnerConsentUI
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
