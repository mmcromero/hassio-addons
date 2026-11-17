import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import Fastify from 'fastify';
import { createHash } from 'node:crypto';

const dir = mkdtempSync(path.join(tmpdir(), 'avisaqui-pong-'));
process.env.DATA_PATH = dir;
process.env.AVISAQUI_PONG_EXPERIMENTAL = '0';
const { default: db } = await import('../src/db.js');
const disabled = Fastify();
await disabled.register((await import('../src/pong.js?disabled')).pongRoutes);
process.env.AVISAQUI_PONG_EXPERIMENTAL = '1';
const app = Fastify({ forceCloseConnections: true });
// Mesmo singleton utilizado pela rota real de pedidos.
const pong = await import('../src/pong.js');
await app.register(pong.pongRoutes);
await app.register((await import('../src/routes/pedidos.js')).pedidosRoutes);
await app.listen({ port: 0, host: '127.0.0.1' });
const base = 'http://127.0.0.1:' + app.server.address().port;
db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)').run('r', 'Sintético', 'sintetico', 1);
function order(n) {
  db.prepare('INSERT INTO pedidos(id,restaurante_id,numero,token,status,created_at) VALUES(?,?,?,?,?,?)')
    .run('p' + n, 'r', n, 't' + n, 'preparo', 1);
  return 't' + n;
}
const post = (route, payload, cookie = '') => app.inject({
  method: 'POST', url: '/api/jogos/pong/' + route, payload,
  headers: { origin: 'http://localhost', host: 'localhost',
    'sec-fetch-site': 'same-origin', ...(cookie ? { cookie } : {}) }
});
const join = async (token, mode = 'dupla') => {
  const response = await post('entrar', { token, mode });
  return { response, data: response.json(), cookie: response.headers['set-cookie']?.split(';')[0] };
};
after(async () => {
  await app.close(); await disabled.close(); db.close();
  rmSync(dir, { recursive: true, force: true });
});

test('Pong exige ativação, Origin e autorização individual', async () => {
  assert.equal((await disabled.inject('/api/jogos/pong/disponivel')).statusCode, 404);
  assert.equal((await app.inject('/api/jogos/pong/disponivel')).statusCode, 200);
  assert.equal((await app.inject({ method: 'POST', url: '/api/jogos/pong/entrar',
    payload: { token: 'x', mode: 'solo' } })).statusCode, 403);
  assert.equal((await post('entrar', { token: 'inexistente', mode: 'solo' })).statusCode, 409);
  const token = order(1);
  const a = await join(token);
  const b = await join(token);
  assert.equal(a.response.statusCode, 200, a.response.body);
  assert.equal(b.response.statusCode, 200, b.response.body);
  assert.equal(a.data.side, 0); assert.equal(b.data.side, 1);
  assert.match(a.response.headers['set-cookie'], /HttpOnly; SameSite=Strict/);
  assert.equal((await post('mover', { player: a.data.player, y: 100 }, b.cookie)).statusCode, 403);
  assert.equal((await post('mover', { player: a.data.player, y: 100 }, a.cookie)).statusCode, 200);
  assert.equal((await post('mover', { player: a.data.player, y: 'NaN' }, a.cookie)).statusCode, 400);
  const crossOrigin = await app.inject({ method: 'POST', url: '/api/jogos/pong/mover',
    payload: { player: b.data.player, y: 120 },
    headers: { origin: 'https://site-externo.example', host: 'localhost',
      'sec-fetch-site': 'cross-site', cookie: b.cookie } });
  assert.equal(crossOrigin.statusCode, 403, 'origem externa não pode controlar jogador');
  assert.equal((await post('mover', { player: b.data.player, y: 120 }, a.cookie)).statusCode, 403,
    'cookie de outro participante não pode mover jogador');
  db.prepare("UPDATE pedidos SET status='pronto' WHERE token=?").run(token);
  assert.equal((await post('mover', { player: a.data.player, y: 120 }, a.cookie)).statusCode, 403);
  assert.equal((await join(token)).response.statusCode, 409);
});

