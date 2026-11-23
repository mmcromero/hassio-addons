import {materialDeficitAttention,closeMaterialDeficit} from './attention.js';
import {syncPurchaseFinance,purchaseFinanceState} from './finance-sources.js';
import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import {randomUUID} from 'node:crypto';
import {executeOperation,OperationConflict,type Json} from './foundation/operations.js';
import {parseDecimal,formatDecimal,divideRounded,safeInteger} from './foundation/decimal.js';
import {units,type MaterialDefinition,type MaterialUnit} from './material-model.js';
import {refreshCurrentCosts,currentDefinition} from './material-current-cost.js';
type Classification='manufacturing'|'product_packaging'|'shipping';
export type MaterialProfile={tracked:boolean;unit:MaterialUnit;container:string;defaultQuantity:string;classifications:Classification[];categoryId:number|null;internalCm?:string[];externalCm?:string[];weightGrams?:string};
export class MaterialError extends Error{constructor(readonly status:number,message:string){super(message);}}
const text=(v:unknown,max:number,required=false,multiline=false)=>{if(typeof v!=='string'||v.length>max||(multiline?/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/:/[\x00-\x1f\x7f]/).test(v)||required&&!v.trim())throw new MaterialError(400,'Confira os campos de texto.');return v.trim();};
const id=(v:unknown)=>{if(!Number.isSafeInteger(v)||Number(v)<1)throw new MaterialError(400,'Identificador inválido.');return Number(v);};
const decimal=(v:unknown,scale:number)=>{try{return parseDecimal(text(v,40,true),scale);}catch{throw new MaterialError(400,'Quantidade ou valor inválido; confira a unidade e as casas decimais.');}};
const positive=(v:unknown)=>{const n=decimal(v,6);if(n<=0n)throw new MaterialError(400,'Informe quantidade maior que zero.');return safeInteger(n);};
const cents=(v:unknown)=>{const n=decimal(v,2);if(n<0n||n>10000000000n)throw new MaterialError(400,'Custo fora do limite.');return Number(n);};
const date=(v:unknown)=>{const s=text(v,10,true);if(!/^\d{4}-\d{2}-\d{2}$/.test(s)||!Number.isFinite(Date.parse(s+'T00:00:00Z'))||new Date(s+'T00:00:00Z').toISOString().slice(0,10)!==s)throw new MaterialError(400,'Data inválida.');return s;};
const factors:Record<MaterialUnit,bigint>={g:10n,kg:10000n,ml:10n,l:10000n,mm:1n,cm:10n,m:1000n,un:10n,custom:10n};
const baseUnit=(unit:MaterialUnit):MaterialUnit=>({mass:'g',volume:'ml',length:'mm',count:'un',custom:'custom'} as const)[units[unit].dimension];
function convert(value:unknown,from:MaterialUnit,to:MaterialUnit){if(!units[from]||units[from].dimension!==units[to].dimension)throw new MaterialError(400,'Unidades incompatíveis.');const n=decimal(value,6)*factors[from];if(n%factors[to]!==0n)throw new MaterialError(400,'Conversão excede seis casas decimais.');const result=safeInteger(n/factors[to]);if(result<=0)throw new MaterialError(400,'Quantidade deve ser positiva.');return result;}
export class MaterialLedger{
 constructor(readonly db:DatabaseSync,readonly actor:string){}
 definition(materialId:number){const row=this.db.prepare('SELECT data FROM materials WHERE id=?').get(materialId);if(!row)throw new MaterialError(404,'Material não encontrado.');return JSON.parse(String(row.data)) as MaterialDefinition;}
 profile(materialId:number):MaterialProfile&{revision:number}{
  const material=this.definition(materialId),row=this.db.prepare('SELECT data,revision FROM material_profiles WHERE material_id=?').get(materialId);
  return row?{...JSON.parse(String(row.data)),...(material.mode==='direct'?{tracked:false,unit:baseUnit(material.purchaseUnit)}:{}),revision:Number(row.revision)}:{tracked:material.mode==='quantity',unit:baseUnit(material.purchaseUnit),container:'unidade física',defaultQuantity:'',classifications:['manufacturing'],categoryId:null,revision:0};
 }
 balance(materialId:number,lotId?:string|null){return Number(this.db.prepare('SELECT COALESCE(SUM(delta_micro),0) n FROM material_movements WHERE material_id=?'+(lotId===undefined?'':lotId===null?' AND lot_id IS NULL':' AND lot_id=?')).get(materialId,...(typeof lotId==='string'?[lotId]:[]))!.n);}
 private operation<T extends Json>(key:unknown,action:string,sourceId:string,request:Json,work:()=>T){return executeOperation(this.db,{scope:'materials',key:text(key,100,true),actor:this.actor,action,sourceId,request},work).result;}
 saveProfile(materialId:number,input:MaterialProfile&{expectedRevision:number;requestKey:string}){
  return this.operation(input.requestKey,'profile',String(materialId),input as unknown as Json,()=>{
   const material=this.definition(materialId),previous=this.profile(materialId);
   if(input.expectedRevision!==previous.revision)throw new MaterialError(409,'Material alterado. Reabra antes de salvar.');
   if(typeof input.tracked!=='boolean'||!units[input.unit]||units[input.unit].dimension!==units[material.purchaseUnit].dimension||material.mode==='direct'&&input.tracked)throw new MaterialError(400,'Modo direto não representa quantidade física; confira a unidade.');
   if(!Array.isArray(input.classifications)||input.classifications.length<1||new Set(input.classifications).size!==input.classifications.length||input.classifications.some(c=>!['manufacturing','product_packaging','shipping'].includes(c)))throw new MaterialError(400,'Selecione classificações válidas.');
   if(input.categoryId!==null&&!this.db.prepare('SELECT 1 FROM material_categories WHERE id=?').get(id(input.categoryId)))throw new MaterialError(400,'Categoria não encontrada.');
   if(this.db.prepare('SELECT 1 FROM material_movements WHERE material_id=? LIMIT 1').get(materialId)&&(input.unit!==previous.unit||input.tracked!==previous.tracked))throw new MaterialError(409,'Unidade e controle físico não podem mudar após compras.');
   const data:MaterialProfile={tracked:input.tracked,unit:input.unit,container:text(input.container,60,true),defaultQuantity:text(input.defaultQuantity,40),classifications:input.classifications,categoryId:input.categoryId};
   if(data.defaultQuantity)positive(data.defaultQuantity);
   for(const key of ['internalCm','externalCm'] as const){const dims=input[key];if(dims!==undefined){if(!Array.isArray(dims)||dims.length!==3)throw new MaterialError(400,'Informe três dimensões em cm.');dims.forEach(positive);data[key]=dims;}}
   if(input.weightGrams!==undefined){const weight=decimal(input.weightGrams,6);if(weight<0n)throw new MaterialError(400,'Peso inválido.');safeInteger(weight);data.weightGrams=input.weightGrams;}
   const revision=previous.revision+1;this.db.prepare('INSERT INTO material_profiles VALUES(?,?,?) ON CONFLICT(material_id) DO UPDATE SET data=excluded.data,revision=excluded.revision').run(materialId,JSON.stringify(data),revision);return {revision};
  });
 }
 lots(materialId:number){return this.db.prepare('SELECT l.*,COALESCE(p.purchased_on,substr(l.registered_at,1,10)) purchased_on FROM material_lots l LEFT JOIN material_purchase_lines pl ON pl.id=l.line_id LEFT JOIN material_purchases p ON p.id=pl.purchase_id WHERE l.material_id=? ORDER BY COALESCE(p.purchased_on,substr(l.registered_at,1,10)),l.registered_at,l.rowid').all(materialId).map(row=>({...row,id:String(row.id),label:String(row.label),revision:Number(row.revision),balance:formatDecimal(BigInt(this.balance(materialId,String(row.id))),6),exhausted:!!row.closed||this.balance(materialId,String(row.id))===0}));}
 list(ids?:number[]){if(ids?.length===0)return [];return this.db.prepare('SELECT id,data FROM materials'+(ids?' WHERE id IN ('+ids.map(()=>'?').join(',')+')':'')+' ORDER BY material_key').all(...(ids??[])).map(row=>{const materialId=Number(row.id),definition=JSON.parse(String(row.data));return {id:materialId,name:definition.name,mode:definition.mode,profile:this.profile(materialId),balance:formatDecimal(BigInt(this.balance(materialId)),6),deficit:formatDecimal(BigInt(this.balance(materialId,null)),6),reference:this.db.prepare('SELECT * FROM material_cost_reference WHERE material_id=?').get(materialId)??null};});}
 private move(materialId:number,lotId:string|null,kind:string,delta:number,cost:string|null,reason:string,source:string){
  safeInteger(BigInt(this.balance(materialId))+BigInt(delta));
  const before=this.balance(materialId,lotId),after=safeInteger(BigInt(before)+BigInt(delta));
  const analytical=['loss','close'].includes(kind)?cost===null?null:safeInteger(divideRounded(BigInt(-delta)*BigInt(cost),1000000000000n)):0;
  this.db.prepare('INSERT INTO material_movements(material_id,lot_id,kind,delta_micro,before_micro,after_micro,unit_cost8,analytical_cents,reason,source_id,actor,registered_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)').run(materialId,lotId,kind,delta,before,after,cost,analytical,reason,source,this.actor,new Date().toISOString());
 }
 purchase(input:{requestKey:string;purchasedOn:string;supplier:string;notes:string;dueOn?:string;lines:{materialId:number;unit:MaterialUnit;totalCost:string;lots:{quantity:string;label:string}[]}[]}){
  return this.operation(input.requestKey,'purchase','new',input as unknown as Json,()=>{
   const purchasedOn=date(input.purchasedOn),supplier=text(input.supplier,200),notes=text(input.notes,2000,false,true),dueOn=input.dueOn?date(input.dueOn):null;
   if(!Array.isArray(input.lines)||input.lines.length<1||input.lines.length>50||new Set(input.lines.map(l=>l.materialId)).size!==input.lines.length)throw new MaterialError(400,'Informe de um a 50 materiais distintos na compra.');
   const lines=input.lines.map(line=>{
    const materialId=id(line.materialId),definition=this.definition(materialId),profile=this.profile(materialId);
    if(!profile.tracked||definition.mode==='direct')throw new MaterialError(400,'Material sem controle físico não recebe lotes.');
    if(!Array.isArray(line.lots)||line.lots.length<1||line.lots.length>200)throw new MaterialError(400,'Informe de uma a 200 unidades físicas por material.');
    const lots=line.lots.map(l=>({quantity:convert(l.quantity,line.unit,profile.unit),label:text(l.label,100)}));
    const quantity=safeInteger(lots.reduce((n,l)=>n+BigInt(l.quantity),0n)),total=cents(line.totalCost),cost=divideRounded(BigInt(total)*1000000000000n,BigInt(quantity)).toString();
    if(quantity>1000000000000000)throw new MaterialError(400,'Quantidade da compra excede o limite da referência de cálculo.');
    return {materialId,definition,profile,lots,quantity,total,cost};
   });
   const total=safeInteger(lines.reduce((n,l)=>n+BigInt(l.total),0n)),now=new Date().toISOString();
   if(total>10000000000)throw new MaterialError(400,'Total da compra fora do limite.');
   const purchaseId=Number(this.db.prepare('INSERT INTO material_purchases(purchased_on,supplier,notes,total_cents,registered_at,actor) VALUES(?,?,?,?,?,?)').run(purchasedOn,supplier,notes,total,now,this.actor).lastInsertRowid);
   const lotIds:string[]=[];
   for(const line of lines){
    const lineId=Number(this.db.prepare('INSERT INTO material_purchase_lines(purchase_id,material_id,quantity_micro,total_cents,unit,unit_cost8,snapshot) VALUES(?,?,?,?,?,?,?)').run(purchaseId,line.materialId,line.quantity,line.total,line.profile.unit,line.cost,JSON.stringify({material:line.definition,profile:line.profile,category:line.profile.categoryId?this.db.prepare('SELECT name FROM material_categories WHERE id=?').get(line.profile.categoryId)?.name:null})).lastInsertRowid);
    for(const lot of line.lots){const lotId=randomUUID();lotIds.push(lotId);this.db.prepare('INSERT INTO material_lots(id,line_id,material_id,label,registered_at,unit_cost8,quantity_micro) VALUES(?,?,?,?,?,?,?)').run(lotId,lineId,line.materialId,lot.label,now,line.cost,lot.quantity);this.move(line.materialId,lotId,'purchase',lot.quantity,line.cost,'Compra registrada',String(purchaseId));}
    this.db.prepare('INSERT INTO material_cost_reference VALUES(?,?,?,?,?,?) ON CONFLICT(material_id) DO UPDATE SET purchase_id=excluded.purchase_id,unit=excluded.unit,quantity_micro=excluded.quantity_micro,total_cents=excluded.total_cents,unit_cost8=excluded.unit_cost8').run(line.materialId,purchaseId,line.profile.unit,line.quantity,line.total,line.cost);
   }
   this.db.prepare('INSERT INTO financial_obligations(origin,origin_id,amount_cents,due_on,registered_at) VALUES(?,?,?,?,?)').run('material_purchase',purchaseId,total,dueOn,now);
   syncPurchaseFinance(this.db,purchaseId);refreshCurrentCosts(this.db,lines.map(line=>line.materialId));return {purchaseId,lotIds,totalCents:total,paymentStatus:'pending'};
  });
 }
 adjust(materialId:number,input:{requestKey:string;lotId:string|null;expectedBalance:string;newBalance:string;kind:'correction'|'loss'|'close';reason:string}){
  return this.operation(input.requestKey,'adjust',String(materialId),input as unknown as Json,()=>{
   this.definition(materialId);if(!['correction','loss','close'].includes(input.kind))throw new MaterialError(400,'Tipo de ajuste inválido.');
   const lot=input.lotId?this.db.prepare('SELECT l.* FROM material_lots l WHERE l.id=? AND l.material_id=?').get(input.lotId,materialId):null;
   if(input.lotId&&!lot)throw new MaterialError(404,'Lote não encontrado neste material.');
   if(input.lotId===null&&input.kind!=='correction')throw new MaterialError(400,'Déficit exige conciliação justificada.');
   const before=this.balance(materialId,input.lotId),expected=safeInteger(decimal(input.expectedBalance,6));if(before!==expected)throw new MaterialError(409,'Saldo mudou. Reabra antes de ajustar.');
   const after=input.kind==='close'?0:safeInteger(decimal(input.newBalance,6));
   if(input.lotId?after<0:after>0)throw new MaterialError(400,'Lote físico não pode ser negativo; déficit não pode ser positivo.');
   const reason=text(input.reason,1000,true);if(input.kind==='loss'&&after>before)throw new MaterialError(400,'Perda não aumenta saldo.');
   const raw=lot?lot.unit_cost8:this.db.prepare('SELECT unit_cost8 FROM material_cost_reference WHERE material_id=?').get(materialId)?.unit_cost8;const cost=raw===undefined||raw===null?null:String(raw);
   this.move(materialId,input.lotId,input.kind,after-before,cost,reason,input.requestKey);
   if(lot)this.db.prepare('UPDATE material_lots SET closed=?,revision=revision+1 WHERE id=?').run(input.kind==='close'?1:0,input.lotId);
   if(input.lotId===null&&input.kind==='correction')closeMaterialDeficit(this.db,this.actor,materialId,reason);
   return {balance:formatDecimal(BigInt(after),6)};
  });
 }
 opening(materialId:number,input:{requestKey:string;quantity:string;label:string;reason:string}){
  return this.operation(input.requestKey,'inventory-opening',String(materialId),input as unknown as Json,()=>{
   if(!this.profile(materialId).tracked)throw new MaterialError(400,'Material sem controle físico.');
   const quantity=positive(input.quantity),label=text(input.label,100),reason=text(input.reason,1000,true),lotId=randomUUID(),now=new Date().toISOString();
   const raw=this.db.prepare('SELECT unit_cost8 FROM material_cost_reference WHERE material_id=?').get(materialId)?.unit_cost8,cost=raw===undefined?null:String(raw);
   this.db.prepare('INSERT INTO material_lots(id,material_id,label,registered_at,unit_cost8,quantity_micro) VALUES(?,?,?,?,?,?)').run(lotId,materialId,label,now,cost,quantity);
   this.move(materialId,lotId,'correction',quantity,cost,reason,input.requestKey);return {lotId};
  });
 }
 consume(materialId:number,input:{requestKey:string;sourceId:string;quantity:string;allocations:{lotId:string;quantity:string}[];allowDeficit:boolean}){
  return this.operation(input.requestKey,'consume',String(materialId),input as unknown as Json,()=>{
   if(!this.profile(materialId).tracked)throw new MaterialError(400,'Material não possui saldo físico.');
   const total=positive(input.quantity),source=text(input.sourceId,100,true);
   if(this.db.prepare('SELECT 1 FROM material_consumption_events WHERE material_id=? AND source_id=?').get(materialId,source))throw new MaterialError(409,'Esta origem de consumo já foi registrada.');
   this.db.prepare('INSERT INTO material_consumption_events(material_id,source_id,quantity_micro,request_key,registered_at) VALUES(?,?,?,?,?)').run(materialId,source,total,input.requestKey,new Date().toISOString());
   if(!Array.isArray(input.allocations)||input.allocations.length>200||new Set(input.allocations.map(a=>a.lotId)).size!==input.allocations.length||typeof input.allowDeficit!=='boolean')throw new MaterialError(400,'Distribuição de lotes inválida.');
   let consumed=0;const raw=this.db.prepare('SELECT unit_cost8 FROM material_cost_reference WHERE material_id=?').get(materialId)?.unit_cost8;const cost=raw===undefined?null:String(raw);
   for(const allocation of input.allocations){const lotId=text(allocation.lotId,100,true),quantity=positive(allocation.quantity);const lot=this.db.prepare('SELECT closed FROM material_lots WHERE id=? AND material_id=?').get(lotId,materialId);
    if(!lot||lot.closed||this.balance(materialId,lotId)<quantity)throw new MaterialError(409,'Lote indisponível ou saldo insuficiente.');consumed=safeInteger(BigInt(consumed)+BigInt(quantity));if(consumed>total)throw new MaterialError(400,'Consumo distribuído excede o total.');this.move(materialId,lotId,'consume',-quantity,cost,'Consumo confirmado',source);
   }
   const deficit=total-consumed;if(deficit&&!input.allowDeficit)throw new MaterialError(409,'Material insuficiente: cancele ou autorize déficit.');
   if(deficit){this.move(materialId,null,'deficit',-deficit,cost,'Consumo com déficit autorizado',source);materialDeficitAttention(this.db,this.actor,materialId,source);}
   return {consumed:formatDecimal(BigInt(total),6),deficit:formatDecimal(BigInt(deficit),6)};
  });
 }
 suggest(materialId:number,quantity:string){const needed=positive(quantity),lots=this.lots(materialId).filter(l=>!l.exhausted);const single=lots.find(l=>positive(l.balance)>=needed);if(single)return [{lotId:String(single.id),quantity:formatDecimal(BigInt(needed),6)}];let remaining=needed;return lots.flatMap(l=>{const use=Math.min(positive(l.balance),remaining);remaining-=use;return use?[{lotId:String(l.id),quantity:formatDecimal(BigInt(use),6)}]:[];});}
}
export function registerMaterialLedger(app:FastifyInstance,db:DatabaseSync,actor:string){
 const ledger=new MaterialLedger(db,actor);
 const route=(fn:(req:any)=>unknown)=>async(req:any,reply:any)=>{try{return fn(req);}catch(e){if(e instanceof MaterialError||e instanceof OperationConflict)return reply.code(e instanceof MaterialError?e.status:409).send({message:e.message});return reply.code(400).send({message:'Não foi possível concluir. Confira quantidades, valores e campos.'});}};
 app.get('/api/inventory/material-references',()=>({purchaseRevision:Number(db.prepare('SELECT COALESCE(MAX(id),0) n FROM material_purchases').get()!.n),materials:db.prepare('SELECT m.id,m.data FROM materials m JOIN material_cost_reference r ON r.material_id=m.id').all().map(r=>({id:Number(r.id),...currentDefinition(db,Number(r.id),JSON.parse(String(r.data)))}))}));
 const page=(req:any,sql:string,args:(string|number)[]=[])=>{
  if(req.query.page===undefined)return db.prepare(sql).all(...args);
  const requested=Number(req.query.page);if(!Number.isSafeInteger(requested)||requested<1||requested>100000)throw new MaterialError(400,'Página inválida.');
  const total=Number(db.prepare('SELECT COUNT(*) n FROM ('+sql+')').get(...args)!.n),pages=Math.max(1,Math.ceil(total/20)),current=Math.min(requested,pages);
  return {items:db.prepare(sql+' LIMIT 20 OFFSET ?').all(...args,(current-1)*20),page:current,pages,total};
 };
 app.get('/api/inventory/materials',route(req=>{
  if(req.query.selection==='1')return ledger.list();
  const search=text(req.query.search??'',100).normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase(),classification=text(req.query.classification??'',40),category=req.query.category?id(Number(req.query.category)):null;
  if(classification&&!['manufacturing','product_packaging','shipping'].includes(classification))throw new MaterialError(400,'Classificação inválida.');
  const args:(string|number)[]=['%'+search.replace(/[!%_]/g,'!$&')+'%'];let where="m.material_key LIKE ? ESCAPE '!'";
  if(classification){where+=" AND ((pr.data IS NULL AND ?='manufacturing') OR EXISTS(SELECT 1 FROM json_each(pr.data,'$.classifications') WHERE value=?))";args.push(classification,classification);}
  if(category){where+=" AND json_extract(pr.data,'$.categoryId')=?";args.push(category);}
  const result=page({query:{...req.query,page:req.query.page??1}},'SELECT m.id FROM materials m LEFT JOIN material_profiles pr ON pr.material_id=m.id WHERE '+where+' ORDER BY m.material_key',args) as {items:Record<string,unknown>[];page:number;pages:number;total:number};
  return {...result,items:ledger.list(result.items.map(r=>Number(r.id)))};
 }));
 app.get('/api/inventory/material-categories',()=>db.prepare('SELECT * FROM material_categories ORDER BY category_key').all());
 app.post('/api/inventory/material-categories',{bodyLimit:2048},route(req=>{const name=text(req.body.name,100,true),key=name.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();return executeOperation(db,{scope:'material-categories',key:text(req.body.requestKey,100,true),actor,action:'create',sourceId:key,request:{name}},()=>{const found=db.prepare('SELECT id FROM material_categories WHERE category_key=?').get(key);return {id:found?Number(found.id):Number(db.prepare('INSERT INTO material_categories(name,category_key) VALUES(?,?)').run(name,key).lastInsertRowid)};}).result;}));
 app.put('/api/inventory/material-categories/:id',{bodyLimit:2048},route(req=>{const categoryId=id(Number(req.params.id)),name=text(req.body.name,100,true),expected=text(req.body.expectedName,100,true),categoryKey=name.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLowerCase();return executeOperation(db,{scope:'material-categories',key:text(req.body.requestKey,100,true),actor,action:'rename',sourceId:String(categoryId),request:{name,expected}},()=>{if(db.prepare('SELECT id FROM material_categories WHERE category_key=? AND id!=?').get(categoryKey,categoryId))throw new MaterialError(409,'Já existe categoria com esse nome.');const changed=db.prepare('UPDATE material_categories SET name=?,category_key=? WHERE id=? AND name=?').run(name,categoryKey,categoryId,expected);if(!changed.changes)throw new MaterialError(409,'Categoria alterada. Atualize a lista.');return {saved:true};}).result;}));
 app.put<{Params:{id:string}}>('/api/inventory/materials/:id/profile',{bodyLimit:8192},route(req=>ledger.saveProfile(id(Number(req.params.id)),req.body)));
 app.get('/api/inventory/materials/:id/detail',route(req=>{const result=ledger.list([id(Number(req.params.id))])[0];if(!result)throw new MaterialError(404,'Material não encontrado.');return result;}));
 app.get('/api/inventory/materials/:id/lots',route(req=>ledger.lots(id(Number(req.params.id)))));
 app.get('/api/inventory/materials/:id/history',route(req=>page(req,'SELECT * FROM material_movements WHERE material_id=? ORDER BY id DESC',[id(Number(req.params.id))])));
 app.get('/api/inventory/materials/:id/suggest',route(req=>ledger.suggest(id(Number(req.params.id)),req.query.quantity)));
 app.post('/api/inventory/materials/:id/opening',{bodyLimit:8192},route(req=>ledger.opening(id(Number(req.params.id)),req.body)));
 app.post('/api/inventory/materials/:id/adjust',{bodyLimit:8192},route(req=>ledger.adjust(id(Number(req.params.id)),req.body)));
 app.post('/api/inventory/materials/:id/consume',{bodyLimit:32768},route(req=>ledger.consume(id(Number(req.params.id)),req.body)));
 app.post('/api/inventory/material-purchases',{bodyLimit:262144},route(req=>ledger.purchase(req.body)));
 app.get('/api/inventory/material-purchases',route(req=>page(req,"SELECT p.*,f.id obligation_id FROM material_purchases p JOIN financial_obligations f ON f.origin='material_purchase' AND f.origin_id=p.id ORDER BY p.id DESC")));
 app.get('/api/inventory/material-purchases/:id',route(req=>{const purchaseId=id(Number(req.params.id)),purchase=db.prepare('SELECT * FROM material_purchases WHERE id=?').get(purchaseId);if(!purchase)throw new MaterialError(404,'Compra não encontrada.');return {...purchase,lines:db.prepare('SELECT * FROM material_purchase_lines WHERE purchase_id=? ORDER BY id').all(purchaseId)};}));
 app.get('/api/inventory/material-payables',(req:any)=>{const rows=db.prepare("SELECT * FROM financial_obligations WHERE origin='material_purchase' ORDER BY id DESC").all().map(r=>{const state=purchaseFinanceState(db,Number(r.origin_id),Number(r.amount_cents));return {...r,...state,payment_status:state.paymentStatus};});return req.query.summary==='1'?{total:rows.filter(r=>r.remainingCents>0).length}:rows;});
 app.get('/api/inventory/current-product-costs',()=>db.prepare('SELECT * FROM product_current_costs').all().map(r=>({productId:r.product_id,...JSON.parse(String(r.data))})));
 app.patch('/api/inventory/lots/:id/label',{bodyLimit:2048},route(req=>{const key=text(req.body.requestKey,100,true),label=text(req.body.label,100);return executeOperation(db,{scope:'lot-label',key,actor,action:'label',sourceId:text(req.params.id,100,true),request:{label,expectedRevision:id(req.body.expectedRevision)}},()=>{const previous=db.prepare('SELECT label FROM material_lots WHERE id=?').get(req.params.id);const r=db.prepare('UPDATE material_lots SET label=?,revision=revision+1 WHERE id=? AND revision=?').run(label,req.params.id,req.body.expectedRevision);if(!r.changes)throw new MaterialError(409,'Lote alterado ou inexistente.');return {saved:true,label,previousLabel:String(previous?.label??'')};}).result;}));
}
