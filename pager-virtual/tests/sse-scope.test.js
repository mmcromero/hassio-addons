import test from 'node:test';
import assert from 'node:assert/strict';
import { EventEmitter } from 'node:events';
import { sseManager } from '../src/sse.js';

function client() {
  const raw = new EventEmitter();
  raw.messages = [];
  raw.write = message => raw.messages.push(message);
  return { raw };
}

test('evento de restaurante A não alcança KDS do restaurante B', () => {
  const a = client(), b = client();
  sseManager.addKds('restaurante-a', a);
  sseManager.addKds('restaurante-b', b);
  sseManager.notifyKds('restaurante-a', 'novo_pedido', { numero: 12 });
  assert.equal(a.raw.messages.length, 1);
  assert.equal(b.raw.messages.length, 0);
  assert.match(a.raw.messages[0], /novo_pedido/);
  a.raw.emit('close'); b.raw.emit('close');
  assert.equal(sseManager.kdsStreams.size, 0);
});

test('cliente acompanha somente token cadastrado', () => {
  const a = client(), b = client();
  sseManager.addClient('token-a', a);
  sseManager.addClient('token-b', b);
  sseManager.notifyClient('token-a', { status: 'pronto' });
  assert.equal(a.raw.messages.length, 1);
  assert.equal(b.raw.messages.length, 0);
  a.raw.emit('close'); b.raw.emit('close');
});