test('SSE usa cookie e ID do participante, sem token do pedido na URL', async () => {
  const token = order(2);
  const a = await join(token);
  const b = await join(token);
  const url = base + '/api/jogos/pong/eventos/' + a.data.player;
  assert.equal((await fetch(url)).status, 403);
  assert.equal((await fetch(url, { headers: { cookie: b.cookie } })).status, 403);
  const controller = new AbortController();
  try {
    const response = await fetch(url, { headers: { cookie: a.cookie }, signal: controller.signal });
    assert.equal(response.status, 200);
    const reader = response.body.getReader();
    const first = new TextDecoder().decode((await reader.read()).value);
    assert.match(first, /^data: .*\n\n/, 'SSE inicia com estado completo');
    const reconnected = await fetch(url, { headers: { cookie: a.cookie } });
    assert.equal(reconnected.status, 200, 'reconexão SSE da mesma sessão deve funcionar');
    await reconnected.body.cancel();
    await post('sair', { player: a.data.player }, a.cookie);
    const closed = await Promise.race([(async () => {
      while (true) { const chunk = await reader.read(); if (chunk.done) return true; }
    })(), new Promise(resolve => setTimeout(() => resolve(false), 1500))]);
    assert.equal(closed, true, 'stream encerrado após saída');
    assert.equal((await post('mover', { player: b.data.player, y: 140 }, b.cookie)).statusCode, 200,
      'saída do jogador A não revoga a sessão válida do jogador B');
  } finally {
    controller.abort();
    await post('sair', { player: b.data.player }, b.cookie);
  }
});


test('revogação imediata usa ID textual e fecha SSE do participante', async () => {
  const token = order(4);
  const a = await join(token, 'solo');
  assert.equal(a.response.statusCode, 200);
  const controller = new AbortController();
  try {
    const response = await fetch(base + '/api/jogos/pong/eventos/' + a.data.player, {
      headers: { cookie: a.cookie }, signal: controller.signal
    });
    assert.equal(response.status, 200);
    const reader = response.body.getReader();
    await reader.read();
    db.prepare("UPDATE pedidos SET status='pronto' WHERE token=?").run(token);
    pong.stopPongForOrder('p4');
    const next = await reader.read();
    assert.match(new TextDecoder().decode(next.value || new Uint8Array()), /event: encerrado/);
    assert.equal((await post('mover', { player: a.data.player, y: 100 }, a.cookie)).statusCode, 403);
  } finally { controller.abort(); }
});

test('alteração persistida do pedido encerra automaticamente a partida e o SSE', async () => {
  const token = order(5);
  const a = await join(token, 'solo');
  assert.equal(a.response.statusCode, 200, a.response.body);
  const controller = new AbortController();
  try {
    const response = await fetch(base + '/api/jogos/pong/eventos/' + a.data.player, {
      headers: { cookie: a.cookie }, signal: controller.signal
    });
    assert.equal(response.status, 200);
    const reader = response.body.getReader();
    await reader.read();
    db.prepare("UPDATE pedidos SET status='pronto' WHERE token=?").run(token);
    const closed = await Promise.race([
      (async () => {
        const decoder = new TextDecoder();
        let data = '';
        while (true) {
          const next = await reader.read();
          if (next.done) return /event: encerrado/.test(data);
          data += decoder.decode(next.value, { stream: true });
          if (data.includes('event: encerrado')) return true;
        }
      })(),
      new Promise(resolve => setTimeout(() => resolve(false), 2500))
    ]);
    assert.equal(closed, true, 'mudança de status encerra SSE sem chamada manual a stopPongForOrder');
    assert.equal((await post('mover', { player: a.data.player, y: 100 }, a.cookie)).statusCode, 403);
  } finally { controller.abort(); }
});

