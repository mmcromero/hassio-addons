import {offlineWorker} from './offline.js';
// The Home Assistant root worker may cache every file on its origin. Keep this
// adapter confined to the pilot scope; never unregister it or clear HA caches.
export function browserScripts(prefix:string,version:string){
 const scope=JSON.stringify(prefix),worker=JSON.stringify(prefix+'service-worker.js?v='+version);
 const serviceWorker=`const prefix=${scope};\n`+offlineWorker(prefix);
 const bootstrap=`(()=>{
 const report=()=>{
  let status=document.getElementById('pilot-browser-status');
  if(!status){status=document.createElement('p');status.id='pilot-browser-status';status.setAttribute('role','alert');document.body.prepend(status);}
  status.textContent='Não foi possível preparar o aplicativo neste navegador. Tente abrir novamente com conexão ativa.';
 };
 window.pilotBrowserReady=(async()=>{
  if(!('serviceWorker' in navigator))return;
  await navigator.serviceWorker.register(${worker},{scope:${scope},updateViaCache:'none'});
  const target=new URL(${worker},location.origin).href;
  if(navigator.serviceWorker.controller?.scriptURL===target)return;
  await new Promise((resolve,reject)=>{
   const check=()=>{if(navigator.serviceWorker.controller?.scriptURL===target){clearTimeout(timer);navigator.serviceWorker.removeEventListener('controllerchange',check);resolve();}};
   const timer=setTimeout(()=>{navigator.serviceWorker.removeEventListener('controllerchange',check);reject(Error('Preparation timeout'));},12000);
   navigator.serviceWorker.addEventListener('controllerchange',check);check();
  });
 })();
 const ready=async()=>{
  const done=window.pilotLoading?.begin('Carregando aplicativo…');
  try{
   if(window.pilotVersionReady&&!await window.pilotVersionReady)return;
   await window.pilotBrowserReady;
   document.querySelectorAll('[data-pilot-login]').forEach(button=>button.disabled=false);
   for(const style of document.querySelectorAll('link[data-pilot-href]'))style.href=style.dataset.pilotHref;
   for(const script of document.querySelectorAll('script[data-pilot-module]'))await import(script.dataset.pilotModule);
  }catch{report();}finally{done?.();}
 };
 // Attach rejection handling immediately, even while the document is parsing.
 window.pilotBrowserReady.catch(()=>{});
 if(document.readyState==='loading')addEventListener('DOMContentLoaded',ready,{once:true});else ready();
})();`;
 return {serviceWorker,bootstrap};
}


export function sessionScript(prefix:string,csrfCookie:string){
 return `(()=>{
 const prefix=${JSON.stringify(prefix)},cookieName=${JSON.stringify(csrfCookie)};
 const original=window.fetch.bind(window);
 const context=document.querySelector('meta[name=pilot-context]')?.content;
 const item=document.cookie.split('; ').find(value=>value.startsWith(cookieName+'='));
 const csrf=item?decodeURIComponent(item.slice(cookieName.length+1)):'';
 window.fetch=(input,init)=>{
  const request=new Request(input,init),url=new URL(request.url);
  if(url.origin===location.origin&&url.pathname.startsWith(prefix)){
   const headers=new Headers(request.headers);
   if(context)headers.set('X-Pilot-Context',context);
   if(csrf&&!['GET','HEAD','OPTIONS'].includes(request.method))headers.set('X-Pilot-CSRF',csrf);
   return original(new Request(request,{headers,cache:'no-store'})).then(async response=>{if(response.status===428){try{if((await response.clone().json()).code==='LEGAL_REQUIRED')window.dispatchEvent(new Event('artesao-legal-required'));}catch{}}return response;}).catch(error=>{if(url.pathname.startsWith(prefix+'api/'))window.dispatchEvent(new Event('artesao-server-unavailable'));throw error;});
  }
  return original(request);
 };
 addEventListener('DOMContentLoaded',async()=>{
  try{await window.pilotBrowserReady;}catch{return;}
  if(window.pilotVersionReady&&!await window.pilotVersionReady)return;
  let response;try{response=await fetch(prefix+'api/pilot/session');}catch{return;}
  if(!response.ok){location.replace(prefix+'login');return;}
  const data=await response.json();
  if(document.body.classList.contains('pilot-first-access-detail'))return;
  const bar=document.createElement('nav');bar.id='pilot-account';bar.className='pilot-account-user-layout';bar.setAttribute('aria-label','Conta do Artesão Digital');
  const title=document.createElement('span');title.className='pilot-account-title';title.textContent='Artesão Digital';if(window.pilotBrand)window.pilotBrand(title);
  const name=document.createElement('span');name.className='pilot-account-user';name.textContent=data.email;name.title=data.email;
  const logout=document.createElement('button');logout.textContent='Sair';
  const status=document.createElement('p');status.id='pilot-session-status';status.setAttribute('role','alert');status.hidden=true;
  status.style.gridColumn='1 / -1';status.style.margin='0';status.style.fontSize='14px';
  logout.onclick=async()=>{
   logout.disabled=true;logout.textContent='Saindo…';status.hidden=true;
   const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),10000);
   try{
    const result=await fetch(prefix+'auth/logout',{method:'POST',signal:controller.signal});
    if(result.ok){await window.artesaoOffline?.lock().catch(()=>{});location.replace(prefix+'login');return;}
    status.textContent=result.status===403?'A sessão desta aba mudou. Reabra a página antes de tentar sair.':'Não foi possível sair. Tente novamente.';
   }catch{status.textContent='Não foi possível sair. Verifique sua conexão e tente novamente.';}
   finally{
    clearTimeout(timer);logout.disabled=false;logout.textContent='Sair';
    if(status.textContent){status.hidden=false;document.body.style.paddingTop=((document.getElementById('pilot-shell')??bar).offsetHeight+16)+'px';}
   }
  };
  const navigation=document.createElement('div');navigation.id='pilot-navigation';
  bar.append(title,name,logout,status);const shell=document.createElement('header');shell.id='pilot-shell';shell.append(bar,navigation);document.body.classList.add('pilot-session-active');document.body.prepend(shell);
  new ResizeObserver(()=>{document.body.style.paddingTop=((document.getElementById('pilot-shell')??bar).offsetHeight+16)+'px';}).observe(shell);
 });
})();`;
}
