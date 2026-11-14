import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

async function freePort() {
  const sock = createServer();
  await new Promise(resolve => sock.listen(0, '127.0.0.1', resolve));
  const port = sock.address().port;
  await new Promise(resolve => sock.close(resolve));
  return port;
}
async function processSuccess(process) {
  return new Promise((resolve, reject) => {
    process.once('error', reject);
    process.once('exit', code => code === 0 ? resolve() : reject(new Error('Exit ' + code)));
  });
}
test('origem HTTPS de proxy usa cookie Secure sem impedir login HTTP local', { timeout: 30000 }, async () => {
  const data = mkdtempSync(path.join(tmpdir(), 'bipou-proxy-test-'));
  const port = await freePort();
  const env = {
    ...process.env, DATA_PATH: data, PORT: String(port), HOST: '127.0.0.1',
    PUBLIC_URL: 'https://pager.example'
  };
  const bootstrap = spawn(process.execPath, ['scripts/bootstrap-admin.js'], {
    env: { ...env, BIPOU_INITIAL_LOGIN: 'admin-proxy-test',
      BIPOU_INITIAL_PASSWORD: 'senha-proxy-forte-123!' }, stdio: 'ignore'
  });
  let child;
  try {
    await processSuccess(bootstrap);
    child = spawn(process.execPath, ['src/server.js'], { env, stdio: 'ignore' });
    const local = 'http://127.0.0.1:' + port;
    let ready = false;
    for (let i = 0; i < 120; i++) {
      if (child.exitCode !== null) throw new Error('Backend encerrou');
      try { if ((await fetch(local + '/api/health')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, 'Servidor não iniciou');

    const credentials = { login: 'admin-proxy-test', senha: 'senha-proxy-forte-123!' };
    async function login(origin, host) {
      return fetch(local + '/api/auth/login', {
        method: 'POST',
        headers: { Origin: origin, Host: host, 'Content-Type': 'application/json' },
        body: JSON.stringify(credentials)
      });
    }
    const localLogin = await login(local, '127.0.0.1:' + port);
    assert.equal(localLogin.status, 200, await localLogin.text());
    const localCookie = localLogin.headers.get('set-cookie');
    assert.match(localCookie, /HttpOnly/);
    assert.match(localCookie, /SameSite=Strict/);
    assert.doesNotMatch(localCookie, /; Secure/);

    const proxyLogin = await login('https://pager.example', 'pager.example');
    assert.equal(proxyLogin.status, 200, await proxyLogin.text());
    assert.match(proxyLogin.headers.get('set-cookie'), /; Secure/);
    const proxyCookie = proxyLogin.headers.get('set-cookie').split(';')[0];
    const profile = await fetch(local + '/api/auth/me', {
      headers: { Cookie: proxyCookie, Host: 'pager.example' }
    });
    assert.equal(profile.status, 200);

    const invalid = await login('https://other.example', 'pager.example');
    assert.equal(invalid.status, 403);
  } finally {
    if (child && child.exitCode === null) {
      child.kill('SIGTERM');
      await new Promise(resolve => child.once('exit', resolve));
    }
    rmSync(data, { recursive: true, force: true });
  }
});
