import type {Production} from './manufacturing-model.js';
import type {MaterialProfile} from './material-ledger.js';
import {units} from './material-model.js';
import type {Dimensions} from './package-fit.js';
/** Dados físicos de referência. Ausência de dados não equivale a peso/dimensão zero. */
export function productPackaging(production:Production|undefined,profiles:{id:number;profile:MaterialProfile}[]){
 const steps=[production,production?.base],manual=steps.some(s=>(s?.packaging??0)>0),uses=steps.flatMap(s=>(s?.materials??[]).filter(m=>m.purpose==='product_packaging'&&(m.quantity??0)>0));
 const present=manual||uses.length>0;let weight=0,known=!manual;let dimensions:Dimensions|null=null;
 for(const m of uses){const p=profiles.find(p=>p.id===m.materialId)?.profile,container=p?.defaultQuantity?Number(p.defaultQuantity.replace(',','.')):p?.unit==='un'?1:null;
  if(!p){known=false;continue;}
  const quantity=m.quantity!*units[m.unit].factor/units[p.unit].factor;
  if(p.weightGrams===undefined||!container)known=false;else weight+=Number(p.weightGrams.replace(',','.'))*quantity/container;
  if(uses.length===1&&!manual&&p.unit==='un'&&quantity===1&&p.externalCm)dimensions=p.externalCm.map(n=>Number(n.replace(',','.'))) as Dimensions;
 }
 return {present,dimensions,weightGrams:known?weight:null};
}
