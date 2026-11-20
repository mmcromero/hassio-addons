"""Real loopback HTTP + temporary Git repositories; no remote network or push."""
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch
from http.server import ThreadingHTTPServer

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import rc_fastlane as lane
spec = importlib.util.spec_from_file_location("integration_server", ROOT / "server.py")
server = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server)

EXPORTER = '''import argparse, hashlib, json, os
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--commit');p.add_argument('--target');p.add_argument('--verify',action='store_true');a=p.parse_args()
assert not any(os.environ.get(k) for k in ('RUNNER_AUTH_TOKEN','GH_TOKEN','GITHUB_TOKEN','PYTHONPATH','SECRET_FIXTURE'))
assert Path(os.environ['HOME']).is_dir()
folder=Path(a.target)/'demo';body=b'synthetic package\\n'
manifest={'commit':a.commit,'version':'1.2.3-rc.2','files':{'payload.txt':hashlib.sha256(body).hexdigest()}}
if a.verify:
 assert (folder/'payload.txt').read_bytes()==body
 assert json.loads((folder/'SOURCE_PROVENANCE.json').read_text())==manifest
else:
 folder.mkdir(exist_ok=True);(folder/'payload.txt').write_bytes(body)
 (folder/'SOURCE_PROVENANCE.json').write_text(json.dumps(manifest))
'''

