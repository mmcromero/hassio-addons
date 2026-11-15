"""Valida o pacote/PR; não cria, remove, integra ou publica refs.

Este check não é um bloqueio nativo à criação de branches. Para impedir merge,
a governança precisa cadastrá-lo como obrigatório nas proteções do GitHub.
"""
import argparse
from datetime import date, datetime
import json
from pathlib import Path
import re
import subprocess
from zoneinfo import ZoneInfo


def normalized_patch(value):
    lines = value.replace('\r\n', '\n').splitlines()
    # Git acrescenta um rótulo de contexto (ex.: "jobs:") após @@; difflib
    # não o faz. Preservar posições, linhas e conteúdo, ignorando só esse rótulo.
    lines = [re.sub(r'^(@@[^@]*@@).*$', r'\1', line) if line.startswith('@@') else line for line in lines]
    for index, line in enumerate(lines):
        if line.startswith('--- '):
            return '\n'.join(lines[index:]).strip()
    return ''


def validate(policy, repository, branch, base, paths=(), versions=None,
             existing_ci_diff=None, approved_ci_patch=None, today=None):
    errors = []
    if policy.get('schema_version') != 1:
        errors.append('Versão de política inválida.')
    limits = policy.get('limits', {})
    for key in ('active_core_packages', 'development_remote_branches_per_package',
                'distribution_remote_branches_per_package'):
        if limits.get(key) != 1:
            errors.append('O limite obrigatório é um: ' + key)
    package = policy.get('active_package', {})
    if package.get('status') != 'open':
        errors.append('Não há pacote aberto; registrar o próximo somente após o fechamento.')
    expected = package.get('branches', {}).get(repository)
    expected_version = package.get('candidate_version')
    if not expected:
        errors.append('Repositório fora do pacote registrado.')
    authorized = bool(expected and branch == expected)
    today = today or datetime.now(ZoneInfo(policy.get('timezone', 'America/Sao_Paulo'))).date()
    for exception in policy.get('emergency_exceptions', []):
        if exception.get('repository') != repository or exception.get('branch') != branch:
            continue
        try:
            valid_until = date.fromisoformat(exception['expires_on'])
        except (ValueError, KeyError):
            continue
        if (exception.get('status') == 'open' and exception.get('reason')
                and exception.get('authorization_reference') and exception.get('version') and valid_until >= today):
            authorized = True
            expected_version = exception['version']
    if not authorized:
        errors.append('Branch fora do pacote aberto. Usar a branch compartilhada: ' + str(expected))
    if base != package.get('base_branch', 'main'):
        errors.append('PR deve usar a base registrada do pacote.')
    if versions is not None:
        wanted = expected_version
        if versions.get('package') != wanted or versions.get('manifest') != wanted:
            errors.append('package.json/config.yaml não correspondem à RC registrada: ' + str(wanted))
    if repository == 'mmcromero/hassio-addons':
        scope = policy.get('public_scope', {})
        prefix = scope.get('prefix', 'pager-virtual/')
        allowed_root = set(scope.get('allowed_root_files', []))
        for path in paths:
            if not path.startswith(prefix) and path not in allowed_root:
                errors.append('Alteração fora do produto Avisaqui: ' + path)
        if '.github/workflows/validate-addons.yml' in paths:
            if (not approved_ci_patch or normalized_patch(existing_ci_diff or '')
                    != normalized_patch(approved_ci_patch)):
                errors.append('Workflow compartilhado difere do único patch de CI autorizado do Avisaqui.')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repository', required=True)
    parser.add_argument('--branch', required=True)
    parser.add_argument('--base', default='main')
    parser.add_argument('--base-sha', default='')
    parser.add_argument('--head-sha', default='HEAD')
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[1]
    policy = json.loads((project / '.governance/package-policy.json').read_text())
    repo_root = subprocess.check_output(['git', '-C', str(project), 'rev-parse', '--show-toplevel'], text=True).strip()

    def git(*options):
        return subprocess.check_output(['git', '-C', repo_root, *options], text=True)

    base = args.base_sha or 'origin/main'
    paths = git('diff', '--name-only', base, args.head_sha).splitlines()
    package = json.loads((project / 'package.json').read_text())
    version = re.search(r'''(?m)^version:\s*["']?([^"'\s#]+)''', (project / 'config.yaml').read_text())
    patch_path = project / policy['public_scope']['approved_existing_ci_patch']
    actual_patch = git('diff', base, args.head_sha, '--', '.github/workflows/validate-addons.yml')
    errors = validate(policy, args.repository, args.branch, args.base, paths,
                      {'package': package.get('version'), 'manifest': version[1] if version else None},
                      actual_patch, patch_path.read_text() if patch_path.exists() else None)
    if errors:
        for error in errors:
            print('ERRO: ' + error)
        return 1
    print('Política validada para o pacote ' + policy['active_package']['id'] + ': ' + args.branch)
    print('Check de PR; não equivale a proteção nativa, publicação ou autorização de merge.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
