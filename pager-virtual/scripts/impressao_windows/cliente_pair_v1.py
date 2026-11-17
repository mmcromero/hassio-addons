"""Cliente HTTP pair-v1 Windows. Nao chama captura/spooler/impressora.

Protocolo v1: challenges one-shot, provas Ed25519 v2 e pacote AES-GCM.
Uma instancia de transporte falso permite testes sem rede.
"""
import json
import re
import ssl
from urllib.parse import urlparse, parse_qsl
from urllib.request import Request, build_opener, HTTPSHandler, HTTPRedirectHandler
from urllib.error import HTTPError, URLError

from pair_v1 import (PROTOCOL, ProtocolError, decode_url64, require_uuid,
                     sign_challenge, decrypt_envelope, public_pem)

MAX_RESPONSE = 16_384
STATES = {'PENDENTE', 'APROVADO', 'RECUSADO', 'EXPIRADO', 'CANCELADO',
          'RESGATADO', 'CONFIRMADO'}

class PairV1Error(RuntimeError):
    def __init__(self, message, status=None, transient=False):
        super().__init__(message)
        self.status = status
        self.transient = transient

def validate_origin(value):
    if not isinstance(value, str) or len(value) > 512:
        raise PairV1Error('Origem HTTPS invalida')
    p = urlparse(value)
    if p.scheme != 'https' or not p.hostname or p.username or p.password or p.query or p.fragment \
            or p.path not in ('', '/', '/avisaqui', '/avisaqui/'):
        raise PairV1Error('Use origem HTTPS valida')
    return value.rstrip('/')

