import base64
import hashlib
import json
import re
import threading
import unittest
from http.client import HTTPConnection
from urllib.parse import urlencode, urlsplit, parse_qs
from oauth_bridge import OAuth, CLIENT, REDIRECT, SCOPE, Denied
from test_server import FakeCentral, MULTI
from server import make_server

ISSUER='https://editorial.example.ts.net'
VERIFIER='a'*43
CHALLENGE=base64.urlsafe_b64encode(hashlib.sha256(VERIFIER.encode()).digest()).decode().rstrip('=')
def request_params():
    return dict(client_id=CLIENT,redirect_uri=REDIRECT,response_type='code',resource=ISSUER+'/mcp-oauth',scope=SCOPE,code_challenge_method='S256',code_challenge=CHALLENGE,state='test-state')
def exchange_params(code):
    return dict(client_id=CLIENT,redirect_uri=REDIRECT,resource=ISSUER+'/mcp-oauth',grant_type='authorization_code',code_verifier=VERIFIER,code=code)
def form_id(body):
    return re.search(rb'name="form" value="([^"]+)"',body).group(1).decode()

class OAuthState(unittest.TestCase):
    def setUp(self):
        self.now=1000
        self.auth=OAuth(ISSUER,lambda:self.now)
    def code(self):
        form=form_id(self.auth.begin(request_params()))
        loc=self.auth.authorize({'form':form,'key':MULTI},lambda k:self.assertEqual(k,MULTI))
        self.assertEqual(parse_qs(urlsplit(loc).query)['iss'],[ISSUER])
        with self.assertRaises(Denied): self.auth.authorize({'form':form,'key':MULTI},lambda k:None)
        return parse_qs(urlsplit(loc).query)['code'][0]
    def test_grant_expiry_refresh_and_replay(self):
        code=self.code()
        token=self.auth.token(exchange_params(code))
        self.assertEqual(self.auth.resolve(token['access_token']),MULTI)
        with self.assertRaises(Denied):self.auth.token(exchange_params(code))
        self.now+=3601
        with self.assertRaises(Denied):self.auth.resolve(token['access_token'])
        p=dict(client_id=CLIENT,resource=ISSUER+'/mcp-oauth',grant_type='refresh_token',refresh_token=token['refresh_token'])
        updated=self.auth.token(p)
        self.assertEqual(self.auth.resolve(updated['access_token']),MULTI)
        with self.assertRaises(Denied):self.auth.token(p)
    def test_reject_wrong_redirect_client_scope_resource_and_pkce(self):
        for key,value in [('client_id','evil'),('redirect_uri','https://evil.example'),('scope','publish'),('resource','https://evil.example'),('code_challenge_method','plain')]:
            with self.assertRaises(Denied):self.auth.begin({**request_params(),key:value})
        code=self.code()
        with self.assertRaises(Denied):self.auth.token({**exchange_params(code),'code_verifier':'b'*43})
        with self.assertRaises(Denied):self.auth.token(exchange_params(code))
    def test_expired_code(self):
        code=self.code();self.now+=61
        with self.assertRaises(Denied): self.auth.token(exchange_params(code))

class OAuthHTTP(unittest.TestCase):
    def setUp(self):
        self.http=make_server('https://central.example',port=0,public_host='editorial.example.ts.net')
        self.fake=self.http.central=FakeCentral()
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
        self.addCleanup(self.stop)
    def stop(self):
        self.http.shutdown();self.http.server_close();self.thread.join()
    def req(self,method,path,body=None,headers=None):
        conn=HTTPConnection('127.0.0.1',self.http.server_port,timeout=5)
        try:
            conn.request(method,path,body,headers or {})
            r=conn.getresponse(); return r.status,dict(r.getheaders()),r.read()
        finally:conn.close()
    def test_full_http(self):
        message=json.dumps({'jsonrpc':'2.0','id':1,'method':'tools/list','params':{}})
        h={'Content-Type':'application/json'}
        status,headers,_=self.req('POST','/mcp-oauth',message,h)
        self.assertEqual(status,401);self.assertIn('resource_metadata',headers['WWW-Authenticate'])
        self.assertEqual(self.req('POST','/mcp',message,h)[0],403)
        self.assertEqual(self.req('GET','/.well-known/oauth-authorization-server')[0],200)
        self.assertEqual(self.req('GET','/.well-known/oauth-protected-resource/mcp-oauth')[0],200)
        status,_,body=self.req('GET','/oauth/authorize?'+urlencode(request_params()))
        self.assertEqual(status,200)
        form_id_value=form_id(body)
        form={'Content-Type':'application/x-www-form-urlencoded','Origin':ISSUER}
        status,headers,_=self.req('POST','/oauth/authorize',urlencode({'form':form_id_value,'key':MULTI}),form)
        self.assertEqual(status,303)
        code=parse_qs(urlsplit(headers['Location']).query)['code'][0]
        status,_,body=self.req('POST','/oauth/token',urlencode(exchange_params(code)),{'Content-Type':'application/x-www-form-urlencoded'})
        self.assertEqual(status,200)
        token=json.loads(body)['access_token']
        status,_,body=self.req('POST','/mcp-oauth',message,{**h,'Authorization':'Bearer '+token})
        self.assertEqual(status,200)
        self.assertTrue(all(t['securitySchemes']==[{'type':'oauth2','scopes':[SCOPE]}] for t in json.loads(body)['result']['tools']))
        self.assertEqual(self.req('POST','/mcp-oauth',message,{**h,'X-API-Key':MULTI})[0],401)
        self.assertEqual(self.req('POST','/mcp',message,{**h,'X-API-Key':MULTI})[0],200)
        self.fake.call=lambda *a,**kw: (_ for _ in ()).throw(__import__('server').Refused('revoked'))
        self.assertEqual(self.req('POST','/mcp-oauth',message,{**h,'Authorization':'Bearer '+token})[0],401)
