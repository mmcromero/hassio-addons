import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('KDS carrega pedidos persistidos sem contador da simulação antiga', () => {
  const html = readFileSync(new URL('../src/public/kds.html', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /\borderCounter\b/);
  assert.match(html, /async function carregarPedidos\(\)/);
  assert.match(html, /activeOrders = dados\.map\(/);
  const start = html.indexOf('async function carregarPedidos()');
  const end = html.indexOf('// Receptor SSE da Cozinha', start);
  assert.ok(start >= 0 && end > start);
  assert.match(html.slice(start, end), /renderOrders\(\)/);
});
