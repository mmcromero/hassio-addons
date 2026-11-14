import { nanoid } from 'nanoid';
import { notifyOrderReady } from '../push.js';
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

  // 2. Criar novo pedido (chamado pelo Interceptador de PDV ou pelo KDS)
  fastify.post('/api/pedidos', async (request, reply) => {
    const user = requireRestaurant(request, reply);
    if (!user) return;
    const { numero, itens = [] } = request.body || {};
    const restaurante_id = user.restaurante_id;
    if (!Array.isArray(itens) || itens.length > 20 ||
        !itens.every(i => typeof i === 'string' && i.length <= 120)) {
      return reply.code(400).send({ error: 'Lista de itens inválida' });
    }

    const numeroNormalizado = Number(numero);
    if (!Number.isSafeInteger(numeroNormalizado) || numeroNormalizado <= 0) {
      return reply.code(400).send({ error: 'Informe um número de pedido válido' });
    }
    const restaurante = db.prepare('SELECT id FROM restaurantes WHERE id = ? AND ativo = 1').get(restaurante_id);
    if (!restaurante) {
      return reply.code(400).send({ error: 'Restaurante inválido' });
    }
    const duplicado = db.prepare("SELECT id FROM pedidos WHERE restaurante_id = ? AND numero = ? AND status IN ('preparo', 'pronto')").get(restaurante_id, numeroNormalizado);
    if (duplicado) {
      return reply.code(409).send({ error: 'Já existe um pedido ativo com esse número', pedido_id: duplicado.id });
    }

    const id = nanoid(12);
    const token = nanoid(21); // Token seguro da página casca do cliente
    const now = Date.now();

    const insert = db.prepare(`
      INSERT INTO pedidos (id, restaurante_id, numero, token, itens_json, status, created_at)
      VALUES (?, ?, ?, ?, ?, 'preparo', ?)
    `);

    insert.run(id, restaurante_id, numeroNormalizado, token, JSON.stringify(itens), now);

    const novoPedido = {
      id,
      restaurante_id,
      numero: numeroNormalizado,
      token,
      itens,
      status: 'preparo',
      created_at: now
    };

    // Notifica telas KDS conectadas
    sseManager.notifyKds(restaurante_id, 'novo_pedido', novoPedido);

    return reply.code(201).send(novoPedido);
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

    db.prepare(updateSql).run(...params);

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
    }
    // Dispara atualização para os painéis KDS
    sseManager.notifyKds(pedido.restaurante_id, 'status_alterado', payload);

    return payload;
  });

  // 4. Stream SSE para o Cliente (Celular do consumidor final)
  fastify.get('/api/pedidos/stream/:token', (request, reply) => {
    const { token } = request.params;

    const pedido = db.prepare('SELECT * FROM pedidos WHERE token = ?').get(token);
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
