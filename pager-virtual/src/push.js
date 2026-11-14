import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import webpush from 'web-push';
import db from './db.js';

const dir = process.env.DATA_PATH || (fs.existsSync('/data') ? '/data' : path.resolve(process.cwd(), 'data'));
const keyFile = path.join(dir, 'push-vapid.json');
let keys;
try {
  if (fs.existsSync(keyFile)) keys = JSON.parse(fs.readFileSync(keyFile, 'utf8'));
  if (!keys?.publicKey || !keys?.privateKey) {
    keys = webpush.generateVAPIDKeys();
    fs.mkdirSync(dir, { recursive: true });
    fs.writeFileSync(keyFile, JSON.stringify(keys), { mode: 0o600, flag: 'wx' });
  }
  webpush.setVapidDetails(process.env.VAPID_SUBJECT || 'https://github.com/mmcromero/pager-virtual', keys.publicKey, keys.privateKey);
} catch (err) {
  // Configuração inválida não deve derrubar o pager principal.
  console.error('[PUSH] Indisponível:', err.message);
  keys = null;
}

db.exec(`
CREATE TABLE IF NOT EXISTS push_assinaturas (
  pedido_token TEXT NOT NULL,
  endpoint TEXT NOT NULL,
  p256dh TEXT NOT NULL,
  auth TEXT NOT NULL,
  criado_em INTEGER NOT NULL,
  PRIMARY KEY (pedido_token, endpoint),
  FOREIGN KEY (pedido_token) REFERENCES pedidos(token) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS idx_push_pedido ON push_assinaturas(pedido_token);
`);

const allowedEndpoint = input => {
  try {
    const u = new URL(input);
    const host = u.hostname.toLowerCase();
    return u.protocol === 'https:' && !u.username && !u.password &&
      host !== 'localhost' && !host.endsWith('.local') &&
      host !== '127.0.0.1' && host !== '::1' &&
      !/^10\.|^192\.168\.|^169\.254\.|^172\.(1[6-9]|2\d|3[01])\.|^0\./.test(host) &&
      input.length <= 2048;
  } catch { return false; }
};

function sameOrigin(request) {
  try {
    const origin = new URL(request.headers.origin);
    if (origin.host === request.headers.host &&
        origin.protocol === request.protocol + ':') return true;
    let publicUrl = process.env.PUBLIC_URL || '';
    const optionsFile = '/data/options.json';
    if (!publicUrl && fs.existsSync(optionsFile)) {
      publicUrl = JSON.parse(fs.readFileSync(optionsFile, 'utf8')).public_url || '';
    }
    return !!publicUrl && origin.origin === new URL(publicUrl).origin &&
      origin.host === request.headers.host;
  } catch { return false; }
}

export async function pushRoutes(app) {
  app.get('/api/push/public-key', async (_req, reply) => {
    reply.header('Cache-Control', 'no-store');
    return { enabled: !!keys, publicKey: keys?.publicKey || null };
  });

  app.post('/api/push/assinaturas/:token', async (request, reply) => {
    if (!sameOrigin(request)) return reply.code(403).send({ error: 'Origem não autorizada' });
    if (!keys) return reply.code(503).send({ error: 'Notificações indisponíveis' });
    const token = request.params.token;
    const pedido = db.prepare('SELECT token, status FROM pedidos WHERE token = ?').get(token);
    if (!pedido) return reply.code(404).send({ error: 'Pedido não encontrado' });
    if (pedido.status === 'entregue') return reply.code(409).send({ error: 'Pedido já entregue' });
    const subscription = request.body;
    const endpoint = subscription?.endpoint;
    const auth = subscription?.keys?.auth;
    const p256dh = subscription?.keys?.p256dh;
    if (typeof endpoint !== 'string' || !allowedEndpoint(endpoint) ||
        typeof auth !== 'string' || auth.length < 8 || auth.length > 256 ||
        typeof p256dh !== 'string' || p256dh.length < 16 || p256dh.length > 256) {
      return reply.code(400).send({ error: 'Assinatura inválida' });
    }
    db.prepare(`INSERT INTO push_assinaturas(pedido_token, endpoint, p256dh, auth, criado_em)
      VALUES (?, ?, ?, ?, ?)
      ON CONFLICT(pedido_token,endpoint) DO UPDATE SET p256dh=excluded.p256dh,
      auth=excluded.auth, criado_em=excluded.criado_em`)
      .run(token, endpoint, p256dh, auth, Date.now());
    return reply.code(201).send({ ok: true });
  });
}

export async function notifyOrderReady(pedido) {
  if (!keys) return;
  const subscriptions = db.prepare('SELECT * FROM push_assinaturas WHERE pedido_token = ?').all(pedido.token);
  const payload = JSON.stringify({
    title: 'Bipou — pedido pronto!',
    body: 'Seu pedido #' + pedido.numero + ' está pronto para retirada.',
    url: '/cliente.html?token=' + encodeURIComponent(pedido.token) + '&pedido=' + encodeURIComponent(pedido.numero),
    tag: 'bipou-' + pedido.id
  });
  await Promise.allSettled(subscriptions.map(async row => {
    try {
      await webpush.sendNotification({
        endpoint: row.endpoint, keys: { auth: row.auth, p256dh: row.p256dh }
      }, payload, { TTL: 900 });
    } catch (err) {
      if ([404, 410].includes(err.statusCode)) {
        db.prepare('DELETE FROM push_assinaturas WHERE pedido_token = ? AND endpoint = ?')
          .run(row.pedido_token, row.endpoint);
      } else console.warn('[PUSH] Falha de envio:', err.statusCode || err.message);
    }
  }));
  // Limpeza simples de assinaturas de pedidos antigos.
  db.prepare('DELETE FROM push_assinaturas WHERE criado_em < ?').run(Date.now() - 7 * 86400000);
}
