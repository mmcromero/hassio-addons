"""Optional private Drive inbox. Drive is read-only; review via existing MCP contract."""
import base64
import hashlib
import json
import re
import sqlite3
import time
from datetime import datetime
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, ProxyHandler, HTTPRedirectHandler

ID = re.compile(r'[A-Za-z0-9_-]{10,200}\Z')
ACCOUNT = re.compile(r'[a-z][a-z0-9_-]{1,39}\Z')
ORDER_ID = re.compile(r'driveq_[0-9a-f]{32}\Z')
KEY = re.compile(r'cei2\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}\Z')
MAX_ORDER = 65536
SCOPE = 'https://www.googleapis.com/auth/drive.readonly'
TOKEN_URL = 'https://oauth2.googleapis.com/token'
API = 'https://www.googleapis.com/drive/v3/'
FIELDS = 'id,name,mimeType,parents,trashed,size,createdTime,version,owners(emailAddress,permissionId),permissionIds,permissions(type,role,emailAddress,deleted),lastModifyingUser(emailAddress,permissionId),sha256Checksum,capabilities(canEdit,canShare),driveId'


class Reject(ValueError):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


def require(condition, code='INVALID'):
    if not condition:
        raise Reject(code)


def diagnostic(exc):
    if isinstance(exc, HTTPError):
        return 'HTTP_'+str(exc.code)
    if isinstance(exc, URLError):
        return 'NETWORK_'+type(exc.reason).__name__
    if isinstance(exc, Reject):
        code = str(exc)
        return code if re.fullmatch(r'[A-Za-z0-9_]{1,80}', code) else 'INVALID'
    return type(exc).__name__


def identifier(value, pattern=ID):
    require(isinstance(value, str) and pattern.fullmatch(value))
    return value


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result)
        result[key] = value
    return result


def parse_order(raw, account, file_id):
    require(isinstance(raw, bytes) and 0 < len(raw) <= MAX_ORDER)
    try:
        item = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_pairs)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise Reject('JSON inválido') from exc
    require(isinstance(item, dict) and set(item) == {'schemaVersion','conta','requestId','transferApproved','format','caption','media'})
    require(type(item['schemaVersion']) is int and item['schemaVersion'] == 1 and item['conta'] == account and item['transferApproved'] is True)
    request = identifier(item['requestId'],ORDER_ID)
    fmt, caption, media = item['format'], item['caption'], item['media']
    require(isinstance(fmt, str) and fmt in ('feed','carousel','story','reel'))
    require(isinstance(caption, str) and len(caption) <= 2200 and isinstance(media, list))
    require(2 <= len(media) <= 20 if fmt == 'carousel' else len(media) == 1)
    total = 0
    for part in media:
        require(isinstance(part, dict) and set(part) == {'fileId','mime','bytes','sha256'})
        identifier(part['fileId'])
        require(part['fileId'] != file_id and part['mime'] in ('image/png','image/jpeg','video/mp4'))
        require(type(part['bytes']) is int and 0 < part['bytes'] <= 4194304)
        require(isinstance(part['sha256'], str) and re.fullmatch(r'[0-9a-f]{64}',part['sha256']))
        total += part['bytes']
    require(total <= 4194304 and len({p['fileId'] for p in media}) == len(media))
    return {'conta': account, 'requestId': request,
            'transferApproved': True, 'format': fmt, 'caption': caption, 'media': media}


