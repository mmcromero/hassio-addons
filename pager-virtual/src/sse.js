/**
 * Gerenciador de conexões em tempo real via Server-Sent Events (SSE)
 * Extremamente leve em memória (< alguns KB por conexão) e perfeito para o Raspberry Pi.
 */
class SSEManager {
  constructor() {
    // Mapa: token -> Set de conexões de clientes
    this.clientStreams = new Map();
    // restaurante_id -> Set de conexões autorizadas do KDS
    this.kdsStreams = new Map();
  }

  // Registra um cliente ouvindo o status de seu pedido
  addClient(token, reply) {
    if (!this.clientStreams.has(token)) {
      this.clientStreams.set(token, new Set());
    }
    const streams = this.clientStreams.get(token);
    streams.add(reply);

    reply.raw.on('close', () => {
      streams.delete(reply);
      if (streams.size === 0) {
        this.clientStreams.delete(token);
      }
    });
  }

  // Registra um terminal de cozinha/KDS ouvindo atualizações
  addKds(restauranteId, reply, isAuthorized = () => true) {
    if (!this.kdsStreams.has(restauranteId)) this.kdsStreams.set(restauranteId, new Set());
    const streams = this.kdsStreams.get(restauranteId);
    const entry = { reply, isAuthorized };
    streams.add(entry);
    reply.raw.on('close', () => {
      streams.delete(entry);
      if (streams.size === 0) this.kdsStreams.delete(restauranteId);
    });
  }

  // Notifica o cliente específico com a mudança de status
  notifyClient(token, data) {
    const streams = this.clientStreams.get(token);
    if (streams && streams.size > 0) {
      const payload = `data: ${JSON.stringify(data)}\n\n`;
      for (const reply of streams) {
        reply.raw.write(payload);
      }
    }
  }

  // Notifica as telas da cozinha sobre novos pedidos ou alterações
  notifyKds(restauranteId, event, data) {
    const streams = this.kdsStreams.get(restauranteId);
    if (!streams?.size) return;
    const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
    for (const entry of streams) {
      const { reply, isAuthorized } = entry;
      if (reply.raw.destroyed || reply.raw.writableEnded) continue;
      // Revalidar antes de cada evento impede que um terminal revogado receba
      // dados durante a janela entre a revogação e o próximo heartbeat.
      if (!isAuthorized()) {
        reply.raw.end();
        continue;
      }
      reply.raw.write(payload);
    }
  }
}

export const sseManager = new SSEManager();
