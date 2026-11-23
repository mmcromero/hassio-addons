import type {DatabaseSync} from 'node:sqlite';
import {essentialModules,moduleKeys,type ModuleAccess,type ModuleKey} from '../module-access.js';
export const moduleGrantsSql=`
CREATE TABLE pilot_module_access(user_id TEXT PRIMARY KEY REFERENCES pilot_users(id),enabled_json TEXT NOT NULL,revision INTEGER NOT NULL);
CREATE TABLE pilot_module_audit(id INTEGER PRIMARY KEY,user_id TEXT NOT NULL REFERENCES pilot_users(id),actor TEXT NOT NULL,before_json TEXT NOT NULL,after_json TEXT NOT NULL,revision INTEGER NOT NULL,created_at TEXT NOT NULL);
CREATE TRIGGER module_audit_no_update BEFORE UPDATE ON pilot_module_audit BEGIN SELECT RAISE(ABORT,'Histórico imutável'); END;
CREATE TRIGGER module_audit_no_delete BEFORE DELETE ON pilot_module_audit BEGIN SELECT RAISE(ABORT,'Histórico imutável'); END;
INSERT INTO pilot_module_access SELECT id,'${JSON.stringify(moduleKeys)}',1 FROM pilot_users;
`;
export class ModuleAccessError extends Error{constructor(readonly status:number,message:string){super(message);}}
export function getModuleAccess(db:DatabaseSync,id:string):ModuleAccess{
 const row=db.prepare('SELECT enabled_json,revision FROM pilot_module_access WHERE user_id=?').get(id);
 return row?{enabled:JSON.parse(String(row.enabled_json)),revision:Number(row.revision)}:{enabled:[...essentialModules],revision:0};
}
export function setModuleAccess(db:DatabaseSync,id:string,enabled:unknown,revision:unknown,actor:string):ModuleAccess{
 if(!Array.isArray(enabled)||enabled.some(k=>!moduleKeys.includes(k))||new Set(enabled).size!==enabled.length||!Number.isSafeInteger(revision)||Number(revision)<0)throw new ModuleAccessError(400,'Liberações inválidas.');
 db.exec('BEGIN IMMEDIATE');try{
  if(!db.prepare('SELECT id FROM pilot_users WHERE id=?').get(id))throw new ModuleAccessError(404,'Usuário não encontrado.');
  const before=getModuleAccess(db,id);if(before.revision!==revision)throw new ModuleAccessError(409,'Liberações alteradas em outra aba. Atualize a lista.');
  const next={enabled:moduleKeys.filter(k=>(enabled as ModuleKey[]).includes(k)),revision:before.revision+1};
  db.prepare('INSERT INTO pilot_module_access VALUES(?,?,?) ON CONFLICT(user_id) DO UPDATE SET enabled_json=excluded.enabled_json,revision=excluded.revision').run(id,JSON.stringify(next.enabled),next.revision);
  db.prepare('INSERT INTO pilot_module_audit(user_id,actor,before_json,after_json,revision,created_at) VALUES(?,?,?,?,?,?)').run(id,actor,JSON.stringify(before.enabled),JSON.stringify(next.enabled),next.revision,new Date().toISOString());
  db.exec('COMMIT');return next;
 }catch(e){db.exec('ROLLBACK');throw e;}
}
