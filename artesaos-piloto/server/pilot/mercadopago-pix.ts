import type {FastifyInstance,FastifyReply} from 'fastify';
import {randomUUID} from 'node:crypto';
import {digest} from './store.js';

/**
 * Pix com confirmação automática via Mercado Pago (API de Orders), só para e-mails administradores.
 * O token fica apenas na configuração privada do servidor (nunca vai ao navegador).
 * Sem webhook e sem tabela: o navegador consulta a rota de status enquanto o QR está na tela.
 */
export type PixAccount={userId:string;email:string};
type Fetch=typeof fetch;
export type MercadoPagoPixOptions={prefix:string;token:string|undefined;adminEmails:string[];auth:(req:any,reply:FastifyReply)=>PixAccount|null;createLimited:(key:string,max:number)=>boolean;fetchImpl?:Fetch;now?:()=>number;retryDelayMs?:number};
const API='https://api.mercadopago.com/v1/orders',MAX_CENTS=99999999,MIN_POLL_MS=1500;
/** A Orders API exige que a cobrança Pix valha entre 30 minutos e 30 dias; 40 minutos dá folga. */
const EXPIRATION='PT40M';
/** Valor sempre em centavos inteiros; a API recebe texto com 2 casas, sem erro de ponto flutuante. */
export function amountText(cents:number){return (Math.trunc(cents)/100).toFixed(2);}
export function centsFrom(value:unknown){const n=Number(value);return Number.isFinite(n)?Math.round(n*100):NaN;}
const owner=(userId:string)=>'ad:'+digest(userId).slice(0,16)+':';
const paymentOf=(body:any)=>body?.transactions?.payments?.[0];
/** 'processed' = pago. Em andamento = aguardando. Qualquer outro (cancelado, expirado, falhou…) encerra. */
export function statusOf(body:any):'approved'|'pending'|'closed'{
 const order=body?.status,payment=paymentOf(body)?.status;
 if(order==='processed')return payment===undefined||payment==='processed'?'approved':'pending';
 return order==='created'||order==='processing'||order==='action_required'?'pending':'closed';
}
async function call(fetchImpl:Fetch,token:string,url:string,init:RequestInit){
 try{return await fetchImpl(url,{...init,headers:{Authorization:'Bearer '+token,'Content-Type':'application/json',Accept:'application/json',...(init.headers??{})},signal:AbortSignal.timeout(10000)});}
 catch{throw Object.assign(Error('Não foi possível falar com o Mercado Pago agora. Use o QR comum e confira no banco.'),{status:502});}
}
async function failure(response:Response){
 let detail='';try{const body:any=await response.json();detail=String(body?.errors?.[0]?.message??body?.message??body?.cause?.[0]?.description??'').slice(0,200);}catch{/* sem corpo */}
 const status=response.status===401||response.status===403?502:response.status>=500?502:400;
 return Object.assign(Error(response.status===401||response.status===403?'O Mercado Pago recusou o token. Confira a configuração do servidor.':'O Mercado Pago não aceitou a cobrança'+(detail?': '+detail:'.')),{status});
}
export function registerMercadoPagoPix(app:FastifyInstance,o:MercadoPagoPixOptions){
 const fetchImpl=o.fetchImpl??fetch,now=o.now??Date.now,admins=new Set(o.adminEmails.map(e=>e.toLowerCase())),lastPoll=new Map<string,number>(),retryDelay=o.retryDelayMs??700;
 const allowed=(a:PixAccount)=>!!o.token&&admins.has(a.email.toLowerCase());
 const qrOf=(body:any)=>{const q=paymentOf(body)?.payment_method?.qr_code;return typeof q==='string'&&q?q:'';};
 app.get(o.prefix+'api/pix-mp/status',(req,reply)=>{const a=o.auth(req,reply);if(!a)return;return {enabled:allowed(a),...(allowed(a)?{scope:owner(a.userId)}:{})};});
 app.post<{Body:{amountCents:number;description?:string}}>(o.prefix+'api/pix-mp/charges',{bodyLimit:2048,schema:{body:{type:'object',additionalProperties:false,required:['amountCents'],properties:{amountCents:{type:'integer',minimum:1,maximum:MAX_CENTS},description:{type:'string',maxLength:60}}}}},async(req,reply)=>{
  const a=o.auth(req,reply);if(!a)return;
  if(!allowed(a))return reply.code(403).send({message:'Pix automático não está liberado para esta conta.'});
  if(o.createLimited('pix-mp:'+a.userId,30))return reply.code(429).send({message:'Muitas cobranças em pouco tempo. Aguarde alguns minutos.'});
  const reference=owner(a.userId)+randomUUID().replace(/-/g,''),amount=amountText(req.body.amountCents);
  try{
   const response=await call(fetchImpl,o.token!,API,{method:'POST',headers:{'X-Idempotency-Key':randomUUID()},body:JSON.stringify({type:'online',total_amount:amount,external_reference:reference,processing_mode:'automatic',transactions:{payments:[{amount,payment_method:{id:'pix',type:'bank_transfer'},expiration_time:EXPIRATION}]},payer:{email:a.email}})});
   if(!response.ok)throw await failure(response);
   let body:any=await response.json();
   // A criação pode ser assíncrona: se o código ainda não veio, consulta poucas vezes antes de desistir.
   for(let i=0;i<3&&body?.id&&!qrOf(body)&&statusOf(body)==='pending';i++){
    if(retryDelay>0)await new Promise(r=>setTimeout(r,retryDelay));
    const again=await call(fetchImpl,o.token!,API+'/'+encodeURIComponent(String(body.id)),{method:'GET'});
    if(!again.ok)break;body=await again.json();
   }
   const qr=qrOf(body);
   if(typeof body?.id!=='string'||!/^[A-Za-z0-9]{8,64}$/.test(body.id)||!qr)return reply.code(502).send({message:'O Mercado Pago não devolveu o código Pix. Use o QR comum.'});
   if(centsFrom(body.total_amount)!==req.body.amountCents)return reply.code(502).send({message:'O valor devolvido pelo Mercado Pago não confere. Use o QR comum.'});
   return {id:body.id,status:statusOf(body),amountCents:req.body.amountCents,qrCode:qr,expiresAt:typeof paymentOf(body)?.date_of_expiration==='string'?paymentOf(body).date_of_expiration:null};
  }catch(error){const e=error as Error&{status?:number};return reply.code(e.status??502).send({message:e.message});}
 });
 app.get<{Params:{id:string}}>(o.prefix+'api/pix-mp/charges/:id',async(req,reply)=>{
  const a=o.auth(req,reply);if(!a)return;
  if(!allowed(a))return reply.code(403).send({message:'Pix automático não está liberado para esta conta.'});
  if(!/^[A-Za-z0-9]{8,64}$/.test(req.params.id))return reply.code(404).send({message:'Cobrança não encontrada.'});
  const key=a.userId+':'+req.params.id,t=now(),last=lastPoll.get(key);
  if(last!==undefined&&t-last<MIN_POLL_MS)return reply.code(429).header('Retry-After','2').send({message:'Aguarde um instante para consultar de novo.'});
  lastPoll.set(key,t);if(lastPoll.size>500)for(const [k,v] of lastPoll)if(t-v>600000)lastPoll.delete(k);
  try{
   const response=await call(fetchImpl,o.token!,API+'/'+req.params.id,{method:'GET'});
   if(response.status===404)return reply.code(404).send({message:'Cobrança não encontrada.'});
   if(!response.ok)throw await failure(response);
   const body:any=await response.json();
   // Só devolve cobranças criadas por este app para esta conta.
   if(typeof body?.external_reference!=='string'||!body.external_reference.startsWith(owner(a.userId))||paymentOf(body)?.payment_method?.id!=='pix')return reply.code(404).send({message:'Cobrança não encontrada.'});
   const status=statusOf(body);
   return {id:String(body.id),status,amountCents:centsFrom(body.total_amount),...(status==='pending'&&qrOf(body)?{qrCode:qrOf(body)}:{})};
  }catch(error){const e=error as Error&{status?:number};return reply.code(e.status??502).send({message:e.message});}
 });
}
