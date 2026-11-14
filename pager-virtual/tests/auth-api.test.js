import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const temp = mkdtempSync(path.join(tmpdir(), 'bipou-auth-integration-'));
process.env.DATA_PATH = temp;
const { default: db } = await import('../src/db.js');
const { passwordHash, authRoutes } = await import('../src/auth.js');
const { adminRoutes } = await import('../src/admin.js');
const { pedidosRoutes } = await import('../src/routes/pedidos.js');
const { default: Fastify } = await import('fastify');
const app = Fastify();
await app.register(authRoutes);
await app.register(adminRoutes);
await app.register(pedidosRoutes);
await app.ready();
after(async () => { await app.close(); db.close(); rmSync(temp, { recursive: true, force: true }); });

const host = { host: 'localhost', origin: 'http://localhost' };
function send(method, url, payload, cookie) {
  return app.inject({
    method, url, headers: { ...host, ...(cookie ? { cookie } : {}) },
    ...(payload === undefined ? {} : { payload })
  });
}
function insertRest(name) {
  const id = randomUUID();
  db.prepare('INSERT INTO restaurantes (id, nome, slug, created_at) VALUES (?, ?, ?, ?)').run(id, name, name.toLowerCase(), Date.now());
  return id;
}
async function insertUser(role, restaurantId, login) {
  const now = Date.now();
  db.prepare(`INSERT INTO usuarios
    (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)`)
    .run(randomUUID(), restaurantId, login, login, await passwordHash('senha-super-forte-123!'), role, now, now);
}
async function login(loginName) {
  const res = await send('POST', '/api/auth/login', { login: loginName, senha: 'senha-super-forte-123!' });
  assert.equal(res.statusCode, 200, res.body);
  return res.headers['set-cookie'].split(';')[0];
}

const restaurantA = insertRest('RestA');
const restaurantB = insertRest('RestB');
await insertUser('master', null, 'admin-main');
await insertUser('gerente', restaurantA, 'gerente-a');
await insertUser('gerente', restaurantB, 'gerente-b');

test('API exige sessão para ler e cadastrar pedidos', async () => {
  assert.equal((await send('GET', '/api/pedidos')).statusCode, 401);
  assert.equal((await send('POST', '/api/pedidos', { numero: 99 })).statusCode, 401);
  assert.equal((await send('GET', '/api/kds/stream')).statusCode, 401);
});

test('restaurante autenticado ignora ID de outro restaurante no corpo', async () => {
  const cookie = await login('gerente-a');
  const created = await send('POST', '/api/pedidos', { numero: 77, restaurante_id: restaurantB }, cookie);
  assert.equal(created.statusCode, 201, created.body);
  assert.equal(created.json().restaurante_id, restaurantA);
  const list = await send('GET', '/api/pedidos', undefined, cookie);
  assert.equal(list.statusCode, 200);
  assert.ok(list.json().every(p => p.restaurante_id === restaurantA));
});

test('Restaurante B não lê ou altera pedidos do A', async () => {
  const ca = await login('gerente-a'), cb = await login('gerente-b');
  const created = await send('POST', '/api/pedidos', { numero: 78 }, ca);
  assert.equal(created.statusCode, 201);
  const id = created.json().id;
  const bList = await send('GET', '/api/pedidos', undefined, cb);
  assert.equal(bList.statusCode, 200);
  assert.equal(bList.json().length, 0);
  const forbidden = await send('PATCH', '/api/pedidos/' + id + '/status', { status: 'pronto' }, cb);
  assert.equal(forbidden.statusCode, 400);
  const aChange = await send('PATCH', '/api/pedidos/' + id + '/status', { status: 'pronto' }, ca);
  assert.equal(aChange.statusCode, 200);
});

test('Master não opera KDS sem contexto de restaurante', async () => {
  const cookie = await login('admin-main');
  assert.equal((await send('GET', '/api/pedidos', undefined, cookie)).statusCode, 403);
  assert.equal((await send('POST', '/api/pedidos', { numero: 12 }, cookie)).statusCode, 403);
  assert.equal((await send('GET', '/api/admin/restaurantes', undefined, cookie)).statusCode, 200);
});

