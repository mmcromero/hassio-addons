import { randomUUID } from 'node:crypto';
import db from './db.js';
import { requireUser, currentUser, passwordHash, passwordMatches } from './auth.js';

// Registro aditivo, sem alteração de contas ou sessões antigas.
db.exec(`CREATE TABLE IF NOT EXISTS auditoria_reset_gerente (
  id TEXT PRIMARY KEY,
  ator_id TEXT NOT NULL,
  gerente_id TEXT NOT NULL,
  restaurante_id TEXT NOT NULL,
  acao TEXT NOT NULL,
  resultado TEXT NOT NULL,
  criado_em INTEGER NOT NULL
)`);

// Cota persistente em SQLite. Toda tentativa válida, inclusive com senha correta,
// consome um slot. A transação IMMEDIATE impede corrida entre processos.
db.exec(`CREATE TABLE IF NOT EXISTS admin_reset_limites (
  chave TEXT PRIMARY KEY,
  quantidade INTEGER NOT NULL,
  janela_ate INTEGER NOT NULL
)`);
const WINDOW_MS = 15 * 60 * 1000;
const LIMIT = 5;
function reservarTentativa(atorId, gerenteId) {
  const now = Date.now();
  const keys = ['actor:' + atorId, 'target:' + atorId + ':' + gerenteId];
  return db.transaction(() => {
    const rows = keys.map(key => db.prepare('SELECT quantidade, janela_ate FROM admin_reset_limites WHERE chave=?').get(key));
    if (rows.some(row => row && row.janela_ate > now && row.quantidade >= LIMIT)) return false;
    keys.forEach((key, index) => {
      const row = rows[index];
      const count = row && row.janela_ate > now ? row.quantidade + 1 : 1;
      const until = row && row.janela_ate > now ? row.janela_ate : now + WINDOW_MS;
      db.prepare(`INSERT INTO admin_reset_limites(chave,quantidade,janela_ate) VALUES(?,?,?)
        ON CONFLICT(chave) DO UPDATE SET quantidade=excluded.quantidade, janela_ate=excluded.janela_ate`)
        .run(key, count, until);
    });
    return true;
  }).immediate();
}

function masterContext(request, reply, id) {
  const user = requireUser(request, reply);
  if (!user) return null;
  if (user.papel !== 'master') {
    reply.code(403).send({ error: 'Acesso não autorizado' });
    return null;
  }
  if (user.restaurante_id !== id) {
    reply.code(403).send({ error: 'Selecione o restaurante solicitado' });
    return null;
  }
  const rest = db.prepare('SELECT id FROM restaurantes WHERE id=? AND ativo=1').get(id);
  if (!rest) {
    reply.code(404).send({ error: 'Restaurante não encontrado' });
    return null;
  }
  return user;
}

export async function managerAdministrationRoutes(app) {
  app.get('/api/admin/restaurantes/:restauranteId/gerentes', async (request, reply) => {
    const { restauranteId } = request.params;
    if (!masterContext(request, reply, restauranteId)) return;
    reply.header('Cache-Control', 'no-store');
    return db.prepare(`SELECT id, nome, login, ativo FROM usuarios
      WHERE restaurante_id=? AND papel='gerente' ORDER BY nome, id`).all(restauranteId);
  });

  app.patch('/api/admin/restaurantes/:restauranteId/gerentes/:id/senha', async (request, reply) => {
    const { restauranteId, id } = request.params;
    const master = masterContext(request, reply, restauranteId);
    if (!master) return;
    reply.header('Cache-Control', 'no-store');
    const body = request.body || {};
    if (typeof body.senha !== 'string' || body.senha.length < 12 || body.senha.length > 256 ||
        typeof body.senha_master_atual !== 'string' || body.senha_master_atual.length > 256 ||
        body.senha_master_atual.length === 0) {
      return reply.code(400).send({ error: 'Informe senha nova válida e senha atual do Master' });
    }
    const target = db.prepare(`SELECT id FROM usuarios
      WHERE id=? AND restaurante_id=? AND papel='gerente' AND ativo=1`).get(id, restauranteId);
    if (!target) return reply.code(404).send({ error: 'Gerente não encontrado' });

    if (!reservarTentativa(master.id, id)) {
      return reply.code(429).send({ error: 'Limite de tentativas. Tente mais tarde.' });
    }
    const actor = db.prepare(`SELECT senha_hash FROM usuarios WHERE id=? AND papel='master' AND ativo=1`).get(master.id);
    if (!actor || !(await passwordMatches(body.senha_master_atual, actor.senha_hash))) {
      return reply.code(403).send({ error: 'Reautenticação não autorizada' });
    }
    const nextHash = await passwordHash(body.senha);
    // A senha só é alterada se autorização, sessão, restaurante e alvo ainda forem válidos.
    const changed = db.transaction(() => {
      const actual = currentUser(request);
      if (!actual || actual.papel !== 'master' || actual.id !== master.id ||
          actual.restaurante_id !== restauranteId) return 'forbidden';
      const stillMaster = db.prepare(`SELECT senha_hash FROM usuarios WHERE id=? AND papel='master' AND ativo=1`).get(master.id);
      if (!stillMaster || stillMaster.senha_hash !== actor.senha_hash) return 'forbidden';
      const stillActive = db.prepare(`SELECT id FROM restaurantes WHERE id=? AND ativo=1`).get(restauranteId);
      const validTarget = db.prepare(`SELECT id FROM usuarios
        WHERE id=? AND restaurante_id=? AND papel='gerente' AND ativo=1`).get(id, restauranteId);
      if (!stillActive || !validTarget) return 'not-found';
      const now = Date.now();
      db.prepare('UPDATE usuarios SET senha_hash=?, atualizado_em=? WHERE id=?')
        .run(nextHash, now, id);
      db.prepare('UPDATE sessoes SET revogado_em=? WHERE usuario_id=? AND revogado_em IS NULL')
        .run(now, id);
      db.prepare(`INSERT INTO auditoria_reset_gerente
        (id,ator_id,gerente_id,restaurante_id,acao,resultado,criado_em)
        VALUES (?,?,?,?,?,?,?)`)
        .run(randomUUID(), master.id, id, restauranteId, 'redefinir_senha', 'sucesso', now);
      return 'ok';
    }).immediate();
    if (changed === 'forbidden') return reply.code(403).send({ error: 'Sessão ou contexto inválido' });
    if (changed === 'not-found') return reply.code(404).send({ error: 'Gerente ou restaurante não encontrado' });
    return { ok: true, sessoes_revogadas: true };
  });
}
