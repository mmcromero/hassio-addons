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

  -- Fundação de autenticação. Sem usuário ou senha pré-cadastrados.
  CREATE TABLE IF NOT EXISTS usuarios (
    id TEXT PRIMARY KEY,
    restaurante_id TEXT,
    nome TEXT NOT NULL,
    login TEXT NOT NULL UNIQUE,
    senha_hash TEXT NOT NULL,
    papel TEXT NOT NULL CHECK (papel IN ('master', 'gerente', 'operador')),
    ativo INTEGER NOT NULL DEFAULT 1 CHECK (ativo IN (0, 1)),
    criado_em INTEGER NOT NULL,
    atualizado_em INTEGER NOT NULL,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id),
    CHECK (
      (papel = 'master' AND restaurante_id IS NULL) OR
      (papel IN ('gerente', 'operador') AND restaurante_id IS NOT NULL)
    )
  );

  CREATE INDEX IF NOT EXISTS idx_usuarios_restaurante
  ON usuarios(restaurante_id, papel, ativo);

  CREATE TABLE IF NOT EXISTS sessoes (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    criado_em INTEGER NOT NULL,
    expira_em INTEGER NOT NULL,
    revogado_em INTEGER,
    FOREIGN KEY (usuario_id) REFERENCES usuarios(id) ON DELETE CASCADE
  );

  CREATE INDEX IF NOT EXISTS idx_sessoes_usuario
  ON sessoes(usuario_id, expira_em);

  -- Seleção explícita do restaurante pelo Master Admin, restrita à sessão atual.
  CREATE TABLE IF NOT EXISTS master_contextos (
    sessao_id TEXT PRIMARY KEY,
    restaurante_id TEXT NOT NULL,
    selecionado_em INTEGER NOT NULL,
    FOREIGN KEY (sessao_id) REFERENCES sessoes(id) ON DELETE CASCADE,
    FOREIGN KEY (restaurante_id) REFERENCES restaurantes(id)
  );

  CREATE TABLE IF NOT EXISTS master_contexto_eventos (
    id TEXT PRIMARY KEY,
    usuario_id TEXT NOT NULL,
    sessao_id TEXT NOT NULL,
    restaurante_id TEXT,
    acao TEXT NOT NULL CHECK (acao IN ('entrar', 'sair')),
    criado_em INTEGER NOT NULL
  );

`);

// Migração aditiva: identidade visual opcional, sem modificar restaurantes existentes.
const restaurantColumns = db.prepare('PRAGMA table_info(restaurantes)').all().map(c => c.name);
if (!restaurantColumns.includes('logo_url')) db.exec('ALTER TABLE restaurantes ADD COLUMN logo_url TEXT');

// Nenhum restaurante fictício é criado automaticamente.
// Registros antigos são preservados na migração aditiva.

export default db;

// Migração aditiva: dados opcionais de atendimento e numeração manual/automática.
const pedidoCols = db.prepare('PRAGMA table_info(pedidos)').all().map(c => c.name);
for (const [col, type] of [['cliente_nome', 'TEXT'], ['cliente_telefone', 'TEXT']]) {
  if (!pedidoCols.includes(col)) db.exec(`ALTER TABLE pedidos ADD COLUMN ${col} ${type}`);
}
db.exec(`
  CREATE TABLE IF NOT EXISTS sequencias_pedidos (
    restaurante_id TEXT PRIMARY KEY REFERENCES restaurantes(id),
    modo TEXT NOT NULL DEFAULT 'manual' CHECK (modo IN ('manual', 'automatico')),
    proximo_numero INTEGER NOT NULL DEFAULT 1 CHECK (proximo_numero > 0)
  );
`);
// Impede duplicatas ativas mesmo em processos distintos. Dados legados conflitantes
// exigem correção explícita antes de instalar o índice, nunca exclusão automática.
try {
  db.exec(`CREATE UNIQUE INDEX IF NOT EXISTS ux_pedidos_ativos_numero
    ON pedidos(restaurante_id, numero) WHERE status IN ('preparo', 'pronto')`);
} catch (error) {
  if (error.code === 'SQLITE_CONSTRAINT_UNIQUE') {
    db.close();
    throw new Error('Migração interrompida: existem números ativos duplicados no mesmo restaurante. '
      + 'Nenhum pedido foi removido. Faça backup consistente e revise os conflitos em cópia isolada antes de tentar novamente.');
  }
  throw error;
}
