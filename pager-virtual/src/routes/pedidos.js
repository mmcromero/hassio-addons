import { nanoid } from 'nanoid';
import db from '../db.js';
import { sseManager } from '../sse.js';

export async function pedidosRoutes(fastify, options) {
  // 1. Listar pedidos ativos para o KDS (Cozinha/Balcão)
  fastify.get('/api/pedidos', async (request, reply) => {
    const pedidos = db.prepare(`
      SELECT p.*, r.nome as restaurante_nome
      FROM pedidos p
      JOIN restaurantes r ON p.restaurante_id = r.id
      WHERE p.status IN ('preparo', 'pronto')
      ORDER BY p.created_at ASC
    `).all();

    return pedidos.map(p => ({
      ...p,
      itens: p.itens_json ? JSON.parse(p.itens_json) : []
    }));
  });

  // 2. Criar novo pedido (chamado pelo Interceptador de PDV ou pelo KDS)
  fastify.post('/api/pedidos', async (request, reply) => {
    const { restaurante_id = 'rest_demo_01', numero, itens = [] } = request.body || {};

    if (!numero) {
      return reply.code(400).send({ error: 'Número do pedido é obrigatório' });
    }

    const id = nanoid(12);
    const token = nanoid(21); // Token seguro da página casca do cliente
    const now = Date.now();

    const insert = db.prepare(`
      INSERT INTO pedidos (id, restaurante_id, numero, token, itens_json, status, created_at)
      VALUES (?, ?, ?, ?, ?, 'preparo', ?)
    `);

    insert.run(id, restaurante_id, numero, token, JSON.stringify(itens), now);

    const novoPedido = {
      id,
      restaurante_id,
      numero,
      token,
      itens,
      status: 'preparo',
      created_at: now
    };

    // Notifica telas KDS conectadas
    sseManager.notifyKds('novo_pedido', novoPedido);

    return reply.code(201).send(novoPedido);
  });

  // 3. Atualizar status do pedido (Cozinha aciona: 'pronto' ou 'entregue')
  fastify.patch('/api/pedidos/:id/status', async (request, reply) => {
    const { id } = request.params;
    const { status } = request.body || {};

    if (!['preparo', 'pronto', 'entregue'].includes(status)) {
      return reply.code(400).send({ error: 'Status inválido' });
    }

    const pedido = db.prepare('SELECT * FROM pedidos WHERE id = ?').get(id);
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
    // Dispara atualização para os painéis KDS
    sseManager.notifyKds('status_alterado', payload);

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

    // Registra conexão no gerenciador SSE
    sseManager.addClient(token, reply);
  });

  // 5. Stream SSE para o KDS (Cozinha)
  fastify.get('/api/kds/stream', (request, reply) => {
    reply.raw.setHeader('Content-Type', 'text/event-stream');
    reply.raw.setHeader('Cache-Control', 'no-cache, no-transform');
    reply.raw.setHeader('Connection', 'keep-alive');
    reply.raw.setHeader('Access-Control-Allow-Origin', '*');

    reply.raw.write(`event: conectado\ndata: ${JSON.stringify({ ok: true })}\n\n`);
    sseManager.addKds(reply);
  });
}
