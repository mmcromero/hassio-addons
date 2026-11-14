import Fastify from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import path from 'path';
import { fileURLToPath } from 'url';
import { pedidosRoutes } from './routes/pedidos.js';
import db from './db.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const fastify = Fastify({
  logger: {
    level: process.env.LOG_LEVEL || 'info'
  }
});

// Habilita CORS para permitir conexões flexíveis
await fastify.register(cors, {
  origin: '*'
});

// Serve arquivos estáticos da pasta public (Cliente e KDS)
const publicDir = path.join(__dirname, 'public');
await fastify.register(fastifyStatic, {
  root: publicDir,
  prefix: '/'
});

// Registra rotas de negócio
await fastify.register(pedidosRoutes);

// Rota de Health Check
fastify.get('/api/health', async () => {
  return { status: 'healthy', uptime: process.uptime(), timestamp: Date.now() };
});

const PORT = parseInt(process.env.PORT || '8095', 10);
const HOST = process.env.HOST || '0.0.0.0';

try {
  await fastify.listen({ port: PORT, host: HOST });
  console.log(`[PAGER-VIRTUAL] Servidor rodando com sucesso em http://${HOST}:${PORT}`);
} catch (err) {
  fastify.log.error(err);
  process.exit(1);
}
