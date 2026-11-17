import test from 'node:test';
import assert from 'node:assert/strict';
import { createEnvelope, validateEnvelope, newInstanceId, createRateLimiter, MAX_MESSAGE_BYTES } from '../src/public/games/protocolo-v1.js';
const id = 'test-instance';
const ready = (sequence = 0) => createEnvelope({ type: 'GAME_READY', instanceId: id, sequence });
const check = (msg, opts = {}) => validateEnvelope(msg, { role: 'frame', state: 'WAIT_READY', instanceId: id, ...opts });
test('READY válido e sequência monotônica', () => {
  assert.equal(check(ready()), true);
  assert.equal(check(ready(), { lastSequence: 0 }), false);
  assert.equal(check(ready(1), { lastSequence: 0 }), true);
});
test('rejeita instância antiga, campos extras e tipos fora do estado', () => {
  assert.equal(check({ ...ready(), instanceId: 'outro' }), false);
  assert.equal(check({ ...ready(), token: 'segredo' }), false);
  assert.equal(check({ ...ready(), type: 'GAME_START' }), false);
  assert.equal(check({ ...ready(), payload: { orderId: 1 } }), false);
});
test('controlador valida modo e esquema exatos', () => {
  const opts = { role: 'controller', state: 'WAIT_READY', instanceId: id };
  assert.equal(validateEnvelope(createEnvelope({ type: 'GAME_START', instanceId: id, sequence: 0, payload: { mode: 'solo' } }), opts), true);
  assert.equal(validateEnvelope(createEnvelope({ type: 'GAME_START', instanceId: id, sequence: 0, payload: { mode: 'admin' } }), opts), false);
});
test('rejeita mensagens grandes e limita taxa', () => {
  assert.equal(check({ ...ready(), payload: { text: 'x'.repeat(MAX_MESSAGE_BYTES) } }), false);
  let now = 0; const allow = createRateLimiter({ limit: 2, now: () => now });
  assert.equal(allow(), true); assert.equal(allow(), true); assert.equal(allow(), false);
  now = 1000; assert.equal(allow(), true);
});
test('identificador aleatório tem formato UUID', () => {
  assert.match(newInstanceId(), /^[0-9a-f-]{36}$/i);
});
