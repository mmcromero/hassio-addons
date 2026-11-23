import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {configFields,operationFields,markupRanges,validMarkup} from '../manufacturing-model.js';
import {materialDefinitionIssue,type MaterialDefinition} from '../material-model.js';
export function registerOnboarding(app:FastifyInstance,db:DatabaseSync){

 const status=()=>{
  const completed=Boolean(db.prepare('SELECT 1 FROM pilot_onboarding WHERE id=1').get());
  const companyRow=db.prepare('SELECT data FROM company_profile WHERE id=1').get();const company=companyRow?JSON.parse(String(companyRow.data)):{};
  const row=db.prepare("SELECT data FROM area_settings WHERE area='fabricacao'").get();const data:Record<string,string>=row?JSON.parse(String(row.data)):{};
  const number=(key:string)=>data[key]?.trim()?Number(data[key].replace(',','.')):NaN;
  const companyReady=typeof company.responsible==='string'&&!!company.responsible.trim()&&/^[\d+().\s-]+$/.test(company.phone??'')&&String(company.phone??'').replace(/\D/g,'').length>=7&&(!company.email||/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(company.email));
  const materialsReady=db.prepare('SELECT data FROM materials').all().some(item=>!materialDefinitionIssue(JSON.parse(String(item.data)) as MaterialDefinition));
  const hourlyReady=['energyHour','wearHour','humanHour'].some(key=>number(key)>0);
  const monthlyReady=number('productiveHours')>0;
  const operationReady=operationFields.some(([key])=>number(key)>0);
  const settingsValid=configFields.every(([key])=>Number.isFinite(number(key))&&number(key)>=0&&(!(key in markupRanges)||validMarkup(key as keyof typeof markupRanges,number(key))))&&operationFields.every(([key])=>!data[key]?.trim()||(Number.isFinite(number(key))&&number(key)>=0));
  const checks={company:companyReady,materials:materialsReady,hourly:hourlyReady,productiveHours:monthlyReady,operation:operationReady,settings:settingsValid};
  return {complete:completed,ready:companyReady,checks};
 };
 app.get('/api/onboarding',status);
 app.post('/api/onboarding/complete',(_req,reply)=>{const current=status();if(!current.ready)return reply.code(400).send({message:'Complete os dados mínimos de boas-vindas antes de continuar.',...current});db.prepare('INSERT INTO pilot_onboarding(id,completed_at) VALUES (1,?) ON CONFLICT(id) DO NOTHING').run(new Date().toISOString());return {...current,complete:true};});
 app.addHook('onRequest',async(req,reply)=>{
  const path=req.url.split('?')[0];if(!path.startsWith('/api/'))return;
  const allowed=path==='/api/company'||path==='/api/company/logo'||path==='/api/company/logo/meta'||path==='/api/onboarding'||path==='/api/onboarding/complete'||path==='/api/settings/fabricacao'||/^\/api\/materials(?:\/\d+)?$/.test(path);
  if(!allowed&&!db.prepare('SELECT 1 FROM pilot_onboarding WHERE id=1').get())return reply.code(428).send({code:'ONBOARDING_REQUIRED',message:'Conclua os dados iniciais de boas-vindas para usar o sistema.'});
 });
}
