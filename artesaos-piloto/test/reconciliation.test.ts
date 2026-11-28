import {test} from 'node:test';
import {DatabaseSync} from 'node:sqlite';
import assert from 'node:assert/strict';
import {mkdtempSync,rmSync} from 'node:fs';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
import {createApp} from '../server/app.js';
import {loadConfig} from '../server/config.js';
import {emptyMaterial,type MaterialUse} from '../server/material-model.js';
import {emptyProduction} from '../server/manufacturing-model.js';
import {importPayload} from '../src/ProductSettings.js';
const manufacturing={machineSeconds:3600,humanSeconds:600,materialGrams:50,extras:1,packaging:2,label:1};
const product={name:'Produto fictício',sku:'FAKE-1',origin:'own',publicAllowed:false,prices:{wholesale:null,factory:null,retail:1200},lengthCm:null,widthCm:null,heightCm:null,weightGrams:null,colors:[],sourceKeys:['https://loja.example#woocommerce:1'],family:'',description:'',category:''};
test('concilia piloto, protege preços/fabricação e parâmetros, preserva agrupamento Woo e exporta sem clientes',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-'));const options={dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local' as const};let app=await createApp(options);
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 try{
  assert.equal((await app.inject({method:'POST',url:'/api/products/import',payload:{products:[product],confirm:true}})).statusCode,200);
  const records=[{key:'linha-1',product:{...product,name:'Nome da planilha',sourceKeys:['excel:fake-1'],prices:{wholesale:2000,factory:3000,retail:4000},manufacturing,category:'Categoria > Subcategoria'}}];
  const settings={filamentKgPrice:'100',productiveHours:'100'};
  const request={records,settings,confirm:false};const preview=(await reconcile(request)).json();assert.equal(preview.valid,true);assert.equal(preview.counts.update,1);assert.equal(preview.details[0].targetId,1);assert.equal(preview.details[0].priceAfter.retail,1200);
  assert.equal((await app.inject('/api/products')).json()[0].manufacturing,undefined);assert.equal((await app.inject('/api/settings/fabricacao')).json().revision,0);
  assert.equal((await reconcile({...request,confirm:true})).statusCode,409);
  assert.equal((await reconcile({...request,confirm:true,previewToken:preview.previewToken})).statusCode,200);
  let saved=(await app.inject('/api/products')).json()[0];assert.equal(saved.name,product.name);assert.equal(saved.prices.retail,1200);assert.equal(saved.manufacturing.machineSeconds,3600);assert.ok(saved.sourceKeys.includes(product.sourceKeys[0]));assert.ok(saved.sourceKeys.includes('excel:fake-1'));assert.equal((await app.inject('/api/settings/fabricacao')).json().revision,0);
  const {id:staleId,updatedAt:staleTime,archived:unusedArchive,...staleBody}=saved;
  assert.equal((await app.inject({method:'PUT',url:'/api/products/1',headers:{'x-expected-updated-at':'stale'},payload:staleBody})).statusCode,409);
  const complement=await app.inject({method:'POST',url:'/api/products/import',payload:{products:[{...product,description:'Complemento fictício'}],confirm:true,fillMissing:true}});assert.equal(complement.statusCode,200);assert.equal(complement.json().updated,1);
  const repeat=(await reconcile(request)).json();assert.equal(repeat.counts.create,0);assert.equal(repeat.counts.preserve,1);
  const decisions=[{key:'linha-1',targetId:1,applyPrices:true,replaceManufacturing:true}];const replace={...request,decisions,applyConfiguration:true};const reviewed=(await reconcile(replace)).json();assert.equal(reviewed.details[0].priceAfter.retail,4000);
  assert.equal((await reconcile({...replace,confirm:true,previewToken:reviewed.previewToken})).statusCode,200);
  const exported=(await app.inject('/api/products/export')).json();assert.equal(exported.type,'catalog-export-v1');assert.equal(exported.products.length,1);assert.equal(exported.products[0].prices.retail,4000);assert.equal(exported.clients,undefined);assert.equal(exported.quotes,undefined);assert.equal(exported.manufacturingSettings.data.filamentKgPrice,'100');
  await app.close();app=await createApp(options);saved=(await app.inject('/api/products')).json()[0];assert.equal(saved.manufacturing.materialGrams,50);assert.equal(saved.prices.retail,4000);assert.equal((await app.inject('/api/products')).json().length,1);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});