class Drive:
    def __init__(self, service):
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        require(isinstance(service, dict) and service.get('type') == 'service_account')
        self.email = service['client_email'].lower()
        require(self.email.endswith('.iam.gserviceaccount.com'))
        require(service.get('token_uri') == TOKEN_URL)
        self.key = load_pem_private_key(service['private_key'].encode(), password=None)
        self.opener = build_opener(ProxyHandler({}), NoRedirect())
        self.token = ''
        self.expiry = 0
        self.reader_id = None

    def read(self, request, limit):
        with self.opener.open(request, timeout=20) as response:
            data = response.read(limit + 1)
        require(len(data) <= limit)
        return data

    def access_token(self):
        from cryptography.hazmat.primitives import hashes
        from cryptography.hazmat.primitives.asymmetric import padding
        now = int(time.time())
        if now < self.expiry:
            return self.token
        def encode(data):
            return base64.urlsafe_b64encode(data).rstrip(b'=')
        claims = {'iss':self.email,'scope':SCOPE,'aud':TOKEN_URL,'iat':now,'exp':now+600}
        body = encode(b'{"alg":"RS256","typ":"JWT"}') + b'.' + encode(json.dumps(claims).encode())
        signature = self.key.sign(body, padding.PKCS1v15(), hashes.SHA256())
        payload = urlencode({'grant_type':'urn:ietf:params:oauth:grant-type:jwt-bearer','assertion':(body+b'.'+encode(signature)).decode()}).encode()
        try:
            result = json.loads(self.read(Request(TOKEN_URL,payload,{'Content-Type':'application/x-www-form-urlencoded'}),MAX_ORDER))
        except (HTTPError, URLError) as exc:
            raise Reject('TOKEN_'+diagnostic(exc)) from None
        require(isinstance(result.get('access_token'), str) and result.get('token_type','').lower() == 'bearer')
        self.token = result['access_token']
        self.expiry = now + max(0,min(300,int(result['expires_in'])-60))
        return self.token

    def get(self, path, params, *, raw=False):
        req = Request(API+path+'?'+urlencode(params),headers={'Authorization':'Bearer '+self.access_token()})
        try:
            data = self.read(req, MAX_ORDER if raw else 1048576)
        except (HTTPError, URLError) as exc:
            stage = 'PERMISSIONS' if path.endswith('/permissions') else ('LIST' if path == 'files' else 'FILE')
            raise Reject(stage+'_'+diagnostic(exc)) from None
        return data if raw else json.loads(data)

    def pages(self, path, params, field):
        result, cursor, seen = [], None, set()
        for _ in range(20):
            query = dict(params)
            if cursor:
                query['pageToken'] = cursor
            page = self.get(path,query)
            require(isinstance(page.get(field),list) and not page.get('incompleteSearch'))
            result.extend(page[field])
            cursor = page.get('nextPageToken')
            if not cursor:
                return result
            require(isinstance(cursor,str) and cursor not in seen)
            seen.add(cursor)
        raise Reject('Paginação excedida')

    def metadata(self, file_id):
        return self.get('files/'+identifier(file_id),{'fields':FIELDS})

    def identity_id(self):
        if self.reader_id is None:
            user = self.get('about', {'fields':'user(emailAddress,permissionId)'}).get('user', {})
            require(user.get('emailAddress','').lower() == self.email, 'READER_IDENTITY_MISMATCH')
            self.reader_id = identifier(user.get('permissionId'))
        return self.reader_id

    def permissions(self, file_id):
        return self.pages('files/'+identifier(file_id)+'/permissions',{'fields':'nextPageToken,permissions(type,role,emailAddress,deleted)','pageSize':100},'permissions')

    def children(self, folder):
        q = "'%s' in parents and trashed = false" % identifier(folder)
        return self.pages('files',{'q':q,'fields':'nextPageToken,incompleteSearch,files('+FIELDS+')','pageSize':100},'files')

    def content(self, file_id):
        return self.get('files/'+identifier(file_id),{'alt':'media'},raw=True)


