import {getModuleAccess} from './module-grants.js';
import {allowsApi,viewModule,contextualApi} from '../module-access.js';
import {entryPage,entryScript,entryCss} from './entry.js';
import {offlineKey,offlineIdentity,offlineShell,offlineLockScript,offlineBinding,offlineNamespace} from './offline.js';
import {legalBackLocation,legalReturnTarget,legalNavigationScript} from './legal-navigation.js';
import {registerVersionGuard,versionGuardScript} from './version-guard.js';
import {loadingCss,loadingScript} from './loading.js';
import {pwaManifest,pwaHead} from './pwa.js';
import {bindDistribution} from './local-admin.js';
import {TenantCache,TenantCapacityError} from './tenant-cache.js';
import {smtpInvitationMailer,type InvitationMailer} from './invitation-mail.js';
import {LegalStore} from './legal.js';
import {SupportStore} from './support-store.js';
import {registerSupportRoutes} from './support-routes.js';
import {browserScripts,sessionScript} from './browser.js';
import {registerCommunity} from './community.js';
import {brandScript,communityCss,identityCss} from './brand.js';
import {existsSync,readFileSync} from 'node:fs';
import {buildInfo} from './build-info.js';
import Fastify from 'fastify';
import staticFiles from '@fastify/static';
import {join} from 'node:path';
import type {FastifyInstance,HTTPMethods} from 'fastify';
import {createApp} from '../app.js';
import type {PilotConfig} from './config.js';
import {googleProvider,type IdentityProvider} from './google.js';
import {PilotStore,token,digest,equal} from './store.js';
import {registerMercadoPagoPix} from './mercadopago-pix.js';
const SESSION='__Secure-artesaos_session',CSRF='__Secure-artesaos_csrf',FLOW='__Secure-artesaos_flow';
function cookie(header:string|undefined,name:string){try{const entries=(header??'').split(';').map(s=>s.trim()).filter(s=>s.startsWith(name+'='));return entries.length===1?decodeURIComponent(entries[0].slice(name.length+1)):'';}catch{return '';}}
export async function createPilotApp(config:PilotConfig,provider:IdentityProvider=googleProvider(config),mailer:InvitationMailer|null=smtpInvitationMailer(config),pixFetch:typeof fetch=fetch){
 const app=Fastify({logger:{redact:['req.headers.cookie','req.headers.authorization','res.headers.set-cookie']},disableRequestLogging:true,bodyLimit:2*1024*1024,trustProxy:false});
 const store=new PilotStore(config.dataDir);try{bindDistribution(store,config.distribution??'home-assistant');}catch(error){store.close();throw error;}const tenants=new TenantCache(id=>createApp({dataDir:join(config.dataDir,'tenants',id),staticDir:config.staticDir,mode:'local',logRequests:false,pilotFeatures:true,actorId:'tenant:'+id}));const prefix=config.prefix;
 let support:SupportStore;try{support=new SupportStore(config.dataDir);}catch(error){store.close();throw error;}
 const legal=new LegalStore(config.dataDir);
 const destination=prefix+'?view=produtos';
 const offlineMaster=offlineKey(config.dataDir);let offlinePage:ReturnType<typeof offlineShell>|null=null;const offline=()=>offlinePage??=offlineShell(config,buildInfo.pilotVersion);
 app.get(prefix+'offline',(_req,reply)=>reply.type('text/html').send(offline().html));
 app.get(prefix+'offline-shell.json',()=>offline().descriptor);
 const scripts=browserScripts(prefix,buildInfo.pilotVersion);
 app.get(prefix+'offline-lock.js',(_req,reply)=>reply.type('application/javascript').send(offlineLockScript(prefix)));
 const browserTag=`${pwaHead(prefix)}<script src="${prefix}offline-lock.js"></script><script defer src="${prefix}legal-navigation.js"></script><meta name="artesao-version" content="${buildInfo.pilotVersion}"><script src="${prefix}version-guard.js?v=${buildInfo.pilotVersion}"></script><script src="${prefix}loading.js?v=${buildInfo.pilotVersion}"></script><script src="${prefix}browser-ready.js?v=${buildInfo.pilotVersion}"></script><script src="${prefix}brand.js?v=${buildInfo.pilotVersion}"></script>`;
 const versionFooter=`<footer id="pilot-build-info" aria-label="Versões do aplicativo"><a class="pilot-support-link" href="${prefix}?view=suporte">Suporte técnico</a><a href="${prefix}?view=ajuda">Ajuda</a><a href="${prefix}legal">Termos e Política de Privacidade</a><span class="pilot-current-version">Artesão Digital v${buildInfo.pilotVersion}</span></footer>`;
 const finishPage=()=>`<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Concluindo acesso — Artesão Digital</title><link rel="stylesheet" href="${prefix}pilot.css">${browserTag}<script defer src="${prefix}auth/finish.js?v=${buildInfo.pilotVersion}"></script></head><body><main class="pilot-auth"><div data-pilot-brand>Artesão Digital</div><h1>Concluindo acesso</h1><p id="finish-status" role="status">Confirmando sua sessão antes de abrir o aplicativo…</p><a id="finish-continue" href="${destination}" hidden>Continuar para Produtos</a><a id="finish-login" href="${prefix}login" hidden>Entrar novamente</a></main>${versionFooter}</body></html>`;
 const setCookie=(name:string,value:string,httpOnly=true,maxAge=28800)=>`${name}=${encodeURIComponent(value)}; Path=${prefix}; Secure; SameSite=Lax; Max-Age=${maxAge}${httpOnly?'; HttpOnly':''}`;
 let community:ReturnType<typeof registerCommunity>;try{community=registerCommunity(app,config,store,provider,cookie,browserTag,versionFooter,support,mailer,legal);}catch(e){support.close();store.close();throw e;}
 function session(req:{headers:{cookie?:string}}){return store.getSession(cookie(req.headers.cookie,SESSION),config.idleMinutes);}
 async function pendingSetup(req:{headers:{cookie?:string}}){
  const current=session(req);if(!current)return false;
  const status=await tenants.use(current.tenantId,inner=>inner.inject({method:'GET',url:'/api/onboarding'}));
  return status.statusCode===200&&status.json().complete===false;
 }
 app.addContentTypeParser('application/x-www-form-urlencoded',{parseAs:'string',bodyLimit:4096},(_req,body,done)=>{const entries=new URLSearchParams(String(body));if([...entries.keys()].some((k,i,all)=>all.indexOf(k)!==i)){done(Error('Formulário inválido.'));return;}done(null,Object.fromEntries(entries));});
 app.addHook('onRequest',async(req,reply)=>{
  reply.header('Cache-Control','no-store').header('X-Content-Type-Options','nosniff').header('Referrer-Policy','same-origin').header('X-Frame-Options','DENY').header('Content-Security-Policy',"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' https: data: blob:; connect-src 'self'; frame-ancestors 'none'; form-action 'self' https://accounts.google.com; base-uri 'self'; object-src 'none'");
  if(req.headers.host!==config.publicUrl.host)return reply.code(421).send({message:'Endereço de acesso não autorizado.'});
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&req.headers.origin!==config.publicUrl.origin)return reply.code(403).send({message:'Origem da alteração não autorizada.'});
 });
 registerVersionGuard(app,prefix,buildInfo.pilotVersion,cookie,(header,admin)=>{if(admin){const a=community.current({headers:{cookie:header}});return a?{context:a.context}:null;}const a=session({headers:{cookie:header}});return a?{context:a.userId}:null;},(context,admin)=>`<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Artesão Digital atualizado</title><link rel="stylesheet" href="${prefix}pilot.css">${browserTag}<meta name="artesao-update-page" content="true"><meta name="${admin?'pilot-admin-context':'pilot-context'}" content="${context}"></head><body>${versionFooter}</body></html>`);
 app.get(prefix+'version-guard.js',(_req,reply)=>reply.type('application/javascript').send(versionGuardScript(prefix)));
 app.get(prefix+'legal-navigation.js',(_req,reply)=>reply.type('application/javascript').send(legalNavigationScript(prefix)));
 app.get(prefix+'legal',async(req,reply)=>{const query=req.query as Record<string,unknown>;const origin=Object.hasOwn(query,'returnTo')?query.returnTo:req.headers.referer;const target=legalReturnTarget(config,await pendingSetup(req)?prefix:origin);return reply.type('text/html').send(legal.publicPage(prefix,target?.path??'').replace('</head>',pwaHead(prefix)+`<script defer src="${prefix}legal-navigation.js"></script>`+'</head>'));});
 app.get(prefix+'legal/back',async(req,reply)=>{if(await pendingSetup(req))return reply.redirect(prefix);const origin=(req.query as Record<string,unknown>).returnTo;return reply.redirect(legalBackLocation(config,origin,!!session(req),!!community.current(req)));});
 app.get(prefix+'entry.js',(_req,reply)=>reply.type('application/javascript').send(entryScript()));
 app.get(prefix+'login',async(req,reply)=>{if(session(req))return reply.redirect(destination);return reply.type('text/html').send(`<!doctype html><html lang="pt-BR"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Quero participar do piloto — Artesão Digital</title>${browserTag}<script defer src="${prefix}interest.js?v=${buildInfo.pilotVersion}"></script><script defer src="${prefix}entry.js?v=${buildInfo.pilotVersion}"></script><link rel="stylesheet" href="${prefix}pilot.css"></head><body class="pilot-entry-page">${entryPage(prefix,community.interestForm())}${versionFooter}</body></html>`);});
 app.get(prefix+'manifest.webmanifest',(_req,reply)=>reply.type('application/manifest+json').send(pwaManifest(prefix)));
 app.get<{Params:{size:string}}>(prefix+'pwa/icon-:size.png',(req,reply)=>{
  if(!['192','512'].includes(req.params.size))return reply.code(404).send({message:'Ícone não encontrado.'});
  const file=join(config.staticDir,'assets','pilot-pwa-'+req.params.size+'.png');
  return existsSync(file)?reply.type('image/png').send(readFileSync(file)):reply.code(404).send({message:'Ícone não disponível nesta compilação.'});
 });
 app.get(prefix+'loading.js',(_req,reply)=>reply.type('application/javascript').send(loadingScript(prefix)));
 app.get(prefix+'browser-ready.js',(_req,reply)=>reply.type('application/javascript').send(scripts.bootstrap));
 app.get(prefix+'service-worker.js',(_req,reply)=>reply.header('Service-Worker-Allowed',prefix).type('application/javascript').send(scripts.serviceWorker));
 app.get(prefix+'brand.js',(_req,reply)=>reply.type('application/javascript').send(brandScript(prefix,buildInfo.pilotVersion,existsSync(join(config.staticDir,'pilot-logo.png')))));
 app.get(prefix+'brand/logo-horizontal.png',(_req,reply)=>{const path=join(config.staticDir,'pilot-logo-horizontal.png');return existsSync(path)?reply.type('image/png').send(readFileSync(path)):reply.code(404).send({message:'Logo não disponível.'});});
 app.get(prefix+'brand/logo.png',(_req,reply)=>{const path=join(config.staticDir,'pilot-logo.png');return existsSync(path)?reply.type('image/png').send(readFileSync(path)):reply.code(404).send({message:'Logo não disponível.'});});
 app.get(prefix+'pilot.css',(_req,reply)=>reply.type('text/css').send('body{font:17px system-ui;background:#f3f6f2;color:#20372e;margin:0;padding-bottom:96px}.pilot-auth{max-width:540px;margin:8vh auto;padding:24px}.pilot-auth input,.pilot-auth button{display:block;box-sizing:border-box;padding:12px;margin:12px 0;width:100%;font:inherit}.pilot-auth button{background:#205e47;color:white;border:0;border-radius:6px}#pilot-account{position:fixed;top:0;left:0;right:0;z-index:3;display:grid;grid-template-columns:minmax(0,1fr) minmax(0,2fr) minmax(0,1fr);gap:8px;align-items:center;padding:12px 16px;min-height:68px;background:#205e47;color:#fff;box-shadow:0 2px 8px #10291e25}.pilot-account-title{min-width:0;font-size:17px;font-weight:750;line-height:1.2;text-align:left;overflow-wrap:anywhere}.pilot-account-user{min-width:0;text-align:center;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:14px}#pilot-account button{justify-self:end;width:auto;min-height:44px;margin:0;padding:8px 12px;background:#f3f6f2;color:#205e47;border:1px solid #b8c7be;border-radius:6px}.pilot-session-active{padding-top:84px}.pilot-session-active .brand{display:none}#pilot-build-info{position:fixed;left:0;right:0;bottom:0;z-index:2;display:flex;justify-content:center;gap:4px 16px;flex-wrap:wrap;margin:0;padding:12px 16px;border-top:1px solid #b8c7be;background:#f3f6f2;font-size:12px;line-height:1.5;color:#425448;overflow-wrap:anywhere}'+communityCss+identityCss+loadingCss+entryCss+'#pilot-build-info .pilot-current-version{flex:0 0 100%;text-align:center;order:99}body{padding-bottom:128px}#invitation-detail-title{scroll-margin-top:112px}#invitation-detail-content>a{display:inline-flex;align-items:center;box-sizing:border-box;min-height:44px;max-width:100%;padding:8px 12px;margin:4px;border:1px solid #205e47;border-radius:6px;overflow-wrap:anywhere}'));
 app.post<{Body:{invite?:string}}>(prefix+'auth/google/start',{bodyLimit:4096},async(req,reply)=>{
  if(store.limited('login-global',30)||store.limited('login:'+req.ip,15))return reply.code(429).send({message:'Muitas tentativas. Aguarde antes de tentar novamente.'});
  if(typeof req.body?.invite!=='undefined'&&typeof req.body.invite!=='string')return reply.code(400).send({message:'Convite inválido.'});
  const state=token(),browser=token(),nonce=token(),verifier=token();
  try{const url=await provider.start(state,nonce,verifier);store.flow(state,browser,verifier,nonce,req.body?.invite??'');reply.header('Set-Cookie',setCookie(FLOW,browser,true,600));return reply.redirect(url);}catch{return reply.code(503).send({message:'Não foi possível iniciar o login Google. Confira a configuração e tente novamente.'});}
 });
 app.get(prefix+'auth/google/callback',async(req,reply)=>{
  reply.header('Referrer-Policy','no-referrer');
  const url=new URL(req.raw.url!,config.publicUrl.origin);const states=url.searchParams.getAll('state');
  if(states.length!==1)return reply.code(400).send({message:'Retorno de login inválido.'});
  const flow=store.takeFlow(states[0],cookie(req.headers.cookie,FLOW));reply.header('Set-Cookie',setCookie(FLOW,'',true,0));
  if(!flow)return reply.code(400).send({message:'Login expirado ou não iniciado neste navegador. Inicie novamente.'});
  try{const identity=await provider.complete(url,states[0],flow.nonce,flow.verifier);if(flow.purpose==='admin')return community.completeAdmin(identity,req,reply);const user=store.activate(identity,flow.inviteHash,config.maxUsers);const old=cookie(req.headers.cookie,SESSION);if(old)store.logout(old);const created=store.session(user,config.sessionHours),tenant=String(store.db.prepare('SELECT tenant_id FROM pilot_users WHERE id=?').get(user)!.tenant_id);reply.header('Set-Cookie',[setCookie(FLOW,'',true,0),setCookie(SESSION,created.value,true,config.sessionHours*3600),setCookie(CSRF,created.csrf,false,config.sessionHours*3600),offlineBinding(prefix,offlineNamespace(config,user,tenant))]);return reply.type('text/html').send(finishPage());}catch{return reply.code(403).send({message:'Não foi possível autorizar esta conta. Confira o convite e a conta Google ou peça ao administrador para revisar seu acesso.'});}
 });
 app.get(prefix+'auth/finish',(_req,reply)=>reply.type('text/html').send(finishPage()));
 app.get(prefix+'auth/finish.js',(_req,reply)=>reply.type('application/javascript').send(`(async()=>{history.replaceState(null,'',${JSON.stringify(prefix+'auth/finish')});const status=document.getElementById('finish-status');try{await window.pilotBrowserReady;}catch{status.textContent='Não foi possível preparar o navegador. Tente entrar novamente.';document.getElementById('finish-login').hidden=false;return;}const proceed=document.getElementById('finish-continue');const login=document.getElementById('finish-login');for(let attempt=0;attempt<3;attempt++){try{const response=await fetch(${JSON.stringify(prefix+'api/pilot/session')},{credentials:'same-origin',cache:'no-store'});if(response.ok){const session=await response.json();if(typeof session.email!=='string'||typeof session.context!=='string')throw Error('Sessão não confirmada');status.textContent='Acesso confirmado. Abrindo Produtos…';proceed.hidden=false;location.replace(${JSON.stringify(destination)});return;}}catch{}await new Promise(resolve=>setTimeout(resolve,250));}status.textContent='Não foi possível confirmar a sessão neste navegador. Verifique se os cookies deste site estão permitidos e tente entrar novamente.';login.hidden=false;})();`));
 app.get(prefix+'pilot-session.js',(_req,reply)=>reply.type('application/javascript').send(sessionScript(prefix,CSRF)));
 app.post(prefix+'auth/logout',async(req,reply)=>{
  const current=session(req);
  // An expired/absent session is already logged out; clear leftover browser cookies.
  // A live session still requires both the originating tab and CSRF proof.
  if(current&&(!equal(digest(String(req.headers['x-pilot-csrf']??'')),current.csrfHash)||req.headers['x-pilot-context']!==current.userId))return reply.code(403).send({message:'Sessão ou confirmação inválida. Reabra a página.'});
  if(current)store.logout(cookie(req.headers.cookie,SESSION));
  reply.header('Set-Cookie',[setCookie(SESSION,'',true,0),setCookie(CSRF,'',false,0),offlineBinding(prefix,'')]);return {ok:true};
 });
 app.get(prefix+'api/pilot/session',async(req,reply)=>{const current=session(req);return current?{email:current.email,context:current.userId,modules:getModuleAccess(store.db,current.userId)}:reply.code(401).send({message:'Entre na sua conta.'});});
 const legalRequired=(account:string)=>legal.status(account).required;
 const legalAuth=(req:Parameters<typeof session>[0]&{method:string;headers:Record<string,any>},reply:any)=>{
  const current=session(req);if(!current){reply.code(401).send({message:'Entre na sua conta.'});return null;}
  if(req.headers['x-pilot-context']!==current.userId){reply.code(409).send({message:'A conta desta janela mudou.'});return null;}
  if(req.method!=='GET'&&!equal(digest(String(req.headers['x-pilot-csrf']??'')),current.csrfHash)){reply.code(403).send({message:'Confirmação de segurança inválida.'});return null;}return current;
 };
 registerMercadoPagoPix(app,{prefix,token:config.mercadopagoToken,adminEmails:config.adminEmails??[],fetchImpl:pixFetch,createLimited:(key,max)=>store.limited(key,max),auth:(req,reply)=>{const c=legalAuth(req,reply);if(!c)return null;if(legalRequired(c.userId)){reply.code(428).send({code:'LEGAL_REQUIRED',message:'Confirme os Termos antes de usar o aplicativo.'});return null;}if(!getModuleAccess(store.db,c.userId).enabled.includes('vendas')){reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'PDV ainda não liberado.'});return null;}return {userId:c.userId,email:c.email};}});
 app.get(prefix+'api/offline/identity',(req,reply)=>{const current=legalAuth(req,reply);if(current){if(!getModuleAccess(store.db,current.userId).enabled.includes('catalogo'))return reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'Catálogo ainda não liberado.'});const identity=offlineIdentity(offlineMaster,config,current,buildInfo.pilotVersion);return identity;}});
 app.get(prefix+'api/legal/status',(req,reply)=>{const current=legalAuth(req,reply);if(current)return legal.status(current.userId);});
 app.post<{Body:{version:string;termsHash:string;accepted:boolean}}>(prefix+'api/legal/accept',{bodyLimit:2048,schema:{body:{type:'object',additionalProperties:false,required:['version','termsHash','accepted'],properties:{version:{type:'string',maxLength:100},termsHash:{type:'string',maxLength:64},accepted:{const:true}}}}},(req,reply)=>{const current=legalAuth(req,reply);if(!current)return;if(!legal.accept(current.userId,req.body.version,req.body.termsHash,req.body.accepted,current.tenantId,current.csrfHash))return reply.code(409).send({message:'Confira a versão atual dos Termos.'});return {ok:true};});
 app.get(prefix+'api/help',(req,reply)=>{const current=legalAuth(req,reply);if(!current)return;return {manual:legal.active('manual')?{id:legal.active('manual').id,version:legal.active('manual').version,publishedAt:legal.active('manual').published_at}:null,history:legal.list().filter((v:any)=>v.kind==='manual'&&v.published_at).map((v:any)=>({id:v.id,version:v.version,publishedAt:v.published_at})),contribution:legal.contribution()};});
 app.get(prefix+'api/manuals/:id',(req:any,reply)=>{if(!session(req))return reply.code(401).send({message:'Entre na sua conta.'});const r:any=legal.db.prepare("SELECT payload FROM resource_versions WHERE id=? AND kind='manual' AND published_at IS NOT NULL").get(req.params.id);return r?reply.type('application/pdf').header('Content-Disposition','attachment; filename="manual-artesao-digital.pdf"').send(Buffer.from(r.payload)):reply.code(404).send({message:'Manual não encontrado.'});});
 app.post(prefix+'api/legal/events',(req:any,reply)=>{const c=legalAuth(req,reply);if(!c)return;try{if(!['acknowledge','refuse','preference'].includes(req.body?.action))throw Error();legal.event(c.userId,c.tenantId,req.body.documentId,req.body.action,c.csrfHash);return {ok:true};}catch{return reply.code(400).send({message:'Evento inválido.'});}});
 app.get(prefix+'api/legal/documents',(req,reply)=>{if(!legalAuth(req,reply))return;return (['terms','privacy','cookies'] as const).map(kind=>{const {payload,...v}=legal.active(kind);return v;});});
 registerSupportRoutes(app,prefix+'api/support',support,false,(req,reply)=>{
  const current=session(req);if(!current){reply.code(401).send({message:'Entre na sua conta para acessar o suporte.'});return null;}
  if(req.headers['x-pilot-context']!==current.userId){reply.code(409).send({message:'A conta desta janela mudou. Reabra a página.'});return null;}
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!equal(digest(String(req.headers['x-pilot-csrf']??'')),current.csrfHash)){reply.code(403).send({message:'Confirmação de segurança inválida. Reabra a página.'});return null;}
  if(legalRequired(current.userId)){reply.code(428).send({code:'LEGAL_REQUIRED',message:'Confirme os Termos antes de usar o suporte.'});return null;}
  return {key:'user:'+current.userId,owner:current.userId,email:current.email};
 },(key,max)=>store.limited(key,max));
 // Cookie-authenticated image reads cannot attach fetch context headers. The opaque
 // owner in each immutable reference prevents reuse under another tenant/session.
 app.get<{Params:{owner:string;file:string}}>(prefix+'api/product-photos/:owner/:file',async(req,reply)=>{
  const current=session(req);if(!current)return reply.code(401).send({message:'Entre na sua conta.'});
  if(legalRequired(current.userId))return reply.code(428).send({code:'LEGAL_REQUIRED',message:'Confirme os Termos antes de usar o aplicativo.'});
  if(!allowsApi(getModuleAccess(store.db,current.userId),'/api/product-photos/'+req.params.owner+'/'+req.params.file,'GET'))return reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'Módulo ainda não liberado.'});
  if(!/^[a-f0-9]{32}$/.test(req.params.owner)||!/^([a-f0-9]{64})\.png$/.test(req.params.file))return reply.code(404).send({message:'Foto não encontrada.'});
  const response=await tenants.use(current.tenantId,inner=>inner.inject({method:'GET',url:'/api/product-photos/'+req.params.owner+'/'+req.params.file}));
  reply.code(response.statusCode);if(response.headers['content-type'])reply.type(String(response.headers['content-type']));return reply.send(response.rawPayload);
 });
 app.all(prefix+'*',async(req,reply)=>{
  const current=session(req);
  if(!current){if(req.method==='GET'&&!req.url.slice(prefix.length).startsWith('api/'))return reply.redirect(prefix+'login');return reply.code(401).send({message:'Entre na sua conta.'});}
  if(req.url.slice(prefix.length).startsWith('api/')&&req.headers['x-pilot-context']!==current.userId)return reply.code(409).send({message:'A conta desta janela mudou. Reabra a página antes de continuar.'});
  if(!['GET','HEAD','OPTIONS'].includes(req.method)&&!equal(digest(String(req.headers['x-pilot-csrf']??'')),current.csrfHash))return reply.code(403).send({message:'Confirmação de segurança inválida. Reabra a página.'});
  if(req.url.slice(prefix.length).startsWith('api/')&&legalRequired(current.userId))return reply.code(428).send({code:'LEGAL_REQUIRED',message:'Confirme os Termos antes de usar o aplicativo.'});
  let path='/'+req.raw.url!.slice(prefix.length);
  const parsed=new URL(path,'https://internal.invalid'),access=getModuleAccess(store.db,current.userId);
  let decodedPath:string;try{decodedPath=decodeURIComponent(parsed.pathname);}catch{return reply.code(400).send({message:'Endereço inválido.'});}
  if(decodedPath.startsWith('/api/')&&req.headers['x-pilot-context']!==current.userId)return reply.code(409).send({message:'A conta desta janela mudou.'});
  if(decodedPath.startsWith('/api/')&&legalRequired(current.userId))return reply.code(428).send({code:'LEGAL_REQUIRED',message:'Confirme os Termos antes de usar o aplicativo.'});
  if(decodedPath.startsWith('/api/')&&!allowsApi(access,decodedPath,req.method))return reply.code(403).send({code:'MODULE_UNAVAILABLE',message:'Módulo ainda não liberado para sua conta. Solicite a liberação ao administrador.'});
  if((parsed.pathname==='/'||parsed.pathname.endsWith('/index.html'))&&req.method==='GET'){
   const requested=parsed.searchParams.get('view');
   if((!requested||requested==='produtos')&&!access.enabled.includes('catalogo')){const target=access.enabled.includes('fabricacao')?'fabricacao':access.enabled.includes('vendas')?'vendas':access.enabled[0];if(target)return reply.redirect(prefix+'?view='+target);}
   const required=viewModule(requested);
   if(required&&!access.enabled.includes(required))return reply.code(403).type('text/html').send('<!doctype html><html lang="pt-BR"><meta charset="UTF-8"><title>Módulo não liberado</title><body><h1>Módulo ainda não liberado</h1><p>Solicite a liberação ao administrador. Seus dados foram preservados.</p><a href="'+prefix+'?view=ajuda">Ajuda</a></body></html>');
  }
  const contextual=contextualApi(decodedPath,req.method);
  if(contextual){path=contextual.target+parsed.search;if(req.method==='POST'&&contextual.target==='/api/clients'&&req.body&&typeof req.body==='object')(req.body as Record<string,unknown>).registrationOrigin='sale';}
  let response;
  try{response=await tenants.use(current.tenantId,inner=>inner.inject({method:req.method as HTTPMethods,url:path,headers:{'x-pilot-modules':access.enabled.join(','),...(req.headers['content-type']?{'content-type':req.headers['content-type']}:{}),...(typeof req.headers['x-expected-updated-at']==='string'?{'x-expected-updated-at':req.headers['x-expected-updated-at']}:{})},...(req.body===undefined?{}:{payload:typeof req.body==='string'?req.body:JSON.stringify(req.body)})}));}catch(error){if(error instanceof TenantCapacityError)return reply.code(503).send({message:error.message});throw error;}
  reply.code(response.statusCode);for(const header of ['content-type','content-disposition'])if(response.headers[header])reply.header(header,response.headers[header]);
  let body:Buffer|string=response.rawPayload;if((response.headers['content-type']??'').toString().startsWith('text/html'))body=response.body.replace(/<script type="module" crossorigin src="([^"]+)"><\/script>/g,(_,src)=>`<script type="application/json" data-pilot-module="${src}"></script>`).replace(/<link rel="stylesheet" crossorigin href="([^"]+)">/g,(_,href)=>`<link rel="stylesheet" data-pilot-href="${href}">`).replace('<html ', '<html data-app-name="Artesão Digital" ').replace(/<title>[^<]*<\/title>/,'<title>Artesão Digital</title>').replace('</head>',`${browserTag}<meta name="pilot-modules" content="${access.enabled.join(',')}"><meta name="pilot-context" content="${current.userId}"><link rel="stylesheet" href="${prefix}pilot.css"><script src="${prefix}pilot-session.js?v=${buildInfo.pilotVersion}"></script></head>`).replace('</body>',versionFooter+'</body>');
  if(typeof body==='string'&&['ajuda','suporte'].includes(String((req.query as Record<string,unknown>).view))&&await pendingSetup(req)){
   body=body.replace('<body>','<body class="pilot-first-access-detail">').replace('</body>',`<form class="pilot-first-access-back" action="${prefix}" method="get"><button type="submit">Voltar</button></form></body>`);
  }
  return reply.send(body);
 });
 if(prefix!=='/')app.get(prefix.slice(0,-1),(_req,reply)=>reply.redirect(prefix));
 app.addHook('onClose',async()=>{await tenants.close();support.close();legal.close();store.close();});
 await app.register(staticFiles,{root:join(config.staticDir,'assets'),prefix:prefix+'assets/',decorateReply:false,index:false,cacheControl:false,etag:false,lastModified:false});
 return app;
}
