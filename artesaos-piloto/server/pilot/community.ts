import {getModuleAccess,setModuleAccess,ModuleAccessError} from './module-grants.js';
import {InterestInvitations} from './interest-invitations.js';
import {InvitationError} from './invitations.js';
import {registerResourceAdmin} from './resource-routes.js';
import type {LegalStore} from './legal.js';
import {LocalAdmin} from './local-admin.js';
import {registerLocalAdmin} from './local-admin-ui.js';
import {registerInvitationAdmin} from './invitation-admin.js';
import type {InvitationMailer} from './invitation-mail.js';
import {adminNavigation} from './admin-navigation.js';
import {registeredUserDetails} from './users-admin.js';
import {usersAdminHtml,usersAdminScript} from './users-admin-ui.js';
import type {SupportStore} from './support-store.js';
import {registerSupportRoutes} from './support-routes.js';
import {supportAdminHtml,supportAdminScript} from './support-admin-ui.js';
import type {FastifyInstance,FastifyReply} from 'fastify';
import type {PilotConfig} from './config.js';
import type {IdentityProvider} from './google.js';
import {PilotStore,token,digest,equal,type Identity} from './store.js';
import {InterestStore,parseInterest} from './interest.js';
import {interestForm,interestScript,adminScript} from './community-ui.js';
const ADMIN='__Secure-artesaos_admin_session',CSRF='__Secure-artesaos_admin_csrf',INTEREST='__Secure-artesaos_interest',FLOW='__Secure-artesaos_flow';
type Cookies=(header:string|undefined,name:string)=>string;
export function registerCommunity(app:FastifyInstance,config:PilotConfig,store:PilotStore,provider:IdentityProvider,readCookie:Cookies,browserTag:string,footer:string,support:SupportStore,mailer:InvitationMailer|null=null,legal?:LegalStore){
 footer=footer.replace('?view=suporte','admin/support').replace('Suporte técnico','Central de suporte');
 const prefix=config.prefix,base=prefix+'admin/',allowed=(config.adminEmails??[]),interests=new InterestStore(config.dataDir);
 const adminCookie=(name:string,value:string,httpOnly=true,age=3600)=>`${name}=${encodeURIComponent(value)}; Path=${base}; Secure; SameSite=Lax; Max-Age=${age}${httpOnly?'; HttpOnly':''}`;
 const local=config.distribution==='debian'?new LocalAdmin(store):null;
 const current=(req:{headers:{cookie?:string}})=>local?local.current(readCookie(req.headers.cookie,ADMIN)):store.getAdmin(readCookie(req.headers.cookie,ADMIN),allowed);
 const page=(title:string,body:string,extra='')=>`<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>${title} — Artesão Digital</title><link rel="stylesheet" href="${prefix}pilot.css">${browserTag}${extra}</head><body>${body}${footer}</body></html>`;
 const finishPage=()=>page('Concluindo administração',`<main class="pilot-auth"><div data-pilot-brand>Artesão Digital</div><h1>Concluindo acesso administrativo</h1><p id="finish-status" role="status">Confirmando acesso…</p><a id="finish-login" hidden href="${base}login">Entrar novamente</a></main>`,`<script defer src="${base}finish.js"></script>`);
 const available=()=>local?local.exists():allowed.length>0;
 const cleanup=setInterval(()=>{try{interests.prune();}catch{app.log.error('Não foi possível executar a retenção da lista de interesse.');}},3600000);cleanup.unref();
 app.addHook('onClose',async()=>{clearInterval(cleanup);interests.close();});
 app.get(prefix+'interest.js',(_req,reply)=>reply.type('application/javascript').send(interestScript(prefix)));
 app.get(prefix+'api/interest/form',async(req,reply)=>{
  if(!available())return reply.code(503).send({message:'Lista temporariamente indisponível.'});
  if(req.headers['sec-fetch-site']==='cross-site'||(req.headers.origin&&req.headers.origin!==config.publicUrl.origin))return reply.code(403).send({message:'Origem não autorizada.'});
  if(store.limited('interest-form:'+req.ip,60))return reply.code(429).send({message:'Aguarde antes de tentar novamente.'});
  const browser=token(),nonce=token();interests.issue(browser,nonce);reply.header('Set-Cookie',`${INTEREST}=${browser}; Path=${prefix}api/interest; Secure; HttpOnly; SameSite=Strict; Max-Age=900`);return {token:nonce};
 });
 app.post(prefix+'api/interest',{bodyLimit:4096},async(req,reply)=>{
  if(!available())return reply.code(503).send({message:'Lista temporariamente indisponível.'});
  if(store.limited('interest-send:'+req.ip,20))return reply.code(429).send({message:'Muitas tentativas. Aguarde antes de tentar novamente.'});
  let data;try{data=parseInterest(req.body);}catch(e){return reply.code(400).send({message:(e as Error).message});}
  const body=req.body as Record<string,unknown>;
  if(typeof body.token!=='string'||body.token.length>100||!interests.consume(readCookie(req.headers.cookie,INTEREST),body.token))return reply.code(403).send({message:'O formulário expirou. Prepare-o novamente antes de enviar.'});
  if(body.website!==undefined&&(typeof body.website!=='string'||body.website))return reply.code(202).send({ok:true});
  try{interests.add(data);}catch{return reply.code(503).send({message:'Lista temporariamente indisponível. Tente novamente mais tarde.'});}
  return reply.code(202).send({ok:true});
 });
 if(local)registerLocalAdmin(app,base,local,store,page,adminCookie,readCookie);
 else app.get(base+'login',async(req,reply)=>{if(current(req))return reply.redirect(base);return reply.type('text/html').send(page('Acesso administrativo',`<main class="pilot-auth"><div data-pilot-brand>Artesão Digital</div><h1>Acesso administrativo</h1><p>Entrada exclusiva para contas autorizadas nas configurações do aplicativo.</p><form method="post" action="${base}auth/google/start"><button data-pilot-login disabled>Entrar na administração com Google</button></form><p>O login de usuário não concede acesso administrativo.</p><a href="${prefix}login">Voltar ao login de usuários</a></main>`));});
 app.post(base+'auth/google/start',{bodyLimit:4096},async(req,reply)=>{
  if(local||!available())return reply.code(403).send({message:'Acesso administrativo indisponível.'});
  if(store.limited('admin-login:'+req.ip,10))return reply.code(429).send({message:'Aguarde antes de tentar novamente.'});
  const state=token(),browser=token(),nonce=token(),verifier=token();
  try{const url=await provider.start(state,nonce,verifier);store.flow(state,browser,verifier,nonce,'','admin');reply.header('Set-Cookie',`${FLOW}=${browser}; Path=${prefix}; Secure; HttpOnly; SameSite=Lax; Max-Age=600`);return reply.redirect(url);}catch{return reply.code(503).send({message:'Não foi possível iniciar o login Google.'});}
 });
 app.get(base+'auth/finish',(_req,reply)=>reply.type('text/html').send(finishPage()));
 app.get(base+'finish.js',(_req,reply)=>reply.type('application/javascript').send(`(async()=>{history.replaceState(null,'',${JSON.stringify(base+'auth/finish')});const status=document.getElementById('finish-status');try{await window.pilotBrowserReady;const r=await fetch(${JSON.stringify(base+'api/session')},{cache:'no-store'});if(r.ok){location.replace(${JSON.stringify(base)});return;}}catch{}status.textContent='Não foi possível confirmar o acesso administrativo.';document.getElementById('finish-login').hidden=false;})();`));
 app.get(base+'session.js',(_req,reply)=>reply.type('application/javascript').send(adminScript(prefix)));
 app.get(base+'api/session',async(req,reply)=>{const admin=current(req);return admin?{email:admin.email,context:admin.context}:reply.code(401).send({message:'Entre com uma conta administrativa autorizada.'});});
 app.get(base+'api/interests',async(req,reply)=>{
  const admin=current(req);if(!admin)return reply.code(401).send({message:'Acesso administrativo necessário.'});
  if(req.headers['x-pilot-admin-context']!==admin.context)return reply.code(409).send({message:'A conta desta aba mudou. Reabra a administração.'});
  const query=req.query as Record<string,unknown>,n=query.page===undefined?1:Number(query.page);if(!Number.isSafeInteger(n)||n<1||n>100000)return reply.code(400).send({message:'Página inválida.'});
  const list=interests.list(n);return {...list,records:list.records.map(r=>({...r,invitation:interestInvitations.status(r)}))};
 });
 app.get<{Querystring:{page?:number;search?:string}}>(base+'api/users',{schema:{querystring:{type:'object',additionalProperties:false,properties:{page:{type:'integer',minimum:1,maximum:100000},search:{type:'string',maxLength:254}}}}},async(req,reply)=>{
  const admin=current(req);if(!admin)return reply.code(401).send({message:'Acesso administrativo necessário.'});
  if(req.headers['x-pilot-admin-context']!==admin.context)return reply.code(409).send({message:'A conta desta aba mudou. Reabra a administração.'});
  const list=store.listUsers(req.query.page??1,req.query.search??'');return {...list,records:list.records.map(user=>({...user,modules:getModuleAccess(store.db,user.id)}))};
 });
 app.get<{Params:{id:string}}>(base+'api/users/:id',{schema:{params:{type:'object',required:['id'],properties:{id:{type:'string',pattern:'^[0-9a-f-]{36}$'}}}}},async(req,reply)=>{
  const admin=current(req);if(!admin)return reply.code(401).send({message:'Acesso administrativo necessário.'});
  if(req.headers['x-pilot-admin-context']!==admin.context)return reply.code(409).send({message:'A conta desta aba mudou. Reabra a administração.'});
  const details=registeredUserDetails(store,config.dataDir,req.params.id);return details?{...details,invitation:invitationControl.contactForUser(req.params.id)}:reply.code(404).send({message:'Usuário não encontrado.'});
 });
 app.put<{Params:{id:string};Body:{enabled:unknown;revision:unknown}}>(base+'api/users/:id/modules',{bodyLimit:2048},async(req,reply)=>{
  const admin=current(req);if(!admin)return reply.code(401).send({message:'Acesso administrativo necessário.'});
  if(req.headers['x-pilot-admin-context']!==admin.context)return reply.code(409).send({message:'A conta desta aba mudou.'});
  if(!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),admin.csrfHash))return reply.code(403).send({message:'Confirmação de segurança inválida.'});
  if(!req.body||Object.keys(req.body).some(k=>!['enabled','revision'].includes(k)))return reply.code(400).send({message:'Liberações inválidas.'});
  try{return setModuleAccess(store.db,req.params.id,req.body.enabled,req.body.revision,admin.email);}catch(e){if(e instanceof ModuleAccessError)return reply.code(e.status).send({message:e.message});throw e;}
 });
 app.get(base+'users',async(req,reply)=>{const admin=current(req);if(!admin)return reply.redirect(base+'login');return reply.type('text/html').send(page('Usuários cadastrados',usersAdminHtml(base),`<meta name="pilot-admin-context" content="${admin.context}"><script defer src="${base}session.js"></script><script defer src="${base}users.js"></script>`));});
 app.get(base+'users.js',(_req,reply)=>reply.type('application/javascript').send(usersAdminScript(base)));
 app.post(base+'auth/logout',async(req,reply)=>{
  const admin=current(req);if(admin&&(!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),admin.csrfHash)||req.headers['x-pilot-admin-context']!==admin.context))return reply.code(403).send({message:'Confirmação de segurança inválida.'});
  if(admin)store.adminLogout(readCookie(req.headers.cookie,ADMIN));reply.header('Set-Cookie',[adminCookie(ADMIN,'',true,0),adminCookie(CSRF,'',false,0)]);return {ok:true};
 });
 const adminPage=async(req:{headers:{cookie?:string}},reply:FastifyReply)=>{
  const admin=current(req);if(!admin)return reply.redirect(base+'login');
  return reply.type('text/html').send(page('Interessados no piloto',`<main class="pilot-admin">${adminNavigation(base,'interests')}<h1>Interessados no piloto</h1><p>Lista restrita à administração. O registro de interesse não cria conta nem libera acesso.</p><p id="admin-total"></p><p id="admin-status" role="status" aria-live="polite"></p><div class="pilot-table"><table><thead><tr><th>Nome</th><th>E-mail</th><th>WhatsApp</th><th>Recebido em</th><th>Situação</th><th>Ações</th></tr></thead><tbody id="interest-rows"></tbody></table></div><nav id="admin-pagination" aria-label="Paginação de interessados" hidden><button id="admin-previous">Anterior</button><span id="admin-page"></span><button id="admin-next">Próxima</button></nav></main>`,`<meta name="pilot-admin-context" content="${admin.context}"><script defer src="${base}session.js"></script>`));
 };
 app.get(base,adminPage);app.get(prefix+'admin',(_req,reply)=>reply.redirect(base));
 registerSupportRoutes(app,base+'api/support',support,true,(req,reply)=>{
  const admin=current(req);if(!admin){reply.code(401).send({message:'Acesso administrativo necessário.'});return null;}
  if(req.headers['x-pilot-admin-context']!==admin.context){reply.code(409).send({message:'A conta desta aba mudou. Reabra a administração.'});return null;}
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),admin.csrfHash)){reply.code(403).send({message:'Confirmação de segurança inválida.'});return null;}
  return {key:'admin:'+admin.email,email:admin.email};
 },(key,max)=>store.limited(key,max));
 app.get(base+'support',async(req,reply)=>{const admin=current(req);if(!admin)return reply.redirect(base+'login');return reply.type('text/html').send(page('Central de suporte',supportAdminHtml(base),`<meta name="pilot-admin-context" content="${admin.context}"><script defer src="${base}session.js"></script><script defer src="${base}support.js"></script>`));});
 app.get(base+'support.js',(_req,reply)=>reply.type('application/javascript').send(supportAdminScript(base)));
 const invitationControl=registerInvitationAdmin(app,config,store,mailer,(req,reply,write)=>{
  const admin=current(req);if(!admin){if(req.method==='GET'&&req.url.split('?')[0]===base+'invitations')reply.redirect(base+'login');else reply.code(401).send({message:'Acesso administrativo necessário.'});return null;}
  if(req.url.startsWith(base+'api/')&&req.headers['x-pilot-admin-context']!==admin.context){reply.code(409).send({message:'A conta desta aba mudou. Reabra a administração.'});return null;}
  if(write&&!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),admin.csrfHash)){reply.code(403).send({message:'Confirmação de segurança inválida.'});return null;}return admin;
 },page);
 const interestInvitations=new InterestInvitations(interests,store,invitationControl);
 app.post<{Params:{id:string}}>(base+'api/interests/:id/invite',{bodyLimit:1024,schema:{params:{type:'object',required:['id'],properties:{id:{type:'string',pattern:'^[a-f0-9-]{36}$'}}}}},(req,reply)=>{
  const admin=current(req);if(!admin)return reply.code(401).send({message:'Acesso administrativo necessário.'});
  if(req.headers['x-pilot-admin-context']!==admin.context)return reply.code(409).send({message:'A conta desta aba mudou.'});
  if(!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),admin.csrfHash))return reply.code(403).send({message:'Confirmação inválida.'});
  if(store.limited('interest-convert:'+admin.email,100))return reply.code(429).send({message:'Aguarde antes de converter outros interessados.'});
  try{return interestInvitations.convert(req.params.id,admin.email,config.maxUsers);}catch(error){return reply.code(error instanceof InvitationError?error.status:503).send({message:error instanceof InvitationError?error.message:'Não foi possível gerar o convite. Tente novamente.'});}
 });
 if(legal)registerResourceAdmin(app,base,legal,(req,reply,write)=>{
  const a=current(req);if(!a){reply.code(401).send({message:'Acesso administrativo necessário.'});return null;}
  if(req.url.startsWith(base+'api/')&&req.headers['x-pilot-admin-context']!==a.context){reply.code(409).send({message:'A conta desta aba mudou.'});return null;}
  if(write&&!equal(digest(String(req.headers['x-pilot-admin-csrf']??'')),a.csrfHash)){reply.code(403).send({message:'Confirmação inválida.'});return null;}return a;
 },page);
 app.all(base+'*',(_req,reply)=>reply.code(404).send({message:'Página administrativa não encontrada.'}));
 return {current,interestForm:()=>available()?interestForm():'<p>A lista de interesse está temporariamente indisponível.</p>',async completeAdmin(identity:Identity,req:{headers:{cookie?:string}},reply:FastifyReply){
  if(local||identity.issuer!=='https://accounts.google.com'||!identity.verified||!identity.subject||!allowed.includes(identity.email.toLowerCase()))return reply.code(403).send({message:'Esta conta não tem autorização administrativa.'});
  store.adminLogout(readCookie(req.headers.cookie,ADMIN));const created=store.adminSession(identity);reply.header('Set-Cookie',[`${FLOW}=; Path=${prefix}; Secure; HttpOnly; SameSite=Lax; Max-Age=0`,adminCookie(ADMIN,created.value),adminCookie(CSRF,created.csrf,false)]);return reply.type('text/html').send(finishPage());
 }};
}
