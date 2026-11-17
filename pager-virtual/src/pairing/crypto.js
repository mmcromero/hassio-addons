// AVISAQUI-PAIR-001: primitivas isoladas para pareamento de agentes Windows.
// Não gera credencial de produção nem altera rotas de impressão.
import { createPublicKey, randomBytes, randomInt, randomUUID, verify } from 'node:crypto';

export const PAIRING_TTL_MS = 5 * 60 * 1000;
export const MAX_PAIRING_ATTEMPTS = 5;
const DOMAIN = 'avisaqui-pair-proof-v1';

export function parsePairingPublicKey(publicKeyPem) {
  if (typeof publicKeyPem !== 'string' || publicKeyPem.length > 1024 ||
      !publicKeyPem.startsWith('-----BEGIN PUBLIC KEY-----')) {
    throw new TypeError('Chave pública de pareamento inválida');
  }
  let key;
  try { key = createPublicKey(publicKeyPem); }
  catch { throw new TypeError('Chave pública de pareamento inválida'); }
  if (key.asymmetricKeyType !== 'ed25519') {
    throw new TypeError('Pareamento exige chave pública Ed25519');
  }
  return key;
}

// O código numérico é APENAS um localizador para a tela autenticada do gerente.
// Nunca é uma credencial, prova de posse ou autorização para resgate.
export function makePairingRequest(publicKeyPem, now = Date.now()) {
  const key = parsePairingPublicKey(publicKeyPem);
  if (!Number.isSafeInteger(now) || now < 0) throw new RangeError('Horário inválido');
  const publicKey = key.export({ type: 'spki', format: 'pem' }).toString();
  return {
    id: randomUUID(),
    code: String(randomInt(0, 100_000_000)).padStart(8, '0'),
    publicKey,
    challenge: randomBytes(32).toString('base64url'),
    state: 'PENDENTE',
    createdAt: now,
    expiresAt: now + PAIRING_TTL_MS,
    attempts: 0
  };
}

// Assinatura vinculada à solicitação e ao desafio gerado pelo servidor.
// A API deve consumir o desafio atomicamente na transição RESGATADO.
export function pairingProofMessage(requestId, challenge, purpose = 'redeem') {
  if (typeof requestId !== 'string' || !/^[a-f0-9-]{36}$/i.test(requestId) ||
      typeof challenge !== 'string' || !/^[a-zA-Z0-9_-]{43}$/.test(challenge)) {
    throw new TypeError('Identificação ou desafio inválido');
  }
  if (!['status', 'redeem'].includes(purpose)) throw new TypeError('Operação inválida');
  return Buffer.from([DOMAIN, purpose, requestId, challenge].join('\n'), 'utf8');
}

export function verifyPairingProof(publicKeyPem, requestId, challenge, signatureBase64Url, purpose = 'redeem') {
  if (typeof signatureBase64Url !== 'string' ||
      !/^[A-Za-z0-9_-]{86}$/.test(signatureBase64Url)) return false;
  try {
    const sig = Buffer.from(signatureBase64Url, 'base64url');
    if (sig.length !== 64) return false;
    return verify(null, pairingProofMessage(requestId, challenge, purpose),
      parsePairingPublicKey(publicKeyPem), sig);
  } catch { return false; }
}

export function isPairingExpired(request, now = Date.now()) {
  return now >= request.expiresAt;
}
