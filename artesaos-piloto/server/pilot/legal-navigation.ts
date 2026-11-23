import type {PilotConfig} from './config.js';
type Target={kind:'landing'|'login'|'internal'|'admin';path:string};
const views=new Set(['ajuda','vendas','financeiro','pedidos','estoque','suporte','configuracoes','orcamentos','clientes','produto','diagnostico','produtos']);
/** Only actual document routes; no auth/API paths, arbitrary domains or redirect loops. */
export function legalReturnTarget(config:Pick<PilotConfig,'publicUrl'|'prefix'>,input:unknown):Target|null{
 if(typeof input!=='string'||!input||input.length>2048||/[\\\u0000-\u0020\u007f]/.test(input)||input.startsWith('//'))return null;
 let url:URL;try{url=new URL(input,config.publicUrl);}catch{return null;}
 if(url.origin!==config.publicUrl.origin||url.username||url.password)return null;
 if([...url.searchParams.keys()].some(k=>/^(code|state|token|password|secret)$/i.test(k)))return null;
 const path=url.pathname+url.search+url.hash;
 if(url.pathname==='/')return {kind:'landing',path:'/'};
 if([config.prefix+'login',config.prefix+'admin/login'].includes(url.pathname))return {kind:'login',path};
 if(url.pathname===config.prefix){const found=url.searchParams.getAll('view');if(found.length>1||found.length===1&&!views.has(found[0]))return null;return {kind:'internal',path};}
 const base=config.prefix+'admin/';
 if([base,base+'users',base+'support',base+'resources',base+'invitations'].includes(url.pathname))return {kind:'admin',path};
 return null;
}
export function legalBackLocation(config:Pick<PilotConfig,'publicUrl'|'prefix'>,input:unknown,userValid:boolean,adminValid:boolean):string{
 const target=legalReturnTarget(config,input);
 if(!target)return userValid?config.prefix:adminValid?config.prefix+'admin/':'/';
 if(target.kind==='internal')return userValid?target.path:config.prefix+'login';
 if(target.kind==='admin')return adminValid?target.path:config.prefix+'admin/login';
 return target.path;
}
export function legalNavigationScript(prefix:string){return `(()=>{
 const prefix=${JSON.stringify(prefix)},key='artesao-legal-origin:'+prefix;
 const local=value=>{try{const u=new URL(value,location.origin);return u.origin===location.origin?u:null;}catch{return null;}};
 const page=location.pathname,login=prefix+'login';
 if([login,prefix+'admin/login'].includes(page)){try{sessionStorage.setItem(key,page);}catch{}}
 else if(page===prefix||page.startsWith(prefix+'admin/')){try{sessionStorage.removeItem(key);}catch{}}
 const link=anchor=>{const url=local(anchor.href);if(!url||url.pathname!==prefix+'legal')return;
  if(page===prefix+'legal'||page===prefix+'legal/back')return;
  url.searchParams.set('returnTo',location.pathname+location.search+location.hash);anchor.href=url.href;
 };
 const links=()=>document.querySelectorAll('a[href]').forEach(link);links();
 if(typeof MutationObserver==='function')new MutationObserver(links).observe(document.body,{subtree:true,childList:true});
 document.addEventListener('click',event=>{const anchor=event.target.closest?.('a[href]');if(anchor)link(anchor);},true);
 if(page===prefix+'legal'){
  const input=document.querySelector('input[name=returnTo]'),query=new URLSearchParams(location.search);
  if(input&&!query.has('returnTo')){const from=local(document.referrer);try{const saved=sessionStorage.getItem(key);if((!from||from.pathname==='/')&&[login,prefix+'admin/login'].includes(saved))input.value=saved;}catch{}}
 }
})();`;}
