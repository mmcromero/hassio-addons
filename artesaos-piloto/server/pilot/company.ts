import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {normalizePixKey,validPixKey} from './pix.js';
type Company={name:string;responsible:string;phone:string;email:string;pixKey?:string};
const empty:Company={name:'',responsible:'',phone:'',email:''};
export function registerCompany(app:FastifyInstance,db:DatabaseSync){
 // Registered only by the pilot in each authenticated user's own database.
 app.get('/api/company',()=>{const row=db.prepare('SELECT data,revision FROM company_profile WHERE id=1').get();return row?{data:JSON.parse(String(row.data)),revision:Number(row.revision)}:{data:empty,revision:0};});
 app.put<{Body:{data:Company;expectedRevision:number}}>('/api/company',{bodyLimit:4096,schema:{body:{type:'object',additionalProperties:false,required:['data','expectedRevision'],properties:{expectedRevision:{type:'integer',minimum:0},data:{type:'object',additionalProperties:false,required:['name','responsible','phone','email'],properties:{name:{type:'string',maxLength:200},responsible:{type:'string',maxLength:200},phone:{type:'string',maxLength:40},email:{type:'string',maxLength:254},pixKey:{type:'string',maxLength:254}}}}}}},(req,reply)=>{
  const current=db.prepare('SELECT data,revision FROM company_profile WHERE id=1').get();
  const previous=current?JSON.parse(String(current.data)):empty;
  const data={...previous,...Object.fromEntries(Object.entries(req.body.data).map(([key,value])=>[key,value.trim()]))} as Company;
  if(!data.responsible||!data.phone)return reply.code(400).send({message:'Preencha seu nome e telefone.'});
  if(Object.values(data).some(value=>/[\u0000-\u001f\u007f]/.test(value)))return reply.code(400).send({message:'Os dados da empresa não podem conter caracteres de controle.'});
  if(data.email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.email))return reply.code(400).send({message:'Informe um e-mail válido.',field:'email'});
  if(!/^[\d+().\s-]+$/.test(data.phone)||data.phone.replace(/\D/g,'').length<7)return reply.code(400).send({message:'Informe um telefone válido com DDD.',field:'phone'});
  if(data.pixKey){data.pixKey=normalizePixKey(data.pixKey);if(!validPixKey(data.pixKey))return reply.code(400).send({message:'Informe uma chave Pix válida.',field:'pixKey'});}
  if(req.body.expectedRevision!==Number(current?.revision??0))return reply.code(409).send({message:'Os dados da empresa foram alterados em outra janela. Reabra a página antes de salvar.'});
  const revision=Number(current?.revision??0)+1;
  db.prepare('INSERT INTO company_profile(id,data,revision) VALUES (1,?,?) ON CONFLICT(id) DO UPDATE SET data=excluded.data,revision=excluded.revision').run(JSON.stringify(data),revision);
  return {revision};
 });
}