test('PATCH autenticado de pedido pronto encerra Pong e revoga sessão', async () => {
  const token = order(6);
  const a = await join(token, 'solo');
  assert.equal(a.response.statusCode, 200, a.response.body);
  const secret = createHash('sha256').update('pong-test-auth-session-6').digest('hex');
  const now = Date.now();
  db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?)')
    .run('u6', 'r', 'Operador Teste', 'operador-pong-6', 'hash-inutil-em-teste', 'operador', now, now);
  db.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
    .run('s6', 'u6', createHash('sha256').update(secret).digest('hex'), now, now + 60_000);
  const controller = new AbortController();
  try {
    const response = await fetch(base + '/api/jogos/pong/eventos/' + a.data.player, {
      headers: { cookie: a.cookie }, signal: controller.signal
    });
    assert.equal(response.status, 200);
    const reader = response.body.getReader();
    await reader.read();
    const patch = await app.inject({
      method: 'PATCH', url: '/api/pedidos/p6/status',
      payload: { status: 'pronto' },
      headers: { cookie: 'bipou_session=' + secret, origin: 'http://localhost', host: 'localhost' }
    });
    assert.equal(patch.statusCode, 200, patch.body);
    assert.equal(patch.json().status, 'pronto');
    const event = await Promise.race([
      (async () => {
        const decoder = new TextDecoder(); let buffer = '';
        while (true) {
          const chunk = await reader.read();
          if (chunk.done) return buffer;
          buffer += decoder.decode(chunk.value, { stream: true });
          if (buffer.includes('event: encerrado')) return buffer;
        }
      })(),
      new Promise(resolve => setTimeout(() => resolve(''), 2000))
    ]);
    assert.match(event, /event: encerrado/, 'PATCH deve encerrar SSE imediatamente');
    assert.equal((await post('mover', { player: a.data.player, y: 100 }, a.cookie)).statusCode, 403);
  } finally { controller.abort(); }
});

test('sessão Pong expirada não permite mover nem reconectar SSE', async () => {
  const token = order(7);
  const a = await join(token, 'solo');
  assert.equal(a.response.statusCode, 200, a.response.body);
  const originalNow = Date.now;
  const future = originalNow() + 16 * 60_000;
  try {
    Date.now = () => future;
    assert.equal((await post('mover', { player: a.data.player, y: 100 }, a.cookie)).statusCode, 403,
      'sessão expirada não pode mover');
    const response = await fetch(base + '/api/jogos/pong/eventos/' + a.data.player, {
      headers: { cookie: a.cookie }
    });
    assert.equal(response.status, 403, 'sessão expirada não pode reconectar SSE');
  } finally {
    Date.now = originalNow;
  }
});

test('HTTPS público configura cookie Secure e Path sem confiar em X-Forwarded-Proto', async () => {
  const previous = process.env.AVISAQUI_PONG_PUBLIC_ORIGIN;
  process.env.AVISAQUI_PONG_PUBLIC_ORIGIN = 'https://pager.example/avisaqui';
  let secureApp;
  try {
    const securePong = await import('../src/pong.js?secure-cookie-test');
    secureApp = Fastify();
    await secureApp.register(securePong.pongRoutes);
    const token = order(8);
    const response = await secureApp.inject({
      method: 'POST', url: '/api/jogos/pong/entrar',
      payload: { token, mode: 'solo' },
      headers: {
        origin: 'https://pager.example', host: 'internal:8099',
        'x-forwarded-proto': 'http', 'sec-fetch-site': 'same-origin'
      }
    });
    assert.equal(response.statusCode, 200, response.body);
    assert.match(response.headers['set-cookie'], /; Secure(?:;|$)/);
    assert.match(response.headers['set-cookie'], /; Path=\/avisaqui\/api\/jogos\/pong;/);
    assert.match(response.headers['set-cookie'], /; HttpOnly; SameSite=Strict/);
    const spoofed = await secureApp.inject({
      method: 'POST', url: '/api/jogos/pong/mover',
      payload: { player: response.json().player, y: 100 },
      headers: {
        origin: 'https://attacker.example', host: 'internal:8099',
        'x-forwarded-host': 'pager.example', 'x-forwarded-proto': 'https',
        'sec-fetch-site': 'cross-site',
        cookie: response.headers['set-cookie'].split(';')[0]
      }
    });
    assert.equal(spoofed.statusCode, 403, 'cabeçalhos encaminhados não autorizam origem externa');
  } finally {
    if (secureApp) await secureApp.close();
    if (previous === undefined) delete process.env.AVISAQUI_PONG_PUBLIC_ORIGIN;
    else process.env.AVISAQUI_PONG_PUBLIC_ORIGIN = previous;
  }
});

