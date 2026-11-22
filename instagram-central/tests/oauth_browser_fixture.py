"""Disposable local HTTPS/proxy fixture. Never contact a provider or real HA."""
import base64
import hashlib
import html
import ipaddress
import json
import logging
import os
from pathlib import Path
import socket
import ssl
import sys
import threading
import time
from datetime import datetime, timedelta, timezone
from http.client import HTTPConnection
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlencode, urlsplit

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import server

server.DATA_DIR = Path(sys.argv[1]); server.DB_PATH = server.DATA_DIR / 'instagram.sqlite3'
CONFIG = {'instagram_account_id': '11111111', 'panel_password': 'oauth_fixture_password_only_123',
          'meta_oauth_enabled': True, 'meta_app_id': '12345678', 'meta_login_config_id': '87654321',
          'meta_app_secret': 'SYNTHETIC_UNUSED_APP_SECRET', 'meta_graph_version': 'v27.0',
          'ingress_enabled': False, 'drafts_enabled': False, 'meta_oauth_redirect_uri': ''}
server.settings = lambda: dict(CONFIG)
server.LOGGER.addHandler(logging.NullHandler()); server.LOGGER.propagate = False
state = {'kind': 'same_https', 'obs': {}, 'exchanges': 0, 'routing_reads': 0, 'inbox_reads': 0,
         'inbox_mode': 'normal', 'inbox_direct_reads': 0}


def exchange(code, cfg):
    if code != 'synthetic-browser-code': raise AssertionError('Provider calls forbidden')
    state['exchanges'] += 1
    return {'access_token': 'SYNTHETIC_TOKEN_NOT_REAL_' * 2, 'expires_in': 0}


server.oauth_meta.exchange_code = exchange
def inbox_content(account,mid='SYNTHETIC_SHARED_MID'):
    return [
        {'id':mid,'message':'SYNTHETIC '+account+' <script>not_script()</script>',
         'created_time':'2026-11-21T23:00:00-03:00','from':{'id':'99999999'},'to':{'data':[{'id':account}]}},
        {'id':'SYNTHETIC_OUT','message':'OUTGOING_NEVER_IMPORTED',
         'created_time':'2026-11-21T23:01:00-03:00','from':{'id':account},'to':{'data':[{'id':'99999999'}]}}
    ]
def graph(version, path, token, **kwargs):
    if '--inbox' in sys.argv and state.get('reject_token'):
        raise server.instagram_connection.GraphError('token_invalid', 400, 190)
    if ('--inbox' in sys.argv and path in ('/11111111/conversations', '/22222222/conversations')
            and kwargs.get('fields') == server.instagram_connection.INBOX_FIELDS):
        state['inbox_reads'] += 1
        account = path.split('/')[1]
        if state['inbox_mode']=='normal':
            return {'data':[{'id':'PRIVATE_CONVERSATION','messages':{'data':inbox_content(account)}}]}
        rows=[{'id':'PRIVATE_'+account}]
        if state['inbox_mode']=='partial':rows.insert(0,{'id':'PRIVATE_UNAVAILABLE'})
        if state['inbox_mode']=='all_unavailable':rows=[{'id':'PRIVATE_UNAVAILABLE'}]
        return {'data':rows}
    if '--inbox' in sys.argv and path.startswith('/PRIVATE_') and path.endswith('/messages') and kwargs.get('fields')==server.instagram_connection.MESSAGE_FIELDS:
        state['inbox_direct_reads']+=1
        if path=='/PRIVATE_UNAVAILABLE/messages':raise server.instagram_connection.GraphError('permission_denied',400,200)
        account=path.removeprefix('/PRIVATE_').removesuffix('/messages')
        if account not in ('11111111','22222222'):raise AssertionError('Unexpected synthetic conversation')
        return {'data':inbox_content(account,'SYNTHETIC_'+state['inbox_mode']+'_'+account)}
    if path == '/me/assigned_instagram_accounts':
        return {'data':[{'id':'11111111','username':'umdoislab'}, {'id':'22222222','username':'second_review'}, {'id':'33333333','username':'third_review'}]}
    if path == '/me': return {'client_business_id':'44444444'}
    if path == '/11111111/subscribed_apps' and kwargs.get('method', 'GET') == 'GET':
        return {'data':[{'app_id':CONFIG['meta_app_id'],'subscribed_fields':['messages']}]}
    if path == '/11111111/conversations' and kwargs.get('method', 'GET') == 'GET':
        if '--routing' in sys.argv and kwargs.get('fields') == server.instagram_connection.ROUTING_FIELDS:
            state['routing_reads'] += 1
            return {'data': [
                {'id': 'PRIVATE_OWNED_ID', 'is_owner': True, 'updated_time': '2026-11-22T05:41:00-03:00'},
                {'id': 'PRIVATE_OTHER_ID', 'is_owner': False},
                {'id': 'PRIVATE_UNSPECIFIED_ID', 'messages': {'data': [{'text': 'PRIVATE_MESSAGE'}]}}
            ]}
        assert kwargs.get('fields') == {'platform':'instagram','fields':'id','limit':'1'}
        return {'data':[{'id':'SYNTHETIC_CONVERSATION_ID_NEVER_RENDERED'}]}
    if path == '/debug_token':
        return {'data':{'is_valid':True,'app_id':CONFIG['meta_app_id'],
                        'scopes':['instagram_basic','instagram_manage_messages']}}
    if path == '/12345678/subscriptions':
        return {'data':[{'object':'instagram','active':True,'fields':[{'name':'messages'}],
                         'callback_url':CONFIG['public_base_url']+'/webhook/instagram'}]}
    raise AssertionError('Unexpected provider operation')

