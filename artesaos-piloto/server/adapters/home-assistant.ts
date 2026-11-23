import type { FastifyInstance } from 'fastify';

// Authentication belongs to HA. Never trust a client-supplied forwarded address.
export function registerHomeAssistantAccess(app: FastifyInstance) {
  app.addHook('onRequest', async (request, reply) => {
    const address = request.raw.socket.remoteAddress?.replace(/^::ffff:/, '');
    if (address !== '172.30.32.2') {
      return reply.code(403).send({ error: 'Acesso permitido somente pelo Ingress.' });
    }
  });
}
