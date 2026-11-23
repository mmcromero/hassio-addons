import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {optimizedPng} from '../product-photos.js';
export function registerCompanyLogo(app:FastifyInstance,db:DatabaseSync){
 db.exec('PRAGMA secure_delete=ON;');

 const current=()=>db.prepare('SELECT image,revision FROM company_logo WHERE id=1').get();
 app.get('/api/company/logo/meta',()=>{const row=current();return {present:!!row?.image,revision:Number(row?.revision??0)};});
 app.get('/api/company/logo',(_req,reply)=>{const row=current();return row?.image?reply.type('image/png').send(Buffer.from(row.image as Uint8Array)):reply.code(404).send({message:'Sem logo.'});});
 const schema={type:'object',additionalProperties:false,required:['expectedRevision'],properties:{expectedRevision:{type:'integer',minimum:0},png:{type:'string',maxLength:683000}}};
 for(const method of ['PUT','DELETE'] as const)app.route<{Body:{expectedRevision:number;png?:string}}>({method,url:'/api/company/logo',bodyLimit:700000,schema:{body:schema},handler:(req,reply)=>{
  const revision=Number(current()?.revision??0);
  if(revision!==req.body.expectedRevision)return reply.code(409).send({message:'A logo mudou em outra janela. Atualize a página antes de tentar novamente.'});
  let image:Buffer|null=null;
  if(method==='PUT'){
   try{
    image=optimizedPng(req.body.png??'').png;
   }catch{return reply.code(400).send({message:'Use uma logo PNG válida de até 1024 × 1024 pixels e 500 KB após otimização.'});}
  }
  db.prepare('INSERT INTO company_logo(id,image,revision) VALUES(1,?,?) ON CONFLICT(id) DO UPDATE SET image=excluded.image,revision=excluded.revision').run(image,revision+1);
  return {present:!!image,revision:revision+1};
 }});
}
