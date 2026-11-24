"""Complete synthetic Git package -> receipt -> independent grant -> local CAS.
No service credentials, source script execution, network or real product writes.
"""
import copy
import hashlib
import hmac
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest
from types import SimpleNamespace
from unittest.mock import patch, Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server
import release_receipt as receipts
import local_publisher as publisher
import release_console
from rc_fastlane import evaluate


class ReleasePipelineTests(unittest.TestCase):
    def git(self, repo, *args):
        return publisher.LocalPublisher._git(repo, *args).decode().strip()

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name)
        self.state = self.root / 'private-state'; self.state.mkdir(mode=0o700)
        self.source = self.root / 'workspaces' / 'avisaqui' / 'source'
        self.dist = self.source.parent / 'distribution'
        for repo in (self.source, self.dist):
            repo.mkdir(parents=True)
            self.git(repo, 'init', '-q', '-b', 'main')
        self.profile = dict(schema_version=1, id='avisaqui', product='Avisaqui',
            source_repo='fixture/source', distribution_repo='fixture/distribution',
            source_ref='refs/remotes/origin/desenvolvimento',
            rc_ref='refs/remotes/origin/release-candidate', public_ref='refs/remotes/origin/main',
            package_policy_path='policy.json', package_json_path='package.json',
            manifest_path='config.yaml', provenance_path='demo/SOURCE_PROVENANCE.json',
            distribution_prefix='demo/', exporter_path='export.py', allowed_shared_paths=[],
            declarative_mapping={'demo/config.yaml':'config.yaml', 'demo/package.json':'package.json',
                                 'demo/run.sh':'run.sh'})
        self.policy = {'schema_version':1, 'product':'Avisaqui', 'active_package':{
            'status':'open','id':'SYNTHETIC-001','candidate_version':'1.2.3-rc.2',
            'branches':{'fixture/source':'release-candidate'}}}
        for name, text in {'policy.json':json.dumps(self.policy),
                           'package.json':'{"version":"1.2.3-rc.2"}',
                           'config.yaml':'version: "1.2.3-rc.2"\n',
                           'run.sh':'#!/bin/sh\necho fixture\n',
                           'export.py':'raise Exception("MUST NEVER EXECUTE")\n'}.items():
            (self.source/name).write_text(text)
        self.sha = self.commit(self.source)
        for ref in ('source_ref', 'rc_ref'):
            self.git(self.source, 'update-ref', self.profile[ref], self.sha)
        self.profile['exporter_git_blob_sha'] = self.git(self.source,'rev-parse',self.sha+':export.py')
        (self.dist/'demo').mkdir()
        (self.dist/'demo/SOURCE_PROVENANCE.json').write_text(json.dumps({'commit':'a'*40,'version':'1.2.3-rc.1'}))
        (self.dist/'demo/obsolete.txt').write_text('remove only approved scope')
        (self.dist/'sentinel.txt').write_text('other add-on must survive')
        self.base = self.commit(self.dist)
        self.git(self.dist, 'update-ref', self.profile['public_ref'], self.base)
        self.target = self.state / 'distribution.git'
        self.git(self.state,'clone','--bare','--no-hardlinks',str(self.dist),str(self.target))
        self.git(self.target,'remote','remove','origin')
        self.projects=self.root/'projects';self.projects.mkdir()
        self.save_profile()
        for key, value in [('PROJECTS_DIR',self.projects),('WORKSPACES_DIR',self.source.parent.parent),
                           ('PREPARATIONS_DIR',self.root/'preparations'),('AUDIT_PATH',self.root/'audit.jsonl')]:
            p=patch.object(server,key,value);p.start();self.addCleanup(p.stop)
        # Synthetic authority only. No production credential or secret is read.
        self.key=b'synthetic-independent-authority-key-0001'
        self.pub=publisher.LocalPublisher(self.state,authorities={'fixture-owner':self.key})
        self.addCleanup(self.pub.close)

    def commit(self, repo):
        self.git(repo,'add','.')
        self.git(repo,'commit','-qm','synthetic fixture')
        return self.git(repo,'rev-parse','HEAD')

    def save_profile(self):
        (self.projects/'avisaqui.json').write_text(json.dumps(self.profile))

    def prepare(self):
        result=server.prepare_project('avisaqui',self.sha,'synthetic-operation')
        self.assertTrue(result['eligible'])
        root=next((self.root/'preparations').iterdir())
        return root, result

    def ready(self):
        root, result=self.prepare()
        # This fixture records this test's real Git preflight, not product tests.
        receipt=receipts.verify_receipt(root,result['receipt_sha256'])
        self.assertTrue(evaluate(self.source,self.dist,self.sha,profile=self.profile)['eligible_for_preparation'])
        receipt['tests']={'status':'PASS','source_sha':self.sha,
                          'checks':[{'command':'synthetic Git preflight', 'exit_code':0,'passed':1}]}
        (root/receipts.RECEIPT).write_bytes(receipts.canonical(receipt))
        return root,receipt,self.grant(receipt)

    def grant(self,receipt,**changes):
        payload=publisher.grant_payload(receipt,issue=2,authority='fixture-owner',
                                      nonce='f'*32,expires_at=int(time.time())+600)
        payload.update(changes)
        return {'payload':payload,'signature':hmac.new(self.key,receipts.canonical(payload),hashlib.sha256).hexdigest()}

    def publish(self,root,receipt,grant,**kwargs):
        return self.pub.publish(root,receipts.digest(receipt),grant,self.target,issue=2,**kwargs)

    def test_end_to_end_local_cas_exact_scope_and_restart_idempotence(self):
        root,receipt,grant=self.ready()
        result=self.publish(root,receipt,grant)
        self.assertEqual(result['state'],'PUBLISHED_LOCAL_FIXTURE')
        self.assertEqual(self.git(self.target,'show','main:sentinel.txt'),'other add-on must survive')
        self.assertNotIn('obsolete.txt',self.git(self.target,'ls-tree','-r','--name-only','main'))
        self.assertEqual(self.git(self.target,'rev-list','--count','main'),'2')
        other=publisher.LocalPublisher(self.state,authorities={'fixture-owner':self.key})
        try:
            again=other.publish(root,receipts.digest(receipt),grant,self.target,issue=2)
            self.assertTrue(again['idempotent']);self.assertEqual(again['commit'],result['commit'])
        finally:other.close()
        self.assertEqual(self.git(self.dist,'rev-parse','HEAD'),self.base)
        self.assertEqual(self.git(self.source,'rev-parse','HEAD'),self.sha)

    def test_preparation_receipt_and_retry_do_not_duplicate_or_claim_tests(self):
        root,first=self.prepare()
        again=server.prepare_project('avisaqui',self.sha,'another-operation')
        self.assertTrue(again['idempotent'])
        self.assertEqual(first['receipt_sha256'],again['receipt_sha256'])
        self.assertEqual(again['tests'],'PENDING');self.assertFalse(again['published'])
        self.assertEqual(len(list(root.parent.iterdir())),1)

    def test_pending_tests_cannot_publish(self):
        root,result=self.prepare();receipt=receipts.verify_receipt(root)
        with self.assertRaisesRegex(publisher.PublishBlocked,'verified_tests_required'):
            self.publish(root,receipt,self.grant(receipt))

    def test_each_grant_binding_is_enforced(self):
        root,receipt,grant=self.ready()
        for key in publisher.BINDING + ('issue','action','receipt_sha256'):
            with self.subTest(key=key):
                with self.assertRaisesRegex(publisher.PublishBlocked,'grant_binding_mismatch'):
                    self.publish(root,receipt,self.grant(receipt,**{key:'wrong'}))
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)

    def test_bearer_whatsapp_and_owner_strings_are_not_grants(self):
        root,receipt,_=self.ready()
        for grant in ({'owner_approved':True},{'bearer':'t'*40},{'whatsapp':'approved'},'owner_approved',None):
            with self.subTest(grant=grant), self.assertRaises(publisher.PublishBlocked):
                self.publish(root,receipt,grant)

    def test_expired_and_excessively_long_grants(self):
        root,receipt,_=self.ready()
        for expiry in (int(time.time())-1,int(time.time())+90000):
            with self.assertRaisesRegex(publisher.PublishBlocked,'expired_or_invalid_grant'):
                self.publish(root,receipt,self.grant(receipt,expires_at=expiry))

    def test_revoked_grant(self):
        root,receipt,grant=self.ready();self.pub.revoke(grant['payload']['nonce'])
        with self.assertRaisesRegex(publisher.PublishBlocked,'grant_revoked'):
            self.publish(root,receipt,grant)

    def test_wrong_signature_and_untrusted_authority(self):
        root,receipt,grant=self.ready()
        for bad in ({**grant,'signature':'0'*64},self.grant(receipt,authority='api-bearer')):
            with self.assertRaisesRegex(publisher.PublishBlocked,'invalid_authority_signature'):
                self.publish(root,receipt,bad)

    def test_nonce_cannot_be_reused_for_another_approved_binding(self):
        root,receipt,grant=self.ready();self.publish(root,receipt,grant)
        modified=copy.deepcopy(receipt);modified['version']='1.2.3-rc.3'
        (root/receipts.RECEIPT).write_bytes(receipts.canonical(modified))
        with self.assertRaisesRegex(publisher.PublishBlocked,'grant_replay'):
            self.publish(root,modified,self.grant(modified))

    def test_tampered_and_missing_files(self):
        root,receipt,grant=self.ready();path=root/'demo/run.sh'
        path.write_text('tampered')
        with self.assertRaises( receipts.ReceiptError): self.publish(root,receipt,grant)
        path.unlink()
        with self.assertRaises(receipts.ReceiptError): self.publish(root,receipt,grant)

    def test_tampered_manifest_and_receipt(self):
        root,receipt,grant=self.ready()
        (root/'DECLARATIVE_BUNDLE_MANIFEST.json').write_text('{}')
        with self.assertRaises(receipts.ReceiptError):self.publish(root,receipt,grant)

    def test_missing_receipt(self):
        root,receipt,grant=self.ready();(root/receipts.RECEIPT).unlink()
        with self.assertRaises(receipts.ReceiptError):self.publish(root,receipt,grant)

    def test_symlink_hardlink_and_directory_alias_rejected(self):
        root,receipt,grant=self.ready();path=root/'demo/run.sh';body=path.read_bytes();path.unlink()
        path.symlink_to(self.source/'run.sh')
        with self.assertRaises(receipts.ReceiptError):self.publish(root,receipt,grant)
        path.unlink();os.link(self.source/'run.sh',path)
        with self.assertRaises(receipts.ReceiptError):self.publish(root,receipt,grant)
        path.unlink();path.write_bytes(body)
        alias=self.root/'alias';alias.symlink_to(root,target_is_directory=True)
        with self.assertRaises(receipts.ReceiptError):self.publish(alias,receipt,grant)

    def test_extra_file_and_path_traversal_rejected(self):
        root,receipt,grant=self.ready();(root/'extra.txt').write_text('unexpected')
        with self.assertRaises(receipts.ReceiptError):self.publish(root,receipt,grant)
        (root/'extra.txt').unlink()
        modified=copy.deepcopy(receipt);modified['artifacts'].append('../escape')
        (root/receipts.RECEIPT).write_bytes(receipts.canonical(modified))
        with self.assertRaises(Exception):self.publish(root,modified,self.grant(modified))

    def test_remote_conflict_never_rolls_back_another_writer(self):
        root,receipt,grant=self.ready()
        advanced=self.git(self.target,'commit-tree',self.git(self.target,'rev-parse','main^{tree}'),'-p',self.base)
        self.git(self.target,'update-ref','refs/heads/main',advanced,self.base)
        with self.assertRaisesRegex(publisher.PublishBlocked,'distribution_cas_conflict'):
            self.publish(root,receipt,grant)
        self.assertEqual(self.git(self.target,'rev-parse','main'),advanced)

    def test_cas_race_is_rejected(self):
        root,receipt,grant=self.ready();real=self.pub._git
        advanced=self.git(self.target,'commit-tree',self.git(self.target,'rev-parse','main^{tree}'),'-p',self.base)
        def race(target,*args,**kwargs):
            if args[0]=='update-ref':real(target,'update-ref','refs/heads/main',advanced,self.base)
            return real(target,*args,**kwargs)
        with patch.object(self.pub,'_git',side_effect=race),self.assertRaises(publisher.PublishBlocked):
            self.publish(root,receipt,grant)
        self.assertEqual(self.git(self.target,'rev-parse','main'),advanced)

    def test_post_cas_crash_reconciles_without_duplicate_commit(self):
        root,receipt,grant=self.ready()
        with patch.object(self.pub,'_verify_commit',side_effect=publisher.PublishBlocked('simulated_crash')):
            with self.assertRaises(publisher.PublishBlocked):self.publish(root,receipt,grant)
        committed=self.git(self.target,'rev-parse','main')
        result=self.publish(root,receipt,grant)
        self.assertTrue(result['idempotent']);self.assertEqual(result['commit'],committed)
        self.assertEqual(self.git(self.target,'rev-list','--count','main'),'2')

    def test_cancel_does_not_move_ref(self):
        root,receipt,grant=self.ready()
        with self.assertRaisesRegex(publisher.PublishBlocked,'operation_cancelled'):
            self.publish(root,receipt,grant,cancel=lambda:True)
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)

    def test_timeout_does_not_publish(self):
        root,receipt,grant=self.ready()
        with patch.object(publisher.subprocess,'run',side_effect=subprocess.TimeoutExpired('git',30)):
            with self.assertRaisesRegex(publisher.PublishBlocked,'git_timeout'):self.publish(root,receipt,grant)
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)

    def test_remote_transport_and_outside_target_rejected(self):
        root,receipt,grant=self.ready()
        self.git(self.target,'remote','add','production','https://example.invalid/never-used')
        with self.assertRaisesRegex(publisher.PublishBlocked,'remote_transport_disabled'):
            self.publish(root,receipt,grant)
        with self.assertRaisesRegex(publisher.PublishBlocked,'local_fixture_target_required'):
            self.pub.publish(root,receipts.digest(receipt),grant,self.dist,issue=2)

    def test_closed_package_and_reused_version_block_before_creating_bundle(self):
        self.policy['active_package']['status']='closed'
        (self.source/'policy.json').write_text(json.dumps(self.policy));sha=self.commit(self.source)
        self.git(self.source,'update-ref',self.profile['source_ref'],sha)
        result=server.prepare_project('avisaqui',sha,'closed')
        self.assertFalse(result['eligible']);self.assertIn('NO_OPEN_PACKAGE',result['errors'])
        self.assertFalse((self.root/'preparations').exists())

    def test_false_exporter_and_stale_sha_fail_closed(self):
        self.profile['exporter_git_blob_sha']='b'*40;self.save_profile()
        with self.assertRaisesRegex(Exception,'declarative_rules_not_approved'):
            self.prepare()
        self.profile['exporter_git_blob_sha']=self.git(self.source,'rev-parse',self.sha+':export.py');self.save_profile()
        (self.source/'new').write_text('new');advanced=self.commit(self.source)
        self.git(self.source,'update-ref',self.profile['source_ref'],advanced)
        # An ancestor RC at the pinned SHA is not a frozen identical-tree snapshot.
        result=server.prepare_project('avisaqui',self.sha,'stale')
        self.assertFalse(result['eligible'])

    def test_subprocess_environment_never_inherits_service_credentials(self):
        root,receipt,grant=self.ready();real=publisher.subprocess.run;seen=[]
        def inspect(*args,**kwargs):
            seen.append(kwargs['env']);return real(*args,**kwargs)
        with patch.dict(os.environ,{'GH_TOKEN':'synthetic','RUNNER_AUTH_TOKEN':'synthetic', 'AWS_SECRET_ACCESS_KEY':'synthetic'}):
            with patch.object(publisher.subprocess,'run',side_effect=inspect):
                self.publish(root,receipt,grant)
        self.assertTrue(seen)
        for env in seen:
            for key in ('GH_TOKEN','RUNNER_AUTH_TOKEN','AWS_SECRET_ACCESS_KEY'):self.assertNotIn(key,env)

    def test_console_and_audit_are_sanitized_and_publication_unavailable(self):
        import io
        stream=io.StringIO()
        with patch('sys.stdout',stream):
            self.assertEqual(release_console.main(['prepare','--project','avisaqui','--source-sha',self.sha]),0)
        result=json.loads(stream.getvalue());self.assertEqual(result['publication'],'disabled')
        self.assertNotIn(str(self.root),stream.getvalue())
        self.assertEqual(server.recent_operations()[0]['status'],'completed_preparation')
        with self.assertRaises(SystemExit):release_console.main(['publish'])

    def test_audit_symlink_refused_without_writing_target(self):
        victim=self.root/'victim';victim.write_text('unchanged')
        server.AUDIT_PATH.symlink_to(victim)
        with self.assertRaises(RuntimeError):server.record('/api/prepare',None,'requested','f'*36)
        self.assertEqual(victim.read_text(),'unchanged')

    def test_artifact_size_budget(self):
        root,receipt,grant=self.ready()
        with patch('release_receipt.MAX_TOTAL_BYTES',1):
            with self.assertRaisesRegex(receipts.ReceiptError,'artifact_budget_exceeded'):
                self.publish(root,receipt,grant)

    def test_executable_bit_preserved_and_verified(self):
        (self.source/'run.sh').chmod(0o755);self.sha=self.commit(self.source)
        for ref in ('source_ref','rc_ref'):self.git(self.source,'update-ref',self.profile[ref],self.sha)
        root,receipt,grant=self.ready()
        record=next(x for x in receipt['files'] if x['path']=='demo/run.sh')
        self.assertEqual(record['mode'],'100755')
        result=self.publish(root,receipt,grant)
        self.assertTrue(self.git(self.target,'ls-tree',result['commit'],'--','demo/run.sh').startswith('100755'))

    def test_cancelled_intent_retry_never_moves_ref(self):
        root,receipt,grant=self.ready();real=self.pub._git
        def fail_before_cas(target,*args,**kwargs):
            if args[0]=='update-ref':raise publisher.PublishBlocked('simulated_crash')
            return real(target,*args,**kwargs)
        with patch.object(self.pub,'_git',side_effect=fail_before_cas):
            with self.assertRaises(publisher.PublishBlocked):self.publish(root,receipt,grant)
        with self.assertRaisesRegex(publisher.PublishBlocked,'operation_cancelled'):
            self.publish(root,receipt,grant,cancel=lambda:True)
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)
        self.assertTrue(any(x['state']=='failed_no_automatic_rollback' for x in self.pub.status()))

    def test_interprocess_lock_blocks_second_preparer(self):
        destination=self.root/'preparations'
        with server.preparation_lock(destination):
            with self.assertRaisesRegex(receipts.ReceiptError,'preparation_busy'):self.prepare()
        self.assertFalse(destination.exists())
        self.prepare()

    def test_failed_stage_is_retained_and_retry_can_complete(self):
        with patch.object(server,'seal_receipt',side_effect=receipts.ReceiptError('synthetic_failure')):
            with self.assertRaises(receipts.ReceiptError):self.prepare()
        stages=list((self.root/'preparations').glob('*.incomplete-*'))
        self.assertEqual(len(stages),1)
        result=server.prepare_project('avisaqui',self.sha,'retry')
        self.assertTrue(result['eligible'])
        self.assertTrue(stages[0].is_dir())
        self.assertTrue(server.prepare_project('avisaqui',self.sha,'retry2')['idempotent'])

    def test_repeated_published_version_with_distinct_source_is_blocked(self):
        (self.dist/'demo/SOURCE_PROVENANCE.json').write_text(json.dumps({'commit':'a'*40,'version':'1.2.3-rc.2'}))
        current=self.commit(self.dist);self.git(self.dist,'update-ref',self.profile['public_ref'],current)
        result=server.prepare_project('avisaqui',self.sha,'reused')
        self.assertFalse(result['eligible'])
        self.assertIn('VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE',result['errors'])

    def test_audit_fifo_and_hardlink_refused(self):
        os.mkfifo(server.AUDIT_PATH)
        with self.assertRaises(RuntimeError):server.record('/api/prepare',None,'requested','f'*36)
        server.AUDIT_PATH.unlink()
        victim=self.root/'victim';victim.write_text('unchanged');os.link(victim,server.AUDIT_PATH)
        with self.assertRaises(RuntimeError):server.record('/api/prepare',None,'requested','f'*36)
        self.assertEqual(victim.read_text(),'unchanged')

    def test_exact_preview_includes_deletions_without_writes(self):
        root,receipt,grant=self.ready()
        preview=self.pub.preview(root,receipts.digest(receipt),self.target)
        self.assertIn({'path':'demo/obsolete.txt','change':'delete'},preview['changes'])
        self.assertTrue(all(x['path'].startswith('demo/') for x in preview['changes']))
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)
        self.assertEqual(self.pub.status(),[])

    def test_publication_deadline_cannot_be_bypassed(self):
        root,receipt,grant=self.ready()
        clock = SimpleNamespace(monotonic=Mock(side_effect=[0,241]), time=time.time)
        with patch.object(publisher,'time',clock):
            with self.assertRaisesRegex(publisher.PublishBlocked,'publication_time_budget_exceeded'):
                self.publish(root,receipt,grant)
        self.assertEqual(self.git(self.target,'rev-parse','main'),self.base)

    def test_sensitive_file_names_are_not_exportable(self):
        self.profile['declarative_mapping']['demo/.env']='.env'
        self.save_profile()
        with self.assertRaises(Exception):self.prepare()
        self.assertFalse((self.root/'preparations').exists())
