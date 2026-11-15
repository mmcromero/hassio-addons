import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import Fastify from 'fastify';

const dir = mkdtempSync(path.join(tmpdir(), 'avisaqui-pong-'));
process.env.DATA_PATH = dir;
process.env.AVISAQUI_PONG_EXPERIMENTAL = '0';
const { default: db } = await import('../src/db.js');
const disabled = Fastify();
await disabled.register((await import('../src/pong.js?disabled')).pongRoutes);
process.env.AVISAQUI_PONG_EXPERIMENTAL = '1';
const app = Fastify({ forceCloseConnections: true });
await app.register((await import('../src/pong.js?enabled')).pongRoutes);
await app.listen({ port: 0, host: '127.0.0.1' });
const base = 'http://127.0.0.1:' + app.server.address().port;
db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)').run('r', 'Sintético', 'sintetico', 1);
function order(n) {
  db.prepare('INSERT INTO pedidos(id,restaurante_id,numero,token,status,created_at) VALUES(?,?,?,?,?,?)')
    .run('p' + n, 'r', n, 't' + n, 'preparo', 1);
  return 't' + n;
}
const post = (route, payload) => app.inject({ method: 'POST', url: '/api/jogos/pong/' + route, payload });
after(async () => {
  await app.close(); await disabled.close(); db.close();
  rmSync(dir, { recursive: true, force: true });
});

test('Pong exige ativação explícita, pedido em preparo e jogador autorizado', async () => {
  assert.equal((await disabled.inject('/api/jogos/pong/disponivel')).statusCode, 404);
  assert.equal((await app.inject('/api/jogos/pong/disponivel')).statusCode, 200);
  assert.equal((await post('entrar', { token: 'inexistente' })).statusCode, 409);
  const token = order(1);
  const a = (await post('entrar', { token })).json();
  const b = (await post('entrar', { token })).json();
  assert.equal(a.side, 0); assert.equal(b.side, 1);
  assert.equal(b.status, 'jogando');
  assert.equal((await post('entrar', { token })).statusCode, 409);
  assert.equal((await post('mover', { token, player: 'invalido', y: 100 })).statusCode, 403);
  assert.equal((await post('mover', { token, player: a.player, y: 'NaN' })).statusCode, 400);
  assert.equal((await post('mover', { token, player: a.player, y: 100 })).statusCode, 200);
  db.prepare("UPDATE pedidos SET status='pronto' WHERE token=?").run(token);
  assert.equal((await post('mover', { token, player: a.player, y: 100 })).statusCode, 409);
  assert.equal((await post('entrar', { token })).statusCode, 409);
  await post('sair', { token, player: a.player });
  await post('sair', { token, player: b.player });
});

test('Pong limita SSE, libera conexões fechadas e encerra ao pedido ficar pronto', async () => {
  const token = order(2);
  const { player } = (await post('entrar', { token })).json();
  const controllers = [];
  try {
    for (let i = 0; i < 4; i++) {
      const controller = new AbortController(); controllers.push(controller);
      const response = await fetch(base + `/api/jogos/pong/eventos/${token}/${player}`, { signal: controller.signal });
      assert.equal(response.status, 200);
    }
    assert.equal((await fetch(base + `/api/jogos/pong/eventos/${token}/${player}`)).status, 429);
    controllers[0].abort();
    // Aguarda a notificação de fechamento TCP antes de reconectar.
    let response;
    const controller = new AbortController(); controllers.push(controller);
    for (let i = 0; i < 50; i++) {
      response = await fetch(base + `/api/jogos/pong/eventos/${token}/${player}`, { signal: controller.signal });
      if (response.status === 200) break;
      await new Promise(resolve => setTimeout(resolve, 10));
    }
    assert.equal(response.status, 200);
    db.prepare("UPDATE pedidos SET status='pronto' WHERE token=?").run(token);
    const text = await response.text();
    assert.match(text, /event: encerrado/);
  } finally { for (const controller of controllers) controller.abort(); }
  await post('sair', { token, player });
});

test('limite de partidas é liberado quando jogadores saem', async () => {
  const players = [];
  try {
    for (let i = 10; i < 74; i++) {
      const token = order(i);
      const response = await post('entrar', { token });
      assert.equal(response.statusCode, 200, response.body);
      players.push({ token, player: response.json().player });
    }
    const token = order(74);
    assert.equal((await post('entrar', { token })).statusCode, 503);
    await post('sair', players.shift());
    const response = await post('entrar', { token });
    assert.equal(response.statusCode, 200);
    players.push({ token, player: response.json().player });
  } finally { for (const player of players) await post('sair', player); }
});
