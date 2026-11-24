"""Independent owner consent on the existing Pi. No API bearer or transport key.

Issuer runs as a distinct OS account. Publisher only receives its pinned public
key and signed live status; neither private signing key nor owner password hash.
No production credentials are provisioned by importing or running this module.
"""
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import secrets
import sqlite3
import stat
import subprocess
import tempfile
import time
import threading
from functools import wraps
from release_receipt import canonical,digest,safe_directory
from publication_contract import PublicationError,FIELDS


def protected_file(path, *, private=True, limit=16384):
    path=Path(path).absolute()
    if path.resolve()!=path or not path.is_file():
        raise PublicationError('unsafe_authority_file')
    info=path.stat()
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>limit
            or (private and (info.st_uid!=os.geteuid() or info.st_mode&0o077))):
        raise PublicationError('unsafe_authority_file')
    return path


def private_database(root,name):
    root=safe_directory(root)
    if root.stat().st_uid!=os.geteuid() or root.stat().st_mode&0o077:
        raise PublicationError('private_state_required')
    path=root/name
    if path.exists() or path.is_symlink():protected_file(path,limit=64*1024*1024)
    db=sqlite3.connect(path,timeout=1,isolation_level=None,check_same_thread=False)
    path.chmod(0o600)
    db.execute('PRAGMA journal_mode=DELETE')
    db.execute('PRAGMA synchronous=FULL')
    return db


def cryptographic_operation(key,payload,signature=None,*,public_material=None):
    """Fixed OpenSSL Ed25519 argv, anonymous input files, scrubbed environment."""
    if public_material is None:key=protected_file(key,private=signature is None)
    env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C'}
    with tempfile.TemporaryDirectory(prefix='owner-verify-') as tmp:
        if public_material is not None:
            key=Path(tmp)/'pinned-public.pem';key.write_bytes(public_material);key.chmod(0o400)
        body=Path(tmp)/'body';body.write_bytes(canonical({'domain':'factory-owner-m006-v1','payload':payload}));body.chmod(0o600)
        argv=['/usr/bin/openssl','pkeyutl','-rawin','-inkey',str(key),'-in',str(body)]
        if signature is None:
            argv+=['-sign']
        else:
            try:signature=base64.b64decode(signature,validate=True)
            except (ValueError,TypeError) as exc:raise PublicationError('invalid_signature') from exc
            if len(signature)!=64:raise PublicationError('invalid_signature')
            sig=Path(tmp)/'sig';sig.write_bytes(signature)
            argv+=['-verify','-pubin','-sigfile',str(sig)]
        try:
            result=subprocess.run(argv,env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=5)
        except (OSError,subprocess.TimeoutExpired) as exc:raise PublicationError('signature_service_unavailable') from exc
        if result.returncode:raise PublicationError('invalid_signature')
        if signature is None:
            if len(result.stdout)!=64:raise PublicationError('ed25519_key_required')
            return base64.b64encode(result.stdout).decode('ascii')


def password_digest(password,salt):
    if not isinstance(password,str) or not 16<=len(password)<=256:
        raise PublicationError('owner_authentication_failed')
    return hashlib.scrypt(password.encode(),salt=salt,n=16384,r=8,p=1,dklen=32).hex()


def serialized(method):
    @wraps(method)
    def call(self,*args,**kwargs):
        with self.lock:return method(self,*args,**kwargs)
    return call


