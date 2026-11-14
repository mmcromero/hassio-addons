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
function runBootstrap(env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['scripts/bootstrap-admin.js'], {
      env: { ...env, BIPOU_INITIAL_LOGIN: 'admin-stream',
        BIPOU_INITIAL_PASSWORD: 'senha-temporaria-stream-1234' }, stdio: 'ignore'
    });
    child.once('error', reject);
    child.once('exit', code => code === 0 ? resolve() : reject(new Error('Bootstrap: ' + code)));
  });
}
async function streamMessage(reader, match, timeoutMs = 7000) {
  const decoder = new TextDecoder();
  let content = '';
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    const result = await Promise.race([
      reader.read(),
      new Promise((_, reject) => setTimeout(() => reject(new Error('SSE timeout: ' + content)), Math.max(1, deadline - Date.now())))
    ]);
    if (result.done) throw new Error('Stream encerrado antes do evento ' + match);
    content += decoder.decode(result.value, { stream: true });
    if (content.includes(match)) return content;
  }
  throw new Error('SSE timeout: ' + content);
}

test('SSE real do KDS e do cliente transmite mudança de pedido', { timeout: 30000 }, async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'bipou-sse-http-'));
  const port = await freePort();
  const env = { ...process.env, DATA_PATH: dir, HOST: '127.0.0.1', PORT: String(port) };
  let child;
  const controllers = [];
  try {
    await runBootstrap(env);
    child = spawn(process.execPath, ['src/server.js'], { env, stdio: 'ignore' });
    const base = 'http://127.0.0.1:' + port;
    let ready = false;
    for (let i = 0; i < 120; i++) {
      if (child.exitCode !== null) throw new Error('Servidor terminou prematuramente');
      try { if ((await fetch(base + '/api/health')).ok) { ready = true; break; } } catch {}
      await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.ok(ready);
    async function api(method, url, data, cookie) {
      const response = await fetch(base + url, {
        method,
        headers: { Origin: base, ...(cookie ? { Cookie: cookie } : {}),
          ...(data === undefined ? {} : { 'Content-Type': 'application/json' }) },
        ...(data === undefined ? {} : { body: JSON.stringify(data) })
      });
      return { response, body: await response.json() };
    }
    const masterLogin = await api('POST', '/api/auth/login', {
      login: 'admin-stream', senha: 'senha-temporaria-stream-1234'
    });
    assert.equal(masterLogin.response.status, 200);
    const masterCookie = masterLogin.response.headers.get('set-cookie').split(';')[0];
    const createdRest = await api('POST', '/api/admin/restaurantes', {
      nome: 'Restaurante SSE', slug: 'restaurante-sse'
    }, masterCookie);
    assert.equal(createdRest.response.status, 201);
    const manager = await api('POST', '/api/admin/restaurantes/' + createdRest.body.id + '/gerentes', {
      nome: 'Gerente SSE', login: 'gerente-sse', senha: 'senha-gerente-sse-1234'
    }, masterCookie);
    assert.equal(manager.response.status, 201);
    const managerLogin = await api('POST', '/api/auth/login', {
      login: 'gerente-sse', senha: 'senha-gerente-sse-1234'
    });
    assert.equal(managerLogin.response.status, 200);
    const cookie = managerLogin.response.headers.get('set-cookie').split(';')[0];

    const kdsAbort = new AbortController(); controllers.push(kdsAbort);
    const kdsResponse = await fetch(base + '/api/kds/stream', {
      headers: { Cookie: cookie }, signal: kdsAbort.signal
    });
    assert.equal(kdsResponse.status, 200);
    assert.match(kdsResponse.headers.get('content-type') || '', /text\/event-stream/);
    const kdsReader = kdsResponse.body.getReader();
    await streamMessage(kdsReader, 'event: conectado');

    const created = await api('POST', '/api/pedidos', { numero: 123, itens: ['Lanche'] }, cookie);
    assert.equal(created.response.status, 201);
    assert.match(await streamMessage(kdsReader, 'novo_pedido'), /123/);

    const clientAbort = new AbortController(); controllers.push(clientAbort);
    const clientResponse = await fetch(base + '/api/pedidos/stream/' + encodeURIComponent(created.body.token), {
      signal: clientAbort.signal
    });
    assert.equal(clientResponse.status, 200);
    const clientReader = clientResponse.body.getReader();
    assert.match(await streamMessage(clientReader, '"preparo"'), /123/);

    const readyOrder = await api('PATCH', '/api/pedidos/' + created.body.id + '/status', {
      status: 'pronto'
    }, cookie);
    assert.equal(readyOrder.response.status, 200);
    assert.match(await streamMessage(clientReader, '"pronto"'), /pronto/);
    assert.match(await streamMessage(kdsReader, 'status_alterado'), /pronto/);
  } finally {
    for (const ctrl of controllers) ctrl.abort();
    if (child && child.exitCode === null) {
      child.kill('SIGTERM');
      await new Promise(resolve => child.once('exit', resolve));
    }
    rmSync(dir, { recursive: true, force: true });
  }
});
