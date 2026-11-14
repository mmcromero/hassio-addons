import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

async function portLivre() {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}
async function waitExit(proc) {
  return new Promise((resolve, reject) => {
    proc.once('error', reject);
    proc.once('exit', code => code === 0 ? resolve() : reject(new Error('Processo encerrou com código ' + code)));
  });
}

test('servidor real isola restaurantes e perfis e revoga terminal', { timeout: 30000 }, async () => {
  const data = mkdtempSync(path.join(tmpdir(), 'bipou-roles-'));
  const port = await portLivre();
  const env = { ...process.env, DATA_PATH: data, PORT: String(port), HOST: '127.0.0.1' };
  const bootstrap = spawn(process.execPath, ['scripts/bootstrap-admin.js'], {
    env: { ...env, BIPOU_INITIAL_LOGIN: 'master-test', BIPOU_INITIAL_PASSWORD: 'senha-master-forte-teste-123' },
    stdio: 'ignore'
  });
  let server;
  try {
    await waitExit(bootstrap);
    server = spawn(process.execPath, ['src/server.js'], { env, stdio: 'ignore' });
    const base = 'http://127.0.0.1:' + port;
    let ready = false;
    for (let i = 0; i < 120; i++) {
      if (server.exitCode !== null) throw new Error('Servidor caiu na inicialização');
      try {
        const response = await fetch(base + '/api/health');
        if (response.ok) { ready = true; break; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready);
    async function call(method, url, data, cookie) {
      const response = await fetch(base + url, {
        method, redirect: 'manual',
        headers: {
          Origin: base, ...(cookie ? { Cookie: cookie } : {}),
          ...(data === undefined ? {} : { 'Content-Type': 'application/json' })
        },
        ...(data === undefined ? {} : { body: JSON.stringify(data) })
      });
      const body = await response.json().catch(() => ({}));
      return { status: response.status, body, cookie: response.headers.get('set-cookie')?.split(';')[0] };
    }
    async function login(user, password) {
      const result = await call('POST', '/api/auth/login', { login: user, senha: password });
      assert.equal(result.status, 200, JSON.stringify(result.body));
      return result.cookie;
    }
    const master = await login('master-test', 'senha-master-forte-teste-123');
    const restaurants = [];
    for (const [slug, manager] of [['resta', 'gerente-a'], ['restb', 'gerente-b']]) {
      const restaurant = await call('POST', '/api/admin/restaurantes', { nome: slug, slug }, master);
      assert.equal(restaurant.status, 201);
      restaurants.push(restaurant.body.id);
      const user = await call('POST', '/api/admin/restaurantes/' + restaurant.body.id + '/gerentes', {
        nome: manager, login: manager, senha: 'senha-gerente-forte-123'
      }, master);
      assert.equal(user.status, 201);
    }
    const managerA = await login('gerente-a', 'senha-gerente-forte-123');
    const managerB = await login('gerente-b', 'senha-gerente-forte-123');
    const a = await call('POST', '/api/admin/terminais', {
      nome: 'Caixa A', login: 'caixa-a', senha: 'senha-caixa-forte-123'
    }, managerA);
    assert.equal(a.status, 201);
    const b = await call('POST', '/api/admin/terminais', {
      nome: 'Caixa B', login: 'caixa-b', senha: 'senha-caixa-forte-123'
    }, managerB);
    assert.equal(b.status, 201);
    const caixaA = await login('caixa-a', 'senha-caixa-forte-123');
    const caixaB = await login('caixa-b', 'senha-caixa-forte-123');

    const created = await call('POST', '/api/pedidos', {
      numero: 42, restaurante_id: restaurants[1]
    }, caixaA);
    assert.equal(created.status, 201);
    assert.equal(created.body.restaurante_id, restaurants[0]);
    const listB = await call('GET', '/api/pedidos', undefined, caixaB);
    assert.equal(listB.status, 200);
    assert.equal(listB.body.length, 0);
    const denied = await call('PATCH', '/api/pedidos/' + created.body.id + '/status', {
      status: 'pronto'
    }, caixaB);
    assert.equal(denied.status, 400);
    const readyOrder = await call('PATCH', '/api/pedidos/' + created.body.id + '/status', {
      status: 'pronto'
    }, caixaA);
    assert.equal(readyOrder.status, 200);

    const crossTerminal = await call('PATCH', '/api/admin/terminais/' + a.body.id + '/ativo', {
      ativo: false
    }, managerB);
    assert.equal(crossTerminal.status, 404);
    const disabled = await call('PATCH', '/api/admin/terminais/' + a.body.id + '/ativo', {
      ativo: false
    }, managerA);
    assert.equal(disabled.status, 200);
    assert.equal((await call('GET', '/api/auth/me', undefined, caixaA)).status, 401);
    assert.equal((await call('GET', '/api/auth/me', undefined, caixaB)).status, 200);
    assert.equal((await call('GET', '/api/pedidos', undefined, master)).status, 403);
  } finally {
    if (server && server.exitCode === null) {
      server.kill('SIGTERM');
      await new Promise(resolve => server.once('exit', resolve));
    }
    rmSync(data, { recursive: true, force: true });
  }
});