class PairV1Client:
    def __init__(self, origin, transport=None):
        self.origin = validate_origin(origin)
        self.transport = transport or self._https

    @staticmethod
    def _https(url, method, data, headers=None):
        try:
            import truststore
        except ImportError as exc:
            raise PairV1Error('Dependencia truststore ausente') from exc
        body = json.dumps(data, separators=(',', ':')).encode('utf-8') if data is not None else None
        parsed = urlparse(url)
        if parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password:
            raise PairV1Error('Destino HTTPS invalido')
        # O backend exige Origin nas escritas. Mesmo com prefixo /avisaqui,
        # Origin inclui somente esquema, host e porta (sem caminho).
        request_headers = {'Accept': 'application/json',
            'Content-Type': 'application/json', 'X-Avisaqui-Pair-Version': PROTOCOL,
            **(headers or {})}
        request_headers['Origin'] = parsed.scheme + '://' + parsed.netloc
        req = Request(url, data=body, headers=request_headers, method=method)
        class NoRedirect(HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener = build_opener(HTTPSHandler(context=truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)),
                              NoRedirect())
        try:
            with opener.open(req, timeout=8) as response:
                raw = response.read(MAX_RESPONSE + 1)
                if len(raw) > MAX_RESPONSE:
                    raise PairV1Error('Resposta excede limite')
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise PairV1Error('Resposta inesperada')
                return value
        except HTTPError as exc:
            raise PairV1Error('Servidor recusou operacao (HTTP %d)' % exc.code,
                              exc.code, transient=exc.code in (502, 503, 504)) from exc
        except (URLError, TimeoutError, OSError) as exc:
            raise PairV1Error('Falha de conexao com o servidor', transient=True) from exc
        except ValueError as exc:
            raise PairV1Error('Resposta invalida do servidor') from exc

    def create(self, client_request_id, signing_key, delivery_key):
        require_uuid(client_request_id)
        answer = self.transport(self.origin + '/api/agentes/pareamentos', 'POST', {
            'protocol': PROTOCOL,
            'client_request_id': client_request_id,
            'signing_public_key': public_pem(signing_key),
            'delivery_public_key': public_pem(delivery_key)}, None)
        if not isinstance(answer, dict) or answer.get('protocol') != PROTOCOL:
            raise PairV1Error('Versao do servidor incompativel')
        require_uuid(answer.get('id'))
        if not isinstance(answer.get('code'), str) or not re.fullmatch(r'[0-9]{8}', answer['code']):
            raise PairV1Error('Codigo do pareamento invalido')
        if type(answer.get('expires_at')) is not int or answer['expires_at'] < 1:
            raise PairV1Error('Prazo invalido')
        if answer.get('state') != 'PENDENTE':
            raise PairV1Error('Estado inicial invalido')
        qr = answer.get('qr_url')
        if not isinstance(qr, str) or len(qr) > 2048:
            raise PairV1Error('QR invalido')
        p, origin = urlparse(qr), urlparse(self.origin)
        expected_path = origin.path.rstrip('/') + '/autorizar'
        try:
            query = parse_qsl(p.query, keep_blank_values=True, strict_parsing=True,
                              max_num_fields=2)
        except ValueError as exc:
            raise PairV1Error('Referencia do QR invalida') from exc
        if (p.scheme != 'https' or p.netloc != origin.netloc or
                p.username or p.password or p.fragment or p.path != expected_path or
                query != [('solicitacao', answer['id'])]):
            raise PairV1Error('QR nao corresponde a solicitacao autorizada')
        return answer

    def challenge(self, pairing_id, purpose, operation_id):
        require_uuid(pairing_id)
        require_uuid(operation_id)
        if purpose not in ('status', 'redeem', 'ack'):
            raise PairV1Error('Finalidade de desafio invalida')
        result = self.transport(self.origin + '/api/agentes/pareamentos/' + pairing_id + '/desafios',
                                'POST', {'protocol': PROTOCOL, 'purpose': purpose,
                                         'operation_id': operation_id}, None)
        if not isinstance(result, dict):
            raise PairV1Error('Resposta do desafio invalida')
        require_uuid(result.get('challenge_id'))
        decode_url64(result.get('challenge'), expected=32)
        if type(result.get('expires_at')) is not int or result['expires_at'] <= 0:
            raise PairV1Error('Expiracao do desafio invalida')
        return result

    def _signed(self, signing_key, pairing_id, purpose, operation_id):
        challenge = self.challenge(pairing_id, purpose, operation_id)
        signature = sign_challenge(signing_key, purpose, pairing_id, operation_id,
                                   challenge['challenge_id'], challenge['challenge'])
        return challenge['challenge_id'], signature

    def status(self, signing_key, pairing_id, operation_id):
        challenge_id, signature = self._signed(signing_key, pairing_id, 'status', operation_id)
        answer = self.transport(self.origin + '/api/agentes/pareamentos/' + pairing_id + '/estado',
                                'GET', None, {
                                    'X-Avisaqui-Pair-Version': PROTOCOL,
                                    'X-Avisaqui-Pair-Operation-Id': operation_id,
                                    'X-Avisaqui-Pair-Challenge-Id': challenge_id,
                                    'X-Avisaqui-Pair-Proof': signature})
        if not isinstance(answer, dict) or answer.get('protocol') != PROTOCOL or answer.get('state') not in STATES:
            raise PairV1Error('Estado do servidor invalido')
        return answer

    def redeem(self, signing_key, delivery_key, pairing_id, operation_id):
        challenge_id, signature = self._signed(signing_key, pairing_id, 'redeem', operation_id)
        response = self.transport(self.origin + '/api/agentes/pareamentos/' + pairing_id + '/resgatar',
                                  'POST', {'protocol': PROTOCOL, 'operation_id': operation_id,
                                           'challenge_id': challenge_id, 'signature': signature}, None)
        return decrypt_envelope(delivery_key, pairing_id, operation_id, response)

    def ack(self, signing_key, pairing_id, redeem_operation_id, ack_operation_id):
        challenge_id, signature = self._signed(signing_key, pairing_id, 'ack', ack_operation_id)
        response = self.transport(self.origin + '/api/agentes/pareamentos/' + pairing_id + '/confirmar',
                                  'POST', {'protocol': PROTOCOL, 'operation_id': redeem_operation_id,
                                           'ack_operation_id': ack_operation_id,
                                           'challenge_id': challenge_id, 'signature': signature}, None)
        if not isinstance(response, dict) or response.get('state') != 'CONFIRMADO':
            raise PairV1Error('Confirmacao invalida')
        require_uuid(response.get('dispositivo_id'))
        return response
