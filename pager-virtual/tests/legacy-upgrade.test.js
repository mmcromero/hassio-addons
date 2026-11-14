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
  } finally {
    if (database) database.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
