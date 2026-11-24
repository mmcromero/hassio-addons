"""M006: real Ed25519, owner reauthentication, Unix IPC, HTTP API and bare Git.
All credentials and repos are synthetic. No external network or project execution.
"""
import base64
import copy
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import threading
import time
import unittest
import urllib.parse
from http.server import BaseHTTPRequestHandler,HTTPServer
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import test_factory_runner_release_pipeline as fixture_module
from local_publisher import LocalPublisher
from publication_contract import ArtifactContract,PublicationError,git_oid
from owner_approval import ApprovalIssuer,GrantVerifier,password_digest,cryptographic_operation
from publication_workflow import PublicationWorkflow,disabled_gate,capabilities
from github_bytes_transport import GitHubBytesHTTP,GitHubBytesTransport,tree_oid
from approval_ipc import ApprovalRPCServer,ApprovalRPCClient
from owner_consent_ui import OwnerConsentUI
from release_receipt import digest,canonical
import rc_fastlane
import server


class GitHubFixture(BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def answer(self,body,code=200):
        raw=json.dumps(body).encode();self.send_response(code);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def cut(self):
        self.connection.shutdown(socket.SHUT_RDWR);self.connection.close()
    def git(self,*args,data=None):return LocalPublisher._git(self.server.repo,*args,data=data)
    def do_GET(self):self.process('GET')
    def do_POST(self):self.process('POST')
    def process(self,method):
        try:
            if self.headers.get('Authorization')!='Bearer synthetic_transport_token':return self.answer({'error':'denied'},401)
            path=urllib.parse.urlsplit(self.path).path
            body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0')))) if method=='POST' else None
            self.server.observed.append((method,self.path,body))
            prefix='/repos/fixture/distribution'
            if method=='GET' and path==prefix:return self.answer({'node_id':'fixture-node','full_name':'fixture/distribution'})
            if method=='GET' and path==prefix+'/git/ref/heads/main':
                return self.answer({'ref':'refs/heads/main','object':{'type':'commit','sha':self.git('rev-parse','refs/heads/main').decode().strip()}})
            if method=='GET' and '/git/commits/' in path:
                sha=path.rsplit('/',1)[1];raw=self.git('cat-file','commit',sha).decode();headers,message=raw.split('\n\n',1)
                return self.answer({'sha':sha,'tree':{'sha':next(x[5:] for x in headers.splitlines() if x.startswith('tree '))},
                                    'parents':[{'sha':x[7:]} for x in headers.splitlines() if x.startswith('parent ')],'message':message.rstrip('\n')})
            if method=='GET' and '/git/trees/' in path:
                sha=path.rsplit('/',1)[1];rows=self.git('ls-tree','-r','-t','-z',sha).split(b'\0');items=[]
                for row in rows:
                    if not row:continue
                    header,name=row.split(b'\t');mode,kind,oid=header.decode().split()
                    items.append({'path':name.decode(),'mode':mode,'type':kind,'sha':oid})
                if self.server.corrupt_tree and items:items[0]['mode']='100755' if items[0]['mode']=='100644' else '100644'
                return self.answer({'sha':sha,'tree':items,'truncated':self.server.truncated})
            if method=='GET' and '/git/blobs/' in path:
                sha=path.rsplit('/',1)[1];raw=self.git('cat-file','blob',sha)
                if self.server.corrupt_blob:raw=b'tampered'
                return self.answer({'sha':sha,'encoding':'base64','content':base64.b64encode(raw).decode()})
            if method=='POST' and path==prefix+'/git/blobs':
                sha=self.git('hash-object','-w','--stdin',data=base64.b64decode(body['content'])).decode().strip()
                if self.server.cut_blob:
                    self.server.cut_blob=False;return self.cut()
                return self.answer({'sha':sha})
            if method=='POST' and path==prefix+'/git/trees':
                with tempfile.TemporaryDirectory() as tmp:
                    index=Path(tmp)/'index'
                    LocalPublisher._git(self.server.repo,'read-tree',body['base_tree'],index=index)
                    for item in body['tree']:
                        entry=(('0 '+'0'*40) if item['sha'] is None else item['mode']+' '+item['sha'])+'\t'+item['path']+'\0'
                        LocalPublisher._git(self.server.repo,'update-index','-z','--index-info',data=entry.encode(),index=index)
                    sha=LocalPublisher._git(self.server.repo,'write-tree',index=index).decode().strip()
                return self.answer({'sha':sha})
            if method=='POST' and path==prefix+'/git/commits':
                epoch=int(__import__('datetime').datetime.fromisoformat(body['author']['date'].replace('Z','+00:00')).timestamp())
                identity=f'Factory Runner <factory-runner@localhost.invalid> {epoch} +0000'
                raw=(f'tree {body["tree"]}\nparent {body["parents"][0]}\nauthor {identity}\ncommitter {identity}\n\n'+body['message']).encode()
                return self.answer({'sha':self.git('hash-object','-t','commit','-w','--stdin',data=raw).decode().strip()})
            if method=='POST' and path=='/graphql':
                args=body['variables']['input'];update=args['refUpdates'][0]
                assert args['repositoryId']=='fixture-node' and update['force'] is False
                if self.server.before_cas:self.server.before_cas()
                try:
                    self.git('merge-base','--is-ancestor',update['beforeOid'],update['afterOid'])
                    self.git('update-ref',update['name'],update['afterOid'],update['beforeOid'])
                except Exception:return self.answer({'errors':[{'message':'CAS refused'}]})
                if self.server.cut_cas:
                    self.server.cut_cas=False;return self.cut()
                return self.answer({'data':{'updateRefs':{'clientMutationId':args['clientMutationId']}}})
            return self.answer({'error':'not found'},404)
        except Exception:return self.answer({'error':'fixture failure'},500)


class M006Tests(unittest.TestCase):
    def setUp(self):
        self.fx=fixture_module.ReleasePipelineTests();self.fx.setUp();self.addCleanup(self.fx.doCleanups)
        self.root=self.fx.root
        self.bundle,self.receipt,_=self.fx.ready();self.receipt_digest=digest(self.receipt)
        self.owner_dir=self.root/'issuer';self.owner_dir.mkdir(mode=0o700)
        self.publisher_dir=self.root/'publisher';self.publisher_dir.mkdir(mode=0o700)
        self.private_key=self.owner_dir/'signing.pem';self.public_key=self.root/'owner-public.pem'
        env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent'}
        subprocess.run(['/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(self.private_key)],env=env,check=True,capture_output=True)
        subprocess.run(['/usr/bin/openssl','pkey','-in',str(self.private_key),'-pubout','-out',str(self.public_key)],env=env,check=True,capture_output=True)
        self.private_key.chmod(0o600);self.public_key.chmod(0o444)
        self.password='synthetic owner passphrase only'
        owner={'owner_id':'fixture-owner','salt':os.urandom(16).hex()}
        owner['password_scrypt']=password_digest(self.password,bytes.fromhex(owner['salt']))
        self.owner_record=self.owner_dir/'owner.json';self.owner_record.write_text(json.dumps(owner));self.owner_record.chmod(0o600)
        self.issuer=ApprovalIssuer(self.owner_dir,self.private_key,self.owner_record,'fixture-ed25519');self.addCleanup(self.issuer.close)
        self.contract=ArtifactContract(self.fx.profile,2,lambda sha:rc_fastlane.evaluate(self.fx.source,self.fx.dist,sha,profile=self.fx.profile),source_checkout=self.fx.source,distribution_checkout=self.fx.dist)
        self.verifier=GrantVerifier(self.public_key,authority='fixture-ed25519',owner_id='fixture-owner',status_provider=self.issuer.status,
                                    public_key_sha256=hashlib.sha256(self.public_key.read_bytes()).hexdigest())
        self.http=HTTPServer(('127.0.0.1',0),GitHubFixture);self.http.repo=self.fx.target;self.http.observed=[]
        self.http.cut_blob=False;self.http.cut_cas=False;self.http.corrupt_blob=False;self.http.corrupt_tree=False;self.http.truncated=False;self.http.before_cas=None
        thread=threading.Thread(target=self.http.serve_forever,daemon=True);thread.start()
        self.addCleanup(self.http.server_close);self.addCleanup(self.http.shutdown)
        class FixtureHTTP(GitHubBytesHTTP):base='http://127.0.0.1:'+str(self.http.server_port)
        self.token=self.publisher_dir/'transport-token';self.token.write_text('synthetic_transport_token');self.token.chmod(0o600)
        self.client=FixtureHTTP(self.token,lambda:None)
        self.transport=GitHubBytesTransport(self.client,'fixture/distribution','refs/heads/main')
        self.workflow=PublicationWorkflow(self.publisher_dir,self.contract,self.verifier,self.transport,gate=lambda:None);self.addCleanup(self.workflow.close)

    def grant(self):
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        return self.issuer.consent(view['proposal_id'],self.password,view['consent_digest'],'PUBLICAR')
    def publish(self,grant,**kwargs):return self.workflow.publish(self.bundle,self.receipt_digest,grant,**kwargs)

    def test_full_http_git_and_independent_owner_consent(self):
        grant=self.grant();out=self.publish(grant)
        self.assertEqual(out['state'],'PUBLISHED_VERIFIED_PENDING_HOMOLOGATION')
        self.assertFalse(out['idempotent'])
        again=self.publish(grant);self.assertTrue(again['idempotent']);self.assertEqual(out['commit'],again['commit'])
        self.assertEqual(self.fx.git(self.fx.target,'show','main:sentinel.txt'),'other add-on must survive')
        self.assertEqual(self.fx.git(self.fx.target,'rev-list','--count','main'),'2')
        mutations=[body for method,path,body in self.http.observed if path=='/graphql']
        self.assertEqual(len(mutations),1);self.assertIs(mutations[0]['variables']['input']['refUpdates'][0]['force'],False)
        self.assertNotIn('obsolete.txt',self.fx.git(self.fx.target,'ls-tree','-r','--name-only','main'))
        self.assertTrue(any('published_verified' in state['state'] for state in self.workflow.status()))

    def test_default_gate_blocks_before_transport(self):
        other=PublicationWorkflow(self.publisher_dir,self.contract,self.verifier,self.transport)
        self.addCleanup(other.close);grant=self.grant();self.http.observed.clear()
        with self.assertRaisesRegex(PublicationError,'publication_disabled'):other.publish(self.bundle,self.receipt_digest,grant)
        self.assertEqual(self.http.observed,[])

    def test_invalid_credential_fails_closed_without_leaking(self):
        grant=self.grant();self.token.write_text('wrong_token')
        with self.assertRaises(PublicationError) as ctx:self.publish(grant)
        self.assertNotIn('wrong_token',str(ctx.exception));self.assertNotIn(self.password,str(ctx.exception))
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),self.fx.base)

    def test_false_bearer_comment_whatsapp_and_confirmation(self):
        for body in ({'owner_approved':True},{'bearer':'x'*40},{'whatsapp':'approved'},None):
            with self.assertRaises(PublicationError):self.publish(body)
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        with self.assertRaisesRegex(PublicationError,'explicit_consent'):
            self.issuer.consent(view['proposal_id'],self.password,view['consent_digest'],'yes')

    def test_owner_password_and_persistent_throttle(self):
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        for _ in range(5):
            with self.assertRaisesRegex(PublicationError,'authentication_failed'):
                self.issuer.consent(view['proposal_id'],'invalid password long',view['consent_digest'],'PUBLICAR')
        restarted=ApprovalIssuer(self.owner_dir,self.private_key,self.owner_record,'fixture-ed25519');self.addCleanup(restarted.close)
        with self.assertRaisesRegex(PublicationError,'authentication_throttled'):
            restarted.consent(view['proposal_id'],self.password,view['consent_digest'],'PUBLICAR')

    def test_reconsent_is_not_an_implicit_second_grant(self):
        grant=self.grant()
        with self.assertRaisesRegex(PublicationError,'proposal_already_used'):
            self.issuer.consent(grant['payload']['proposal_id'],self.password,grant['payload']['consent_digest'],'PUBLICAR')

    def test_each_binding_field_and_owner_identity_fail_closed(self):
        grant=self.grant()
        for key in list(grant['payload']):
            wrong=copy.deepcopy(grant);wrong['payload'][key]='wrong'
            # Even a signature by the trusted issuer cannot broaden trusted policy.
            wrong['signature']=cryptographic_operation(self.private_key,wrong['payload'])
            with self.subTest(key=key),self.assertRaises(PublicationError):self.publish(wrong)

    def test_revoked_grant_and_disconnected_status(self):
        grant=self.grant();self.issuer.revoke(grant['payload']['nonce'],self.password)
        with self.assertRaisesRegex(PublicationError,'grant_revoked'):self.publish(grant)
        with patch.object(self.verifier,'status_provider',side_effect=OSError('synthetic secret')):
            with self.assertRaisesRegex(PublicationError,'revocation_service_unavailable'):self.publish(grant)

    def test_expiry(self):
        grant=self.grant()
        with patch('owner_approval.time.time',return_value=grant['payload']['expires_at']+1):
            with self.assertRaisesRegex(PublicationError,'grant_binding_or_expiry'):self.publish(grant)

    def test_forged_signature_and_wrong_public_key(self):
        grant=self.grant();grant['signature']=base64.b64encode(b'x'*64).decode()
        with self.assertRaisesRegex(PublicationError,'invalid_signature'):self.publish(grant)
        with self.assertRaisesRegex(PublicationError,'untrusted_verifier_key'):
            GrantVerifier(self.public_key,authority='fixture',owner_id='fixture-owner',status_provider=self.issuer.status,public_key_sha256='0'*64)

    def test_live_status_challenge_cannot_be_replayed(self):
        grant=self.grant();old=self.issuer.status(grant['payload']['nonce'],'old',digest(grant['payload']),'check')
        with patch.object(self.verifier,'status_provider',return_value=old):
            with self.assertRaisesRegex(PublicationError,'grant_revoked_or_status'):self.publish(grant)

    def test_network_loss_before_ref_write_retries_same_objects(self):
        grant=self.grant();self.http.cut_blob=True
        with self.assertRaises(PublicationError):self.publish(grant)
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),self.fx.base)
        self.publish(grant);self.assertEqual(self.fx.git(self.fx.target,'rev-list','--count','main'),'2')

    def test_network_loss_after_cas_recovers_without_duplicate_write(self):
        grant=self.grant();self.http.cut_cas=True
        with self.assertRaises(PublicationError):self.publish(grant)
        commit=self.fx.git(self.fx.target,'rev-parse','main');self.assertNotEqual(commit,self.fx.base)
        result=self.publish(grant);self.assertTrue(result['idempotent']);self.assertEqual(result['commit'],commit)
        self.assertEqual(len([x for x in self.http.observed if x[1]=='/graphql']),1)

    def test_remote_cas_race_exact_head(self):
        grant=self.grant()
        advanced=LocalPublisher._git(self.fx.target,'commit-tree',self.fx.git(self.fx.target,'rev-parse','main^{tree}'),'-p',self.fx.base,data=b'other writer\n').decode().strip()
        self.http.before_cas=lambda:self.fx.git(self.fx.target,'update-ref','refs/heads/main',advanced)
        with self.assertRaisesRegex(PublicationError,'remote_atomic_cas_refused'):self.publish(grant)
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),advanced)

    def test_remote_tree_truncation_tamper_and_blob_corruption(self):
        self.http.truncated=True
        with self.assertRaisesRegex(PublicationError,'remote_tree_incomplete'):self.grant()
        self.http.truncated=False;self.http.corrupt_tree=True
        with self.assertRaises(PublicationError):self.grant()
        self.http.corrupt_tree=False;grant=self.grant();self.http.corrupt_blob=True
        with self.assertRaisesRegex(PublicationError,'remote_blob_integrity'):self.publish(grant)
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),self.fx.base)

    def test_cancellation_and_no_implicit_rollback(self):
        grant=self.grant()
        with self.assertRaisesRegex(PublicationError,'publication_cancelled'):self.publish(grant,cancel=lambda:True)
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),self.fx.base)
        self.assertTrue(any(x['state']=='blocked_or_remote_result_unknown' for x in self.workflow.status()))

    def test_current_package_policy_and_artifact_bytes_revalidated(self):
        grant=self.grant();self.fx.policy['active_package']['status']='closed'
        (self.fx.source/'policy.json').write_text(json.dumps(self.fx.policy));sha=self.fx.commit(self.fx.source)
        self.fx.git(self.fx.source,'update-ref',self.fx.profile['source_ref'],sha)
        with self.assertRaisesRegex(PublicationError,'current_project_policy_blocked'):self.publish(grant)

    def test_no_project_code_execution_or_secret_in_artifacts_and_logs(self):
        grant=self.grant();self.publish(grant)
        for p in self.bundle.rglob('*'):
            if p.is_file():
                data=p.read_bytes()
                for secret in (self.password,'synthetic_transport_token',self.private_key.read_text()):self.assertNotIn(secret.encode(),data)
        raw=json.dumps(self.http.observed)
        self.assertNotIn('synthetic_transport_token',raw);self.assertNotIn(self.password,raw)
        self.assertEqual(self.fx.git(self.fx.source,'status','--porcelain'),'')

    def test_unix_peer_uid_and_action_acl(self):
        directory=self.root/'socket';directory.mkdir(mode=0o750)
        rpc=ApprovalRPCServer(directory/'approval.sock',self.issuer,{os.geteuid():{'status','view'}},group_gid=os.getgid())
        thread=threading.Thread(target=rpc.serve_forever,daemon=True);thread.start()
        self.addCleanup(rpc.server_close);self.addCleanup(rpc.shutdown)
        client=ApprovalRPCClient(directory/'approval.sock',os.geteuid())
        with self.assertRaisesRegex(PublicationError,'approval_request_denied'):client.request('propose',body={})
        with self.assertRaisesRegex(PublicationError,'issuer_peer_mismatch'):
            ApprovalRPCClient(directory/'approval.sock',os.geteuid()+100).request('view',proposal='x')
        grant=self.grant()
        proof=client.status(grant['payload']['nonce'],'challenge',digest(grant['payload']),'check')
        self.assertTrue(proof['payload']['active'])

    def test_ha_owner_ui_rejects_malformed_or_non_origin_urls(self):
        class RPC:
            def request(self,*args,**kwargs):return {}
        invalid=('https://','https:///ha.example.invalid','http://ha.example.invalid',
                 'https://user@ha.example.invalid','https://ha.example.invalid/path',
                 'https://ha.example.invalid?x=1','https://ha.example.invalid#fragment',
                 'https://ha.example.invalid:bad','https://ha.example.invalid\n')
        for origin in invalid:
            with self.subTest(origin=origin),self.assertRaisesRegex(PublicationError,'https_owner_origin_required'):
                OwnerConsentUI(RPC(),origin,ingress_verifier=lambda ctx:'fixture-owner')

    def test_ha_owner_ui_requires_verified_context_csrf_and_reauth(self):
        outer=self
        class RPC:
            def request(self,action,**body):return getattr(outer.issuer,action)(**body)
        ui=OwnerConsentUI(RPC(),'https://ha.example.invalid',ingress_verifier=lambda ctx:'fixture-owner' if ctx.get('trusted') else None)
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        with self.assertRaisesRegex(PublicationError,'verified_owner_ingress'):
            ui.view(view['proposal_id'],{'Authorization':'Bearer synthetic'})
        page=ui.view(view['proposal_id'],{'trusted':True})
        self.assertNotIn(self.password,page['html']);self.assertIn('no-store',page['headers']['Cache-Control'])
        csrf=ui.sessions[page['session']]['csrf']
        with self.assertRaisesRegex(PublicationError,'owner_csrf'):
            ui.consent(page['session'],{'csrf':csrf,'password':self.password,'confirmation':'PUBLICAR'},{'trusted':True},'https://evil.invalid')
        page=ui.view(view['proposal_id'],{'trusted':True});csrf=ui.sessions[page['session']]['csrf']
        grant=ui.consent(page['session'],{'csrf':csrf,'password':self.password,'confirmation':'PUBLICAR'},{'trusted':True},'https://ha.example.invalid')
        self.publish(grant)

    def test_api_status_keeps_publish_disabled_without_owner_route(self):
        self.assertEqual(capabilities()['publication'],'gated_by_default')
        self.assertNotIn('/api/publish',server.OPERATIONS)
        with self.assertRaisesRegex(PublicationError,'publication_disabled'):disabled_gate()

    def test_revoke_before_reservation_blocks_ref_write(self):
        grant=self.grant();real=self.transport.verify_objects;done=[]
        def revoke(plan):
            real(plan)
            if not done:
                done.append(True);self.issuer.revoke(grant['payload']['nonce'],self.password)
        with patch.object(self.transport,'verify_objects',side_effect=revoke):
            with self.assertRaisesRegex(PublicationError,'grant_revoked'):self.publish(grant)
        self.assertEqual(self.fx.git(self.fx.target,'rev-parse','main'),self.fx.base)

    def test_revocation_after_reservation_reports_too_late(self):
        grant=self.grant();observed=[]
        def attempt():
            try:self.issuer.revoke(grant['payload']['nonce'],self.password)
            except PublicationError as exc:observed.append(str(exc))
        self.http.before_cas=attempt;self.publish(grant)
        self.assertEqual(observed,['publication_reserved_reconcile_required'])

    def test_two_publishers_share_single_nonce_and_commit(self):
        grant=self.grant();second=PublicationWorkflow(self.publisher_dir,self.contract,self.verifier,self.transport,gate=lambda:None)
        self.addCleanup(second.close);answers=[];errors=[]
        def execute(workflow):
            try:answers.append(workflow.publish(self.bundle,self.receipt_digest,grant))
            except Exception as exc:errors.append(type(exc).__name__)
        threads=[threading.Thread(target=execute,args=(workflow,)) for workflow in (self.workflow,second)]
        for thread in threads:thread.start()
        for thread in threads:thread.join(30);self.assertFalse(thread.is_alive())
        self.assertTrue(answers)
        self.assertEqual(self.fx.git(self.fx.target,'rev-list','--count','main'),'2')
        self.assertEqual(len([x for x in self.http.observed if x[1]=='/graphql']),1)
        self.assertTrue(all(x['commit']==answers[0]['commit'] for x in answers))

    def test_pending_tests_no_scope_self_authorization_and_receipt_tampering(self):
        changed=copy.deepcopy(self.receipt);changed['tests']['status']='PENDING'
        (self.bundle/'RELEASE_RECEIPT.json').write_bytes(canonical(changed))
        with self.assertRaisesRegex(PublicationError,'verified_product_tests'):
            self.workflow.preview(self.bundle,digest(changed))
        changed=copy.deepcopy(self.receipt);changed['scope']='other-addon/'
        (self.bundle/'RELEASE_RECEIPT.json').write_bytes(canonical(changed))
        with self.assertRaisesRegex(PublicationError,'trusted_profile_mismatch'):
            self.workflow.preview(self.bundle,digest(changed))

    def test_executable_modes_and_empty_blob_roundtrip(self):
        (self.fx.source/'run.sh').chmod(0o755);(self.fx.source/'empty.txt').write_bytes(b'')
        self.fx.profile['declarative_mapping']['demo/empty.txt']='empty.txt';self.fx.save_profile()
        self.fx.sha=self.fx.commit(self.fx.source)
        for name in ('source_ref','rc_ref'):self.fx.git(self.fx.source,'update-ref',self.fx.profile[name],self.fx.sha)
        # Preserve earlier successful fixture, choose the new deterministic identity.
        server.prepare_project('avisaqui',self.fx.sha,'new-modes')
        folders=[p for p in (self.root/'preparations').iterdir() if p.is_dir() and json.loads((p/'RELEASE_RECEIPT.json').read_text())['source_sha']==self.fx.sha]
        self.bundle=folders[0];self.receipt=json.loads((self.bundle/'RELEASE_RECEIPT.json').read_text())
        self.receipt['tests']={'status':'PASS','source_sha':self.fx.sha,'checks':[{'exit_code':0,'passed':1}]}
        (self.bundle/'RELEASE_RECEIPT.json').write_bytes(canonical(self.receipt));self.receipt_digest=digest(self.receipt)
        self.contract.profile=self.fx.profile;result=self.publish(self.grant())
        self.assertTrue(self.fx.git(self.fx.target,'ls-tree',result['commit'],'--','demo/run.sh').startswith('100755'))
        self.assertEqual(LocalPublisher._git(self.fx.target,'show',result['commit']+':demo/empty.txt'),b'')

    def test_http_redirect_is_not_followed_with_credential(self):
        class Redirect(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(302);self.send_header('Location','https://example.invalid/credential-sink');self.end_headers()
            def log_message(self,*args):pass
        fixture=HTTPServer(('127.0.0.1',0),Redirect);threading.Thread(target=fixture.serve_forever,daemon=True).start()
        self.addCleanup(fixture.server_close);self.addCleanup(fixture.shutdown)
        class RedirectHTTP(GitHubBytesHTTP):base='http://127.0.0.1:'+str(fixture.server_port)
        with self.assertRaisesRegex(PublicationError,'remote_http_302'):
            RedirectHTTP(self.token,lambda:None).request('GET','/repos/fixture/distribution')

    def test_read_only_api_status_and_publish_route_gated(self):
        from http.server import ThreadingHTTPServer
        fixture=ThreadingHTTPServer(('127.0.0.1',0),server.Handler)
        threading.Thread(target=fixture.serve_forever,daemon=True).start()
        self.addCleanup(fixture.server_close);self.addCleanup(fixture.shutdown)
        with patch.dict(os.environ,{'RUNNER_AUTH_TOKEN':'t'*40}):
            conn=http.client.HTTPConnection('127.0.0.1',fixture.server_port)
            conn.request('GET','/api/publication-status');response=conn.getresponse();self.assertEqual(response.status,401);response.read()
            conn.request('GET','/api/publication-status',headers={'Authorization':'Bearer '+'t'*40})
            response=conn.getresponse();self.assertEqual(response.status,200);self.assertEqual(json.loads(response.read())['publication'],'disabled')
            conn.request('POST','/api/publish',body='{}',headers={'Authorization':'Bearer '+'t'*40})
            response=conn.getresponse();payload=json.loads(response.read());self.assertEqual(response.status,400);self.assertEqual(payload['error'],'invalid_publication_payload');conn.close()

    def test_recovery_after_cas_sync_expiry_and_process_restart_is_read_only(self):
        grant=self.grant();self.http.cut_cas=True
        with self.assertRaises(PublicationError):self.publish(grant)
        commit=self.fx.git(self.fx.target,'rev-parse','main')
        # Simulate legitimate workspace sync after publication, before retry.
        LocalPublisher._git(self.fx.dist,'fetch',str(self.fx.target),'refs/heads/main')
        self.fx.git(self.fx.dist,'update-ref',self.fx.profile['public_ref'],commit)
        restarted=PublicationWorkflow(self.publisher_dir,self.contract,self.verifier,self.transport)
        self.addCleanup(restarted.close);self.http.observed.clear()
        with patch('owner_approval.time.time',return_value=grant['payload']['expires_at']+1):
            result=restarted.reconcile(grant['payload']['nonce'])
        self.assertEqual(result['commit'],commit);self.assertTrue(result['read_only_recovery'])
        self.assertTrue(all(method=='GET' for method,_,_ in self.http.observed))
        with self.assertRaises(PublicationError):restarted.publish(self.bundle,self.receipt_digest,grant)

    def test_public_key_replacement_cannot_change_pinned_authority(self):
        grant=self.grant();other=self.owner_dir/'other.pem'
        subprocess.run(['/usr/bin/openssl','genpkey','-algorithm','ED25519','-out',str(other)],check=True,capture_output=True)
        replacement=self.root/'replacement.pem'
        subprocess.run(['/usr/bin/openssl','pkey','-in',str(other),'-pubout','-out',str(replacement)],check=True,capture_output=True)
        replacement.chmod(0o444);os.replace(replacement,self.public_key)
        grant['signature']=cryptographic_operation(other,grant['payload'])
        with self.assertRaisesRegex(PublicationError,'invalid_signature'):self.publish(grant)

    def test_consent_audit_failure_rolls_back_grant_but_preserves_throttle(self):
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        with patch.object(self.issuer,'event',side_effect=RuntimeError('audit unavailable')):
            with self.assertRaises(RuntimeError):
                self.issuer.consent(view['proposal_id'],self.password,view['consent_digest'],'PUBLICAR')
        row=self.issuer.db.execute('SELECT nonce,grant FROM proposals WHERE id=?',(view['proposal_id'],)).fetchone()
        self.assertEqual(row,(None,None))
        grant=self.issuer.consent(view['proposal_id'],self.password,view['consent_digest'],'PUBLICAR')
        self.publish(grant)

    def test_consistent_payload_and_receipt_forgery_fails_source_reproduction(self):
        (self.bundle/'demo/run.sh').write_text('forged but self-consistent\n')
        forged=copy.deepcopy(self.receipt)
        from release_receipt import inventory
        forged['files']=inventory(self.bundle)
        (self.bundle/'RELEASE_RECEIPT.json').write_bytes(canonical(forged))
        with self.assertRaisesRegex(PublicationError,'artifact_not_from_pinned_recipe'):
            self.workflow.preview(self.bundle,digest(forged))

    def test_current_policy_closed_after_valid_frozen_snapshot_is_denied(self):
        tree=self.fx.git(self.fx.source,'rev-parse',self.fx.sha+'^{tree}')
        frozen=LocalPublisher._git(self.fx.source,'commit-tree',tree,'-p',self.fx.sha,data=b'frozen identical snapshot\n').decode().strip()
        self.fx.git(self.fx.source,'update-ref',self.fx.profile['rc_ref'],frozen)
        self.fx.policy['active_package']['status']='closed'
        (self.fx.source/'policy.json').write_text(json.dumps(self.fx.policy));head=self.fx.commit(self.fx.source)
        self.fx.git(self.fx.source,'update-ref',self.fx.profile['source_ref'],head)
        # Preparation and publication both consult current policy: freezing the
        # legitimate bytes cannot freeze an authorization later closed.
        report=rc_fastlane.evaluate(self.fx.source,self.fx.dist,self.fx.sha,profile=self.fx.profile)
        self.assertFalse(report['eligible_for_preparation'])
        self.assertIn('CURRENT_PACKAGE_POLICY_CHANGED',report['errors'])
        self.assertFalse(server.prepare_project('avisaqui',self.fx.sha,'closed-frozen')['eligible'])
        with self.assertRaisesRegex(PublicationError,'current_project_policy_blocked'):
            self.workflow.preview(self.bundle,self.receipt_digest)

    def test_same_workflow_instance_concurrency_cannot_rollback_other_thread(self):
        grant=self.grant();answers=[];errors=[]
        def run():
            try:answers.append(self.publish(grant))
            except Exception as exc:errors.append(type(exc).__name__)
        workers=[threading.Thread(target=run) for _ in range(2)]
        for worker in workers:worker.start()
        for worker in workers:worker.join(30);self.assertFalse(worker.is_alive())
        self.assertEqual(errors,[]);self.assertEqual(len(answers),2)
        self.assertEqual(sum(not result['idempotent'] for result in answers),1)
        self.assertEqual(len([x for x in self.http.observed if x[1]=='/graphql']),1)

    def test_owner_ui_displays_exact_deletions_and_receipt_tests(self):
        outer=self
        class RPC:
            def request(self,action,**body):return getattr(outer.issuer,action)(**body)
        view=self.workflow.propose(self.bundle,self.receipt_digest,self.issuer)
        ui=OwnerConsentUI(RPC(),'https://ha.example.invalid',ingress_verifier=lambda context:'fixture-owner')
        page=ui.view(view['proposal_id'],{})['html']
        self.assertIn('demo/obsolete.txt',page);self.assertIn('null',page)
        self.assertIn('PASS',page);self.assertIn(self.receipt_digest,page)

    def test_remote_sha256_independent_of_git_oid(self):
        r,_,files=self.contract.snapshot(self.bundle,self.receipt_digest)
        plan=self.transport.plan(r,files)
        self.transport.upload_objects(plan,files,lambda:None)
        plan['artifact_sha256']['demo/run.sh']='0'*64
        with self.assertRaisesRegex(PublicationError,'remote_blob_integrity'):
            self.transport.verify_objects(plan)

    def test_approved_shared_workflow_identical_allowed_but_changed_denied(self):
        name='.github/workflows/existing.yml'
        for repo,path in ((self.fx.source,'ci.yml'),(self.fx.dist,name)):
            target=repo/path;target.parent.mkdir(parents=True,exist_ok=True);target.write_text('name: existing\n')
        self.fx.profile['allowed_shared_paths']=[name]
        self.fx.profile['declarative_mapping'][name]='ci.yml';self.fx.save_profile()
        self.fx.sha=self.fx.commit(self.fx.source)
        for ref in ('source_ref','rc_ref'):self.fx.git(self.fx.source,'update-ref',self.fx.profile[ref],self.fx.sha)
        base=self.fx.commit(self.fx.dist);self.fx.git(self.fx.dist,'update-ref',self.fx.profile['public_ref'],base)
        LocalPublisher._git(self.fx.target,'fetch',str(self.fx.dist),'refs/heads/main')
        self.fx.git(self.fx.target,'update-ref','refs/heads/main',base)
        result=server.prepare_project('avisaqui',self.fx.sha,'shared')
        output=next(p for p in (self.root/'preparations').iterdir()
                    if p.is_dir() and digest(json.loads((p/'RELEASE_RECEIPT.json').read_text()))==result['receipt_sha256'])
        self.bundle=output;self.receipt=json.loads((output/'RELEASE_RECEIPT.json').read_text())
        self.receipt['tests']={'status':'PASS','source_sha':self.fx.sha,'checks':[{'exit_code':0,'passed':1}]}
        (output/'RELEASE_RECEIPT.json').write_bytes(canonical(self.receipt));self.receipt_digest=digest(self.receipt)
        preview=self.workflow.preview(output,self.receipt_digest)
        self.assertNotIn(name,[change['path'] for change in preview['changes']])
        # This same receipt cannot authorize a workflow change: even when a
        # caller constructs a changed snapshot, the remote diff gate denies it.
        r,_,files=self.contract.snapshot(output,self.receipt_digest)
        files[name]={'mode':'100644','type':'blob','data':b'name: changed\n',
                     'sha':git_oid('blob',b'name: changed\n'),'sha256':hashlib.sha256(b'name: changed\n').hexdigest()}
        with self.assertRaisesRegex(PublicationError,'workflow_changes_disabled'):
            self.transport.plan(r,files)

    def test_reproducer_repeats_ci_gate_and_mapping_version_evidence(self):
        self.contract.profile=copy.deepcopy(self.fx.profile)
        self.contract.profile['declarative_mapping'].pop('demo/package.json')
        with self.assertRaisesRegex(PublicationError,'trusted_recipe_missing_version_evidence'):
            self.contract.reproduce(self.receipt)
        self.contract.profile=copy.deepcopy(self.fx.profile)
        self.contract.profile['declarative_ci']={'patch_source':'export.py','workflow_path':'sentinel.txt','compatible_markers':['required-ci-marker']}
        with self.assertRaisesRegex(PublicationError,'trusted_recipe_ci_requires_separate_review'):
            self.contract.reproduce(self.receipt)
