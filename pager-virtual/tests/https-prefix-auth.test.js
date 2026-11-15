import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const dir = mkdtempSync(path.join(tmpdir(), 'avisaqui-https-auth-'));
process.env.DATA_PATH = dir;
process.env.PUBLIC_URL = 'https://example.test:8443/avisaqui/';
const { default: db } = await import('../src/db.js');
const { authRoutes, passwordHash } = await import('../src/auth.js');
const { default: Fastify } = await import('fastify');
const app = Fastify();
await app.register(authRoutes);
await app.ready();
after(async () => {
  await app.close();
  db.close();
  rmSync(dir, { recursive: true, force: true });
});

const now = Date.now();
const id = randomUUID();
db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)')
  .run(id, 'Restaurante HTTPS', 'restaurante-https', now);
db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?)')
  .run(randomUUID(), id, 'Gerente', 'gerentehttps', await passwordHash('senha-de-teste-12345!'), 'gerente', now, now);
const payload = { login: 'gerentehttps', senha: 'senha-de-teste-12345!' };
const login = headers => app.inject({ method: 'POST', url: '/api/auth/login', headers, payload });

test('login por proxy HTTPS reconhece a origem pública e devolve cookie Secure', async () => {
  const res = await login({ host: 'example.test:8443', origin: 'https://example.test:8443',
    'x-forwarded-prefix': '/avisaqui', 'x-forwarded-proto': 'https' });
  assert.equal(res.statusCode, 200, res.body);
  assert.match(res.headers['set-cookie'], /; Secure/);
  assert.match(res.headers['set-cookie'], /; HttpOnly/);
  assert.match(res.headers['set-cookie'], /; SameSite=Strict/);
});

test('login HTTP local continua disponível sem cookie Secure', async () => {
  const res = await login({ host: '192.168.0.6:8090', origin: 'http://192.168.0.6:8090' });
  assert.equal(res.statusCode, 200, res.body);
  assert.doesNotMatch(res.headers['set-cookie'], /; Secure/);
});

test('origem estranha não pode usar o login da API', async () => {
  const res = await login({ host: 'example.test:8443', origin: 'https://origem-estranha.test',
    'x-forwarded-prefix': '/avisaqui', 'x-forwarded-proto': 'https' });
  assert.equal(res.statusCode, 403, res.body);
});

test('cabeçalho X-Forwarded-Proto isolado não habilita cookie Secure no HTTP local', async () => {
  const res = await login({ host: '192.168.0.6:8090', origin: 'http://192.168.0.6:8090',
    'x-forwarded-proto': 'https' });
  assert.equal(res.statusCode, 200, res.body);
  assert.doesNotMatch(res.headers['set-cookie'], /; Secure/);
});

test('origem pública com Host diferente não pode autenticar nem definir cookie', async () => {
  const res = await login({ host: '192.168.0.6:8090', origin: 'https://example.test:8443',
    'x-forwarded-prefix': '/avisaqui', 'x-forwarded-proto': 'https' });
  assert.equal(res.statusCode, 403, res.body);
  assert.equal(res.headers['set-cookie'], undefined);
});
