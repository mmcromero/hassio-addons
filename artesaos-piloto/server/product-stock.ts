import {captureClientExcess,matchesStockAttention,closeAttention} from './attention.js';
import {refreshReservations,reservedStock} from './stock-reservations.js';
import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import {randomUUID,createHash} from 'node:crypto';
import {executeOperation,OperationConflict,type Json} from './foundation/operations.js';
import {parseDecimal,formatDecimal,safeInteger} from './foundation/decimal.js';
import {MaterialLedger,MaterialError} from './material-ledger.js';
import {currentProduction} from './material-current-cost.js';
import {calculateManufacturing} from './manufacturing-model.js';
import {units} from './material-model.js';
import type {Product} from './products.js';
export class StockError extends Error{constructor(readonly status:number,message:string){super(message);}}
export const stockText=(v:unknown,max=200,required=true)=>{if(typeof v!=='string'||v.length>max||/[\x00-\x1f\x7f]/.test(v)||required&&!v.trim())throw new StockError(400,'Confira os campos de texto.');return v.trim();};
export const stockInt=(v:unknown,min=0,max=1000000000)=>{if(!Number.isSafeInteger(v)||Number(v)<min||Number(v)>max)throw new StockError(400,'Quantidade inteira ou identificador inválido.');return Number(v);};
const tiers=['wholesale','factory','retail'] as const;
export type Prices=Product['prices'];
type Allocation={lotId:string;quantity:string};
export type ManufactureInput={orderId?:string;requestKey:string;productId:number;quantity:number;previewToken:string;materials:{materialId:number;allocations:Allocation[]}[];allowDeficit:boolean};
export class ProductStock{
 readonly materials:MaterialLedger;
 constructor(readonly db:DatabaseSync,readonly actor:string){this.materials=new MaterialLedger(db,actor);}
 operation<T extends Json>(key:string,action:string,source:string,request:Json,work:()=>T){return executeOperation(this.db,{scope:'product-stock',key:stockText(key,100),actor:this.actor,action,sourceId:source,request},work).result;}
 product(productId:number){const row=this.db.prepare('SELECT data,updated_at FROM products WHERE id=? AND archived=0').get(stockInt(productId,1));if(!row)throw new StockError(404,'Produto não encontrado.');return {data:JSON.parse(String(row.data)) as Product,updatedAt:String(row.updated_at)};}
 item(itemId:string){const row=this.db.prepare('SELECT * FROM stock_items WHERE id=?').get(stockText(itemId,100));if(!row)throw new StockError(404,'Estoque não encontrado.');return row;}
 location(locationId:string){const row=this.db.prepare('SELECT * FROM stock_locations WHERE id=? AND active=1').get(stockText(locationId,100));if(!row)throw new StockError(404,'Local não encontrado ou inativo.');return row;}
 balance(itemId:string,locationId?:string){return safeInteger(BigInt(this.db.prepare('SELECT COALESCE(SUM(delta),0) n FROM product_stock_movements WHERE item_id=?'+(locationId?' AND location_id=?':'')).get(itemId,...(locationId?[locationId]:[]))!.n as number));}
 ensureOwn(productId:number){stockInt(productId,1);let item=this.db.prepare("SELECT * FROM stock_items WHERE product_id=? AND kind='own'").get(productId);if(item)return item;const p=this.product(productId).data;if(p.origin!=='own')throw new StockError(400,'Produto de cliente não pertence ao estoque comercial.');if(!item){const itemId=randomUUID();this.db.prepare("INSERT INTO stock_items(id,product_id,kind,prices) VALUES(?,?,'own',?)").run(itemId,productId,JSON.stringify(p.prices));item=this.item(itemId);this.priceHistory(itemId,{},p.prices,'Primeira entrada: preços aplicados do Produto');}return item;}
 private priceHistory(itemId:string,before:unknown,after:unknown,reason:string){this.db.prepare('INSERT INTO stock_price_history(item_id,before_prices,after_prices,reason,actor,registered_at) VALUES(?,?,?,?,?,?)').run(itemId,JSON.stringify(before),JSON.stringify(after),reason,this.actor,new Date().toISOString());}
 writePrices(itemId:string,prices:Prices,reason:string){const item=this.item(itemId);if(item.kind!=='own')throw new StockError(400,'Preços comerciais somente para produtos próprios.');for(const key of tiers)if(prices[key]!==null)stockInt(prices[key],0,10000000000);if(tiers.every(t=>prices[t]===null))throw new StockError(400,'Informe ao menos uma faixa de preço.');this.priceHistory(itemId,JSON.parse(String(item.prices)),prices,reason);this.db.prepare('UPDATE stock_items SET prices=?,revision=revision+1 WHERE id=?').run(JSON.stringify(prices),itemId);}
 move(itemId:string,locationId:string,delta:number,kind:string,sourceId:string,reason:string){this.item(itemId);this.location(locationId);const before=this.balance(itemId,locationId),after=safeInteger(BigInt(before)+BigInt(delta));safeInteger(BigInt(this.balance(itemId))+BigInt(delta));this.db.prepare('INSERT INTO product_stock_movements(item_id,location_id,delta,before_qty,after_qty,kind,source_id,reason,actor,registered_at) VALUES(?,?,?,?,?,?,?,?,?,?)').run(itemId,locationId,delta,before,after,kind,sourceId,reason,this.actor,new Date().toISOString());refreshReservations(this.db);return after;}
 list(){return this.db.prepare('SELECT s.*,p.data,p.archived FROM stock_items s JOIN products p ON p.id=s.product_id ORDER BY s.rowid DESC').all().map(row=>{const itemId=String(row.id),locations=this.db.prepare('SELECT l.*,COALESCE(SUM(m.delta),0) quantity FROM stock_locations l LEFT JOIN product_stock_movements m ON m.location_id=l.id AND m.item_id=? GROUP BY l.id ORDER BY l.rowid').all(itemId);const inHand=this.balance(itemId,'central');return {...row,id:String(row.id),kind:String(row.kind),order_id:row.order_id===null?null:String(row.order_id),product_id:Number(row.product_id),product:JSON.parse(String(row.data)),prices:JSON.parse(String(row.prices)),total:this.balance(itemId),inHand,reserved:reservedStock(this.db,itemId),available:inHand-reservedStock(this.db,itemId),locations};});}
 ensureClient(productId:number,orderId:string){this.validateOrder(productId,orderId);const p=this.product(productId).data;if(p.origin!=='client')throw new StockError(400,'Produto não é exclusivo de cliente.');let item=this.db.prepare("SELECT * FROM stock_items WHERE product_id=? AND kind='client' AND order_id=?").get(productId,orderId);if(!item){const itemId=randomUUID();this.db.prepare("INSERT INTO stock_items(id,product_id,kind,order_id,prices) VALUES(?,?,'client',?,'{}')").run(itemId,productId,orderId);item=this.item(itemId);}return item;}
 private validateOrder(productId:number,orderId:string){stockText(orderId,100);const line=this.db.prepare("SELECT 1 FROM order_lines l JOIN orders o ON o.id=l.order_id WHERE l.order_id=? AND l.product_id=? AND l.active=1 AND o.status NOT IN ('delivered','cancelled')").get(orderId,productId);if(!line)throw new StockError(409,'Produto não pertence a pedido ativo desta conta.');}
 preview(productId:number,quantity:number,orderId?:string){
  stockInt(quantity,1,1000000);const product=this.product(productId),p=product.data;
  if(orderId)this.validateOrder(productId,orderId);else if(p.origin!=='own')throw new StockError(400,'Fabricação de produto de cliente exige pedido vinculado.');
  if(!p.manufacturing)throw new StockError(400,'Preencha a ficha de fabricação do produto antes de fabricar.');
  const settings=this.db.prepare("SELECT data,revision FROM area_settings WHERE area='fabricacao'").get();
  const production=currentProduction(this.db,p.manufacturing),calculation=calculateManufacturing(production,settings?JSON.parse(String(settings.data)):{},true);
  const totals=new Map<number,bigint>(),notes:string[]=[];
  const factors:Record<string,bigint>={g:10n,kg:10000n,ml:10n,l:10000n,mm:1n,cm:10n,m:1000n,un:10n,custom:10n};
  for(const step of [production,production.base])if(step){
   if(step.materials===undefined&&(step.materialGrams??0)>0)throw new StockError(400,'Atualize a composição legada para identificar os materiais físicos.');
   for(const m of step.materials??[]){
    if(m.mode==='direct'){notes.push(m.name+': custo direto, sem baixa física.');continue;}
    if(m.quantity===null||!Number.isFinite(m.quantity)||m.quantity<0)throw new StockError(400,'Informe quantidades válidas na composição.');
    if(!m.materialId){if(m.quantity>0)throw new StockError(400,'Vincule o material '+m.name+' ao cadastro para registrar seu consumo.');continue;}
    const profile=this.materials.profile(m.materialId);
    if(!profile.tracked){notes.push(m.name+': sem controle físico.');continue;}
    if(!units[m.unit]||units[m.unit].dimension!==units[profile.unit].dimension)throw new StockError(400,'Unidades incompatíveis na ficha.');
    let n:bigint;try{n=parseDecimal(String(m.quantity),6)*BigInt(quantity)*factors[m.unit];}catch{throw new StockError(400,'Quantidade de material excede seis casas decimais.');}
    if(n%factors[profile.unit])throw new StockError(400,'Conversão física excede seis casas decimais.');
    n/=factors[profile.unit];safeInteger(n);totals.set(m.materialId,(totals.get(m.materialId)??0n)+n);
   }
  }
  const materials=[...totals].filter(([,n])=>n>0n).map(([materialId,n])=>{safeInteger(n);const profile=this.materials.profile(materialId),qty=formatDecimal(n,6),lots=this.materials.lots(materialId);return {materialId,name:this.materials.definition(materialId).name,unit:profile.unit,quantity:qty,lots,allocations:this.materials.suggest(materialId,qty)};});
  const item=this.db.prepare('SELECT id,prices,revision FROM stock_items WHERE product_id=? AND kind=? AND '+(p.origin==='own'?'order_id IS NULL':'order_id=?')).get(productId,p.origin,...(p.origin==='own'?[]:[orderId!])),totalBefore=item?this.balance(String(item.id)):0;
  const purchaseRevision=Number(this.db.prepare('SELECT COALESCE(MAX(id),0) n FROM material_purchases').get()!.n);
  const previewToken=createHash('sha256').update(JSON.stringify({product,quantity,orderId:orderId??null,settings,materials,totalBefore,item,purchaseRevision})).digest('hex');
  return {productId,quantity,name:p.name,materials,notes,calculation,totalBefore,copyPrices:p.origin==='own'&&(!item||totalBefore===0),prices:p.origin==='own'?(!item||totalBefore===0?p.prices:JSON.parse(String(item.prices))):null,previewToken};
 }
 manufacture(input:ManufactureInput){return this.operation(input.requestKey,'manufacture',String(input.productId),input as unknown as Json,()=>{
  const preview=this.preview(input.productId,input.quantity,input.orderId);if(preview.previewToken!==input.previewToken)throw new StockError(409,'Ficha, materiais ou estoque mudaram. Confira novamente antes de fabricar.');
  if(typeof input.allowDeficit!=='boolean'||!Array.isArray(input.materials)||input.materials.length!==preview.materials.length||new Set(input.materials.map(m=>m.materialId)).size!==input.materials.length)throw new StockError(400,'Confira a distribuição de todos os materiais.');
  const eventId=randomUUID(),item=this.product(input.productId).data.origin==='own'?this.ensureOwn(input.productId):this.ensureClient(input.productId,input.orderId!),itemId=String(item.id);
  if(preview.copyPrices)this.writePrices(itemId,this.product(input.productId).data.prices,'Fabricação com total físico exatamente zero');
  for(const required of preview.materials){const selected=input.materials.find(m=>m.materialId===required.materialId);if(!selected)throw new StockError(400,'Distribuição incompleta.');this.materials.consume(required.materialId,{requestKey:eventId+':'+required.materialId,sourceId:eventId,quantity:required.quantity,allocations:selected.allocations,allowDeficit:input.allowDeficit});}
  const now=new Date().toISOString();this.db.prepare('INSERT INTO completed_manufacturing VALUES(?,?,?,?,?,?,?,?,?)').run(eventId,input.productId,itemId,'central',input.quantity,input.orderId??null,JSON.stringify({product:this.product(input.productId).data,preview,allocations:input.materials}),this.actor,now);
  this.move(itemId,'central',input.quantity,'manufacture',eventId,'Unidades já concluídas');
  if(input.orderId){this.db.prepare("UPDATE orders SET status='production',revision=revision+1,updated_at=? WHERE id=?").run(now,input.orderId);this.db.prepare('INSERT INTO order_events(order_id,kind,snapshot,actor,registered_at) VALUES(?,?,?,?,?)').run(input.orderId,'manufactured',JSON.stringify({eventId,productId:input.productId,quantity:input.quantity}),this.actor,now);captureClientExcess(this.db,this.actor,input.orderId);}
  return {id:eventId,itemId,quantity:input.quantity,balance:this.balance(itemId),copiedPrices:preview.copyPrices};
 });}
 adjust(input:{requestKey:string;productId:number;locationId:string;expectedBalance:number;newBalance:number;reason:string;attentionId?:string}){return this.operation(input.requestKey,'adjust',String(input.productId),input as unknown as Json,()=>{const item=this.ensureOwn(input.productId),itemId=String(item.id);this.location(input.locationId);const before=this.balance(itemId,input.locationId);if(before!==stockInt(input.expectedBalance,-1000000000))throw new StockError(409,'Saldo mudou. Reabra antes de ajustar.');const after=stockInt(input.newBalance,-1000000000);const reason=stockText(input.reason,1000);this.move(itemId,input.locationId,after-before,'correction',input.requestKey,reason);if(input.attentionId){if(after<0||!matchesStockAttention(this.db,stockText(input.attentionId,100),itemId,input.locationId,'own'))throw new StockError(409,'Pendência não corresponde ao produto/local ou saldo continua negativo.');closeAttention(this.db,this.actor,input.attentionId,'Conferência de inventário: '+reason);}return {itemId,balance:after};});}
 transfer(input:{requestKey:string;itemId:string;from:string;to:string;quantity:number;expectedBalance:number;reason:string}){return this.operation(input.requestKey,'transfer',input.itemId,input as unknown as Json,()=>{const item=this.item(input.itemId);if(item.kind!=='own')throw new StockError(400,'Não transferir produto de cliente para estoque comercial.');if(input.from===input.to)throw new StockError(400,'Escolha locais diferentes.');const n=stockInt(input.quantity,1),before=this.balance(input.itemId,input.from);if(before!==stockInt(input.expectedBalance,-1000000000)||before-(input.from==='central'?reservedStock(this.db,input.itemId):0)<n)throw new StockError(409,'Saldo de origem alterado ou insuficiente.');if(this.location(input.to).kind==='session'&&this.db.prepare("SELECT 1 FROM sqlite_master WHERE name='sales_sessions'").get()&&this.db.prepare('SELECT 1 FROM sales_sessions WHERE location_id=? AND financial_closed_at IS NOT NULL').get(input.to))throw new StockError(409,'Sessão encerrada recebe somente conferência, não novo reforço.');if(this.location(input.from).kind==='partner'||this.location(input.to).kind==='partner')throw new StockError(400,'Use remessas e devoluções do ponto parceiro para preservar o acordo.');const reason=stockText(input.reason,1000);this.move(input.itemId,input.from,-n,'transfer',input.requestKey,reason);this.move(input.itemId,input.to,n,'transfer',input.requestKey,reason);return {total:this.balance(input.itemId)};});}
 prices(input:{requestKey:string;itemId:string;expectedRevision:number;prices:Prices}){return this.operation(input.requestKey,'prices',input.itemId,input as unknown as Json,()=>{const item=this.item(input.itemId);if(item.revision!==stockInt(input.expectedRevision,1))throw new StockError(409,'Preços alterados. Reabra antes de salvar.');this.writePrices(input.itemId,input.prices,'Edição explícita no Estoque');return {saved:true};});}
}
export function protectStockOrigin(db:DatabaseSync,productId:number,origin:string){if(db.prepare('SELECT 1 FROM stock_items WHERE product_id=? AND kind!=? LIMIT 1').get(productId,origin))throw new StockError(409,'Origem com histórico físico não pode mudar. Preserve o produto e seu histórico privado.');}
export function registerProductStock(app:FastifyInstance,db:DatabaseSync,actor:string){
 const stock=new ProductStock(db,actor);
 const route=(fn:(req:any)=>unknown)=>async(req:any,reply:any)=>{try{return fn(req);}catch(e){if(e instanceof StockError||e instanceof MaterialError||e instanceof OperationConflict)return reply.code(e instanceof StockError||e instanceof MaterialError?e.status:409).send({message:e.message});return reply.code(400).send({message:'Não foi possível registrar a operação. Confira os dados ou consulte o suporte.'});}};
 app.get('/api/inventory/product-stock',route(()=>stock.list()));
 app.get('/api/inventory/stock-locations',()=>db.prepare('SELECT * FROM stock_locations ORDER BY rowid').all());
 app.post('/api/inventory/manufacturing-preview',{bodyLimit:8192},route(req=>stock.preview(req.body.productId,req.body.quantity,req.body.orderId)));
 app.post('/api/inventory/manufacture',{bodyLimit:262144},route(req=>stock.manufacture(req.body)));
 app.post('/api/inventory/product-adjust',{bodyLimit:8192},route(req=>stock.adjust(req.body)));
 app.post('/api/inventory/product-transfer',{bodyLimit:8192},route(req=>stock.transfer(req.body)));
 app.put('/api/inventory/stock-prices',{bodyLimit:8192},route(req=>stock.prices(req.body)));
 app.get('/api/inventory/product-history/:id',route(req=>{stock.item(req.params.id);const before=(value:unknown)=>value===undefined?Number.MAX_SAFE_INTEGER:stockInt(Number(value),1,Number.MAX_SAFE_INTEGER);const movements=db.prepare('SELECT rowid cursor,* FROM product_stock_movements WHERE item_id=? AND rowid<? ORDER BY rowid DESC LIMIT 200').all(req.params.id,before(req.query.movementBefore)),manufacturing=db.prepare('SELECT rowid cursor,* FROM completed_manufacturing WHERE item_id=? AND rowid<? ORDER BY rowid DESC LIMIT 100').all(req.params.id,before(req.query.manufacturingBefore)),prices=db.prepare('SELECT rowid cursor,* FROM stock_price_history WHERE item_id=? AND rowid<? ORDER BY rowid DESC LIMIT 100').all(req.params.id,before(req.query.priceBefore));return {movements,manufacturing,prices,hasMore:movements.length===200||manufacturing.length===100||prices.length===100};}));
}
