// Integracao opt-in de laboratorio: agente Windows -> API -> KDS existente.
// Sem leitura de PRN no servidor; sem alteracao no caminho fisico da impressora.
import { randomBytes, randomUUID, createHash, timingSafeEqual } from 'node:crypto';
import { nanoid } from 'nanoid';
import db from '../db.js';
import { requireRestaurant } from '../auth.js';
import { sseManager } from '../sse.js';

const sha = value => createHash('sha256').update(value).digest('hex');
const authorized = (request, reply) => {
  const user = requireRestaurant(request, reply);
  if (!user) return null;
  if (!['gerente', 'master'].includes(user.papel)) {
    reply.code(403).send({ error: 'Somente gerente ou administrador' });
    return null;
  }
  return user;
};

function schema() {
  db.exec(`
    CREATE TABLE IF NOT EXISTS integracao_impressao_chaves (
      id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL, hash TEXT NOT NULL UNIQUE,
      criado_em INTEGER NOT NULL, revogado_em INTEGER,
      FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id)
    );
    CREATE TABLE IF NOT EXISTS integracao_impressao_eventos (
      id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL, chave_id TEXT NOT NULL,
      evento_origem TEXT NOT NULL, numero INTEGER NOT NULL,
      pedido_id TEXT, situacao TEXT NOT NULL, criado_em INTEGER NOT NULL,
      UNIQUE(chave_id, evento_origem),
      FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id)
    );
    CREATE INDEX IF NOT EXISTS idx_integracao_impressao_rest
      ON integracao_impressao_eventos(restaurante_id, criado_em);
  `);
}

function chaveValida(request) {
  const raw = request.headers['x-avisaqui-agent-key'];
  if (typeof raw !== 'string' || !/^[a-f0-9]{64}$/.test(raw)) return null;
  const digest = sha(raw);
  const row = db.prepare(`SELECT c.id,c.restaurante_id,c.hash
    FROM integracao_impressao_chaves c JOIN restaurantes r ON r.id=c.restaurante_id
    WHERE c.hash=? AND c.revogado_em IS NULL AND r.ativo=1`).get(digest);
  if (!row || !timingSafeEqual(Buffer.from(row.hash, 'hex'), Buffer.from(digest, 'hex'))) return null;
  return row;
}

