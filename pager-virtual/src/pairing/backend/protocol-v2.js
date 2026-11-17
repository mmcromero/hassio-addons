// AVISAQUI-PAIR-001 — pair-v1: primitivas servidor isoladas.
// NÃO importar em src/server.js até aceite de Segurança e interoperabilidade Windows.
import {
  createPublicKey, createHash, verify, randomBytes, generateKeyPairSync,
  diffieHellman, hkdfSync, createCipheriv
} from 'node:crypto';

export const PAIR_PROTOCOL = 'pair-v1';
export const PROOF_DOMAIN = 'avisaqui-pair-proof-v2';
export const ENVELOPE_SUITE = 'X25519-HKDF-SHA256-AES-256-GCM';
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const B64URL = /^[A-Za-z0-9_-]+$/;

export function assertUuid(value) {
  if (typeof value !== 'string' || !UUID.test(value)) throw new TypeError('UUID canônico inválido');
  return value;
}
export function assertProtocol(value) {
  if (value !== PAIR_PROTOCOL) throw new TypeError('Versão de pareamento não suportada');
  return value;
}
export function strictBase64Url(value, bytes) {
  if (typeof value !== 'string' || value.length > 4096 || !B64URL.test(value)) {
    throw new TypeError('Base64url inválido');
  }
  const buffer = Buffer.from(value, 'base64url');
  if (buffer.toString('base64url') !== value || (bytes !== undefined && buffer.length !== bytes)) {
    throw new TypeError('Base64url não canônico');
  }
  return buffer;
}
export function parsePublicKey(pem, kind) {
  if (!['ed25519', 'x25519'].includes(kind) || typeof pem !== 'string' ||
      pem.length > 512 || !pem.startsWith('-----BEGIN PUBLIC KEY-----') ||
      !pem.trimEnd().endsWith('-----END PUBLIC KEY-----')) {
    throw new TypeError('Chave pública inválida');
  }
  let key;
  try { key = createPublicKey(pem); } catch { throw new TypeError('Chave pública inválida'); }
  if (key.asymmetricKeyType !== kind) throw new TypeError('Curva pública incompatível');
  const der = key.export({ format: 'der', type: 'spki' });
  if (der.length !== 44) throw new TypeError('Chave pública SPKI inválida');
  return key;
}
export function canonicalProofMessage({ purpose, pairingId, operationId, challengeId, challenge }) {
  if (!['status', 'redeem', 'ack'].includes(purpose)) throw new TypeError('Finalidade de prova inválida');
  assertUuid(pairingId); assertUuid(operationId); assertUuid(challengeId);
  strictBase64Url(challenge, 32);
  return Buffer.from([PROOF_DOMAIN, purpose, pairingId, operationId, challengeId, challenge].join('\n'), 'utf8');
}
export function verifyOperationProof({ signingPublicKey, purpose, pairingId, operationId, challengeId, challenge, signature }) {
  // A verificação criptográfica NÃO consome o desafio.
  // O backend deverá conferir propósito, validade e consumo em transação IMMEDIATE.
  try {
    const message = canonicalProofMessage({ purpose, pairingId, operationId, challengeId, challenge });
    const sig = strictBase64Url(signature, 64);
    return verify(null, message, parsePublicKey(signingPublicKey, 'ed25519'), sig);
  } catch { return false; }
}
export function sealCredentialEnvelope({ pairingId, operationId, deliveryPublicKey, deviceId, restaurantId, cashierName, credential }) {
  assertUuid(pairingId); assertUuid(operationId); assertUuid(deviceId);
  if (typeof restaurantId !== 'string' || restaurantId.length < 1 || restaurantId.length > 120 ||
      typeof cashierName !== 'string' || cashierName.trim().length < 1 || cashierName.length > 120 ||
      typeof credential !== 'string' || !/^[a-f0-9]{64}$/.test(credential)) {
    throw new TypeError('Dados do dispositivo inválidos');
  }
  const recipient = parsePublicKey(deliveryPublicKey, 'x25519');
  const recipientDer = recipient.export({ type: 'spki', format: 'der' });
  const recipientId = createHash('sha256').update(recipientDer).digest('hex');
  const context = Buffer.from(['avisaqui-pair-envelope-v1', pairingId, operationId, recipientId].join('\n'), 'utf8');
  const { publicKey, privateKey } = generateKeyPairSync('x25519');
  // A API deve tratar e rejeitar chaves públicas de baixa ordem e segredos inválidos.
  const shared = diffieHellman({ privateKey, publicKey: recipient });
  if (shared.length !== 32 || shared.every(byte => byte === 0)) throw new TypeError('Segredo ECDH inválido');
  const salt = randomBytes(32);
  const nonce = randomBytes(12);
  const key = Buffer.from(hkdfSync('sha256', shared, salt, context, 32));
  const data = Buffer.from(JSON.stringify({
    protocol: PAIR_PROTOCOL, operation_id: operationId, dispositivo_id: deviceId,
    restaurante_id: restaurantId, caixa_nome: cashierName, credential
  }), 'utf8');
  const cipher = createCipheriv('aes-256-gcm', key, nonce, { authTagLength: 16 });
  cipher.setAAD(context);
  const ciphertext = Buffer.concat([cipher.update(data), cipher.final()]);
  const tag = cipher.getAuthTag();
  key.fill(0); shared.fill(0); data.fill(0);
  return {
    protocol: PAIR_PROTOCOL, operation_id: operationId,
    envelope: {
      suite: ENVELOPE_SUITE,
      ephemeral_public_key: publicKey.export({ type: 'spki', format: 'der' }).toString('base64url'),
      salt: salt.toString('base64url'), nonce: nonce.toString('base64url'),
      ciphertext: ciphertext.toString('base64url'), tag: tag.toString('base64url')
    }
  };
}
