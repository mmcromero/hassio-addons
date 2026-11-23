import {currentDefinition} from './material-current-cost.js';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {compatibleUnits,definitionOf,materialDefinitionIssue,materialDefinitionSchema,type MaterialDefinition,type MaterialUse,materialUseSchema,materialUseCost} from './material-model.js';
const key=(name:string)=>name.trim().normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('pt-BR');
export function rememberMaterialUses(db:DatabaseSync,production?:{materials?:MaterialUse[];base?:{materials?:MaterialUse[]}|null}){
 for(const step of [production,production?.base])for(const value of step?.materials??[]){
  if(materialDefinitionIssue(value))continue;
  if(value.materialId&&db.prepare('SELECT id FROM materials WHERE id=?').get(value.materialId))continue;
  let row=db.prepare('SELECT id,revision FROM materials WHERE material_key=?').get(key(value.name));
  if(!row){const result=db.prepare('INSERT INTO materials(material_key,data,updated_at) VALUES (?,?,?)').run(key(value.name),JSON.stringify(definitionOf(value)),new Date().toISOString());row={id:result.lastInsertRowid,revision:1};}
  value.materialId=Number(row.id);value.materialRevision=Number(row.revision);
 }
}
export function registerMaterials(app:FastifyInstance,db:DatabaseSync,pilot=false){

 const list=()=>db.prepare('SELECT id,data,revision,updated_at FROM materials ORDER BY material_key').all().map(row=>({...(pilot?currentDefinition(db,Number(row.id),JSON.parse(String(row.data))):JSON.parse(String(row.data))),id:Number(row.id),revision:Number(row.revision),updatedAt:String(row.updated_at),...(pilot&&db.prepare('SELECT purchase_id FROM material_cost_reference WHERE material_id=?').get(row.id)?{referencePurchaseId:Number(db.prepare('SELECT purchase_id FROM material_cost_reference WHERE material_id=?').get(row.id)!.purchase_id)}:{})}));
 app.get('/api/materials',list);
 app.post<{Body:{materials:MaterialUse[]}}>('/api/materials/remember',{bodyLimit:131072,schema:{body:{type:'object',additionalProperties:false,required:['materials'],properties:{materials:{type:'array',minItems:1,maxItems:200,items:materialUseSchema}}}}},(req,reply)=>{
  for(const material of req.body.materials){const issue=materialUseCost(material).issue;if(issue)return reply.code(400).send({message:issue});}
  db.exec('BEGIN IMMEDIATE');try{rememberMaterialUses(db,{materials:req.body.materials});db.exec('COMMIT');}catch(error){db.exec('ROLLBACK');throw error;}
  return {ok:true};
 });

 app.post<{Body:MaterialDefinition}>('/api/materials',{schema:{body:materialDefinitionSchema}},(req,reply)=>{
  const problem=materialDefinitionIssue(req.body);if(problem)return reply.code(400).send({message:problem});
  if(db.prepare('SELECT id FROM materials WHERE material_key=?').get(key(req.body.name)))return reply.code(409).send({message:'Já existe um material com esse nome. Selecione-o na lista ou use outro nome.',field:'name'});
  const data=definitionOf(req.body);const now=new Date().toISOString();const result=db.prepare('INSERT INTO materials(material_key,data,updated_at) VALUES (?,?,?)').run(key(data.name),JSON.stringify(data),now);return {id:Number(result.lastInsertRowid),...data,revision:1,updatedAt:now};
 });
 app.put<{Params:{id:string};Body:MaterialDefinition&{expectedRevision:number}}>('/api/materials/:id',{schema:{body:{...materialDefinitionSchema,required:[...materialDefinitionSchema.required,'expectedRevision'],properties:{...materialDefinitionSchema.properties,expectedRevision:{type:'integer',minimum:1}}}}},(req,reply)=>{
  const row=db.prepare('SELECT * FROM materials WHERE id=?').get(req.params.id);if(!row)return reply.code(404).send({message:'Material não encontrado.'});
  if(row.revision!==req.body.expectedRevision)return reply.code(409).send({message:'O material mudou em outra janela. Reabra antes de editar.'});
  const problem=materialDefinitionIssue(req.body);if(problem)return reply.code(400).send({message:problem});
  if(db.prepare('SELECT id FROM materials WHERE material_key=? AND id<>?').get(key(req.body.name),req.params.id))return reply.code(409).send({message:'Já existe outro material com esse nome.',field:'name'});
  if(pilot&&db.prepare('SELECT 1 FROM material_movements WHERE material_id=? LIMIT 1').get(req.params.id)){const previous=JSON.parse(String(row.data));if(req.body.mode!==previous.mode||!compatibleUnits(req.body.purchaseUnit,previous.purchaseUnit))return reply.code(409).send({message:'Preserve modo e unidade após compras; gerencie as referências pelo Estoque.'});}
  const data=definitionOf(req.body),now=new Date().toISOString(),revision=Number(row.revision)+1;
  db.prepare('UPDATE materials SET material_key=?,data=?,revision=?,updated_at=? WHERE id=?').run(key(data.name),JSON.stringify(data),revision,now,req.params.id);return {id:Number(row.id),...data,revision,updatedAt:now};
 });
}
