import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const temp = mkdtempSync(path.join(tmpdir(), 'bipou-quick-order-'));
process.env.DATA_PATH = temp;
const { default: db } = await import('../src/db.js');
const { passwordHash, authRoutes } = await import('../src/auth.js');
const { pedidosRoutes } = await import('../src/routes/pedidos.js');
const { default: Fastify } = await import('fastify');
const app = Fastify();
await app.register(authRoutes);
await app.register(pedidosRoutes);
await app.ready();
after(async () => { await app.close(); db.close(); rmSync(temp, { recursive: true, force: true }); });

const rest = randomUUID();
db.prepare('INSERT INTO restaurantes (id, nome, slug, created_at) VALUES (?, ?, ?, ?)').run(rest, 'Teste', 'teste', Date.now());
const now = Date.now();
db.prepare(`INSERT INTO usuarios (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
  VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(randomUUID(), rest, 'Gerente', 'gerente-quick',
  await passwordHash('senha-super-forte-123!'), 'gerente', now, now);
const login = await app.inject({ method: 'POST', url: '/api/auth/login',
  headers: { host: 'localhost', origin: 'http://localhost' },
  payload: { login: 'gerente-quick', senha: 'senha-super-forte-123!' } });
assert.equal(login.statusCode, 200, login.body);
const cookie = login.headers['set-cookie'].split(';')[0];
function send(method, url, payload) {
  return app.inject({ method, url,
    headers: { host: 'localhost', origin: 'http://localhost', cookie },
    ...(payload === undefined ? {} : { payload }) });
}

test('duplicidade manual e restrição no SQLite', async () => {
  const a = await send('POST', '/api/pedidos', { numero: 900 });
  assert.equal(a.statusCode, 201, a.body);
  const b = await send('POST', '/api/pedidos', { numero: 900 });
  assert.equal(b.statusCode, 409);
  assert.throws(() => db.prepare(`INSERT INTO pedidos
    (id, restaurante_id, numero, token, created_at) VALUES (?, ?, ?, ?, ?)`)
    .run(randomUUID(), rest, 900, randomUUID(), Date.now()), /UNIQUE/);
  assert.equal((await send('PATCH', '/api/pedidos/' + a.json().id + '/status', { status: 'entregue' })).statusCode, 200);
  assert.equal((await send('POST', '/api/pedidos', { numero: 900 })).statusCode, 201);
  assert.equal((await send('PATCH', '/api/pedidos/' + a.json().id + '/status', { status: 'pronto' })).statusCode, 409);
});

test('sequência bloqueada com pedido ativo e reserva concorrente', async () => {
  assert.equal((await send('PUT', '/api/pedidos/sequencia', { modo: 'automatico', proximo_numero: 100 })).statusCode, 409);
  db.prepare("UPDATE pedidos SET status = 'entregue' WHERE restaurante_id = ?").run(rest);
  assert.equal((await send('PUT', '/api/pedidos/sequencia', { modo: 'automatico', proximo_numero: 100 })).statusCode, 200);
  const results = await Promise.all(Array.from({ length: 8 }, () => send('POST', '/api/pedidos', {
    cliente_nome: 'Cliente', cliente_telefone: '11999999999'
  })));
  assert.ok(results.every(x => x.statusCode === 201), results.map(x => x.body).join('; '));
  assert.deepEqual(results.map(x => x.json().numero).sort((a,b) => a-b), [100,101,102,103,104,105,106,107]);
  const first = results[0].json();
  assert.equal(first.cliente_nome, 'Cliente');
  assert.equal(first.cliente_telefone, '11999999999');
  assert.equal((await send('PATCH', '/api/pedidos/' + first.id + '/status', { status: 'entregue' })).statusCode, 200);
  const stored = db.prepare('SELECT cliente_nome, cliente_telefone FROM pedidos WHERE id = ?').get(first.id);
  assert.equal(stored.cliente_nome, null);
  assert.equal(stored.cliente_telefone, null);
});
