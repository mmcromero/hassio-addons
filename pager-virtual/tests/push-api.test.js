import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const tmp = mkdtempSync(path.join(tmpdir(), 'bipou-push-'));
process.env.DATA_PATH = tmp;
const [{ default: db }, { pushRoutes }, { default: Fastify }] = await Promise.all([
  import('../src/db.js'), import('../src/push.js'), import('fastify')
]);
const app = Fastify();
await app.register(pushRoutes);
await app.ready();

test('chave VAPID persistente e assinatura vinculada a pedido válido', async () => {
  const pub = await app.inject({ method: 'GET', url: '/api/push/public-key' });
  assert.equal(pub.statusCode, 200);
  assert.equal(pub.json().enabled, true);
  assert.ok(pub.json().publicKey.length > 60);
  assert.equal(statSync(path.join(tmp, 'push-vapid.json')).mode & 0o777, 0o600);

  const rest = randomUUID(), token = 'token-teste-push-123';
  const now = Date.now();
  db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)')
    .run(rest, 'Restaurante Push', 'rest-push', now);
  db.prepare("INSERT INTO pedidos(id,restaurante_id,numero,token,status,created_at) VALUES(?,?,?,?, 'preparo', ?)")
    .run('pedido-push', rest, 15, token, now);

  const url = '/api/push/assinaturas/' + token;
  const data = { endpoint: 'https://fcm.googleapis.com/fcm/send/abc',
    keys: { auth: 'exemplo-auth-teste', p256dh: 'exemplo-chave-publica-ficticia' } };
  const opts = { method: 'POST', url, payload: data, headers: {
    host: 'localhost', origin: 'http://localhost'
  } };
  assert.equal((await app.inject(opts)).statusCode, 201);
  assert.equal(db.prepare('SELECT count(*) n FROM push_assinaturas WHERE pedido_token=?').get(token).n, 1);
  assert.equal((await app.inject(opts)).statusCode, 201);
  assert.equal(db.prepare('SELECT count(*) n FROM push_assinaturas WHERE pedido_token=?').get(token).n, 1);
  assert.equal((await app.inject({ ...opts, url:'/api/push/assinaturas/token-desconhecido' })).statusCode, 404);
  assert.equal((await app.inject({ ...opts, headers: {
    host: 'localhost', origin: 'https://outro-site.example'
  } })).statusCode, 403);
  assert.equal((await app.inject({ ...opts, payload: {
    ...data, endpoint: 'https://127.0.0.1/private'
  } })).statusCode, 400);
});
test.after(async () => {
  await app.close();
  db.close();
  rmSync(tmp, { recursive: true, force: true });
});
