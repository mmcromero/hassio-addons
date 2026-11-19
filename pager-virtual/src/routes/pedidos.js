import { nanoid } from 'nanoid';
import { notifyOrderReady } from '../push.js';
import { notifyGoogleWalletReady, generateSaveUrl } from '../wallet.js';
import { stopPongForOrder } from '../pong.js';
import db from '../db.js';
import { sseManager } from '../sse.js';
import { requireRestaurant, currentUser } from '../auth.js';

export async function pedidosRoutes(fastify, options) {
  // 1. Listar pedidos ativos para o KDS (Cozinha/Balcão)
  fastify.get('/api/pedidos', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    const pedidos = db.prepare(`
      SELECT p.*, r.nome as restaurante_nome
      FROM pedidos p
      JOIN restaurantes r ON p.restaurante_id = r.id
      WHERE p.restaurante_id = ? AND p.status IN ('preparo', 'pronto')
      ORDER BY p.created_at ASC
    `).all(user.restaurante_id);

    return pedidos.map(p => ({
      ...p,
      itens: p.itens_json ? JSON.parse(p.itens_json) : []
    }));
  });

  // 1.1 Listar histórico de pedidos finalizados com filtro de período e preservação de privacidade (Issue #36)
  fastify.get('/api/pedidos/historico', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    const { periodo = 'hoje', limite = 50 } = request.query || {};

    let dataFiltro = "(p.entregue_at IS NULL OR date(p.entregue_at / 1000, 'unixepoch', 'localtime') = date('now', 'localtime'))";
    if (periodo === 'ontem') {
      dataFiltro = "date(p.entregue_at / 1000, 'unixepoch', 'localtime') = date('now', 'localtime', '-1 day')";
    } else if (periodo === '7dias') {
      dataFiltro = "date(p.entregue_at / 1000, 'unixepoch', 'localtime') >= date('now', 'localtime', '-7 days')";
    } else if (periodo === 'todos') {
      dataFiltro = "1=1";
    }

    const pedidos = db.prepare(`
      SELECT p.id, p.numero, p.restaurante_id, p.status, p.created_at, p.pronto_at, p.entregue_at, p.itens_json,
             r.nome as restaurante_nome
      FROM pedidos p
      JOIN restaurantes r ON p.restaurante_id = r.id
      WHERE p.restaurante_id = ? AND p.status = 'entregue' AND ${dataFiltro}
      ORDER BY COALESCE(p.entregue_at, p.created_at) DESC
      LIMIT ?
    `).all(user.restaurante_id, Math.min(Number(limite) || 50, 100));

    const resumoHoje = db.prepare(`
      SELECT COUNT(*) as total
      FROM pedidos
      WHERE restaurante_id = ? AND status = 'entregue'
        AND (entregue_at IS NULL OR date(entregue_at / 1000, 'unixepoch', 'localtime') = date('now', 'localtime'))
    `).get(user.restaurante_id);

    return {
      periodo,
      total_hoje: resumoHoje ? resumoHoje.total : 0,
      pedidos: pedidos.map(p => ({
        id: p.id,
        numero: p.numero,
        restaurante_id: p.restaurante_id,
        restaurante_nome: p.restaurante_nome,
        status: p.status,
        created_at: p.created_at,
        pronto_at: p.pronto_at,
        entregue_at: p.entregue_at,
        itens: p.itens_json ? JSON.parse(p.itens_json) : []
      }))
    };
  });

  // 2. Criar novo pedido (chamado pelo Interceptador de PDV ou pelo KDS)
  fastify.post('/api/pedidos', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    const { numero, itens = [], cliente_nome = null, cliente_telefone = null } = request.body || {};
    const restaurante_id = user.restaurante_id;
    if (!Array.isArray(itens) || itens.length > 20 ||
        !itens.every(i => typeof i === 'string' && i.length <= 120)) {
      return reply.code(400).send({ error: 'Lista de itens inválida' });
    }

    const nome = cliente_nome == null ? null : String(cliente_nome).trim();
    const telefone = cliente_telefone == null ? null : String(cliente_telefone).replace(/[^0-9]/g, '');
    if ((nome && nome.length > 80) || (telefone && (telefone.length < 10 || telefone.length > 15))) {
      return reply.code(400).send({ error: 'Nome ou telefone inválido' });
    }
    const restaurante = db.prepare('SELECT id, nome FROM restaurantes WHERE id = ? AND ativo = 1').get(restaurante_id);
    if (!restaurante) return reply.code(400).send({ error: 'Restaurante inválido' });
    const criar = db.transaction(() => {
      const cfg = db.prepare('SELECT * FROM sequencias_pedidos WHERE restaurante_id = ?').get(restaurante_id);
      const automatico = cfg?.modo === 'automatico' && (numero === undefined || numero === null || numero === '');
      const numeroNormalizado = Number(automatico ? cfg.proximo_numero : numero);
      if (!Number.isSafeInteger(numeroNormalizado) || numeroNormalizado <= 0) {
        return { erro: 'Informe um número de pedido válido', codigo: 400 };
      }
      const duplicado = db.prepare("SELECT id FROM pedidos WHERE restaurante_id = ? AND numero = ? AND status IN ('preparo', 'pronto')").get(restaurante_id, numeroNormalizado);
      if (duplicado) return { erro: 'Já existe um pedido ativo com esse número', codigo: 409 };
      const id = nanoid(12), token = nanoid(21), now = Date.now();
      db.prepare(`INSERT INTO pedidos
        (id, restaurante_id, numero, token, itens_json, status, created_at, cliente_nome, cliente_telefone)
        VALUES (?, ?, ?, ?, ?, 'preparo', ?, ?, ?)`)
        .run(id, restaurante_id, numeroNormalizado, token, JSON.stringify(itens), now, nome || null, telefone || null);
      if (automatico) db.prepare('UPDATE sequencias_pedidos SET proximo_numero = ? WHERE restaurante_id = ?')
        .run(numeroNormalizado + 1, restaurante_id);
      return { pedido: { id, restaurante_id, numero: numeroNormalizado, token, itens,
        status: 'preparo', created_at: now, restaurante_nome: restaurante.nome, cliente_nome: nome || null, cliente_telefone: telefone || null } };
    });
    let resultado;
    try { resultado = criar.immediate(); }
    catch (err) {
      if (String(err.code || '').startsWith('SQLITE_CONSTRAINT')) {
        return reply.code(409).send({ error: 'Número ativo já utilizado; atualize e tente novamente' });
      }
      throw err;
    }
    if (resultado.erro) return reply.code(resultado.codigo).send({ error: resultado.erro });
    const novoPedido = resultado.pedido;

    // Notifica telas KDS conectadas
    sseManager.notifyKds(restaurante_id, 'novo_pedido', novoPedido);

    return reply.code(201).send(novoPedido);
  });

  // Configuração mínima da sequência, sempre por restaurante autenticado.
  fastify.get('/api/pedidos/sequencia', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    return db.prepare('SELECT modo, proximo_numero FROM sequencias_pedidos WHERE restaurante_id = ?')
      .get(user.restaurante_id) || { modo: 'manual', proximo_numero: 1 };
  });

  fastify.put('/api/pedidos/sequencia', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    if (!['gerente', 'master'].includes(user.papel)) return reply.code(403).send({ error: 'Somente gerente pode alterar a sequência' });
    const { modo, proximo_numero } = request.body || {};
    if (!['manual', 'automatico'].includes(modo) || !Number.isSafeInteger(proximo_numero) || proximo_numero <= 0) {
      return reply.code(400).send({ error: 'Configuração inválida' });
    }
    const atualizar = db.transaction(() => {
      const ativos = db.prepare("SELECT COUNT(*) AS total FROM pedidos WHERE restaurante_id = ? AND status IN ('preparo','pronto')").get(user.restaurante_id).total;
      if (ativos) return false;
      db.prepare(`INSERT INTO sequencias_pedidos (restaurante_id, modo, proximo_numero)
        VALUES (?, ?, ?) ON CONFLICT(restaurante_id) DO UPDATE SET modo=excluded.modo, proximo_numero=excluded.proximo_numero`)
        .run(user.restaurante_id, modo, proximo_numero);
      return true;
    });
    if (!atualizar.immediate()) return reply.code(409).send({ error: 'Finalize todos os pedidos ativos antes de alterar a sequência' });
    return { modo, proximo_numero };
  });

  // 3. Atualizar status do pedido (Cozinha aciona: 'pronto' ou 'entregue')
  fastify.patch('/api/pedidos/:id/status', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    const { id } = request.params;
    const { status } = request.body || {};

    if (!['preparo', 'pronto', 'entregue'].includes(status)) {
      return reply.code(400).send({ error: 'Status inválido' });
    }

    const pedido = db.prepare('SELECT * FROM pedidos WHERE id = ? AND restaurante_id = ?').get(id, user.restaurante_id);
    if (!pedido) {
      return reply.code(400).send({ error: 'Pedido não encontrado' });
    }

    const now = Date.now();
    let updateSql = 'UPDATE pedidos SET status = ? WHERE id = ?';
    let params = [status, id];

    if (status === 'pronto') {
      updateSql = 'UPDATE pedidos SET status = ?, pronto_at = ? WHERE id = ?';
      params = [status, now, id];
    } else if (status === 'entregue') {
      updateSql = 'UPDATE pedidos SET status = ?, entregue_at = ? WHERE id = ?';
      params = [status, now, id];
    }

    if (pedido.status === 'entregue' && status !== 'entregue') return reply.code(409).send({ error: 'Pedido entregue não pode ser reaberto' });
    if (status === 'entregue') {
      updateSql = 'UPDATE pedidos SET status = ?, entregue_at = ?, cliente_nome = NULL, cliente_telefone = NULL WHERE id = ?';
    }
    db.prepare(updateSql).run(...params);
    if (status !== 'preparo') stopPongForOrder(pedido.id);

    const payload = {
      id: pedido.id,
      numero: pedido.numero,
      token: pedido.token,
      status,
      timestamp: now
    };

    // Dispara alerta em tempo real para o celular do cliente
    sseManager.notifyClient(pedido.token, payload);
    if (status === 'pronto' && pedido.status !== 'pronto') {
      void notifyOrderReady(pedido).catch(err => fastify.log.warn({ err }, 'Falha ao enviar Web Push'));
      void notifyGoogleWalletReady(pedido).catch(err => fastify.log.warn({ err }, 'Falha ao atualizar Google Wallet'));
    }
    // Dispara atualização para os painéis KDS
    sseManager.notifyKds(pedido.restaurante_id, 'status_alterado', payload);

    return payload;
  });

  // Rota para obter URL da Carteira do Google para o pedido
  fastify.get('/api/pedidos/:token/wallet/google', async (request, reply) => {
    const { token } = request.params;
    const pedido = db.prepare(`
      SELECT p.*, r.nome as restaurante_nome
      FROM pedidos p
      JOIN restaurantes r ON p.restaurante_id = r.id
      WHERE p.token = ?
    `).get(token);

    if (!pedido) {
      return reply.code(404).send({ error: 'Pedido não encontrado ou expirado' });
    }

    try {
      const url = generateSaveUrl(pedido);
      return { url };
    } catch (err) {
      // Nunca serializar stack, credenciais ou dados do passe ao cliente.
      if (err?.message === 'Chave de serviço da Carteira do Google não configurada.') {
        fastify.log.warn('Google Wallet não configurado nesta instalação');
        return reply.code(503).send({ error: 'Google Wallet indisponível', code: 'WALLET_NOT_CONFIGURED' });
      }
      fastify.log.warn('Não foi possível gerar link da Carteira do Google');
      return reply.code(503).send({ error: 'Google Wallet temporariamente indisponível', code: 'WALLET_UNAVAILABLE' });
    }
  });

  // 4. Stream SSE para o Cliente (Celular do consumidor final)
  fastify.get('/api/pedidos/stream/:token', (request, reply) => {
    const { token } = request.params;

    const pedido = db.prepare(`SELECT p.*, r.nome AS restaurante_nome, r.logo_url AS restaurante_logo_url
      FROM pedidos p JOIN restaurantes r ON r.id = p.restaurante_id WHERE p.token = ?`).get(token);
    if (!pedido) {
      return reply.code(404).send({ error: 'Pedido não encontrado ou expirado' });
    }

    // Configuração dos cabeçalhos HTTP para Server-Sent Events
    reply.hijack();
    reply.raw.setHeader('Content-Type', 'text/event-stream');
    reply.raw.setHeader('Cache-Control', 'no-cache, no-transform');
    reply.raw.setHeader('Connection', 'keep-alive');
    reply.raw.setHeader('Access-Control-Allow-Origin', '*');

    // Envia status atual imediatamente ao conectar
    reply.raw.write(`data: ${JSON.stringify({
      numero: pedido.numero,
      status: pedido.status,
      restaurante_nome: pedido.restaurante_nome,
      restaurante_logo_url: pedido.restaurante_logo_url,
      timestamp: Date.now()
    })}\n\n`);

    // Registra conexão no gerenciador SSE.
    sseManager.addClient(token, reply);
    const clientHeartbeat = setInterval(() => {
      if (reply.raw.destroyed || reply.raw.writableEnded) clearInterval(clientHeartbeat);
      else reply.raw.write(': ping\n\n');
    }, 25000);
    reply.raw.on('close', () => clearInterval(clientHeartbeat));
  });

  // 5. Stream SSE para o KDS (Cozinha)
  fastify.get('/api/kds/stream', (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    reply.hijack();
    reply.raw.setHeader('Content-Type', 'text/event-stream');
    reply.raw.setHeader('Cache-Control', 'no-cache, no-transform');
    reply.raw.setHeader('Connection', 'keep-alive');
    reply.raw.setHeader('Access-Control-Allow-Origin', '*');

    reply.raw.write(`event: conectado\ndata: ${JSON.stringify({ ok: true })}\n\n`);
    const isAuthorized = () => {
      const current = currentUser(request);
      return current?.id === user.id && current.restaurante_id === user.restaurante_id;
    };
    sseManager.addKds(user.restaurante_id, reply, isAuthorized);
    // Sessões encerradas, revogadas ou expiradas não conservam um canal SSE aberto.
    const heartbeat = setInterval(() => {
      if (!isAuthorized()) {
        clearInterval(heartbeat);
        reply.raw.end();
      } else {
        reply.raw.write(': ping\n\n');
      }
    }, 25000);
    reply.raw.on('close', () => clearInterval(heartbeat));
  });
}
