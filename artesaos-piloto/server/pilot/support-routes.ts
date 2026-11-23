import type {FastifyInstance,FastifyRequest,FastifyReply} from 'fastify';
import {SupportStore,SupportError} from './support-store.js';
import {supportKinds,supportStatuses,type SupportKind,type SupportStatus} from './support-model.js';
type Actor={key:string;email:string;owner?:string};
type Authorize=(req:FastifyRequest,reply:FastifyReply)=>Actor|null;
function object(value:unknown,allowed:string[]){if(!value||typeof value!=='object'||Array.isArray(value)||Object.keys(value).some(key=>!allowed.includes(key)))throw new SupportError(400,'Confira os campos da solicitação.');return value as Record<string,unknown>;}
function text(value:unknown,max:number,required=true){if(typeof value!=='string'||value.length>max||/[\u0000-\u0008\u000b\u000c\u000e-\u001f\u007f]/.test(value)||required&&!value.trim())throw new SupportError(400,'Preencha os campos e respeite os limites de tamanho.');return value.trim();}
function requestKey(value:unknown){const key=text(value,80);if(!/^[a-zA-Z0-9_-]{16,80}$/.test(key))throw new SupportError(400,'Identificação de envio inválida. Atualize a página.');return key;}
function idOf(req:FastifyRequest){const raw=(req.params as Record<string,string>).id;if(!/^[1-9]\d{0,12}$/.test(raw))throw new SupportError(404,'Chamado não encontrado.');return Number(raw);}
export function registerSupportRoutes(app:FastifyInstance,base:string,store:SupportStore,admin:boolean,authorize:Authorize,limited:(key:string,max:number)=>boolean){
 const run=(work:(req:FastifyRequest,actor:Actor)=>unknown)=>async(req:FastifyRequest,reply:FastifyReply)=>{
  const actor=authorize(req,reply);if(!actor)return;
  try{if(!admin&&!actor.owner)throw new SupportError(403,'Conta não autorizada.');return work(req,actor);}catch(error){if(error instanceof SupportError)return reply.code(error.code).send({message:error.message});req.log.error('Não foi possível processar o chamado de suporte.');return reply.code(500).send({message:'Não foi possível processar o chamado. Tente novamente.'});}
 };
 app.get(base,run((req,actor)=>{const query=object(req.query,['page','status','kind']);const page=query.page===undefined?1:Number(query.page);if(!Number.isSafeInteger(page)||page<1||page>100000)throw new SupportError(400,'Página inválida.');const status=query.status?text(query.status,30):undefined,kind=query.kind?text(query.kind,30):undefined;if(status&&!Object.hasOwn(supportStatuses,status)||kind&&!Object.hasOwn(supportKinds,kind))throw new SupportError(400,'Filtro inválido.');return store.list(admin?undefined:actor.owner,page,status as SupportStatus|undefined,kind as SupportKind|undefined);}));
 app.get(base+'/:id',run((req,actor)=>store.detail(idOf(req),admin?undefined:actor.owner)));
 if(!admin)app.post(base,{bodyLimit:32768},run((req,actor)=>{
  const data=object(req.body,['kind','subject','body','requestKey']);const kind=text(data.kind,20) as SupportKind;if(!Object.hasOwn(supportKinds,kind))throw new SupportError(400,'Escolha dúvida de uso ou relato de erro.');const subject=text(data.subject,160),body=text(data.body,6000),key=requestKey(data.requestKey);
  if(/[\r\n\t]/.test(subject))throw new SupportError(400,'O assunto deve ocupar uma única linha.');
  if(limited('support-create:'+actor.key,15))throw new SupportError(429,'Muitos envios. Aguarde antes de abrir outro chamado.');
  return store.create(actor.owner!,actor.email,{kind,subject,body,requestKey:key});
 }));
 app.post(base+'/:id/messages',{bodyLimit:32768},run((req,actor)=>{
  const data=object(req.body,admin?['body','status','expectedRevision','requestKey']:['body','expectedRevision','requestKey']);const body=text(data.body??'',6000,!admin),key=requestKey(data.requestKey);const revision=data.expectedRevision;
  if(!Number.isSafeInteger(revision)||Number(revision)<1)throw new SupportError(400,'Atualize o chamado antes de responder.');
  let status:SupportStatus|undefined;if(data.status!==undefined){if(typeof data.status!=='string'||!Object.hasOwn(supportStatuses,data.status))throw new SupportError(400,'Status inválido.');status=data.status as SupportStatus;}
  if(limited('support-update:'+actor.key,100))throw new SupportError(429,'Muitas atualizações. Aguarde antes de tentar novamente.');
  return store.update(idOf(req),admin?undefined:actor.owner,{key:actor.key,role:admin?'admin':'user'},{body,status,expectedRevision:Number(revision),requestKey:key});
 }));
}
