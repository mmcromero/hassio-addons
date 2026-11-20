"""Runner-owned artifact receipts. No source scripts, network or Git writes.

The receipt is evidence, not authority. A publisher must bind its digest to an
independently approved grant. Callers own the directory exclusively while using it.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import time

from declarative_export import (safe_path, DeclarativeExportError, MAX_FILES,
                                MAX_FILE_BYTES, MAX_TOTAL_BYTES)

RECEIPT = 'RELEASE_RECEIPT.json'

class ReceiptError(Exception):
    pass


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      ensure_ascii=True, allow_nan=False).encode('ascii')


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def safe_directory(path):
    path = Path(path).absolute()
    if path.resolve() != path or not path.is_dir() or path.is_symlink():
        raise ReceiptError('unsafe_directory')
    return path


def inventory(root):
    """Exact file set, modes and hashes; refuse aliases, devices and .git."""
    root = safe_directory(root)
    records, total = [], 0
    started = time.monotonic()
    for parent, dirs, files in os.walk(root, followlinks=False):
        for name in dirs + files:
            target = Path(parent) / name
            relative = target.relative_to(root).as_posix()
            try:
                safe_path(relative)
            except DeclarativeExportError as exc:
                raise ReceiptError('unsafe_artifact_path') from exc
            info = target.lstat()
            if stat.S_ISDIR(info.st_mode):
                continue
            if (not stat.S_ISREG(info.st_mode) or info.st_nlink != 1
                    or info.st_size > MAX_FILE_BYTES):
                raise ReceiptError('unsafe_artifact_file')
            if relative == RECEIPT:
                continue
            total += info.st_size
            if (total > MAX_TOTAL_BYTES or len(records) >= MAX_FILES
                    or time.monotonic() - started > 240):
                raise ReceiptError('artifact_budget_exceeded')
            records.append({'path': relative, 'size': info.st_size,
                            'mode': '100755' if info.st_mode & 0o111 else '100644',
                            'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    if not records:
        raise ReceiptError('empty_artifact')
    return sorted(records, key=lambda item: item['path'])


def read_receipt(root):
    root = safe_directory(root)
    path = root / RECEIPT
    if (path.is_symlink() or not path.is_file() or path.stat().st_nlink != 1
            or path.stat().st_size > 2 * 1024 * 1024):
        raise ReceiptError('receipt_unavailable')
    try:
        result = json.loads(path.read_bytes())
    except (ValueError, UnicodeError) as exc:
        raise ReceiptError('invalid_receipt') from exc
    if not isinstance(result, dict) or result.get('format') != 'factory-release-receipt-v1':
        raise ReceiptError('invalid_receipt')
    return result


def verify_receipt(root, expected_digest=None):
    receipt = read_receipt(root)
    if expected_digest is not None and digest(receipt) != expected_digest:
        raise ReceiptError('receipt_digest_mismatch')
    if receipt.get('files') != inventory(root):
        raise ReceiptError('artifact_integrity_mismatch')
    return receipt


def seal_receipt(root, *, profile, report, tests=None):
    """Seal trusted preparation output; test results remain PENDING by default."""
    root = safe_directory(root)
    if report.get('eligible_for_preparation') is not True or report.get('errors'):
        raise ReceiptError('preparation_policy_blocked')
    files = inventory(root)
    # Metadata belongs only to the local bundle, never to public add-on files.
    artifacts = [item['path'] for item in files
                 if item['path'] != 'DECLARATIVE_BUNDLE_MANIFEST.json']
    prefix = profile['distribution_prefix']
    if any(not path.startswith(prefix) and path not in profile['allowed_shared_paths']
           for path in artifacts):
        raise ReceiptError('artifact_outside_project_scope')
    receipt = {'format': 'factory-release-receipt-v1',
               'project': profile['id'], 'source_repository': profile['source_repo'],
               'source_ref': profile['source_ref'],
               'source_sha': report['source_sha'],
               'distribution_repository': profile['distribution_repo'],
               'distribution_ref': profile['public_ref'].replace('refs/remotes/origin/', 'refs/heads/'),
               'expected_distribution_sha': report['public_main_sha'],
               'package_id': report['package_id'], 'version': report['candidate_version'],
               'profile_sha256': digest(profile), 'scope': prefix,
               'allowed_shared_paths': profile['allowed_shared_paths'],
               'files': files, 'artifacts': artifacts,
               'tests': tests or {'status': 'PENDING', 'checks': []},
               'created_at': int(time.time()), 'state': 'PREPARED_NOT_PUBLISHED'}
    with (root / RECEIPT).open('x', encoding='ascii') as stream:
        stream.write(canonical(receipt).decode() + '\n')
    verify_receipt(root)
    return receipt
