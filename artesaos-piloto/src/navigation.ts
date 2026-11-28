type RouteSnapshot = string;
const listeners = new Set<()=>void>();
let installed = false;
let routePreloader:((view:string)=>Promise<unknown>|undefined)|undefined;
let navigationToken=0;
export function registerRoutePreloader(preloader:(view:string)=>Promise<unknown>|undefined){routePreloader=preloader;}
let snapshot:RouteSnapshot = typeof window==='undefined'?'':window.location.pathname + window.location.search + window.location.hash;
export function preserveContextParams(next:URL,current:URL){new URLSearchParams(current.search).forEach((value,key)=>{if(!['view','area','settings'].includes(key)&&!next.searchParams.has(key))next.searchParams.append(key,value);});return next;}
function publish(){snapshot=location.pathname+location.search+location.hash;for(const listener of listeners)listener();}
function saveScroll(){const state=history.state&&typeof history.state==='object'?history.state:{};history.replaceState({...state,adScrollY:window.scrollY},'',location.href);}
function eligible(anchor:HTMLAnchorElement,event:MouseEvent){
 if(document.documentElement.hasAttribute('data-offline-mode'))return false;
 if(event.defaultPrevented||event.button!==0||event.metaKey||event.ctrlKey||event.shiftKey||event.altKey)return false;
 if(anchor.target&&anchor.target!=='_self')return false;
 if(anchor.hasAttribute('download')||anchor.rel.split(/\s+/).includes('external'))return false;
 const raw=anchor.getAttribute('href');if(!raw||raw.startsWith('#'))return false;
 const target=new URL(raw,location.href);
 if(target.origin!==location.origin||target.pathname!==location.pathname)return false;
 if(target.search===location.search&&target.hash!==location.hash)return false;
 const current=new URL(location.href),sameView=target.searchParams.get('view')===current.searchParams.get('view');
 const settingsChange=target.searchParams.get('view')==='configuracoes'&&(target.searchParams.get('settings')!==current.searchParams.get('settings')||target.searchParams.get('area')!==current.searchParams.get('area'));
 if(sameView&&!settingsChange)return false;
 if(!target.searchParams.has('view')&&!target.searchParams.has('settings')&&!target.searchParams.has('area'))return false;
 if(target.pathname.includes('/auth/')||target.pathname.endsWith('/login')||target.pathname.endsWith('/logout')||target.pathname.endsWith('/legal'))return false;
 return true;
}
export function subscribeRoute(listener:()=>void){listeners.add(listener);if(!installed){installed=true;history.scrollRestoration='manual';document.addEventListener('click',event=>{const target=event.target;if(!(target instanceof Element))return;const anchor=target.closest('a[href]');if(!(anchor instanceof HTMLAnchorElement))return;if(anchor.href===location.href){event.preventDefault();return;}if(!eligible(anchor,event))return;event.preventDefault();saveScroll();const next=preserveContextParams(new URL(anchor.href),new URL(location.href));const token=++navigationToken;const commit=()=>{if(token!==navigationToken)return;document.documentElement.removeAttribute('data-route-pending');history.pushState({...(history.state??{}),adScrollY:0},'',next.href);publish();window.scrollTo({top:0,behavior:'instant'});};const preload=routePreloader?.(next.searchParams.get('view')??'');if(preload){document.documentElement.setAttribute('data-route-pending','true');void preload.catch(()=>{}).then(commit);}else{document.documentElement.removeAttribute('data-route-pending');commit();}});addEventListener('popstate',()=>{navigationToken++;document.documentElement.removeAttribute('data-route-pending');publish();const y=history.state?.adScrollY;requestAnimationFrame(()=>window.scrollTo({top:Number.isFinite(y)?y:0,behavior:'instant'}));});}return()=>listeners.delete(listener);}
export function getRouteSnapshot(){return snapshot;}
