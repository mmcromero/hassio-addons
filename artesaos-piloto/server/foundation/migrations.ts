import {moduleGrantsSql} from '../pilot/module-grants.js';
import {engagementSql,resourceSql} from '../evolution-schema.js';
import {shippingSql} from '../shipping-schema.js';
import {attentionSql} from '../attention-schema.js';
import {distributionSql} from '../distribution-schema.js';
import {saleSql} from '../sale-schema.js';
import {financeSql} from '../finance-schema.js';
import {orderSql} from '../order-schema.js';
import {productStockSql} from '../product-stock-schema.js';
import {materialLedgerSql} from '../material-ledger-schema.js';
import {legacySql,upgradeTenant,upgradeControl} from './legacy-schema.js';
import type {DatabaseSync} from 'node:sqlite';
import {createHash} from 'node:crypto';
import {transaction} from './transaction.js';
export type DatabaseScope='tenant'|'control'|'interest'|'support'|'legal';
export type Migration={version:number;name:string;sql:string;upId?:string;up?:(db:DatabaseSync)=>void};
const operations=`CREATE TABLE operation_records(
 scope TEXT NOT NULL, operation_key TEXT NOT NULL, request_hash TEXT NOT NULL,
 response_json TEXT NOT NULL, created_at TEXT NOT NULL,
 PRIMARY KEY(scope,operation_key));
CREATE TABLE operation_audit(
 id INTEGER PRIMARY KEY, scope TEXT NOT NULL, operation_key TEXT NOT NULL,
 actor TEXT NOT NULL, action TEXT NOT NULL, source_id TEXT NOT NULL,
 details_json TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(scope,operation_key) REFERENCES operation_records(scope,operation_key));
CREATE INDEX operation_audit_source ON operation_audit(action,source_id,id);
CREATE TRIGGER operation_audit_no_update BEFORE UPDATE ON operation_audit BEGIN SELECT RAISE(ABORT,'Histórico imutável'); END;
CREATE TRIGGER operation_audit_no_delete BEFORE DELETE ON operation_audit BEGIN SELECT RAISE(ABORT,'Histórico imutável'); END;`;
export const migrations:Record<DatabaseScope,readonly Migration[]>={
 tenant:[{version:1,name:'fundacao-operacoes',sql:operations},{version:2,name:'consolidacao-legada',sql:legacySql.tenant,upId:'tenant-legacy-v1',up:upgradeTenant},{version:3,name:'materiais-compras',sql:materialLedgerSql},{version:4,name:'estoque-produtos-fabricacao',sql:productStockSql},{version:5,name:'pedidos-reservas',sql:orderSql},{version:6,name:'financeiro-liquidacoes',sql:financeSql},{version:7,name:'vendas-cupons-divergencias',sql:saleSql},{version:8,name:'sessoes-consignacoes',sql:distributionSql},{version:9,name:'central-pendencias',sql:attentionSql},{version:10,name:'preparo-expedicao',sql:shippingSql},{version:11,name:'clientes-visitantes-rastreabilidade',sql:engagementSql}],
 control:[{version:1,name:'fundacao-controle',sql:'SELECT 1;'},
 {version:2,name:'administracao-local-debian',sql:`CREATE TABLE local_admin(
 id INTEGER PRIMARY KEY CHECK(id=1),email TEXT NOT NULL UNIQUE,password_hash TEXT NOT NULL,
 revision INTEGER NOT NULL CHECK(revision>=1),updated_at TEXT NOT NULL);
 CREATE TABLE local_admin_activation(id INTEGER PRIMARY KEY CHECK(id=1),purpose TEXT NOT NULL CHECK(purpose IN ('setup','recovery')),code_hash TEXT NOT NULL,expires_at INTEGER NOT NULL);
 CREATE TABLE installation_distribution(id INTEGER PRIMARY KEY CHECK(id=1),distribution TEXT NOT NULL CHECK(distribution IN ('home-assistant','debian')));`},{version:3,name:'consolidacao-legada',sql:legacySql.control,upId:'control-legacy-v1',up:upgradeControl},{version:4,name:'interessados-convites-rastreaveis',sql:`
 CREATE TABLE pilot_interest_invitation_links(interest_id TEXT NOT NULL,invitation_hash TEXT NOT NULL REFERENCES pilot_invites(hash),registered_at INTEGER NOT NULL,linked_at INTEGER NOT NULL,actor TEXT NOT NULL,channel TEXT NOT NULL,PRIMARY KEY(interest_id,invitation_hash));
 CREATE TABLE pilot_invitation_share_events(request_key TEXT PRIMARY KEY,invitation_hash TEXT NOT NULL REFERENCES pilot_invites(hash),actor TEXT NOT NULL,event TEXT NOT NULL,created_at INTEGER NOT NULL);
 CREATE TRIGGER invitation_share_no_update BEFORE UPDATE ON pilot_invitation_share_events BEGIN SELECT RAISE(ABORT,'Compartilhamento imutável'); END;
 CREATE TRIGGER invitation_share_no_delete BEFORE DELETE ON pilot_invitation_share_events BEGIN SELECT RAISE(ABORT,'Compartilhamento imutável'); END;
 CREATE TABLE pilot_account_registrations(user_id TEXT PRIMARY KEY REFERENCES pilot_users(id),registered_at INTEGER NOT NULL);
 CREATE TRIGGER interest_links_no_update BEFORE UPDATE ON pilot_interest_invitation_links BEGIN SELECT RAISE(ABORT,'Vínculo histórico imutável'); END;
 CREATE TRIGGER interest_links_no_delete BEFORE DELETE ON pilot_interest_invitation_links BEGIN SELECT RAISE(ABORT,'Vínculo histórico imutável'); END;
 CREATE TRIGGER account_registration_no_update BEFORE UPDATE ON pilot_account_registrations BEGIN SELECT RAISE(ABORT,'Data original imutável'); END;
 CREATE TRIGGER account_registration_no_delete BEFORE DELETE ON pilot_account_registrations BEGIN SELECT RAISE(ABORT,'Data original imutável'); END;`},{version:5,name:'liberacao-modulos-piloto',sql:moduleGrantsSql}],
 interest:[{version:1,name:'fundacao-interesses',sql:'SELECT 1;'},{version:2,name:'consolidacao-legada',sql:legacySql.interest}],
 support:[{version:1,name:'fundacao-suporte',sql:'SELECT 1;'},{version:2,name:'consolidacao-legada',sql:legacySql.support}],
 legal:[{version:1,name:'fundacao-legal',sql:'SELECT 1;'},{version:2,name:'consolidacao-legada',sql:legacySql.legal},{version:3,name:'documentos-manuais-contribuicao',sql:resourceSql}]
};
export const schemaVersions=Object.fromEntries(Object.entries(migrations).map(([scope,list])=>[scope,list.at(-1)?.version??0]));
const checksum=(m:Migration)=>createHash('sha256').update(JSON.stringify(m.up?[m.version,m.name,m.sql,m.upId]:[m.version,m.name,m.sql])).digest('hex');
/** Migrações futuras são comuns às duas distribuições. Não abre arquivos de banco. */
export function migrate(db:DatabaseSync,scope:DatabaseScope,list:readonly Migration[]=migrations[scope]){
 if(db.isTransaction)throw Error('Inicie migrações fora de transações de negócio.');
 list.forEach((m,i)=>{if(m.version!==i+1||!m.name||!m.sql||(m.up&&!m.upId))throw Error('Sequência de migrações inválida.');});
 db.exec('PRAGMA busy_timeout=5000; PRAGMA foreign_keys=ON;');
 transaction(db,()=>{
  db.exec(`CREATE TABLE IF NOT EXISTS schema_identity(id INTEGER PRIMARY KEY CHECK(id=1),scope TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS schema_migrations(version INTEGER PRIMARY KEY,name TEXT NOT NULL,checksum TEXT NOT NULL,applied_at TEXT NOT NULL);`);
  const identity=db.prepare('SELECT scope FROM schema_identity WHERE id=1').get();
  if(identity&&identity.scope!==scope)throw Error('Tipo de banco incompatível.');
  const applied=db.prepare('SELECT version,name,checksum FROM schema_migrations ORDER BY version').all();
  for(const [i,row] of applied.entries()){
   const expected=list[i];
   if(!expected||row.version!==expected.version||row.name!==expected.name||row.checksum!==checksum(expected))throw Error('Schema futuro ou migração histórica divergente; atualização recusada.');
  }
  if(!identity)db.prepare('INSERT INTO schema_identity VALUES(1,?)').run(scope);
  for(const m of list.slice(applied.length)){
   db.exec(m.sql);m.up?.(db);
   db.prepare('INSERT INTO schema_migrations VALUES(?,?,?,?)').run(m.version,m.name,checksum(m),new Date().toISOString());
  }
 });
}
/** Fecha a conexão caso a preparação falhe, inclusive em schema futuro. */
export function initializeDatabase(db:DatabaseSync,scope:DatabaseScope){
 try{migrate(db,scope);}catch(error){db.close();throw error;}
}