def private_item(drive, item, owner, parent=None):
    require(item.get('trashed') is False and not item.get('driveId'), 'TRASH_OR_SHARED_DRIVE')
    require([x.get('emailAddress','').lower() for x in item.get('owners',[])] == [owner], 'OWNER_MISMATCH')
    if parent is not None:
        require(item.get('parents') == [parent], 'PARENT_MISMATCH')
    try:
        perms = drive.permissions(item['id'])
    except Reject as exc:
        if str(exc) != 'PERMISSIONS_HTTP_403':
            raise
        # Google does not disclose complete ACLs to readers. Do not infer
        # privacy from missing entries. The authenticated owner-client audits
        # the ACL before submitting; this worker authenticates the actual
        # order author using Google-controlled metadata, not a JSON assertion.
        owner_id = identifier(item['owners'][0].get('permissionId'))
        reader_id = drive.identity_id()
        ids = item.get('permissionIds')
        require(owner_id != reader_id, 'READER_IS_OWNER')
        if ids is not None:
            require(isinstance(ids,list) and all(x in {owner_id,reader_id} for x in ids), 'ACL_IDS_MISMATCH')
        for permission in item.get('permissions',[]):
            if not permission.get('deleted'):
                require(permission.get('type') == 'user' and
                        permission.get('role') in ('owner','reader'), 'VISIBLE_ACL_MISMATCH')
                email = permission.get('emailAddress','').lower()
                require(not email or (permission['role'],email) in {('owner',owner),('reader',drive.email)}, 'VISIBLE_ACL_MISMATCH')
        caps = item.get('capabilities',{})
        require(caps.get('canEdit') is False and caps.get('canShare') is False, 'READER_CAPABILITIES_MISMATCH')
        return
    actual = {(p.get('type'),p.get('role'),p.get('emailAddress','').lower()) for p in perms if not p.get('deleted')}
    require(actual == {('user','owner',owner),('user','reader',drive.email)}, 'ACL_MISMATCH')


def owner_authored(item, owner):
    author = item.get('lastModifyingUser', {})
    owner_id = item.get('owners',[{}])[0].get('permissionId')
    require(isinstance(author,dict), 'AUTHOR_UNVERIFIED')
    author_id = author.get('permissionId')
    author_email = author.get('emailAddress','').lower()
    require((author_id and owner_id and author_id == owner_id) or author_email == owner, 'AUTHOR_UNVERIFIED')
    require(not author_email or author_email == owner, 'AUTHOR_MISMATCH')
    require(not (author_id and owner_id) or author_id == owner_id, 'AUTHOR_MISMATCH')


