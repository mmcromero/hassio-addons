// RC003: valida o servidor real, nao apenas o host isolado de laboratorio.
// Cria SQLite descartavel e nao acessa /data, HA, Raspberry ou rede publica.
import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { createServer } from 'node:net';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';
import { createHash, randomBytes, randomUUID } from 'node:crypto';

const ROOT = resolve(fileURLToPath(new URL('..', import.meta.url)));
const sleep = ms => new Promise(r => setTimeout(r, ms));
async function freePort() {
  return new Promise((resolvePort, reject) => {
    const server = createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolvePort(port));
    });
  });
}
async function launch(env) {
  const proc = spawn(process.execPath, ['src/server.js'], {
    cwd: ROOT, env: { ...process.env, ...env }, stdio: ['ignore', 'pipe', 'pipe']
  });
  let error = '';
  proc.stderr.on('data', d => { error = (error + d.toString()).slice(-2000); });
  proc.stdout.on('data', () => {});
  return { proc, get error() { return error; } };
}
async function close(proc) {
  if (proc.exitCode !== null) return;
  proc.kill('SIGTERM');
  await Promise.race([
    new Promise(resolve => proc.once('close', resolve)),
    sleep(3000).then(() => { if (proc.exitCode === null) proc.kill('SIGKILL'); })
  ]);
}
async function ready(port, child) {
  for (let i = 0; i < 100; i++) {
    if (child.proc.exitCode !== null)
      throw Error('Servidor encerrou antes do health: ' + child.error);
    try {
      const response = await fetch('http://127.0.0.1:' + port + '/api/health');
      if (response.ok) return;
    } catch {}
    await sleep(100);
  }
  throw Error('Servidor nao iniciou no prazo: ' + child.error);
}
test('servidor comercial mantém pair-v1 desabilitado por padrão', { timeout: 30000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'avisaqui-host-off-'));
  let child;
  try {
    const port = await freePort();
    child = await launch({
      DATA_PATH: dir, PORT: String(port), HOST: '127.0.0.1',
      AVISAQUI_PAIR_V1_ENABLED: 'false',
      AVISAQUI_PAIR_V1_PUBLIC_ORIGIN: '',
      AVISAQUI_PAIR_V1_MOUNT_PREFIX: ''
    });
    await ready(port, child);
    const base = 'http://127.0.0.1:' + port;
    const health = await fetch(base + '/api/health');
    assert.equal(health.status, 200);
    assert.equal(health.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(health.headers.get('referrer-policy'), 'no-referrer');
    assert.equal(health.headers.get('strict-transport-security'), null,
      'HSTS exige avaliação no proxy HTTPS, não no HTTP local');
    const login = await fetch(base + '/login.html');
    assert.equal(login.status, 200);
    assert.equal(login.headers.get('x-frame-options'), 'DENY');
    assert.equal(login.headers.get('content-security-policy'), "frame-ancestors 'none'");
    const game = await fetch(base + '/games/jogo-da-velha-isolado.html');
    assert.equal(game.status, 200);
    assert.equal(game.headers.get('x-frame-options'), null,
      'nao bloquear iframe sandbox do jogo');
    assert.ok(!/frame-ancestors 'none'/.test(game.headers.get('content-security-policy') || ''),
      'o CSP do jogo nao pode receber restricao global contra iframe');
    assert.equal((await fetch(base + '/autorizar')).status, 404);
    assert.equal((await fetch(base + '/api/agentes/dispositivos')).status, 404);
    const db = new Database(join(dir, 'pager_virtual.db'), { readonly: true });
    try {
      const table = db.prepare("SELECT name FROM sqlite_master WHERE name='integracao_pareamento_solicitacoes'").get();
      assert.equal(table, undefined, 'modo desligado nao altera esquema pair-v1');
    } finally { db.close(); }
  } finally {
    if (child) await close(child.proc);
    rmSync(dir, { recursive: true, force: true });
  }
});
test('servidor opt-in em banco sintético monta rotas e exige gerente', { timeout: 30000 }, async () => {
  const dir = mkdtempSync(join(tmpdir(), 'avisaqui-host-on-'));
  let child;
  try {
    const port = await freePort();
    const origin = 'https://pager.test/avisaqui';
    child = await launch({
      DATA_PATH: dir, PORT: String(port), HOST: '127.0.0.1',
      PUBLIC_URL: origin,
      AVISAQUI_PAIR_V1_ENABLED: 'true',
      AVISAQUI_PAIR_V1_PUBLIC_ORIGIN: origin,
      AVISAQUI_PAIR_V1_MOUNT_PREFIX: '',
      AVISAQUI_PAIR_V1_APPROVAL_MS: '300000',
      AVISAQUI_PAIR_V1_CHALLENGE_MS: '60000',
      AVISAQUI_PAIR_V1_RECOVERY_MS: '3600000'
    });
    await ready(port, child);
    const base = 'http://127.0.0.1:' + port;
    assert.equal((await fetch(base + '/autorizar?solicitacao=00000000-0000-4000-8000-000000000000')).status, 401);
    const denied = await fetch(base + '/api/agentes/dispositivos');
    assert.equal(denied.status, 401);
    assert.deepEqual(await denied.json(), { error: 'Sessão inválida ou expirada' },
      'headers não podem substituir a resposta original da autenticação');
    assert.equal(denied.headers.get('x-content-type-options'), 'nosniff');
    assert.equal(denied.headers.get('referrer-policy'), 'no-referrer');
    assert.equal((await fetch(base + '/avisaqui/autorizar')).status, 404,
      'prefixo externo nao deve ser duplicado no backend');
    const db = new Database(join(dir, 'pager_virtual.db'), { readonly: true });
    try {
      assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE name='integracao_pareamento_solicitacoes'").get());
      assert.ok(db.prepare('PRAGMA table_info(integracao_impressao_chaves)').all().some(c => c.name === 'dispositivo_id'));
    } finally { db.close(); }
    const seed = new Database(join(dir, 'pager_virtual.db'));
    const tokens = {};
    try {
      const now = Date.now();
      seed.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)')
        .run('rest-header-test', 'Sintético', 'rest-header-test', now);
      for (const role of ['gerente', 'operador']) {
        const token = randomBytes(32).toString('hex'); tokens[role] = token;
        seed.prepare(`INSERT INTO usuarios
          (id,restaurante_id,nome,login,senha_hash,papel,ativo,criado_em,atualizado_em)
          VALUES(?,?,?,?,?,?,1,?,?)`).run(role, 'rest-header-test', role, role,
            'synthetic-not-authenticatable', role, now, now);
        seed.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
          .run(randomUUID(), role, createHash('sha256').update(token).digest('hex'), now, now + 60000);
      }
    } finally { seed.close(); }
    const target = '/autorizar?solicitacao=' + randomUUID();
    const browser = await fetch(base + target, { headers: { Accept: 'text/html' }, redirect: 'manual' });
    assert.equal(browser.status, 303);
    assert.equal(new URL(browser.headers.get('location'), base).searchParams.get('return_to'),
      '/avisaqui' + target);
    for (const path of [target, '/api/agentes/dispositivos']) {
      const operator = await fetch(base + path, { headers: { Cookie: 'bipou_session=' + tokens.operador } });
      assert.equal(operator.status, 403, 'sessão de operador não vira gerente');
      assert.equal(operator.headers.get('x-content-type-options'), 'nosniff');
      const manager = await fetch(base + path, { headers: { Cookie: 'bipou_session=' + tokens.gerente } });
      assert.equal(manager.status, 200);
      assert.equal(manager.headers.get('referrer-policy'), 'no-referrer');
      if (path === target) {
        assert.match(manager.headers.get('content-security-policy'), /script-src 'sha256-/);
        assert.equal(manager.headers.get('x-frame-options'), 'DENY');
        assert.equal(manager.headers.get('cache-control'), 'no-store');
      } else assert.deepEqual(await manager.json(), []);
    }
  } finally {
    if (child) await close(child.proc);
    rmSync(dir, { recursive: true, force: true });
  }
});
