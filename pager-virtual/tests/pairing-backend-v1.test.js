import test from 'node:test';
import assert from 'node:assert/strict';
import {
  generateKeyPairSync, randomBytes, randomUUID, sign, createHash,
  createPublicKey, diffieHellman, hkdfSync, createDecipheriv
} from 'node:crypto';
import {
  assertUuid, strictBase64Url, assertProtocol, parsePublicKey, canonicalProofMessage,
  verifyOperationProof, sealCredentialEnvelope, PAIR_PROTOCOL, ENVELOPE_SUITE
} from '../src/pairing/backend/protocol-v2.js';

const pairId = randomUUID(), operationId = randomUUID(), challengeId = randomUUID();
const signingKeys = generateKeyPairSync('ed25519');
const deliveryKeys = generateKeyPairSync('x25519');
const signingPem = signingKeys.publicKey.export({ format: 'pem', type: 'spki' });
const deliveryPem = deliveryKeys.publicKey.export({ format: 'pem', type: 'spki' });
const challenge = randomBytes(32).toString('base64url');

test('prova Ed25519 v2 tem LF exato e finalidade vinculada', () => {
  const opts = { purpose:'status', pairingId:pairId, operationId, challengeId, challenge };
  const message = canonicalProofMessage(opts);
  assert.equal(message.toString(), ['avisaqui-pair-proof-v2','status',pairId,operationId,challengeId,challenge].join('\n'));
  assert.equal(message[message.length - 1], challenge.charCodeAt(challenge.length - 1));
  const signature = sign(null,message,signingKeys.privateKey).toString('base64url');
  assert.equal(verifyOperationProof({ ...opts, signingPublicKey:signingPem, signature }), true);
  assert.equal(verifyOperationProof({ ...opts, purpose:'redeem', signingPublicKey:signingPem, signature }), false);
  assert.equal(verifyOperationProof({ ...opts, operationId:randomUUID(), signingPublicKey:signingPem, signature }), false);
  assert.equal(verifyOperationProof({ ...opts, challengeId:randomUUID(), signingPublicKey:signingPem, signature }), false);
  assert.equal(verifyOperationProof({ ...opts, signature:signature + '=', signingPublicKey:signingPem }), false);
});
test('validações rejeitam downgrade, UUID malformado e chaves erradas', () => {
  assert.equal(assertProtocol('pair-v1'), 'pair-v1');
  assert.throws(() => assertProtocol('pair-v0.2'));
  assert.equal(assertUuid(pairId), pairId);
  assert.throws(() => assertUuid(pairId.toUpperCase()));
  assert.throws(() => strictBase64Url('aa==',1));
  assert.throws(() => strictBase64Url('abc!',3));
  assert.equal(parsePublicKey(signingPem,'ed25519').asymmetricKeyType,'ed25519');
  assert.throws(() => parsePublicKey(signingPem,'x25519'));
});
test('envelope X25519 / HKDF-SHA256 / AES-256-GCM abre somente com AAD correto', () => {
  const deviceId=randomUUID(), credential=randomBytes(32).toString('hex'), restaurantId=randomUUID();
  const packet=sealCredentialEnvelope({
    pairingId:pairId, operationId, deliveryPublicKey:deliveryPem,
    deviceId, restaurantId, cashierName:'Caixa 1', credential
  });
  assert.equal(packet.protocol, PAIR_PROTOCOL);
  assert.equal(packet.envelope.suite, ENVELOPE_SUITE);
  assert.equal(JSON.stringify(packet).includes(credential),false);
  const e=packet.envelope;
  const serverPub=createPublicKey({
    key:strictBase64Url(e.ephemeral_public_key,44),format:'der',type:'spki'
  });
  const secret=diffieHellman({privateKey:deliveryKeys.privateKey,publicKey:serverPub});
  const clientDer=deliveryKeys.publicKey.export({format:'der',type:'spki'});
  const context=Buffer.from(['avisaqui-pair-envelope-v1',pairId,operationId,createHash('sha256').update(clientDer).digest('hex')].join('\n'));
  const aesKey=Buffer.from(hkdfSync('sha256',secret,strictBase64Url(e.salt,32),context,32));
  const decrypt=(aad) => {
    const d=createDecipheriv('aes-256-gcm',aesKey,strictBase64Url(e.nonce,12));
    d.setAAD(aad);d.setAuthTag(strictBase64Url(e.tag,16));
    return Buffer.concat([d.update(strictBase64Url(e.ciphertext)),d.final()]);
  };
  const payload=JSON.parse(decrypt(context).toString('utf8'));
  assert.deepEqual(payload,{protocol:'pair-v1',operation_id:operationId,dispositivo_id:deviceId,restaurante_id:restaurantId,caixa_nome:'Caixa 1',credential});
  assert.throws(()=>decrypt(Buffer.from('AAD alterado')));
});
test('dados inválidos não geram envelope', () => {
  const valid={pairingId:pairId,operationId,deviceId:randomUUID(),restaurantId:'rest-1',cashierName:'Caixa',credential:randomBytes(32).toString('hex'),deliveryPublicKey:deliveryPem};
  assert.throws(()=>sealCredentialEnvelope({...valid,credential:'segredo'}));
  assert.throws(()=>sealCredentialEnvelope({...valid,deliveryPublicKey:signingPem}));
  assert.throws(()=>sealCredentialEnvelope({...valid,deviceId:'../../invalid'}));
});
