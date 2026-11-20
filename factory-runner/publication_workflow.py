"""Pi-local trusted workflow. Present in runtime, NEVER activated by Bearer/env.

The installed service has no publish/consent route and launches no issuer or
publisher. Formal security acceptance, owner enrollment and separate activation
change remain required. Tests inject a gate only into disposable local fixtures.
"""
import json
import time
import uuid
import threading
import re
from owner_approval import private_database,serialized
from publication_contract import PublicationError
from release_receipt import canonical,digest


def disabled_gate():raise PublicationError('publication_disabled_pending_formal_acceptance')


def capabilities():
    return {'publication':'disabled','activation':'requires_security_and_owner_acceptance',
            'operation_host':'existing_rpi4_home_assistant',
            'approval':'independent_owner_reauthentication_not_configured',
            'transport':'github_bytes_cas_component_not_activated','project_code_execution':False}


class PublicationWorkflow:
    def __init__(self,state_dir,contract,verifier,transport,*,gate=disabled_gate):
        self.lock=threading.RLock()
        self.db=private_database(state_dir,'remote-publication.sqlite3')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS operations
            (nonce TEXT PRIMARY KEY,binding TEXT NOT NULL,plan TEXT NOT NULL,state TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY,operation TEXT,state TEXT,at INTEGER);''')
        self.contract=contract;self.verifier=verifier;self.transport=transport;self.gate=gate

    def close(self):self.db.close()
    def event(self,operation,state):
        self.db.execute('INSERT INTO events(operation,state,at) VALUES (?,?,?)',(operation,state,int(time.time())))
    def status(self):
        return [{'operation_id':row[0],'state':row[1]} for row in self.db.execute('''
            SELECT e.operation,e.state FROM events e JOIN
            (SELECT operation,MAX(id) id FROM events GROUP BY operation) x ON e.id=x.id
            ORDER BY e.id DESC LIMIT 20''')]

    @staticmethod
    def complete_binding(body,plan):
        return {**body,'preview_sha256':digest(plan['changes']),'destination_tree_sha':plan['tree']}

    @serialized
    def preview(self,root,receipt_digest):
        self.transport.http.deadline=time.monotonic()+240
        r,body,files=self.contract.snapshot(root,receipt_digest)
        plan=self.transport.plan(r,files)
        return {'binding':self.complete_binding(body,plan),'changes':plan['changes'],
                'state':'PREVIEW_NOT_CONSENT','receipt':r,'publication':'disabled'}

    @serialized
    def propose(self,root,receipt_digest,issuer):
        # Internal trusted IPC interface, not HTTP request body parameters.
        preview=self.preview(root,receipt_digest)
        return {**issuer.propose(preview['binding'],preview['changes'],preview['receipt']),'changes':preview['changes']}

    @serialized
    def reconcile(self,nonce):
        """Read-only remote recovery from a previously authorized durable intent.

        Does not require a live grant/current source policy because it cannot
        upload objects or update refs. Caller is the trusted publisher account.
        It can prove an already completed CAS after sync, expiry or revocation.
        """
        self.transport.http.deadline=time.monotonic()+240
        row=self.db.execute('SELECT plan FROM operations WHERE nonce=?',(nonce,)).fetchone()
        if not row:raise PublicationError('unknown_publication_intent')
        plan=json.loads(row[0])
        if (plan.get('repository')!=self.transport.repo or plan.get('ref')!=self.transport.ref
                or plan.get('profile_sha256')!=digest(self.contract.profile)):
            raise PublicationError('recovery_destination_or_profile_mismatch')
        head=self.transport.head()
        if head==plan['commit']:
            self.transport.verify_published(plan)
            self.db.execute('UPDATE operations SET state=? WHERE nonce=?',('published',nonce))
            self.event(nonce,'published_verified_pending_homologation')
            return {'state':'PUBLISHED_VERIFIED_PENDING_HOMOLOGATION','commit':head,'read_only_recovery':True}
        if head==plan['expected']:
            return {'state':'REF_UNCHANGED_NO_PUBLICATION_CONFIRMED','read_only_recovery':True}
        raise PublicationError('recovery_remote_head_conflict_no_rollback')

    @serialized
    def publish(self,root,receipt_digest,grant,*,cancel=None):
        operation=uuid.uuid4().hex
        self.event(operation,'requested')
        try:
            self.gate()
            self.transport.http.deadline=time.monotonic()+240
            r,body,files=self.contract.snapshot(root,receipt_digest)
            nonce=grant.get('payload',{}).get('nonce') if isinstance(grant,dict) else None
            if not isinstance(nonce,str) or not re.fullmatch('[a-f0-9]{32}',nonce):raise PublicationError('independent_grant_required')
            old=self.db.execute('SELECT binding,plan,state FROM operations WHERE nonce=?',(nonce,)).fetchone()
            plan=json.loads(old[1]) if old else self.transport.plan(r,files)
            expected=self.complete_binding(body,plan)
            nonce,bound=self.verifier.check(grant,expected)
            if old and old[0]!=bound:raise PublicationError('grant_replay')
            self.db.execute('BEGIN IMMEDIATE')
            # Reload under database lock; concurrent publishers share ONE ledger.
            current=self.db.execute('SELECT binding,plan,state FROM operations WHERE nonce=?',(nonce,)).fetchone()
            if current and (current[0]!=bound or json.loads(current[1])!=plan):raise PublicationError('concurrent_grant_conflict')
            if not current:
                self.db.execute('INSERT INTO operations VALUES (?,?,?,?)',(nonce,bound,canonical(plan).decode(),'intent'))
            self.event(operation,'durable_intent')
            self.db.execute('COMMIT')
            self.db.execute('BEGIN IMMEDIATE')
            head=self.transport.head()
            if head==plan['commit']:
                self.transport.verify_published(plan)
                self.db.execute('UPDATE operations SET state=? WHERE nonce=?',('published',nonce))
                self.event(operation,'published_verified_pending_homologation')
                self.db.execute('COMMIT')
                return {'state':'PUBLISHED_VERIFIED_PENDING_HOMOLOGATION','commit':plan['commit'],
                        'idempotent':True,'operation_id':operation}
            if head!=plan['expected']:raise PublicationError('remote_head_conflict')
            if current and current[2]=='published':raise PublicationError('published_ref_changed_no_republish')
            started=time.monotonic()
            def check(reserve=False):
                if time.monotonic()-started>240:raise PublicationError('publication_deadline')
                if cancel is not None and cancel():raise PublicationError('publication_cancelled')
                self.gate();self.verifier.check(grant,expected,reserve=reserve)
            check()
            self.transport.upload_objects(plan,files,check)
            # Revalidate policy and all disk bytes. Frozen snapshot is the only
            # source of HTTP data, so a TOCTOU cannot substitute bytes in a send.
            _,again,again_files=self.contract.snapshot(root,receipt_digest)
            if again!=body or again_files!=files:raise PublicationError('artifact_changed_before_cas')
            self.transport.verify_objects(plan)
            check(reserve=True)
            self.transport.cas(plan)
            self.transport.verify_published(plan)
            self.db.execute('UPDATE operations SET state=? WHERE nonce=?',('published',nonce))
            self.event(operation,'published_verified_pending_homologation')
            self.db.execute('COMMIT')
            return {'state':'PUBLISHED_VERIFIED_PENDING_HOMOLOGATION','commit':plan['commit'],
                    'idempotent':False,'operation_id':operation}
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            self.event(operation,'blocked_or_remote_result_unknown')
            # Never roll back a remote ref or renew consent automatically.
            raise


def workflow_for_project(project,issue,state_dir,verifier,transport,*,gate=disabled_gate):
    """Trusted assembly within the Pi using only configured project workspaces."""
    from server import project_workspace,preflight_project
    from publication_contract import ArtifactContract
    profile,source,distribution=project_workspace(project)
    contract=ArtifactContract(profile,issue,lambda sha:preflight_project(project,sha),source_checkout=source,distribution_checkout=distribution)
    return PublicationWorkflow(state_dir,contract,verifier,transport,gate=gate)
