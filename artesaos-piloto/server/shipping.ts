import {productPackaging} from './product-packaging.js';
import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import {randomUUID,createHash} from 'node:crypto';
import {MaterialLedger,MaterialError} from './material-ledger.js';
import {Orders} from './orders.js';
import {StockError,stockInt,stockText} from './product-stock.js';
import {executeOperation,OperationConflict,type Json} from './foundation/operations.js';
import {parseDecimal,formatDecimal,divideRounded,safeInteger} from './foundation/decimal.js';
import {fitPackage,type PhysicalItem,type Dimensions} from './package-fit.js';
export type ShippingInput={orderId?:string;items?:PhysicalItem[];boxId:number|null;protectionCm:string;materials:{materialId:number;quantity:string}[];manual:{dimensions:string[];weightGrams:string;cost:string}};
const decimal=(v:unknown,allowZero=true)=>{try{if(typeof v!=='string'||v.length>30)throw Error();const n=parseDecimal(v.replace(',','.'),6);if(n<0n||!allowZero&&n===0n||n>1000000000000000n)throw Error();return n;}catch{throw new StockError(400,'Informe quantidade/peso/medida válida, até seis casas decimais.');}};
const dimensions=(v:unknown):Dimensions|null=>{if(v===null||v===undefined)return null;if(!Array.isArray(v)||v.length!==3)throw new StockError(400,'Informe três dimensões.');return v.map(n=>{if(typeof n==='number'){if(!Number.isFinite(n)||n<=0||n>1000000)throw new StockError(400,'Dimensão inválida.');return n;}return Number(decimal(n,false))/1e6;}) as Dimensions;};
export class Shipping{
 readonly ledger:MaterialLedger;readonly orders:Orders;
 constructor(readonly db:DatabaseSync,readonly actor:string){this.ledger=new MaterialLedger(db,actor);this.orders=new Orders(db,actor);}
 catalog(){return this.ledger.list().filter(m=>m.profile.tracked&&m.profile.classifications.includes('shipping')).map(m=>({...m,lots:this.ledger.lots(m.id)}));}
 history(orderId:string){const order=this.orders.get(orderId);const row=this.db.prepare('SELECT * FROM shipment_preparations WHERE order_id=?').get(orderId);if(!row)return null;const snapshot=JSON.parse(String(row.snapshot));return {...row,snapshot,changedSincePreparation:snapshot.preview.orderItemsHash!==this.itemsHash(order)};}
 private itemsHash(order:ReturnType<Orders['get']>){return createHash('sha256').update(JSON.stringify(order.items.map(l=>({id:l.id,quantity:l.quantity,snapshot:l.snapshot})))).digest('hex');}
 preview(input:ShippingInput){
  if(!input||typeof input!=='object')throw new StockError(400,'Informe os dados do pacote.');
  const order=input.orderId?this.orders.get(input.orderId):null;
  const profiles=this.ledger.list();
  const rawItems=order?order.items.map(l=>{const s=l.snapshot,pack=productPackaging(s.manufacturing,profiles),quotePacked=s.packaging==='with',packed=[s.packagingLengthCm,s.packagingWidthCm,s.packagingHeightCm].every(n=>typeof n==='number'&&n>0),bare=[s.lengthCm,s.widthCm,s.heightCm].every(n=>typeof n==='number'&&n>0);
   const dims=quotePacked?(packed?[s.packagingLengthCm,s.packagingWidthCm,s.packagingHeightCm]:null):pack.present?pack.dimensions:bare?[s.lengthCm,s.widthCm,s.heightCm]:null;
   const packWeight=quotePacked?(typeof s.packagingWeightGrams==='number'?s.packagingWeightGrams:null):pack.weightGrams;
   return {quantity:l.quantity,dimensions:dims,weightGrams:typeof s.weightGrams==='number'&&s.weightGrams>0&&packWeight!==null?s.weightGrams+packWeight:null};}):input.items;
  if(!Array.isArray(rawItems)||!rawItems.length||rawItems.length>200)throw new StockError(400,'Inclua de um a 200 itens para estimar.');
  const items:PhysicalItem[]=rawItems.map(i=>({quantity:stockInt(i.quantity,1,1000000),dimensions:dimensions(i.dimensions),weightGrams:i.weightGrams===null||i.weightGrams===undefined?null:Number(decimal(String(i.weightGrams)))/1e6}));
  const clearance=Number(decimal(input.protectionCm))/1e6;
  if(!Array.isArray(input.materials)||input.materials.length>50||new Set(input.materials.map(m=>m.materialId)).size!==input.materials.length)throw new StockError(400,'Selecione materiais distintos de envio.');
  const boxId=input.boxId===null?null:stockInt(input.boxId,1);
  if(input.materials.some(m=>m.materialId===boxId))throw new StockError(400,'A caixa já está incluída; não repita como proteção.');
  const selections=[...(boxId?[{materialId:boxId,quantity:'1'}]:[]),...input.materials];
  let packagingGrams=0,cost=0;const warnings:string[]=[];
  const materials=selections.map(m=>{
   const id=stockInt(m.materialId,1),profile=this.ledger.profile(id),definition=this.ledger.definition(id),quantity=decimal(m.quantity,false);
   if(!profile.tracked||!profile.classifications.includes('shipping'))throw new StockError(400,'Selecione materiais físicos classificados para envio.');
   if(id===boxId&&profile.unit!=='un')throw new StockError(400,'Cadastre caixas em unidades (un).');
   const ref=this.db.prepare('SELECT * FROM material_cost_reference WHERE material_id=?').get(id),value=ref?safeInteger(divideRounded(quantity*BigInt(String(ref.unit_cost8)),1000000000000n)):null;
   if(value===null)warnings.push('Custo desconhecido: '+definition.name);else cost=safeInteger(BigInt(cost)+BigInt(value));
   const containerQuantity=profile.defaultQuantity?Number(decimal(profile.defaultQuantity,false))/1e6:profile.unit==='un'?1:null;
   if(profile.weightGrams!==undefined&&containerQuantity)packagingGrams+=Number(profile.weightGrams.replace(',','.'))*(Number(quantity)/1e6)/containerQuantity;else warnings.push('Peso de embalagem pendente: '+definition.name);
   return {materialId:id,name:definition.name,unit:profile.unit,quantity:formatDecimal(quantity,6),profile,reference:ref??null,costCents:value,lots:this.ledger.lots(id),allocations:this.ledger.suggest(id,formatDecimal(quantity,6))};
  });
  if(!input.manual||!Array.isArray(input.manual.dimensions)||input.manual.dimensions.length!==3)throw new StockError(400,'Confira os dados manuais do pacote.');
  const manualDims=input.manual.dimensions.every(d=>d==='')?null:dimensions(input.manual.dimensions);
  const manualWeight=input.manual.weightGrams===''?null:Number(decimal(input.manual.weightGrams))/1e6;
  let manualCost:number|null=null;if(input.manual.cost!==''){try{manualCost=safeInteger(parseDecimal(input.manual.cost.replace(',','.'),2));if(manualCost<0||manualCost>10000000000)throw Error();}catch{throw new StockError(400,'Informe custo manual em reais com até duas casas decimais.');}}
  if(manualCost!==null)cost=safeInteger(BigInt(cost)+BigInt(manualCost));
  const box=materials.find(m=>m.materialId===boxId),inside=box?.profile.internalCm?dimensions(box.profile.internalCm):null;
  const fit=fitPackage(items,inside,clearance);
  const external=manualDims??(box?.profile.externalCm?dimensions(box.profile.externalCm):null);
  if(!external)warnings.push('Dimensões externas pendentes');
  if(items.some(i=>i.weightGrams===null))warnings.push('Peso de produto pendente');
  warnings.push('Estimativa retangular: volumes somados não comprovam encaixe. Confirme orientação, formato e proteção no preparo real.');
  const estimatedGrams=items.reduce((n,i)=>n+(i.weightGrams??0)*i.quantity,0)+packagingGrams+(manualWeight??0);
  const boxGrams=box?.profile.weightGrams!==undefined?Number(box.profile.weightGrams.replace(',','.'))/Number((box.profile.defaultQuantity||'1').replace(',','.')):0;
  const snapshot={orderItemsHash:order?this.itemsHash(order):null,boxGrams,protectionGrams:packagingGrams-boxGrams+(manualWeight??0),orderId:order?.id??null,orderRevision:order?.revision??null,items,boxId,protectionCm:input.protectionCm,materials,manual:input.manual,fit,external,estimatedGrams,costCents:cost,costComplete:materials.every(m=>m.costCents!==null)&&(boxId!==null||manualCost!==null),warnings};
  const previewToken=createHash('sha256').update(JSON.stringify(snapshot)).digest('hex');
  return {...snapshot,previewToken};
 }
 prepare(input:ShippingInput&{requestKey:string;previewToken:string;confirmedFit:boolean;allowDeficit:boolean;allocations:{materialId:number;lots:{lotId:string;quantity:string}[]}[];notes:string}){
  return executeOperation(this.db,{scope:'shipping',key:stockText(input.requestKey,100),actor:this.actor,action:'prepare-shipment',sourceId:stockText(input.orderId,100),request:input as unknown as Json},()=>{
   const preview=this.preview(input),order=this.orders.get(input.orderId!);
   if(['cancelled','delivered'].includes(order.status))throw new StockError(409,'Prepare somente pedidos ativos, antes de confirmar a entrega.');
   if(this.history(order.id))throw new StockError(409,'Preparo deste pedido já registrado. Consulte o histórico; não baixe embalagens novamente.');
   if(preview.previewToken!==input.previewToken)throw new StockError(409,'Pedido, materiais ou custos mudaram. Estime novamente.');
   if(input.confirmedFit!==true)throw new StockError(400,'Confirme a conferência real do encaixe, formato e proteção.');
   if(typeof input.allowDeficit!=='boolean'||!Array.isArray(input.allocations)||input.allocations.length!==preview.materials.length||new Set(input.allocations.map(a=>a.materialId)).size!==input.allocations.length)throw new StockError(400,'Confira os lotes de todos os materiais.');
   const notes=stockText(input.notes,1000,false),id=randomUUID(),now=new Date().toISOString();
   for(const m of preview.materials){const allocation=input.allocations.find(a=>a.materialId===m.materialId);if(!allocation)throw new StockError(400,'Distribuição incompleta.');this.ledger.consume(m.materialId,{requestKey:id+':'+m.materialId,sourceId:id,quantity:m.quantity,allocations:allocation.lots,allowDeficit:input.allowDeficit});}
   this.db.prepare('INSERT INTO shipment_preparations VALUES(?,?,?,?,?,?)').run(id,order.id,order.revision,JSON.stringify({preview,allocations:input.allocations,notes}),this.actor,now);
   this.db.prepare('INSERT INTO order_events(order_id,kind,snapshot,actor,registered_at) VALUES(?,?,?,?,?)').run(order.id,'shipment-prepared',JSON.stringify({id,preview,notes}),this.actor,now);
   return {id,orderId:order.id};
  }).result;
 }
}
export function registerShipping(app:FastifyInstance,db:DatabaseSync,actor:string){const shipping=new Shipping(db,actor);const route=(fn:(req:any)=>unknown)=>async(req:any,reply:any)=>{try{return fn(req);}catch(e){return reply.code(e instanceof StockError||e instanceof MaterialError?e.status:e instanceof OperationConflict?409:400).send({message:e instanceof StockError||e instanceof MaterialError||e instanceof OperationConflict?e.message:'Não foi possível preparar o envio. Confira os dados.'});}};
 app.get('/api/shipping/materials',route(()=>shipping.catalog()));
 app.post('/api/shipping/recommend',{bodyLimit:262144},route(req=>{const base=shipping.preview({...req.body,boxId:null});return shipping.catalog().filter(m=>m.profile.unit==='un'&&Number(m.balance)>0&&m.profile.internalCm).map(m=>{const result=fitPackage(base.items,dimensions(m.profile.internalCm),Number(decimal(req.body.protectionCm))/1e6);return {materialId:m.id,name:m.name,balance:m.balance,...result};}).sort((a,b)=>Number(b.fits)-Number(a.fits));}));
 app.post('/api/shipping/preview',{bodyLimit:262144},route(req=>shipping.preview(req.body)));
 app.get('/api/orders/:id/shipment',route(req=>shipping.history(req.params.id)));
 app.post('/api/shipping/prepare',{bodyLimit:262144},route(req=>shipping.prepare(req.body)));
}
