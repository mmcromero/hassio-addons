import type {FastifyInstance} from 'fastify';
import {LocalAdmin,LocalAdminError} from './local-admin.js';
import type {PilotStore} from './store.js';
type Page=(title:string,body:string,extra?:string)=>string;
const escape=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
export function registerLocalAdmin(app:FastifyInstance,base:string,local:LocalAdmin,store:PilotStore,page:Page,cookie:(name:string,value:string,httpOnly?:boolean,age?:number)=>string,readCookie:(header:string|undefined,name:string)=>string){
 const form=(mode:'login'|'setup'|'recovery',message='')=>{
  const title=mode==='setup'?'Primeiro Acesso':mode==='recovery'?'Recuperar acesso administrativo':'Acesso administrativo';
  return page(title,`<main class="pilot-auth"><div data-pilot-brand>Artesão Digital</div><h1>${title}</h1>${message?`<p role="alert">${escape(message)}</p>`:''}<form method="post" action="${base}auth/${mode}"><label>E-mail<input name="email" type="email" maxlength="254" required autocomplete="username"></label><label>Senha<input name="password" type="password" minlength="12" maxlength="128" required autocomplete="${mode==='login'?'current-password':'new-password'}"></label>${mode==='login'?'':`<label>Confirmação da senha<input name="confirmation" type="password" minlength="12" maxlength="128" required autocomplete="new-password"></label><label>Código de ${mode==='setup'?'ativação':'recuperação'}<input name="code" type="password" maxlength="100" required autocomplete="off"></label><p>Obtenha o código temporário pelo console administrativo local. Válido por 30 minutos e para um único uso. Use senha de 12 a 128 caracteres.</p>`}<button>${mode==='login'?'Entrar':mode==='setup'?'Criar administrador':'Definir nova senha'}</button></form>${mode==='login'?`<p><a href="${base}recover">Recuperar acesso</a></p>`:''}<p>${mode==='login'?'':`<a href="${base}login">Login administrativo</a> · `}<a href="${base.replace(/admin\/$/,'')}login">Login de usuários com Google</a></p></main>`);
 };
 app.get(base+'login',async(req,reply)=>{
  if(local.current(readCookie(req.headers.cookie,'__Secure-artesaos_admin_session')))return reply.redirect(base);
  if(!local.exists())return reply.redirect(base+'setup');return reply.type('text/html').send(form('login'));
 });
 app.get(base+'setup',(_req,reply)=>local.exists()?reply.code(404).send({message:'Primeiro Acesso indisponível.'}):reply.type('text/html').send(form('setup')));
 app.get(base+'recover',(_req,reply)=>!local.exists()?reply.code(404).send({message:'Recuperação indisponível.'}):reply.type('text/html').send(form('recovery')));
 for(const mode of ['login','setup','recovery'] as const){
  const properties={email:{type:'string',maxLength:254},password:{type:'string',maxLength:128},...(mode==='login'?{}:{confirmation:{type:'string',maxLength:128},code:{type:'string',maxLength:100}})};
  app.post<{Body:{email:string;password:string;confirmation?:string;code?:string}}>(base+'auth/'+mode,{bodyLimit:2048,schema:{body:{type:'object',additionalProperties:false,required:Object.keys(properties),properties}}},async(req,reply)=>{
   if(store.limited('local-admin:'+req.ip,10)||store.limited('local-admin-global',30))return reply.code(429).type('text/html').send(form(mode,'Muitas tentativas. Aguarde antes de tentar novamente.'));
   try{
    if(mode==='login'){
     const session=await local.login(req.body.email,req.body.password);
     store.adminLogout(readCookie(req.headers.cookie,'__Secure-artesaos_admin_session'));
     reply.header('Set-Cookie',[cookie('__Secure-artesaos_admin_session',session.value),cookie('__Secure-artesaos_admin_csrf',session.csrf,false)]);
     return reply.redirect(base+'auth/finish',303);
    }
    await local.setPassword(mode,req.body.email,req.body.password,req.body.confirmation!,req.body.code!);
    return reply.header('Set-Cookie',[cookie('__Secure-artesaos_admin_session','',true,0),cookie('__Secure-artesaos_admin_csrf','',false,0)]).redirect(base+'login',303);
   }catch(error){const status=error instanceof LocalAdminError?error.status:503;return reply.code(status).type('text/html').send(form(mode,error instanceof LocalAdminError?error.message:'Não foi possível concluir a autenticação. Tente novamente.'));}
  });
 }
}
