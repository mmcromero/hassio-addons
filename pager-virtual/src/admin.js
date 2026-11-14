import { randomUUID } from 'node:crypto';
import db from './db.js';
import { passwordHash, requireUser, changeMasterContext } from './auth.js';

const simpleName = value => typeof value === 'string' && value.trim().length >= 2 && value.trim().length <= 120;
const loginValid = value => typeof value === 'string' && /^[a-z0-9._@-]{3,120}$/.test(value.trim().toLowerCase());
const slugValid = value => typeof value === 'string' && /^[a-z0-9-]{3,80}$/.test(value.trim().toLowerCase());

function mustBe(request, reply, roles) {
  const user = requireUser(request, reply);
  if (!user) return null;
  if (!roles.includes(user.papel)) {
    reply.code(403).send({ error: 'Acesso não autorizado' });
    return null;
  }
  return user;
}

function createAccount({ restauranteId, nome, login, senha, papel }) {
  const now = Date.now();
  const id = randomUUID();
  return passwordHash(senha).then(hash => {
    db.prepare(`
      INSERT INTO usuarios
      (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `).run(id, restauranteId, nome.trim(), login.trim().toLowerCase(), hash, papel, now, now);
    return { id, nome: nome.trim(), login: login.trim().toLowerCase(), papel, restaurante_id: restauranteId };
  });
}
function invalidAccount(body) {
  return !simpleName(body.nome) || !loginValid(body.login) ||
    typeof body.senha !== 'string' || body.senha.length < 12 || body.senha.length > 256;
}
function conflict(reply, error) {
  if (error.code?.startsWith('SQLITE_CONSTRAINT')) {
    return reply.code(409).send({ error: 'Identificador ou login já cadastrado' });
  }
  throw error;
}

export async function adminRoutes(app) {
  app.get('/api/admin/restaurantes', async (request, reply) => {
    if (!mustBe(request, reply, ['master'])) return;
    return db.prepare('SELECT id, nome, slug, ativo FROM restaurantes ORDER BY nome').all();
  });

  // Master seleciona restaurante na própria sessão; nunca altera a sessão do gerente.
  app.post('/api/admin/contexto/:restauranteId', async (request, reply) => {
    if (!mustBe(request, reply, ['master'])) return;
    if (!changeMasterContext(request, request.params.restauranteId)) {
      return reply.code(404).send({ error: 'Restaurante ativo não encontrado' });
    }
    return { ok: true, restaurante_id: request.params.restauranteId };
  });

  app.post('/api/admin/contexto/sair', async (request, reply) => {
    if (!mustBe(request, reply, ['master'])) return;
    changeMasterContext(request, null);
    return { ok: true };
  });

  app.post('/api/admin/restaurantes', async (request, reply) => {
    if (!mustBe(request, reply, ['master'])) return;
    const { nome, slug } = request.body || {};
    if (!simpleName(nome) || !slugValid(slug)) {
      return reply.code(400).send({ error: 'Informe nome e identificador válido (letras, números e hífen)' });
    }
    const restaurante = { id: randomUUID(), nome: nome.trim(), slug: slug.trim().toLowerCase() };
    try {
      db.prepare('INSERT INTO restaurantes (id, nome, slug, ativo, created_at) VALUES (?, ?, ?, 1, ?)')
        .run(restaurante.id, restaurante.nome, restaurante.slug, Date.now());
      return reply.code(201).send(restaurante);
    } catch (e) { return conflict(reply, e); }
  });

  // O Master cria SOMENTE o acesso inicial do gerente. A operação fica com o gerente.
  app.post('/api/admin/restaurantes/:restauranteId/gerentes', async (request, reply) => {
    if (!mustBe(request, reply, ['master'])) return;
    const restaurante = db.prepare('SELECT id FROM restaurantes WHERE id = ? AND ativo = 1').get(request.params.restauranteId);
    if (!restaurante) return reply.code(404).send({ error: 'Restaurante não encontrado' });
    const body = request.body || {};
    if (invalidAccount(body)) return reply.code(400).send({ error: 'Nome, login e senha de pelo menos 12 caracteres são obrigatórios' });
    try {
      return reply.code(201).send(await createAccount({
        restauranteId: restaurante.id, nome: body.nome, login: body.login, senha: body.senha, papel: 'gerente'
      }));
    } catch (e) { return conflict(reply, e); }
  });

  app.get('/api/admin/terminais', async (request, reply) => {
    const user = mustBe(request, reply, ['gerente']);
    if (!user) return;
    return db.prepare(`
      SELECT id, nome, login, ativo FROM usuarios
      WHERE restaurante_id = ? AND papel = 'operador' ORDER BY nome
    `).all(user.restaurante_id);
  });

  app.post('/api/admin/terminais', async (request, reply) => {
    const user = mustBe(request, reply, ['gerente']);
    if (!user) return;
    const body = request.body || {};
    if (invalidAccount(body)) return reply.code(400).send({ error: 'Informe nome, login e senha de pelo menos 12 caracteres' });
    try {
      return reply.code(201).send(await createAccount({
        restauranteId: user.restaurante_id, nome: body.nome, login: body.login, senha: body.senha, papel: 'operador'
      }));
    } catch (e) { return conflict(reply, e); }
  });

  // Gerente redefine a senha do terminal, sem assumir acesso de outro restaurante.
  app.patch('/api/admin/terminais/:id/senha', async (request, reply) => {
    const user = mustBe(request, reply, ['gerente']);
    if (!user) return;
    const terminal = db.prepare(`
      SELECT id FROM usuarios WHERE id = ? AND restaurante_id = ? AND papel = 'operador'
    `).get(request.params.id, user.restaurante_id);
    if (!terminal) return reply.code(404).send({ error: 'Terminal não encontrado' });
    let hash;
    try { hash = await passwordHash(request.body?.senha); }
    catch { return reply.code(400).send({ error: 'Senha deve ter entre 12 e 256 caracteres' }); }
    db.transaction(() => {
      db.prepare('UPDATE usuarios SET senha_hash = ?, atualizado_em = ? WHERE id = ?')
        .run(hash, Date.now(), terminal.id);
      db.prepare('UPDATE sessoes SET revogado_em = ? WHERE usuario_id = ? AND revogado_em IS NULL')
        .run(Date.now(), terminal.id);
    })();
    return { ok: true };
  });

  app.patch('/api/admin/terminais/:id/ativo', async (request, reply) => {
    const user = mustBe(request, reply, ['gerente']);
    if (!user) return;
    const ativo = request.body?.ativo;
    if (typeof ativo !== 'boolean') return reply.code(400).send({ error: 'Informe ativo como verdadeiro ou falso' });
    const info = db.prepare(`
      UPDATE usuarios SET ativo = ?, atualizado_em = ?
      WHERE id = ? AND restaurante_id = ? AND papel = 'operador'
    `).run(ativo ? 1 : 0, Date.now(), request.params.id, user.restaurante_id);
    if (!info.changes) return reply.code(404).send({ error: 'Terminal não encontrado' });
    if (!ativo) {
      db.prepare('UPDATE sessoes SET revogado_em = ? WHERE usuario_id = ? AND revogado_em IS NULL')
        .run(Date.now(), request.params.id);
    }
    return { ok: true, ativo };
  });
}
