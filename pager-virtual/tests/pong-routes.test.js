import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

async function freePort() {
  const server = createServer();
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const port = server.address().port;
  await new Promise(resolve => server.close(resolve));
  return port;
}

test('Pong registra GET disponibilidade e POST entrada no mesmo prefixo de API', { timeout: 20000 }, async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'avisaqui-pong-api-'));
  const port = await freePort();
  const child = spawn(process.execPath, ['src/server.js'], {
    env: { ...process.env, AVISAQUI_PONG_EXPERIMENTAL: '1', DATA_PATH: dir, PORT: String(port), HOST: '127.0.0.1' },
    stdio: 'ignore'
  });
  try {
    const base = 'http://127.0.0.1:' + port;
    let ready = false;
    for (let i = 0; i < 100; i++) {
      try { const r = await fetch(base + '/api/health'); if (r.ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready, 'servidor não iniciou');
    const available = await fetch(base + '/api/jogos/pong/disponivel');
    assert.equal(available.status, 200);
    const join = await fetch(base + '/api/jogos/pong/entrar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token: 'token-inexistente', mode: 'solo' })
    });
    assert.equal(join.status, 409, 'POST deve existir e rejeitar pedido inexistente, não retornar 404');
    assert.match((await join.json()).error, /indisponível/);
  } finally {
    child.kill('SIGTERM');
    await new Promise(resolve => child.once('exit', resolve)).catch(() => {});
    rmSync(dir, { recursive: true, force: true });
  }
});
