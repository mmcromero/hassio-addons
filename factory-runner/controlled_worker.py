#!/usr/bin/env python3
"""Factory Runner: worker filho para verificacoes confiaveis e SOMENTE LEITURA.

Nao executa scripts, testes, exportadores nem comandos fornecidos pelo cliente.
Nao e sandbox para codigo nao confiavel. Invocado apenas pelo servidor local.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import resource
import sys

PROJECT_ID = re.compile(r"^[a-z][a-z0-9_-]{1,47}$")
SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_RESULT = 16 * 1024
# Python -I remove a pasta do script; esta origem e parte da imagem imutavel.
sys.path.insert(0, str(Path(__file__).resolve().parent))


class WorkerBlocked(Exception):
    pass


def restrict_process():
    """Limites por processo, NAO quotas agregadas de grupo/cgroup."""
    if os.geteuid() == 0:
        raise WorkerBlocked("refusing_root")
    for key, ceiling in (
        (resource.RLIMIT_CPU, 12),
        (resource.RLIMIT_AS, 512 * 1024 * 1024),
        (resource.RLIMIT_FSIZE, 1024 * 1024),
        (resource.RLIMIT_NOFILE, 96),
        (resource.RLIMIT_CORE, 0),
    ):
        _, hard = resource.getrlimit(key)
        actual = ceiling if hard == resource.RLIM_INFINITY else min(hard, ceiling)
        resource.setrlimit(key, (actual, actual))


def security_diagnostic():
    """Ler somente campos conhecidos de /proc; nenhum segredo ou dado do host."""
    try:
        profile = Path('/proc/self/attr/current').read_text(encoding='utf-8').strip()
    except OSError:
        profile = 'unavailable'
    profile = re.sub(r'[^A-Za-z0-9_.:/() -]', '?', profile)[:120]
    fields = {}
    try:
        for line in Path('/proc/self/status').read_text(encoding='utf-8').splitlines():
            key, _, value = line.partition(':')
            if key in ('NoNewPrivs', 'Seccomp', 'CapEff', 'CapBnd'):
                value = value.strip()
                if re.fullmatch(r'[0-9a-fA-F]{1,20}', value):
                    fields[key] = value
    except OSError:
        pass
    from landlock_probe import landlock_status
    return {'mode': 'diagnostic_only', 'uid': os.geteuid(),
            'apparmor': profile, 'security_flags': fields,
            'landlock': landlock_status(),
            'bubblewrap_available': 'not_tested', 'sandbox_ready': False}


def profile_audit(project):
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise WorkerBlocked('invalid_project')
    from rc_fastlane import load_profile
    root = Path(os.environ.get('RUNNER_PROJECTS_DIR', '/app/projects'))
    profile_path = root / (project + '.json')
    if profile_path.is_symlink() or not profile_path.is_file():
        raise WorkerBlocked('profile_unavailable')
    profile = load_profile(profile_path)
    if profile.get('id') != project:
        raise WorkerBlocked('profile_mismatch')
    digest = hashlib.sha256(profile_path.read_bytes()).hexdigest()
    return {'mode': 'read_only', 'project': project,
            'product': profile['product'], 'source_repo': profile['source_repo'],
            'distribution_repo': profile['distribution_repo'],
            'profile_sha256': digest, 'scripts_executed': False,
            'publication': False}


def read_only_preflight(project, expected_sha):
    if not isinstance(project, str) or not PROJECT_ID.fullmatch(project):
        raise WorkerBlocked('invalid_project')
    if not isinstance(expected_sha, str) or not SHA.fullmatch(expected_sha):
        raise WorkerBlocked('invalid_sha')
    from server import preflight_project
    report = preflight_project(project, expected_sha)
    if not isinstance(report, dict) or report.get('mode') != 'read_only':
        raise WorkerBlocked('unsafe_preflight_result')
    return report


def execute(task, project=None, expected_sha=None):
    if task == 'diagnose' and project is None and expected_sha is None:
        return security_diagnostic()
    if task == 'profile' and project is not None and expected_sha is None:
        return profile_audit(project)
    if task == 'preflight' and project is not None and expected_sha is not None:
        return read_only_preflight(project, expected_sha)
    raise WorkerBlocked('task_not_allowed')


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--task', required=True, choices=('diagnose', 'profile', 'preflight'))
    parser.add_argument('--project')
    parser.add_argument('--sha')
    args = parser.parse_args(argv)
    try:
        restrict_process()
        result = execute(args.task, args.project, args.sha)
        payload = {'worker': 'factory-runner-controlled', 'task': args.task,
                   'ok': True, 'result': result}
        encoded = json.dumps(payload, ensure_ascii=True, separators=(',', ':'))
        if len(encoded.encode('utf-8')) > MAX_RESULT:
            raise WorkerBlocked('result_too_large')
        print(encoded, flush=True)
        return 0
    except (WorkerBlocked, OSError, ValueError, RuntimeError, KeyError, TypeError):
        print('{"worker":"factory-runner-controlled","ok":false,"error":"unavailable"}', flush=True)
        return 3


if __name__ == '__main__':
    sys.exit(main())
