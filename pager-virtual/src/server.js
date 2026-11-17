import './bootstrap-config.js';
import Fastify from 'fastify';
import cors from '@fastify/cors';
import fastifyStatic from '@fastify/static';
import path from 'path';
import { fileURLToPath } from 'url';
import { pedidosRoutes } from './routes/pedidos.js';
import { pongRoutes } from './pong.js';
import { integracaoImpressaoRoutes } from './routes/integracao-impressao.js';
import { pushRoutes } from './push.js';
import { authRoutes, currentUser } from './auth.js';
import { adminRoutes } from './admin.js';
import { interessesRoutes } from './interesses.js';
import { setupRoutes, needsSetup } from './setup.js';
import db from './db.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const fastify = Fastify({
  logger: {
    level: process.env.LOG_LEVEL || 'info'
  }
});

// Proteções comuns a páginas e APIs servidas pelo Fastify.
// CSP de páginas específicas permanece por rota: jogos isolados usam iframe,
// e HTTPS/HSTS depende do proxy público, pois há acesso HTTP local.
// Não há I/O neste hook. Finalizar sincronicamente preserva reply.sent nos
// adaptadores que já enviaram 401/403 e impede uma segunda resposta de ACL.
fastify.addHook('onSend', (_request, reply, payload, done) => {
  if (!reply.hasHeader('X-Content-Type-Options'))
    reply.header('X-Content-Type-Options', 'nosniff');
  if (!reply.hasHeader('Referrer-Policy'))
    reply.header('Referrer-Policy', 'no-referrer');
  // Nunca aplicar DENY globalmente: os jogos locais usam iframe sandbox.
  // Proteger somente as interfaces administrativas e de autenticação.
  const route = _request.url.split('?')[0];
  if (['/login.html', '/setup.html', '/admin.html', '/kds.html', '/impressao.html'].includes(route)) {
    reply.header('Cache-Control', 'no-store, no-cache, must-revalidate, private');
    reply.header('Pragma', 'no-cache');
    if (!reply.hasHeader('X-Frame-Options'))
      reply.header('X-Frame-Options', 'DENY');
    if (!reply.hasHeader('Content-Security-Policy'))
      reply.header('Content-Security-Policy', "frame-ancestors 'none'");
  }
  done(null, payload);
});

// Habilita CORS para permitir conexões flexíveis
await fastify.register(cors, {
  origin: false
});

// Serve arquivos estáticos da pasta public (Cliente e KDS)
const publicDir = path.join(__dirname, 'public');
// Prefixo informado exclusivamente pelo proxy NGINX na rota HTTPS configurada.
const requestBasePath = request => request.headers['x-forwarded-prefix'] === '/avisaqui' ? '/avisaqui' : '';
const pageUrl = (request, page) => requestBasePath(request) + page;
fastify.addHook('onRequest', async (request, reply) => {
  const route = request.url.split('?')[0];
  if (route === '/kds.html' || route === '/admin.html' || route === '/impressao.html') {
    if (needsSetup()) return reply.redirect(pageUrl(request, '/setup.html'));
    const user = currentUser(request);
    if (!user) return reply.redirect(pageUrl(request, '/login.html'));
    if ((route === '/admin.html' || route === '/impressao.html') && user.papel === 'operador') return reply.redirect(pageUrl(request, '/kds.html'));
    if (route === '/kds.html' && user.papel === 'master' && !user.restaurante_id) return reply.redirect(pageUrl(request, '/admin.html'));
  }
});
fastify.get('/', async (request, reply) => {
  if (needsSetup()) return reply.redirect(pageUrl(request, '/setup.html'));
  const user = currentUser(request);
  return reply.redirect(pageUrl(request, user?.papel === 'master' ? '/admin.html' :
    user ? '/kds.html' : '/landing.html'));
});
await fastify.register(fastifyStatic, {
  root: publicDir,
  prefix: '/'
});

// Registra login e rotas operacionais.
await fastify.register(setupRoutes);
await fastify.register(authRoutes);
await fastify.register(adminRoutes);
await fastify.register(interessesRoutes);
await fastify.register(pedidosRoutes);
await fastify.register(pongRoutes);
await fastify.register(integracaoImpressaoRoutes);
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

// PAIR-V1 RC003: somente opt-in explícito. O modo padrão não importa o plugin,
// não executa a migração de pareamento e preserva o fluxo manual existente.
// NÃO habilitar em host comercial antes dos portões Segurança/Privacidade.
if (process.env.AVISAQUI_PAIR_V1_ENABLED === 'true') {
  const publicOrigin = process.env.AVISAQUI_PAIR_V1_PUBLIC_ORIGIN;
  const mountPrefix = process.env.AVISAQUI_PAIR_V1_MOUNT_PREFIX;
  const fields = ['APPROVAL_MS', 'CHALLENGE_MS', 'RECOVERY_MS'];
  const durations = fields.map(key => {
    const raw = process.env['AVISAQUI_PAIR_V1_' + key];
    if (!raw || !/^[1-9][0-9]*$/.test(raw)) {
      throw new Error('Política temporal do pair-v1 incompleta: ' + key);
    }
    const value = Number(raw);
    if (!Number.isSafeInteger(value) || value <= 1000 || value > 7 * 86400000) {
      throw new Error('Política temporal do pair-v1 inválida: ' + key);
    }
    return value;
  });
  if (!publicOrigin || !PUBLIC_URL || publicOrigin.replace(/\/$/, '') !== PUBLIC_URL ||
      !['', '/avisaqui'].includes(mountPrefix)) {
    throw new Error('Pair-v1 requer origem HTTPS pública e prefixo interno explícitos e compatíveis');
  }
  // O validador interno exige HTTPS e pathname /avisaqui.
  const { registerPairV1IntegratedLab } = await import('./pairing/backend/integrated-host-lab.js');
  await registerPairV1IntegratedLab(fastify, {
    db, publicOrigin, mountPrefix,
    policy: { approvalMs: durations[0], challengeMs: durations[1], recoveryMs: durations[2] }
  });
}
fastify.get('/api/config/publica', async () => ({
  public_url: PUBLIC_URL,
  pair_v1_enabled: process.env.AVISAQUI_PAIR_V1_ENABLED === 'true'
}));

// O Supervisor exige [HOST]/[PORT] no manifesto. O botão passa por esta rota
// e chega à landing HTTPS definida em public_url, sem fixar domínio no pacote.
// Sem URL pública, preservar a landing local e eventual prefixo do proxy.
fastify.get('/webui', async (request, reply) => {
  reply.header('Cache-Control', 'no-store');
  return reply.redirect(PUBLIC_URL ? `${PUBLIC_URL}/landing.html` : pageUrl(request, '/landing.html'));
});

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
