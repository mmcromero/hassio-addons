import type {DatabaseSync} from 'node:sqlite';
import type {MaterialDefinition} from './material-model.js';
import type {Production} from './manufacturing-model.js';
import {calculateManufacturing} from './manufacturing-model.js';
export function currentDefinition(db:DatabaseSync,id:number,fallback:MaterialDefinition):MaterialDefinition{
 const ref=db.prepare('SELECT * FROM material_cost_reference WHERE material_id=?').get(id);
 return ref?{...fallback,purchaseQuantity:Number(ref.quantity_micro)/1e6,purchasePrice:Number(ref.total_cents)/100,purchaseUnit:String(ref.unit) as MaterialDefinition['purchaseUnit']}:fallback;
}
export function currentProduction(db:DatabaseSync,value:Production){
 const p=structuredClone(value);
 for(const step of [p,p.base])for(const material of step?.materials??[]){if(material.materialId&&material.mode==='quantity')Object.assign(material,currentDefinition(db,material.materialId,material));}
 return p;
}
export function refreshCurrentCosts(db:DatabaseSync,materialIds?:number[]){
 const settings=db.prepare("SELECT data FROM area_settings WHERE area='fabricacao'").get();
 for(const row of db.prepare('SELECT id,data FROM products').all()){
  const product=JSON.parse(String(row.data));if(!product.manufacturing)continue;
  if(materialIds&&![product.manufacturing,product.manufacturing.base].some(step=>(step?.materials??[]).some((m:{materialId?:number})=>m.materialId&&materialIds.includes(m.materialId))))continue;
  const result=calculateManufacturing(currentProduction(db,product.manufacturing),settings?JSON.parse(String(settings.data)):{},true);
  db.prepare('INSERT INTO product_current_costs VALUES(?,?,?) ON CONFLICT(product_id) DO UPDATE SET data=excluded.data,updated_at=excluded.updated_at').run(row.id,JSON.stringify(result),new Date().toISOString());
 }
}
