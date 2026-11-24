"""Tests for safe propagation of constant Approval IPC reason codes."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from approval_ipc import _safe_error_code
from publication_contract import PublicationError


class ApprovalIPCErrorTests(unittest.TestCase):
    def test_constant_publication_error_code_is_preserved(self):
        self.assertEqual(
            _safe_error_code(PublicationError("owner_key_generation_unavailable")),
            "owner_key_generation_unavailable",
        )

    def test_only_bounded_reason_codes_are_preserved(self):
        self.assertEqual(_safe_error_code("owner_enrollment_input_invalid"),
                         "owner_enrollment_input_invalid")
        self.assertEqual(_safe_error_code("password must not appear"),
                         "approval_request_denied")
        self.assertEqual(_safe_error_code(None), "approval_request_denied")
        self.assertEqual(_safe_error_code("A" * 100), "approval_request_denied")


if __name__ == "__main__":
    unittest.main()
