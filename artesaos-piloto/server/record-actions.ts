import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {normalizedProduct as normalizeProduct} from './product-category.js';
export function registerRecordActions(app:FastifyInstance,db:DatabaseSync,pilotFeatures=false){
 const normalizedProduct=<T extends {origin:string;category?:string;catalogVisible?:boolean}>(product:T)=>normalizeProduct(product,pilotFeatures);
 const kind={enum:['products','clients','quotes']};
 app.get<{Params:{kind:string}}>('/api/records/:kind/archived',{schema:{params:{type:'object',required:['kind'],properties:{kind}}}},req=>db.prepare(`SELECT id,data,updated_at FROM ${req.params.kind} WHERE archived=1 ORDER BY id DESC`).all().map(row=>{const data=JSON.parse(String(row.data));return {id:row.id,name:data.name||data.contact||data.title||`Orçamento ${row.id}`,updatedAt:row.updated_at};}));
 type Body={action:'archive'|'restore'|'public'|'private'|'catalog_include'|'catalog_remove';records:{id:number;updatedAt:string}[];confirm:boolean};
 app.post<{Params:{kind:string};Body:Body}>('/api/records/:kind/actions',{bodyLimit:2*1024*1024,schema:{params:{type:'object',required:['kind'],properties:{kind}},body:{type:'object',additionalProperties:false,required:['action','records','confirm'],properties:{action:{enum:['archive','restore','public','private','catalog_include','catalog_remove']},confirm:{type:'boolean'},records:{type:'array',minItems:1,maxItems:10000,items:{type:'object',additionalProperties:false,required:['id','updatedAt'],properties:{id:{type:'integer',minimum:1},updatedAt:{type:'string',maxLength:100}}}}}}}},(req,reply)=>{
  const {action,records,confirm}=req.body;const table=req.params.kind;
  const catalogAction=action==='catalog_include'||action==='catalog_remove';
  const productAction=action==='public'||action==='private'||catalogAction;
  if(productAction&&table!=='products')return reply.code(400).send({message:'Esta ação é exclusiva de produtos.'});
  if(new Set(records.map(r=>r.id)).size!==records.length)return reply.code(400).send({message:'Seleção repetida.'});
  const planned=[];let skipped=0;
  for(const selected of records){
   const row=db.prepare(`SELECT * FROM ${table} WHERE id=?`).get(selected.id);
   if(!row||row.updated_at!==selected.updatedAt||Number(row.archived)!==(action==='restore'?1:0))return reply.code(409).send({message:'A seleção mudou em outra janela. Atualize a lista e revise novamente. Nada foi alterado.'});
   const data=JSON.parse(String(row.data));
   if((action==='public'||(pilotFeatures&&action==='catalog_include'))&&data.origin==='client'){skipped++;continue;}
   if(action==='public'||action==='private'){data.publicAllowed=action==='public';if(data.publicAllowed===JSON.parse(String(row.data)).publicAllowed){skipped++;continue;}}
   if(catalogAction){const included=action==='catalog_include';if(Boolean(data.catalogVisible)===included){skipped++;continue;}data.catalogVisible=included;}
   planned.push({id:selected.id,data:table==='products'?normalizedProduct(data):data,updatedAt:new Date(Math.max(Date.now(),Date.parse(String(row.updated_at))+1)).toISOString()});
  }
  if(confirm){db.exec('BEGIN IMMEDIATE');try{for(const row of planned){
   if(productAction)db.prepare(`UPDATE ${table} SET data=?,updated_at=? WHERE id=?`).run(JSON.stringify(row.data),row.updatedAt,row.id);
   else db.prepare(`UPDATE ${table} SET archived=?,updated_at=?${table==='quotes'?',revision=revision+1':''} WHERE id=?`).run(action==='archive'?1:0,row.updatedAt,row.id);
  }db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}}
  return {affected:planned.length,skipped,confirmed:confirm};
 });
}