test('catálogo alterado invalida confirmação, conflitos são revisáveis e arquivados não são reativados',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-conflicts-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 const post=(path:string,payload:object)=>app.inject({method:'POST',url:path,payload});
 try{
  const body={...product,sourceKeys:[]};await post('/api/products',body);await post('/api/products',{...body,sku:'FAKE-2'});
  const records=[{key:'linha',product:{...product,sku:'',sourceKeys:['excel:ambiguous']}}];const preview=(await post('/api/products/reconcile',{records,confirm:false})).json();assert.equal(preview.valid,false);assert.equal(preview.details[0].targetId,'review');
  const skip={records,decisions:[{key:'linha',targetId:'skip'}],confirm:false};const skipped=(await post('/api/products/reconcile',skip)).json();assert.equal(skipped.valid,true);
  await post('/api/products',{...body,name:'Outro fictício',sku:'FAKE-3'});
  assert.equal((await post('/api/products/reconcile',{...skip,confirm:true,previewToken:skipped.previewToken})).statusCode,409);
  await app.inject({method:'DELETE',url:'/api/products/1'});const archiveRecord=[{key:'arquivo',product:{...product,sourceKeys:['excel:archived']}}];const archived=(await post('/api/products/reconcile',{records:archiveRecord,decisions:[{key:'arquivo',targetId:1}],confirm:false})).json();assert.equal(archived.valid,false);
  assert.equal((await app.inject('/api/products/export')).json().products.filter((p:{archived:boolean})=>p.archived).length,1);
  const reservedOwn=[{key:'reserved',product:{...product,category:'Produtos de cliente',sourceKeys:['excel:reserved']}}];assert.equal((await post('/api/products/reconcile',{records:reservedOwn,confirm:false})).json().valid,false);
  const differentCategories=[{key:'cat-a',product:{...product,name:'Outra peça fictícia',sku:'',category:'Categoria A',sourceKeys:['excel:cat-a']}},{key:'cat-b',product:{...product,name:'Outra peça fictícia',sku:'',category:'Categoria B',sourceKeys:['excel:cat-b']}}];assert.equal((await post('/api/products/reconcile',{records:differentCategories,confirm:false})).json().valid,true);
  const prepared=importPayload(JSON.stringify({type:'manufacturing-import-v1',records,settings:{},report:{summary:{records:149},warnings:['Conferir duplicidades']}}));assert.equal(prepared.type,'reconciliation');if(prepared.type==='reconciliation')assert.equal(prepared.report?.summary?.records,149);assert.throws(()=>importPayload('{"type":"catalog-export-v1","products":[]}'),/conferência/);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});


