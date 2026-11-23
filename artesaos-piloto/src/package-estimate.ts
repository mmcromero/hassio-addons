export type PackageData={weightGrams:string;lengthCm:string;widthCm:string;heightCm:string;boxWeightGrams:string;protectionWeightGrams:string};
export const emptyPackage=():PackageData=>({weightGrams:'',lengthCm:'',widthCm:'',heightCm:'',boxWeightGrams:'',protectionWeightGrams:''});
type PhysicalLine={quantity:string;weightGrams:number|null;lengthCm:number|null;widthCm:number|null;heightCm:number|null;packaging:string;packagingWeightGrams?:number|null;packagingLengthCm?:number|null;packagingWidthCm?:number|null;packagingHeightCm?:number|null};
export function estimatePackage(items:PhysicalLine[],pack:PackageData){
 let productGrams=0,productVolumeCm3=0,packagingGrams=0,occupiedVolumeCm3=0;const pending=new Set<string>();
 for(const item of items){const quantity=Number(item.quantity);if(!Number.isSafeInteger(quantity)||quantity<1){pending.add('Quantidade de produto pendente');continue;}
  if(item.weightGrams!==null&&item.weightGrams>0)productGrams+=quantity*item.weightGrams;else pending.add('Peso de produto pendente');
  if([item.lengthCm,item.widthCm,item.heightCm].every(n=>n!==null&&n>0))productVolumeCm3+=quantity*item.lengthCm!*item.widthCm!*item.heightCm!;else pending.add('Dimensões de produto pendentes');
  const packed=[item.packagingLengthCm,item.packagingWidthCm,item.packagingHeightCm];
  if(item.packaging==='with'&&packed.every(n=>n!==null&&n!==undefined&&n>0))occupiedVolumeCm3+=quantity*packed[0]!*packed[1]!*packed[2]!;
  else {if(item.packaging==='with')pending.add('Dimensões da embalagem individual pendentes');if([item.lengthCm,item.widthCm,item.heightCm].every(n=>n!==null&&n>0))occupiedVolumeCm3+=quantity*item.lengthCm!*item.widthCm!*item.heightCm!;}
  if(!item.packaging)pending.add('Embalagem individual a definir');
  if(item.packaging==='with'){if(item.packagingWeightGrams!==null&&item.packagingWeightGrams!==undefined&&item.packagingWeightGrams>=0)packagingGrams+=quantity*item.packagingWeightGrams;else pending.add('Peso da embalagem individual pendente');}
 }
 const numeric=(value:string)=>value.trim()!==''&&Number.isFinite(Number(value.replace(',','.')))&&Number(value.replace(',','.'))>=0?Number(value.replace(',','.')):null;
 const box=numeric(pack.boxWeightGrams),protection=numeric(pack.protectionWeightGrams);
 if(box===null)pending.add('Peso da caixa pendente');if(protection===null)pending.add('Peso da proteção pendente');
 const actualWeight=numeric(pack.weightGrams),dimensions=[pack.lengthCm,pack.widthCm,pack.heightCm].map(numeric);
 return {productGrams,productVolumeCm3,occupiedVolumeCm3,packagingGrams,estimatedGrams:productGrams+packagingGrams+(box??0)+(protection??0),pending:[...pending],actualWeight:actualWeight!==null&&actualWeight>0?actualWeight:null,actualDimensions:dimensions.every(n=>n!==null&&n>0)?dimensions as number[]:null};
}
