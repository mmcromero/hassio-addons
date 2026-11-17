import test from 'node:test';
import assert from 'node:assert/strict';
import Database from 'better-sqlite3';
import { preparePairingSchema } from '../src/pairing/backend/schema.js';

test('migração aditiva mantém credencial antiga e pode repetir', () => {
  const db = new Database(':memory:');
  try {
    db.pragma('foreign_keys = ON');
    db.exec("CREATE TABLE restaurantes(id TEXT PRIMARY KEY);CREATE TABLE usuarios(id TEXT PRIMARY KEY);"+
      "CREATE TABLE integracao_impressao_chaves(id TEXT PRIMARY KEY,restaurante_id TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,criado_em INTEGER NOT NULL,revogado_em INTEGER,FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id));"+
      "INSERT INTO restaurantes(id) VALUES('rest-1');"+
      "INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em) VALUES('legacy-1','rest-1','hash-ficticio',111);");
    preparePairingSchema(db);
    preparePairingSchema(db);
    assert.equal(db.prepare('PRAGMA table_info(integracao_impressao_chaves)').all().filter(c => c.name === 'dispositivo_id').length,1);
    const legacy=db.prepare('SELECT * FROM integracao_impressao_chaves').get();
    assert.equal(legacy.id,'legacy-1');
    assert.equal(legacy.hash,'hash-ficticio');
    assert.equal(legacy.dispositivo_id,null);
    assert.equal(legacy.revogado_em,null);
    const names=db.prepare("SELECT name FROM sqlite_master WHERE type='table'").all().map(x=>x.name);
    for(const name of ['integracao_pareamento_solicitacoes','integracao_pareamento_desafios','integracao_impressao_dispositivos','integracao_pareamento_resgates','integracao_pareamento_auditoria'])assert.ok(names.includes(name));
  } finally { db.close(); }
});
test('restrições impedem resgates duplicados e desafios inválidos', () => {
  const db = new Database(':memory:');
  try {
    db.pragma('foreign_keys = ON');
    db.exec("CREATE TABLE restaurantes(id TEXT PRIMARY KEY);CREATE TABLE usuarios(id TEXT PRIMARY KEY);INSERT INTO restaurantes(id) VALUES('rest-1');");
    preparePairingSchema(db);
    db.prepare("INSERT INTO integracao_pareamento_solicitacoes(id,client_request_id,protocol,estado,signing_public_key,delivery_public_key,codigo,criado_em,expira_aprovacao_em) VALUES(?,?,?,?,?,?,?,?,?)").run('pair-1','req-1','pair-v1','APROVADO','sign-key','delivery-key','00000001',10,20);
    db.prepare("INSERT INTO integracao_impressao_dispositivos(id,restaurante_id,caixa_nome,criado_em) VALUES(?,?,?,?)").run('dev-1','rest-1','Caixa',10);
    const insert=db.prepare("INSERT INTO integracao_pareamento_resgates(pairing_id,operation_id,dispositivo_id,envelope_json,emitido_em,recuperacao_expira_em) VALUES(?,?,?,?,?,?)");
    insert.run('pair-1','op-1','dev-1','{"envelope":"cifrado-ficticio"}',10,99);
    assert.throws(()=>insert.run('pair-1','op-2','dev-1','outro',12,99),/UNIQUE/);
    assert.equal(db.prepare('SELECT envelope_json FROM integracao_pareamento_resgates').get().envelope_json,'{"envelope":"cifrado-ficticio"}');
    assert.throws(()=>db.prepare("INSERT INTO integracao_pareamento_desafios(id,pairing_id,purpose,operation_id,desafio,criado_em,expira_em) VALUES(?,?,?,?,?,?,?)").run('challenge-1','pair-1','bad','op',Buffer.alloc(32),11,22),/CHECK/);
  } finally {db.close();}
});
