import {photoReferenceAllowed,PHOTO_REFERENCE_ERROR} from './product-photos.js';
import {ProductStock,protectStockOrigin,StockError} from './product-stock.js';
import {currentProduction} from './material-current-cost.js';
import {rememberMaterialUses} from './materials.js';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {productSchema,type Product} from './products.js';
import {calculateManufacturing} from './manufacturing-model.js';
import {normalizedProduct as normalizeProduct,categoryAllowed} from './product-category.js';
import {storeCategory} from './categories.js';
export function registerProductEditor(app:FastifyInstance,db:DatabaseSync,pilotFeatures=false,actor='local-development'){
 const normalizedProduct=<T extends {origin:string;category?:string;catalogVisible?:boolean}>(product:T)=>normalizeProduct(product,pilotFeatures);
 const schema={type:'object',additionalProperties:false,required:['product','applyPrices'],properties:{updateStockTiers:{type:'array',maxItems:3,uniqueItems:true,items:{enum:['wholesale','factory','retail']}},expectedMaterialPurchaseId:{type:'integer',minimum:0},product:productSchema,applyPrices:{type:'boolean'},applyTiers:{type:'array',maxItems:3,uniqueItems:true,items:{enum:['wholesale','factory','retail']}},expectedUpdatedAt:{type:'string'},expectedSettingsRevision:{type:'integer',minimum:0}}};
 type Body={updateStockTiers?:('wholesale'|'factory'|'retail')[];expectedMaterialPurchaseId?:number;product:Product;applyPrices:boolean;applyTiers?:('wholesale'|'factory'|'retail')[];expectedUpdatedAt?:string;expectedSettingsRevision?:number};
 async function save(req:{body:Body;params?:{id:string}},reply:any){
  const id=req.params?.id;const row=id?db.prepare('SELECT data,updated_at FROM products WHERE id=? AND archived=0').get(id):undefined;
  if(id&&!row)return reply.code(404).send({message:'Produto não encontrado ou arquivado.'});
  if(row&&(!req.body.expectedUpdatedAt||row.updated_at!==req.body.expectedUpdatedAt))return reply.code(409).send({message:'O produto mudou. Reabra o cadastro antes de salvar.'});
  const old=row?JSON.parse(String(row.data)) as Product:undefined;
  if(pilotFeatures&&!photoReferenceAllowed(db,req.body.product.imageUrl,old?.imageUrl))return reply.code(400).send({message:PHOTO_REFERENCE_ERROR});
  const p=normalizedProduct({...req.body.product,...(req.body.product.imageUrl===undefined?{imageUrl:old?.imageUrl}:{}),catalogVisible:req.body.product.catalogVisible??old?.catalogVisible??false});
  if(pilotFeatures&&id){try{protectStockOrigin(db,Number(id),p.origin);}catch(e){return reply.code(e instanceof StockError?e.status:400).send({message:(e as Error).message});}}
  if(!categoryAllowed(p.origin,p.category))return reply.code(400).send({message:'A categoria Produtos de cliente é reservada a produtos de cliente.'});
  if(JSON.stringify(p.sourceKeys)!==JSON.stringify(old?.sourceKeys??[]))return reply.code(400).send({message:'Vínculos de importação devem ser preservados.'});
  const applied=req.body.applyPrices?['wholesale','factory','retail'] as const:req.body.applyTiers??[];
  const stockTiers=req.body.updateStockTiers??[];
  if(stockTiers.length&&(!pilotFeatures||p.origin!=='own'||stockTiers.some(t=>!applied.includes(t))))return reply.code(400).send({message:'Atualize no Estoque somente faixas calculadas escolhidas explicitamente.'});
  if(applied.length){
   const config=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
   if(req.body.expectedSettingsRevision!==Number(config?.revision??0))return reply.code(409).send({message:'As configurações mudaram. Reabra o formulário e revise os preços.'});
   if(!p.manufacturing)return reply.code(400).send({message:'Informe os dados de fabricação.'});
   const costRevision=pilotFeatures?Number(db.prepare('SELECT COALESCE(MAX(id),0) n FROM material_purchases').get()!.n):0;
   if(costRevision&&req.body.expectedMaterialPurchaseId!==costRevision)return reply.code(409).send({message:'Compras alteraram custos. Reabra o produto para revisar a sugestão.'});
   const result=calculateManufacturing(pilotFeatures?currentProduction(db,p.manufacturing):p.manufacturing,config?JSON.parse(String(config.data)):{},pilotFeatures);
   if(!result.prices)return reply.code(400).send({message:'Complete os dados e configurações antes de aplicar preços.'});
   for(const key of applied)p.prices[key]=result.prices[key];
  }
  if(!Object.values(p.prices).some(v=>v!==null))return reply.code(400).send({message:'Informe pelo menos um preço ou aplique os preços calculados.'});
  db.exec('BEGIN IMMEDIATE');try{
   rememberMaterialUses(db,p.manufacturing);
   if(p.origin==='own'&&p.category)storeCategory(db,p.category);
   const now=new Date(Math.max(Date.now(),row?Date.parse(String(row.updated_at))+1:0)).toISOString();
   const savedId=id?Number(id):Number(db.prepare('INSERT INTO products(data,updated_at) VALUES (?,?)').run(JSON.stringify(p),now).lastInsertRowid);
   if(id)db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(p),now,id);
   if(stockTiers.length){const item=db.prepare("SELECT id,prices FROM stock_items WHERE product_id=? AND kind='own'").get(savedId);if(item){const next=JSON.parse(String(item.prices));for(const t of stockTiers)next[t]=p.prices[t];new ProductStock(db,actor).writePrices(String(item.id),next,'Aplicação explícita de preços calculados do Produto');}}
   db.exec('COMMIT');return {id:savedId,...p,updatedAt:now};
  }catch(e){db.exec('ROLLBACK');throw e;}
 }
 app.post<{Body:Body}>('/api/products/editor',{bodyLimit:65536,schema:{body:schema}},(req,reply)=>save({body:req.body},reply));
 app.put<{Body:Body;Params:{id:string}}>('/api/products/:id/editor',{bodyLimit:65536,schema:{body:schema}},save);
}
