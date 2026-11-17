import test from 'node:test';
import assert from 'node:assert/strict';
import Database from 'better-sqlite3';
import { mkdtempSync, rmSync } from 'node:fs';
import { join } from 'node:path';
import { tmpdir } from 'node:os';
import { preparePairingSchema } from '../src/pairing/backend/schema.js';

test('backup consistente de SQLite WAL permite ensaio aditivo e recuperação de credencial legada',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'avisaqui-pair-restore-'));
  const live=join(dir,'original-lab.db'),backup=join(dir,'backup-lab.db');
  let primary,restore;
  try {
    primary=new Database(live);
    primary.pragma('journal_mode = WAL');
    primary.pragma('foreign_keys = ON');
    primary.exec(`CREATE TABLE restaurantes(id TEXT PRIMARY KEY);
      CREATE TABLE usuarios(id TEXT PRIMARY KEY);
      CREATE TABLE integracao_impressao_chaves(
        id TEXT PRIMARY KEY,restaurante_id TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,
        criado_em INTEGER NOT NULL,revogado_em INTEGER,
        FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id));
      INSERT INTO restaurantes(id) VALUES('rest-lab');
      INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em)
        VALUES('credencial-legada','rest-lab','digest-sintetico',111);`);
    // better-sqlite3 backup API produz snapshot íntegro mesmo em WAL, sem
    // copiar somente o arquivo .db enquanto há escrita pendente.
    await primary.backup(backup);
    preparePairingSchema(primary);
    preparePairingSchema(primary);
    assert.equal(primary.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name='integracao_pareamento_solicitacoes'").get().n,1);
    const migrated=primary.prepare("SELECT * FROM integracao_impressao_chaves WHERE id='credencial-legada'").get();
    assert.equal(migrated.hash,'digest-sintetico');
    assert.equal(migrated.dispositivo_id,null);
    assert.equal(migrated.revogado_em,null);
    primary.close();primary=null;
    // Restaurar a partir do backup em NOVA conexão, sem operar em produção.
    restore=new Database(backup,{readonly:true});
    const original=restore.prepare("SELECT * FROM integracao_impressao_chaves WHERE id='credencial-legada'").get();
    assert.equal(original.hash,'digest-sintetico');
    assert.equal(original.revogado_em,null);
    assert.equal(Object.hasOwn(original,'dispositivo_id'),false);
    assert.equal(restore.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE type='table' AND name='integracao_pareamento_solicitacoes'").get().n,0);
    assert.equal(restore.pragma('integrity_check',{simple:true}),'ok');
  } finally {
    if(primary)primary.close();
    if(restore)restore.close();
    rmSync(dir,{recursive:true,force:true});
  }
});
