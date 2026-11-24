import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stderr
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import owner_settings_enroll as settings
from publication_contract import PublicationError

class Response:
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, limit): return b'{"result":"ok"}'

class OwnerSettingsEnrollmentTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() != 0:
            self.skipTest("Supervisor options ownership contract requires root")
        self.tmp = tempfile.TemporaryDirectory()
        self.options = Path(self.tmp.name) / "options.json"
        self._old_options = settings.OPTIONS
        settings.OPTIONS = self.options

    def tearDown(self):
        settings.OPTIONS = self._old_options
        self.tmp.cleanup()

    def write_options(self, password="", confirmation="", enabled=True, user_id="synthetic-ha-user", origin="https://ha.example.invalid"):
        self.options.write_text(json.dumps({
            "owner_password": password,
            "owner_password_confirm": confirmation,
            "owner_ha_user_id": user_id,
            "owner_ingress_origin": origin,
            "owner_ingress_enabled": enabled,
        }))
        self.options.chmod(0o600)

    def test_settings_enrollment_uses_only_local_approval_ipc_and_scrubs_options(self):
        secret = "synthetic-owner-password-123"
        self.write_options(secret, secret)
        with patch.object(settings.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=21001)), \
             patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear, \
             patch.dict(os.environ, {"SUPERVISOR_TOKEN": "synthetic-supervisor-token"}):
            rpc = rpc_type.return_value
            rpc.enrollment_status.return_value = {"enrolled": False}
            rpc.enroll.return_value = {"enrolled": True}
            captured = StringIO()
            with redirect_stderr(captured):
                self.assertEqual(settings.main(), 0)
            rpc_type.assert_called_once_with(settings.SOCKET, 21001)
            rpc.enroll.assert_called_once_with(secret, secret, "CADASTRAR")
            clear.assert_called_once_with("synthetic-supervisor-token")
            self.assertNotIn(secret, captured.getvalue())

    def test_already_enrolled_clears_stale_temporary_fields_without_reenrolling(self):
        self.write_options("synthetic-owner-password-123", "synthetic-owner-password-123")
        with patch.object(settings.pwd, "getpwnam", return_value=SimpleNamespace(pw_uid=21001)), \
             patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear:
            rpc_type.return_value.enrollment_status.return_value = {"enrolled": True}
            self.assertEqual(settings.main(), 0)
            rpc_type.return_value.enroll.assert_not_called()
            clear.assert_called_once()

    def test_invalid_or_mismatched_password_never_reaches_ipc(self):
        self.write_options("short", "short")
        with patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear:
            with self.assertRaisesRegex(PublicationError, "owner_settings_password_invalid"):
                settings.main()
            rpc_type.assert_not_called()
            clear.assert_not_called()
        self.write_options("synthetic-owner-password-123", "different-synthetic-password")
        with patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear:
            with self.assertRaisesRegex(PublicationError, "owner_settings_password_invalid"):
                settings.main()
            rpc_type.assert_not_called()
            clear.assert_not_called()

    def test_identity_settings_must_be_complete_before_enrollment(self):
        self.write_options("synthetic-owner-password-123", "synthetic-owner-password-123", enabled=False)
        with patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear:
            with self.assertRaisesRegex(PublicationError, "owner_settings_identity_incomplete"):
                settings.main()
            rpc_type.assert_not_called()
            clear.assert_not_called()

    def test_empty_fields_are_noop(self):
        self.write_options()
        with patch.object(settings, "ApprovalRPCClient") as rpc_type, \
             patch.object(settings, "clear_temporary_options") as clear:
            self.assertEqual(settings.main(), 0)
            rpc_type.assert_not_called()
            clear.assert_not_called()

    def test_supervisor_scrub_updates_only_temporary_password_fields(self):
        seen = {}
        def fake_urlopen(request, timeout):
            seen["url"] = request.full_url
            seen["method"] = request.get_method()
            seen["payload"] = json.loads(request.data.decode("utf-8"))
            seen["auth"] = request.get_header("Authorization")
            seen["timeout"] = timeout
            return Response()
        with patch.object(settings.urllib.request, "urlopen", side_effect=fake_urlopen):
            settings.clear_temporary_options("synthetic-supervisor-token")
        self.assertEqual(seen["url"], "http://supervisor/addons/self/options")
        self.assertEqual(seen["method"], "POST")
        self.assertEqual(seen["payload"], {"options": {
            "owner_password": "", "owner_password_confirm": "",
        }})
        self.assertEqual(seen["auth"], "Bearer synthetic-supervisor-token")
        self.assertEqual(seen["timeout"], 8)

    def test_supervisor_scrub_failure_is_safe(self):
        with patch.object(settings.urllib.request, "urlopen", side_effect=OSError("private detail")):
            with self.assertRaisesRegex(PublicationError, "supervisor_options_clear_failed"):
                settings.clear_temporary_options("synthetic-supervisor-token")

if __name__ == "__main__":
    unittest.main()
