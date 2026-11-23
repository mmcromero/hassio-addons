export const units={g:{label:'Gramas (g)',dimension:'mass',factor:1},kg:{label:'Quilos (kg)',dimension:'mass',factor:1000},ml:{label:'Mililitros (ml)',dimension:'volume',factor:1},l:{label:'Litros (l)',dimension:'volume',factor:1000},mm:{label:'Milímetros (mm)',dimension:'length',factor:0.1},cm:{label:'Centímetros (cm)',dimension:'length',factor:1},m:{label:'Metros (m)',dimension:'length',factor:100},un:{label:'Unidades',dimension:'count',factor:1},custom:{label:'Outra unidade',dimension:'custom',factor:1}} as const;
export type MaterialUnit=keyof typeof units;
export type MaterialDefinition={name:string;mode:'quantity'|'direct';purchaseQuantity:number|null;purchasePrice:number|null;purchaseUnit:MaterialUnit;customUnit:string};
export type MaterialUse=MaterialDefinition&{quantity:number|null;unit:MaterialUnit;materialId?:number;materialRevision?:number;purpose?:'product_packaging'};
export type SavedMaterial=MaterialDefinition&{id:number;revision:number;updatedAt:string;referencePurchaseId?:number};
const number={type:['number','null'],minimum:0,maximum:1000000000};
export const materialProperties={name:{type:'string',maxLength:200},mode:{enum:['quantity','direct']},purchaseQuantity:number,purchasePrice:number,purchaseUnit:{enum:Object.keys(units)},customUnit:{type:'string',maxLength:40}};
export const materialDefinitionSchema={type:'object',additionalProperties:false,required:Object.keys(materialProperties),properties:materialProperties};
export const materialUseSchema={allOf:[{if:{required:['purpose']},then:{required:['materialId'],properties:{mode:{const:'quantity'}}}}],type:'object',additionalProperties:false,required:[...Object.keys(materialProperties),'quantity','unit'],properties:{purpose:{const:'product_packaging'},...materialProperties,quantity:number,unit:{enum:Object.keys(units)},materialId:{type:'integer',minimum:1},materialRevision:{type:'integer',minimum:1}}};
export const emptyMaterial=():MaterialUse=>({name:'',mode:'quantity',purchaseQuantity:null,purchasePrice:null,purchaseUnit:'kg',customUnit:'',quantity:null,unit:'g'});
export function materialDefinitionIssue(value:MaterialDefinition):string|null{
 if(!value.name.trim())return 'Informe o nome do material.';
 if(value.mode==='direct')return null;
 if(value.purchaseQuantity===null||!Number.isFinite(value.purchaseQuantity)||value.purchaseQuantity<=0)return 'Informe a quantidade de referência da compra, maior que zero.';
 if(value.purchasePrice===null||!Number.isFinite(value.purchasePrice)||value.purchasePrice<0)return 'Informe o preço pago pela quantidade de referência.';
 if(!units[value.purchaseUnit])return 'Selecione a unidade da compra.';
 if(value.purchaseUnit==='custom'&&!value.customUnit.trim())return 'Informe o nome da unidade específica.';
 return null;
}
export function compatibleUnits(a:MaterialUnit,b:MaterialUnit){return !!units[a]&&!!units[b]&&units[a].dimension===units[b].dimension;}
export function materialUseCost(value:MaterialUse):{cost:number|null;issue:string|null}{
 const issue=materialDefinitionIssue(value);if(issue)return {cost:null,issue};
 if(value.quantity===null||!Number.isFinite(value.quantity)||value.quantity<0)return {cost:null,issue:'Informe a quantidade utilizada ou o custo direto do material.'};
 if(value.mode==='direct')return {cost:value.quantity,issue:null};
 if(!compatibleUnits(value.purchaseUnit,value.unit))return {cost:null,issue:'Use unidades compatíveis na compra e no consumo do material.'};
 const cost=value.purchasePrice!*value.quantity*units[value.unit].factor/(value.purchaseQuantity!*units[value.purchaseUnit].factor);
 return Number.isFinite(cost)?{cost,issue:null}:{cost:null,issue:'Custo do material fora do limite.'};
}
export function definitionOf(value:MaterialDefinition):MaterialDefinition{return {name:value.name.trim(),mode:value.mode,purchaseQuantity:value.purchaseQuantity,purchasePrice:value.purchasePrice,purchaseUnit:value.purchaseUnit,customUnit:value.customUnit.trim()};}

/** Referência atual apenas para cálculo; nunca modifica snapshots salvos. */
export function applyMaterialReferences<T extends {materials?:MaterialUse[];base?:{materials?:MaterialUse[]}|null}>(production:T,references:(MaterialDefinition&{id:number})[]):T{
 const p=structuredClone(production);
 for(const step of [p,p.base])for(const material of step?.materials??[]){const ref=references.find(r=>r.id===material.materialId);if(ref&&material.mode==='quantity')Object.assign(material,definitionOf(ref));}
 return p;
}
