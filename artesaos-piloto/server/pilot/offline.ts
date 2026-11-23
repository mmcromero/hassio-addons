import {createHash,createHmac,randomBytes} from 'node:crypto';
import {openSync,closeSync,readFileSync,writeFileSync,fstatSync,constants,readdirSync,statSync} from 'node:fs';
import {join} from 'node:path';
import type {PilotConfig} from './config.js';
import {pwaHead} from './pwa.js';
import {OFFLINE_FORMAT,offlineCachePrefix,offlineDatabase,OFFLINE_BINDING_COOKIE} from '../offline-format.js';
/** This key protects only local cached copies; it never authenticates an API request. */
export function offlineKey(dataDir:string){
 const path=join(dataDir,'.offline-key');try{writeFileSync(path,randomBytes(32),{flag:'wx',mode:0o600});}catch(e){if((e as NodeJS.ErrnoException).code!=='EEXIST')throw e;}
 const fd=openSync(path,constants.O_RDONLY|constants.O_NOFOLLOW);try{if(!fstatSync(fd).isFile()||fstatSync(fd).size!==32)throw Error('Invalid offline cache key');return readFileSync(fd);}finally{closeSync(fd);}
}
export function offlineNamespace(config:Pick<PilotConfig,'prefix'|'publicUrl'>,userId:string,tenantId:string){return createHash('sha256').update(JSON.stringify([config.publicUrl.origin,config.prefix,userId,tenantId])).digest('hex');}
/** Non-secret identity hint only. APIs never trust this cookie for authentication.
 * No application TTL is applied to snapshots. Browser cookie/storage policies can require login. */
