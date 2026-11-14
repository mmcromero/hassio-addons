import { randomBytes, randomUUID, timingSafeEqual } from 'node:crypto';
import db from './db.js';
import { passwordHash } from './auth.js';

const expiresAt = Date.now() + 30 * 60 * 1000;
let setupCode = randomBytes(24).toString('hex');
let failures = 0;

export function needsSetup() {
  return db.prepare("SELECT COUNT(*) AS total FROM usuarios WHERE papel = 'master'").get().total === 0;
}
export async function setupRoutes(app) {
  if (needsSetup()) {
    // O código só aparece no log privado do add-on e nunca na API nem no código-fonte.
    app.log.warn('BIPOU PRIMEIRO ACESSO: código temporário para configurar Master Admin (válido por 30 min): ' + setupCode);
  }

  app.get('/api/setup/status', async () => ({ needs_setup: needsSetup() }));

  app.post('/api/setup/master', async (request, reply) => {
    if (!needsSetup()) return reply.code(409).send({ error: 'Master Admin já configurado' });
    const host = request.headers.host;
    const origin = request.headers.origin;
    let sameOrigin = false;
    try {
      const url = new URL(origin);
      sameOrigin = url.host === host && url.protocol === request.protocol + ':';
    } catch {}
    // Primeiro acesso somente pela rede privada/local, com código temporário.
    const ip = request.ip.replace(/^::ffff:/, '');
    const localIp = ip === '::1' || ip === '127.0.0.1' || /^10\./.test(ip) ||
      /^192\.168\./.test(ip) || /^172\.(1[6-9]|2[0-9]|3[01])\./.test(ip);
    // Um proxy público pode apresentar IP interno ao servidor.
    // A origem do cadastro deve apontar para endereço literal de loopback ou LAN.
    // Não autorizar hostname público só porque a conexão veio do proxy.
    let localHost = false;
    try {
      const hostname = new URL(origin).hostname.replace(/^\[|\]$/g, '');
      localHost = hostname === 'localhost' || hostname === '127.0.0.1' || hostname === '::1' ||
        /^10\./.test(hostname) || /^192\.168\./.test(hostname) ||
        /^172\.(1[6-9]|2[0-9]|3[01])\./.test(hostname);
    } catch {}
    if (!sameOrigin || !localIp || !localHost) {
      return reply.code(403).send({ error: 'Primeiro acesso disponível apenas na rede local' });
    }
    if (Date.now() > expiresAt || failures >= 6) {
      return reply.code(429).send({ error: 'Código expirado ou bloqueado. Reinicie o add-on para gerar outro código.' });
    }
    const { codigo, nome, login, senha } = request.body || {};
    const input = typeof codigo === 'string' && /^[a-f0-9]{48}$/.test(codigo) ? Buffer.from(codigo, 'hex') : null;
    const expected = Buffer.from(setupCode, 'hex');
    if (!input || !timingSafeEqual(input, expected)) {
      failures++;
      return reply.code(403).send({ error: 'Código inválido' });
    }
    if (typeof nome !== 'string' || nome.trim().length < 2 || nome.trim().length > 120 ||
        typeof login !== 'string' || !/^[a-z0-9._@-]{3,120}$/.test(login.trim().toLowerCase())) {
      return reply.code(400).send({ error: 'Informe nome e login válidos' });
    }
    let hash;
    try { hash = await passwordHash(senha); }
    catch { return reply.code(400).send({ error: 'Senha deve ter entre 12 e 256 caracteres' }); }

    const register = db.transaction(() => {
      if (!needsSetup()) return false;
      const now = Date.now();
      db.prepare(`INSERT INTO usuarios
        (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
        VALUES (?, NULL, ?, ?, ?, 'master', ?, ?)`)
        .run(randomUUID(), nome.trim(), login.trim().toLowerCase(), hash, now, now);
      return true;
    });
    try {
      if (!register.immediate()) return reply.code(409).send({ error: 'Master Admin já configurado' });
    } catch (e) {
      if (e.code?.startsWith('SQLITE_CONSTRAINT')) return reply.code(409).send({ error: 'Login já existente' });
      throw e;
    }
    setupCode = '';
    return reply.code(201).send({ ok: true });
  });
}
