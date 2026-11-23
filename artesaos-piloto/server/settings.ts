import {minimumSettings} from './pilot/minimum-settings.js';
import {configFields,operationFields,markupRanges,validMarkup} from './manufacturing-model.js';
import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
const areas=['fabricacao','orcamentos','clientes','produtos'];
const params={type:'object',required:['area'],properties:{area:{enum:areas}}};
const manufacturingFields=Object.fromEntries([...configFields,...operationFields].map(([key])=>[key,{type:'string',maxLength:20,pattern:'^(|[0-9]+([.,][0-9]+)?)$'}]));
const fields={...manufacturingFields,filamentKgPrice:{type:'string',maxLength:20,pattern:'^(|[0-9]+([.,][0-9]+)?)$'},quotesPerPage:{enum:['10','15','20','30','40','50','all']},clientsPerPage:{enum:['10','20','30','40','50','all']},productsPerPage:{enum:['10','20','30','40','50','all']},originPostal:{type:'string',maxLength:20,pattern:'^(|[0-9]{5}-?[0-9]{3})$'},dailyCapacity:{type:'string',maxLength:1000},workDays:{type:'string',maxLength:1000},machines:{type:'string',maxLength:2000},queue:{type:'string',maxLength:2000},contingency:{type:'string',maxLength:1000}};
export function registerSettings(app:FastifyInstance,db:DatabaseSync,pilotFeatures=false){


 app.get<{Params:{area:string}}>('/api/settings/:area',{schema:{params}},req=>{

  const row=db.prepare('SELECT data,revision FROM area_settings WHERE area=?').get(req.params.area);
  if(!row)return {data:{},revision:0};const data=JSON.parse(String(row.data));if(req.params.area==='fabricacao')delete data.filamentKgPrice;return {data,revision:row.revision};
 });
 app.put<{Params:{area:string};Body:{data:Record<string,string>;expectedRevision:number}}>('/api/settings/:area',{bodyLimit:16384,schema:{params,body:{type:'object',additionalProperties:false,required:['data','expectedRevision'],properties:{expectedRevision:{type:'integer',minimum:0},data:{type:'object',additionalProperties:false,properties:fields}}}}},(req,reply)=>{
  const allowed=req.params.area==='orcamentos'?['originPostal','quotesPerPage']:req.params.area==='fabricacao'?['filamentKgPrice','dailyCapacity','workDays','machines','queue','contingency',...configFields.map(([key])=>key),...operationFields.map(([key])=>key)]:req.params.area==='clientes'?['clientsPerPage']:['productsPerPage'];
  if(Object.keys(req.body.data).some(k=>!allowed.includes(k)))return reply.code(400).send({message:'Configuração não pertence a esta área.'});
  if(pilotFeatures&&req.params.area==='fabricacao')req.body.data=minimumSettings(req.body.data);
  for(const key of Object.keys(markupRanges) as (keyof typeof markupRanges)[]){const raw=req.body.data[key];if(raw!==undefined&&raw!==''&&!validMarkup(key,Number(raw.replace(',','.'))))return reply.code(400).send({message:`Use ${markupRanges[key].min} a ${markupRanges[key].max}, com uma casa decimal.`,field:key});}
  const row=db.prepare('SELECT revision FROM area_settings WHERE area=?').get(req.params.area);
  const revision=Number(row?.revision??0);
  if(revision!==req.body.expectedRevision)return reply.code(409).send({message:'Estas configurações foram alteradas em outra janela. Reabra a página antes de salvar.'});
  db.prepare('INSERT INTO area_settings(area,data,revision) VALUES (?,?,?) ON CONFLICT(area) DO UPDATE SET data=excluded.data,revision=excluded.revision').run(req.params.area,JSON.stringify(req.body.data),revision+1);
  return {revision:revision+1,...(pilotFeatures?{data:req.body.data}:{})};
 });
}