class ApprovalIssuer:
    def __init__(self,state_dir,private_key,owner_record,authority):
        self.lock=threading.RLock()
        self.key=protected_file(private_key)
        self.owner=json.loads(protected_file(owner_record).read_bytes())
        if (set(self.owner)!={'owner_id','salt','password_scrypt'}
                or not re.fullmatch('[a-zA-Z0-9_-]{1,64}',self.owner['owner_id'])
                or not re.fullmatch('[a-f0-9]{32}',self.owner['salt'])
                or not re.fullmatch('[a-f0-9]{64}',self.owner['password_scrypt'])):
            raise PublicationError('invalid_owner_configuration')
        self.authority=authority
        self.db=private_database(state_dir,'issuer.sqlite3')
        self.db.executescript('''CREATE TABLE IF NOT EXISTS proposals
          (id TEXT PRIMARY KEY,body TEXT,expires INTEGER,failures INTEGER DEFAULT 0,locked INTEGER DEFAULT 0,nonce TEXT UNIQUE,grant TEXT,revoked INTEGER DEFAULT 0,reserved INTEGER DEFAULT 0,preview TEXT,receipt TEXT);
          CREATE TABLE IF NOT EXISTS audit (at INTEGER,proposal TEXT,state TEXT);
          CREATE TABLE IF NOT EXISTS throttle (id INTEGER PRIMARY KEY,failures INTEGER,locked INTEGER);
          INSERT OR IGNORE INTO throttle VALUES (1,0,0);''')

    @serialized
    def grant(self, proposal):
        row=self.db.execute('SELECT grant,expires,revoked FROM proposals WHERE id=?',(proposal,)).fetchone()
        if not row or not row[0] or row[2] or row[1] <= time.time():
            raise PublicationError('owner_grant_unavailable')
        grant=json.loads(row[0])
        if grant.get('payload',{}).get('proposal_id') != proposal:
            raise PublicationError('owner_grant_binding_invalid')
        return grant

    @serialized
    def public_key(self):
        env={'PATH':'/usr/bin:/bin','HOME':'/nonexistent','LANG':'C'}
        try:
            result=subprocess.run(['/usr/bin/openssl','pkey','-in',str(self.key),'-pubout'],
                env=env,stdin=subprocess.DEVNULL,capture_output=True,timeout=5)
        except (OSError,subprocess.TimeoutExpired) as exc:
            raise PublicationError('public_key_unavailable') from exc
        if result.returncode or not result.stdout.startswith(b'-----BEGIN PUBLIC KEY-----'):
            raise PublicationError('public_key_unavailable')
        return base64.b64encode(result.stdout).decode('ascii')

    def close(self):self.db.close()
    def event(self,proposal,state):
        self.db.execute('INSERT INTO audit VALUES (?,?,?)',(int(time.time()),proposal,state))

    @serialized
    def propose(self,body,preview,receipt):
        # Trusted coordinator IPC only; never a project-supplied blob or HTTP body.
        required=set(FIELDS)|{'issue','action','receipt_sha256','preview_sha256','destination_tree_sha'}
        if (not isinstance(body,dict) or set(body)!=required or body['action']!='publish'
                or type(body['issue']) is not int or body['issue']<=0
                or not re.fullmatch('[a-f0-9]{64}',body['receipt_sha256'])):
            raise PublicationError('invalid_proposal')
        if (not isinstance(preview,list) or digest(preview)!=body['preview_sha256']
                or not isinstance(receipt,dict) or digest(receipt)!=body['receipt_sha256']
                or any(body[key]!=receipt.get(key) for key in FIELDS)):
            raise PublicationError('proposal_preview_or_receipt_mismatch')
        proposal=secrets.token_hex(16)
        self.db.execute('INSERT INTO proposals(id,body,expires,preview,receipt) VALUES (?,?,?,?,?)',
                        (proposal,canonical(body).decode(),int(time.time())+900,canonical(preview).decode(),canonical(receipt).decode()))
        self.event(proposal,'awaiting_owner_consent')
        return self.view(proposal)

    @serialized
    def view(self,proposal):
        row=self.db.execute('SELECT body,expires,nonce,preview,receipt FROM proposals WHERE id=?',(proposal,)).fetchone()
        if not row or row[1]<=time.time():raise PublicationError('proposal_unavailable')
        body=json.loads(row[0])
        return {'proposal_id':proposal,'binding':body,'preview':json.loads(row[3]),'receipt':json.loads(row[4]),'consent_digest':digest(body),
                'expires_at':row[1],'state':'already_consented' if row[2] else 'awaiting_owner_consent'}

    def _authenticate(self,password):
        failures,locked=self.db.execute('SELECT failures,locked FROM throttle WHERE id=1').fetchone()
        if locked>time.time():raise PublicationError('owner_authentication_throttled')
        try:actual=password_digest(password,bytes.fromhex(self.owner['salt']))
        except PublicationError:actual=''
        if not hmac.compare_digest(actual,self.owner['password_scrypt']):
            failures+=1
            self.db.execute('UPDATE throttle SET failures=?,locked=? WHERE id=1',
                            (failures,int(time.time())+300 if failures>=5 else 0))
            self.event(None,'owner_authentication_failed')
            raise PublicationError('owner_authentication_failed')
        self.db.execute('UPDATE throttle SET failures=0,locked=0 WHERE id=1')

    @serialized
    def consent(self,proposal,password,consent_digest,confirmation):
        # Persist authentication throttling independently. Issuing a grant is
        # a second atomic transaction: missing audit must roll the grant back.
        self.db.execute('BEGIN IMMEDIATE')
        try:
            self._authenticate(password)
            self.db.execute('COMMIT')
        except Exception:
            if self.db.in_transaction:self.db.execute('COMMIT')
            raise
        self.db.execute('BEGIN IMMEDIATE')
        try:
            view=self.view(proposal)
            if confirmation!='PUBLICAR' or consent_digest!=view['consent_digest']:
                raise PublicationError('explicit_consent_required')
            if view['state']!='awaiting_owner_consent':raise PublicationError('proposal_already_used')
            now=int(time.time());nonce=secrets.token_hex(16)
            payload={**view['binding'],'authority':self.authority,'owner_id':self.owner['owner_id'],
                     'kind':'owner-publication-grant-v1','proposal_id':proposal,'consent_digest':consent_digest,'nonce':nonce,
                     'issued_at':now,'expires_at':min(view['expires_at'],now+300)}
            grant={'payload':payload,'signature':cryptographic_operation(self.key,payload)}
            self.db.execute('UPDATE proposals SET nonce=?,grant=? WHERE id=?',(nonce,canonical(grant).decode(),proposal))
            self.event(proposal,'owner_reauthenticated_and_consented')
            self.db.execute('COMMIT');return grant
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise

    @serialized
    def revoke(self,nonce,password):
        self._authenticate(password)
        row=self.db.execute('SELECT reserved FROM proposals WHERE nonce=?',(nonce,)).fetchone()
        if row and row[0]:raise PublicationError('publication_reserved_reconcile_required')
        self.db.execute('UPDATE proposals SET revoked=1 WHERE nonce=?',(nonce,))
        self.event(None,'grant_revoked')

    @serialized
    def status(self,nonce,challenge,grant_digest,purpose):
        if purpose not in ('check','reserve'):raise PublicationError('invalid_status_purpose')
        self.db.execute('BEGIN IMMEDIATE')
        try:
            row=self.db.execute('SELECT grant,revoked,reserved FROM proposals WHERE nonce=?',(nonce,)).fetchone()
            active=bool(row and not row[1] and digest(json.loads(row[0])['payload'])==grant_digest
                        and json.loads(row[0])['payload']['expires_at']>time.time())
            reserved=bool(row and row[2])
            if purpose=='reserve' and active:
                # Linearization point for consent vs revoke. Revocation after
                # this point reports too late/needs reconciliation, never success.
                self.db.execute('UPDATE proposals SET reserved=1 WHERE nonce=?',(nonce,))
                self.event(None,'publication_reserved')
                reserved=True
            payload={'kind':'owner-grant-status-v1','nonce':nonce,'challenge':challenge,
                     'grant_digest':grant_digest,'purpose':purpose,'reserved':reserved,
                     'active':active,'at':int(time.time()),'authority':self.authority}
            proof={'payload':payload,'signature':cryptographic_operation(self.key,payload)}
            self.db.execute('COMMIT');return proof
        except Exception:
            if self.db.in_transaction:self.db.execute('ROLLBACK')
            raise


