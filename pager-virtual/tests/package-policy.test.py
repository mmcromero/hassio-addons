from datetime import date
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('package_policy', ROOT / 'scripts/check-package-policy.py')
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class PackagePolicy(unittest.TestCase):
    def setUp(self):
        self.policy = json.loads((ROOT / '.governance/package-policy.json').read_text())
        self.private = 'mmcromero/pager-virtual'
        self.public = 'mmcromero/hassio-addons'

    def check(self, repository=None, branch=None, base='main', **options):
        repository = repository or self.private
        branch = branch or self.policy['active_package']['branches'][repository]
        return module.validate(self.policy, repository, branch, base, **options)

    def test_accepts_shared_rc(self):
        self.assertEqual(self.check(), [])
        self.assertEqual(self.check(self.public), [])

    def test_rejects_parallel_feature_and_factory_pr_to_main(self):
        for branch in ['feat/mais-uma-branch', 'feat/avisaqui-games-001-lote-1']:
            self.assertTrue(self.check(branch=branch))

    def test_rejects_closed_package_and_wrong_base(self):
        self.assertTrue(self.check(base='outra-branch'))
        self.policy['active_package']['status'] = 'closed'
        self.assertTrue(self.check())

    def test_cannot_raise_branch_limits_silently(self):
        self.policy['limits']['development_remote_branches_per_package'] = 3
        self.assertTrue(self.check())

    def test_exception_requires_approval_reason_and_expiration(self):
        exception = {'repository': self.private, 'branch': 'fix/emergencia', 'status': 'open',
                     'reason': 'Falha operacional', 'authorization_reference': 'aprovação-registrada',
                     'expires_on': '2026-11-16', 'version': '0.1.17'}
        self.policy['emergency_exceptions'] = [exception]
        self.assertEqual(self.check(branch='fix/emergencia', today=date(2026, 11, 15)), [])
        self.assertEqual(self.check(branch='fix/emergencia', today=date(2026, 11, 15),
                                   versions={'package': '0.1.17', 'manifest': '0.1.17'}), [])
        exception['authorization_reference'] = ''
        self.assertTrue(self.check(branch='fix/emergencia', today=date(2026, 11, 15)))

    def test_expired_or_closed_exception_is_rejected(self):
        self.policy['emergency_exceptions'] = [{'repository': self.private, 'branch': 'fix/emergencia',
            'status': 'open', 'reason': 'Falha', 'authorization_reference': 'aprovação',
            'expires_on': '2026-11-14', 'version': '0.1.17'}]
        self.assertTrue(self.check(branch='fix/emergencia', today=date(2026, 11, 15)))
        self.policy['emergency_exceptions'][0].update(status='closed', expires_on='2026-11-16')
        self.assertTrue(self.check(branch='fix/emergencia', today=date(2026, 11, 15)))

    def test_distribution_cannot_modify_other_products(self):
        self.assertEqual(self.check(self.public, paths=['pager-virtual/src/server.js']), [])
        self.assertTrue(self.check(self.public, paths=['evolution-api/config.yaml']))
        self.assertTrue(self.check(self.public, paths=['README.md']))

    def test_shared_workflow_requires_exact_approved_patch(self):
        patch = (ROOT / '.governance/approved-pager-ci.patch').read_text()
        options = {'paths': ['.github/workflows/validate-addons.yml'], 'approved_ci_patch': patch}
        self.assertEqual(self.check(self.public, existing_ci_diff='diff --git a/b a/b\nindex 123..456\n' + patch, **options), [])
        git_style = '\n'.join(line + ' jobs:' if line.startswith('@@') else line for line in patch.splitlines())
        self.assertEqual(self.check(self.public, existing_ci_diff=git_style, **options), [])
        self.assertTrue(self.check(self.public, existing_ci_diff=patch.replace("'22'", "'24'"), **options))

    def test_versions_must_match_active_package(self):
        version = self.policy['active_package']['candidate_version']
        self.assertEqual(self.check(versions={'package': version, 'manifest': version}), [])
        self.assertTrue(self.check(versions={'package': version, 'manifest': '0.1.17'}))


if __name__ == '__main__':
    unittest.main()
