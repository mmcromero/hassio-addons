import type {FastifyInstance} from 'fastify';
import {digest} from './store.js';
export function registerVersionGuard(app:FastifyInstance,prefix:string,version:string,readCookie:(h:string|undefined,n:string)=>string,account:(h:string|undefined,a:boolean)=>{context:string}|null,page:(c:string,a:boolean)=>string){
 const role=(p:string)=>p.startsWith(prefix+'admin/');
 const names=(a:boolean)=>({session:a?'__Secure-artesaos_admin_session':'__Secure-artesaos_session',marker:a?'__Secure-artesaos_admin_version':'__Secure-artesaos_version',path:prefix+(a?'admin/':'')});
 const stamp=(t:string)=>digest(version+':'+t);
 const outdated=(h:string|undefined,a:boolean)=>{const n=names(a),t=readCookie(h,n.session),m=readCookie(h,n.marker);return Boolean(t&&m&&m!==stamp(t)&&account(h,a));};
 app.get(prefix+'version',async req=>({version,reauthenticate:outdated(req.headers.cookie,(req.query as any)?.admin==='1')}));
 app.addHook('onRequest',async(req,reply)=>{const p=req.url.split('?')[0];if(!p.startsWith(prefix))return;const a=role(p),api=p.startsWith(prefix+(a?'admin/api/':'api/'));
  if(api&&((req.headers['x-artesao-version']&&req.headers['x-artesao-version']!==version)||outdated(req.headers.cookie,a)))return reply.code(409).send({code:'APP_UPDATED',version,message:'O Artesão Digital foi atualizado! Entre novamente.'});
  const document=req.method==='GET'&&(p===prefix||p===prefix+'login'||p===prefix+'admin/'||p===prefix+'admin/login'||(!p.includes('.',prefix.length)&&a&&!p.includes('/auth/')));
  if(document&&outdated(req.headers.cookie,a)){const current=account(req.headers.cookie,a);if(current)return reply.type('text/html').send(page(current.context,a));}
 });
 app.addHook('onSend',async(req,reply,payload)=>{const h=reply.getHeader('set-cookie'),cookies=h?(Array.isArray(h)?h.map(String):[String(h)]):[];for(const a of [false,true]){const n=names(a),issued=cookies.find(c=>c.startsWith(n.session+'='));let value:string|undefined;
  if(issued){const t=decodeURIComponent(issued.slice(n.session.length+1).split(';')[0]);value=t?stamp(t):'';}
  else if(a===role(req.url.split('?')[0])&&String(reply.getHeader('content-type')??'').startsWith('text/html')&&!readCookie(req.headers.cookie,n.marker)&&account(req.headers.cookie,a)){const t=readCookie(req.headers.cookie,n.session);if(t)value=stamp(t);}
  if(value!==undefined)cookies.push(`${n.marker}=${value}; Path=${n.path}; Secure; HttpOnly; SameSite=Lax; Max-Age=${value?31536000:0}`);}
  if(cookies.length){reply.removeHeader('set-cookie');reply.header('Set-Cookie',cookies);}return payload;
 });
}
export function versionGuardScript(prefix:string){return `(()=>{
 const prefix=${JSON.stringify(prefix)},version=document.querySelector('meta[name=artesao-version]').content,original=window.fetch.bind(window);
 let blocked=false,checking=null,allowedToLeave=false,panel=null,banner=null,edited=false;
 const admin=()=>Boolean(document.querySelector('meta[name=pilot-admin-context]'));
 const context=()=>document.querySelector(admin()?'meta[name=pilot-admin-context]':'meta[name=pilot-context]')?.content;
 const hold=()=>new Promise(()=>{}),text=(tag,value)=>{const el=document.createElement(tag);el.textContent=value;return el;};
 const close=()=>{panel?.close();panel?.remove();panel=null;};
 const dialog=(title,body)=>{close();panel=document.createElement('dialog');panel.className='pilot-auth';panel.style.cssText='max-width:500px;box-sizing:border-box;width:calc(100% - 32px);border:1px solid #b8c7be;border-radius:8px;background:#f3f6f2;color:#20372e';panel.setAttribute('aria-labelledby','version-title');const h=text('h1',title);h.id='version-title';panel.append(h,text('p',body));document.body.append(panel);panel.addEventListener('cancel',e=>{e.preventDefault();review();});panel.showModal();};
 const button=(label,action)=>{const b=text('button',label);b.type='button';b.onclick=action;panel.append(b);};
 const review=()=>{close();if(!banner){banner=text('aside','Esta versão não pode mais salvar ou enviar operações. Revise ou copie suas informações antes de entrar novamente. ');banner.setAttribute('role','status');banner.style.cssText='padding:16px;border:1px solid #b8c7be;background:#f3f6f2;color:#20372e';const b=text('button','Entrar novamente');b.onclick=risk;banner.append(b);(document.querySelector('dialog[open]')??document.body).prepend(banner);}};
 const logout=async()=>{const current=panel,buttons=current.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);const n=admin()?'__Secure-artesaos_admin_csrf':'__Secure-artesaos_csrf',c=document.cookie.split('; ').find(c=>c.startsWith(n+'=')),csrf=c?decodeURIComponent(c.slice(n.length+1)):'';const headers=admin()?{'X-Pilot-Admin-Context':context(),'X-Pilot-Admin-CSRF':csrf}:{'X-Pilot-Context':context(),'X-Pilot-CSRF':csrf};try{const r=await original(prefix+(admin()?'admin/':'')+'auth/logout',{method:'POST',headers,credentials:'same-origin',cache:'no-store',signal:AbortSignal.timeout(10000)});if(!r.ok)throw Error();await window.artesaoOffline?.lock().catch(()=>{});allowedToLeave=true;location.replace(prefix+(admin()?'admin/':'')+'login');}catch{current.append(text('p','Não foi possível encerrar a sessão. Verifique sua conexão ou se a conta desta aba mudou e tente novamente.'));buttons.forEach(b=>b.disabled=false);}};
 const risk=()=>{if(document.querySelector('meta[name=artesao-update-page]')){void logout();return;}dialog('Atenção às suas alterações','O Artesão Digital recebeu uma atualização. Algumas informações que você ainda não salvou podem ser perdidas ao continuar.');panel.append(text('p','Pedimos desculpas pelo transtorno. Estamos trabalhando para tornar esse processo cada vez mais seguro e tranquilo.'));button('Voltar e revisar',review);button('Continuar',()=>void logout());};
 const changed=()=>{if(blocked)return;blocked=true;dialog('O Artesão Digital foi atualizado!','Fizemos algumas melhorias para deixar sua experiência ainda melhor.');panel.append(text('p','Para continuar, é só entrar novamente na sua conta.'));button('Entrar novamente',risk);};
 const check=()=>{if(blocked)return Promise.resolve(false);if(!context())return Promise.resolve(true);if(checking)return checking;checking=original(prefix+'version'+(admin()?'?admin=1':''),{cache:'no-store',credentials:'same-origin',signal:AbortSignal.timeout(10000)}).then(r=>{if(!r.ok)throw Error();return r.json();}).then(d=>{if(d.version!==version||d.reauthenticate){changed();return false;}return true;}).finally(()=>{checking=null;});return checking;};
 window.fetch=async(input,init)=>{const request=new Request(input,init),url=new URL(request.url);if(url.origin!==location.origin||!url.pathname.startsWith(prefix))return original(request);const api=url.pathname.startsWith(prefix+'api/')||url.pathname.startsWith(prefix+'admin/api/');if(!api)return original(request);if(blocked){if(!panel&&!banner?.isConnected)risk();return hold();}if(!['GET','HEAD','OPTIONS'].includes(request.method)&&!await check())return hold();if(blocked)return hold();const headers=new Headers(request.headers);headers.set('X-Artesao-Version',version);const r=await original(new Request(request,{headers}));if(r.status===409){try{if((await r.clone().json()).code==='APP_UPDATED'){changed();return hold();}}catch{}}return r;};
 document.addEventListener('submit',e=>{if(blocked){e.preventDefault();if(!panel)risk();}},true);
 document.addEventListener('click',e=>{if(blocked&&e.target.closest?.('a[href]')&&!panel){e.preventDefault();risk();}},true);
 document.addEventListener('input',()=>{edited=true;},true);document.addEventListener('change',()=>{edited=true;},true);
 addEventListener('beforeunload',e=>{if((blocked||edited)&&context()&&!allowedToLeave&&!document.querySelector('meta[name=artesao-update-page]')){e.preventDefault();e.returnValue='';}});
 document.addEventListener('visibilitychange',()=>{if(document.visibilityState==='visible')void check().catch(()=>{});});addEventListener('pageshow',e=>{if(e.persisted)void check().catch(()=>{});});
 if(document.readyState==='loading')window.pilotVersionReady=new Promise(resolve=>document.addEventListener('DOMContentLoaded',()=>{check().then(resolve).catch(()=>resolve(true));},{once:true}));else window.pilotVersionReady=check().catch(()=>true);
})();`;}
