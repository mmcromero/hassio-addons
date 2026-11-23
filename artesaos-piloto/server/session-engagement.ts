import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import {transaction} from './foundation/transaction.js';
export class SessionEngagement{
 constructor(readonly db:DatabaseSync,readonly actor:string){}
 summary(id:string){const session=this.db.prepare('SELECT id,place_id,financial_closed_at FROM sales_sessions WHERE id=?').get(id);if(!session)throw Error('Sessão não encontrada.');
  const total=Number(this.db.prepare('SELECT COALESCE(SUM(delta),0) n FROM visitor_events WHERE session_id=?').get(id)!.n);
  const sales=Number(this.db.prepare('SELECT COUNT(*) n FROM sales WHERE session_id=?').get(id)!.n);
  const clients=this.db.prepare('SELECT id,data,commercial_type,created_at FROM clients WHERE capture_session_id=? ORDER BY id').all(id).map((r:any)=>({id:r.id,name:JSON.parse(r.data).name||JSON.parse(r.data).contact,commercialType:r.commercial_type,createdAt:r.created_at}));
  return {sessionId:id,placeId:session.place_id,total,sales,conversion:total?sales/total*100:null,estimated:true,expanded:!!this.db.prepare('SELECT expanded FROM visitor_preferences WHERE session_id=? AND actor=?').get(id,this.actor)?.expanded,newContacts:clients.length,clients};
 }
 change(id:string,delta:unknown,key:unknown){if(![-1,1].includes(delta as number)||typeof key!=='string'||!/^[a-zA-Z0-9-]{16,100}$/.test(key))throw Error('Incremento ou identificador inválido.');
  return transaction(this.db,()=>{const old=this.db.prepare('SELECT delta FROM visitor_events WHERE session_id=? AND request_key=?').get(id,key);if(old){if(old.delta!==delta)throw Error('Reenvio divergente.');return this.summary(id);}
   const s=this.summary(id);if(!Number.isSafeInteger(s.total+(delta as number)))throw Error('Limite de contagem.');if(s.total+(delta as number)<0)throw Error('O contador não pode ficar negativo.');
   this.db.prepare('INSERT INTO visitor_events(session_id,request_key,delta,total_after,actor,created_at) VALUES(?,?,?,?,?,?)').run(id,key,delta as number,s.total+(delta as number),this.actor,new Date().toISOString());return this.summary(id);
  });
 }
 preference(id:string,expanded:unknown){if(typeof expanded!=='boolean')throw Error('Preferência inválida.');this.summary(id);this.db.prepare('INSERT INTO visitor_preferences VALUES(?,?,?) ON CONFLICT(session_id,actor) DO UPDATE SET expanded=excluded.expanded').run(id,this.actor,expanded?1:0);return this.summary(id);}
}
export function registerSessionEngagement(app:FastifyInstance,db:DatabaseSync,actor:string){const e=new SessionEngagement(db,actor);const run=(f:(req:any)=>unknown)=>(req:any,reply:any)=>{try{return f(req);}catch(error){return reply.code(400).send({message:error instanceof Error?error.message:'Operação inválida.'});}};
 app.get('/api/sales-sessions/:id/engagement',run(req=>e.summary(req.params.id)));
 app.post('/api/sales-sessions/:id/visitors',run(req=>e.change(req.params.id,req.body?.delta,req.body?.requestKey)));
 app.put('/api/sales-sessions/:id/visitor-preference',run(req=>e.preference(req.params.id,req.body?.expanded)));
}