server.instagram_connection.request_graph = graph
if '--integration' in sys.argv:
    from editorial_publishing import PublisherHub
    from test_editorial_publishing import FakeMeta
    fake_meta = FakeMeta()
    fake_meta.delivery = server.PUBLICATION_DELIVERY
    integration_clock = [time.time()]
    server.PUBLICATIONS = PublisherHub(server.meta_configuration_for_business, server._meta_credential,
        server.editorial_store_for_business, server.publication_businesses, server.PUBLICATION_DELIVERY,
        api_factory=fake_meta.client, checker=lambda cfg, *a, **kw: {'origin': CONFIG['public_base_url'], 'stories': True},
        clock=lambda: integration_clock[0])
original_connect = socket.socket.connect
original_dns = socket.getaddrinfo


def allowed(host):
    if host == 'localhost': return True
    try: return ipaddress.ip_address(host).is_loopback
    except ValueError: return False


def connect(sock, address):
    if isinstance(address, tuple) and not allowed(address[0]): raise AssertionError('External connection forbidden')
    return original_connect(sock, address)


def resolve(host, *args, **kwargs):
    if not allowed(host): raise AssertionError('External DNS forbidden')
    return original_dns(host, *args, **kwargs)


socket.socket.connect = connect; socket.getaddrinfo = resolve
backend = ThreadingHTTPServer(('127.0.0.1', 0), server.Handler)