class GrantVerifier:
    def __init__(self,public_key,*,authority,owner_id,status_provider,public_key_sha256):
        self.public_key=protected_file(public_key,private=False)
        self.public_material=self.public_key.read_bytes()
        if (self.public_key.stat().st_mode&0o022
                or hashlib.sha256(self.public_material).hexdigest()!=public_key_sha256):
            raise PublicationError('untrusted_verifier_key')
        self.authority=authority;self.owner_id=owner_id;self.status_provider=status_provider

    def check(self,grant,expected_binding,*,reserve=False):
        if not isinstance(grant,dict) or set(grant)!={'payload','signature'} or not isinstance(grant['payload'],dict):
            raise PublicationError('independent_grant_required')
        p=grant['payload'];cryptographic_operation(None,p,grant['signature'],public_material=self.public_material)
        extra={'kind','authority','owner_id','proposal_id','consent_digest','nonce','issued_at','expires_at'}
        if (set(p)!=set(expected_binding)|extra or any(p.get(k)!=v for k,v in expected_binding.items())
                or p['kind']!='owner-publication-grant-v1' or p['authority']!=self.authority or p['owner_id']!=self.owner_id
                or p['consent_digest']!=digest(expected_binding)
                or not isinstance(p['nonce'],str) or not re.fullmatch('[a-f0-9]{32}',p['nonce'])
                or not isinstance(p['proposal_id'],str) or not re.fullmatch('[a-f0-9]{32}',p['proposal_id'])
                or type(p['issued_at']) is not int or type(p['expires_at']) is not int
                or not p['issued_at']<=time.time()<p['expires_at']
                or not 0<p['expires_at']-p['issued_at']<=300):
            raise PublicationError('grant_binding_or_expiry_invalid')
        challenge=secrets.token_hex(32)
        purpose='reserve' if reserve else 'check'
        try:status=self.status_provider(p['nonce'],challenge,digest(p),purpose)
        except Exception as exc:raise PublicationError('revocation_service_unavailable') from exc
        if not isinstance(status,dict) or set(status)!={'payload','signature'}:
            raise PublicationError('invalid_revocation_proof')
        cryptographic_operation(None,status['payload'],status['signature'],public_material=self.public_material)
        proof=status['payload']
        expected={'kind':'owner-grant-status-v1','nonce':p['nonce'],'challenge':challenge,
                  'grant_digest':digest(p),'purpose':purpose,'reserved':proof.get('reserved'),
                  'active':True,'at':proof.get('at'),'authority':self.authority}
        if (proof!=expected or type(proof.get('reserved')) is not bool
                or (reserve and proof['reserved'] is not True)
                or type(proof.get('at')) is not int or not 0<=time.time()-proof['at']<=30):
            raise PublicationError('grant_revoked_or_status_stale')
        return p['nonce'],digest(p)

