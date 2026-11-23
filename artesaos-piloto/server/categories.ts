import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {CLIENT_CATEGORY} from './product-category.js';
const key=(path:string)=>path.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('pt-BR');
const clean=(path:string)=>path.split('>').map(part=>part.trim()).join(' > ');
const valid=(path:string)=>path.length<=200&&path.split('>').every(part=>part.trim())&&key(path.split('>')[0].trim())!==key(CLIENT_CATEGORY);
export function storeCategory(db:DatabaseSync,path:string){
 if(!path.trim())return;let parent='';
 for(const part of clean(path).split(' > ')){
  const value=parent?parent+' > '+part:part;
  db.prepare('INSERT OR IGNORE INTO categories(path,category_key) VALUES (?,?)').run(value,key(value));
  parent=String(db.prepare('SELECT path FROM categories WHERE category_key=?').get(key(value))!.path);
 }
}
export function registerCategories(app:FastifyInstance,db:DatabaseSync){

 const add=(path:string)=>storeCategory(db,path);
 const list=()=>db.prepare('SELECT id,path,reserved,revision FROM categories ORDER BY category_key').all();
 app.get('/api/categories',list);
 const body={type:'object',additionalProperties:false,required:['path'],properties:{path:{type:'string',minLength:1,maxLength:200},expectedRevision:{type:'integer',minimum:1}}};
 app.post<{Body:{path:string}}>('/api/categories',{schema:{body}},(req,reply)=>{
  const path=clean(req.body.path);if(!valid(path))return reply.code(400).send({message:'Informe uma categoria válida. Produtos de cliente é reservada.'});
  if(db.prepare('SELECT id FROM categories WHERE category_key=?').get(key(path)))return reply.code(409).send({message:'Esta categoria já está cadastrada.'});
  db.exec('BEGIN IMMEDIATE');try{add(path);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}return {categories:list()};
 });
 app.put<{Params:{id:string};Body:{path:string;expectedRevision?:number}}>('/api/categories/:id',{schema:{body}},(req,reply)=>{
  const row=db.prepare('SELECT * FROM categories WHERE id=?').get(req.params.id);
  if(!row)return reply.code(404).send({message:'Categoria não encontrada.'});
  if(row.reserved)return reply.code(400).send({message:'Produtos de cliente é uma categoria reservada e não pode ser editada.'});
  if(row.revision!==req.body.expectedRevision)return reply.code(409).send({message:'A categoria mudou em outra janela. Recarregue antes de editar.'});
  const path=clean(req.body.path),old=row.path as string;
  if(!valid(path)||key(path).startsWith(key(old)+' > '))return reply.code(400).send({message:'Categoria inválida ou movida para dentro de si mesma.'});
  const changes=list().filter(c=>key(String(c.path))===key(old)||key(String(c.path)).startsWith(key(old)+' > ')).map(c=>({id:Number(c.id),path:String(c.path),next:path+(c.path as string).slice(old.length)}));
  if(changes.some(c=>c.next.length>200||list().some(other=>!changes.some(ch=>ch.id===other.id)&&key(other.path as string)===key(c.next))))return reply.code(409).send({message:'A alteração conflita com outra categoria ou excede 200 caracteres. Nada foi alterado.'});
  db.exec('BEGIN IMMEDIATE');try{
   // Temporary unique keys allow case-only changes and moving a hierarchy atomically.
   for(const c of changes)db.prepare('UPDATE categories SET category_key=? WHERE id=?').run(`__moving_${c.id}`,c.id);
   for(const c of changes)db.prepare('UPDATE categories SET path=?,category_key=?,revision=revision+1 WHERE id=?').run(c.next,key(c.next),c.id);
   add(path);
   for(const product of db.prepare("SELECT id,data,updated_at FROM products WHERE json_extract(data,'$.origin')='own'").all()){
    const data=JSON.parse(product.data as string);const match=changes.find(c=>key(c.path as string)===key(clean(data.category??'')));
    if(match){data.category=match.next;db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(data),new Date(Math.max(Date.now(),(Date.parse(String(product.updated_at))||0)+1)).toISOString(),product.id);}
   }
   db.exec('COMMIT');
  }catch(e){db.exec('ROLLBACK');throw e;}return {categories:list()};
 });
 app.post<{Body:{categories:string[];confirm:boolean}}>('/api/categories/import',{bodyLimit:1024*1024,schema:{body:{type:'object',additionalProperties:false,required:['categories','confirm'],properties:{confirm:{type:'boolean'},categories:{type:'array',minItems:1,maxItems:500,items:{type:'string',minLength:1,maxLength:200}}}}}},(req,reply)=>{
  const paths=new Map<string,string>();
  for(const raw of req.body.categories){const path=clean(raw);if(!valid(path))return reply.code(400).send({message:'Categoria inválida ou reservada no arquivo. Nenhum dado foi gravado.'});const parts=path.split(' > ');for(let i=1;i<=parts.length;i++){const value=parts.slice(0,i).join(' > ');paths.set(key(value),value);}}
  const existing=list(),create=[...paths].filter(([k])=>!existing.some(c=>key(c.path as string)===k)).map(([,p])=>p);
  if(req.body.confirm){db.exec('BEGIN IMMEDIATE');try{for(const path of create)add(path);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}}
  return {type:'categories',toCreate:create.length,skipped:paths.size-create.length,paths:create,created:req.body.confirm?create.length:0,confirmed:req.body.confirm};
 });
}
