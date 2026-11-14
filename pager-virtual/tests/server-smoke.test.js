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
  child.stdout.on('data', part => { logs += part.toString(); });
  child.stderr.on('data', part => { logs += part.toString(); });
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
    const status = await fetch('http://127.0.0.1:' + port + '/api/setup/status');
    assert.deepEqual(await status.json(), { needs_setup: true });
    let codeMatch;
    for (let attempt = 0; attempt < 30; attempt++) {
      codeMatch = logs.match(/BIPOU PRIMEIRO ACESSO[^\\n]*?([a-f0-9]{48})/);
      if (codeMatch) break;
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(codeMatch, 'código temporário deve aparecer nos logs locais');
    const origin = 'http://127.0.0.1:' + port;
    const registration = { codigo: codeMatch[1], nome: 'Administrador Teste',
      login: 'master-teste', senha: 'senha-super-forte-teste-123' };
    const post = (url, payload, sentOrigin = origin) => fetch(origin + url, {
      method: 'POST',
      headers: { Origin: sentOrigin, 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
      redirect: 'manual'
    });
    const forbidden = await post('/api/setup/master', registration, 'http://outro-host.example');
    assert.equal(forbidden.status, 403);
    const created = await post('/api/setup/master', registration);
    assert.equal(created.status, 201, await created.text());
    const repeated = await post('/api/setup/master', registration);
    assert.equal(repeated.status, 409);


  } finally {
    child.kill('SIGTERM');
    await new Promise(resolve => child.once('exit', resolve)).catch(() => {});
    rmSync(dataDir, { recursive: true, force: true });
  }
});
