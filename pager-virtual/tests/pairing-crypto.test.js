import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync, sign } from 'node:crypto';
import {
  PAIRING_TTL_MS, MAX_PAIRING_ATTEMPTS, makePairingRequest,
  pairingProofMessage, verifyPairingProof, isPairingExpired
} from '../src/pairing/crypto.js';

function keys() {
  const { publicKey, privateKey } = generateKeyPairSync('ed25519');
  return {
    publicKey: publicKey.export({ type: 'spki', format: 'pem' }).toString(),
    privateKey
  };
}

test('solicitação usa identificador, código e desafio temporários', () => {
  const { publicKey } = keys();
  const now = 1780000000000;
  const a = makePairingRequest(publicKey, now);
  const b = makePairingRequest(publicKey, now);
  assert.match(a.id, /^[0-9a-f-]{36}$/);
  assert.match(a.code, /^\d{8}$/);
  assert.match(a.challenge, /^[a-zA-Z0-9_-]{43}$/);
  assert.equal(a.state, 'PENDENTE');
  assert.equal(a.expiresAt, now + PAIRING_TTL_MS);
  assert.equal(MAX_PAIRING_ATTEMPTS, 5);
  assert.notEqual(a.id, b.id);
  assert.notEqual(a.challenge, b.challenge);
  assert.equal(isPairingExpired(a, a.expiresAt - 1), false);
  assert.equal(isPairingExpired(a, a.expiresAt), true);
});

test('prova válida só para a solicitação e o desafio corretos', () => {
  const a = keys();
  const b = keys();
  const r = makePairingRequest(a.publicKey);
  const other = makePairingRequest(a.publicKey);
  const signature = sign(null, pairingProofMessage(r.id, r.challenge), a.privateKey).toString('base64url');
  assert.equal(verifyPairingProof(a.publicKey, r.id, r.challenge, signature), true);
  assert.equal(verifyPairingProof(a.publicKey, r.id, r.challenge, signature, 'status'), false);
  assert.equal(verifyPairingProof(a.publicKey, other.id, r.challenge, signature), false);
  assert.equal(verifyPairingProof(a.publicKey, r.id, other.challenge, signature), false);
  assert.equal(verifyPairingProof(b.publicKey, r.id, r.challenge, signature), false);
  assert.equal(verifyPairingProof(a.publicKey, r.id, r.challenge, 'token-invalido'), false);
});

test('rejeita material de chave inválido e algoritmo diferente', () => {
  const { publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const rsaPem = publicKey.export({ type: 'spki', format: 'pem' }).toString();
  assert.throws(() => makePairingRequest(rsaPem), /Ed25519/);
  assert.throws(() => makePairingRequest('texto'), /inválida/);
  assert.throws(() => pairingProofMessage('inválido', 'x'), /inválido/);
});
