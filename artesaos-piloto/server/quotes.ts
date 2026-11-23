import {captureDocument} from './pilot/quote-document.js';
import {CLIENT_CATEGORY} from './product-category.js';
import {quoteSearchText,quoteListQuerySchema,pagedQuotes,type QuoteListQuery} from './quote-pagination.js';
import {isDeepStrictEqual} from 'node:util';
import {clientSchema} from './client-data.js';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
const text=(maxLength:number)=>({type:'string',maxLength});
const amount={type:['integer','null'],minimum:0,maximum:10000000000};
const prices={type:'object',additionalProperties:false,required:['wholesale','factory','retail'],properties:{wholesale:amount,factory:amount,retail:amount}};
const item={type:'object',additionalProperties:false,required:['id','name','productId','prices','priceKey','quantity','origin','lengthCm','widthCm','heightCm','weightGrams','packaging','packagingType','packagingAmount','packagingIncluded'],properties:{
 category:text(200),id:{type:'integer',minimum:1},name:{...text(200),minLength:1,pattern:'\\S'},productId:{type:['integer','null'],minimum:1},prices,
 priceKey:{enum:['','wholesale','factory','retail']},quantity:{type:'string',maxLength:6,pattern:'^[0-9]*$'},origin:{enum:['own','client']},
 lengthCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},widthCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},heightCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},weightGrams:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},
 packagingLengthCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},packagingWidthCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},packagingHeightCm:{type:['number','null'],exclusiveMinimum:0,maximum:1000000},packagingWeightGrams:{type:['number','null'],minimum:0,maximum:1000000},packaging:{enum:['','none','with']},packagingType:text(200),packagingAmount:{type:'string',maxLength:14},packagingIncluded:{type:'boolean'}
}};
const client={anyOf:[{type:'null'},{...clientSchema,required:[...clientSchema.required,'id'],properties:{...clientSchema.properties,id:{type:'integer',minimum:1}}}]};
const dataSchema={type:'object',additionalProperties:false,required:['client','items','notes'],properties:{package:{type:'object',additionalProperties:false,properties:Object.fromEntries(['weightGrams','lengthCm','widthCm','heightCm','boxWeightGrams','protectionWeightGrams'].map(key=>[key,{type:'string',maxLength:20,pattern:'^(|[0-9]+([.,][0-9]+)?)$'}]))},status:{enum:['draft','finalized','sent']},delivery:{type:'object',additionalProperties:false,required:['mode','carrier','amount','notes'],properties:{mode:{enum:['','carrier','pickup','courtesy']},carrier:text(200),amount:text(14),notes:text(1000)}},title:text(200),client,notes:text(10000),items:{type:'array',maxItems:200,items:item}}};
type Line={packagingLengthCm?:number|null;packagingWidthCm?:number|null;packagingHeightCm?:number|null;packagingWeightGrams?:number|null;origin?:string;category?:string;id:number;name:string;prices:Record<string,number|null>;priceKey:string;quantity:string;packaging:string;packagingAmount:string;packagingIncluded:boolean};
type Delivery={mode:''|'carrier'|'pickup'|'courtesy';carrier:string;amount:string;notes:string};
type QuoteData={package?:Record<string,string>;title?:string;status?:'draft'|'finalized'|'sent';delivery?:Delivery;client:Record<string,unknown>|null;items:Line[];notes:string};
const emptyDelivery=():Delivery=>({mode:'',carrier:'',amount:'',notes:''});
const normalized=(data:QuoteData)=>{
 const delivery={...(data.delivery??emptyDelivery())};delivery.carrier=delivery.carrier.trim();delivery.amount=delivery.amount.trim();
 if(delivery.mode==='pickup'||delivery.mode==='courtesy'){delivery.carrier='';delivery.amount='0';}
 return {...data,package:{weightGrams:'',lengthCm:'',widthCm:'',heightCm:'',boxWeightGrams:'',protectionWeightGrams:'',...data.package},items:data.items.map(item=>({...item,packagingLengthCm:item.packagingLengthCm??null,packagingWidthCm:item.packagingWidthCm??null,packagingHeightCm:item.packagingHeightCm??null,packagingWeightGrams:item.packagingWeightGrams??null,category:item.origin==='client'?CLIENT_CATEGORY:(item.category??'').trim()})),title:(data.title??'').trim(),client:data.client?{street:'',number:'',complement:'',district:'',city:'',state:'',...data.client}:null,status:data.status??'draft',delivery};
};
export function quoteTotals(items:Line[],delivery:Delivery=emptyDelivery()){
 let productCents=0,packagingCents=0,pending=false;
 for(const item of items){
  const quantity=Number(item.quantity);const price=item.prices[item.priceKey];
  if(!Number.isSafeInteger(quantity)||quantity<1){pending=true;continue;}
  if(typeof price==='number'&&Number.isSafeInteger(productCents+price*quantity))productCents+=price*quantity;else pending=true;
  const extra=item.packaging==='none'||(item.packaging==='with'&&item.packagingIncluded)?0:item.packaging==='with'&&/^\d+(?:[.,]\d{1,2})?$/.test(item.packagingAmount.trim())?Math.round(Number(item.packagingAmount.replace(',','.'))*100):null;
  if(extra!==null&&Number.isSafeInteger(packagingCents+extra*quantity))packagingCents+=extra*quantity;else pending=true;
  if(item.packaging==='with'&&!(item as Line&{packagingType:string}).packagingType?.trim())pending=true;
 }
 const subtotalCents=Number.isSafeInteger(productCents+packagingCents)?productCents+packagingCents:null;
 const deliveryCents=delivery.mode==='pickup'||delivery.mode==='courtesy'?0:delivery.mode==='carrier'&&delivery.carrier.trim()&&/^\d+(?:[.,]\d{1,2})?$/.test(delivery.amount.trim())?Math.round(Number(delivery.amount.replace(',','.'))*100):null;
 const totalCents=subtotalCents!==null&&deliveryCents!==null&&Number.isSafeInteger(subtotalCents+deliveryCents)?subtotalCents+deliveryCents:null;
 return {productCents,packagingCents,subtotalCents,deliveryCents,totalCents,pending:pending||subtotalCents===null,freightPending:deliveryCents===null||totalCents===null};
}
function completionIssues(data:QuoteData){
 const issues:string[]=[];
 if(!data.client)issues.push('selecione o cliente');
 if(!data.items.length)issues.push('adicione ao menos um produto');
 const totals=quoteTotals(data.items,data.delivery);
 if(totals.pending)issues.push('confira quantidade, preço e embalagem dos itens');
 if(totals.freightPending)issues.push('defina transportadora e valor do frete, retirada no local ou entrega por cortesia');
 return issues;
}
const content=(data:QuoteData)=>{const {status,...rest}=normalized(data);return rest;};
export function registerQuotes(app:FastifyInstance,db:DatabaseSync,pilot=false){



 const body={type:'object',additionalProperties:false,required:['data','expectedRevision'],properties:{data:dataSchema,expectedRevision:{type:'integer',minimum:0}}};
 const link=(quoteId:unknown)=>pilot?db.prepare('SELECT id,status FROM orders WHERE quote_id=?').get(Number(quoteId)):undefined;
 const decode=(row:Record<string,unknown>)=>{const order=link(row.id);const data=normalized(JSON.parse(row.data as string));return {id:row.id,data,orderId:order?.id??null,orderStatus:order?.status??null,revision:row.revision,updatedAt:row.updated_at,totals:quoteTotals(data.items,data.delivery)};};
 app.get<{Querystring:QuoteListQuery}>('/api/quotes',{schema:{querystring:quoteListQuerySchema}},req=>req.query.pageSize?pagedQuotes(db,req.query,pilot):db.prepare('SELECT * FROM quotes WHERE archived=0 ORDER BY id DESC').all().map(decode));
 app.get<{Params:{id:string}}>('/api/quotes/:id',(req,reply)=>{const row=db.prepare('SELECT * FROM quotes WHERE id=? AND archived=0').get(req.params.id);return row?decode(row):reply.code(404).send({message:'Orçamento não encontrado.'});});
 function archivedReference(data:QuoteData,old?:QuoteData){
  if(data.client?.id!==old?.client?.id&&data.client?.id&&db.prepare('SELECT archived FROM clients WHERE id=?').get(Number(data.client.id))?.archived===1)return true;
  const previous=new Set((old?.items??[]).map(i=>(i as Line&{productId?:number}).productId));
  return data.items.some(i=>{const id=(i as Line&{productId?:number}).productId;return id&&!previous.has(id)&&db.prepare('SELECT archived FROM products WHERE id=?').get(id)?.archived===1;});
 }
 function unique(items:Line[]){return new Set(items.map(i=>i.id)).size===items.length;}
 app.post<{Body:{data:QuoteData;expectedRevision:number}}>('/api/quotes',{bodyLimit:512*1024,schema:{body}},(req,reply)=>{
  const data=normalized(req.body.data);
  if(archivedReference(data))return reply.code(400).send({message:'Produto ou cliente arquivado não pode ser incluído em novo orçamento. Atualize a seleção.'});
  if(req.body.expectedRevision!==0||!unique(data.items))return reply.code(400).send({message:'Revise a versão e os itens do orçamento.'});
  if(data.status==='sent')return reply.code(400).send({message:'Finalize o orçamento antes de marcar como enviado ao cliente.'});
  const issues=data.status==='draft'?[]:completionIssues(data);
  if(issues.length)return reply.code(400).send({message:'Para finalizar: '+issues.join('; ')+'.'});
  db.exec('BEGIN IMMEDIATE');
  try{
   const result=db.prepare('INSERT INTO quotes(data,search_text,updated_at) VALUES (?,?,?)').run(JSON.stringify(data),quoteSearchText(data),new Date().toISOString());
   const id=Number(result.lastInsertRowid);
   if(pilot&&data.status==='finalized')captureDocument(db,id,1,data,quoteTotals(data.items,data.delivery));
   db.exec('COMMIT');return {id,revision:1};
  }catch(e){db.exec('ROLLBACK');throw e;}
 });
 app.put<{Params:{id:string};Body:{data:QuoteData;expectedRevision:number}}>('/api/quotes/:id',{bodyLimit:512*1024,schema:{body}},(req,reply)=>{
  const data=normalized(req.body.data);
  if(!unique(data.items))return reply.code(400).send({message:'Identificador de item repetido.'});
  const row=db.prepare('SELECT * FROM quotes WHERE id=? AND archived=0').get(req.params.id);
  if(!row||Number(row.revision)!==req.body.expectedRevision)return reply.code(409).send({message:'Este orçamento foi alterado em outra janela. Preserve suas alterações e reabra a versão salva antes de continuar.'});
  if(link(row.id))return reply.code(409).send({message:'Orçamento aprovado preservado como histórico. Edite o pedido vinculado.'});
  const old=normalized(JSON.parse(row.data as string));
  if(archivedReference(data,old))return reply.code(400).send({message:'Produto ou cliente arquivado não pode ser incluído no orçamento. Atualize a seleção.'});
  if(data.status==='sent'&&old.status!=='finalized'&&old.status!=='sent')return reply.code(400).send({message:'Finalize o orçamento antes de marcar como enviado ao cliente.'});
  if(old.status!=='draft'&&!isDeepStrictEqual(content(old),content(data)))return reply.code(400).send({message:'Reabra como rascunho antes de editar um orçamento finalizado ou enviado.'});
  if(old.status==='sent'&&data.status==='finalized')return reply.code(400).send({message:'Reabra como rascunho para revisar o orçamento enviado.'});
  const issues=data.status==='draft'?[]:completionIssues(data);
  if(issues.length)return reply.code(400).send({message:'Para finalizar: '+issues.join('; ')+'.'});
  db.exec('BEGIN IMMEDIATE');
  try{
   db.prepare('INSERT INTO quote_versions(quote_id,revision,data,updated_at) VALUES (?,?,?,?)').run(req.params.id,row.revision,row.data,row.updated_at);
   const result=db.prepare('UPDATE quotes SET data=?,search_text=?,revision=revision+1,updated_at=? WHERE id=? AND revision=? AND archived=0').run(JSON.stringify(data),quoteSearchText(data),new Date().toISOString(),req.params.id,req.body.expectedRevision);
   if(!result.changes)throw Error('Conflito de versão.');
   if(pilot&&old.status==='draft'&&data.status==='finalized')captureDocument(db,Number(req.params.id),req.body.expectedRevision+1,data,quoteTotals(data.items,data.delivery));
   db.exec('COMMIT');
  }catch(e){db.exec('ROLLBACK');throw e;}
  return {id:Number(req.params.id),revision:req.body.expectedRevision+1};
 });
}
