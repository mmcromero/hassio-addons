import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, copyFileSync, rmSync, statSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawn } from 'node:child_process';
import Database from 'better-sqlite3';

function runMigrator(dataDir) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, ['--input-type=module', '-e',
      "import db from './src/db.js'; db.close();"
    ], { env: { ...process.env, DATA_PATH: dataDir }, stdio: ['ignore', 'ignore', 'pipe'] });
    let error = '';
    child.stderr.on('data', chunk => { error += chunk.toString(); });
    child.on('error', reject);
    child.on('exit', code => code === 0 ? resolve() : reject(new Error(error || 'Migração falhou: ' + code)));
  });
}

test('backup SQLite consistente durante WAL permite restauração e upgrade sem perda', { timeout: 20000 }, async () => {
  const root = mkdtempSync(path.join(tmpdir(), 'bipou-backup-'));
  const sourceDir = path.join(root, 'source');
  const restoredDir = path.join(root, 'restored');
  mkdirSync(sourceDir); mkdirSync(restoredDir);
  const sourceFile = path.join(sourceDir, 'pager_virtual.db');
  const backupFile = path.join(root, 'snapshot.db');
  const restoredFile = path.join(restoredDir, 'pager_virtual.db');
  let source;
  try {
    source = new Database(sourceFile);
    source.pragma('journal_mode = WAL');
    source.pragma('foreign_keys = ON');
    source.exec(`
      CREATE TABLE restaurantes (id TEXT PRIMARY KEY, nome TEXT NOT NULL, slug TEXT UNIQUE NOT NULL, ativo INTEGER DEFAULT 1, created_at INTEGER NOT NULL);
      CREATE TABLE pedidos (id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL, numero INTEGER NOT NULL, token TEXT UNIQUE NOT NULL, itens_json TEXT,
        status TEXT NOT NULL DEFAULT 'preparo', created_at INTEGER NOT NULL, pronto_at INTEGER, entregue_at INTEGER,
        FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id));
      CREATE INDEX idx_pedidos_token ON pedidos(token);
      CREATE INDEX idx_pedidos_rest_status ON pedidos(restaurante_id, status);
    `);
    const now = Date.now();
    source.prepare('INSERT INTO restaurantes (id, nome, slug, created_at) VALUES (?, ?, ?, ?)')
      .run('rest-demo', 'Restaurante em operação', 'rest-demo', now);
    const insert = source.prepare(`INSERT INTO pedidos (id, restaurante_id, numero, token, itens_json, status, created_at)
      VALUES (?, 'rest-demo', ?, ?, '[]', 'preparo', ?)`);
    for (let i = 1; i <= 120; i++) insert.run('pedido-' + i, i, 'token-' + i, now + i);
    source.prepare("UPDATE pedidos SET status='pronto', pronto_at=? WHERE id='pedido-2'").run(now + 200);
    source.prepare("UPDATE pedidos SET status='entregue', entregue_at=? WHERE id='pedido-3'").run(now + 300);
    // Não fecha o banco antes da cópia: a conexão permanece aberta em WAL.
    const original = source.prepare('SELECT * FROM pedidos ORDER BY numero').all();
    assert.equal(original.length, 120);
    await source.backup(backupFile);
    assert.ok(statSync(backupFile).size > 0);
    const snapshot = new Database(backupFile, { readonly: true });
    try {
      assert.equal(snapshot.pragma('integrity_check', { simple: true }), 'ok');
      assert.deepEqual(snapshot.prepare('SELECT * FROM pedidos ORDER BY numero').all(), original);
      assert.deepEqual(snapshot.pragma('foreign_key_check'), []);
    } finally { snapshot.close(); }

    copyFileSync(backupFile, restoredFile);
    await runMigrator(restoredDir);
    let recovered = new Database(restoredFile);
    try {
      assert.equal(recovered.pragma('integrity_check', { simple: true }), 'ok');
      assert.deepEqual(recovered.pragma('foreign_key_check'), []);
      assert.deepEqual(recovered.prepare('SELECT * FROM pedidos ORDER BY numero').all(), original);
      assert.equal(recovered.prepare('SELECT COUNT(*) n FROM usuarios').get().n, 0);
      assert.equal(recovered.prepare('SELECT COUNT(*) n FROM sessoes').get().n, 0);
    } finally { recovered.close(); }

    // O arquivo de backup não foi alterado pela migração da cópia restaurada.
    const unchanged = new Database(backupFile, { readonly: true });
    try {
      assert.deepEqual(unchanged.prepare('SELECT * FROM pedidos ORDER BY numero').all(), original);
      assert.equal(unchanged.prepare("SELECT count(*) n FROM sqlite_master WHERE name='usuarios'").get().n, 0);
    } finally { unchanged.close(); }

    // Simula rollback da cópia migrada: restaura o snapshot antigo em pasta separada.
    const rollbackDir = path.join(root, 'rollback');
    mkdirSync(rollbackDir);
    const rollbackFile = path.join(rollbackDir, 'pager_virtual.db');
    copyFileSync(backupFile, rollbackFile);
    const rollback = new Database(rollbackFile, { readonly: true });
    try {
      assert.equal(rollback.pragma('integrity_check', { simple: true }), 'ok');
      assert.deepEqual(rollback.prepare('SELECT * FROM pedidos ORDER BY numero').all(), original);
    } finally { rollback.close(); }
  } finally {
    if (source) source.close();
    rmSync(root, { recursive: true, force: true });
  }
});
