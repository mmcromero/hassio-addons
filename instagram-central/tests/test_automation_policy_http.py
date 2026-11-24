"""Authenticated policy controls; synthetic loopback only."""
import unittest
from urllib.parse import urlencode

import test_http as contracts
import automation_policy

server = contracts.server


class AutomationPolicyHTTPTests(unittest.TestCase):
    def setUp(self):
        self.fixture = contracts.HTTPContractTests()
        self.fixture.setUp()
        self.addCleanup(self.fixture.tearDown)
        _, headers, _ = self.fixture.request('/auth/login', 'POST', urlencode({
            'username': 'admin', 'password': self.fixture.config['panel_password']}),
            {'Content-Type': 'application/x-www-form-urlencoded'})
        self.cookie = headers['Set-Cookie'].split(';', 1)[0]
        self.headers = {'Cookie': self.cookie}

    def test_settings_show_automation_tab_and_default_to_tests(self):
        status, _, body = self.fixture.request('/panel?view=settings', headers=self.headers)
        self.assertEqual(status, 200)
        self.assertIn(b'data-ui-tab="automation"', body)
        self.assertIn(b'Somente testes', body)
        self.assertIn(b'name="mode" value="tests" checked', body)
        self.assertIn(b'data-automation-csrf', body)
        self.assertNotIn(b'name="mode" value="all" checked', body)

    def test_policy_save_requires_session_and_csrf(self):
        body = urlencode({'csrf': 'bad', 'mode': 'tests', 'test_ids': '12345678', 'excluded_ids': ''})
        self.assertEqual(self.fixture.request('/panel/automation/policy', 'POST', body,
            {'Content-Type': 'application/x-www-form-urlencoded'})[0], 403)
        self.assertEqual(self.fixture.request('/panel/automation/policy', 'POST', body,
            {'Content-Type': 'application/x-www-form-urlencoded', **self.headers})[0], 403)

    def test_save_policy_and_render_saved_profiles(self):
        csrf = server.panel_login.admin_csrf_token(
            self.cookie, self.fixture.config['panel_password'], 'automation')
        body = urlencode({'csrf': csrf, 'mode': 'tests',
                          'test_ids': '12345678', 'excluded_ids': '87654321'})
        status, headers, _ = self.fixture.request('/panel/automation/policy', 'POST', body,
            {'Content-Type': 'application/x-www-form-urlencoded', **self.headers})
        self.assertEqual(status, 303)
        self.assertIn('automation_result=saved', headers['Location'])
        with server.database() as db:
            saved = automation_policy.snapshot(db, self.fixture.config['instagram_account_id'])
        self.assertEqual(saved['mode'], 'tests')
        self.assertEqual(saved['test'], ['12345678'])
        self.assertEqual(saved['excluded'], ['87654321'])
        status, _, page = self.fixture.request('/panel?view=settings', headers=self.headers)
        self.assertEqual(status, 200)
        self.assertIn(b'12345678', page)
        self.assertIn(b'87654321', page)

    def test_invalid_profile_id_keeps_previous_policy(self):
        csrf = server.panel_login.admin_csrf_token(
            self.cookie, self.fixture.config['panel_password'], 'automation')
        first = urlencode({'csrf': csrf, 'mode': 'tests',
                           'test_ids': '12345678', 'excluded_ids': ''})
        self.assertEqual(self.fixture.request('/panel/automation/policy', 'POST', first,
            {'Content-Type': 'application/x-www-form-urlencoded', **self.headers})[0], 303)
        second = urlencode({'csrf': csrf, 'mode': 'all',
                            'test_ids': '@bad', 'excluded_ids': ''})
        status, headers, _ = self.fixture.request('/panel/automation/policy', 'POST', second,
            {'Content-Type': 'application/x-www-form-urlencoded', **self.headers})
        self.assertEqual(status, 303)
        self.assertIn('automation_result=invalid', headers['Location'])
        with server.database() as db:
            saved = automation_policy.snapshot(db, self.fixture.config['instagram_account_id'])
        self.assertEqual(saved['mode'], 'tests')
        self.assertEqual(saved['test'], ['12345678'])


if __name__ == '__main__':
    unittest.main()