test('POST Pong rejeita Origin ausente, null, divergente e Fetch Metadata cross-site', async () => {
  const token = order(9);
  const scenarios = [
    { name: 'Origin ausente', headers: { host: 'localhost' } },
    { name: 'Origin null', headers: { origin: 'null', host: 'localhost' } },
    { name: 'Origin com caminho', headers: { origin: 'http://localhost/externo', host: 'localhost' } },
    { name: 'Origin com porta diferente', headers: { origin: 'http://localhost:9999', host: 'localhost' } },
    { name: 'Fetch Metadata cross-site', headers: {
      origin: 'http://localhost', host: 'localhost', 'sec-fetch-site': 'cross-site'
    } },
    { name: 'Fetch Metadata same-site', headers: {
      origin: 'http://localhost', host: 'localhost', 'sec-fetch-site': 'same-site'
    } }
  ];
  for (const scenario of scenarios) {
    const response = await app.inject({
      method: 'POST', url: '/api/jogos/pong/entrar',
      payload: { token, mode: 'solo' }, headers: scenario.headers
    });
    assert.equal(response.statusCode, 403, scenario.name + ': ' + response.body);
  }
  const valid = await join(token, 'solo');
  assert.equal(valid.response.statusCode, 200, 'requisições rejeitadas não impedem ingresso legítimo');
  await post('sair', { player: valid.data.player }, valid.cookie);
});

test('refresh reconecta SSE com mesma sessão sem permitir segunda entrada', async () => {
  const token = order(10);
  const a = await join(token, 'solo');
  assert.equal(a.response.statusCode, 200, a.response.body);
  const url = base + '/api/jogos/pong/eventos/' + a.data.player;
  const firstController = new AbortController();
  const secondController = new AbortController();
  try {
    const first = await fetch(url, { headers: { cookie: a.cookie }, signal: firstController.signal });
    assert.equal(first.status, 200);
    const firstReader = first.body.getReader();
    await firstReader.read();
    firstController.abort(); // simula navegação/refresh: conexão SSE anterior é perdida
    const second = await fetch(url, { headers: { cookie: a.cookie }, signal: secondController.signal });
    assert.equal(second.status, 200, 'mesmo cookie pode restabelecer SSE');
    const secondReader = second.body.getReader();
    const initial = new TextDecoder().decode((await secondReader.read()).value);
    assert.match(initial, /^data: .*\n\n/, 'reconexão recebe estado atual');
    assert.equal((await post('mover', { player: a.data.player, y: 130 }, a.cookie)).statusCode, 200);
    // Endereço sintético exclusivo: isola o limite global por IP da verificação de sessão duplicada.
    const duplicate = await app.inject({
      method: 'POST', url: '/api/jogos/pong/entrar',
      remoteAddress: '198.51.100.10',
      payload: { token, mode: 'solo' },
      headers: { origin: 'http://localhost', host: 'localhost',
        'sec-fetch-site': 'same-origin', cookie: a.cookie }
    });
    assert.equal(duplicate.statusCode, 409, 'sessão duplicada deve ser rejeitada sem atingir limite por IP');
    const saida = await post('sair', { player: a.data.player }, a.cookie);
    assert.equal(saida.statusCode, 200, 'saída do participante deve ser aceita');
    // Eventos SSE enviados antes da saída podem continuar no buffer do cliente.
    // Consumir esses eventos até o encerramento real, limitado pelo prazo.
    let timeout;
    const closed = await Promise.race([
      (async () => {
        while (true) {
          const next = await secondReader.read();
          if (next.done) return true;
        }
      })(),
      new Promise(resolve => { timeout = setTimeout(() => resolve(false), 1500); })
    ]).finally(() => clearTimeout(timeout));
    assert.equal(closed, true, 'saída fecha SSE reconectado');
  } finally {
    firstController.abort();
    secondController.abort();
  }
});

test('limite de ingresso protege pedidos contra repetição', async () => {
  const token = order(3);
  let blocked = false;
  for (let i = 0; i < 20; i++) {
    const result = await post('entrar', { token, mode: 'solo' });
    if (result.statusCode === 429) { blocked = true; break; }
  }
  assert.equal(blocked, true);
});
