"""Independent Central Editorial MCP bridge. No Meta, filesystem reads or publication tools."""
import base64
import hashlib
import json
import re
import socket
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, parse_qs
from datetime import datetime, timezone, timedelta
from urllib.request import Request, build_opener, HTTPRedirectHandler, ProxyHandler

VERSION = '0.1.2'
PROTOCOLS = ('2025-11-25', '2025-06-18', '2025-03-26')
KEY = re.compile(r'cei1\.([a-z][a-z0-9_-]{1,39})\.[0-9a-f]{32}\.[A-Za-z0-9_-]{43}\Z')
RID = re.compile(r'[A-Za-z0-9_-]{16,100}\Z')
MAX_MEDIA = 4 * 1024 * 1024
MAX_BODY = 6 * 1024 * 1024
MIMES = ('image/png', 'image/jpeg', 'video/mp4')
FORMATS = ('feed', 'carousel', 'story', 'reel')
PROBE = 'mcp_connection_probe_v1'


class Refused(Exception):
    pass


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        return None


class Central:
    def __init__(self, origin):
        u = urlsplit(origin)
        if (u.scheme != 'https' or not u.hostname or u.username or u.password or
                u.path not in ('', '/') or u.query or u.fragment):
            raise ValueError('Origem HTTPS inválida')
        self.origin = origin.rstrip('/')
        self.opener = build_opener(ProxyHandler({}), NoRedirect())

    def call(self, token, action, data, *, request_id=None, index=None, mime=None):
        if action not in ('receipt', 'upload', 'commit'):
            raise Refused('Operação não permitida')
        upload = action == 'upload'
        headers = {'Authorization': 'Bearer ' + token,
                   'X-Editorial-Action': 'import_' + action,
                   'Content-Type': mime if upload else 'application/json'}
        if upload:
            headers.update({'X-Import-Id': request_id, 'X-Media-Index': str(index)})
        path = '/editorial/api/' + ('media' if upload else 'drafts')
        body = data if upload else json.dumps(data).encode()
        try:
            with self.opener.open(Request(self.origin + path, body, headers, method='POST'), timeout=18) as res:
                raw = res.read(65537)
            if len(raw) > 65536:
                raise Refused('Resposta da Central inválida')
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise Refused('Resposta da Central inválida')
            return result
        except HTTPError as exc:
            status = exc.code
            exc.close()
            raise Refused('Central recusou a operação (HTTP %d)' % status) from None
        except (URLError, OSError, ValueError):
            raise Refused('Central indisponível; consulte o mesmo recibo antes de repetir') from None


def receipt(central, token, request):
    if not isinstance(request, str) or not RID.fullmatch(request):
        raise Refused('requestId inválido')
    data = central.call(token, 'receipt', {'requestId': request})
    if type(data.get('found')) is not bool:
        raise Refused('Recibo inválido')
    return data


def safe_receipt(data):
    return {k: v for k, v in data.items() if k in ('found', 'id', 'version',
            'importedVersion', 'contentDigest', 'status', 'published', 'publicationAuthorized')}




