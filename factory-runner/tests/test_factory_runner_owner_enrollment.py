import base64, hashlib, json, os, stat, sys, tempfile, unittest, subprocess
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from owner_approval import ApprovalAuthority
from publication_contract import PublicationError

class OwnerEnrollmentTests(unittest.TestCase):
    def test_atomic_one_time_enrollment_and_restart_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            authority=ApprovalAuthority(root,root/"credentials"/"signing.pem",
                root/"credentials"/"owner.json","factory-runner-owner-m006-v1","ha-owner-123")
            self.assertEqual(authority.enrollment_status(),{"enrolled":False})
            result=authority.enroll("strong-owner-password-123","strong-owner-password-123","CADASTRAR")
            self.assertEqual(result,{"enrolled":True,"owner_id":"ha-owner-123"})
            credentials=root/"credentials"
            self.assertEqual(stat.S_IMODE(credentials.stat().st_mode),0o700)
            self.assertEqual(stat.S_IMODE((credentials/"signing.pem").stat().st_mode),0o600)
            self.assertEqual(stat.S_IMODE((credentials/"owner.json").stat().st_mode),0o600)
            record=json.loads((credentials/"owner.json").read_text())
            self.assertEqual(record["owner_id"],"ha-owner-123")
            self.assertNotIn("strong-owner-password-123",(credentials/"owner.json").read_text())
            public=base64.b64decode(authority.public_key(),validate=True)
            derived=subprocess.run(["/usr/bin/openssl","pkey","-in",str(credentials/"signing.pem"),"-pubout"],
                capture_output=True,check=True).stdout
            self.assertEqual(public,derived)
            authority.close()
            restarted=ApprovalAuthority(root,credentials/"signing.pem",
                credentials/"owner.json","factory-runner-owner-m006-v1","ha-owner-123")
            self.assertEqual(restarted.enrollment_status(),{"enrolled":True})
            with self.assertRaisesRegex(PublicationError,"owner_already_enrolled"):
                restarted.enroll("another-strong-password-456","another-strong-password-456","CADASTRAR")
            restarted.close()

    def test_short_or_mismatched_password_does_not_create_credentials(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            authority=ApprovalAuthority(root,root/"credentials"/"signing.pem",
                root/"credentials"/"owner.json","authority","owner")
            with self.assertRaisesRegex(PublicationError,"owner_enrollment_input_invalid"):
                authority.enroll("short","short","CADASTRAR")
            with self.assertRaisesRegex(PublicationError,"owner_enrollment_input_invalid"):
                authority.enroll("long-enough-password-123","different-password-123","CADASTRAR")
            self.assertFalse((root/"credentials").exists())
            authority.close()

    def test_existing_symlink_or_partial_credentials_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);root.chmod(0o700)
            (root/"credentials").symlink_to(root,target_is_directory=True)
            with self.assertRaisesRegex(PublicationError,"unsafe_owner_credentials_directory"):
                ApprovalAuthority(root,root/"credentials"/"signing.pem",
                    root/"credentials"/"owner.json","authority","owner")
