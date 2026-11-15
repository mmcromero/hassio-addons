import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';

// Home Assistant Supervisor 2026.01.1, supervisor/addons/validate.py,
// SCHEMA_ADDON_CONFIG / ATTR_WEBUI; mesma regra em supervisor/apps/validate.py.
// https://github.com/home-assistant/supervisor/blob/2026.01.1/supervisor/addons/validate.py
const supervisorWebui = /^(?:https?|\[PROTO:\w+\]):\/\/\[HOST\]:\[PORT:\d+\].*$/;

test('manifesto usa WebUI aceito pelo Supervisor, com porta declarada', () => {
  const yaml = readFileSync(new URL('../config.yaml', import.meta.url), 'utf8');
  const value = yaml.match(/^webui:\s*["']([^"']+)["']/m)?.[1];
  assert.ok(value && supervisorWebui.test(value), 'webui inválido para o catálogo do Supervisor: ' + value);
  const port = value.match(/\[PORT:(\d+)\]/)[1];
  assert.match(yaml, new RegExp('^  ' + port + '/tcp:', 'm'));
  assert.ok(value.endsWith('/webui'), 'botão deve usar a rota de abertura dedicada');
});

test('URL fixa da 0.1.16 anterior é rejeitada pela regra do Supervisor', () => {
  assert.equal(supervisorWebui.test('https://example.test:8443/avisaqui/landing.html'), false);
  assert.equal(supervisorWebui.test('http://[HOST]:[PORT:8095]/webui'), true);
});

async function freePort() {
  const socket = createServer();
  await new Promise(resolve => socket.listen(0, '127.0.0.1', resolve));
  const port = socket.address().port;
  await new Promise(resolve => socket.close(resolve));
  return port;
}

for (const scenario of [
  { name: 'URL HTTPS configurada', publicUrl: 'https://example.test:8443/avisaqui/', location: 'https://example.test:8443/avisaqui/landing.html' },
  { name: 'HTTP local sem URL pública', publicUrl: '', location: '/landing.html' },
  { name: 'prefixo do proxy sem URL pública', publicUrl: '', prefix: '/avisaqui', location: '/avisaqui/landing.html' }
]) {
  test('botão WebUI abre a landing: ' + scenario.name, { timeout: 20000 }, async () => {
    const data = mkdtempSync(path.join(tmpdir(), 'avisaqui-webui-'));
    const port = await freePort();
    const child = spawn(process.execPath, ['src/server.js'], {
      env: { ...process.env, DATA_PATH: data, PORT: String(port), HOST: '127.0.0.1',
        PUBLIC_URL: scenario.publicUrl, LOG_LEVEL: 'error' }, stdio: 'ignore'
    });
    try {
      const base = 'http://127.0.0.1:' + port;
      let ready = false;
      for (let attempt = 0; attempt < 100; attempt++) {
        if (child.exitCode !== null) throw new Error('Servidor encerrou antes do teste');
        try { if ((await fetch(base + '/api/health')).ok) { ready = true; break; } } catch {}
        await new Promise(resolve => setTimeout(resolve, 50));
      }
      assert.ok(ready, 'Servidor não iniciou');
      const response = await fetch(base + '/webui?next=https://untrusted.example/', {
        redirect: 'manual', headers: scenario.prefix ? { 'x-forwarded-prefix': scenario.prefix } : {}
      });
      assert.equal(response.status, 302);
      assert.equal(response.headers.get('location'), scenario.location);
      assert.equal(response.headers.get('cache-control'), 'no-store');
    } finally {
      if (child.exitCode === null) {
        const exited = new Promise(resolve => child.once('exit', resolve));
        child.kill('SIGTERM'); await exited;
      }
      rmSync(data, { recursive: true, force: true });
    }
  });
}
