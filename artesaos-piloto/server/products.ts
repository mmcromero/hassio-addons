import {photoReferenceAllowed,PHOTO_REFERENCE_ERROR} from './product-photos.js';
import {protectStockOrigin,StockError} from './product-stock.js';
import {rememberMaterialUses} from './materials.js';
import {manufacturingSchema,type Production} from './manufacturing-model.js';
import {storeCategory} from './categories.js';
import {normalizedProduct as normalizeProduct,categoryAllowed} from './product-category.js';
import type { FastifyInstance } from 'fastify';
import type { DatabaseSync } from 'node:sqlite';

const money = {type:['integer','null'], minimum:0, maximum:10000000000};
const measure = {type:['number','null'], exclusiveMinimum:0, maximum:1000000};
export const productSchema = {type:'object', additionalProperties:false, required:['name','origin','publicAllowed','prices','weightGrams','lengthCm','widthCm','heightCm','colors','sourceKeys','family','description'], properties:{
  manufacturing:manufacturingSchema,name:{type:'string',minLength:1,maxLength:200,pattern:'\\S'}, origin:{enum:['own','client']}, publicAllowed:{type:'boolean'},catalogVisible:{type:'boolean'},
  prices:{type:'object',additionalProperties:false,required:['wholesale','factory','retail'],properties:{wholesale:money,factory:money,retail:money}},
  weightGrams:measure,lengthCm:measure,widthCm:measure,heightCm:measure,
  colors:{type:'array',maxItems:100,uniqueItems:true,items:{type:'string',maxLength:100}},
  sourceKeys:{type:'array',maxItems:200,uniqueItems:true,items:{type:'string',minLength:1,maxLength:250}},
  sku:{type:'string',maxLength:100},imageUrl:{type:'string',maxLength:2048,pattern:'^(https://[^\\s]+|api/product-photos/[a-f0-9]{32}/[a-f0-9]{64}\\.png|)$'},category:{type:'string',maxLength:200},sourceFamily:{type:'string',maxLength:250},family:{type:'string',maxLength:200},description:{type:'string',maxLength:20000}
}};
export type Product = {manufacturing?:Production;sku?:string;imageUrl?:string;category?:string;sourceFamily?:string;name:string;origin:'own'|'client';publicAllowed:boolean;catalogVisible?:boolean;prices:{wholesale:number|null;factory:number|null;retail:number|null};weightGrams:number|null;lengthCm:number|null;widthCm:number|null;heightCm:number|null;colors:string[];sourceKeys:string[];family:string;description:string};
function valid(p:Product) {return Object.values(p.prices).some(v=>v!==null) && categoryAllowed(p.origin,p.category) && !(p.origin==='client' && p.publicAllowed);}
export function registerProducts(app:FastifyInstance, db:DatabaseSync,pilotFeatures=false){
 const normalizedProduct=<T extends {origin:string;category?:string;catalogVisible?:boolean}>(product:T)=>normalizeProduct(product,pilotFeatures);

  const list=()=>db.prepare('SELECT id,data,updated_at FROM products WHERE archived=0 ORDER BY id DESC').all().map(r=>({id:r.id,...normalizedProduct(JSON.parse(r.data as string)),updatedAt:r.updated_at}));
  const add=(input:Product)=>{
    const p=normalizedProduct(input);
    rememberMaterialUses(db,p.manufacturing);
    if(p.origin==='own'&&p.category)storeCategory(db,p.category);
    const id=Number(db.prepare('INSERT INTO products(data,updated_at) VALUES (?,?)').run(JSON.stringify(p),new Date().toISOString()).lastInsertRowid);
    for(const key of p.sourceKeys) db.prepare('INSERT INTO product_sources VALUES (?,?)').run(key,id);
    return id;
  };
  app.get('/api/products',list);
  app.post<{Body:Product}>('/api/products',{bodyLimit:65536,schema:{body:productSchema}},(req,reply)=>{
    if(!categoryAllowed(req.body.origin,req.body.category))return reply.code(400).send({message:'Produtos de cliente é uma categoria reservada. Para produto próprio, escolha outra categoria ou deixe em branco.'});
    if(!valid(req.body)) return reply.code(400).send({message:'Informe pelo menos um preço. Produto de cliente deve permanecer privado.'});
    if(pilotFeatures&&!photoReferenceAllowed(db,req.body.imageUrl))return reply.code(400).send({message:PHOTO_REFERENCE_ERROR});
    if(req.body.sourceKeys.length) return reply.code(400).send({message:'Vínculos externos são reservados à importação.'});
    return {id:add(req.body)};
  });
  app.put<{Params:{id:string};Body:Product}>('/api/products/:id',{bodyLimit:65536,schema:{body:productSchema}},(req,reply)=>{
    const row=db.prepare('SELECT data,updated_at FROM products WHERE id=? AND archived=0').get(req.params.id);
    if(!row) return reply.code(404).send({message:'Produto não encontrado.'});
    if(req.headers['x-expected-updated-at']&&req.headers['x-expected-updated-at']!==row.updated_at)return reply.code(409).send({message:'Este produto mudou em outra janela. Preserve sua edição e reabra o cadastro antes de salvar.'});
    if(!categoryAllowed(req.body.origin,req.body.category))return reply.code(400).send({message:'Produtos de cliente é uma categoria reservada. Para produto próprio, escolha outra categoria ou deixe em branco.'});
    if(pilotFeatures){try{protectStockOrigin(db,Number(req.params.id),req.body.origin);}catch(e){return reply.code(e instanceof StockError?e.status:400).send({message:(e as Error).message});}}
    const old=JSON.parse(row.data as string) as Product;
    if(pilotFeatures&&!photoReferenceAllowed(db,req.body.imageUrl,old.imageUrl))return reply.code(400).send({message:PHOTO_REFERENCE_ERROR});
    if(!valid(req.body)||JSON.stringify(old.sourceKeys)!==JSON.stringify(req.body.sourceKeys)) return reply.code(400).send({message:'Confira os preços, a privacidade e os vínculos externos.'});
    if(req.body.origin==='own'&&req.body.category)storeCategory(db,req.body.category);
    rememberMaterialUses(db,req.body.manufacturing);
    db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(normalizedProduct({...req.body,...(req.body.imageUrl===undefined?{imageUrl:old.imageUrl}:{}),catalogVisible:req.body.catalogVisible??old.catalogVisible??false})),new Date(Math.max(Date.now(),(Date.parse(String(row.updated_at))||0)+1)).toISOString(),req.params.id);
    return {ok:true};
  });
  app.delete<{Params:{id:string}}>('/api/products/:id',(req,reply)=>{
    const result=db.prepare('UPDATE products SET archived=1 WHERE id=? AND archived=0').run(req.params.id);
    return result.changes?{ok:true}:reply.code(404).send({message:'Produto não encontrado.'});
  });
  app.post<{Body:{products:Product[];confirm:boolean;fillMissing?:boolean}}>('/api/products/import',{bodyLimit:1024*1024,schema:{body:{type:'object',additionalProperties:false,required:['products','confirm'],properties:{fillMissing:{type:'boolean'},confirm:{type:'boolean'},products:{type:'array',minItems:1,maxItems:500,items:productSchema}}}}},(req,reply)=>{
    const seen=new Set<string>();
    const pending:Product[]=[];const updates:{id:number;data:Product}[]=[];let skipped=0;
    for(const input of req.body.products){
      const p=normalizedProduct(input);
      if(!valid(p)||!p.sourceKeys.length) return reply.code(400).send({message:'Carga inválida: confira preços, origem e identificadores.'});
      const matches=new Set<number>();
      for(const key of p.sourceKeys){
        if(seen.has(key)) return reply.code(400).send({message:'Identificador repetido dentro do arquivo.'});
        seen.add(key);
        const row=db.prepare('SELECT product_id FROM product_sources WHERE source_key=?').get(key);
        if(row)matches.add(Number(row.product_id));
      }
      if(matches.size>1) return reply.code(409).send({message:'Vínculos conflitantes. Nenhum produto foi importado.'});
      if(matches.size){
        const linked=db.prepare('SELECT source_key FROM product_sources WHERE product_id=?').all([...matches][0]).map(r=>r.source_key as string);
        // Excel reconciliation adds a separate source; it must not change WooCommerce variation grouping.
        const existing=p.sourceKeys.some(key=>key.startsWith('excel:'))?linked:linked.filter(key=>!key.startsWith('excel:'));
        if(existing.length!==p.sourceKeys.length || existing.some(k=>!p.sourceKeys.includes(k))) return reply.code(409).send({message:'O agrupamento das variações mudou. Revise antes de importar; nenhum produto foi gravado.'});
        const id=[...matches][0];
        const row=db.prepare('SELECT data,archived FROM products WHERE id=?').get(id)!;
        const stored=JSON.parse(row.data as string) as Product;
        if(pilotFeatures&&!photoReferenceAllowed(db,p.imageUrl,stored.imageUrl))return reply.code(400).send({message:PHOTO_REFERENCE_ERROR});
        let changed=false;
        if(req.body.fillMissing && !row.archived){
          if(!stored.sku?.trim() && p.sku?.trim()){stored.sku=p.sku;changed=true;}
          if(!stored.description.trim() && p.description.trim()){stored.description=p.description;changed=true;}
          if(!stored.imageUrl?.trim() && p.imageUrl?.trim()){stored.imageUrl=p.imageUrl;changed=true;}
        }
        if(changed)updates.push({id,data:stored});else skipped++;
      }else {
        const normalized=(value:string)=>value.trim().normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase();
        const duplicates=[...db.prepare('SELECT data FROM products').all().map(row=>JSON.parse(row.data as string) as Product),...pending];
        if(duplicates.some(old=>(p.sku?.trim()&&old.sku?.trim()&&normalized(p.sku)===normalized(old.sku))||(p.origin===old.origin&&normalized(p.name)===normalized(old.name))))return reply.code(409).send({message:'Possível duplicata por nome ou SKU com vínculos diferentes. Revise a conciliação; nenhum produto foi importado.'});
        if(pilotFeatures&&!photoReferenceAllowed(db,p.imageUrl))return reply.code(400).send({message:PHOTO_REFERENCE_ERROR});
        pending.push(p);
      }
    }
    if(req.body.confirm){
      db.exec('BEGIN IMMEDIATE');
      try{for(const p of pending)add(p);for(const update of updates)db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(update.data),new Date().toISOString(),update.id);db.exec('COMMIT');}catch(e){db.exec('ROLLBACK');throw e;}
    }
    return {updated:req.body.confirm?updates.length:0,toUpdate:updates.length,created:req.body.confirm?pending.length:0,toCreate:pending.length,skipped,confirmed:req.body.confirm};
  });
}