class IntegrationTests(unittest.TestCase):
    def git(self, repo, *args):
        return subprocess.check_output(['git', '-C', str(repo), *args],
            env=lane.local_environment(), text=True, stderr=subprocess.DEVNULL).strip()

    def init_repo(self, path):
        path.mkdir(parents=True)
        self.git(path, 'init', '-q', '-b', 'main')
        self.git(path, 'config', 'user.name', 'Synthetic Fixture')
        self.git(path, 'config', 'user.email', 'fixture@example.invalid')

    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.root = Path(folder.name)
        self.workspace = self.root / 'workspaces' / 'laboratorio'
        self.source, self.dist = self.workspace/'source', self.workspace/'distribution'
        self.init_repo(self.source); self.init_repo(self.dist)
        self.profile = dict(schema_version=1, id='laboratorio', product='Laboratorio',
            source_repo='fixture/source', distribution_repo='fixture/distribution',
            source_ref='refs/remotes/origin/desenvolvimento',
            rc_ref='refs/remotes/origin/release/rc', public_ref='refs/remotes/origin/main',
            package_policy_path='policy.json', package_json_path='package.json',
            manifest_path='config.yaml', provenance_path='demo/SOURCE_PROVENANCE.json',
            distribution_prefix='demo/', exporter_path='scripts/export.py',
            allowed_shared_paths=[])
        (self.source/'scripts').mkdir()
        (self.source/'scripts/export.py').write_text(EXPORTER)
        policy = {'schema_version':1, 'product':'Laboratorio', 'active_package':{
            'status':'open','id':'FIXTURE','candidate_version':'1.2.3-rc.2',
            'branches':{'fixture/source':'release/rc'}}}
        (self.source/'policy.json').write_text(json.dumps(policy))
        (self.source/'package.json').write_text(json.dumps({'version':'1.2.3-rc.2'}))
        (self.source/'config.yaml').write_text('version: "1.2.3-rc.2"\n')
        self.git(self.source,'add','.');self.git(self.source,'commit','-qm','fixture')
        self.sha=self.git(self.source,'rev-parse','HEAD')
        for ref in ('source_ref','rc_ref'):
            self.git(self.source,'update-ref',self.profile[ref],self.sha)
        self.profile['exporter_git_blob_sha']=self.git(self.source,'rev-parse','HEAD:scripts/export.py')
        (self.dist/'demo').mkdir()
        (self.dist/'demo/SOURCE_PROVENANCE.json').write_text(json.dumps({
            'commit':'1'*40,'version':'1.2.3-rc.1'}))
        (self.dist/'sentinel.txt').write_text('must remain unchanged')
        self.git(self.dist,'add','.');self.git(self.dist,'commit','-qm','distribution fixture')
        self.git(self.dist,'update-ref',self.profile['public_ref'],self.git(self.dist,'rev-parse','HEAD'))
        self.projects=self.root/'projects';self.projects.mkdir()
        (self.projects/'laboratorio.json').write_text(json.dumps(self.profile))
        self.preparations=self.root/'preparations'
        self.audit=self.root/'audit.jsonl'
        env=patch.dict(os.environ,{'RUNNER_AUTH_TOKEN':'t'*40,'GH_TOKEN':'synthetic-secret',
                                 'SECRET_FIXTURE':'synthetic-secret'})
        env.start();self.addCleanup(env.stop)
        for name,value in [('PROJECTS_DIR',self.projects),('WORKSPACES_DIR',self.workspace.parent),
                           ('PREPARATIONS_DIR',self.preparations),('AUDIT_PATH',self.audit)]:
            context=patch.object(server,name,value);context.start();self.addCleanup(context.stop)
        self.http=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        thread=threading.Thread(target=self.http.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)

    def request(self, method, path, auth=True, payload=None):
        # Real clones/export under user-mode QEMU exceed the old 10 s harness
        # deadline. Keep a bounded client wait; production limits are unchanged.
        conn=http.client.HTTPConnection('127.0.0.1',self.http.server_port,
                                        timeout=60 if path=='/api/prepare' else 10)
        headers={'Content-Type':'application/json'}
        if auth: headers['Authorization']='Bearer '+'t'*40
        body=payload or {'project':'laboratorio','expected_source_sha':self.sha}
        try:
            conn.request(method,path,body=json.dumps(body) if method=='POST' else None,headers=headers)
            response=conn.getresponse();return response.status,json.loads(response.read())
        finally:
            conn.close()
            # The response body may arrive before Handler's finally releases
            # its operation lock. Serialize fixture requests, not product work.
            if not server.LOCK.acquire(timeout=60):
                self.fail('HTTP fixture cleanup did not release operation lock')
            server.LOCK.release()

    @staticmethod
    def trusted_fixture_export(*, source, target, script, sha, verify, env, **budget):
        """Test only: run a synthetic fixture; NOT a sandbox security proof."""
        argv = [sys.executable, "-I", str(Path(source) / script),
                "--commit", sha, "--target", str(target)]
        if verify:
            argv.append("--verify")
        subprocess.run(argv, cwd=source, env=env, check=True,
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=budget["elapsed_seconds"])

    def test_real_http_git_prepare_is_local_verified_and_does_not_push(self):
        initial={str(r):(self.git(r,'show-ref'),self.git(r,'status','--porcelain')) for r in (self.source,self.dist)}
        for method,path in [('GET','/api/status'),('GET','/api/projects'),
                            ('POST','/api/preflight'),('POST','/api/prepare')]:
            self.assertEqual(self.request(method,path,auth=False)[0],401)
        self.assertEqual(self.request('GET','/api/status')[1]['publication'],'disabled')
        self.assertEqual(self.request('GET','/api/projects')[1]['projects'][0]['id'],'laboratorio')
        code,data=self.request('POST','/api/preflight')
        self.assertEqual(code,200);self.assertTrue(data['result']['eligible_for_preparation'])
        # Functional HTTP/Git coverage. The real sandbox has separate tests.
        with patch.object(lane, 'sandbox_export', side_effect=self.trusted_fixture_export):
            code,data=self.request('POST','/api/prepare')
        self.assertEqual(code,200,data);self.assertFalse(data['result']['published'])
        self.assertEqual(data['result']['state'],'PREPARED_NOT_PUBLISHED')
        reports=list(self.preparations.glob('*.report.json'));self.assertEqual(len(reports),1)
        prepared=json.loads(reports[0].read_text());self.assertTrue(prepared['export_verified'])
        checkout=reports[0].with_name(reports[0].name.removesuffix('.report.json'))
        provenance=json.loads((checkout/'demo/SOURCE_PROVENANCE.json').read_text())
        self.assertEqual(provenance['commit'],self.sha)
        self.assertEqual(provenance['files']['payload.txt'],hashlib.sha256((checkout/'demo/payload.txt').read_bytes()).hexdigest())
        self.assertEqual((checkout/'sentinel.txt').read_text(),'must remain unchanged')
        for repo in (self.source,self.dist):
            self.assertEqual(initial[str(repo)],(self.git(repo,'show-ref'),self.git(repo,'status','--porcelain')))
        for path in server.OPERATIONS:
            self.assertEqual(self.request('POST',path,payload={'issue':2})[0],403)
        audit=self.audit.read_text()
        self.assertNotIn('synthetic-secret',audit);self.assertNotIn('t'*40,audit)
        self.assertIn('completed_preparation',audit)

    def test_real_http_declarative_export_no_scripts_no_git_writes(self):
        # This test creates a local bundle, never commits or publishes it.
        profile = dict(self.profile)
        profile["declarative_mapping"] = {
            "demo/config.yaml": "config.yaml",
            "demo/package.json": "package.json"
        }
        (self.projects / "laboratorio.json").write_text(json.dumps(profile))
        before = {
            str(repo): (self.git(repo, 'show-ref'),
                        self.git(repo, 'status', '--porcelain'))
            for repo in (self.source, self.dist)
        }
        with patch.object(lane, "sandbox_export",
                          side_effect=AssertionError("untrusted script executed")):
            code, data = self.request('POST', '/api/prepare-declarative')
        self.assertEqual(code, 200, data)
        self.assertFalse(data['result']['published'])
        self.assertEqual(data['result']['method'], 'declarative_no_script')
        candidates = list(self.preparations.iterdir())
        self.assertEqual(len(candidates), 1)
        output = candidates[0]
        provenance = json.loads((output / 'DECLARATIVE_BUNDLE_MANIFEST.json').read_text())
        self.assertEqual(provenance['commit'], self.sha)
        self.assertEqual(len(provenance['files']), 2)
        for item in provenance['files']:
            path = output / item['path']
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),
                             item['sha256'])
        for repo in (self.source, self.dist):
            self.assertEqual(before[str(repo)],
                             (self.git(repo, 'show-ref'),
                              self.git(repo, 'status', '--porcelain')))
        self.assertNotIn('synthetic-secret', self.audit.read_text())
        self.assertIn('completed_preparation', self.audit.read_text())

    def test_declarative_rule_selection_via_actual_http(self):
        (self.source / "src" / "nested").mkdir(parents=True)
        (self.source / "src" / "nested" / "module.txt").write_text("synthetic")
        self.git(self.source, 'add', '.')
        self.git(self.source, 'commit', '-qm', 'new synthetic source tree')
        new_sha = self.git(self.source, 'rev-parse', 'HEAD')
        for ref in ('source_ref', 'rc_ref'):
            self.git(self.source, 'update-ref', self.profile[ref], new_sha)
        rules = {
            "required": {"demo/config.yaml": "config.yaml",
                         "demo/package.json": "package.json"},
            "optional": {},
            "include_prefixes": ["src/"],
            "include_suffixes": {}
        }
        profile = dict(self.profile, declarative_rules=rules)
        (self.projects / 'laboratorio.json').write_text(json.dumps(profile))
        code, data = self.request(
            'POST', '/api/prepare-declarative',
            payload={"project": "laboratorio", "expected_source_sha": new_sha})
        self.assertEqual(code, 200, data)
        self.assertEqual(data['result']['files'], 3)
        output = next(self.preparations.iterdir())
        self.assertEqual((output / 'demo/src/nested/module.txt').read_text(),
                         'synthetic')
        self.assertFalse(data['result']['published'])

    def test_standard_prepare_uses_approved_declarative_without_sandbox(self):
        # Same preflight/Git policy as the existing route, but deterministic
        # mappings do not execute source scripts or depend on Bubblewrap.
        cfg = dict(self.profile)
        cfg["declarative_mapping"] = {
            "demo/config.yaml": "config.yaml",
            "demo/package.json": "package.json"
        }
        (self.projects / "laboratorio.json").write_text(json.dumps(cfg))
        initial = {
            str(repo): (self.git(repo, "show-ref"),
                        self.git(repo, "status", "--porcelain"))
            for repo in (self.source, self.dist)
        }
        with patch.object(lane, "sandbox_export",
                          side_effect=AssertionError("legacy exporter executed")):
            code, data = self.request("POST", "/api/prepare")
        self.assertEqual(code, 200, data)
        self.assertEqual(data["result"]["method"], "declarative_no_script")
        self.assertEqual(data["result"]["state"], "PREPARED_NOT_PUBLISHED")
        self.assertFalse(data["result"]["published"])
        self.assertEqual(data['result']['tests'], 'PENDING')
        first_receipt = data['result']['receipt_sha256']
        code, again = self.request('POST', '/api/prepare')
        self.assertEqual(code, 200, again)
        self.assertTrue(again['result']['idempotent'])
        self.assertEqual(again['result']['receipt_sha256'], first_receipt)
        outputs = list(self.preparations.iterdir())
        self.assertEqual(len(outputs), 1)
        manifest = json.loads(
            (outputs[0] / "demo/SOURCE_PROVENANCE.json").read_text())
        self.assertEqual(manifest["commit"], self.sha)
        self.assertEqual(len(manifest["files"]), 2)
        for item in manifest["files"]:
            content = (outputs[0] / "demo" / item["path"]).read_bytes()
            self.assertEqual(hashlib.sha256(content).hexdigest(), item["sha256"])
        for repo in (self.source, self.dist):
            self.assertEqual(initial[str(repo)],
                             (self.git(repo, "show-ref"),
                              self.git(repo, "status", "--porcelain")))
        self.assertIn("completed_preparation", self.audit.read_text())

    def test_missing_real_checkouts_return_503(self):
        with patch.object(server,'WORKSPACES_DIR',self.root/'missing'):
            for path in ('/api/preflight','/api/prepare'):
                self.assertEqual(self.request('POST',path)[0],503)

    def test_actual_prepare_path_audits_unavailable_sandbox_as_503(self):
        with patch.object(lane,'sandbox_export',side_effect=server.SandboxUnavailable('user namespace unavailable')) as export:
            code,data=self.request('POST','/api/prepare')
        self.assertEqual(code,503,data);export.assert_called_once()
        self.assertIn('blocked_workspace_or_git',self.audit.read_text())
        self.assertNotIn('completed_preparation',self.audit.read_text())

    def test_preparations_symlink_is_rejected(self):
        self.preparations.symlink_to(self.projects,target_is_directory=True)
        self.assertEqual(self.request('POST','/api/prepare')[0],503)
        self.assertEqual(list(self.projects.iterdir()),[self.projects/'laboratorio.json'])

    def test_unapproved_exporter_is_blocked(self):
        report=lane.evaluate(self.source,self.dist,self.sha,profile=self.profile)
        wrong=dict(self.profile,exporter_git_blob_sha='f'*40)
        with self.assertRaisesRegex(lane.PreflightError,'Exporter SHA'):
            lane.prepare(self.source,self.dist,report,self.root/'blocked',profile=wrong)
        self.assertFalse((self.root/'blocked/demo/payload.txt').exists())

    def test_overlap_in_source_is_blocked(self):
        report=lane.evaluate(self.source,self.dist,self.sha,profile=self.profile)
        with self.assertRaisesRegex(lane.PreflightError,'inside source'):
            lane.prepare(self.source,self.dist,report,self.source/'output',profile=self.profile)

    def test_frozen_real_tree_and_nested_rc_ref(self):
        self.git(self.source,'commit','--allow-empty','-qm','freeze same tree')
        self.git(self.source,'update-ref',self.profile['rc_ref'],self.git(self.source,'rev-parse','HEAD'))
        (self.source/'next.txt').write_text('next package')
        self.git(self.source,'add','.');self.git(self.source,'commit','-qm','advance development')
        self.git(self.source,'update-ref',self.profile['source_ref'],self.git(self.source,'rev-parse','HEAD'))
        report=lane.evaluate(self.source,self.dist,self.sha,profile=self.profile)
        self.assertTrue(report['eligible_for_preparation'],report)
        self.assertIn('PRIVATE_RC_ALREADY_FROZEN_AT_SOURCE_TREE',report['warnings'])

    def test_git_environment_does_not_forward_credentials_or_home(self):
        with patch.object(lane.subprocess,'run',return_value=type('Result',(),{'returncode':0,'stdout':'ok'})()) as call:
            lane.git(self.source,'rev-parse','HEAD')
        env=call.call_args.kwargs['env']
        for key in ('RUNNER_AUTH_TOKEN','GH_TOKEN','SECRET_FIXTURE'):
            self.assertNotIn(key,env)
        self.assertEqual(env['HOME'],os.devnull)

if __name__=='__main__':
    unittest.main()
