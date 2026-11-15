import { randomUUID } from 'node:crypto';
import db from './db.js';
import { readFileSync } from 'node:fs';

// Protótipo em memória: nenhuma tabela ou pedido é alterado.
const rooms = new Map();
function experimentalEnabled() {
  if (process.env.AVISAQUI_PONG_EXPERIMENTAL === '1') return true;
  try {
    const opts = JSON.parse(readFileSync('/data/options.json', 'utf8'));
    return opts.pong_experimental === true;
  } catch { return false; }
}
const enabled = experimentalEnabled();
const WIDTH = 600, HEIGHT = 360;
const MAX_ROOMS = 64;
const MAX_STREAMS_PER_ROOM = 4;
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const snapshot = (room) => ({
  status: room.status, ball: room.ball, paddles: room.paddles,
  scores: room.scores, players: room.players.map(p => Boolean(p)),
  width: WIDTH, height: HEIGHT
});
function orderFor(token) {
  return db.prepare('SELECT id, status FROM pedidos WHERE token = ?').get(token);
}
function stop(room) {
  if (room.status === 'encerrado') return;
  room.status = 'encerrado';
  for (const res of room.listeners) {
    try { res.write('event: encerrado\ndata: {}\n\n'); res.end(); } catch {}
  }
  room.listeners.clear();
}
function send(room) {
  const data = 'data: ' + JSON.stringify(snapshot(room)) + '\n\n';
  for (const res of room.listeners) {
    try { res.write(data); } catch { room.listeners.delete(res); }
  }
}
function advance(room) {
  if (room.players.filter(Boolean).length !== 2) return;
  const b = room.ball;
  b.x += b.vx; b.y += b.vy;
  if (b.y < 9 || b.y > HEIGHT - 9) { b.vy *= -1; b.y = clamp(b.y, 9, HEIGHT - 9); }
  for (let side = 0; side < 2; side++) {
    const x = side === 0 ? 27 : WIDTH - 27;
    if ((side === 0 && b.vx < 0 && b.x <= x + 9 && b.x >= x - 9) ||
        (side === 1 && b.vx > 0 && b.x >= x - 9 && b.x <= x + 9)) {
      if (Math.abs(b.y - room.paddles[side]) < 43) {
        b.vx *= -1.04;
        b.vy = clamp((b.y - room.paddles[side]) * 0.12, -6, 6);
      }
    }
  }
  if (b.x < 0 || b.x > WIDTH) {
    room.scores[b.x < 0 ? 1 : 0]++;
    room.ball = { x: WIDTH / 2, y: HEIGHT / 2, vx: b.x < 0 ? 3.5 : -3.5, vy: 2 };
  }
}
setInterval(() => {
  if (!enabled) return;
  for (const [key, room] of rooms) {
    if (Date.now() - room.lastSeen > 30 * 60_000) { stop(room); rooms.delete(key); continue; }
    if (room.status !== 'encerrado') {
      if (!room.lastOrderCheck || Date.now() - room.lastOrderCheck >= 1000) {
        room.lastOrderCheck = Date.now();
        const order = orderFor(room.token);
        if (!order || order.status !== 'preparo') { stop(room); continue; }
      }
      advance(room);
      if (room.listeners.size) send(room);
    }
  }
}, 50).unref();

export async function pongRoutes(app) {
  if (!enabled) return;
  app.get('/api/jogos/pong/disponivel', async () => ({ enabled: true }));
  app.post('/api/jogos/pong/entrar', async (req, reply) => {
    const token = String(req.body?.token || '');
    const order = orderFor(token);
    if (!order || order.status !== 'preparo') return reply.code(409).send({ error: 'Jogo indisponível para este pedido' });
    let room = rooms.get(order.id);
    if (room?.status === 'encerrado') { rooms.delete(order.id); room = null; }
    if (!room) {
      if (rooms.size >= MAX_ROOMS) return reply.code(503).send({ error: 'Limite de partidas simultâneas atingido' });
      room = { token, status: 'aguardando', players: [null, null], paddles: [180, 180],
        ball: { x: 300, y: 180, vx: 3.5, vy: 2 }, scores: [0, 0],
        listeners: new Set(), lastSeen: Date.now() };
      rooms.set(order.id, room);
    }
    let side = room.players.findIndex(p => p === req.body?.player && p !== null);
    if (side < 0) side = room.players.findIndex(p => p === null);
    if (side < 0) return reply.code(409).send({ error: 'Sala cheia' });
    const player = room.players[side] || randomUUID();
    room.players[side] = player;
    room.lastSeen = Date.now();
    room.status = room.players.every(Boolean) ? 'jogando' : 'aguardando';
    return { player, side, ...snapshot(room) };
  });
  app.post('/api/jogos/pong/sair', async (req, reply) => {
    const order = orderFor(String(req.body?.token || ''));
    const room = order && rooms.get(order.id);
    if (!room) return { ok: true };
    const side = room.players.indexOf(req.body?.player);
    if (side < 0) return reply.code(403).send({ error: 'Jogador inválido' });
    room.players[side] = null;
    room.status = 'aguardando';
    room.lastSeen = Date.now();
    if (room.players.every(p => p === null)) { stop(room); rooms.delete(order.id); }
    else send(room);
    return { ok: true };
  });
  app.post('/api/jogos/pong/mover', async (req, reply) => {
    const order = orderFor(String(req.body?.token || ''));
    const room = order && rooms.get(order.id);
    if (!room || order.status !== 'preparo') {
      if (room) stop(room);
      return reply.code(409).send({ error: 'Partida encerrada' });
    }
    const side = room.players.indexOf(req.body?.player);
    if (side < 0) return reply.code(403).send({ error: 'Jogador inválido' });
    const y = Number(req.body?.y);
    if (!Number.isFinite(y)) return reply.code(400).send({ error: 'Posição inválida' });
    room.paddles[side] = clamp(y, 40, HEIGHT - 40);
    room.lastSeen = Date.now();
    return { ok: true };
  });
  app.get('/api/jogos/pong/eventos/:token/:player', (req, reply) => {
    const order = orderFor(req.params.token);
    const room = order && rooms.get(order.id);
    if (!room || order.status !== 'preparo' || !room.players.includes(req.params.player)) {
      return reply.code(403).send({ error: 'Partida indisponível' });
    }
    if (room.listeners.size >= MAX_STREAMS_PER_ROOM) return reply.code(429).send({ error: 'Limite de conexões da partida atingido' });
    reply.hijack();
    reply.raw.setHeader('Content-Type', 'text/event-stream');
    reply.raw.setHeader('Cache-Control', 'no-cache, no-transform');
    reply.raw.write('data: ' + JSON.stringify(snapshot(room)) + '\n\n');
    room.listeners.add(reply.raw);
    reply.raw.on('close', () => room.listeners.delete(reply.raw));
  });
}
