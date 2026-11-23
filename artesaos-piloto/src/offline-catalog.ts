import type {OfflineAssets,OfflineIdentity} from '../server/offline-format';
import {OFFLINE_FORMAT,offlineCachePrefix} from '../server/offline-format';
import {bindAccess,assertAccess,read,hash,photo,savePhoto,commitCatalog,prefix,lockAccess,currentBinding,type Access,type Catalog} from './offline-storage';
declare const __ARTESAO_RELEASE__:string;
export const offlineVersion=__ARTESAO_RELEASE__;
export class OfflineNetworkError extends Error{}
export class OfflineAccountError extends Error{}
export class OfflineLoginError extends Error{}
async function response(path:string,headers?:HeadersInit){
 let r:Response;try{r=await fetch(new URL(path,document.baseURI),{credentials:'same-origin',cache:'no-store',headers,signal:AbortSignal.timeout(12000)});}catch{throw new OfflineNetworkError('Sem conexão com o servidor.');}
 if(!r.ok){if(r.status===401)throw new OfflineLoginError('Entre novamente para atualizar os dados.');if([403,409].includes(r.status))throw new OfflineAccountError('A conta ou a versão mudou. Reabra o aplicativo e entre novamente.');throw Error('Não foi possível preparar todos os dados. A cópia anterior foi preservada.');}return r;
}
export async function identify(){
 if(!navigator.onLine)throw new OfflineNetworkError('Sem conexão com o servidor.');
 const s=await(await response('api/pilot/session')).json();if(typeof s.context!=='string')throw new OfflineAccountError('Sessão não confirmada.');
 const context=document.querySelector<HTMLMetaElement>('meta[name="pilot-context"]')?.content;
 if(context&&context!==s.context){await lockAccess(context);throw new OfflineAccountError('A conta desta janela mudou. Reabra o aplicativo.');}
 const identity:OfflineIdentity=await(await response('api/offline/identity',{'X-Pilot-Context':s.context,'X-Artesao-Version':offlineVersion})).json();
 if(identity.account!==s.context||!identity.tenant||!/^[a-f0-9]{64}$/.test(identity.namespace)||!/^[a-f0-9]{64}$/.test(identity.keyId)||identity.version!==offlineVersion)throw new OfflineAccountError('O aplicativo foi atualizado. Entre novamente para preparar os dados com a versão atual.');
 return identity;
}
export async function authorize(){return bindAccess(await identify());}
function safeAsset(value:string){const url=new URL(value,document.baseURI),base=prefix();if(url.origin!==location.origin||url.search||!(url.pathname.startsWith(base+'assets/')||[base+'offline',base+'pilot.css',base+'manifest.webmanifest',base+'pwa/icon-192.png',base+'pwa/icon-512.png'].includes(url.pathname)))throw Error('Arquivo de preparação inválido.');return url.href;}
async function prepareAssets(){
 const descriptor:OfflineAssets=await(await response('offline-shell.json')).json();if(descriptor.version!==offlineVersion||!Array.isArray(descriptor.assets)||descriptor.shell!==prefix()+'offline')throw new OfflineAccountError('Versão de preparação incompatível. Reabra o aplicativo.');
 const cache=offlineCachePrefix(prefix())+offlineVersion+':'+await hash(new TextEncoder().encode(JSON.stringify(descriptor))),storage=await caches.open(cache);
 for(const asset of descriptor.assets){const url=safeAsset(asset.url);let file=await storage.match(url);if(!file)file=await response(asset.url);const bytes=await file.clone().arrayBuffer();if(!bytes.byteLength||asset.bytes!==undefined&&asset.bytes!==bytes.byteLength||asset.sha256&&await hash(bytes)!==asset.sha256)throw Error('Um arquivo da aplicação não passou na conferência. A cópia anterior foi mantida.');
  if(asset.url===descriptor.shell){const html=new TextDecoder().decode(bytes);if(!html.includes('data-offline-shell="true"')||html.includes('name="pilot-context"'))throw Error('Página de consulta offline inválida.');}
  await storage.put(url,file);
 }
 if(!await storage.match(safeAsset(descriptor.shell)))throw Error('A página offline não foi preparada.');
 return {cache,shell:safeAsset(descriptor.shell)};
}
const internal=/^api\/product-photos\/[a-f0-9]{32}\/([a-f0-9]{64})\.png$/;
let preparing=false;
export async function prepareCatalog(progress:(message:string)=>void){
 if(preparing)throw Error('Uma preparação já está em andamento nesta janela.');preparing=true;
 try{
  progress('Conferindo conta e catálogo…');const access=await authorize(),head=await read<{snapshot:string}>('heads',access.namespace);
  const source=await(await response('api/products/export',{'X-Pilot-Context':access.account,'X-Artesao-Version':offlineVersion})).json();
  if(source.type!=='catalog-export-v1'||!Array.isArray(source.products)||source.products.some((p:any)=>!Number.isSafeInteger(p.id)||p.id<1||typeof p.name!=='string'||!p.prices))throw Error('Catálogo incompleto. A cópia anterior foi mantida.');
  const images:Catalog['images']={},urls=[...new Set<string>(source.products.map((p:any)=>p.imageUrl??'').filter((url:string)=>internal.test(url)))];
  const estimate=await navigator.storage?.estimate?.().catch(()=>null);const planned=JSON.stringify(source.products).length*4+2*1024*1024;let remaining=estimate?.quota&&estimate.usage!==undefined?estimate.quota-estimate.usage-planned:Infinity;
  if(estimate?.quota&&estimate.usage!==undefined&&estimate.quota-estimate.usage<planned)throw Error('Espaço insuficiente para preparar com margem de segurança. A cópia anterior foi preservada.');
  for(let i=0;i<urls.length;i++){
   await assertAccess(access);progress(`Preparando fotos ${i+1} de ${urls.length}…`);const url=urls[i],sha=internal.exec(url)![1];let stored=await photo(access,sha);
   if(!stored){if(remaining<512000)throw Error('Espaço insuficiente. A cópia anterior foi preservada.');const r=await response(url,{'X-Pilot-Context':access.account});if(!r.headers.get('content-type')?.startsWith('image/png'))throw Error('Uma foto interna não está disponível. A preparação anterior foi mantida.');const bytes=await r.arrayBuffer();if(bytes.byteLength>512000||!bytes.byteLength)throw Error('Foto inválida. A cópia anterior foi mantida.');stored=await savePhoto(access,sha,bytes);remaining-=bytes.byteLength+64;}
   images[url]={id:stored.id,hash:sha};
  }
  progress('Preparando abertura sem internet…');const assets=await prepareAssets();
  const confirm=await(await response('api/products/export',{'X-Pilot-Context':access.account,'X-Artesao-Version':offlineVersion})).json();
  if(JSON.stringify(source.products)!==JSON.stringify(confirm.products)||JSON.stringify(source.categories)!==JSON.stringify(confirm.categories))throw Error('O catálogo mudou durante a preparação. A cópia anterior foi mantida; tente novamente.');
  const catalog:Catalog={format:OFFLINE_FORMAT,account:access.account,tenant:access.tenant,namespace:access.namespace,label:access.label,preparedAt:new Date().toISOString(),products:source.products,categories:source.categories,pageSize:'10',images};
  await commitCatalog(access,catalog,head?.snapshot,assets);
  const persistent=await navigator.storage?.persist?.().catch(()=>false);return {...catalog,persistent:!!persistent};
 }catch(e){if(e instanceof DOMException)throw Error('Não foi possível guardar a preparação. Verifique o espaço e as permissões de armazenamento. A cópia anterior foi preservada.');throw e;}finally{preparing=false;}
}
export async function currentPreparation(){const access=await read<Access>('access','current');return access&&access.namespace===currentBinding()?read<{preparedAt:string}>('heads',access.namespace):undefined;}
