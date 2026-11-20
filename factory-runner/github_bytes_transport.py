"""GitHub transport for validated bytes. No project checkout, script or shell.

Production URL is fixed; TLS verified, redirects refused, bounded JSON responses.
Network writes require a separate trusted gate (disabled in the HA integration).
GraphQL updateRefs.beforeOid supplies atomic compare-and-swap, with force=false.
"""
import base64
import datetime
import hashlib
import json
import re
import socket
import time
import urllib.error
import urllib.request
from publication_contract import PublicationError,git_oid
from owner_approval import protected_file


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):return None


class GitHubBytesHTTP:
    base='https://api.github.com'
    def __init__(self,token_file,write_gate):
        self.deadline=None
        self.token_path=protected_file(token_file)
        self.write_gate=write_gate
        self.opener=urllib.request.build_opener(NoRedirect())

    def request(self,method,path,body=None):
        if method not in ('GET','POST') or not path.startswith('/') or '://' in path or '#' in path:
            raise PublicationError('invalid_transport_path')
        if '?' in path and not (method=='GET' and re.fullmatch(
                r'/repos/[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+/git/trees/[a-f0-9]{40}\?recursive=1',path)):
            raise PublicationError('invalid_transport_query')
        if method!='GET':self.write_gate()
        # Read secret only inside the trusted transport process. Never put it in
        # argv, environment, bundles, receipts or error messages.
        if self.deadline is not None and time.monotonic()>=self.deadline:raise PublicationError('transport_deadline')
        token=self.token_path.read_text().strip()
        if not re.fullmatch('[A-Za-z0-9_]+',token):raise PublicationError('invalid_transport_credential')
        headers={'Authorization':'Bearer '+token,'Accept':'application/vnd.github+json',
                 'X-GitHub-Api-Version':'2022-11-28','Content-Type':'application/json'}
        payload=None if body is None else json.dumps(body,separators=(',',':')).encode()
        req=urllib.request.Request(self.base+path,data=payload,headers=headers,method=method)
        try:
            timeout=15 if self.deadline is None else max(.1,min(15,self.deadline-time.monotonic()))
            with self.opener.open(req,timeout=timeout) as response:
                chunks=[];length=0
                while True:
                    if self.deadline is not None and time.monotonic()>=self.deadline:raise PublicationError('transport_deadline')
                    chunk=response.read(65536)
                    if not chunk:break
                    length+=len(chunk)
                    if length>48*1024*1024:raise PublicationError('remote_response_budget')
                    chunks.append(chunk)
                result=json.loads(b''.join(chunks))
        except urllib.error.HTTPError as exc:
            code=exc.code;exc.close()
            raise PublicationError('remote_http_'+str(code)) from None
        except (urllib.error.URLError,socket.timeout,OSError,ValueError) as exc:
            raise PublicationError('remote_response_unavailable') from None
        if not isinstance(result,dict):raise PublicationError('invalid_remote_document')
        return result


def tree_oid(entries):
    """Hash the complete flattened tree independently of the GitHub response."""
    root={}
    for path,item in entries.items():
        parts=path.split('/')
        if any(not part or part in ('.','..') or '\0' in part for part in parts):
            raise PublicationError('invalid_remote_tree_path')
        node=root
        for part in parts[:-1]:
            if part in node and not isinstance(node[part],dict):raise PublicationError('remote_tree_collision')
            node=node.setdefault(part,{})
        if parts[-1] in node:raise PublicationError('remote_tree_collision')
        if item['mode'] not in ('100644','100755','120000','160000') or not re.fullmatch('[a-f0-9]{40}',item['sha']):
            raise PublicationError('invalid_remote_tree_entry')
        node[parts[-1]]=(item['mode'],item['sha'])
    def walk(node):
        data=b''
        for name,value in sorted(node.items(),key=lambda item:(item[0]+('/' if isinstance(item[1],dict) else '')).encode()):
            mode,sha=('40000',walk(value)) if isinstance(value,dict) else value
            data+=mode.encode()+b' '+name.encode()+b'\0'+bytes.fromhex(sha)
        return git_oid('tree',data)
    return walk(root)


