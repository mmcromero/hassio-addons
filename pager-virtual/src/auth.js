import { randomBytes, randomUUID, createHash, scrypt as scryptCallback, timingSafeEqual } from 'node:crypto';
import { promisify } from 'node:util';
import fs from 'node:fs';
import db from './db.js';

const scrypt = promisify(scryptCallback);
const SESSION_MS = 12 * 60 * 60 * 1000;
const COOKIE = 'bipou_session';
const MAX_LOGIN_LENGTH = 120;
const MAX_PASSWORD_LENGTH = 256;
const attempts = new Map();
const LIMIT = 6;
const WINDOW_MS = 15 * 60 * 1000;

export async function passwordHash(password) {
  if (typeof password !== 'string' || password.length < 12 || password.length > MAX_PASSWORD_LENGTH) {
    throw new Error('Senha deve ter entre 12 e 256 caracteres');
  }
  const salt = randomBytes(16);
  const value = await scrypt(password, salt, 64);
  return 'scrypt:' + salt.toString('hex') + ':' + value.toString('hex');
}

export async function passwordMatches(password, encoded) {
  if (typeof password !== 'string' || password.length > MAX_PASSWORD_LENGTH || typeof encoded !== 'string') return false;
  const parts = encoded.split(':');
  if (parts.length !== 3 || parts[0] !== 'scrypt' || !/^[a-f0-9]{32}$/.test(parts[1]) || !/^[a-f0-9]{128}$/.test(parts[2])) return false;
  const expected = Buffer.from(parts[2], 'hex');
  const actual = await scrypt(password, Buffer.from(parts[1], 'hex'), expected.length);
  return timingSafeEqual(actual, expected);
}

const hashToken = token => createHash('sha256').update(token).digest('hex');
const parseCookie = header => {
  const match = (header || '').split(';').map(v => v.trim()).find(v => v.startsWith(COOKIE + '='));
  return match ? match.slice(COOKIE.length + 1) : '';
};
const getSession = token => {
  if (!/^[a-f0-9]{64}$/.test(token)) return null;
  return db.prepare(`
    SELECT u.id, u.login, u.nome, u.papel, u.restaurante_id
    FROM sessoes s
    JOIN usuarios u ON u.id = s.usuario_id
    LEFT JOIN restaurantes r ON r.id = u.restaurante_id
    WHERE s.token_hash = ? AND s.revogado_em IS NULL AND s.expira_em > ?
      AND u.ativo = 1 AND (u.papel = 'master' OR r.ativo = 1)
  `).get(hashToken(token), Date.now()) || null;
};

