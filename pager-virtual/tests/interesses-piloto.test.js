import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const temp = mkdtempSync(path.join(tmpdir(), 'avisaqui-piloto-'));
process.env.DATA_PATH = temp;
const { default: db } = await import('../src/db.js');
const { interessesRoutes } = await import('../src/interesses.js');
const { authRoutes, passwordHash } = await import('../src/auth.js');
const { default: Fastify } = await import('fastify');
const app = Fastify();
await app.register(authRoutes);
await app.register(interessesRoutes);
await app.ready();
after(async () => { await app.close(); db.close(); rmSync(temp, { recursive: true, force: true }); });

const headers = { host: 'localhost', origin: 'http://localhost' };
const payload = { nome: 'Cliente Teste', telefone: '(11) 99999-8888', email: 'cliente@example.com' };
test('formulário público valida, grava e confirma', async () => {
  const response = await app.inject({ method:'POST', url:'/api/piloto/interesse', headers, payload });
  assert.equal(response.statusCode, 201, response.body);
  assert.equal(response.json().ok, true);
  assert.equal(db.prepare('SELECT count(*) n FROM interesses_piloto').get().n, 1);
  assert.equal((await app.inject({method:'POST',url:'/api/piloto/interesse',payload})).statusCode,403);
  assert.equal((await app.inject({method:'POST',url:'/api/piloto/interesse',headers,payload:{...payload,email:'invalido'}})).statusCode,400);
});
test('somente master consulta contatos', async () => {
  assert.equal((await app.inject({method:'GET',url:'/api/admin/interesses-piloto'})).statusCode,401);
  const now=Date.now();
  db.prepare('INSERT INTO usuarios (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)')
    .run(randomUUID(),null,'Admin','master-piloto',await passwordHash('senha-super-forte-123!'),'master',now,now);
  const login=await app.inject({method:'POST',url:'/api/auth/login',headers,payload:{login:'master-piloto',senha:'senha-super-forte-123!'}});
  assert.equal(login.statusCode,200,login.body);
  const cookie=login.headers['set-cookie'].split(';')[0];
  const response=await app.inject({method:'GET',url:'/api/admin/interesses-piloto',headers:{...headers,cookie}});
  assert.equal(response.statusCode,200,response.body);
  assert.equal(response.json().length,1);
  assert.equal(response.json()[0].email,payload.email);
  assert.equal(response.headers['cache-control'],'no-store');
});