test('prévia compartilha referências de materiais, preserva snapshots e invalida token se a biblioteca mudar',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-plan-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 try{
  const pla=(quantity:number):MaterialUse=>({...emptyMaterial(),name:'PLA genérico',purchaseQuantity:1,purchasePrice:130,purchaseUnit:'kg',quantity,unit:'g'});
  const extra:MaterialUse={...emptyMaterial(),name:'Materiais extras',mode:'direct',purchaseQuantity:null,purchasePrice:null,purchaseUnit:'un',quantity:2,unit:'un'};
  const step=(quantity:number,withExtra:boolean)=>({...emptyProduction(),machineSeconds:3600,humanSeconds:600,materialGrams:0,extras:0,packaging:0,label:0,materials:[pla(quantity),...(withExtra?[extra]:[])]});
  const records: {key:string;product:object}[]=[];
  for(let index=1;index<=146;index++){
   const manufacturing={...step(17.3,index<=83),...(index<=6?{base:step(47,false)}:{})};
   records.push({key:'produto-'+index,product:{...product,name:'Produto de fabricação '+index,sku:'IMP-'+String(index).padStart(3,'0'),category:'Headshop > Teste',sourceKeys:['excel:import:produto-'+index],prices:{wholesale:1000,factory:2000,retail:3000},manufacturing}});
  }
  for(let index=1;index<=3;index++)records.push({key:'kit-'+index,product:{...product,name:'Kit sem fabricação '+index,sku:'KIT-'+index,category:'Headshop > Teste',sourceKeys:['excel:import:kit-'+index],prices:{wholesale:5000,factory:6000,retail:7000}}});
  const request={records,confirm:false};
  const first=(await reconcile(request)).json();
  assert.equal(first.valid,true);assert.equal(first.counts.create,149);
  assert.equal(first.materialCounts.create,2);assert.equal(first.materialCounts.reuse,0);
  assert.equal(first.materials.find((item:any)=>item.name==='PLA genérico').uses,152);
  assert.equal(first.materials.find((item:any)=>item.name==='Materiais extras').uses,83);
  assert.equal((await app.inject('/api/products')).json().length,0);
  assert.equal((await app.inject('/api/materials')).json().length,0);
  const created=await app.inject({method:'POST',url:'/api/materials',payload:{name:'PLA genérico',mode:'quantity',purchaseQuantity:1,purchasePrice:140,purchaseUnit:'kg',customUnit:''}});
  assert.equal(created.statusCode,200,created.body);const existingId=created.json().id;
  const stale=await reconcile({...request,confirm:true,previewToken:first.previewToken});assert.equal(stale.statusCode,409);
  const second=(await reconcile(request)).json();
  const plaPlan=second.materials.find((item:any)=>item.name==='PLA genérico');
  assert.equal(plaPlan.action,'reuse');assert.equal(plaPlan.materialId,existingId);assert.equal(plaPlan.current.purchasePrice,140);assert.ok(plaPlan.warnings.length>0);
  assert.equal(second.materialCounts.create,1);assert.equal(second.materialCounts.reuse,1);
  const confirmed=await reconcile({...request,confirm:true,previewToken:second.previewToken});assert.equal(confirmed.statusCode,200,confirmed.body);
  const products=(await app.inject('/api/products')).json();assert.equal(products.length,149);
  assert.equal(products.filter((item:any)=>item.manufacturing).length,146);
  assert.equal(products.filter((item:any)=>!item.manufacturing).length,3);
  const uses:any[]=[];for(const item of products)for(const part of [item.manufacturing,item.manufacturing?.base])for(const material of part?.materials??[])uses.push(material);
  const plaUses=uses.filter((item:any)=>item.name==='PLA genérico');assert.equal(plaUses.length,152);
  assert.deepEqual([...new Set(plaUses.map((item:any)=>item.materialId))],[existingId]);
  assert.ok(plaUses.every((item:any)=>item.purchasePrice===130&&item.materialRevision===1));
  const extraUses=uses.filter((item:any)=>item.name==='Materiais extras');assert.equal(extraUses.length,83);
  assert.equal(new Set(extraUses.map((item:any)=>item.materialId)).size,1);
  assert.equal((await app.inject('/api/materials')).json().length,2);
  assert.equal((await app.inject('/api/settings/fabricacao')).json().revision,0);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('conciliação bloqueia material com unidade de consumo incompatível antes de gravar',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-invalid-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 try{
  const invalidMaterial:MaterialUse={...emptyMaterial(),name:'PLA incompatível',purchaseQuantity:1,purchasePrice:130,purchaseUnit:'kg',quantity:20,unit:'ml'};
  const invalidProduct={...product,name:'Produto com unidade incompatível',sku:'INVALID-UNIT',sourceKeys:['excel:invalid-unit'],prices:{wholesale:1000,factory:2000,retail:3000},manufacturing:{...emptyProduction(),machineSeconds:100,humanSeconds:60,materials:[invalidMaterial]}};
  const request={records:[{key:'invalid-unit',product:invalidProduct}],confirm:false};
  const preview=(await reconcile(request)).json();assert.equal(preview.valid,false);assert.match(preview.details[0].errors.join(' '),/unidades compatíveis/);
  assert.equal((await app.inject('/api/materials')).json().length,0);assert.equal((await app.inject('/api/products')).json().length,0);
  const confirmed=await reconcile({...request,confirm:true,previewToken:preview.previewToken});assert.equal(confirmed.statusCode,400);
  assert.equal((await app.inject('/api/materials')).json().length,0);assert.equal((await app.inject('/api/products')).json().length,0);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('referência existente com unidade incompatível não é reutilizada',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-ref-conflict-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 try{
  const created=await app.inject({method:'POST',url:'/api/materials',payload:{name:'PLA genérico',mode:'quantity',purchaseQuantity:1,purchasePrice:140,purchaseUnit:'l',customUnit:''}});
  assert.equal(created.statusCode,200,created.body);
  const material:MaterialUse={...emptyMaterial(),name:'PLA genérico',purchaseQuantity:1,purchasePrice:130,purchaseUnit:'kg',quantity:20,unit:'g'};
  const incoming={...product,name:'Produto com referência incompatível',sku:'REF-CONFLICT',sourceKeys:['excel:ref-conflict'],prices:{wholesale:1000,factory:2000,retail:3000},manufacturing:{...emptyProduction(),machineSeconds:100,humanSeconds:60,materials:[material]}};
  const preview=(await app.inject({method:'POST',url:'/api/products/reconcile',payload:{records:[{key:'ref-conflict',product:incoming}],confirm:false}})).json();
  assert.equal(preview.valid,false);assert.match(preview.details[0].errors.join(' '),/tipo\\/unidade incompatível/);
  assert.equal((await app.inject('/api/products')).json().length,0);assert.equal((await app.inject('/api/materials')).json().length,1);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('definições de compra divergentes para o mesmo material no arquivo bloqueiam ambas as linhas',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-file-conflict-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 try{
  const make=(name:string,key:string,price:number)=>({ ...product,name,sku:key,sourceKeys:['excel:'+key],prices:{wholesale:1000,factory:2000,retail:3000},manufacturing:{...emptyProduction(),machineSeconds:100,humanSeconds:60,materials:[{...emptyMaterial(),name:'PLA genérico',purchaseQuantity:1,purchasePrice:price,purchaseUnit:'kg',quantity:20,unit:'g'}]}});
  const records=[{key:'material-a',product:make('Produto A','A',130)},{key:'material-b',product:make('Produto B','B',140)}];
  const preview=(await app.inject({method:'POST',url:'/api/products/reconcile',payload:{records,confirm:false}})).json();
  assert.equal(preview.valid,false);assert.equal(preview.details.every((item:any)=>item.errors.some((error:string)=>error.includes('definições incompatíveis'))),true);
  assert.equal(preview.materials[0].errors.length>0,true);assert.equal((await app.inject('/api/products')).json().length,0);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('nomes iguais com um SKU ausente não geram falso conflito entre produtos distintos',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-name-sku-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local'});
 try{
  const records=[
   {key:'max360-smokinha',product:{...product,name:'Smokinha',sku:'',category:'Headshop > Dichavadores',sourceKeys:['excel:max360:smokinha']}},
   {key:'dc050-smokinha',product:{...product,name:'Smokinha',sku:'DC-50',category:'Headshop > Dichavadores',sourceKeys:['excel:dc050:smokinha']}},
  ];
  const preview=(await app.inject({method:'POST',url:'/api/products/reconcile',payload:{records,confirm:false}})).json();
  assert.equal(preview.valid,true);assert.equal(preview.counts.create,2);assert.equal(preview.counts.conflicts,0);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});
test('prévia invalida o token quando categorias ou configurações mudam',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-token-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local',logRequests:false});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 const request={records:[{key:'token-categorias',product:{...product,name:'Produto de token',sku:'TOKEN-1',sourceKeys:['excel:token-categorias']}}],settings:{humanHour:'20'},confirm:false};
 try{
  const first=(await reconcile(request)).json();assert.equal(first.valid,true);
  const category=await app.inject({method:'POST',url:'/api/categories',payload:{path:'Headshop > Importação > Teste'}});assert.equal(category.statusCode,200,category.body);
  assert.equal((await reconcile({...request,confirm:true,previewToken:first.previewToken})).statusCode,409);
  const second=(await reconcile(request)).json();
  const current=(await app.inject('/api/settings/fabricacao')).json();
  const changed=await app.inject({method:'PUT',url:'/api/settings/fabricacao',payload:{data:{...current.data,humanHour:'21'},expectedRevision:current.revision}});
  assert.equal(changed.statusCode,200,changed.body);
  assert.equal((await reconcile({...request,confirm:true,previewToken:second.previewToken})).statusCode,409);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('referência de compra de material invalida token e é reutilizada sem sobrescrita',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-purchase-'));
 const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local',pilotFeatures:true,logRequests:false});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 const db=new DatabaseSync(join(dir,'validation.sqlite'));
 db.prepare('INSERT INTO pilot_onboarding VALUES(1,?)').run('synthetic');
 db.close();
 try{
  const created=await app.inject({method:'POST',url:'/api/materials',payload:{name:'PLA teste',mode:'quantity',purchaseQuantity:1,purchasePrice:130,purchaseUnit:'kg',customUnit:''}});
  assert.equal(created.statusCode,200,created.body);
  const material=(await app.inject('/api/materials')).json().find((item:any)=>item.name==='PLA teste');
  assert.ok(material);
  const materialUse:MaterialUse={...emptyMaterial(),name:'PLA teste',mode:'quantity',purchaseQuantity:1,purchasePrice:130,purchaseUnit:'kg',customUnit:'',quantity:50,unit:'g'};
  const manufacturing={...emptyProduction(),machineSeconds:0,humanSeconds:0,materials:[materialUse]};
  const incoming={...product,name:'Produto com PLA',sku:'PLA-TESTE',sourceKeys:['excel:produto-pla'],manufacturing};
  const request={records:[{key:'produto-pla',product:incoming}],settings:{},confirm:false};
  const first=(await reconcile(request)).json();assert.equal(first.valid,true);assert.equal(first.materials[0].action,'reuse');
  const purchase=await app.inject({method:'POST',url:'/api/inventory/material-purchases',payload:{requestKey:'purchase-pla',purchasedOn:'2026-11-28',supplier:'Fornecedor teste',notes:'',lines:[{materialId:material.id,unit:'kg',totalCost:'140.00',lots:[{quantity:'1',label:'Rolo A'}]}]}});
  assert.equal(purchase.statusCode,200,purchase.body);
  assert.equal((await reconcile({...request,confirm:true,previewToken:first.previewToken})).statusCode,409);
  const refreshed=(await reconcile(request)).json();
  assert.equal(refreshed.materials[0].hasPurchaseReference,true);assert.equal(refreshed.materials[0].current.purchasePrice,140);
  const confirmed=await reconcile({...request,confirm:true,previewToken:refreshed.previewToken});assert.equal(confirmed.statusCode,200,confirmed.body);
  const saved=(await app.inject('/api/products')).json().find((item:any)=>item.name==='Produto com PLA');
  assert.equal(saved.manufacturing.materials[0].materialId,material.id);
  assert.equal(saved.manufacturing.materials[0].purchasePrice,130);
  const current=(await app.inject('/api/materials')).json().find((item:any)=>item.id===material.id);
  assert.equal(current.purchasePrice,140);
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('índice product_sources participa da conciliação e do token de prévia',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-source-index-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local',logRequests:false});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 const db=new DatabaseSync(join(dir,'validation.sqlite'));
 try{
  const created=await app.inject({method:'POST',url:'/api/products/import',payload:{products:[product],confirm:true}});assert.equal(created.statusCode,200,created.body);
  const existing=(await app.inject('/api/products')).json()[0];
  const row=db.prepare('SELECT data FROM products WHERE id=?').get(existing.id) as {data:string};
  const stored=JSON.parse(row.data);stored.sourceKeys=[];
  db.prepare('UPDATE products SET data=? WHERE id=?').run(JSON.stringify(stored),existing.id);
  const incoming={...product,name:'Produto vindo da planilha',sku:'FAKE-2',sourceKeys:[product.sourceKeys[0],'excel:source-index']};
  const request={records:[{key:'linha-index',product:incoming}],settings:{},confirm:false};
  const preview=(await reconcile(request)).json();
  assert.equal(preview.valid,true);assert.equal(preview.counts.update,1);assert.equal(preview.details[0].targetId,existing.id);
  const confirmed=await reconcile({...request,confirm:true,previewToken:preview.previewToken});assert.equal(confirmed.statusCode,200,confirmed.body);
  const saved=(await app.inject('/api/products')).json()[0];
  assert.equal(saved.id,existing.id);assert.ok(saved.sourceKeys.includes('excel:source-index'));
  assert.equal((await app.inject('/api/products')).json().length,1);
  const staleRequest={records:[{key:'linha-stale',product:{...product,name:'Produto sem vínculo',sku:'FAKE-STALE',sourceKeys:['excel:stale']}}],settings:{},confirm:false};
  const stalePreview=(await reconcile(staleRequest)).json();
  db.prepare('INSERT INTO product_sources(source_key,product_id) VALUES (?,?)').run('https://loja.example#woocommerce:late',existing.id);
  const stale=await reconcile({...staleRequest,confirm:true,previewToken:stalePreview.previewToken});
  assert.equal(stale.statusCode,409);assert.equal((await app.inject('/api/products')).json().length,1);
 }finally{db.close();await app.close();rmSync(dir,{recursive:true,force:true});}
});

test('definições equivalentes normalizam unidades; escalas incompatíveis são bloqueadas',async()=>{
 const dir=mkdtempSync(join(tmpdir(),'reconciliation-material-units-'));const app=await createApp({dataDir:dir,staticDir:loadConfig({}).staticDir,mode:'local',logRequests:false});
 const reconcile=(body:object)=>app.inject({method:'POST',url:'/api/products/reconcile',payload:body});
 const record=(key:string,sku:string,purchaseQuantity:number,purchaseUnit:'kg'|'g')=>({
  key,product:{...product,name:'Produto '+sku,sku,sourceKeys:['excel:'+key],manufacturing:{...emptyProduction(),machineSeconds:0,humanSeconds:0,materials:[{...emptyMaterial(),name:'PLA compartilhado',purchaseQuantity,purchasePrice:130,purchaseUnit,customUnit:'',quantity:50,unit:'g'}]}}
 });
 try{
  const equivalent=(await reconcile({records:[record('equiv-a','EQUIV-A',1,'kg'),record('equiv-b','EQUIV-B',1000,'g')],settings:{},confirm:false})).json();
  assert.equal(equivalent.valid,true);assert.equal(equivalent.materials.length,1);assert.equal(equivalent.materials[0].uses,2);
  const inconsistent=(await reconcile({records:[record('scale-a','SCALE-A',1,'kg'),record('scale-b','SCALE-B',1,'g')],settings:{},confirm:false})).json();
  assert.equal(inconsistent.valid,false);
  assert.ok(inconsistent.details.every((detail:any)=>detail.errors.some((error:string)=>error.includes('definições incompatíveis'))));
 }finally{await app.close();rmSync(dir,{recursive:true,force:true});}
});
