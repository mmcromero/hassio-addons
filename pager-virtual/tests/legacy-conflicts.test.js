import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import Database from 'better-sqlite3';

test('migração com duplicatas legadas interrompe sem remover pedidos ou histórico', () => {
  const dir = mkdtempSync(path.join(tmpdir(), 'avisaqui-conflict-'));
  let db;
  try {
    const file = path.join(dir, 'pager_virtual.db');
    db = new Database(file);
    db.exec(`CREATE TABLE restaurantes(id TEXT PRIMARY KEY,nome TEXT,slug TEXT UNIQUE,ativo INTEGER,created_at INTEGER);
      CREATE TABLE pedidos(id TEXT PRIMARY KEY,restaurante_id TEXT,numero INTEGER,token TEXT UNIQUE,
        itens_json TEXT,status TEXT,created_at INTEGER,pronto_at INTEGER,entregue_at INTEGER);
      INSERT INTO restaurantes VALUES('a','Sintético','sintetico',1,1);
      INSERT INTO pedidos VALUES('p1','a',42,'t1','[]','preparo',1,NULL,NULL);
      INSERT INTO pedidos VALUES('p2','a',42,'t2','[]','pronto',2,3,NULL);
      INSERT INTO pedidos VALUES('p3','a',42,'t3','[]','entregue',3,4,5);`);
    const original = db.prepare('SELECT * FROM pedidos ORDER BY id').all();
    db.close();
    const run = () => spawnSync(process.execPath, ['--input-type=module', '-e',
      "import db from './src/db.js'; db.close();"], {
      env: { ...process.env, DATA_PATH: dir }, encoding: 'utf8'
    });
    for (let attempt = 0; attempt < 2; attempt++) {
      const result = run();
      assert.notEqual(result.status, 0);
      assert.match(result.stderr, /Migração interrompida/);
      assert.match(result.stderr, /Nenhum pedido foi removido/);
      db = new Database(file);
      const recovered = db.prepare('SELECT * FROM pedidos ORDER BY id').all();
      // Novas colunas opcionais são aditivas, os campos antigos permanecem iguais.
      assert.deepEqual(recovered.map(row => Object.fromEntries(Object.keys(original[0]).map(k => [k, row[k]]))), original);
      assert.equal(db.pragma('integrity_check', { simple: true }), 'ok');
      db.close();
    }
  } finally {
    if (db?.open) db.close();
    rmSync(dir, { recursive: true, force: true });
  }
});
