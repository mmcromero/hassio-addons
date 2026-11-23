import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';

import {clientSchema as schema,normalizeClient,type ClientDraft} from './client-data.js';

export function registerClients(app:FastifyInstance,db:DatabaseSync,evolution=false){

  app.get('/api/clients',()=>db.prepare('SELECT * FROM clients WHERE archived=0 ORDER BY id DESC').all().map(row=>({id:row.id,...normalizeClient(JSON.parse(row.data as string)),updatedAt:row.updated_at,...(evolution?{commercialType:row.commercial_type,registrationOrigin:row.registration_origin,captureSessionId:row.capture_session_id,createdAt:row.created_at}:{})})));
  app.post<{Body:ClientDraft}>('/api/clients',{bodyLimit:8192,schema:{body:schema}},(req,reply)=>{
    const data=normalizeClient(req.body);
    if(evolution){const session=data.captureSessionId??null;if(session&&!db.prepare('SELECT id FROM sales_sessions WHERE id=? AND financial_closed_at IS NULL').get(session))return reply.code(400).send({message:'Sessão de captação inexistente ou encerrada.'});if(session&&data.registrationOrigin!=='sale')return reply.code(400).send({message:'Sessão de captação exige origem Venda.'});const now=new Date().toISOString();const r=db.prepare('INSERT INTO clients(data,updated_at,commercial_type,registration_origin,capture_session_id,created_at) VALUES(?,?,?,?,?,?)').run(JSON.stringify(data),now,data.commercialType??'retail',data.registrationOrigin??'direct',session,now);return {id:Number(r.lastInsertRowid)};}
    const result=db.prepare('INSERT INTO clients(data,updated_at) VALUES (?,?)').run(JSON.stringify(data),new Date().toISOString());
    return {id:Number(result.lastInsertRowid)};
  });
  app.put<{Params:{id:string};Body:ClientDraft}>('/api/clients/:id',{bodyLimit:8192,schema:{body:schema}},(req,reply)=>{
    if(evolution){const r=db.prepare('UPDATE clients SET data=?,updated_at=?,commercial_type=COALESCE(?,commercial_type) WHERE id=? AND archived=0').run(JSON.stringify(normalizeClient(req.body)),new Date().toISOString(),req.body.commercialType??null,req.params.id);return r.changes?{ok:true}:reply.code(404).send({message:'Cliente não encontrado.'});}
    const result=db.prepare('UPDATE clients SET data=?,updated_at=? WHERE id=? AND archived=0').run(JSON.stringify(normalizeClient(req.body)),new Date().toISOString(),req.params.id);
    return result.changes?{ok:true}:reply.code(404).send({message:'Cliente não encontrado.'});
  });
  app.delete<{Params:{id:string}}>('/api/clients/:id',(req,reply)=>{
    const result=db.prepare('UPDATE clients SET archived=1 WHERE id=? AND archived=0').run(req.params.id);
    return result.changes?{ok:true}:reply.code(404).send({message:'Cliente não encontrado.'});
  });
}
