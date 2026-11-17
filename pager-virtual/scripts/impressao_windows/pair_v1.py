"""AVISAQUI-PAIR-001 pair-v1: contrato binario criptografico isolado.

Ed25519 assina desafios de uso unico; X25519 recebe envelope cifrado.
A validacao de estados/consumo do desafio pertence ao servidor.
"""
import base64
import hashlib
import json
import re
import uuid

from cryptography.hazmat.primitives.asymmetric import ed25519, x25519
from cryptography.hazmat.primitives.serialization import (
    Encoding, PublicFormat, PrivateFormat, NoEncryption, load_der_public_key
)
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.exceptions import InvalidTag

PROTOCOL = 'pair-v1'
DOMAIN = 'avisaqui-pair-proof-v2'
SUITE = 'X25519-HKDF-SHA256-AES-256-GCM'
PURPOSES = frozenset(('status', 'redeem', 'ack'))
UUID_RX = re.compile(r'[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}\Z')
HEX_KEY_RX = re.compile(r'[a-f0-9]{64}\Z')

class ProtocolError(ValueError):
    pass

def require_uuid(value):
    if not isinstance(value, str) or len(value) != 36 or not UUID_RX.fullmatch(value):
        raise ProtocolError('Identificador nao canonico')
    return value

def decode_url64(value, expected=None, maximum=8192):
    if not isinstance(value, str) or len(value) > maximum or not re.fullmatch(r'[A-Za-z0-9_-]+', value):
        raise ProtocolError('Base64url invalido')
    try:
        decoded = base64.b64decode(value + '=' * (-len(value) % 4), altchars=b'-_', validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ProtocolError('Base64url invalido') from exc
    if expected is not None and len(decoded) != expected:
        raise ProtocolError('Tamanho criptografico invalido')
    if encode_url64(decoded) != value:
        raise ProtocolError('Base64url nao canonico')
    return decoded

def encode_url64(data):
    return base64.urlsafe_b64encode(data).rstrip(b'=').decode('ascii')

def new_keys():
    signer = ed25519.Ed25519PrivateKey.generate()
    receiver = x25519.X25519PrivateKey.generate()
    return signer, receiver

def public_pem(key):
    return key.public_key().public_bytes(Encoding.PEM, PublicFormat.SubjectPublicKeyInfo).decode('ascii')

def private_raw(key):
    return key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())

def restore_keys(signing_raw, delivery_raw):
    if len(signing_raw) != 32 or len(delivery_raw) != 32:
        raise ProtocolError('Comprimento de chave privada invalido')
    return ed25519.Ed25519PrivateKey.from_private_bytes(signing_raw), x25519.X25519PrivateKey.from_private_bytes(delivery_raw)

def signing_message(purpose, pairing_id, operation_id, challenge_id, challenge):
    if purpose not in PURPOSES:
        raise ProtocolError('Finalidade invalida')
    for item in (pairing_id, operation_id, challenge_id):
        require_uuid(item)
    decode_url64(challenge, expected=32)
    return ('\n'.join((DOMAIN, purpose, pairing_id, operation_id, challenge_id, challenge))).encode('ascii')

def sign_challenge(private, purpose, pairing_id, operation_id, challenge_id, challenge):
    return encode_url64(private.sign(signing_message(
        purpose, pairing_id, operation_id, challenge_id, challenge)))

def decrypt_envelope(receiver, pairing_id, operation_id, response):
    """Abre somente o envelope pair-v1 cujo contexto e destinatario coincidem."""
    require_uuid(pairing_id)
    require_uuid(operation_id)
    if not isinstance(response, dict) or response.get('protocol') != PROTOCOL or response.get('operation_id') != operation_id:
        raise ProtocolError('Versao ou operacao de resgate invalida')
    envelope = response.get('envelope')
    if not isinstance(envelope, dict) or envelope.get('suite') != SUITE:
        raise ProtocolError('Suite criptografica nao suportada')
    ephemeral_der = decode_url64(envelope.get('ephemeral_public_key'), maximum=256)
    salt = decode_url64(envelope.get('salt'), expected=32)
    nonce = decode_url64(envelope.get('nonce'), expected=12)
    ciphertext = decode_url64(envelope.get('ciphertext'), maximum=8192)
    tag = decode_url64(envelope.get('tag'), expected=16)
    try:
        ephemeral = load_der_public_key(ephemeral_der)
        if not isinstance(ephemeral, x25519.X25519PublicKey):
            raise ProtocolError('Chave publica X25519 invalida')
        recipient_der = receiver.public_key().public_bytes(Encoding.DER, PublicFormat.SubjectPublicKeyInfo)
        recipient_id = hashlib.sha256(recipient_der).hexdigest()
        context = ('avisaqui-pair-envelope-v1\n' + pairing_id + '\n'
                   + operation_id + '\n' + recipient_id).encode('utf-8')
        shared = receiver.exchange(ephemeral)
        key = HKDF(algorithm=hashes.SHA256(), length=32, salt=salt, info=context).derive(shared)
        clear = AESGCM(key).decrypt(nonce, ciphertext + tag, context)
        result = json.loads(clear)
    except (ValueError, InvalidTag, TypeError, KeyError) as exc:
        raise ProtocolError('Envelope invalido ou autenticacao criptografica falhou') from exc
    if not isinstance(result, dict) or result.get('protocol') != PROTOCOL or result.get('operation_id') != operation_id:
        raise ProtocolError('Conteudo do envelope divergente')
    if not HEX_KEY_RX.fullmatch(str(result.get('credential', ''))):
        raise ProtocolError('Credencial do envelope invalida')
    require_uuid(result.get('dispositivo_id'))
    if not isinstance(result.get('restaurante_id'), str) or not (1 <= len(result['restaurante_id']) <= 128):
        raise ProtocolError('Restaurante do envelope invalido')
    if not isinstance(result.get('caixa_nome'), str) or len(result['caixa_nome']) > 120:
        raise ProtocolError('Nome do caixa invalido')
    return result