class GitHubBytesTransport:
    def __init__(self,http,repository,ref):
        if (not re.fullmatch('[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+',repository)
                or not re.fullmatch('refs/heads/[A-Za-z0-9_/-]+',ref)
                or '..' in ref or '//' in ref):raise PublicationError('invalid_remote_destination')
        self.http=http;self.repo=repository;self.ref=ref;self.prefix='/repos/'+repository

    def head(self):
        doc=self.http.request('GET',self.prefix+'/git/ref/'+self.ref.removeprefix('refs/'))
        if doc.get('ref')!=self.ref or doc.get('object',{}).get('type')!='commit':
            raise PublicationError('remote_ref_mismatch')
        sha=doc['object']['sha']
        if not isinstance(sha,str) or not re.fullmatch('[a-f0-9]{40}',sha):raise PublicationError('invalid_remote_head')
        return sha

    def read_commit(self,sha):
        if not re.fullmatch('[a-f0-9]{40}',sha):raise PublicationError('invalid_commit')
        doc=self.http.request('GET',self.prefix+'/git/commits/'+sha)
        if doc.get('sha')!=sha:raise PublicationError('remote_commit_mismatch')
        tree=doc.get('tree',{}).get('sha')
        if not isinstance(tree,str) or not re.fullmatch('[a-f0-9]{40}',tree):raise PublicationError('invalid_remote_tree')
        return doc

    def read_tree(self,tree):
        # Use GraphQL recursive REST query through a fixed endpoint field, not a
        # user-provided URL. Request parameters are fixed by this implementation.
        doc=self.http.request('GET',self.prefix+'/git/trees/'+tree+'?recursive=1')
        if doc.get('truncated') is not False or doc.get('sha')!=tree or not isinstance(doc.get('tree'),list) or len(doc['tree'])>20000:
            raise PublicationError('remote_tree_incomplete')
        result={}
        for item in doc['tree']:
            if (not isinstance(item,dict) or not isinstance(item.get('path'),str)
                    or not re.fullmatch('[a-f0-9]{40}',str(item.get('sha','')))):
                raise PublicationError('invalid_remote_tree')
            if item.get('type')=='tree':
                if item.get('mode') not in ('040000','40000'):raise PublicationError('invalid_remote_directory_mode')
                continue
            if (item.get('type')=='blob' and item.get('mode') not in ('100644','100755','120000')) or (item.get('type')=='commit' and item.get('mode')!='160000'):
                raise PublicationError('invalid_remote_object_mode')
            if item.get('type') not in ('blob','commit') or item.get('path') in result:
                raise PublicationError('invalid_remote_tree')
            result[item['path']]={key:item[key] for key in ('mode','type','sha')}
        if tree_oid(result)!=tree:raise PublicationError('remote_tree_hash_mismatch')
        return result

    def plan(self,receipt,files):
        if receipt['distribution_repository']!=self.repo or receipt['distribution_ref']!=self.ref:
            raise PublicationError('transport_destination_mismatch')
        expected=receipt['expected_distribution_sha']
        if self.head()!=expected:raise PublicationError('remote_head_conflict')
        commit=self.read_commit(expected);before=self.read_tree(commit['tree']['sha'])
        after={path:dict(item) for path,item in before.items()}
        for path in list(after):
            if path.startswith(receipt['scope']):del after[path]
        for path,item in files.items():after[path]={key:item[key] for key in ('mode','type','sha')}
        changes=[]
        for path in sorted(set(before)|set(after)):
            if before.get(path)==after.get(path):continue
            if not (path.startswith(receipt['scope']) or path in receipt['allowed_shared_paths']):
                raise PublicationError('remote_diff_outside_scope')
            if path.startswith('.github/'):raise PublicationError('workflow_changes_disabled')
            value=after.get(path)
            changes.append({'path':path,**(value if value else {**before[path],'sha':None})})
        if not changes:raise PublicationError('no_changes_to_publish')
        epoch=receipt['created_at']
        if type(epoch) is not int or epoch<0 or epoch>4102444800:raise PublicationError('invalid_receipt_time')
        message='Factory Runner receipt '+__import__('release_receipt').digest(receipt)+' [skip ci]\n'
        identity=f'Factory Runner <factory-runner@localhost.invalid> {epoch} +0000'
        new_tree=tree_oid(after)
        raw=(f'tree {new_tree}\nparent {expected}\nauthor {identity}\ncommitter {identity}\n\n'+message).encode()
        new_commit=git_oid('commit',raw)
        return {'repository':self.repo,'ref':self.ref,'profile_sha256':receipt['profile_sha256'],'expected':expected,'base_tree':commit['tree']['sha'],'tree':new_tree,'commit':new_commit,
                'artifact_sha256':{path:item['sha256'] for path,item in files.items()},'entries':after,'changes':changes,'message':message,'epoch':epoch}

    def upload_objects(self,plan,files,check):
        for item in files.values():
            check()
            doc=self.http.request('POST',self.prefix+'/git/blobs',{'encoding':'base64','content':base64.b64encode(item['data']).decode()})
            if doc.get('sha')!=item['sha']:raise PublicationError('remote_blob_hash_mismatch')
        check()
        tree=self.http.request('POST',self.prefix+'/git/trees',{'base_tree':plan['base_tree'],'tree':plan['changes']})
        if tree.get('sha')!=plan['tree']:raise PublicationError('remote_created_tree_mismatch')
        date=datetime.datetime.fromtimestamp(plan['epoch'],datetime.timezone.utc).isoformat().replace('+00:00','Z')
        actor={'name':'Factory Runner','email':'factory-runner@localhost.invalid','date':date}
        check()
        commit=self.http.request('POST',self.prefix+'/git/commits',{
            'tree':plan['tree'],'parents':[plan['expected']],'message':plan['message'],'author':actor,'committer':actor})
        if commit.get('sha')!=plan['commit']:raise PublicationError('remote_created_commit_mismatch')
        self.verify_objects(plan)

    def verify_objects(self,plan):
        commit=self.read_commit(plan['commit'])
        if (commit['tree']['sha']!=plan['tree'] or [x['sha'] for x in commit.get('parents',[])]!=[plan['expected']]
                or not isinstance(commit.get('message'),str) or commit['message'].rstrip('\n')!=plan['message'].rstrip('\n')):raise PublicationError('remote_commit_provenance_mismatch')
        if self.read_tree(plan['tree'])!=plan['entries']:raise PublicationError('remote_exact_tree_mismatch')
        # Independently download and hash every proposed blob before ref write.
        for path in plan['artifact_sha256']:
            item=plan['entries'][path]
            blob=self.http.request('GET',self.prefix+'/git/blobs/'+item['sha'])
            try:data=base64.b64decode(blob.get('content',''),validate=False)
            except (ValueError,TypeError) as exc:raise PublicationError('invalid_remote_blob') from exc
            if (blob.get('encoding')!='base64' or git_oid('blob',data)!=item['sha']
                    or hashlib.sha256(data).hexdigest()!=plan['artifact_sha256'][path]):
                raise PublicationError('remote_blob_integrity_mismatch')

    def cas(self,plan):
        repo=self.http.request('GET',self.prefix)
        if repo.get('full_name')!=self.repo:raise PublicationError('remote_repository_mismatch')
        repository_id=repo.get('node_id')
        if not isinstance(repository_id,str) or not repository_id or len(repository_id)>200:
            raise PublicationError('remote_repository_identity_missing')
        response=self.http.request('POST','/graphql',{
            'query':'mutation($input:UpdateRefsInput!){updateRefs(input:$input){clientMutationId}}',
            'variables':{'input':{'repositoryId':repository_id,'clientMutationId':plan['commit'],
              'refUpdates':[{'name':self.ref,'beforeOid':plan['expected'],'afterOid':plan['commit'],'force':False}]}}})
        if response.get('errors') or ((response.get('data') or {}).get('updateRefs') or {}).get('clientMutationId')!=plan['commit']:
            raise PublicationError('remote_atomic_cas_refused')

    def verify_published(self,plan):
        if self.head()!=plan['commit']:raise PublicationError('remote_post_cas_conflict')
        self.verify_objects(plan)
        if self.head()!=plan['commit']:raise PublicationError('remote_post_verification_conflict')
