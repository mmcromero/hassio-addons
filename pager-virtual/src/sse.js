/**
 * Gerenciador de conexões em tempo real via Server-Sent Events (SSE)
 * Extremamente leve em memória (< alguns KB por conexão) e perfeito para o Raspberry Pi.
 */
class SSEManager {
  constructor() {
    // Mapa: token -> Set de conexões de clientes
    this.clientStreams = new Map();
    // Set de conexões do painel KDS/Cozinha
    this.kdsStreams = new Set();
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
  addKds(reply) {
    this.kdsStreams.add(reply);
    reply.raw.on('close', () => {
      this.kdsStreams.delete(reply);
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
  notifyKds(event, data) {
    if (this.kdsStreams.size > 0) {
      const payload = `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;
      for (const reply of this.kdsStreams) {
        reply.raw.write(payload);
      }
    }
  }
}

export const sseManager = new SSEManager();
