import {transaction} from './foundation/transaction.js';
import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import type {Production,ProductionStep} from './manufacturing-model.js';
import {definitionOf,materialDefinitionIssue,type MaterialDefinition,type MaterialUse} from './material-model.js';
type State={cutoff:number;complete:boolean;changed:number;reason:string;reference?:{id:number;name:string}};
function legacy(production?:Production){return !!production&&(production.materials===undefined||!!production.base&&production.base.materials===undefined);}
function read(db:DatabaseSync):State{return JSON.parse(String(db.prepare('SELECT data FROM manufacturing_material_upgrade WHERE id=1').get()!.data));}
function save(db:DatabaseSync,state:State){db.prepare('UPDATE manufacturing_material_upgrade SET data=? WHERE id=1').run(JSON.stringify(state));}
export function applyLegacyMaterialUpgrade(db:DatabaseSync){
 const state=read(db);if(state.complete)return state;
 const rows=db.prepare('SELECT id,data,updated_at FROM products WHERE id<=? ORDER BY id').all(state.cutoff).filter(row=>legacy(JSON.parse(String(row.data)).manufacturing));
 if(!rows.length){state.complete=true;state.reason='';save(db,state);return state;}
 const first=db.prepare('SELECT id,data,revision FROM materials ORDER BY id LIMIT 1').get();
 if(!first){state.reason='Cadastre o primeiro material com uma referência de compra em gramas ou quilos para atualizar os produtos antigos.';save(db,state);return {...state,pending:rows.length};}
 const reference=JSON.parse(String(first.data)) as MaterialDefinition;
 if(materialDefinitionIssue(reference)||reference.mode!=='quantity'||!['g','kg'].includes(reference.purchaseUnit)){
  state.reason='O primeiro material cadastrado precisa ter preço e quantidade de compra em gramas ou quilos. A atualização antiga está pendente; nenhuma conversão foi inventada.';save(db,state);return {...state,pending:rows.length};
 }
 const convert=(step:ProductionStep):ProductionStep=>{
  if(step.materials!==undefined)return step;
  const materials:MaterialUse[]=[{...definitionOf(reference),materialId:Number(first.id),materialRevision:Number(first.revision),quantity:step.materialGrams,unit:'g'}];
  if(step.extras!==0)materials.push({name:'Materiais extras (cadastro anterior)',mode:'direct',purchaseQuantity:null,purchasePrice:null,purchaseUnit:'un',customUnit:'',quantity:step.extras,unit:'un'});
  return {...step,materialGrams:0,extras:0,materials};
 };
 transaction(db,()=>{
  for(const row of rows){const data=JSON.parse(String(row.data));const production=data.manufacturing as Production;
   db.prepare('INSERT OR IGNORE INTO manufacturing_material_backup(product_id,data,updated_at) VALUES (?,?,?)').run(row.id,String(row.data),String(row.updated_at));
   data.manufacturing={...convert(production),...(production.base?{base:convert(production.base)}:{})};
   db.prepare('UPDATE products SET data=?,updated_at=? WHERE id=?').run(JSON.stringify(data),new Date(Math.max(Date.now(),(Date.parse(String(row.updated_at))||0)+1)).toISOString(),row.id);
  }
  state.complete=true;state.changed+=rows.length;state.reason='';state.reference={id:Number(first.id),name:reference.name};save(db,state);
 });
 return state;
}
export function registerLegacyMaterialUpgrade(app:FastifyInstance,db:DatabaseSync){

 app.get('/api/manufacturing/material-upgrade',()=>read(db));
 app.post('/api/manufacturing/material-upgrade',()=>applyLegacyMaterialUpgrade(db));
 app.addHook('onResponse',async(req,reply)=>{if(req.method!=='GET'&&reply.statusCode<400&&!read(db).complete){try{applyLegacyMaterialUpgrade(db);}catch(error){app.log.error(error,'Não foi possível concluir a atualização dos materiais antigos.');}}});
}