export function offlineBinding(prefix:string,value:string){return `${OFFLINE_BINDING_COOKIE}=${value}; Path=${prefix}; Secure; SameSite=Lax; ${value?'Expires=Fri, 31 Dec 9999 23:59:59 GMT':'Max-Age=0'}`;}
export function offlineIdentity(master:Buffer,config:Pick<PilotConfig,'prefix'|'publicUrl'>,account:{userId:string;tenantId:string;email:string},version:string){
 const scope=JSON.stringify([config.publicUrl.origin,config.prefix,account.userId,account.tenantId]);const key=createHmac('sha256',master).update('key:'+scope).digest();
 return {account:account.userId,tenant:account.tenantId,namespace:offlineNamespace(config,account.userId,account.tenantId),label:account.email,key:key.toString('base64'),keyId:createHash('sha256').update(key).digest('hex'),version};
}
export function offlineShell(config:Pick<PilotConfig,'prefix'|'staticDir'>,version:string){
 const prefix=config.prefix;let html=readFileSync(join(config.staticDir,'index.html'),'utf8');
 html=html.replace('<html ','<html data-app-name="Artesão Digital" data-offline-shell="true" ').replace(/<title>[^<]*<\/title>/,'<title>Produtos offline — Artesão Digital</title>').replace(/(["'])\.\/assets\//g,`$1${prefix}assets/`).replace('</head>',`<base href="${prefix}"><meta name="artesao-version" content="${version}">${pwaHead(prefix)}<link rel="stylesheet" href="${prefix}pilot.css"></head>`);
 const assets:{url:string;sha256?:string;bytes?:number}[]=[];
 const walk=(dir:string,relative='')=>{for(const entry of readdirSync(dir,{withFileTypes:true})){const rel=relative+entry.name,path=join(dir,entry.name);if(entry.isDirectory())walk(path,rel+'/');else if(entry.isFile()&&/\.(js|css|png|svg|woff2?|ttf)$/.test(rel)){const bytes=readFileSync(path);assets.push({url:prefix+'assets/'+rel,bytes:bytes.length,sha256:createHash('sha256').update(bytes).digest('hex')});}}};walk(join(config.staticDir,'assets'));
 assets.push({url:prefix+'pilot.css'},{url:prefix+'manifest.webmanifest'},{url:prefix+'pwa/icon-192.png'},{url:prefix+'pwa/icon-512.png'},{url:prefix+'offline',bytes:Buffer.byteLength(html),sha256:createHash('sha256').update(html).digest('hex')});
 return {html,descriptor:{version,shell:prefix+'offline',assets}};
}
/** No authenticated response is cached. Never removes old copies, even on activation. */
export function offlineWorker(prefix:string){return `const dbName=${JSON.stringify(offlineDatabase(prefix))},ownCaches=${JSON.stringify(offlineCachePrefix(prefix))};
const assetState=()=>new Promise(resolve=>{const request=indexedDB.open(dbName,${OFFLINE_FORMAT});request.onupgradeneeded=()=>{request.transaction.abort();};request.onerror=()=>resolve(null);request.onsuccess=()=>{const db=request.result;if(!db.objectStoreNames.contains('state')){db.close();resolve(null);return;}const tx=db.transaction('state'),get=tx.objectStore('state').get('assets');get.onsuccess=()=>resolve(get.result??null);get.onerror=()=>resolve(null);tx.oncomplete=()=>db.close();};});
const cachedAsset=async request=>{const state=await assetState();for(const name of [...new Set([state?.cache,...(state?.history??[]).map(x=>x.cache)])].filter(n=>typeof n==='string'&&n.startsWith(ownCaches))){const found=await(await caches.open(name)).match(request);if(found)return found;}return null;};
const offlineDocument=async()=>{const state=await assetState();return state?(await caches.open(state.cache)).match(state.shell):null;};
self.addEventListener('install',event=>event.waitUntil(self.skipWaiting()));
self.addEventListener('activate',event=>event.waitUntil((async()=>{if(self.registration.navigationPreload)await self.registration.navigationPreload.disable();await self.clients.claim();})()));
self.addEventListener('fetch',event=>{const url=new URL(event.request.url);if(url.origin!==self.location.origin||!url.pathname.startsWith(prefix))return;
 const document=event.request.mode==='navigate'&&(url.pathname===prefix||url.pathname===prefix+'offline');
 const asset=url.pathname.startsWith(prefix+'assets/')||[prefix+'pilot.css',prefix+'manifest.webmanifest',prefix+'pwa/icon-192.png',prefix+'pwa/icon-512.png'].includes(url.pathname);
 event.respondWith((async()=>{try{const response=await fetch(event.request,{cache:'no-store'});if(response.status<500)return response;if(!document&&!asset)return response;const fallback=document?await offlineDocument():await cachedAsset(event.request);return fallback??response;}catch(error){const fallback=document?await offlineDocument():asset?await cachedAsset(event.request):null;if(fallback)return fallback;throw error;}})());
});`;}

/** Public login/update pages can lock local access without loading the React app. */
export function offlineLockScript(prefix:string){return `(()=>{window.artesaoOffline={lock:()=>new Promise((resolve,reject)=>{const account=document.querySelector('meta[name="pilot-context"]')?.content;if(!account){resolve();return;}const request=indexedDB.open(${JSON.stringify(offlineDatabase(prefix))},${OFFLINE_FORMAT});request.onupgradeneeded=()=>{request.transaction.abort();resolve();};request.onerror=()=>reject(Error('Não foi possível bloquear a consulta local.'));request.onsuccess=()=>{const db=request.result;if(!db.objectStoreNames.contains('access')){db.close();resolve();return;}const tx=db.transaction('access','readwrite'),store=tx.objectStore('access'),r=store.get('current');r.onsuccess=()=>{if(r.result?.account===account)store.delete('current');};tx.oncomplete=()=>{db.close();try{localStorage.setItem(${JSON.stringify(offlineDatabase(prefix)+':access')},String(Date.now()));}catch{}if(typeof BroadcastChannel!=='undefined'){const c=new BroadcastChannel(${JSON.stringify(offlineDatabase(prefix)+':access')});c.postMessage('changed');c.close();}window.dispatchEvent(new Event('artesao-offline-access'));resolve();};tx.onerror=tx.onabort=()=>{db.close();reject(Error('Não foi possível bloquear a consulta local.'));};};})};})();`;}