class OwnerEnrollment:
    """One-time owner enrollment, callable only through the trusted HA UI UID."""
    def __init__(self, state_dir, owner_id):
        self.state_dir = safe_directory(state_dir)
        if (not re.fullmatch(r"[a-zA-Z0-9_-]{1,64}", owner_id)
                or self.state_dir.stat().st_uid != os.geteuid()
                or self.state_dir.stat().st_mode & 0o077):
            raise PublicationError("unsafe_owner_enrollment_store")
        self.owner_id = owner_id
        self.credentials_dir = self.state_dir / "credentials"
        self.private_key = self.credentials_dir / "signing.pem"
        self.owner_record = self.credentials_dir / "owner.json"
        self.lock = threading.RLock()

    def enrolled(self):
        if not self.credentials_dir.exists() and not self.credentials_dir.is_symlink():
            return False
        info = self.credentials_dir.lstat()
        if (not stat.S_ISDIR(info.st_mode) or info.st_uid != os.geteuid()
                or stat.S_IMODE(info.st_mode) != 0o700 or self.credentials_dir.is_symlink()):
            raise PublicationError("unsafe_owner_credentials_directory")
        if not self.private_key.is_file() or self.private_key.is_symlink():
            raise PublicationError("partial_owner_enrollment")
        if not self.owner_record.is_file() or self.owner_record.is_symlink():
            raise PublicationError("partial_owner_enrollment")
        protected_file(self.private_key)
        protected_file(self.owner_record)
        if set(path.name for path in self.credentials_dir.iterdir()) != {"signing.pem", "owner.json"}:
            raise PublicationError("unexpected_owner_credentials")
        return True

    @serialized
    def enroll(self, password, password_confirm, confirmation):
        if self.enrolled():
            raise PublicationError("owner_already_enrolled")
        if (confirmation != "CADASTRAR" or not isinstance(password, str)
                or not isinstance(password_confirm, str)
                or not hmac.compare_digest(password.encode('utf-8'), password_confirm.encode('utf-8'))
                or not 16 <= len(password) <= 256):
            raise PublicationError("owner_enrollment_input_invalid")
        salt = secrets.token_bytes(16)
        record = {"owner_id": self.owner_id, "salt": salt.hex(),
                  "password_scrypt": password_digest(password, salt)}
        env = {"PATH": "/usr/bin:/bin", "HOME": "/nonexistent", "LANG": "C"}
        with tempfile.TemporaryDirectory(prefix=".owner-enroll-", dir=self.state_dir) as tmp:
            stage = Path(tmp)
            key_tmp = stage / "signing.pem"
            record_tmp = stage / "owner.json"
            try:
                result = subprocess.run(
                    ["/usr/bin/openssl", "genpkey", "-algorithm", "ED25519", "-out", str(key_tmp)],
                    env=env, stdin=subprocess.DEVNULL, capture_output=True, timeout=10)
            except (OSError, subprocess.TimeoutExpired) as exc:
                raise PublicationError("owner_key_generation_unavailable") from exc
            if result.returncode:
                raise PublicationError("owner_key_generation_unavailable")
            key_tmp.chmod(0o600)
            fd = os.open(record_tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            with os.fdopen(fd, "wb") as stream:
                stream.write(canonical(record))
                stream.flush()
                os.fsync(stream.fileno())
            directory_fd = os.open(stage, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(directory_fd)
            finally:
                os.close(directory_fd)
            try:
                os.rename(stage, self.credentials_dir)
            except FileExistsError:
                raise PublicationError("owner_already_enrolled") from None
            parent_fd = os.open(self.state_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        if not self.enrolled():
            raise PublicationError("owner_enrollment_not_durable")
        return {"enrolled": True, "owner_id": self.owner_id}


class ApprovalAuthority:
    """Enrollment facade that becomes the normal ApprovalIssuer after setup."""
    def __init__(self, state_dir, private_key, owner_record, authority, owner_id):
        self.state_dir = Path(state_dir)
        self.private_key = Path(private_key)
        self.owner_record = Path(owner_record)
        self.authority = authority
        self.enrollment = OwnerEnrollment(state_dir, owner_id)
        self.issuer = None
        if self.enrollment.enrolled():
            self._load_issuer()

    def _load_issuer(self):
        issuer = ApprovalIssuer(
            self.state_dir, self.private_key, self.owner_record, self.authority)
        if issuer.owner.get("owner_id") != self.enrollment.owner_id:
            issuer.close()
            raise PublicationError("approval_owner_identity_mismatch")
        self.issuer = issuer

    def enrollment_status(self):
        return {"enrolled": self.enrollment.enrolled()}

    def enroll(self, password, password_confirm, confirmation):
        result = self.enrollment.enroll(password, password_confirm, confirmation)
        self._load_issuer()
        return result

    def close(self):
        if self.issuer is not None:
            self.issuer.close()

    def __getattr__(self, name):
        if self.issuer is None:
            raise PublicationError("owner_enrollment_required")
        return getattr(self.issuer, name)

