import {photoReferenceAllowed,PHOTO_REFERENCE_ERROR} from './product-photos.js';
import {rememberMaterialUses} from './materials.js';
import {createHash} from 'node:crypto';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {productSchema,type Product} from './products.js';
import {normalizedProduct as normalizeProduct,categoryAllowed} from './product-category.js';
import {storeCategory} from './categories.js';
import {configFields,operationFields,markupRanges,validMarkup} from './manufacturing-model.js';
type Target=number|null|'skip';
type Decision={key:string;targetId:Target;applyPrices?:boolean;replaceManufacturing?:boolean;category?:string};
type RecordInput={key:string;product:Product};
type Body={records:RecordInput[];settings?:Record<string,string>;decisions?:Decision[];applyConfiguration?:boolean;confirm:boolean;previewToken?:string};
const normalized=(value:string)=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('pt-BR').trim();
const sameCategory=(a:string|undefined,b:string|undefined)=>!a?.trim()||!b?.trim()||normalized(a.split(' > ').at(-1)!)===normalized(b.split(' > ').at(-1)!);
const priceChanged=(a:Product['prices'],b:Product['prices'])=>['wholesale','factory','retail'].some(key=>a[key as keyof typeof a]!==b[key as keyof typeof b]);
const settingsProperties=Object.fromEntries([['filamentKgPrice','Referência legada'],...configFields,...operationFields].map(([key])=>[key,{type:'string',maxLength:20,pattern:'^(|[0-9]+([.,][0-9]+)?)$'}]));
export function registerReconciliation(app:FastifyInstance,db:DatabaseSync,pilotFeatures=false){
 const normalizedProduct=<T extends {origin:string;category?:string;catalogVisible?:boolean}>(product:T)=>normalizeProduct(product,pilotFeatures);
 app.get('/api/products/export',(_req,reply)=>{
  const products=db.prepare('SELECT id,data,archived,updated_at FROM products ORDER BY id').all().map(row=>({...normalizedProduct(JSON.parse(String(row.data))),id:Number(row.id),archived:Boolean(row.archived),updatedAt:row.updated_at}));
  const config=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
  return reply.header('Content-Disposition','attachment; filename="catalogo-fabricacao-e-orcamentos.json"').send({type:'catalog-export-v1',exportedAt:new Date().toISOString(),products,categories:db.prepare('SELECT id,path,reserved,revision FROM categories ORDER BY id').all(),manufacturingSettings:config?{data:JSON.parse(String(config.data)),revision:config.revision}:{data:{},revision:0}});
 });
 app.post<{Body:Body}>('/api/products/reconcile',{bodyLimit:2*1024*1024,schema:{body:{type:'object',additionalProperties:false,required:['records','confirm'],properties:{records:{type:'array',minItems:1,maxItems:500,items:{type:'object',additionalProperties:false,required:['key','product'],properties:{key:{type:'string',minLength:1,maxLength:250},product:productSchema}}},settings:{type:'object',additionalProperties:false,properties:settingsProperties},applyConfiguration:{type:'boolean'},decisions:{type:'array',maxItems:500,items:{type:'object',additionalProperties:false,required:['key','targetId'],properties:{key:{type:'string',minLength:1,maxLength:250},targetId:{anyOf:[{type:'integer',minimum:1},{type:'null'},{enum:['skip']}]},applyPrices:{type:'boolean'},replaceManufacturing:{type:'boolean'},category:{type:'string',maxLength:200}}}},confirm:{type:'boolean'},previewToken:{type:'string',pattern:'^[a-f0-9]{64}$'}}}}},(req,reply)=>{
  const rows=db.prepare('SELECT id,data,archived,updated_at FROM products ORDER BY id').all().map(row=>({id:Number(row.id),data:JSON.parse(String(row.data)) as Product,archived:Boolean(row.archived),updatedAt:String(row.updated_at)}));
  const config=db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
  const configData=config?JSON.parse(String(config.data)) as Record<string,string>:{};
  const decisions=req.body.decisions??[],seenKeys=new Set<string>(),seenTargets=new Set<number>(),seenSources=new Set<string>();
  if(new Set(decisions.map(d=>d.key)).size!==decisions.length||decisions.some(d=>!req.body.records.some(record=>record.key===d.key)))return reply.code(400).send({message:'Decisões repetidas ou sem registro correspondente.'});
  const token=createHash('sha256').update(JSON.stringify({records:req.body.records,settings:req.body.settings??{},decisions,applyConfiguration:Boolean(req.body.applyConfiguration),rows,config:config??null})).digest('hex');
  if(req.body.confirm&&(!req.body.previewToken||req.body.previewToken!==token))return reply.code(409).send({message:'O catálogo, as escolhas ou as configurações mudaram. Gere uma nova prévia antes de confirmar. Nenhum dado foi gravado.'});
  const planned:{id:number|null;data:Product;sources:string[];updatedAt?:string}[]=[];
  const details=req.body.records.map(record=>{
   const incoming=normalizedProduct(record.product),decision=decisions.find(d=>d.key===record.key);const errors:string[]=[];
   if(seenKeys.has(record.key))errors.push('Identificador repetido no arquivo');seenKeys.add(record.key);
   if(!Object.values(incoming.prices).some(v=>v!==null)||!incoming.sourceKeys.length||!record.product.name.trim())errors.push('Nome, preço ou vínculo externo ausente');
   if(record.product.origin==='client'&&record.product.publicAllowed)errors.push('Produto de cliente deve permanecer privado');
   const sourceMatches=rows.filter(row=>row.data.sourceKeys.some(key=>incoming.sourceKeys.includes(key)));
   const skuMatches=incoming.sku?.trim()?rows.filter(row=>normalized(row.data.sku??'')===normalized(incoming.sku!)):[];
   const nameMatches=rows.filter(row=>row.data.origin===incoming.origin&&sameCategory(row.data.category,incoming.category)&&normalized(row.data.name)===normalized(incoming.name)&&(!incoming.sku?.trim()||!row.data.sku?.trim()));
   const candidates=sourceMatches.length?sourceMatches:skuMatches.length?skuMatches:nameMatches;
   const suggested=sourceMatches.length===1&&sourceMatches[0].archived?'skip':candidates.length===1&&!candidates[0].archived?candidates[0].id:candidates.length?'review':null;
   const target:Target|'review'=decision?decision.targetId:suggested;
   const existing=typeof target==='number'?rows.find(row=>row.id===target):undefined;
   if(target==='review')errors.push('Escolha o vínculo: há correspondência ambígua ou arquivada');
   if(typeof target==='number'&&(!existing||existing.archived))errors.push('Produto de destino ausente ou arquivado');
   if(target!=='skip'){
    if(existing&&seenTargets.has(existing.id))errors.push('Dois registros foram vinculados ao mesmo produto');
    if(existing)seenTargets.add(existing.id);
    if(existing&&existing.data.origin!==incoming.origin)errors.push('A origem difere: revise o cadastro em vez de substituí-la');
    if(existing&&skuMatches.some(row=>row.id!==existing.id))errors.push('O SKU corresponde a outro produto; revise o vínculo');
    if(sourceMatches.some(row=>row.id!==existing?.id))errors.push('Vínculo externo já pertence a outro produto');
    if(target===null&&(candidates.length||planned.some(p=>(incoming.sku?.trim()&&normalized(p.data.sku??'')===normalized(incoming.sku))||(p.data.origin===incoming.origin&&sameCategory(p.data.category,incoming.category)&&normalized(p.data.name)===normalized(incoming.name)&&(!p.data.sku?.trim()||!incoming.sku?.trim())))))errors.push('Possível duplicata por nome ou SKU; vincule ao cadastro existente ou ignore');
    for(const source of incoming.sourceKeys){if(seenSources.has(source))errors.push('Vínculo externo repetido entre linhas');seenSources.add(source);}
   }
   const changes:string[]=[];let next=existing?structuredClone(existing.data):structuredClone(incoming);
   if(existing&&target!=='skip'){
    for(const key of ['sku','description','imageUrl','category'] as const)if(!next[key]?.trim()&&incoming[key]?.trim()){next[key]=incoming[key];changes.push(key);}
    for(const key of ['weightGrams','lengthCm','widthCm','heightCm'] as const)if(next[key]===null&&incoming[key]!==null){next[key]=incoming[key];changes.push(key);}
    if(incoming.manufacturing&&(!next.manufacturing||decision?.replaceManufacturing)){next.manufacturing=incoming.manufacturing;changes.push('fabricação');}
    if(decision?.applyPrices){next.prices={...incoming.prices};if(priceChanged(existing.data.prices,next.prices))changes.push('preços');}
    const newSources=incoming.sourceKeys.filter(key=>!next.sourceKeys.includes(key));next.sourceKeys=[...next.sourceKeys,...newSources];if(newSources.length)changes.push('vínculos da planilha');
    if(next.sourceKeys.length>200)errors.push('O produto excederia o limite de vínculos externos');
   }
   if(decision?.category!==undefined&&incoming.origin==='own'&&next.category!==decision.category){next.category=decision.category;changes.push('categoria escolhida');}
   next=normalizedProduct(next);
   if(pilotFeatures&&target!=='skip'&&!photoReferenceAllowed(db,incoming.imageUrl,existing?.data.imageUrl))errors.push(PHOTO_REFERENCE_ERROR);
   if(pilotFeatures&&target!=='skip'&&!photoReferenceAllowed(db,next.imageUrl,existing?.data.imageUrl)&&!errors.includes(PHOTO_REFERENCE_ERROR))errors.push(PHOTO_REFERENCE_ERROR);
   if(!categoryAllowed(next.origin,next.category))errors.push('A categoria Produtos de cliente é reservada. Escolha outra categoria para o produto próprio');
   if(target==='skip')errors.length=0;
   const action=target==='skip'?'Ignorar':target===null?'Criar produto':changes.length?'Completar cadastro':'Preservar cadastro';
   if(target!=='skip'&&target!=='review'&&!errors.length&&(!existing||changes.length))planned.push({id:existing?.id??null,data:next,sources:incoming.sourceKeys,updatedAt:existing?.updatedAt});
   return {origin:incoming.origin,categoryAfter:next.category??'',matchBy:sourceMatches.length?'vínculo externo':skuMatches.length?'SKU exato':nameMatches.length?'nome exato — confira o vínculo':'sem correspondência',category:incoming.category??'',key:record.key,name:incoming.name,sku:incoming.sku??'',targetId:target,action,changes,errors,candidates:candidates.map(row=>({id:row.id,name:row.data.name,sku:row.data.sku??'',archived:row.archived})),existingName:existing?.data.name??null,priceBefore:existing?.data.prices??null,priceAfter:next.prices,pricesDiffer:existing?priceChanged(existing.data.prices,incoming.prices):false,manufacturingBefore:existing?.data.manufacturing??null,manufacturingIncoming:incoming.manufacturing??null,manufacturingExists:Boolean(existing?.data.manufacturing),incomingManufacturing:Boolean(incoming.manufacturing)};
  });
  if(req.body.applyConfiguration)for(const key of Object.keys(markupRanges) as (keyof typeof markupRanges)[]){const raw=req.body.settings?.[key];if(raw&& !validMarkup(key,Number(raw.replace(',','.'))))return reply.code(400).send({message:`Multiplicador fora da faixa permitida: ${key}.`,field:key});}
  const configuration=Object.entries(req.body.settings??{}).map(([key,value])=>({key,before:configData[key]??'',after:value,changed:(configData[key]??'')!==value}));
  const invalid=details.some(row=>row.errors.length);
  if(req.body.confirm&&invalid)return reply.code(400).send({message:'Resolva os vínculos e conflitos na prévia. Nenhum dado foi gravado.'});
  if(req.body.confirm){
   db.exec('BEGIN IMMEDIATE');try{
    for(const entry of planned){
     rememberMaterialUses(db,entry.data.manufacturing);
     if(entry.data.origin==='own'&&entry.data.category)storeCategory(db,entry.data.category);
     let id=entry.id;
     if(id===null)id=Number(db.prepare('INSERT INTO products(data,updated_at) VALUES (?,?)').run(JSON.stringify(entry.data),new Date().toISOString()).lastInsertRowid);
     else db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(entry.data),new Date(Math.max(Date.now(),(Date.parse(entry.updatedAt??'')||0)+1)).toISOString(),id);
     for(const source of entry.data.sourceKeys)db.prepare('INSERT OR IGNORE INTO product_sources(source_key,product_id) VALUES (?,?)').run(source,id);
    }
    if(req.body.applyConfiguration&&configuration.some(row=>row.changed))db.prepare('INSERT INTO area_settings(area,data,revision) VALUES (?,?,?) ON CONFLICT(area) DO UPDATE SET data=excluded.data,revision=excluded.revision').run('fabricacao',JSON.stringify({...configData,...req.body.settings}),Number(config?.revision??0)+1);
    db.exec('COMMIT');
   }catch(e){db.exec('ROLLBACK');throw e;}
  }
  return {type:'reconciliation',details,configuration,previewToken:token,valid:!invalid,confirmed:req.body.confirm,counts:{create:details.filter(r=>r.action==='Criar produto').length,update:details.filter(r=>r.action==='Completar cadastro').length,preserve:details.filter(r=>r.action==='Preservar cadastro').length,skip:details.filter(r=>r.action==='Ignorar').length,conflicts:details.filter(r=>r.errors.length).length},categories:db.prepare('SELECT path FROM categories WHERE reserved=0 ORDER BY category_key').all().map(row=>String(row.path)),catalog:rows.filter(row=>!row.archived).map(row=>({id:row.id,name:row.data.name,sku:row.data.sku??''}))};
 });
}
