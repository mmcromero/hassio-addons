import Database from 'better-sqlite3';
import path from 'path';
import fs from 'fs';

// Diretório de dados persistentes:
// No Home Assistant OS, o volume mapeado é /data
// Em desenvolvimento local ou VPS, usa pasta ./data na raiz do projeto
const DATA_DIR = process.env.DATA_PATH || (fs.existsSync('/data') ? '/data' : path.resolve(process.cwd(), 'data'));

if (!fs.existsSync(DATA_DIR)) {
  fs.mkdirSync(DATA_DIR, { recursive: true });
}

const DB_PATH = path.join(DATA_DIR, 'pager_virtual.db');
console.log(`[DB] Conectando ao banco SQLite em: ${DB_PATH}`);

const db = new Database(DB_PATH);

// Configurações de alta performance e resiliência (WAL mode)
db.pragma('journal_mode = WAL');
db.pragma('synchronous = NORMAL');
db.pragma('foreign_keys = ON');

// Inicialização das tabelas essenciais (Arquitetura Multi-Tenant / Escalável)
db.exec(`
  CREATE TABLE IF NOT EXISTS restaurantes (
    id TEXT PRIMARY KEY,
    nome TEXT NOT NULL,
    slug TEXT UNIQUE NOT NULL,
    ativo INTEGER DEFAULT 1,
    created_at INTEGER NOT NULL
  );

  CREATE TABLE IF NOT EXISTS pedidos (
    id TEXT PRIMARY KEY,
    restaurante_id TEXT NOT NULL,
    numero INTEGER NOT NULL,
    token TEXT UNIQUE NOT NULL,
    itens_json TEXT,
    status TEXT NOT NULL DEFAULT 'preparo', -- preparo | pronto | entregue
    created_at INTEGER NOT NULL,
    pronto_at INTEGER,
    entregue_at INTEGER,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id)
  );

  CREATE INDEX IF NOT EXISTS idx_pedidos_token ON pedidos(token);
  CREATE INDEX IF NOT EXISTS idx_pedidos_rest_status ON pedidos(restaurante_id, status);
`);

// Seed de restaurante padrão caso não exista
const defaultRest = db.prepare('SELECT id FROM restaurantes WHERE slug = ?').get('demo');
if (!defaultRest) {
  const insertRest = db.prepare(`
    INSERT INTO restaurantes (id, nome, slug, ativo, created_at)
    VALUES (?, ?, ?, 1, ?)
  `);
  insertRest.run('rest_demo_01', 'Burger House Demo', 'demo', Date.now());
  console.log('[DB] Restaurante padrão demo inserido com sucesso.');
}

export default db;