def _host_file_url(url):
    """Accept only short-lived, read-only ChatGPT-host file URLs; never log them."""
    if not isinstance(url, str) or len(url) > 8192:
        raise Refused('Referência temporária inválida')
    try:
        u = urlsplit(url)
        host = (u.hostname or '').lower()
        port = u.port
        query = parse_qs(u.query, keep_blank_values=True)
    except ValueError:
        raise Refused('Referência temporária inválida') from None
    if (u.scheme != 'https' or not host.endswith('.oaiusercontent.com') or
            host == 'oaiusercontent.com' or port not in (None, 443) or
            u.username or u.password or u.fragment or not u.path.startswith('/files/') or
            any(part == '..' for part in u.path.split('/'))):
        raise Refused('Somente referências temporárias privadas do host ChatGPT são aceitas')
    if (len(query.get('se', [])) != 1 or len(query.get('sig', [])) != 1 or
            not query['sig'][0] or len(query.get('sp', [])) != 1 or 'r' not in query['sp'][0] or
            len(query.get('sr', [])) != 1 or query['sr'][0] != 'b'):
        raise Refused('A referência não é uma URL temporária de leitura')
    try:
        expiry = datetime.fromisoformat(query['se'][0].replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        if expiry.tzinfo is None or expiry <= now or expiry > now + timedelta(minutes=15):
            raise ValueError()
    except (ValueError, TypeError):
        raise Refused('A referência temporária expirou ou tem validade inválida') from None
    return url


def fetch_host_file(url, mime, expected_size, expected_sha256):
    """Fetch one allowlisted, expiring host URL in memory and verify exact bytes."""
    if mime not in MIMES or type(expected_size) is not int or not 1 <= expected_size <= MAX_MEDIA:
        raise Refused('Manifesto de mídia inválido')
    if not isinstance(expected_sha256, str) or not re.fullmatch(r'[0-9a-f]{64}', expected_sha256):
        raise Refused('SHA-256 esperado inválido')
    _host_file_url(url)
    opener = build_opener(ProxyHandler({}), NoRedirect())
    request = Request(url, headers={'Accept': mime, 'User-Agent': 'CentralEditorialMCP'}, method='GET')
    try:
        with opener.open(request, timeout=15) as response:
            if getattr(response, 'status', 200) != 200:
                raise Refused('Download temporário não confirmado')
            length = response.headers.get('Content-Length')
            if length is not None and (not str(length).isdigit() or int(length) != expected_size):
                raise Refused('Tamanho informado não corresponde ao manifesto')
            raw = response.read(expected_size + 1)
    except HTTPError as exc:
        code = exc.code
        exc.close()
        if code in (401, 403, 404, 410):
            raise Refused('Referência temporária expirou ou foi recusada; gere uma nova referência do mesmo arquivo') from None
        if 300 <= code < 400:
            raise Refused('Redirecionamento de arquivo temporário recusado') from None
        raise Refused('Não foi possível obter o arquivo temporário') from None
    except (URLError, OSError, TimeoutError, ValueError):
        raise Refused('Arquivo temporário indisponível; gere uma nova referência do mesmo arquivo') from None
    if len(raw) != expected_size:
        raise Refused('Tamanho recebido diferente do tamanho aprovado')
    if mime == 'image/png' and not raw.startswith(b'\x89PNG\r\n\x1a\n'):
        raise Refused('Assinatura PNG não corresponde ao manifesto')
    if mime == 'image/jpeg' and not raw.startswith(b'\xff\xd8\xff'):
        raise Refused('Assinatura JPEG não corresponde ao manifesto')
    if mime == 'video/mp4' and (len(raw) < 12 or raw[4:8] != b'ftyp'):
        raise Refused('Contêiner MP4 não corresponde ao manifesto')
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise Refused('SHA-256 recebido diferente do arquivo aprovado')
    return raw


def transfer_host_files(central, token, args):
    keys = {'requestId', 'transferApproved', 'format', 'caption', 'media'}
    if set(args) != keys or args['transferApproved'] is not True:
        raise Refused('Confirme explicitamente o envio para revisão')
    request, fmt, caption, media = (args[k] for k in ('requestId', 'format', 'caption', 'media'))
    if (not isinstance(request, str) or not RID.fullmatch(request) or request == PROBE or
            fmt not in FORMATS or not isinstance(caption, str) or len(caption) > 2200 or
            not isinstance(media, list) or
            not (2 <= len(media) <= 20 if fmt == 'carousel' else len(media) == 1)):
        raise Refused('Manifesto inválido')
    metadata, total = [], 0
    for item in media:
        if (not isinstance(item, dict) or set(item) != {'mime', 'url', 'bytes', 'sha256'} or
                item['mime'] not in MIMES or not isinstance(item['url'], str) or
                not isinstance(item['sha256'], str) or not re.fullmatch(r'[0-9a-f]{64}', item['sha256']) or
                type(item['bytes']) is not int or not 1 <= item['bytes'] <= MAX_MEDIA):
            raise Refused('Referência ou metadados de mídia inválidos')
        if len(item['url']) > 8192:
            raise Refused('Referência temporária inválida')
        total += item['bytes']
        if total > MAX_MEDIA:
            raise Refused('Limite inicial de 4 MiB de mídia por transferência')
        metadata.append({'sha256': item['sha256'], 'mime': item['mime']})
    digest = hashlib.sha256(json.dumps({'format': fmt, 'caption': caption, 'files': metadata},
                                       sort_keys=True).encode()).hexdigest()
    result = receipt(central, token, request)
    if result['found']:
        if result.get('contentDigest') != digest or result.get('status') == 'deleted':
            raise Refused('Recibo em conflito ou excluído; não recriar automaticamente')
        return safe_receipt(result)
    files = []
    for item in media:
        raw = fetch_host_file(item['url'], item['mime'], item['bytes'], item['sha256'])
        files.append((raw, item['mime']))
    ids = []
    for index, (raw, mime) in enumerate(files):
        staged = central.call(token, 'upload', raw, request_id=request, index=index, mime=mime)
        media_id = staged.get('id')
        if not isinstance(media_id, str) or not re.fullmatch(r'[0-9a-f]{32}', media_id):
            raise Refused('Upload não confirmado; consulte o mesmo recibo antes de repetir')
        ids.append(media_id)
    result = central.call(token, 'commit', {'schemaVersion': 1, 'requestId': request,
        'transferApproved': True, 'format': fmt, 'caption': caption, 'mediaIds': ids, 'contentDigest': digest})
    if result.get('found') is not True or result.get('contentDigest') != digest:
        raise Refused('Commit não confirmado; consulte o mesmo recibo antes de repetir')
    return safe_receipt(result)


def transfer(central, token, args):
    keys = {'requestId', 'transferApproved', 'format', 'caption', 'media'}
    if set(args) != keys or args['transferApproved'] is not True:
        raise Refused('Confirme explicitamente o envio para revisão')
    request, fmt, caption, media = (args[k] for k in ('requestId','format','caption','media'))
    if (not isinstance(request, str) or not RID.fullmatch(request) or request == PROBE or
            fmt not in FORMATS or not isinstance(caption, str) or len(caption) > 2200 or
            not isinstance(media, list) or not (2 <= len(media) <= 20 if fmt == 'carousel' else len(media) == 1)):
        raise Refused('Manifesto inválido')
    files, total = [], 0
    for item in media:
        if (not isinstance(item, dict) or set(item) != {'mime', 'base64'} or
                item['mime'] not in MIMES or not isinstance(item['base64'], str)):
            raise Refused('Mídia inválida; forneça bytes reais, não URL ou caminho')
        try:
            raw = base64.b64decode(item['base64'], validate=True)
        except (ValueError, TypeError):
            raise Refused('Base64 inválido') from None
        total += len(raw)
        if not raw or total > MAX_MEDIA:
            raise Refused('Limite inicial de 4 MiB de mídia por transferência')
        files.append((raw, item['mime']))
    digest = hashlib.sha256(json.dumps({'format': fmt, 'caption': caption, 'files': [
        {'sha256': hashlib.sha256(raw).hexdigest(), 'mime': mime} for raw, mime in files]},
        sort_keys=True).encode()).hexdigest()
    result = receipt(central, token, request)
    if result['found']:
        if result.get('contentDigest') != digest or result.get('status') == 'deleted':
            raise Refused('Recibo em conflito ou excluído; não recriar automaticamente')
        return safe_receipt(result)
    ids = []
    for index, (raw, mime) in enumerate(files):
        staged = central.call(token, 'upload', raw, request_id=request, index=index, mime=mime)
        media_id = staged.get('id')
        if not isinstance(media_id, str) or not re.fullmatch(r'[0-9a-f]{32}', media_id):
            raise Refused('Upload não confirmado; consulte o mesmo recibo antes de repetir')
        ids.append(media_id)
    result = central.call(token, 'commit', {'schemaVersion':1, 'requestId':request,
        'transferApproved':True, 'format':fmt, 'caption':caption, 'mediaIds':ids, 'contentDigest':digest})
    if result.get('found') is not True or result.get('contentDigest') != digest:
        raise Refused('Commit não confirmado; consulte o mesmo recibo antes de repetir')
    return safe_receipt(result)


def schema(properties, required):
    return {'type':'object','properties':properties,'required':required,'additionalProperties':False}


REQUEST = {'type':'string','pattern':RID.pattern[:-2] + '$'}
TOOLS = [
    {'name':'consultar_conexao','description':'Verifica a conta vinculada à chave deste conector. Não transfere.',
     'inputSchema':schema({},[]),'annotations':{'readOnlyHint':True}},
    {'name':'consultar_envio','description':'Consulta o recibo da própria conexão, com o mesmo requestId.',
     'inputSchema':schema({'requestId':REQUEST},['requestId']),'annotations':{'readOnlyHint':True}},
    {'name':'enviar_para_revisao','description':'Somente após pedido explícito do usuário para enviar o conteúdo escolhido à conta vinculada. Exige bytes reais em base64; não invente bytes, não use caminhos ou URLs. Nunca publica. Máximo 4 MiB total.',
     'inputSchema':schema({'requestId':REQUEST,'transferApproved':{'type':'boolean','const':True},
        'format':{'type':'string','enum':list(FORMATS)},'caption':{'type':'string','maxLength':2200},
        'media':{'type':'array','minItems':1,'maxItems':20,'items':schema({'mime':{'type':'string','enum':list(MIMES)},
            'base64':{'type':'string','maxLength':5592408}},['mime','base64'])}},
        ['requestId','transferApproved','format','caption','media']),
     'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':True}},
    {'name':'enviar_arquivo_temporario_para_revisao','description':'Após pedido explícito do usuário para enviar o conteúdo escolhido à revisão. Aceita somente URL temporária, assinada e de leitura gerada pelo host ChatGPT para arquivo do conector (subdomínio oaiusercontent.com); não aceita link público do Drive nem URL arbitrária. O Worker baixa em memória, confere tamanho, MIME e SHA-256 e não armazena a imagem. Nunca publica. Não registre nem reutilize a URL temporária. Máximo 4 MiB agregado.',
     'inputSchema':schema({'requestId':REQUEST,'transferApproved':{'type':'boolean','const':True},
        'format':{'type':'string','enum':list(FORMATS)},'caption':{'type':'string','maxLength':2200},
        'media':{'type':'array','minItems':1,'maxItems':20,'items':schema({
            'mime':{'type':'string','enum':list(MIMES)},'url':{'type':'string','maxLength':8192},
            'bytes':{'type':'integer','minimum':1,'maximum':MAX_MEDIA},
            'sha256':{'type':'string','pattern':'^[0-9a-f]{64}
    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0' or not isinstance(request.get('method'), str):
        return 400, {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    method, params = request['method'], request.get('params', {})
    if 'id' not in request:
        return (202, None) if method.startswith('notifications/') else (400, None)
    ident = request['id']
    if type(ident) not in (str, int) or not isinstance(params, dict):
        return 400, {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    response = {'jsonrpc':'2.0','id':ident}
    if method == 'initialize':
        version = params.get('protocolVersion')
        response['result'] = {'protocolVersion':version if version in PROTOCOLS else PROTOCOLS[0],
            'capabilities':{'tools':{}},'serverInfo':{'name':'central-editorial-universal','version':VERSION}}
    elif method == 'ping':
        response['result'] = {}
    elif method == 'tools/list':
        response['result'] = {'tools':TOOLS}
    elif method == 'tools/call':
        args, name = params.get('arguments', {}), params.get('name')
        try:
            if not isinstance(args, dict):
                raise Refused('Argumentos inválidos')
            if name == 'consultar_conexao' and not args:
                result = {'connected':True,'account':KEY.fullmatch(token)[1],'publishingAvailable':False}
            elif name == 'consultar_envio' and set(args) == {'requestId'}:
                result = safe_receipt(receipt(central, token, args['requestId']))
            elif name == 'enviar_para_revisao':
                result = transfer(central, token, args)
            elif name == 'enviar_arquivo_temporario_para_revisao':
                result = transfer_host_files(central, token, args)
            else:
                raise Refused('Ferramenta ou argumentos inválidos')
            response['result'] = {'content':[{'type':'text','text':json.dumps(result, ensure_ascii=False)}]}
        except Refused as exc:
            response['result'] = {'content':[{'type':'text','text':str(exc)}],'isError':True}
    else:
        response['error'] = {'code':-32601,'message':'Method not found'}
    return 200, response


class Server(ThreadingHTTPServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(4)
    def process_request(self, request, address):
        if not self.slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(20)
        super().setup()

    def reply(self, status, body=None):
        raw = b'' if body is None else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Connection','close')
        if status == 405:
            self.send_header('Allow','POST')
        self.end_headers()
        self.close_connection = True
        if raw:
            self.wfile.write(raw)

    def valid_route(self):
        if self.path != '/mcp':
            self.reply(404); return False
        hosts = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        if (len(hosts) != 1 or hosts[0].lower() not in self.server.allowed_hosts or
                len(origins) > 1 or origins and origins[0] not in self.server.allowed_origins):
            self.reply(403); return False
        return True

    def do_GET(self):
        if self.valid_route(): self.reply(405)
    do_DELETE = do_GET

    def do_POST(self):
        if not self.valid_route(): return
        keys = self.headers.get_all('X-Editorial-Key', [])
        if len(keys) != 1 or not KEY.fullmatch(keys[0]):
            return self.reply(403)
        protocol = self.headers.get('MCP-Protocol-Version')
        if protocol is not None and protocol not in PROTOCOLS: return self.reply(400)
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,8}', lengths[0]):
            return self.reply(400)
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY: return self.reply(413)
        if self.headers.get_content_type() != 'application/json': return self.reply(415)
        try:
            # Authenticate every operation through the original account-scoped API.
            receipt(self.server.central, keys[0], PROBE)
        except Refused:
            return self.reply(403)
        try:
            raw = self.rfile.read(length)
            if len(raw) != length: return self.reply(400)
            request = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError, socket.timeout):
            return self.reply(400)
        try:
            status, result = dispatch(self.server.central, keys[0], request)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return self.reply(400)
        self.reply(status, result)

    def log_message(self, *args):
        pass


def make_server(origin, host='127.0.0.1', port=8765, public_host=''):
    server = Server((host, port), Handler)
    server.central = Central(origin)
    server.allowed_hosts = {'127.0.0.1:'+str(server.server_port), 'localhost:'+str(server.server_port), '127.0.0.1', 'localhost'}
    server.allowed_origins = set()
    if public_host:
        if not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', public_host):
            server.server_close(); raise ValueError('Hostname do nó dedicado inválido')
        server.allowed_hosts.update({public_host, public_host+':443'})
        server.allowed_origins.add('https://'+public_host)
    return server
}},
            ['mime','url','bytes','sha256'])}},
        ['requestId','transferApproved','format','caption','media']),
     'annotations':{'readOnlyHint':False,'destructiveHint':False,'idempotentHint':True,'openWorldHint':False}},
]


def dispatch(central, token, request):
    if not isinstance(request, dict) or request.get('jsonrpc') != '2.0' or not isinstance(request.get('method'), str):
        return 400, {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    method, params = request['method'], request.get('params', {})
    if 'id' not in request:
        return (202, None) if method.startswith('notifications/') else (400, None)
    ident = request['id']
    if type(ident) not in (str, int) or not isinstance(params, dict):
        return 400, {'jsonrpc':'2.0','id':None,'error':{'code':-32600,'message':'Invalid Request'}}
    response = {'jsonrpc':'2.0','id':ident}
    if method == 'initialize':
        version = params.get('protocolVersion')
        response['result'] = {'protocolVersion':version if version in PROTOCOLS else PROTOCOLS[0],
            'capabilities':{'tools':{}},'serverInfo':{'name':'central-editorial-universal','version':VERSION}}
    elif method == 'ping':
        response['result'] = {}
    elif method == 'tools/list':
        response['result'] = {'tools':TOOLS}
    elif method == 'tools/call':
        args, name = params.get('arguments', {}), params.get('name')
        try:
            if not isinstance(args, dict):
                raise Refused('Argumentos inválidos')
            if name == 'consultar_conexao' and not args:
                result = {'connected':True,'account':KEY.fullmatch(token)[1],'publishingAvailable':False}
            elif name == 'consultar_envio' and set(args) == {'requestId'}:
                result = safe_receipt(receipt(central, token, args['requestId']))
            elif name == 'enviar_para_revisao':
                result = transfer(central, token, args)
            else:
                raise Refused('Ferramenta ou argumentos inválidos')
            response['result'] = {'content':[{'type':'text','text':json.dumps(result, ensure_ascii=False)}]}
        except Refused as exc:
            response['result'] = {'content':[{'type':'text','text':str(exc)}],'isError':True}
    else:
        response['error'] = {'code':-32601,'message':'Method not found'}
    return 200, response


class Server(ThreadingHTTPServer):
    daemon_threads = True
    slots = threading.BoundedSemaphore(4)
    def process_request(self, request, address):
        if not self.slots.acquire(False):
            self.shutdown_request(request)
            return
        try:
            super().process_request(request, address)
        except BaseException:
            self.slots.release()
            raise
    def process_request_thread(self, request, address):
        try:
            super().process_request_thread(request, address)
        finally:
            self.slots.release()


class Handler(BaseHTTPRequestHandler):
    def setup(self):
        self.request.settimeout(20)
        super().setup()

    def reply(self, status, body=None):
        raw = b'' if body is None else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(status)
        self.send_header('Content-Type','application/json')
        self.send_header('Content-Length',str(len(raw)))
        self.send_header('Cache-Control','no-store')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Connection','close')
        if status == 405:
            self.send_header('Allow','POST')
        self.end_headers()
        self.close_connection = True
        if raw:
            self.wfile.write(raw)

    def valid_route(self):
        if self.path != '/mcp':
            self.reply(404); return False
        hosts = self.headers.get_all('Host', [])
        origins = self.headers.get_all('Origin', [])
        if (len(hosts) != 1 or hosts[0].lower() not in self.server.allowed_hosts or
                len(origins) > 1 or origins and origins[0] not in self.server.allowed_origins):
            self.reply(403); return False
        return True

    def do_GET(self):
        if self.valid_route(): self.reply(405)
    do_DELETE = do_GET

    def do_POST(self):
        if not self.valid_route(): return
        keys = self.headers.get_all('X-Editorial-Key', [])
        if len(keys) != 1 or not KEY.fullmatch(keys[0]):
            return self.reply(403)
        protocol = self.headers.get('MCP-Protocol-Version')
        if protocol is not None and protocol not in PROTOCOLS: return self.reply(400)
        lengths = self.headers.get_all('Content-Length', [])
        if self.headers.get('Transfer-Encoding') or len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,8}', lengths[0]):
            return self.reply(400)
        length = int(lengths[0])
        if not 0 < length <= MAX_BODY: return self.reply(413)
        if self.headers.get_content_type() != 'application/json': return self.reply(415)
        try:
            # Authenticate every operation through the original account-scoped API.
            receipt(self.server.central, keys[0], PROBE)
        except Refused:
            return self.reply(403)
        try:
            raw = self.rfile.read(length)
            if len(raw) != length: return self.reply(400)
            request = json.loads(raw)
        except (ValueError, UnicodeError, RecursionError, socket.timeout):
            return self.reply(400)
        try:
            status, result = dispatch(self.server.central, keys[0], request)
        except (TypeError, ValueError, OverflowError, RecursionError):
            return self.reply(400)
        self.reply(status, result)

    def log_message(self, *args):
        pass


def make_server(origin, host='127.0.0.1', port=8765, public_host=''):
    server = Server((host, port), Handler)
    server.central = Central(origin)
    server.allowed_hosts = {'127.0.0.1:'+str(server.server_port), 'localhost:'+str(server.server_port), '127.0.0.1', 'localhost'}
    server.allowed_origins = set()
    if public_host:
        if not re.fullmatch(r'[a-z0-9.-]+\.ts\.net', public_host):
            server.server_close(); raise ValueError('Hostname do nó dedicado inválido')
        server.allowed_hosts.update({public_host, public_host+':443'})
        server.allowed_origins.add('https://'+public_host)
    return server
