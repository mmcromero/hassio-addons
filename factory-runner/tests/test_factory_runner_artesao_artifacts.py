"""Synthetic official-format dual receipts; no real builds or authority claims."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from artesao_artifacts import verify_builder_artifacts
from artesao_isolated_executor import ExecutorBlocked, _sha


class DualArtifactTests(unittest.TestCase):
    sha='a'*40
    version='0.2.0-dev.29'

    def put(self,path,value):
        path=self.root/path;path.parent.mkdir(parents=True,exist_ok=True)
        path.write_text(json.dumps(value) if isinstance(value,dict) else value)
        return path

    def sums(self,folder):
        root=self.root/folder
        records=[_sha(p)+'  '+p.relative_to(root).as_posix() for p in sorted(root.rglob('*')) if p.is_file() and p.name!='SHA256SUMS']
        (root/'SHA256SUMS').write_text('\n'.join(records)+'\n')

    def setUp(self):
        tmp=tempfile.TemporaryDirectory();self.addCleanup(tmp.cleanup);self.root=Path(tmp.name)
        self.validation={'sourceCommit':self.sha,'status':'passed',
             'checks':[{'name':n,'status':'passed'} for n in ('build','application-tests','distribution-helper','operations')],
             'schemaChecksums':{scope:[{'name':scope,'version':1,'checksum':'c'*64}] for scope in ('tenant','control','interest','support','legal')},
             'physicalValidation':'not-performed'}
        validation_path=self.put('validation.json',self.validation)
        common={'sourceCommit':self.sha,'releaseVersion':self.version,'validation':self.validation,
                'schemaChecksums':self.validation['schemaChecksums'],'schemaVersions':{'tenant':1}}
        self.ha={**common,'distribution':'home-assistant','packageKind':'home-assistant-precompiled-aarch64',
                 'architecture':'linux/arm64','runtimeSourceCommit':self.sha,'addonSlug':'artesaos_piloto'}
        image=self.put('debian-final/artesao-digital-debian/image.tar','synthetic amd64 image bytes')
        self.debian={**common,'distribution':'debian','packageKind':'compose-with-image',
                     'imageArchitecture':'linux/amd64','imageSourceCommit':self.sha,'imageArchiveSha256':_sha(image)}
        self.put('home-assistant/apps/artesaos-piloto/runtime.tar.gz','synthetic arm64 image bytes')
        self.put('home-assistant/apps/artesaos-piloto/release.json',self.ha)
        self.put('debian-final/artesao-digital-debian/release.json',self.debian)
        ha_archive=self.put('home-assistant/artesao-digital-home-assistant-aarch64-'+self.version+'.tar.gz','synthetic HA archive')
        deb_archive=self.put('debian-final/artesao-digital-debian-'+self.version+'.tar.gz','synthetic Debian archive')
        self.report={'format':'factory-runner-artesao-isolated-builder-v1','state':'PREPARED_LOCAL_ONLY',
            'source_sha':self.sha,'version':self.version,'receipt_sha256':_sha(validation_path),'published':False,
            'tracks':{'home_assistant':{'state':'PREPARED_NOT_PUBLISHED','arch':'linux/arm64','archive_sha256':_sha(ha_archive)},
                      'debian':{'state':'PREPARED_NOT_PUBLISHED','arch':'linux/amd64','archive_sha256':_sha(deb_archive)}}}
        self.put('FACTORY_ARTESAO_BUILD_REPORT.json',self.report)
        self.refresh()

    def refresh(self):
        for folder in ('home-assistant/apps/artesaos-piloto','debian-final/artesao-digital-debian','home-assistant','debian-final'):
            self.sums(folder)

    def verify(self):return verify_builder_artifacts(self.root,self.sha,self.version)

    def test_distinct_ha_debian_evidence_verified_offline(self):
        receipt=self.verify()
        self.assertFalse(receipt['published'])
        self.assertEqual(receipt['tracks']['home_assistant']['architecture'],'linux/arm64')
        self.assertEqual(receipt['tracks']['debian']['architecture'],'linux/amd64')
        self.assertNotEqual(receipt['tracks']['home_assistant']['archive_sha256'],receipt['tracks']['debian']['archive_sha256'])

    def test_missing_track_never_uses_other_architecture(self):
        self.report['tracks'].pop('debian');self.put('FACTORY_ARTESAO_BUILD_REPORT.json',self.report)
        with self.assertRaisesRegex(ExecutorBlocked,'BUILD_TRACK_EVIDENCE'):self.verify()

    def test_wrong_architecture_rejected_even_with_matching_checksums(self):
        self.ha['architecture']='linux/amd64';self.put('home-assistant/apps/artesaos-piloto/release.json',self.ha);self.refresh()
        with self.assertRaisesRegex(ExecutorBlocked,'HA_RUNTIME_OR_ARCH'):self.verify()

    def test_receipt_source_and_archive_hash_tampering(self):
        self.validation['sourceCommit']='b'*40;self.put('validation.json',self.validation)
        with self.assertRaisesRegex(ExecutorBlocked,'RECEIPT_SOURCE'):self.verify()

    def test_archive_tampering_rejected_after_checksum_refresh(self):
        self.put('debian-final/artesao-digital-debian-'+self.version+'.tar.gz','tampered');self.refresh()
        with self.assertRaisesRegex(ExecutorBlocked,'BUILD_TRACK_EVIDENCE'):self.verify()

    def test_incomplete_marker_rejected(self):
        self.put('INCOMPLETE-NOT-FOR-PUBLICATION','partial')
        with self.assertRaisesRegex(ExecutorBlocked,'INCOMPLETE_BUILD'):self.verify()

    def test_symlink_parent_rejected(self):
        (self.root/'alias').symlink_to(self.root/'validation.json')
        with self.assertRaisesRegex(ExecutorBlocked,'BUILD_ALIAS'):self.verify()

    def test_dual_schema_disagreement_rejected(self):
        changed=copy.deepcopy(self.debian);changed['schemaVersions']={'tenant':2}
        self.put('debian-final/artesao-digital-debian/release.json',changed);self.refresh()
        with self.assertRaisesRegex(ExecutorBlocked,'DUAL_SCHEMA'):self.verify()

    def test_cli_module_identity_keeps_sanitized_exception_contract(self):
        import runpy
        from unittest.mock import patch
        namespace=runpy.run_path(str(Path(__file__).resolve().parents[1]/'artesao_isolated_executor.py'),run_name='isolated_cli_fixture')
        with patch('artesao_artifacts.verify_builder_artifacts',side_effect=ExecutorBlocked('private-detail')):
            with self.assertRaisesRegex(namespace['ExecutorBlocked'],'^DUAL_ARTIFACT_VERIFICATION_FAILED$'):
                namespace['verify_completed_builder'](self.root,self.sha,self.version)
