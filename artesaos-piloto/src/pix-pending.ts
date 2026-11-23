/** Identificador de cobranca Pix pendente, vinculado a uma sessao de navegador. Sem token. */
export type PendingPixCharge={id:string;amountCents:number;qrCode:string;savedAt:number};
export function pendingPixKey(scope:string):string|null{
 return /^ad:[0-9a-f]{16}:$/.test(scope)?'artesao.pix.mp.pending.v1.'+scope:null;
}
export function readPendingPix(raw:string|null):PendingPixCharge|null{
 if(!raw)return null;
 try{
  const value:unknown=JSON.parse(raw);
  if(!value||typeof value!=='object')return null;
  const v=value as Record<string,unknown>;
  if(typeof v.id!=='string'||!/^[A-Za-z0-9]{8,64}$/.test(v.id))return null;
  if(typeof v.amountCents!=='number'||!Number.isSafeInteger(v.amountCents)||v.amountCents<1||v.amountCents>99999999)return null;
  if(typeof v.qrCode!=='string'||v.qrCode.length<20||v.qrCode.length>4096)return null;
  if(typeof v.savedAt!=='number'||!Number.isSafeInteger(v.savedAt)||v.savedAt<=0)return null;
  return {id:v.id,amountCents:v.amountCents,qrCode:v.qrCode,savedAt:v.savedAt};
 }catch{return null;}
}
