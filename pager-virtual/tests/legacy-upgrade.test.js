import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import Database from 'better-sqlite3';

const historicSchema = `
  CREATE TABLE restaurantes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    ativo INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
  );
  CREATE TABLE pedidos (
    id TEXT PRIMARY KEY,
    restaurante_id TEXT NOT NULL,
    numero INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    itens_json TEXT,
    status TEXT NOT NULL DEFAULT 'preparo',
    created_at INTEGER NOT NULL,
    pronto_at INTEGER,
    entregue_at INTEGER,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id)
  );
  CREATE INDEX idx_pedidos_token ON pedidos(token);
  CREATE INDEX idx_pedidos_rest_status ON pedidos(restaurante_id, status);
`;

function executeNode(code, env) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['--input-type=module', '-e', code], {
      env, stdio: ['ignore', 'pipe', 'pipe']
    });
    let stderr = '';
    child.stderr.on('data', c => { stderr += c.toString(); });
    child.on('error', reject);
    child.on('exit', status => status === 0 ? resolve() : reject(new Error(stderr || 'Exit ' + status)));
  });
}

test('atualizar banco 0.1.3 preserva pedidos, restaurante, tokens e status', { timeout: 15000 }, async () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'bipou-legacy-upgrade-'));
  let database;
  try {
    const file = path.join(dir, 'pager_virtual.db');
    database = new Database(file);
    database.pragma('foreign_keys = ON');
    database.exec(historicSchema);
    const now = Date.now();
    database.prepare('INSERT INTO restaurantes (id, nome, slug, ativo, created_at) VALUES (?, ?, ?, 1, ?)')
      .run('rest_demo_01', 'Burger House Demo', 'demo', now);
    const insert = database.prepare(`INSERT INTO pedidos
      (id, restaurante_id, numero, token, itens_json, status, created_at, pronto_at, entregue_at)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)`);
    insert.run('legado-1', 'rest_demo_01', 41, 'token-persistido-41', '[]', 'preparo', now, null, null);
    insert.run('legado-2', 'rest_demo_01', 42, 'token-persistido-42', '[]', 'pronto', now, now + 1000, null);
    insert.run('legado-3', 'rest_demo_01', 43, 'token-persistido-43', '[]', 'entregue', now, now + 1000, now + 2000);
    const original = database.prepare('SELECT * FROM pedidos ORDER BY id').all();
    const originalRest = database.prepare('SELECT * FROM restaurantes ORDER BY id').all();
    database.close();
    database = undefined;

    const env = { ...process.env, DATA_PATH: dir };
    await executeNode("import db from './src/db.js'; db.close();", env);
    database = new Database(file);
    assert.deepEqual(database.prepare('SELECT * FROM pedidos ORDER BY id').all(), original);
    assert.deepEqual(database.prepare('SELECT * FROM restaurantes ORDER BY id').all(), originalRest);
    assert.equal(database.prepare('SELECT count(*) n FROM usuarios').get().n, 0);
    assert.equal(database.prepare('SELECT count(*) n FROM sessoes').get().n, 0);
    assert.ok(database.prepare("SELECT name FROM sqlite_master WHERE name='usuarios'").get());
    assert.ok(database.prepare("SELECT name FROM sqlite_master WHERE name='sessoes'").get());
    database.close();
    database = undefined;

    // Reiniciar não deve recriar o restaurante, modificar pedidos ou criar credenciais.
    await executeNode("import db from './src/db.js'; db.close();", env);
    database = new Database(file);
    assert.deepEqual(database.prepare('SELECT * FROM pedidos ORDER BY id').all(), original);
    assert.deepEqual(database.prepare('SELECT * FROM restaurantes ORDER BY id').all(), originalRest);
    assert.equal(database.prepare('SELECT count(*) n FROM usuarios').get().n, 0);
    database.close();
    database = undefined;

    // Depois do upgrade, o gerente vinculado ao restaurante legado deve ver os pedidos antigos.
    process.env.DATA_PATH = dir;
    const [{ default: db }, { default: Fastify }, authModule, pedidosModule] = await Promise.all([
      import('../src/db.js'),
      import('fastify'),
      import('../src/auth.js'),
      import('../src/routes/pedidos.js')
    ]);
    const current = Date.now();
    db.prepare(`INSERT INTO usuarios
      (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
      VALUES (?, ?, ?, ?, ?, ?, ?, ?)`).run(
      'legacy-manager', 'rest_demo_01', 'Gerente legado', 'gerente-legado',
      await authModule.passwordHash('senha-forte-legado-123'), 'gerente', current, current
    );
    const app = Fastify();
    try {
      await app.register(authModule.authRoutes);
      await app.register(pedidosModule.pedidosRoutes);
      await app.ready();
      const signed = await app.inject({
        method: 'POST', url: '/api/auth/login',
        headers: { host: 'localhost', origin: 'http://localhost' },
        payload: { login: 'gerente-legado', senha: 'senha-forte-legado-123' }
      });
      assert.equal(signed.statusCode, 200, signed.body);
      const cookie = signed.headers['set-cookie'].split(';')[0];
      const response = await app.inject({
        method: 'GET', url: '/api/pedidos',
        headers: { host: 'localhost', cookie }
      });
      assert.equal(response.statusCode, 200, response.body);
      assert.deepEqual(response.json().map(p => [p.numero, p.token, p.status]).sort((a, b) => a[0] - b[0]), [
        [41, 'token-persistido-41', 'preparo'],
        [42, 'token-persistido-42', 'pronto']
      ]);
      // Pedido entregue continua armazenado, mas não reaparece na fila ativa.
      assert.equal(db.prepare("SELECT status FROM pedidos WHERE id='legado-3'").get().status, 'entregue');
    } finally {
      await app.close();
      db.close();
    }
  } finally {
    if (database) database.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
