import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {ProductStock,StockError,stockText} from './product-stock.js';
import {MaterialLedger,MaterialError} from './material-ledger.js';
import {Consigned} from './consigned.js';
import {Distribution} from './distribution.js';
import {Finance} from './finance.js';
import {reservedStock} from './stock-reservations.js';
import {executeOperation,OperationConflict,type Json} from './foundation/operations.js';
import {moduleKeys} from './module-access.js';

/** Existing occurrences authorize only their own correction, never a whole module. */
export class AttentionCorrection{
 constructor(readonly db:DatabaseSync,readonly actor:string){}
 occurrence(id:string){const row=this.db.prepare('SELECT * FROM attention_events WHERE id=?').get(stockText(id,100));if(!row)throw new StockError(404,'Pendência não encontrada.');return {...row,id:String(row.id),kind:String(row.kind),state:String(row.state),source_id:String(row.source_id),item_ref:String(row.item_ref??''),location_id:String(row.location_id??'central'),details:JSON.parse(String(row.details))};}
 read(id:string){
  const row=this.occurrence(id),base={id:row.id,kind:row.kind,state:row.state,details:row.details};
  const stock=new ProductStock(this.db,this.actor),finance=new Finance(this.db,this.actor);
  if(row.kind==='stock-divergence'){
   const consigned=row.details.kind==='consigned',item=consigned?new Consigned(this.db,this.actor).item(row.item_ref):stock.item(row.item_ref);
   return {...base,item:{id:row.item_ref,name:consigned?item.name:JSON.parse(String(this.db.prepare('SELECT data FROM products WHERE id=?').get(item.product_id)?.data??'{}')).name,productId:consigned?null:item.product_id},locationId:row.location_id,balance:consigned?new Consigned(this.db,this.actor).balance(row.item_ref,row.location_id):stock.balance(row.item_ref,row.location_id)};
  }
  if(row.kind==='material-deficit')return {...base,material:new MaterialLedger(this.db,this.actor).list([Number(row.details.materialId)])[0]};
  if(row.kind==='session-count')return {...base,session:new Distribution(this.db,this.actor).session(row.source_id)};
  if(row.kind==='client-excess'){
   const item=stock.item(row.item_ref);if(item.kind!=='client')throw new StockError(409,'Origem privada incompatível.');
   return {...base,row:{id:row.item_ref,inHand:stock.balance(row.item_ref,'central'),reserved:reservedStock(this.db,row.item_ref)},products:this.db.prepare('SELECT id,data FROM products WHERE archived=0').all().map(p=>({id:Number(p.id),...JSON.parse(String(p.data))})).filter(p=>p.origin==='own').map(p=>({id:p.id,origin:p.origin,name:p.name}))};
  }
  if(row.kind==='financial-overdue'||row.kind==='financial-excess')return {...base,title:finance.title(row.source_id),accounts:this.db.prepare('SELECT id,name,active FROM finance_accounts WHERE active=1').all(),methods:this.db.prepare('SELECT * FROM finance_methods').all(),payments:this.db.prepare("SELECT id,amount_cents,fee_cents,state FROM finance_payments WHERE title_id=? AND state IN ('settled','scheduled')").all(row.source_id)};
  throw new StockError(400,'Tipo de pendência sem correção contextual.');
 }
 correct(id:string,input:Record<string,any>){
  if(!input||typeof input!=='object'||Array.isArray(input))throw new StockError(400,'Correção inválida.');
  const action=stockText(input.action,50),requestKey=stockText(input.requestKey,80);
  const fields:Record<string,string[]>={stock:['expectedBalance','newBalance','reason'],material:['expectedBalance','newBalance','reason'],session:['expectedRevision','reason'],destination:['kind','quantity','targetProductId','confirmPrivacy','reason'],scheduled:['paymentId','settlement','reason'],pay:['expectedRevision','parts'],refund:['paymentId','amountCents','feeRefundCents','accountId','reason'],credit:['amountCents','reason']};
  if(!Object.hasOwn(fields,action)||Object.keys(input).some(k=>!['action','requestKey',...fields[action]].includes(k)))throw new StockError(400,'Campos de correção inválidos. O destino é definido pela pendência.');
  return executeOperation(this.db,{scope:'attention-correction',key:requestKey,actor:this.actor,action,sourceId:id,request:input as Json},()=>{
   const row=this.occurrence(id);if(row.state!=='open')throw new StockError(409,'Pendência já resolvida. Consulte o histórico.');
   const key='correction:'+requestKey,stock=new ProductStock(this.db,this.actor),finance=new Finance(this.db,this.actor);
   if(action==='stock'&&row.kind==='stock-divergence'){
    const body={requestKey:key,locationId:row.location_id,expectedBalance:input.expectedBalance,newBalance:input.newBalance,reason:input.reason,attentionId:row.id};
    if(row.details.kind==='consigned')return new Consigned(this.db,this.actor).adjust(row.item_ref,body);
    return stock.adjust({...body,productId:Number(stock.item(row.item_ref).product_id)});
   }
   if(action==='material'&&row.kind==='material-deficit')return new MaterialLedger(this.db,this.actor).adjust(Number(row.details.materialId),{requestKey:key,lotId:null,kind:'correction',expectedBalance:input.expectedBalance,newBalance:input.newBalance,reason:input.reason});
   if(action==='session'&&row.kind==='session-count')return new Distribution(this.db,this.actor).closeSession(row.source_id,{requestKey:key,expectedRevision:input.expectedRevision,physical:'return',reason:input.reason});
   if(action==='destination'&&row.kind==='client-excess')return new Distribution(this.db,this.actor).destination(row.item_ref,{requestKey:key,kind:input.kind,quantity:input.quantity,targetProductId:input.targetProductId,confirmPrivacy:input.confirmPrivacy,reason:input.reason});
   if(action==='pay'&&row.kind==='financial-overdue')return finance.pay(row.source_id,{requestKey:key,expectedRevision:input.expectedRevision,allowExcess:false,parts:input.parts});
   if(action==='scheduled'&&row.kind==='financial-overdue'){
    const payment=this.db.prepare('SELECT title_id FROM finance_payments WHERE id=?').get(stockText(input.paymentId,100));if(!payment||payment.title_id!==row.source_id)throw new StockError(403,'Pagamento não pertence à origem desta pendência.');
    return finance.settle(input.paymentId,{requestKey:key,action:input.settlement,reason:input.reason});
   }
   if(action==='credit'&&row.kind==='financial-excess')return finance.issueCredit(row.source_id,{requestKey:key,amountCents:input.amountCents,reason:input.reason});
   if(action==='refund'&&row.kind==='financial-excess'){
    const payment=this.db.prepare('SELECT title_id FROM finance_payments WHERE id=?').get(stockText(input.paymentId,100));
    if(!payment||payment.title_id!==row.source_id)throw new StockError(403,'Pagamento não pertence à origem desta pendência.');
    if(!Number.isSafeInteger(input.amountCents)||input.amountCents>Math.max(0,-finance.title(row.source_id).remaining))throw new StockError(409,'Reembolso supera o excedente atual.');
    return finance.refund(input.paymentId,{requestKey:key,amountCents:input.amountCents,feeRefundCents:input.feeRefundCents,accountId:input.accountId,reason:input.reason});
   }
   throw new StockError(403,'Operação não autorizada para esta pendência.');
  }).result;
 }
}
export function registerAttentionCorrections(app:FastifyInstance,db:DatabaseSync,actor:string){
 const correction=new AttentionCorrection(db,actor);
 const route=(write:boolean)=>async(req:any,reply:any)=>{
  const grants=String(req.headers['x-pilot-modules']??'').split(',');if(!grants.some(k=>moduleKeys.includes(k as any)))return reply.code(403).send({message:'Uma ferramenta liberada é necessária para corrigir a pendência.'});
  try{return write?correction.correct(req.params.id,req.body):correction.read(req.params.id);}catch(e){return reply.code(e instanceof StockError||e instanceof MaterialError?e.status:e instanceof OperationConflict?409:400).send({message:e instanceof StockError||e instanceof MaterialError||e instanceof OperationConflict?e.message:'Não foi possível corrigir a pendência. Confira os dados e tente novamente.'});}
 };
 app.get('/api/attention/:id/correction',route(false));
 app.post('/api/attention/:id/correction',{bodyLimit:16384},route(true));
}
