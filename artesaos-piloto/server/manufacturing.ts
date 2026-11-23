import {currentProduction} from './material-current-cost.js';
import {rememberMaterialUses} from './materials.js';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {calculateManufacturing,manufacturingSchema,type Production} from './manufacturing-model.js';
import {normalizedProduct as normalizeProduct,categoryAllowed} from './product-category.js';
import {storeCategory} from './categories.js';
export function registerManufacturing(app:FastifyInstance,db:DatabaseSync,pilotFeatures=false){
 const normalizedProduct=<T extends {origin:string;category?:string;catalogVisible?:boolean}>(product:T)=>normalizeProduct(product,pilotFeatures);
 app.post<{Body:{name:string;sku:string;category:string;origin:'own'|'client';manufacturing:Production;applyPrices:boolean;expectedSettingsRevision:number}}>('/api/manufacturing/products',{bodyLimit:65536,schema:{body:{type:'object',additionalProperties:false,required:['name','sku','category','origin','manufacturing','applyPrices','expectedSettingsRevision'],properties:{name:{type:'string',minLength:1,maxLength:200,pattern:'\\S'},sku:{type:'string',maxLength:100},category:{type:'string',maxLength:200},origin:{enum:['own','client']},manufacturing:manufacturingSchema,applyPrices:{const:true},expectedSettingsRevision:{type:'integer',minimum:0}}}}},(req,reply)=>{
  const config=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
  if(Number(config?.revision??0)!==req.body.expectedSettingsRevision)return reply.code(409).send({message:'As configurações mudaram. Recarregue e revise os preços antes de criar o produto.'});
  if(!categoryAllowed(req.body.origin,req.body.category))return reply.code(400).send({message:'Produtos de cliente é reservada à origem de cliente. Escolha outra categoria ou deixe em branco.'});
  const result=calculateManufacturing(pilotFeatures?currentProduction(db,req.body.manufacturing):req.body.manufacturing,config?JSON.parse(config.data as string):{},pilotFeatures);
  if(!result.prices)return reply.code(400).send({message:'Complete os dados e configurações para criar um produto com preços calculados.'});
  const data=normalizedProduct({name:req.body.name.trim(),sku:req.body.sku.trim(),category:req.body.category,origin:req.body.origin,manufacturing:req.body.manufacturing,publicAllowed:false,prices:result.prices,weightGrams:null,lengthCm:null,widthCm:null,heightCm:null,colors:[],sourceKeys:[],family:'',description:''});
  db.exec('BEGIN IMMEDIATE');try{
   rememberMaterialUses(db,data.manufacturing);
   if(data.origin==='own'&&data.category)storeCategory(db,data.category);
   const id=Number(db.prepare('INSERT INTO products(data,updated_at) VALUES (?,?)').run(JSON.stringify(data),new Date().toISOString()).lastInsertRowid);db.exec('COMMIT');return {id};
  }catch(e){db.exec('ROLLBACK');throw e;}
 });

 app.put<{Params:{id:string};Body:{name:string;sku:string;category:string;manufacturing:Production;applyPrices:boolean;expectedUpdatedAt:string;expectedSettingsRevision:number}}>('/api/products/:id/manufacturing',{bodyLimit:65536,schema:{body:{type:'object',additionalProperties:false,required:['name','sku','category','manufacturing','applyPrices','expectedUpdatedAt','expectedSettingsRevision'],properties:{name:{type:'string',minLength:1,maxLength:200,pattern:'\\S'},sku:{type:'string',maxLength:100},category:{type:'string',maxLength:200},manufacturing:manufacturingSchema,applyPrices:{type:'boolean'},expectedUpdatedAt:{type:'string'},expectedSettingsRevision:{type:'integer',minimum:0}}}}},(req,reply)=>{
  const row=db.prepare('SELECT data,updated_at FROM products WHERE id=? AND archived=0').get(req.params.id);
  if(!row)return reply.code(404).send({message:'Produto não encontrado no cadastro único.'});
  if(row.updated_at!==req.body.expectedUpdatedAt)return reply.code(409).send({message:'O produto mudou em outra janela. Recarregue antes de salvar.'});
  const config=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
  if(Number(config?.revision??0)!==req.body.expectedSettingsRevision)return reply.code(409).send({message:'As configurações de fabricação mudaram. Recarregue e revise o resultado.'});
  if(!categoryAllowed(JSON.parse(String(row.data)).origin,req.body.category))return reply.code(400).send({message:'Produtos de cliente é reservada à origem de cliente. Escolha outra categoria ou deixe em branco.'});
  const result=calculateManufacturing(pilotFeatures?currentProduction(db,req.body.manufacturing):req.body.manufacturing,config?JSON.parse(config.data as string):{},pilotFeatures);
  if(req.body.applyPrices&&!result.prices)return reply.code(400).send({message:'Complete os dados e configurações antes de aplicar preços.'});
  const data=normalizedProduct({...JSON.parse(row.data as string),name:req.body.name.trim(),sku:req.body.sku.trim(),category:req.body.category,manufacturing:req.body.manufacturing});
  if(req.body.applyPrices)data.prices=result.prices;
  db.exec('BEGIN IMMEDIATE');try{
   rememberMaterialUses(db,data.manufacturing);
   if(data.origin==='own'&&data.category)storeCategory(db,data.category);
   db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(data),new Date(Math.max(Date.now(),Date.parse(String(row.updated_at))+1)).toISOString(),req.params.id);db.exec('COMMIT');
  }catch(e){db.exec('ROLLBACK');throw e;}
  return {ok:true,appliedPrices:req.body.applyPrices,calculation:result};
 });
}
