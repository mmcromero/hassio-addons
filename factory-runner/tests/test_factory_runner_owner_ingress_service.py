"""Tests for the owner ingress service's safe disabled mode."""
import unittest
from unittest.mock import patch
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import owner_ingress_service


class OwnerIngressServiceTests(unittest.TestCase):
    def test_disabled_mode_starts_only_status_service(self):
        with patch("owner_ingress_service.serve_owner_ingress_disabled") as serve:
            self.assertEqual(owner_ingress_service.main(["--disabled"]), 0)
            serve.assert_called_once_with(port=8099)

    def test_unknown_mode_is_rejected(self):
        self.assertEqual(owner_ingress_service.main(["--unexpected"]), 2)


if __name__ == "__main__":
    unittest.main()
