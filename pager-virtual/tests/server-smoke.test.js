import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

async function getFreePort() {
  const server = createServer();
  await new Promise((resolve, reject) => server.once('error', reject).listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test('servidor inicia e primeiro acesso redireciona para configuração segura', { timeout: 20000 }, async () => {
  const dataDir = mkdtempSync(path.join(tmpdir(), 'bipou-server-smoke-'));
  const port = await getFreePort();
  const child = spawn(process.execPath, ['src/server.js'], {
    env: { ...process.env, DATA_PATH: dataDir, PORT: String(port), HOST: '127.0.0.1' },
    stdio: ['ignore', 'pipe', 'pipe']
  });
  let logs = '';
  child.stdout.on('data', chunk => { logs += chunk.toString(); });
  child.stderr.on('data', chunk => { logs += chunk.toString(); });
  try {
    let ready = false;
    for (let n = 0; n < 100; n++) {
      if (child.exitCode !== null) throw new Error('Servidor encerrou antes de iniciar');
      try {
        const res = await fetch('http://127.0.0.1:' + port + '/api/health');
        if (res.ok) { ready = true; break; }
      } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, 'servidor não iniciou');
    const root = await fetch('http://127.0.0.1:' + port + '/', { redirect: 'manual' });
    assert.equal(root.status, 302);
    assert.equal(root.headers.get('location'), '/setup.html');
    const kds = await fetch('http://127.0.0.1:' + port + '/kds.html', { redirect: 'manual' });
    assert.equal(kds.status, 302);
    assert.equal(kds.headers.get('location'), '/setup.html');
    const setup = await fetch('http://127.0.0.1:' + port + '/setup.html');
    assert.equal(setup.status, 200);
    assert.match(await setup.text(), /Primeiro acesso/);
    let codeMatch;
    for (let i = 0; i < 30; i++) {
      codeMatch = logs.match(/BIPOU PRIMEIRO ACESSO.*?([a-f0-9]{48})/);
      if (codeMatch) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(codeMatch, 'código inicial precisa aparecer nos logs privados');
    const origin = 'http://127.0.0.1:' + port;
    const headers = { Origin: origin, 'Content-Type': 'application/json' };
    const request = (url, payload, overrideOrigin = origin) => fetch(origin + url, {
      method: 'POST', headers: { ...headers, Origin: overrideOrigin },
      body: JSON.stringify(payload), redirect: 'manual'
    });
    const registration = { codigo: codeMatch[1], nome: 'Administrador Teste',
      login: 'master-teste', senha: 'senha-super-forte-teste-123' };
    const deniedExternal = await request('/api/setup/master', registration, 'http://exemplo-publico.com');
    assert.equal(deniedExternal.status, 403);
    const deniedPublicHost = await fetch(origin + '/api/setup/master', {
      method: 'POST',
      headers: { Host: 'site-publico.example', Origin: 'http://site-publico.example',
        'Content-Type': 'application/json' },
      body: JSON.stringify(registration)
    });
    assert.equal(deniedPublicHost.status, 403);

    const created = await request('/api/setup/master', registration);
    assert.equal(created.status, 201, await created.text());
    const repeated = await request('/api/setup/master', registration);
    assert.equal(repeated.status, 409);
    const needs = await fetch(origin + '/api/setup/status');
    assert.equal((await needs.json()).needs_setup, false);
    const unauth = await fetch(origin + '/admin.html', { redirect: 'manual' });
    assert.equal(unauth.status, 302);
    assert.equal(unauth.headers.get('location'), '/login.html');
    const signedIn = await request('/api/auth/login', {
      login: 'master-teste', senha: 'senha-super-forte-teste-123'
    });
    assert.equal(signedIn.status, 200, await signedIn.text());
    const cookie = signedIn.headers.get('set-cookie').split(';')[0];
    assert.ok(cookie.startsWith('bipou_session='));
    const admin = await fetch(origin + '/admin.html', { headers: { Cookie: cookie } });
    assert.equal(admin.status, 200);
    assert.match(await admin.text(), /Administra/);
    const masterKds = await fetch(origin + '/kds.html', {
      headers: { Cookie: cookie }, redirect: 'manual'
    });
    assert.equal(masterKds.status, 302);
    assert.equal(masterKds.headers.get('location'), '/admin.html');
  } finally {
    child.kill('SIGTERM');
    await new Promise(resolve => child.once('exit', resolve)).catch(() => {});
    rmSync(dataDir, { recursive: true, force: true });
  }
});
