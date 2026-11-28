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
type WooCategoryItem={id:number;name:string;parent:number};
export async function fetchWooCommerceCategories(fetcher:typeof fetch=fetch):Promise<string[]>{
 const items:WooCategoryItem[]=[];
 for(let page=1;page<=20;page++){
  const url=new URL('https://umdoislab.com.br/wp-json/wc/store/v1/products/categories');
  url.searchParams.set('hide_empty','false');url.searchParams.set('per_page','100');url.searchParams.set('page',String(page));
  const response=await fetcher(url,{headers:{Accept:'application/json'},signal:AbortSignal.timeout(12000)});
  if(!response.ok)throw Error(`WooCommerce respondeu HTTP ${response.status}.`);
  const batch=await response.json();
  if(!Array.isArray(batch))throw Error('A resposta de categorias WooCommerce não é uma lista.');
  for(const raw of batch){const id=Number(raw?.id),name=typeof raw?.name==='string'?raw.name.trim():'',parent=Number(raw?.parent??0);if(!Number.isInteger(id)||id<=0||!name||!Number.isInteger(parent)||parent<0)throw Error('A resposta WooCommerce contém uma categoria inválida.');items.push({id,name,parent});}
  if(items.length>500)throw Error('A loja retornou mais de 500 categorias; a importação foi interrompida para revisão.');
  const totalPages=Number(response.headers.get('X-WP-TotalPages')??0);
  if(batch.length===0||(totalPages>0?page>=totalPages:batch.length<100))break;
  if(page===20)throw Error('A paginação de categorias WooCommerce excedeu o limite de segurança.');
 }
 if(!items.length)throw Error('WooCommerce não retornou categorias.');
 const byId=new Map<number,WooCategoryItem>();
 for(const item of items){if(byId.has(item.id))throw Error('WooCommerce retornou IDs de categoria duplicados.');byId.set(item.id,item);}
 const cache=new Map<number,string>();
 const resolve=(id:number,trail:number[]=[]):string=>{
  if(cache.has(id))return cache.get(id)!;
  if(trail.includes(id))throw Error('A hierarquia de categorias WooCommerce contém um ciclo.');
  const item=byId.get(id);if(!item)throw Error('A hierarquia WooCommerce referencia uma categoria-pai ausente.');
  const path=item.parent?resolve(item.parent,[...trail,id])+' > '+item.name:item.name;
  if(path.length>200)throw Error('Uma categoria WooCommerce excede 200 caracteres.');
  cache.set(id,path);return path;
 };
 const paths=new Map<string,string>();
 for(const id of byId.keys()){const path=resolve(id),normalized=key(path),existing=paths.get(normalized);if(existing&&existing!==path)throw Error('WooCommerce possui categorias com nomes equivalentes que não podem ser distinguidos no Artesão.');paths.set(normalized,path);}
 return [...paths.values()];
}
export function registerCategories(app:FastifyInstance,db:DatabaseSync,fetcher:typeof fetch=fetch){

 const add=(path:string)=>storeCategory(db,path);
 const list=()=>db.prepare('SELECT id,path,reserved,revision FROM categories ORDER BY category_key').all();
 app.get('/api/categories',list);
 app.get('/api/categories/woocommerce',async(_req,reply)=>{try{return {type:'woocommerce-categories',source:'https://umdoislab.com.br/wp-json/wc/store/v1/products/categories?hide_empty=false',categories:await fetchWooCommerceCategories(fetcher)};}catch(error){return reply.code(502).send({message:'Não foi possível obter a árvore completa de categorias do WooCommerce. Nenhuma categoria foi gravada. '+(error instanceof Error?error.message:'Falha de comunicação.')});}});
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
