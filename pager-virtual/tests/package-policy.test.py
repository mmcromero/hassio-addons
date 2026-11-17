from datetime import date
import importlib.util
import json
from pathlib import Path
import sys
import unittest

sys.dont_write_bytecode = True
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

    def shared_baseline(self):
        # Fixture da capacidade do validador. Uma RC nova não deve herdar
        # exceções de arquivos compartilhados de um pacote já encerrado.
        baseline = {'repository': self.public, 'commit': '1' * 40,
                    'authorization_reference': 'fixture de autorização explícita',
                    'files': {'.github/addon-registry.json': 'a' * 64,
                              '.github/workflows/validate-addons.yml': 'b' * 64}}
        self.policy['public_scope']['preserved_shared_baseline'] = baseline
        return baseline

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
        # Compatibilidade com políticas anteriores sem baseline compartilhada.
        self.policy['public_scope'].pop('preserved_shared_baseline', None)
        patch = (ROOT / '.governance/approved-pager-ci.patch').read_text()
        options = {'paths': ['.github/workflows/validate-addons.yml'], 'approved_ci_patch': patch}
        self.assertEqual(self.check(self.public, existing_ci_diff='diff --git a/b a/b\nindex 123..456\n' + patch, **options), [])
        git_style = '\n'.join(line + ' jobs:' if line.startswith('@@') else line for line in patch.splitlines())
        self.assertEqual(self.check(self.public, existing_ci_diff=git_style, **options), [])
        self.assertTrue(self.check(self.public, existing_ci_diff=patch.replace("'22'", "'24'"), **options))

    def test_preserved_shared_files_require_exact_content(self):
        files = self.shared_baseline()['files']
        self.assertEqual(self.check(self.public, paths=list(files), shared_file_hashes=files), [])
        for path in files:
            changed = dict(files, **{path: '0' * 64})
            self.assertTrue(self.check(self.public, paths=list(files), shared_file_hashes=changed))

    def test_missing_shared_file_or_missing_hash_fails_closed(self):
        files = self.shared_baseline()['files']
        for path in files:
            missing = {key: value for key, value in files.items() if key != path}
            self.assertTrue(self.check(self.public, paths=list(files), shared_file_hashes=missing))
        self.assertTrue(self.check(self.public, paths=list(files)))

    def test_shared_baseline_does_not_allow_new_paths_or_other_products(self):
        files = self.shared_baseline()['files']
        for path in ['.github/scripts/outro.py', 'docs/outro.md', 'evolution-api/config.yaml']:
            self.assertTrue(self.check(self.public, paths=[*files, path], shared_file_hashes=files))

    def test_shared_baseline_requires_traceable_authorization(self):
        baseline = self.shared_baseline()
        files = baseline['files']
        for key in ['repository', 'commit', 'authorization_reference']:
            value = baseline[key]
            baseline[key] = ''
            self.assertTrue(self.check(self.public, paths=list(files), shared_file_hashes=files))
            baseline[key] = value

    def test_historical_patch_cannot_hide_modified_preserved_workflow(self):
        self.shared_baseline()
        patch = (ROOT / '.governance/approved-pager-ci.patch').read_text()
        self.assertTrue(self.check(self.public, paths=['.github/workflows/validate-addons.yml'],
                                   existing_ci_diff=patch, approved_ci_patch=patch,
                                   shared_file_hashes={'.github/workflows/validate-addons.yml': '0' * 64}))

    def test_versions_must_match_active_package(self):
        version = self.policy['active_package']['candidate_version']
        self.assertEqual(self.check(versions={'package': version, 'manifest': version}), [])
        self.assertTrue(self.check(versions={'package': version, 'manifest': '0.1.17'}))


if __name__ == '__main__':
    unittest.main()
