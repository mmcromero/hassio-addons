import {materialUseCost,materialUseSchema,type MaterialUse} from './material-model.js';
export type ProductionStep={machineSeconds:number|null;humanSeconds:number|null;materialGrams:number|null;extras:number|null;packaging:number|null;label:number|null;materials?:MaterialUse[]};
export type Production=ProductionStep&{base?:ProductionStep|null};
export const emptyProduction=():Production=>({machineSeconds:null,humanSeconds:null,materialGrams:0,extras:0,packaging:0,label:0,materials:[]});
export const configFields=[['energyHour','Energia por hora de máquina (R$)'],['wearHour','Desgaste por hora de máquina (R$)'],['humanHour','Valor da hora humana (R$)'],['productiveHours','Horas produtivas por mês'],['wholesaleMarkup','Multiplicador Atacado'],['factoryMarkup','Multiplicador Loja de fábrica'],['retailMarkup','Multiplicador Varejo']] as const;
export const markupRanges={wholesaleMarkup:{min:1.5,max:2},factoryMarkup:{min:2,max:3},retailMarkup:{min:3,max:5}} as const;
export function validMarkup(key:keyof typeof markupRanges,value:number){const range=markupRanges[key];return Number.isFinite(value)&&value>=range.min&&value<=range.max&&Math.abs(value*10-Math.round(value*10))<1e-8;}
export const operationFields=[['internetCost','Internet (R$/mês)'],['pluginsCost','Plugins (R$/mês)'],['toolsCost','Ferramentas (R$/mês)'],['energyCost','Energia geral (R$/mês)'],['maintenanceCost','Manutenção (R$/mês)'],['otherCost','Outras despesas (R$/mês)']] as const;
export const productionSchema={allOf:[{if:{required:['materials'],properties:{materials:{type:'array',contains:{type:'object',required:['purpose'],properties:{purpose:{const:'product_packaging'}}}}}},then:{properties:{packaging:{const:0}}}}],type:'object',additionalProperties:false,required:['machineSeconds','humanSeconds','materialGrams','extras','packaging','label'],properties:{materials:{type:'array',maxItems:100,items:materialUseSchema},machineSeconds:{type:['integer','null'],minimum:0,maximum:3600000000},humanSeconds:{type:['integer','null'],minimum:0,maximum:3600000000},materialGrams:{type:['number','null'],minimum:0,maximum:1000000},extras:{type:['number','null'],minimum:0,maximum:100000000},packaging:{type:['number','null'],minimum:0,maximum:100000000},label:{type:['number','null'],minimum:0,maximum:100000000}}};
export const manufacturingSchema={...productionSchema,properties:{...productionSchema.properties,base:{anyOf:[{type:'null'},productionSchema]}}};
const parse=(raw:string|undefined)=>raw?.trim()&&/^\d+([.,]\d+)?$/.test(raw.trim())?Number(raw.replace(',','.')):null;
export function calculateManufacturing(production:Production,settings:Record<string,string>,manualOperatingFallback=false){
 const pending:string[]=[];const config:Record<string,number>={};
 const legacy=[production,production.base].some(step=>step&&step.materials===undefined);
 if(legacy){const value=parse(settings.filamentKgPrice);if(value===null||!Number.isFinite(value)||value<0)pending.push('Atualize os materiais dos cadastros antigos nas configurações de Fabricação.');else config.filamentKgPrice=value;}
 for(const [key,label] of configFields){const value=parse(settings[key]);if(value===null||!Number.isFinite(value)||value<0||(key in markupRanges&&!validMarkup(key as keyof typeof markupRanges,value))||(['productiveHours','wholesaleMarkup','factoryMarkup','retailMarkup'].includes(key)&&value===0))pending.push(label);else config[key]=value;}
 let operatingTotal=0;for(const [key,label] of operationFields){const raw=settings[key];const value=raw?.trim()?parse(raw):0;if(value===null||!Number.isFinite(value))pending.push(label);else operatingTotal+=value;}
 const operatingHour=config.productiveHours?operatingTotal/config.productiveHours:null;
 const cost=(step:ProductionStep,name:string)=>{
  for(const key of ['machineSeconds','humanSeconds','packaging','label',...(step.materials===undefined?['materialGrams','extras']:[])] as (keyof ProductionStep)[]){const value=step[key];if(value===null||typeof value!=='number'||!Number.isFinite(value)||value<0)pending.push(`${name}: ${({machineSeconds:'tempo de máquina',humanSeconds:'tempo de trabalho humano',materialGrams:'material em gramas',extras:'materiais extras',packaging:'embalagem de fabricação',label:'etiqueta'} as Record<string,string>)[key]??'dado inválido'}`);}
  if((step.materials??[]).some(m=>m.purpose==='product_packaging')){if(step.packaging!==0)pending.push(name+': escolha embalagem cadastrada OU custo manual, sem duplicar.');if((step.materials??[]).some(m=>m.purpose==='product_packaging'&&(!m.materialId||m.mode!=='quantity')))pending.push(name+': vincule a embalagem cadastrada com unidade física.');}
  let materialsCost=0;
  if(step.materials!==undefined){for(const material of step.materials){const result=materialUseCost(material);if(result.issue)pending.push(`${name} — ${material.name||'Material'}: ${result.issue}`);else materialsCost+=result.cost!;}}
  if(pending.length)return null;
  const machineHours=step.machineSeconds!/3600,humanHours=step.humanSeconds!/3600;
  if(step.materials===undefined)return step.materialGrams!*config.filamentKgPrice/1000+machineHours*(config.energyHour+config.wearHour)+(manualOperatingFallback&&machineHours===0?humanHours:machineHours)*operatingHour!+humanHours*config.humanHour+step.extras!+step.packaging!+step.label!;
  return materialsCost+machineHours*(config.energyHour+config.wearHour)+(manualOperatingFallback&&machineHours===0?humanHours:machineHours)*operatingHour!+humanHours*config.humanHour+step.packaging!+step.label!;
 };
 const {base,...main}=production;const mainCost=cost(main,'Produção'),baseCost=base?cost(base,'Etapa adicional'):0;
 if(pending.length||mainCost===null||baseCost===null)return {pending,operatingTotal,operatingHour,cost:null,prices:null,rawPrices:null};
 const total=mainCost+baseCost;
 const rawPrices={wholesale:total*config.wholesaleMarkup,factory:total*config.factoryMarkup,retail:total*config.retailMarkup};
 const hasMaterialsList=production.materials!==undefined||production.base?.materials!==undefined;
 const rounded=(value:number)=>Math.round((value+(hasMaterialsList?Number.EPSILON*Math.max(1,Math.abs(value)):0))*100);
 const prices={wholesale:rounded(rawPrices.wholesale),factory:rounded(rawPrices.factory),retail:rounded(rawPrices.retail)};
 if(Object.values(prices).some(value=>!Number.isSafeInteger(value)||value>10000000000))return {pending:['Resultado fora do limite de preços do catálogo'],operatingTotal,operatingHour,cost:null,prices:null,rawPrices:null};
 return {pending,operatingTotal,operatingHour,cost:total,prices,rawPrices};
}
export function durationParts(seconds:number|null){const n=seconds??0;return {hours:Math.floor(n/3600),minutes:Math.floor(n%3600/60),seconds:n%60};}

export type DurationInput={hours:string;minutes:string;seconds:string};
export function durationSeconds(parts:DurationInput):number|null{
 if(Object.values(parts).every(value=>value===''))return null;
 if(Object.values(parts).some(value=>value!==''&&!/^\d+$/.test(value)))return null;
 const hours=Number(parts.hours),minutes=Number(parts.minutes),seconds=Number(parts.seconds);
 if(hours>999999||minutes>59||seconds>59)return null;
 const total=hours*3600+minutes*60+seconds;return Number.isSafeInteger(total)?total:null;
}
