import type {FastifyInstance,FastifyRequest,FastifyReply} from 'fastify';
import type {PilotConfig} from './config.js';
import {Invitations,InvitationError} from './invitations.js';
import {invitationText,type InvitationMailer} from './invitation-mail.js';
import type {PilotStore} from './store.js';
import {invitationsAdminHtml,invitationsAdminScript} from './invitations-admin-ui.js';
type Admin={email:string;context:string;csrfHash:string};
export function registerInvitationAdmin(app:FastifyInstance,config:PilotConfig,store:PilotStore,mailer:InvitationMailer|null,authorize:(req:FastifyRequest,reply:FastifyReply,write:boolean)=>Admin|null,page:(title:string,body:string,extra?:string)=>string){
 const base=config.prefix+'admin/',invites=new Invitations(store,config.dataDir);
 app.addHook('onClose',async()=>{mailer?.close?.();invites.close();});
 const run=(write:boolean,fn:(req:any,reply:FastifyReply,admin:Admin)=>unknown)=>async(req:FastifyRequest,reply:FastifyReply)=>{
  const admin=authorize(req,reply,write);if(!admin)return;
  try{return await fn(req,reply,admin);}catch(error){if(error instanceof InvitationError)return reply.code(error.status).send({message:error.message});return reply.code(503).send({message:'Não foi possível consultar ou salvar o convite. Tente novamente.'});}
 };
 const id={type:'object',required:['id'],properties:{id:{type:'string',pattern:'^[a-f0-9]{64}$'}}},requestKey={type:'string',pattern:'^[a-f0-9-]{36}$'};
 app.get(base+'api/invitations',{schema:{querystring:{type:'object',additionalProperties:false,properties:{page:{type:'integer',minimum:1,maximum:100000},search:{type:'string',maxLength:254},status:{enum:['unaccepted','all','pending','accepted','expired','revoked']}}}}},run(false,req=>({...invites.list(req.query.page??1,req.query.status??'unaccepted',req.query.search??''),automaticAvailable:!!mailer,maxUsers:config.maxUsers})));
 app.get(base+'api/invitations/:id',{schema:{params:id}},run(false,req=>{const detail=invites.detail(req.params.id);return {...detail,loginUrl:new URL('login',config.publicUrl).href,messageText:detail.code?invitationText({to:detail.email,name:detail.name??'',code:detail.code,expiresAt:detail.expiresAt,loginUrl:new URL('login',config.publicUrl).href}):null};}));
 app.post(base+'api/invitations',{bodyLimit:4096,schema:{body:{type:'object',additionalProperties:false,required:['name','email','requestKey'],properties:{name:{type:'string',minLength:1,maxLength:100},email:{type:'string',maxLength:254},channel:{enum:['email','whatsapp']},phone:{type:'string',maxLength:40},requestKey}}}},run(true,(req,_reply,admin)=>{
  if(store.limited('invitation-create:'+admin.email,100))throw new InvitationError(429,'Aguarde antes de gerar mais convites.');return invites.issue(req.body.name,req.body.email,admin.email,req.body.requestKey,config.maxUsers,req.body.channel??'email',req.body.phone??'');
 }));
 app.post(base+'api/invitations/:id/share',{bodyLimit:1024,schema:{params:id,body:{type:'object',additionalProperties:false,required:['event','requestKey'],properties:{event:{enum:['copy_code','copy_link','copy_message','open_whatsapp','native_share']},requestKey}}}},run(true,(req,_reply,admin)=>invites.recordShare(req.params.id,admin.email,req.body.event,req.body.requestKey)));
 app.post(base+'api/invitations/:id/revoke',{bodyLimit:1024,schema:{params:id}},run(true,(req,_reply,admin)=>{
  if(store.limited('invitation-revoke:'+admin.email,100))throw new InvitationError(429,'Aguarde antes de alterar outros convites.');return invites.revoke(req.params.id);
 }));
 app.post(base+'api/invitations/:id/reactivate',{bodyLimit:4096,schema:{params:id,body:{type:'object',additionalProperties:false,required:['name','email','channel','requestKey'],properties:{name:{type:'string',minLength:1,maxLength:100},email:{type:'string',maxLength:254},channel:{enum:['email','whatsapp']},phone:{type:'string',maxLength:40},requestKey}}}},run(true,(req,_reply,admin)=>{
  if(store.limited('invitation-reactivate:'+admin.email,100))throw new InvitationError(429,'Aguarde antes de alterar outros convites.');return invites.reactivate(req.params.id,req.body.name,req.body.email,admin.email,req.body.requestKey,config.maxUsers,req.body.channel,req.body.phone??'');
 }));
 app.post(base+'api/invitations/:id/send',{bodyLimit:2048,schema:{params:id,body:{type:'object',additionalProperties:false,required:['requestKey'],properties:{requestKey}}}},run(true,async(req,reply,admin)=>{
  if(!mailer)throw new InvitationError(503,'Envio automático não configurado. Copie o convite para envio manual.');
  if(store.limited('invitation-send:'+admin.email,10)||store.limited('invitation-send-global',30))throw new InvitationError(429,'Aguarde antes de enviar outros convites.');
  const attempt=invites.beginDelivery(req.params.id,admin.email,req.body.requestKey,'smtp');if(!attempt.fresh)return invites.detail(req.params.id);
  const record=invites.detail(req.params.id);
  try{await mailer.send({to:record.email,name:record.name??'',code:record.code!,expiresAt:record.expiresAt,loginUrl:new URL('login',config.publicUrl).href});invites.finishDelivery(attempt.id,true);}catch{invites.finishDelivery(attempt.id,false);return reply.code(502).send({message:'Envio não confirmado. O convite foi salvo. Confira o provedor antes de tentar novamente.',invitation:invites.detail(req.params.id)});}
  return invites.detail(req.params.id);
 }));
 app.get(base+'invitations',async(req,reply)=>{const admin=authorize(req,reply,false);if(!admin)return;return reply.type('text/html').send(page('Convites',invitationsAdminHtml(base),`<meta name="pilot-admin-context" content="${admin.context}"><script defer src="${base}session.js"></script><script defer src="${base}invitations.js"></script>`));});
 app.get(base+'invitations.js',(_req,reply)=>reply.type('application/javascript').send(invitationsAdminScript(base)));
 return invites;
}
