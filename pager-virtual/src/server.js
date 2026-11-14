import Fastify from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import path from 'path';
import { fileURLToPath } from 'url';
import { pedidosRoutes } from './routes/pedidos.js';
import { pushRoutes } from './push.js';
import { authRoutes, currentUser } from './auth.js';
import { adminRoutes } from './admin.js';
import { setupRoutes, needsSetup } from './setup.js';
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
  origin: false
});

// Serve arquivos estáticos da pasta public (Cliente e KDS)
const publicDir = path.join(__dirname, 'public');
fastify.addHook('onRequest', async (request, reply) => {
  const route = request.url.split('?')[0];
  if (route === '/kds.html' || route === '/admin.html') {
    if (needsSetup()) return reply.redirect('/setup.html');
    const user = currentUser(request);
    if (!user) return reply.redirect('/login.html');
    if (route === '/admin.html' && user.papel === 'operador') return reply.redirect('/kds.html');
    if (route === '/kds.html' && user.papel === 'master') return reply.redirect('/admin.html');
  }
});
fastify.get('/', async (request, reply) => {
  if (needsSetup()) return reply.redirect('/setup.html');
  const user = currentUser(request);
  return reply.redirect(user?.papel === 'master' ? '/admin.html' :
    user ? '/kds.html' : '/login.html');
});
await fastify.register(fastifyStatic, {
  root: publicDir,
  prefix: '/'
});

// Registra login e rotas operacionais.
await fastify.register(setupRoutes);
await fastify.register(authRoutes);
await fastify.register(adminRoutes);
await fastify.register(pedidosRoutes);
await fastify.register(pushRoutes);


// Configuração pública do add-on: lida no início do processo após reiniciar.
// O Home Assistant disponibiliza as opções no arquivo /data/options.json.
import fs from 'fs';

function publicUrlConfigurada() {
  let candidate = process.env.PUBLIC_URL || '';
  if (!candidate && fs.existsSync('/data/options.json')) {
    try {
      const options = JSON.parse(fs.readFileSync('/data/options.json', 'utf8'));
      candidate = options.public_url || '';
    } catch (err) {
      fastify.log.warn('Não foi possível ler public_url de /data/options.json');
    }
  }
  if (!candidate) return '';
  try {
    const url = new URL(candidate);
    if (!['https:', 'http:'].includes(url.protocol) || url.username || url.password || url.search || url.hash) throw new Error('URL inválida');
    return url.href.replace(/\/$/, '');
  } catch {
    fastify.log.warn('public_url inválida; os QR Codes usarão o endereço do navegador');
    return '';
  }
}

const PUBLIC_URL = publicUrlConfigurada();
fastify.get('/api/config/publica', async () => ({ public_url: PUBLIC_URL }));

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