class Queue:
    def __init__(self, drive, central, call, config, db_path):
        self.drive, self.central, self.call = drive, central, call
        self.root = identifier(config['root_id'])
        self.owner = config['owner_email'].strip().lower()
        require('@' in self.owner and self.owner != drive.email)
        self.key = identifier(config['central_key'], KEY)
        accounts = config['accounts']
        require(isinstance(accounts,list) and 0 < len(accounts) <= 20)
        self.accounts = {identifier(a, ACCOUNT) for a in accounts}
        require(len(self.accounts) == len(accounts))
        self.db = sqlite3.connect(db_path)
        self.db.execute('CREATE TABLE IF NOT EXISTS orders (id TEXT PRIMARY KEY, state TEXT NOT NULL, receipt TEXT, attempts INTEGER NOT NULL, retry_after INTEGER NOT NULL)')
        self.db.commit()

    def close(self):
        self.db.close()

    def record(self, file_id, state, receipt=None, attempts=0, retry_after=0):
        self.db.execute('INSERT OR REPLACE INTO orders VALUES (?,?,?,?,?)',(file_id,state,json.dumps(receipt) if receipt else None,attempts,retry_after))
        self.db.commit()

    def process(self, folder, item, account, now):
        file_id = identifier(item['id'])
        previous = self.db.execute('SELECT state,attempts,retry_after FROM orders WHERE id=?',(file_id,)).fetchone()
        if previous and (previous[0] in ('done','rejected') or previous[2] > now):
            return
        attempts = previous[1] if previous else 0
        try:
            private_item(self.drive,item,self.owner,folder['id'])
            owner_authored(item,self.owner)
            require(item.get('mimeType') == 'application/json' and 0 < int(item.get('size',0)) <= MAX_ORDER)
            created = datetime.fromisoformat(item['createdTime'].replace('Z','+00:00')).timestamp()
            require(-60 <= now-created <= 86400)
            raw = self.drive.content(file_id)
            require(len(raw) == int(item['size']))
            checksum = item.get('sha256Checksum')
            require(checksum is None or checksum == hashlib.sha256(raw).hexdigest(), 'ORDER_HASH_MISMATCH')
            args = parse_order(raw,account,file_id)
            require(item['name'] == 'ordem-'+args['requestId']+'.json')
            # Verify source manifest is unmodified and access has not changed before transfer.
            current = self.drive.metadata(file_id)
            require(item.get('version') and current == item, 'ORDER_CHANGED')
            private_item(self.drive,self.drive.metadata(self.root),self.owner)
            private_item(self.drive,self.drive.metadata(folder['id']),self.owner,self.root)
            private_item(self.drive,current,self.owner,folder['id'])
            owner_authored(current,self.owner)
            for part in args['media']:
                private_item(self.drive,self.drive.metadata(part['fileId']),self.owner,folder['id'])
            result = self.call(self.central,self.key,'enviar_arquivo_drive_para_revisao',args)
            if not (result.get('found') is True and result.get('account') == account and result.get('status') == 'draft' and result.get('publicationAuthorized') is False and result.get('published') is False):
                raise RuntimeError('Recibo não confirmado')
            confirmed = self.call(self.central,self.key,'consultar_envio',{'conta':account,'requestId':args['requestId']})
            if confirmed != result:
                raise RuntimeError('Recibo não confirmado')
            if not re.fullmatch(r'[0-9a-f]{32}',str(confirmed.get('id',''))):
                raise RuntimeError('Recibo não confirmado')
            self.record(file_id,'done',confirmed)
            print('Drive queue PASS requestId='+args['requestId']+' account='+account+' id='+str(confirmed.get('id')),flush=True)
        except Reject as exc:
            self.record(file_id,'rejected',attempts=attempts+1)
            print('Drive queue REJECT '+diagnostic(exc),flush=True)
        except Exception as exc:
            # Ambiguous transport: retry with the SAME requestId; Central checks receipt first.
            self.record(file_id,'retry',attempts=attempts+1,retry_after=now+min(900,30*2**min(attempts,5)))
            print('Drive queue RETRY '+diagnostic(exc),flush=True)

    def poll(self):
        now = int(time.time())
        root = self.drive.metadata(self.root)
        private_item(self.drive,root,self.owner)
        require(root.get('mimeType') == 'application/vnd.google-apps.folder')
        children = self.drive.children(self.root)
        for account in sorted(self.accounts):
            try:
                self.poll_account(children,account,now)
            except Exception as exc:
                print('Drive queue account blocked: '+account+' '+diagnostic(exc),flush=True)

    def poll_account(self, children, account, now):
        matches = [x for x in children if x.get('name') == account]
        require(len(matches) == 1)
        folder = matches[0]
        private_item(self.drive,folder,self.owner,self.root)
        require(folder.get('mimeType') == 'application/vnd.google-apps.folder')
        for item in self.drive.children(folder['id']):
            if item.get('name','').startswith('ordem-') and item['name'].endswith('.json'):
                self.process(folder,item,account,now)


def run_queue(raw_config, origin, stop, db_path='/data/drive-queue.sqlite3'):
    from server import Central, multi_call
    queue = None
    try:
        config = json.loads(raw_config,object_pairs_hook=unique_pairs)
        require(set(config) == {'root_id','owner_email','central_key','accounts','service_account'})
        queue = Queue(Drive(config['service_account']),Central(origin),multi_call,config,db_path)
        print('Drive queue enabled (review only)',flush=True)
        while not stop.is_set():
            try:
                queue.poll()
            except Exception as exc:
                print('Drive queue blocked: '+diagnostic(exc),flush=True)
            stop.wait(30)
    except Exception as exc:
        print('Drive queue disabled: '+diagnostic(exc),flush=True)
    finally:
        if queue:
            queue.close()