test('Gerente cria terminal somente no próprio restaurante e pode revogar', async () => {
  const ca = await login('gerente-a');
  const created = await send('POST', '/api/admin/terminais', {
    nome: 'Caixa 1', login: 'caixa-a', senha: 'senha-super-forte-123!'
  }, ca);
  assert.equal(created.statusCode, 201, created.body);
  const userId = created.json().id;
  const cb = await login('gerente-b');
  assert.equal((await send('PATCH', '/api/admin/terminais/' + userId + '/ativo', { ativo: false }, cb)).statusCode, 404);
  assert.equal((await send('PATCH', '/api/admin/terminais/' + userId + '/ativo', { ativo: false }, ca)).statusCode, 200);
  const disabledLogin = await send('POST', '/api/auth/login', { login: 'caixa-a', senha: 'senha-super-forte-123!' });
  assert.equal(disabledLogin.statusCode, 401);
});

test('logout revoga a sessão e bloqueia o próximo acesso', async () => {
  const cookie = await login('gerente-a');
  assert.equal((await send('GET', '/api/auth/me', undefined, cookie)).statusCode, 200);
  assert.equal((await send('POST', '/api/auth/logout', {}, cookie)).statusCode, 200);
  assert.equal((await send('GET', '/api/auth/me', undefined, cookie)).statusCode, 401);
});

test('requisições de alteração sem Origin são recusadas', async () => {
  const cookie = await login('gerente-a');
  const response = await app.inject({ method: 'POST', url: '/api/pedidos', headers: { host: 'localhost', cookie }, payload: { numero: 79 } });
  assert.equal(response.statusCode, 403);
});


test('gerente redefine senha somente do seu terminal e derruba sessões antigas', async () => {
  const managerA = await login('gerente-a');
  const created = await send('POST', '/api/admin/terminais', {
    nome: 'Caixa protegido', login: 'caixa-protegido', senha: 'senha-super-forte-123!'
  }, managerA);
  assert.equal(created.statusCode, 201, created.body);
  const terminalId = created.json().id;
  const previousSession = await login('caixa-protegido');
  const managerB = await login('gerente-b');
  const deny = await send('PATCH', '/api/admin/terminais/' + terminalId + '/senha', {
    senha: 'outra-senha-super-forte!'
  }, managerB);
  assert.equal(deny.statusCode, 404);
  const changed = await send('PATCH', '/api/admin/terminais/' + terminalId + '/senha', {
    senha: 'outra-senha-super-forte!'
  }, managerA);
  assert.equal(changed.statusCode, 200, changed.body);
  assert.equal((await send('GET', '/api/auth/me', undefined, previousSession)).statusCode, 401);
  assert.equal((await send('POST', '/api/auth/login', {
    login: 'caixa-protegido', senha: 'senha-super-forte-123!'
  })).statusCode, 401);
  const latest = await send('POST', '/api/auth/login', {
    login: 'caixa-protegido', senha: 'outra-senha-super-forte!'
  });
  assert.equal(latest.statusCode, 200, latest.body);
});

test('troca da própria senha exige senha anterior e revoga sessão', async () => {
  const manager = await login('gerente-b');
  const bad = await send('POST', '/api/auth/password', {
    senha_atual: 'errada', nova_senha: 'uma-nova-senha-forte-123'
  }, manager);
  assert.equal(bad.statusCode, 403);
  const changed = await send('POST', '/api/auth/password', {
    senha_atual: 'senha-super-forte-123!', nova_senha: 'uma-nova-senha-forte-123'
  }, manager);
  assert.equal(changed.statusCode, 200, changed.body);
  assert.equal((await send('GET', '/api/auth/me', undefined, manager)).statusCode, 401);
  const fresh = await send('POST', '/api/auth/login', {
    login: 'gerente-b', senha: 'uma-nova-senha-forte-123'
  });
  assert.equal(fresh.statusCode, 200, fresh.body);
});