export async function integracaoImpressaoRoutes(app) {
  schema();

  // Token mostrado uma unica vez ao gerente. Nunca persistir token em claro.
  app.post('/api/integracoes/impressao/chave', async (request, reply) => {
    const user = authorized(request, reply);
    if (!user) return;
    const token = randomBytes(32).toString('hex');
    const id = randomUUID();
    db.prepare('INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em) VALUES(?,?,?,?)')
      .run(id, user.restaurante_id, sha(token), Date.now());
    reply.header('Cache-Control', 'no-store');
    return reply.code(201).send({ id, token, aviso: 'Copie agora. O token nao sera exibido novamente.' });
  });

  app.get('/api/integracoes/impressao/chaves', async (request, reply) => {
    const user = authorized(request, reply);
    if (!user) return;
    return db.prepare('SELECT id,criado_em,revogado_em FROM integracao_impressao_chaves WHERE restaurante_id=? ORDER BY criado_em DESC')
      .all(user.restaurante_id);
  });

  app.delete('/api/integracoes/impressao/chaves/:id', async (request, reply) => {
    const user = authorized(request, reply);
    if (!user) return;
    const result = db.prepare('UPDATE integracao_impressao_chaves SET revogado_em=? WHERE id=? AND restaurante_id=? AND revogado_em IS NULL')
      .run(Date.now(), request.params.id, user.restaurante_id);
    return result.changes ? { ok: true } : reply.code(404).send({ error: 'Chave nao encontrada' });
  });

  app.get('/api/integracoes/impressao/eventos', async (request, reply) => {
    const user = authorized(request, reply);
    if (!user) return;
    return db.prepare(`SELECT evento_origem,numero,pedido_id,situacao,criado_em
      FROM integracao_impressao_eventos WHERE restaurante_id=? ORDER BY criado_em DESC LIMIT 50`)
      .all(user.restaurante_id);
  });

  // Protocolo do agente: apenas dados extraidos, nunca PRN ou documento fiscal completo.
  // Evento idempotente por credencial + identificador local estavel do agente.
  app.post('/api/integracoes/impressao/pedidos', async (request, reply) => {
    const credential = chaveValida(request);
    if (!credential) return reply.code(401).send({ error: 'Credencial do agente invalida' });
    const { evento_id, numero, itens = [] } = request.body || {};
    if (typeof evento_id !== 'string' || !/^[a-zA-Z0-9._:-]{8,100}$/.test(evento_id) ||
        !Number.isSafeInteger(numero) || numero <= 0 ||
        !Array.isArray(itens) || itens.length > 20 ||
        !itens.every(i => typeof i === 'string' && i.length <= 120)) {
      return reply.code(400).send({ error: 'Evento ou dados do pedido invalidos' });
    }
    const now = Date.now();
    const create = db.transaction(() => {
      const previous = db.prepare('SELECT pedido_id,situacao,numero FROM integracao_impressao_eventos WHERE chave_id=? AND evento_origem=?')
        .get(credential.id, evento_id);
      if (previous) return { status: 200, body: { repetido: true, pedido_id: previous.pedido_id, situacao: previous.situacao } };
      const existing = db.prepare("SELECT id FROM pedidos WHERE restaurante_id=? AND numero=? AND status IN ('preparo','pronto')")
        .get(credential.restaurante_id, numero);
      if (existing) {
        db.prepare(`INSERT INTO integracao_impressao_eventos
          (id,restaurante_id,chave_id,evento_origem,numero,pedido_id,situacao,criado_em)
          VALUES(?,?,?,?,?,?,?,?)`)
          .run(randomUUID(),credential.restaurante_id,credential.id,evento_id,numero,existing.id,'PENDENTE_DUPLICADO',now);
        return { status: 409, body: { situacao: 'PENDENTE_DUPLICADO', mensagem: 'Pedido ativo com esse numero; requer revisao no painel' } };
      }
      const pedido = {
        id: randomUUID(), restaurante_id: credential.restaurante_id, numero,
        token: nanoid(21), itens,
        status: 'preparo', created_at: now
      };
      db.prepare(`INSERT INTO pedidos(id,restaurante_id,numero,token,itens_json,status,created_at)
        VALUES(?,?,?,?,?,'preparo',?)`)
        .run(pedido.id,pedido.restaurante_id,numero,pedido.token,JSON.stringify(itens),now);
      db.prepare(`INSERT INTO integracao_impressao_eventos
        (id,restaurante_id,chave_id,evento_origem,numero,pedido_id,situacao,criado_em)
        VALUES(?,?,?,?,?,?,?,?)`)
        .run(randomUUID(),credential.restaurante_id,credential.id,evento_id,numero,pedido.id,'CRIADO',now);
      return { status: 201, body: { situacao: 'CRIADO', pedido } };
    });
    let outcome;
    try { outcome = create.immediate(); }
    catch (err) {
      if (String(err.code || '').startsWith('SQLITE_CONSTRAINT')) {
        return reply.code(409).send({ error: 'Conflito de identificacao. Nao reenviar com outro ID automaticamente.' });
      }
      throw err;
    }
    if (outcome.status === 201) {
      const p = outcome.body.pedido;
      const restaurante = db.prepare('SELECT nome FROM restaurantes WHERE id=?').get(p.restaurante_id);
      sseManager.notifyKds(p.restaurante_id, 'novo_pedido', { ...p, restaurante_nome: restaurante?.nome || '' });
    }
    return reply.code(outcome.status).send(outcome.body);
  });
}
