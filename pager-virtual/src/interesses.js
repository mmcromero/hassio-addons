import { randomUUID } from 'node:crypto';
import db from './db.js';
import { requireUser } from './auth.js';

// Migração aditiva: contatos ficam no mesmo volume SQLite persistente do add-on.
db.exec(`
  CREATE TABLE IF NOT EXISTS interesses_piloto (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    telefone TEXT NOT NULL,
    email TEXT NOT NULL,
    criado_em INTEGER NOT NULL
  );
  CREATE INDEX IF NOT EXISTS idx_interesses_piloto_criado ON interesses_piloto(criado_em DESC);
`);

const recent = new Map();
const LIMIT_WINDOW = 60 * 60 * 1000;
function sameOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return false;
  try {
    const url = new URL(origin);
    const configured = process.env.PUBLIC_URL;
    return (url.host === request.headers.host && ['http:', 'https:'].includes(url.protocol)) ||
      (configured && origin === new URL(configured).origin);
  } catch { return false; }
}
export async function interessesRoutes(app) {
  app.post('/api/piloto/interesse', async (request, reply) => {
    if (!sameOrigin(request)) return reply.code(403).send({ error: 'Origem não autorizada' });
    const body = request.body || {};
    // Campo invisível: rejeita envios automatizados sem guardar dados.
    if (body.website) return reply.code(400).send({ error: 'Não foi possível enviar o cadastro' });
    const nome = typeof body.nome === 'string' ? body.nome.trim() : '';
    const telefone = typeof body.telefone === 'string' ? body.telefone.trim() : '';
    const email = typeof body.email === 'string' ? body.email.trim().toLowerCase() : '';
    if (nome.length < 2 || nome.length > 120 || !/^[+()\d\s.-]{8,24}$/.test(telefone) ||
        email.length > 254 || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      return reply.code(400).send({ error: 'Confira nome, telefone e e-mail' });
    }
    const key = request.ip;
    const now = Date.now();
    if (recent.size > 5000) recent.clear();
    const history = (recent.get(key) || []).filter(t => now - t < LIMIT_WINDOW);
    if (history.length >= 5) return reply.code(429).send({ error: 'Limite de envios atingido. Tente novamente mais tarde.' });
    history.push(now); recent.set(key, history);
    db.prepare('INSERT INTO interesses_piloto (id, nome, telefone, email, criado_em) VALUES (?, ?, ?, ?, ?)')
      .run(randomUUID(), nome, telefone, email, now);
    return reply.code(201).send({ ok: true, mensagem: 'Recebemos seu interesse! Obrigado. Entraremos em contato quando houver novidades sobre o piloto.' });
  });

  app.get('/api/admin/interesses-piloto', async (request, reply) => {
    const user = requireUser(request, reply);
    if (!user) return;
    if (user.papel !== 'master') return reply.code(403).send({ error: 'Acesso exclusivo do Master Admin' });
    reply.header('Cache-Control', 'no-store');
    return db.prepare('SELECT id, nome, telefone, email, criado_em FROM interesses_piloto ORDER BY criado_em DESC LIMIT 1000').all();
  });
}
