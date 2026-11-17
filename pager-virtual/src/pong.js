import { randomUUID, randomBytes, createHash } from 'node:crypto';
import db from './db.js';
import { readFileSync } from 'node:fs';

// Protótipo em memória: nenhuma tabela ou pedido é alterado.
const rooms = new Map();
const entryAttempts = new Map();
const sessions = new Map();
const COOKIE = 'avisaqui_pong_session';
const SESSION_TTL_MS = 15 * 60_000; // Valor inicial; requer validação de Segurança.
const hash = secret => createHash('sha256').update(secret).digest('hex');
// Origem pública é configuração do servidor, nunca um cabeçalho encaminhado pelo cliente.
function publicOrigin() {
  let raw = process.env.AVISAQUI_PONG_PUBLIC_ORIGIN || process.env.PUBLIC_URL || '';
  if (!raw) {
    try { raw = JSON.parse(readFileSync('/data/options.json', 'utf8')).public_url || ''; }
    catch { /* HTTP local sem configuração pública */ }
  }
  if (!raw) return null;
  try {
    const u = new URL(raw);
    if (!['https:', 'http:'].includes(u.protocol) || u.username || u.password || u.search || u.hash) return null;
    return u;
  } catch { return null; }
}
const configuredOrigin = publicOrigin();
const publicPrefix = configuredOrigin?.pathname.replace(/\/$/, '') || '';
// Cookie vinculado à configuração confiável da implantação, não ao Origin enviado pelo cliente.
// Uma instalação pública HTTPS deve usar a URL pública configurada; uma instalação
// HTTP local de testes deve iniciar sem URL pública configurada.
const cookiePath = () => (publicPrefix === '/avisaqui' ? '/avisaqui' : '') + '/api/jogos/pong';
const secureRequest = req => configuredOrigin ? configuredOrigin.protocol === 'https:' : req.protocol === 'https';
function cookieOptions(req, secret, clear = false) {
  return `${COOKIE}=${clear ? '' : encodeURIComponent(secret)}; Path=${cookiePath()}; HttpOnly; SameSite=Strict${secureRequest(req) ? '; Secure' : ''}${clear ? '; Max-Age=0' : ''}`;
}
function readCookie(req) {
  const match = String(req.headers.cookie || '').split(';').map(s => s.trim()).find(s => s.startsWith(COOKIE + '='));
  return match ? match.slice(COOKIE.length + 1) : '';
}
function sameOrigin(req) {
  const origin = req.headers.origin;
  const site = req.headers['sec-fetch-site'];
  if (site && !['same-origin', 'none'].includes(site)) return false;
  if (!origin || origin === 'null') return false;
  try {
    const u = new URL(origin);
    if (u.username || u.password || u.pathname !== '/' || u.search || u.hash) return false;
    if (configuredOrigin && u.origin === configuredOrigin.origin) return true;
    // Origem local direta; nunca aceitar cabeçalhos x-forwarded-* como prova.
    return u.origin === `${req.protocol}://${req.headers.host}`;
  } catch { return false; }
}
function validPost(req) { return sameOrigin(req) && /^application\/json(?:\s*;|$)/i.test(req.headers['content-type'] || ''); }
function authorize(req, participant) {
  const raw = readCookie(req);
  if (!raw || raw.length > 256) return null;
  const key = hash(raw), session = sessions.get(key);
  if (!session || Date.now() >= session.expires || session.participant !== participant) return null;
  const room = rooms.get(session.orderId);
  if (!room || room.status === 'encerrado' || room.players[session.side] !== participant || orderFor(room.token)?.status !== 'preparo') return null;
  return { key, session, room };
}
function revokeRoom(room) {
  for (const [key, s] of sessions) if (s.orderId === room.orderId) revokeSession(key, s);
}

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
const MAX_STREAMS_PER_SESSION = 1;
function rateLimit(map, key, limit, intervalMs) {
  const now = Date.now();
  const prev = map.get(key);
  if (!prev || now - prev.start >= intervalMs) { map.set(key, { start: now, count: 1 }); return true; }
  prev.count++;
  return prev.count <= limit;
}
function closeSessionStreams(session) {
  for (const res of session.streams || []) {
    try { if (!res.writableEnded && !res.destroyed) res.end(); } catch {}
  }
  session.streams?.clear();
}
function revokeSession(key, session, room) {
  sessions.delete(key);
  closeSessionStreams(session);
  if (room && room.players[session.side] === session.participant) {
    room.players[session.side] = null;
    room.status = 'aguardando';
  }
}
const CPU_PLAYER = '__pong_cpu__';
const clamp = (n, min, max) => Math.max(min, Math.min(max, n));
const snapshot = (room) => ({
  status: room.status, ball: room.ball, paddles: room.paddles,
  scores: room.scores, players: room.players.map(p => Boolean(p)),
  width: WIDTH, height: HEIGHT
});
function orderFor(token) {
  return db.prepare('SELECT id, status FROM pedidos WHERE token = ?').get(token);
}
export function stopPongForOrder(orderId) {
  const room = rooms.get(orderId);
  if (room) { stop(room); rooms.delete(orderId); }
}
function stop(room) {
  if (room.status === 'encerrado') return;
  room.status = 'encerrado';
  for (const res of room.listeners) {
    try { if (!res.writableEnded && !res.destroyed) { res.write('event: encerrado\ndata: {}\n\n'); res.end(); } } catch {}
  }
  room.listeners.clear();
  revokeRoom(room);
}
function send(room) {
  const data = 'data: ' + JSON.stringify(snapshot(room)) + '\n\n';
  for (const res of room.listeners) {
    if (res.writableEnded || res.destroyed) { room.listeners.delete(res); continue; }
    try { res.write(data); } catch { room.listeners.delete(res); }
  }
}
function advance(room) {
  if (room.players.filter(Boolean).length !== 2) return;
  if (room.mode === 'solo') {
    const target = clamp(room.ball.y + room.ball.vy * 5, 40, HEIGHT - 40);
    room.paddles[1] += clamp(target - room.paddles[1], -3.1, 3.1);
  }
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
const pongTimer = setInterval(() => {
  if (!enabled) return;
  for (const [key, value] of entryAttempts) if (Date.now() - value.start > 60_000) entryAttempts.delete(key);
  for (const [key, room] of rooms) {
    if (Date.now() - room.lastSeen > 30 * 60_000) { stop(room); rooms.delete(key); continue; }
    if (room.status !== 'encerrado') {
      for (const [key, s] of sessions) if (s.orderId === room.orderId && Date.now() >= s.expires) {
        revokeSession(key, s, room);
      }
      if (!room.lastOrderCheck || Date.now() - room.lastOrderCheck >= 1000) {
        room.lastOrderCheck = Date.now();
        const order = orderFor(room.token);
        if (!order || order.status !== 'preparo') { stop(room); continue; }
      }
      advance(room);
      if (room.listeners.size) send(room);
    }
  }
}, 50);
pongTimer.unref();

export async function pongRoutes(app) {
  if (!enabled) return;
  app.addHook('onClose', async () => {
    clearInterval(pongTimer);
    for (const room of rooms.values()) stop(room);
    rooms.clear();
    sessions.clear();
    entryAttempts.clear();
  });
  app.get('/api/jogos/pong/disponivel', async () => ({ enabled: true }));
  app.post('/api/jogos/pong/entrar', async (req, reply) => {
    reply.header('Cache-Control', 'no-store');
    if (!validPost(req)) return reply.code(403).send({ error: 'Origem ou conteúdo inválido' });
    const ip = req.ip;
    if (!rateLimit(entryAttempts, 'ip:' + ip, 12, 60_000)) return reply.code(429).send({ error: 'Muitas tentativas de ingresso' });
    const token = String(req.body?.token || '');
    if (token.length > 128) return reply.code(400).send({ error: 'Token inválido' });
    if (!rateLimit(entryAttempts, 'order:' + hash(token), 12, 60_000)) return reply.code(429).send({ error: 'Muitas tentativas para este pedido' });
    const mode = req.body?.mode;
    if (!['solo','dupla'].includes(mode)) return reply.code(400).send({ error: 'Modo inválido' });
    const order = orderFor(token);
    if (!order || order.status !== 'preparo') return reply.code(409).send({ error: 'Jogo indisponível para este pedido' });
    const existing = readCookie(req);
    if (existing) {
      const prior = sessions.get(hash(existing));
      if (prior && prior.expires > Date.now()) return reply.code(409).send({ error: 'Já existe uma sessão de Pong neste navegador' });
      if (prior) revokeSession(hash(existing), prior, rooms.get(prior.orderId));
    }
    let room = rooms.get(order.id);
    if (room?.status === 'encerrado') { rooms.delete(order.id); room = null; }
    if (room && room.mode !== mode) return reply.code(409).send({ error: 'Este pedido já tem uma partida em outro modo' });
    if (!room) {
      if (rooms.size >= MAX_ROOMS) return reply.code(503).send({ error: 'Limite de partidas simultâneas atingido' });
      room = { orderId: order.id, token, mode, status: 'aguardando', players: [null, mode === 'solo' ? CPU_PLAYER : null], paddles: [180, 180],
        ball: { x: 300, y: 180, vx: 3.5, vy: 2 }, scores: [0, 0],
        listeners: new Set(), lastSeen: Date.now() };
      rooms.set(order.id, room);
    }
    const side = room.players.findIndex(p => p === null);
    if (side < 0) return reply.code(409).send({ error: 'Sala cheia' });
    const player = randomUUID(), secret = randomBytes(32).toString('base64url');
    room.players[side] = player;
    room.lastSeen = Date.now();
    room.status = room.players.every(Boolean) ? 'jogando' : 'aguardando';
    sessions.set(hash(secret), { orderId: order.id, participant: player, side, expires: Date.now() + SESSION_TTL_MS, streams: new Set() });
    reply.header('Set-Cookie', cookieOptions(req, secret));
    return { player, side, mode: room.mode, ...snapshot(room) };
  });
  app.post('/api/jogos/pong/sair', async (req, reply) => {
    reply.header('Cache-Control', 'no-store');
    if (!validPost(req)) return reply.code(403).send({ error: 'Origem ou conteúdo inválido' });
    const auth = authorize(req, req.body?.player);
    if (!auth) return reply.code(403).send({ error: 'Sessão inválida' });
    const { key, room, session } = auth;
    revokeSession(key, session, room);
    reply.header('Set-Cookie', cookieOptions(req, '', true));
    room.lastSeen = Date.now();
    if (room.players.every(p => p === null || p === CPU_PLAYER)) { stop(room); rooms.delete(session.orderId); }
    else send(room);
    return { ok: true };
  });
  app.post('/api/jogos/pong/mover', async (req, reply) => {
    reply.header('Cache-Control', 'no-store');
    if (!validPost(req)) return reply.code(403).send({ error: 'Origem ou conteúdo inválido' });
    const auth = authorize(req, req.body?.player);
    if (!auth) return reply.code(403).send({ error: 'Sessão inválida' });
    const { room, session } = auth;
    const y = req.body?.y;
    if (typeof y !== 'number' || !Number.isFinite(y)) return reply.code(400).send({ error: 'Posição inválida' });
    const now = Date.now();
    if (session.lastMove && now - session.lastMove < 35) return reply.code(429).send({ error: 'Comandos muito frequentes' });
    session.lastMove = now;
    room.paddles[session.side] = clamp(y, 40, HEIGHT - 40);
    room.lastSeen = Date.now();
    return { ok: true };
  });
  app.get('/api/jogos/pong/eventos/:player', (req, reply) => {
    const auth = authorize(req, req.params.player);
    if (!auth) return reply.code(403).send({ error: 'Partida indisponível' });
    const { room, session } = auth;
    // Reconexão legítima substitui o stream antigo da mesma sessão, sem permitir
    // outro participante usar a credencial. O fechamento antigo não remove o novo.
    if (session.streams.size >= MAX_STREAMS_PER_SESSION) {
      for (const previous of [...session.streams]) {
        room.listeners.delete(previous);
        session.streams.delete(previous);
        try { if (!previous.writableEnded && !previous.destroyed) previous.end(); } catch {}
      }
    }
    if (room.listeners.size >= MAX_STREAMS_PER_ROOM) return reply.code(429).send({ error: 'Limite de conexões da partida atingido' });
    reply.hijack();
    reply.raw.setHeader('Content-Type', 'text/event-stream');
    reply.raw.setHeader('Cache-Control', 'no-store, no-transform');
    reply.raw.write('data: ' + JSON.stringify(snapshot(room)) + '\n\n');
    room.listeners.add(reply.raw);
    session.streams.add(reply.raw);
    reply.raw.on('close', () => { room.listeners.delete(reply.raw); session.streams.delete(reply.raw); });
  });
}
