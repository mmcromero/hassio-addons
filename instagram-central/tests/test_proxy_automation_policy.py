"""Regression tests for the generated Instagram Central reverse-proxy routes."""
import importlib.util
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "tools" / "generate_proxy.py"
spec = importlib.util.spec_from_file_location("central_proxy_generator", SOURCE)
generator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generator)


class AutomationPolicyProxyTests(unittest.TestCase):
    def setUp(self):
        self.config = generator.generate(
            "https://instagram.example.org:8443",
            "homeassistant",
            "45c28620-umdoislab-instagram",
        )

    def test_primary_policy_form_is_forwarded_as_post_only(self):
        block = self.config.split("location = /panel/automation/policy {", 1)[1].split("\n    }", 1)[0]
        self.assertIn("limit_except POST { deny all;", block)
        self.assertIn("proxy_pass http://45c28620-umdoislab-instagram:8099;", block)

    def test_account_scoped_policy_form_is_forwarded_as_post_only(self):
        marker = 'location ~ "^/accounts/[a-z][a-z0-9_-]{1,39}/panel/automation/policy$" {'
        self.assertIn(marker, self.config)
        block = self.config.split(marker, 1)[1].split("\n    }", 1)[0]
        self.assertIn("limit_except POST { deny all;", block)
        self.assertIn("proxy_pass http://45c28620-umdoislab-instagram:8099;", block)

    def test_distributed_proxy_file_has_real_lines_and_both_post_routes(self):
        distributed = (ROOT / "proxy" / "instagram.conf").read_text()
        self.assertNotIn(r"\n", distributed)
        self.assertNotIn(r"\n", self.config)
        for marker in (
            "location = /panel/automation/policy {",
            'location ~ "^/accounts/[a-z][a-z0-9_-]{1,39}/panel/automation/policy$" {',
        ):
            self.assertIn(marker, distributed)
            block = distributed.split(marker, 1)[1].split("\n    }", 1)[0]
            self.assertIn("limit_except POST { deny all;", block)
            self.assertIn("proxy_pass http://45c28620-umdoislab-instagram:8099;", block)

    def test_policy_route_is_not_opened_for_get(self):
        for marker in (
            "location = /panel/automation/policy {",
            'location ~ "^/accounts/[a-z][a-z0-9_-]{1,39}/panel/automation/policy$" {',
        ):
            block = self.config.split(marker, 1)[1].split("\n    }", 1)[0]
            self.assertNotIn("limit_except GET", block)


if __name__ == "__main__":
    unittest.main()
