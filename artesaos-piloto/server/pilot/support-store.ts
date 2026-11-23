import {initializeDatabase} from '../foundation/migrations.js';
import {DatabaseSync} from 'node:sqlite';
import {mkdirSync,chmodSync} from 'node:fs';
import {join} from 'node:path';
import type {SupportKind,SupportStatus,SupportSummary,SupportDetail,SupportEvent} from './support-model.js';
export class SupportError extends Error{constructor(public code:number,message:string){super(message);}}
type Row=Record<string,unknown>;
export class SupportStore{
 readonly db:DatabaseSync;
 constructor(dir:string){
  mkdirSync(dir,{recursive:true,mode:0o700});const path=join(dir,'pilot-support.sqlite');this.db=new DatabaseSync(path);initializeDatabase(this.db,'support');chmodSync(path,0o600);

 }
 private summary(row:Row):SupportSummary{return {id:Number(row.id),email:String(row.email),kind:row.kind as SupportKind,subject:String(row.subject),status:row.status as SupportStatus,revision:Number(row.revision),createdAt:String(row.created_at),updatedAt:String(row.updated_at)};}
 private ticket(id:number,owner?:string){return owner===undefined?this.db.prepare('SELECT * FROM support_tickets WHERE id=?').get(id):this.db.prepare('SELECT * FROM support_tickets WHERE id=? AND owner=?').get(id,owner);}
 list(owner:string|undefined,page=1,status?:SupportStatus,kind?:SupportKind){
  const conditions:string[]=[],values:(string|number)[]=[];
  if(owner!==undefined){conditions.push('owner=?');values.push(owner);}if(status){conditions.push('status=?');values.push(status);}if(kind){conditions.push('kind=?');values.push(kind);}
  const where=conditions.length?' WHERE '+conditions.join(' AND '):'';const total=Number(this.db.prepare('SELECT COUNT(*) n FROM support_tickets'+where).get(...values)!.n),pages=Math.max(1,Math.ceil(total/20));
  const current=Math.min(page,pages);const items=this.db.prepare('SELECT * FROM support_tickets'+where+' ORDER BY updated_at DESC,id DESC LIMIT 20 OFFSET ?').all(...values,(current-1)*20).map(row=>this.summary(row));
  return {items,page:current,pages,total};
 }
 detail(id:number,owner?:string):SupportDetail{
  const row=this.ticket(id,owner);if(!row)throw new SupportError(404,'Chamado não encontrado.');
  const events=this.db.prepare('SELECT id,role,body,status,created_at FROM support_events WHERE ticket_id=? ORDER BY id').all(id).map(event=>({id:Number(event.id),role:event.role as SupportEvent['role'],body:String(event.body),status:event.status as SupportStatus,createdAt:String(event.created_at)}));
  return {...this.summary(row),events};
 }
 create(owner:string,email:string,input:{kind:SupportKind;subject:string;body:string;requestKey:string}){
  const existing=this.db.prepare('SELECT * FROM support_tickets WHERE owner=? AND request_key=?').get(owner,input.requestKey);
  if(existing){const detail=this.detail(Number(existing.id),owner);if(detail.subject!==input.subject||detail.kind!==input.kind||detail.events[0]?.body!==input.body)throw new SupportError(409,'Esta solicitação já foi usada. Atualize a página antes de enviar outro chamado.');return detail;}
  if(Number(this.db.prepare("SELECT COUNT(*) n FROM support_tickets WHERE owner=? AND status<>'closed'").get(owner)!.n)>=100)throw new SupportError(429,'Há muitos chamados em andamento. Continue a conversa em um chamado existente.');
  this.db.exec('BEGIN IMMEDIATE');try{
   const now=new Date().toISOString();const id=Number(this.db.prepare("INSERT INTO support_tickets(owner,email,kind,subject,status,revision,created_at,updated_at,request_key) VALUES (?,?,?,?,'open',1,?,?,?)").run(owner,email,input.kind,input.subject,now,now,input.requestKey).lastInsertRowid);
   this.db.prepare("INSERT INTO support_events(ticket_id,actor,role,body,status,created_at,request_key) VALUES (?,?,'user',?,'open',?,?)").run(id,'user:'+owner,input.body,now,input.requestKey);this.db.exec('COMMIT');return this.detail(id,owner);
  }catch(error){this.db.exec('ROLLBACK');throw error;}
 }
 update(id:number,owner:string|undefined,actor:{key:string;role:'user'|'admin'},input:{body:string;status?:SupportStatus;expectedRevision:number;requestKey:string}){
  const row=this.ticket(id,owner);if(!row)throw new SupportError(404,'Chamado não encontrado.');
  const repeated=this.db.prepare('SELECT body,status FROM support_events WHERE ticket_id=? AND actor=? AND request_key=?').get(id,actor.key,input.requestKey);
  if(repeated){if(repeated.body!==input.body||(input.status&&repeated.status!==input.status))throw new SupportError(409,'Esta solicitação já foi usada. Atualize o chamado.');return this.detail(id,owner);}
  if(Number(row.revision)!==input.expectedRevision)throw new SupportError(409,'Este chamado recebeu uma atualização. Atualize a conversa antes de enviar; seu texto foi preservado.');
  const nextStatus=input.status??(actor.role==='user'?'open':'answered');
  if(!input.body&&nextStatus===row.status)throw new SupportError(400,'Escreva uma resposta ou escolha outro status.');
  if(Number(this.db.prepare('SELECT COUNT(*) n FROM support_events WHERE ticket_id=?').get(id)!.n)>=500)throw new SupportError(409,'Este chamado atingiu o limite de histórico. Abra outro chamado e informe este número.');
  this.db.exec('BEGIN IMMEDIATE');try{
   const now=new Date(Math.max(Date.now(),Date.parse(String(row.updated_at))+1)).toISOString();
   this.db.prepare('INSERT INTO support_events(ticket_id,actor,role,body,status,created_at,request_key) VALUES (?,?,?,?,?,?,?)').run(id,actor.key,actor.role,input.body,nextStatus,now,input.requestKey);
   const updated=this.db.prepare('UPDATE support_tickets SET status=?,revision=revision+1,updated_at=? WHERE id=? AND revision=?').run(nextStatus,now,id,input.expectedRevision);if(Number(updated.changes)!==1)throw new SupportError(409,'Este chamado recebeu uma atualização. Atualize a conversa antes de reenviar.');this.db.exec('COMMIT');return this.detail(id,owner);
  }catch(error){this.db.exec('ROLLBACK');throw error;}
 }
 close(){this.db.close();}
}
