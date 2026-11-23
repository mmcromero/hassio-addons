/** Encaixe conservador por prateleiras, com seis orientações ortogonais.
 * Só uma disposição construída é sugerida; falhar não prova impossibilidade.
 * Não considera compressão, encaixe de peças ocas ou formas não retangulares. */
export type Dimensions=[number,number,number];
export type PhysicalItem={quantity:number;dimensions:Dimensions|null;weightGrams:number|null};
export function fitPackage(items:PhysicalItem[],inside:Dimensions|null,clearance:number){
 const unknown=!inside||!items.length||items.some(i=>!i.dimensions||!Number.isInteger(i.quantity)||i.quantity<1);
 if(unknown)return {fits:false,status:'Dados insuficientes para sugerir encaixe',placements:[] as Dimensions[]};
 const total=items.reduce((n,i)=>n+i.quantity,0);
 if(total>2000)return {fits:false,status:'Mais de 2.000 unidades: conferir acondicionamento manualmente',placements:[] as Dimensions[]};
 const space=inside!.map(n=>n-2*clearance);
 if(space.some(n=>n<=0))return {fits:false,status:'Folga de proteção ocupa a caixa',placements:[] as Dimensions[]};
 const pieces=items.flatMap(i=>Array.from({length:i.quantity},()=>i.dimensions!)).sort((a,b)=>Math.max(...b)-Math.max(...a));
 let x=0,y=0,z=0,row=0,layer=0;const placements:Dimensions[]=[];
 for(const d of pieces){const orientations:Dimensions[]=[[d[0],d[1],d[2]],[d[0],d[2],d[1]],[d[1],d[0],d[2]],[d[1],d[2],d[0]],[d[2],d[0],d[1]],[d[2],d[1],d[0]]];
  const find=()=>orientations.filter(o=>o[0]+x<=space[0]+1e-8&&o[1]+y<=space[1]+1e-8&&o[2]+z<=space[2]+1e-8).sort((a,b)=>a[2]-b[2]||a[1]-b[1])[0];
  let o=find();if(!o){x=0;y+=row;row=0;o=find();}if(!o){x=0;y=0;z+=layer;row=0;layer=0;o=find();}
  if(!o)return {fits:false,status:'Encaixe não demonstrado: conferir outra disposição ou caixa',placements:[] as Dimensions[]};
  placements.push(o);x+=o[0];row=Math.max(row,o[1]);layer=Math.max(layer,o[2]);
 }
 return {fits:true,status:'Disposição retangular estimada; confirme o encaixe real',placements};
}