function configuredOrigin() {
  try {
    let value = process.env.PUBLIC_URL || '';
    if (!value && fs.existsSync('/data/options.json')) {
      value = JSON.parse(fs.readFileSync('/data/options.json', 'utf8')).public_url || '';
    }
    return value ? new URL(value).origin : '';
  } catch { return ''; }
}
const publicOrigin = configuredOrigin();
function secureRequest(request) {
  // Se o endereço público é HTTPS, a sessão deve exigir HTTPS no navegador.
  // Não se deve confiar automaticamente no cabeçalho X-Forwarded-Proto.
  // Acesso HTTP local precisa de cookie sem Secure; HTTPS público recebe Secure.
  // Nunca definir Secure apenas pela configuração global, pois impediria login local.
  return request.protocol === 'https' ||
    (publicOrigin.startsWith('https://') && request.headers.origin === publicOrigin);
}
function sessionCookie(token, request) {
  return `${COOKIE}=${token}; Path=/; HttpOnly; SameSite=Strict; Max-Age=${Math.floor(SESSION_MS / 1000)}${secureRequest(request) ? '; Secure' : ''}`;
}
function clearCookie(request) {
  return `${COOKIE}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0${secureRequest(request) ? '; Secure' : ''}`;
}
const loginKey = request => request.ip + '|' + String(request.body?.login || '').toLowerCase();
function recordFailedAttempt(key) {
  const now = Date.now();
  const entry = attempts.get(key);
  const next = (!entry || entry.until < now) ? { count: 1, until: now + WINDOW_MS } : { count: entry.count + 1, until: entry.until };
  attempts.set(key, next);
  if (attempts.size > 10000) attempts.clear();
}
function tooMany(key) {
  const a = attempts.get(key);
  if (!a) return false;
  if (a.until < Date.now()) { attempts.delete(key); return false; }
  return a.count >= LIMIT;
}
function validateOrigin(request) {
  const origin = request.headers.origin;
  if (!origin) return false;
  try {
    const url = new URL(origin);
    const host = request.headers.host;
    return origin === publicOrigin || (url.host === host && url.protocol === (request.protocol + ':'));
  } catch { return false; }
}
export async function authRoutes(app) {
  app.post('/api/auth/login', async (request, reply) => {
    if (!validateOrigin(request)) return reply.code(403).send({ error: 'Origem não autorizada' });
    const { login, senha } = request.body || {};
    if (typeof login !== 'string' || login.length < 1 || login.length > MAX_LOGIN_LENGTH ||
        typeof senha !== 'string' || senha.length > MAX_PASSWORD_LENGTH) {
      return reply.code(400).send({ error: 'Credenciais inválidas' });
    }
    const key = loginKey(request);
    if (tooMany(key)) return reply.code(429).send({ error: 'Muitas tentativas. Tente mais tarde.' });
    const usuario = db.prepare(`
      SELECT u.*, r.ativo AS restaurante_ativo FROM usuarios u
      LEFT JOIN restaurantes r ON r.id = u.restaurante_id
      WHERE u.login = ?
    `).get(login.trim().toLowerCase());
    const ok = usuario?.ativo === 1 && (usuario.papel === 'master' || usuario.restaurante_ativo === 1)
      && await passwordMatches(senha, usuario.senha_hash);
    if (!ok) {
      recordFailedAttempt(key);
      return reply.code(401).send({ error: 'Login ou senha inválidos' });
    }
    attempts.delete(key);
    const token = randomBytes(32).toString('hex');
    const now = Date.now();
    db.prepare('INSERT INTO sessoes (id, usuario_id, token_hash, criado_em, expira_em) VALUES (?, ?, ?, ?, ?)')
      .run(randomUUID(), usuario.id, hashToken(token), now, now + SESSION_MS);
    reply.header('Set-Cookie', sessionCookie(token, request));
    return { login: usuario.login, nome: usuario.nome, papel: usuario.papel, restaurante_id: usuario.restaurante_id };
  });

  app.get('/api/auth/me', async (request, reply) => {
    const user = getSession(parseCookie(request.headers.cookie));
    if (!user) return reply.code(401).send({ error: 'Não autenticado' });
    return user;
  });

  // Troca da própria senha: exige senha atual e revoga as demais sessões.
  app.post('/api/auth/password', async (request, reply) => {
    const user = requireUser(request, reply);
    if (!user) return;
    const { senha_atual, nova_senha } = request.body || {};
    if (typeof senha_atual !== 'string' || typeof nova_senha !== 'string') {
      return reply.code(400).send({ error: 'Informe a senha atual e a nova senha' });
    }
    const account = db.prepare('SELECT senha_hash FROM usuarios WHERE id = ?').get(user.id);
    if (!account || !(await passwordMatches(senha_atual, account.senha_hash))) {
      return reply.code(403).send({ error: 'Senha atual incorreta' });
    }
    let newHash;
    try { newHash = await passwordHash(nova_senha); }
    catch { return reply.code(400).send({ error: 'Nova senha deve ter entre 12 e 256 caracteres' }); }
    if (await passwordMatches(nova_senha, account.senha_hash)) {
      return reply.code(400).send({ error: 'A nova senha deve ser diferente da atual' });
    }
    db.transaction(() => {
      db.prepare('UPDATE usuarios SET senha_hash = ?, atualizado_em = ? WHERE id = ?')
        .run(newHash, Date.now(), user.id);
      db.prepare('UPDATE sessoes SET revogado_em = ? WHERE usuario_id = ? AND revogado_em IS NULL')
        .run(Date.now(), user.id);
    })();
    reply.header('Set-Cookie', clearCookie(request));
    return { ok: true, login_novamente: true };
  });

  app.post('/api/auth/logout', async (request, reply) => {
    if (!validateOrigin(request)) return reply.code(403).send({ error: 'Origem não autorizada' });
    const token = parseCookie(request.headers.cookie);
    if (/^[a-f0-9]{64}$/.test(token)) {
      db.prepare('UPDATE sessoes SET revogado_em = ? WHERE token_hash = ? AND revogado_em IS NULL')
        .run(Date.now(), hashToken(token));
    }
    reply.header('Set-Cookie', clearCookie(request));
    return { ok: true };
  });
}

export function currentUser(request) {
  return getSession(parseCookie(request.headers.cookie));
}

export function requireUser(request, reply) {
  const user = currentUser(request);
  if (!user) { reply.code(401).send({ error: 'Sessão inválida ou expirada' }); return null; }
  if (!['GET', 'HEAD', 'OPTIONS'].includes(request.method) && !validateOrigin(request)) {
    reply.code(403).send({ error: 'Origem não autorizada' }); return null;
  }
  return user;
}

export function requireRestaurant(request, reply) {
  const user = requireUser(request, reply);
  if (!user) return null;
  if (!user.restaurante_id || user.papel === 'master') {
    reply.code(403).send({ error: 'Selecione um restaurante autorizado' });
    return null;
  }
  return user;
}
