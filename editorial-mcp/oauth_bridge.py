"""Restricted OAuth code+PKCE bridge; existing Central connection is the grant.
No credentials on disk; restart invalidates OAuth sessions. No general IdP."""
import base64
import hashlib
import hmac
import html
import re
import secrets
import threading
import time
from urllib.parse import urlencode, parse_qs

CLIENT = 'https://chatgpt.com/oauth/client.json'
REDIRECT = 'https://chatgpt.com/connector_platform_oauth_redirect'
SCOPE = 'editorial:review'
VERIFIER = re.compile(r'[A-Za-z0-9_.~-]{43,128}\Z')
CHALLENGE = re.compile(r'[A-Za-z0-9_-]{43}\Z')
OPAQUE = re.compile(r'[A-Za-z0-9_-]{43}\Z')


class Denied(ValueError):
    pass


def require(ok):
    if not ok:
        raise Denied('invalid_request')


def digest(value):
    return hashlib.sha256(value.encode('ascii')).hexdigest()


def params(raw):
    require(len(raw) <= 8192)
    try:
        p = parse_qs(raw, keep_blank_values=True, strict_parsing=True, max_num_fields=20, errors='strict')
    except (ValueError, UnicodeError):
        raise Denied('invalid_request') from None
    require(all(len(v) == 1 for v in p.values()))
    return {k:v[0] for k,v in p.items()}


class OAuth:
    def __init__(self, issuer, clock=time.time):
        self.issuer, self.resource, self.clock = issuer, issuer+'/mcp-oauth', clock
        self.lock = threading.RLock()
        self.pending, self.codes, self.tokens, self.refresh = {}, {}, {}, {}

    def resource_metadata(self):
        return {'resource':self.resource,'authorization_servers':[self.issuer],
                'scopes_supported':[SCOPE],'bearer_methods_supported':['header']}

    def metadata(self):
        return {'issuer':self.issuer,'authorization_response_iss_parameter_supported':True,
                'authorization_endpoint':self.issuer+'/oauth/authorize',
                'token_endpoint':self.issuer+'/oauth/token',
                'client_id_metadata_document_supported':True,
                'token_endpoint_auth_methods_supported':['none'],
                'response_types_supported':['code'],'grant_types_supported':['authorization_code','refresh_token'],
                'code_challenge_methods_supported':['S256'],'scopes_supported':[SCOPE]}

    def challenge(self):
        return {'WWW-Authenticate':'Bearer resource_metadata="'+self.issuer+'/.well-known/oauth-protected-resource/mcp-oauth", scope="'+SCOPE+'"'}

    def purge(self):
        now = self.clock()
        for table in (self.pending,self.codes,self.tokens,self.refresh):
            for k,v in list(table.items()):
                if v[0] <= now:
                    del table[k]

    def put(self, table, expiry, *data):
        self.purge()
        require(len(table)<128)
        value=secrets.token_urlsafe(32)
        table[digest(value)]=(expiry,*data)
        return value

    def take(self, table, value):
        require(isinstance(value,str) and OPAQUE.fullmatch(value))
        self.purge()
        record=table.pop(digest(value),None)
        require(record is not None)
        return record

    def begin(self, p):
        require(p.get('client_id')==CLIENT and p.get('redirect_uri')==REDIRECT and
                p.get('response_type')=='code' and p.get('resource')==self.resource and
                p.get('scope',SCOPE)==SCOPE and p.get('code_challenge_method')=='S256' and
                CHALLENGE.fullmatch(p.get('code_challenge','')) and 1<=len(p.get('state',''))<=1024)
        with self.lock:
            form=self.put(self.pending,self.clock()+300,p['state'],p['code_challenge'])
        return ('<!doctype html><html lang="pt-BR"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
                '<title>Autorizar Central Editorial</title><h1>Conectar ChatGPT à Central Editorial</h1>'
                '<p>Use uma chave exclusiva de conexão cei2 emitida na Central. Autoriza somente revisão nas contas concedidas. Não publica.</p>'
                '<form action="/oauth/authorize" method="post"><input type="hidden" name="form" value="'+html.escape(form)+'">'
                '<label>Chave da conexão <input type="password" name="key" required autocomplete="off" maxlength="120"></label>'
                '<button type="submit">Autorizar revisão</button></form></html>').encode()

    def authorize(self, p, validate):
        require(set(p)=={'form','key'})
        with self.lock:
            _,state,challenge=self.take(self.pending,p['form'])
        key=p['key']
        validate(key)
        with self.lock:
            code=self.put(self.codes,self.clock()+60,key,challenge)
        return REDIRECT+'?'+urlencode({'code':code,'state':state,'iss':self.issuer})

    def token(self,p):
        require(p.get('client_id')==CLIENT and p.get('resource')==self.resource and
                p.get('scope',SCOPE)==SCOPE and not any(k in p for k in ('client_secret','client_assertion','client_assertion_type')))
        with self.lock:
            if p.get('grant_type')=='authorization_code':
                require(p.get('redirect_uri')==REDIRECT and VERIFIER.fullmatch(p.get('code_verifier','')))
                _,key,challenge=self.take(self.codes,p.get('code'))
                actual=base64.urlsafe_b64encode(hashlib.sha256(p['code_verifier'].encode('ascii')).digest()).decode().rstrip('=')
                require(hmac.compare_digest(challenge,actual))
                deadline=self.clock()+7*86400
            elif p.get('grant_type')=='refresh_token':
                require(p.get('scope',SCOPE)==SCOPE)
                deadline,key,old=self.take(self.refresh,p.get('refresh_token'))
                self.tokens.pop(old,None)
            else:
                raise Denied('unsupported_grant_type')
            now=self.clock()
            expires=min(deadline,now+3600)
            access=self.put(self.tokens,expires,key)
            refresh=self.put(self.refresh,deadline,key,digest(access))
            return {'access_token':access,'token_type':'Bearer','expires_in':int(expires-now),
                    'refresh_token':refresh,'scope':SCOPE}

    def resolve(self, value):
        require(isinstance(value,str) and OPAQUE.fullmatch(value))
        with self.lock:
            self.purge()
            record=self.tokens.get(digest(value))
            require(record is not None)
            return record[1]
