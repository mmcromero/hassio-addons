// AVISAQUI-PAIR-001 — esquema aditivo isolado.
// Não executar na inicialização até revisão técnica + plano de migração.
// A aplicação existente e suas credenciais legadas permanecem inalteradas.
export function preparePairingSchema(db) {
  // better-sqlite3: DDL transacional com BEGIN IMMEDIATE; rollback em falha.
  const migration = db.transaction(() => {
    db.exec(`
      CREATE TABLE IF NOT EXISTS integracao_pareamento_solicitacoes (
        id TEXT PRIMARY KEY,
        client_request_id TEXT NOT NULL UNIQUE,
        protocol TEXT NOT NULL CHECK (protocol = 'pair-v1'),
        estado TEXT NOT NULL CHECK (estado IN
          ('PENDENTE','APROVADO','RECUSADO','EXPIRADO','RESGATADO','CONFIRMADO','CANCELADO')),
        signing_public_key TEXT NOT NULL,
        delivery_public_key TEXT NOT NULL,
        codigo TEXT NOT NULL CHECK (length(codigo) = 8),
        caixa_nome_aprovado TEXT CHECK (caixa_nome_aprovado IS NULL OR length(caixa_nome_aprovado) BETWEEN 1 AND 120),
        criado_em INTEGER NOT NULL,
        expira_aprovacao_em INTEGER NOT NULL,
        restaurante_id TEXT REFERENCES restaurantes(id),
        aprovado_por TEXT REFERENCES usuarios(id),
        aprovado_em INTEGER,
        recusado_em INTEGER,
        cancelado_em INTEGER,
        tentativas_codigo INTEGER NOT NULL DEFAULT 0 CHECK (tentativas_codigo >= 0)
      );
      CREATE INDEX IF NOT EXISTS idx_pair_solicitacoes_estado
        ON integracao_pareamento_solicitacoes(estado, expira_aprovacao_em);
      CREATE INDEX IF NOT EXISTS idx_pair_solicitacoes_restaurante
        ON integracao_pareamento_solicitacoes(restaurante_id, criado_em);
      CREATE INDEX IF NOT EXISTS idx_pair_solicitacoes_codigo
        ON integracao_pareamento_solicitacoes(codigo, estado);

      CREATE TABLE IF NOT EXISTS integracao_pareamento_desafios (
        id TEXT PRIMARY KEY,
        pairing_id TEXT NOT NULL REFERENCES integracao_pareamento_solicitacoes(id),
        purpose TEXT NOT NULL CHECK (purpose IN ('status','redeem','ack')),
        operation_id TEXT NOT NULL,
        desafio BLOB NOT NULL CHECK (length(desafio) = 32),
        criado_em INTEGER NOT NULL,
        expira_em INTEGER NOT NULL,
        consumido_em INTEGER
      );
      CREATE INDEX IF NOT EXISTS idx_pair_desafios_operacao
        ON integracao_pareamento_desafios(pairing_id, purpose, operation_id);
      CREATE INDEX IF NOT EXISTS idx_pair_desafios_prazo
        ON integracao_pareamento_desafios(expira_em, consumido_em);

      CREATE TABLE IF NOT EXISTS integracao_impressao_dispositivos (
        id TEXT PRIMARY KEY,
        restaurante_id TEXT NOT NULL REFERENCES restaurantes(id),
        caixa_nome TEXT NOT NULL,
        criado_em INTEGER NOT NULL,
        aprovado_por TEXT REFERENCES usuarios(id),
        revogado_em INTEGER,
        last_seen_em INTEGER
      );
      CREATE INDEX IF NOT EXISTS idx_pair_dispositivos_restaurante
        ON integracao_impressao_dispositivos(restaurante_id, revogado_em);

      CREATE TABLE IF NOT EXISTS integracao_pareamento_resgates (
        pairing_id TEXT PRIMARY KEY REFERENCES integracao_pareamento_solicitacoes(id),
        operation_id TEXT NOT NULL UNIQUE,
        dispositivo_id TEXT NOT NULL UNIQUE REFERENCES integracao_impressao_dispositivos(id),
        envelope_json TEXT NOT NULL,
        emitido_em INTEGER NOT NULL,
        recuperacao_expira_em INTEGER NOT NULL,
        ack_operation_id TEXT UNIQUE,
        ack_em INTEGER
      );
      CREATE INDEX IF NOT EXISTS idx_pair_resgates_recuperacao
        ON integracao_pareamento_resgates(recuperacao_expira_em, ack_em);

      -- Limites compartilhados entre processos que usam o mesmo arquivo SQLite.
      -- Chave derivada em SHA256; não persistir IP em claro.
      CREATE TABLE IF NOT EXISTS integracao_pareamento_limites (
        chave_hash TEXT PRIMARY KEY CHECK (length(chave_hash) = 64),
        contador INTEGER NOT NULL CHECK (contador >= 0),
        expira_em INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_pair_limites_expira
        ON integracao_pareamento_limites(expira_em);

      CREATE TABLE IF NOT EXISTS integracao_pareamento_auditoria (
        id TEXT PRIMARY KEY,
        actor_id TEXT,
        restaurante_id TEXT,
        dispositivo_id TEXT,
        pairing_id TEXT,
        acao TEXT NOT NULL,
        resultado TEXT NOT NULL,
        criado_em INTEGER NOT NULL
      );
      CREATE INDEX IF NOT EXISTS idx_pair_auditoria_restaurante
        ON integracao_pareamento_auditoria(restaurante_id, criado_em);
    `);
    // Evolução aditiva: bancos de laboratório anteriores podem ter a solicitação sem nome aprovado.
    const pairingCols = db.prepare('PRAGMA table_info(integracao_pareamento_solicitacoes)').all();
    if (!pairingCols.some(c => c.name === 'caixa_nome_aprovado')) {
      db.exec('ALTER TABLE integracao_pareamento_solicitacoes ADD COLUMN caixa_nome_aprovado TEXT');
    }
    // Esta tabela pode não existir antes de registrar as rotas de impressão.
    // Se existir, migrar sem tocar em chaves já emitidas.
    const legacy = db.prepare("SELECT name FROM sqlite_master WHERE type='table' AND name='integracao_impressao_chaves'").get();
    if (legacy) {
      const columns = db.prepare('PRAGMA table_info(integracao_impressao_chaves)').all();
      if (!columns.some(c => c.name === 'dispositivo_id')) {
        db.exec('ALTER TABLE integracao_impressao_chaves ADD COLUMN dispositivo_id TEXT REFERENCES integracao_impressao_dispositivos(id)');
      }
      db.exec('CREATE INDEX IF NOT EXISTS idx_pair_chaves_dispositivo ON integracao_impressao_chaves(dispositivo_id)');
    }
  });
  migration.immediate();
}
