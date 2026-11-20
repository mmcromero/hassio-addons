"""Offline verification of the official dual Artesao builder output.

Only for the external disposable executor. No Docker, extraction, install or
publication. Matching JSON is evidence, never proof of builder/approver identity.
"""
from pathlib import Path
from artesao_isolated_executor import (ExecutorBlocked, SAFE_VERSION, SHA,
    _json_file, _sha, verify_receipt, verify_sums, verify_package_release)
from release_receipt import safe_directory, digest


def verify_builder_artifacts(output, source_sha, version):
    output = safe_directory(output)
    if not SHA.fullmatch(source_sha) or not SAFE_VERSION.fullmatch(version):
        raise ExecutorBlocked('INVALID_ARTESAO_BINDING')
    if (output / 'INCOMPLETE-NOT-FOR-PUBLICATION').exists():
        raise ExecutorBlocked('INCOMPLETE_BUILD')
    # Refuse every filesystem alias before opening nested evidence or archives.
    for path in output.rglob('*'):
        if path.is_symlink() or (path.is_file() and path.stat().st_nlink != 1):
            raise ExecutorBlocked('BUILD_ALIAS_REJECTED')
    report = _json_file(output / 'FACTORY_ARTESAO_BUILD_REPORT.json')
    if (report.get('format') != 'factory-runner-artesao-isolated-builder-v1'
            or report.get('state') != 'PREPARED_LOCAL_ONLY'
            or report.get('source_sha') != source_sha or report.get('version') != version
            or report.get('published') is not False):
        raise ExecutorBlocked('BUILD_REPORT_BINDING_MISMATCH')
    evidence = verify_receipt(output / 'validation.json', source_sha)
    validation = _json_file(output / 'validation.json')
    if report.get('receipt_sha256') != evidence['sha256']:
        raise ExecutorBlocked('BUILD_RECEIPT_HASH_MISMATCH')
    tracks = {}
    metadata = []
    for name, arch, folder, release_path, archive_name, distribution in (
        ('home_assistant', 'linux/arm64', 'home-assistant',
         'apps/artesaos-piloto/release.json',
         'artesao-digital-home-assistant-aarch64-' + version + '.tar.gz', 'home-assistant'),
        ('debian', 'linux/amd64', 'debian-final',
         'artesao-digital-debian/release.json',
         'artesao-digital-debian-' + version + '.tar.gz', 'debian')):
        root = output / folder
        release = verify_package_release(root / release_path, source_sha, version, distribution)
        verify_sums((root / release_path).parent)
        verify_sums(root, require_complete=False)
        archive = root / archive_name
        if not archive.is_file():
            raise ExecutorBlocked('BUILD_ARCHIVE_MISSING')
        archive_sha = _sha(archive)
        track = report.get('tracks', {}).get(name, {})
        if (track.get('arch') != arch or track.get('state') != 'PREPARED_NOT_PUBLISHED'
                or track.get('archive_sha256') != archive_sha
                or release.get('validation') != validation):
            raise ExecutorBlocked('BUILD_TRACK_EVIDENCE_MISMATCH')
        if name == 'debian' and _sha((root / release_path).parent / 'image.tar') != release['imageArchiveSha256']:
            raise ExecutorBlocked('DEBIAN_IMAGE_HASH_MISMATCH')
        metadata.append(release)
        tracks[name] = {'architecture': arch, 'archive_sha256': archive_sha,
                        'release_sha256': _sha(root / release_path)}
    if (metadata[0].get('schemaChecksums') != metadata[1].get('schemaChecksums')
            or metadata[0].get('schemaVersions') != metadata[1].get('schemaVersions')):
        raise ExecutorBlocked('DUAL_SCHEMA_DIVERGENCE')
    receipt = {'format': 'factory-artesao-dual-artifacts-v1', 'source_sha': source_sha,
               'version': version, 'validation_sha256': evidence['sha256'], 'tracks': tracks,
               'state': 'VERIFIED_LOCAL_ARTIFACTS_NOT_PUBLISHED', 'published': False}
    return {**receipt, 'receipt_sha256': digest(receipt)}