class Proxy(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        route = urlsplit(self.path)
        if route.path in ('/worker-lab', '/sw-modern.js'):
            if route.path == '/worker-lab':
                raw = b'<!doctype html><title>Worker fixture</title><p>Synthetic old origin</p>'
                kind = 'text/html'
            else:
                # Deliberately replay a synthetic redirect without Set-Cookie.
                # This models interference; it is not HA's installed source.
                callback = CONFIG['meta_oauth_redirect_uri'] + '?probe=' + 'A' * 43
                raw = ("self.addEventListener('install',()=>self.skipWaiting());"
                       "self.addEventListener('activate',e=>e.waitUntil(clients.claim()));"
                       "self.addEventListener('fetch',e=>{if(new URL(e.request.url).pathname==='/oauth/meta/start')"
                       "e.respondWith(Promise.resolve(Response.redirect(" + json.dumps(callback) + ",302)));});").encode()
                kind = 'application/javascript'
            self.send_response(200); self.send_header('Content-Type', kind)
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if route.path == '/favicon.ico': self.send_response(204); self.end_headers(); return
        if route.path == '/fake-authorize':
            value = parse_qs(route.query)['state'][0]
            callback = CONFIG['meta_oauth_redirect_uri'] + '?' + urlencode({'state': value, 'code': 'synthetic-browser-code'})
            raw = ('<!doctype html><title>Provider stub</title><a href="' + html.escape(callback, quote=True) + '">Voltar à Central</a>').encode()
            self.send_response(200); self.send_header('Content-Type', 'text/html; charset=utf-8')
            self.send_header('Content-Length', str(len(raw))); self.end_headers(); self.wfile.write(raw); return
        if route.path not in ('/oauth/meta/start', '/oauth/meta/callback', '/panel', '/panel/account-context', '/accounts', '/webhook/instagram') and not route.path.startswith(('/accounts/', '/editorial/')):
            self.send_response(404); self.end_headers(); return
        cookie = self.headers.get('Cookie', '')
        headers = {'Host': self.headers.get('Host', ''), 'X-Forwarded-Proto': 'https'}
        if state['kind'] == 'wrong_forwarded_https' and route.path.endswith('callback'): headers['X-Forwarded-Proto'] = 'http'
        if self.headers.get('Authorization'): headers['Authorization'] = self.headers['Authorization']
        if cookie and not (state['kind'] == 'strip_request_cookie' and route.path.endswith('callback')):
            headers['Cookie'] = cookie
        if route.path.endswith('callback'):
            diagnostic = server.oauth_meta.cookie_diagnostics(route.query, cookie, probe=True)
            upstream = server.oauth_meta.cookie_diagnostics(route.query, headers.get('Cookie', ''), probe=True)
            state['obs'].update(browserAnyCookie=bool(cookie), browserExpectedCookie=diagnostic['expected_cookie_present'],
                                upstreamAnyCookie=bool(headers.get('Cookie')), upstreamExpectedCookie=upstream['expected_cookie_present'])
        client = HTTPConnection('127.0.0.1', backend.server_address[1], timeout=5)
        try:
            if state['kind'] == 'split_cookie_header' and route.path.endswith('callback'):
                client.putrequest('GET', self.path, skip_host=True)
                for name, value in headers.items():
                    if name != 'Cookie': client.putheader(name, value)
                client.putheader('Cookie', 'unrelated=synthetic')
                if headers.get('Cookie'): client.putheader('Cookie', headers['Cookie'])
                client.endheaders()
            else:
                client.request('GET', self.path, headers=headers)
            response = client.getresponse()
            raw = response.read(); result_headers = response.getheaders(); status = response.status
        finally: client.close()
        self.send_response(status)
        for key, value in result_headers:
            if key.lower() in ('server', 'date', 'connection'): continue
            if route.path.endswith('start') and key.lower() == 'set-cookie':
                state['obs']['backendSetCookie'] = True
                if state['kind'] == 'strip_set_cookie': state['obs']['deliveredSetCookie'] = False; continue
                state['obs']['deliveredSetCookie'] = True
            if route.path.endswith('start') and key.lower() == 'location' and state['kind'] == 'rewrite_nonce':
                value = state['alternate']
            self.send_header(key, value)
        self.end_headers(); self.wfile.write(raw)

    def do_POST(self):
        if self.path not in ('/auth/login', '/auth/logout', '/accounts', '/panel/meta/check') and not self.path.startswith(('/accounts/', '/editorial/')):
            self.send_response(404); self.end_headers(); return
        raw = self.rfile.read(int(self.headers.get('Content-Length', '0')))
        headers = {'Host': self.headers.get('Host', ''), 'X-Forwarded-Proto': 'https',
                   'Content-Type': self.headers.get('Content-Type', '')}
        for key in ('Cookie', 'Origin', 'Authorization', 'X-CSRF-Token', 'X-Editorial-Action', 'X-Import-Id', 'X-Media-Index', 'X-Meta-Diagnostic', 'X-Meta-Inbox'):
            if self.headers.get(key): headers[key] = self.headers[key]
        client = HTTPConnection('127.0.0.1', backend.server_address[1], timeout=5)
        try:
            client.request('POST', self.path, raw, headers)
            response = client.getresponse(); body = response.read()
            self.send_response(response.status)
            for key, value in response.getheaders():
                if key.lower() not in ('server', 'date', 'connection'): self.send_header(key, value)
            self.end_headers(); self.wfile.write(body)
        finally: client.close()


class Control(BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        if self.path.startswith('/set/'):
            state['kind'] = self.path.split('/')[-1]; state['obs'] = {}; CONFIG['meta_login_config_id'] = '87654321'
            CONFIG['public_base_url'] = ''
            CONFIG['meta_oauth_redirect_uri'] = 'https://probe-review.test:' + str(first.server_address[1]) + '/oauth/meta/callback'
            if state['kind'] == 'dedicated_host':
                CONFIG['public_base_url'] = 'https://central.probe-review.test:' + str(first.server_address[1])
                CONFIG['meta_oauth_redirect_uri'] = CONFIG['public_base_url'] + '/oauth/meta/callback'
            state['alternate'] = server.oauth_meta.start_cookie_probe(CONFIG)[0]
            data = {}
        elif self.path == '/drift': CONFIG['meta_login_config_id'] = '98765432'; data = {}
        elif self.path == '/routing-observe' and '--routing' in sys.argv:
            data = {'routingReads': state['routing_reads']}
        elif self.path == '/inbox-reject-token' and '--inbox' in sys.argv:
            state['reject_token'] = True
            data = {}
        elif self.path in ('/inbox-mode/no_expansion','/inbox-mode/partial','/inbox-mode/all_unavailable') and '--inbox' in sys.argv:
            state['inbox_mode']=self.path.rsplit('/',1)[1];data={}
        elif self.path == '/inbox-observe' and '--inbox' in sys.argv:
            with server.database() as conn:
                data = {'inboxReads': state['inbox_reads'], 'directReads':state['inbox_direct_reads'],
                        'stored': conn.execute('SELECT COUNT(*) FROM inbound').fetchone()[0],
                        'queued': len(server.list_pending(account_id='11111111'))}
        elif self.path == '/integration-observe' and '--integration' in sys.argv:
            for business in server.publication_businesses():
                for _ in range(8):
                    server.PUBLICATIONS.step(business)
                    integration_clock[0] += 20
            data = {'publishedCount': len(fake_meta.published)}
        else:
            primary = server.DATA_DIR / server.oauth_meta.TOKEN_FILENAME
            data = {**state['obs'], 'exchanges': state['exchanges'],
                    'primaryDigest': hashlib.sha256(primary.read_bytes()).hexdigest() if primary.exists() else None}
        raw = json.dumps(data).encode(); self.send_response(200); self.send_header('Content-Length', str(len(raw)))
        self.end_headers(); self.wfile.write(raw)


first = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
second = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
plain = ThreadingHTTPServer(('127.0.0.1', 0), Proxy)
control = ThreadingHTTPServer(('127.0.0.1', 0), Control)
CONFIG['meta_oauth_redirect_uri'] = 'https://probe-review.test:' + str(first.server_address[1]) + '/oauth/meta/callback'
server.oauth_meta.AUTHORIZE = 'https://meta-review.test:' + str(second.server_address[1]) + '/fake-authorize'
key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
subject = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'probe-review.test')])
cert = (x509.CertificateBuilder().subject_name(subject).issuer_name(subject).public_key(key.public_key())
        .serial_number(x509.random_serial_number()).not_valid_before(datetime.now(timezone.utc)-timedelta(days=1))
        .not_valid_after(datetime.now(timezone.utc)+timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName(name) for name in
                       ('probe-review.test', 'central.probe-review.test', 'meta-review.test')]), critical=False).sign(key, hashes.SHA256()))
fd = os.memfd_create('offline-oauth-fixture')
os.write(fd, cert.public_bytes(serialization.Encoding.PEM) + key.private_bytes(serialization.Encoding.PEM,
         serialization.PrivateFormat.TraditionalOpenSSL, serialization.NoEncryption()))
context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER); context.load_cert_chain('/proc/self/fd/' + str(fd))
first.socket = context.wrap_socket(first.socket, server_side=True)
second.socket = context.wrap_socket(second.socket, server_side=True)
for http in (backend, first, second, plain): threading.Thread(target=http.serve_forever, daemon=True).start()
print(json.dumps({'control': control.server_address[1], 'https': first.server_address[1],
                  'other': second.server_address[1], 'http': plain.server_address[1]}), flush=True)
control.serve_forever()
