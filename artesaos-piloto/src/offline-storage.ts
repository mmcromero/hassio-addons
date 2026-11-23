import {OFFLINE_FORMAT,offlineDatabase,offlineStores,OFFLINE_BINDING_COOKIE} from '../server/offline-format';
import type {OfflineIdentity} from '../server/offline-format';
import type {EditableProduct} from './ProductForm';
export const prefix=()=>new URL(document.baseURI).pathname;
export const currentBinding=()=>document.cookie.split('; ').find(c=>c.startsWith(OFFLINE_BINDING_COOKIE+'='))?.slice(OFFLINE_BINDING_COOKIE.length+1)??'';
const changeName=()=>offlineDatabase(prefix())+':access';
export type Access={id:'current';account:string;tenant:string;namespace:string;label:string;key:CryptoKey;keyId:string;serial:string};
type Cipher={iv:Uint8Array;data:ArrayBuffer};
type PhotoRecord=Cipher&{id:string;content:string;namespace:string;hash:string};
export type Catalog={format:number;account:string;tenant:string;namespace:string;label:string;preparedAt:string;products:(EditableProduct&{archived?:boolean})[];categories:{path:string}[];pageSize:string;images:Record<string,{id:string;hash:string}>};
export type LocalCatalog=Catalog&{objectUrls:Set<string>;accessSerial:string;recovered:boolean};
let database:Promise<IDBDatabase>|null=null;
export function db(){return database??=new Promise((resolve,reject)=>{
 if(!globalThis.indexedDB){reject(Error('Armazenamento local indisponível neste navegador.'));return;}
 const r=indexedDB.open(offlineDatabase(prefix()),OFFLINE_FORMAT);
 r.onupgradeneeded=()=>{const d=r.result;for(const name of offlineStores){const store=d.createObjectStore(name,{keyPath:'id'});if(name==='photos')store.createIndex('content','content');if(name==='snapshots')store.createIndex('namespace','namespace');}};
 r.onerror=()=>{database=null;reject(Error('Não foi possível abrir o armazenamento local.'));};r.onblocked=()=>reject(Error('Feche outras abas para preparar o armazenamento local.'));
 r.onsuccess=()=>{r.result.onversionchange=()=>{r.result.close();database=null;};resolve(r.result);};
 });}
export async function read<T>(store:string,id:string):Promise<T|undefined>{const d=await db();return new Promise((resolve,reject)=>{const tx=d.transaction(store),r=tx.objectStore(store).get(id);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Falha ao consultar a cópia local.'));});}
export async function write(store:string,value:unknown){const d=await db();return new Promise<void>((resolve,reject)=>{const tx=d.transaction(store,'readwrite');tx.objectStore(store).put(value);tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(Error('Não foi possível gravar. A cópia anterior foi preservada. Verifique o espaço disponível.'));});}
export function notifyAccess(){window.dispatchEvent(new Event('artesao-offline-access'));try{localStorage.setItem(changeName(),crypto.randomUUID());}catch{}if(typeof BroadcastChannel!=='undefined'){const c=new BroadcastChannel(changeName());c.postMessage('changed');c.close();}}
export function listenAccess(fn:()=>void){const storage=(e:StorageEvent)=>{if(e.key===changeName())fn();};window.addEventListener('storage',storage);window.addEventListener('artesao-offline-access',fn);const channel=typeof BroadcastChannel!=='undefined'?new BroadcastChannel(changeName()):null;if(channel)channel.onmessage=fn;return()=>{window.removeEventListener('storage',storage);window.removeEventListener('artesao-offline-access',fn);channel?.close();};}
export async function lockAccess(account?:string){const d=await db();await new Promise<void>((resolve,reject)=>{const tx=d.transaction('access','readwrite'),s=tx.objectStore('access'),r=s.get('current');r.onsuccess=()=>{if(r.result&&(!account||r.result.account===account))s.delete('current');};tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(Error('Não foi possível bloquear a consulta local.'));});notifyAccess();}
export async function bindAccess(identity:OfflineIdentity):Promise<Access>{
 if(currentBinding()!==identity.namespace)throw Error('Não foi possível confirmar o vínculo local desta conta.');
 const old=await read<Access>('access','current'),head=await read<{keyId?:string}>('heads',identity.namespace);
 if(head?.keyId&&head.keyId!==identity.keyId)throw Error('A chave da instalação mudou. Sua cópia foi preservada; recupere a chave original antes de atualizar esta preparação.');
 if(old?.namespace===identity.namespace&&old.keyId===identity.keyId)return old;
 // Revoke the previous account's key separately, before attempting a new write.
 if(old)await lockAccess(old.account);
 const bytes=Uint8Array.from(atob(identity.key),c=>c.charCodeAt(0));const key=await crypto.subtle.importKey('raw',bytes,'AES-GCM',false,['encrypt','decrypt']);
 const value:Access={id:'current',account:identity.account,tenant:identity.tenant,namespace:identity.namespace,label:identity.label,key,keyId:identity.keyId,serial:crypto.randomUUID()};const d=await db();const saved=await new Promise<Access>((resolve,reject)=>{const tx=d.transaction('access','readwrite'),store=tx.objectStore('access'),r=store.get('current');let result=value;r.onsuccess=()=>{if(r.result){if(r.result.namespace!==value.namespace||r.result.keyId!==value.keyId){tx.abort();return;}result=r.result;}else store.put(value);};tx.oncomplete=()=>resolve(result);tx.onabort=tx.onerror=()=>reject(Error('Não foi possível confirmar a conta da consulta local.'));});notifyAccess();return saved;
}
export async function assertAccess(access:Access){const now=await read<Access>('access','current');if(currentBinding()!==access.namespace||!now||now.serial!==access.serial||now.namespace!==access.namespace)throw Error('A conta desta consulta mudou. Entre novamente com a conta correspondente.');}
const encode=(text:string)=>new TextEncoder().encode(text);
export async function encrypt(key:CryptoKey,data:BufferSource,aad:string):Promise<Cipher>{const iv=crypto.getRandomValues(new Uint8Array(12));return {iv,data:await crypto.subtle.encrypt({name:'AES-GCM',iv,additionalData:encode(aad)},key,data)};}
export async function decrypt(key:CryptoKey,cipher:Cipher,aad:string){return crypto.subtle.decrypt({name:'AES-GCM',iv:cipher.iv as BufferSource,additionalData:encode(aad)},key,cipher.data);}
export async function hash(data:BufferSource){return Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',data))).map(n=>n.toString(16).padStart(2,'0')).join('');}
export async function photo(access:Access,sha:string):Promise<PhotoRecord|undefined>{const d=await db();const rows:PhotoRecord[]=await new Promise((resolve,reject)=>{const r=d.transaction('photos').objectStore('photos').index('content').getAll(access.namespace+':'+sha);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Não foi possível conferir as fotos locais.'));});for(const r of rows){try{if(r.namespace!==access.namespace||r.hash!==sha)continue;if(await hash(await decrypt(access.key,r,'photo:'+r.content))===sha)return r;}catch{}}return undefined;}
export async function savePhoto(access:Access,sha:string,bytes:ArrayBuffer){await assertAccess(access);if(await hash(bytes)!==sha)throw Error('A foto recebida não passou na conferência. A cópia anterior foi mantida.');const content=access.namespace+':'+sha;const value:PhotoRecord={id:crypto.randomUUID(),content,namespace:access.namespace,hash:sha,...await encrypt(access.key,bytes,'photo:'+content)};await write('photos',value);return value;}
export async function commitCatalog(access:Access,catalog:Catalog,baseHead:string|undefined,assets:{cache:string;shell:string}){
 await assertAccess(access);const id=crypto.randomUUID(),value={id,namespace:access.namespace,preparedAt:catalog.preparedAt,...await encrypt(access.key,encode(JSON.stringify(catalog)),'snapshot:'+access.namespace+':'+id)};const d=await db();
 await new Promise<void>((resolve,reject)=>{const tx=d.transaction(['access','heads','snapshots','state'],'readwrite'),a=tx.objectStore('access').get('current'),previous=tx.objectStore('state').get('assets'),h=tx.objectStore('heads').get(access.namespace);h.onsuccess=()=>{try{if(a.result?.serial!==access.serial||h.result?.snapshot!==baseHead){tx.abort();return;}tx.objectStore('snapshots').add(value);tx.objectStore('heads').put({id:access.namespace,snapshot:id,preparedAt:catalog.preparedAt,keyId:access.keyId});const history=[previous.result,...(previous.result?.history??[])].filter(x=>x&&x.cache!==assets.cache).map(x=>({cache:x.cache,shell:x.shell}));tx.objectStore('state').put({id:'assets',...assets,history});}catch{tx.abort();}};tx.oncomplete=()=>resolve();tx.onabort=tx.onerror=()=>reject(Error('A preparação não foi confirmada. A cópia anterior foi preservada; confira espaço e conta e tente novamente.'));});
}
export async function loadCatalog():Promise<LocalCatalog>{
 const access=await read<Access>('access','current');if(!access||currentBinding()!==access.namespace)throw Error('Entre online com a conta correspondente para recuperar sua cópia. Nenhum dado local foi apagado.');
 const context=document.querySelector<HTMLMetaElement>('meta[name="pilot-context"]')?.content;if(context&&context!==access.account)throw Error('A cópia pertence a outra conta. Entre novamente para continuar.');
 const d=await db(),head=await read<{snapshot:string}>('heads',access.namespace);const rows:any[]=await new Promise((resolve,reject)=>{const r=d.transaction('snapshots').objectStore('snapshots').index('namespace').getAll(access.namespace);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(Error('Não foi possível consultar a cópia.'));});
 rows.sort((a,b)=>a.id===head?.snapshot?-1:b.id===head?.snapshot?1:b.preparedAt.localeCompare(a.preparedAt));
 for(const row of rows){try{
  const catalog=JSON.parse(new TextDecoder().decode(await decrypt(access.key,row,'snapshot:'+access.namespace+':'+row.id))) as Catalog;
  if(catalog.format!==OFFLINE_FORMAT||catalog.namespace!==access.namespace||catalog.account!==access.account||catalog.tenant!==access.tenant||!Array.isArray(catalog.products))throw Error();
  for(const [url,ref] of Object.entries(catalog.images)){const image=await read<PhotoRecord>('photos',ref.id);if(!image||image.namespace!==access.namespace||image.hash!==ref.hash)throw Error();const bytes=await decrypt(access.key,image,'photo:'+image.content);if(await hash(bytes)!==ref.hash)throw Error();}
  await assertAccess(access);return {...catalog,objectUrls:new Set<string>(),accessSerial:access.serial,recovered:row.id!==head?.snapshot};
 }catch{}}
 throw Error('Nenhuma cópia completa está disponível para esta conta. Prepare os dados online; os registros locais existentes foram preservados.');
}
export async function loadPhoto(catalog:LocalCatalog,url:string){
 const ref=catalog.images[url];if(!ref)return null;const access=await read<Access>('access','current');if(!access||currentBinding()!==catalog.namespace||access.serial!==catalog.accessSerial||access.namespace!==catalog.namespace)throw Error('Conta mudou.');const image=await read<PhotoRecord>('photos',ref.id);if(!image||image.namespace!==access.namespace)throw Error('Foto indisponível.');const bytes=await decrypt(access.key,image,'photo:'+image.content);if(await hash(bytes)!==ref.hash)throw Error('Foto não conferida.');await assertAccess(access);const result=URL.createObjectURL(new Blob([bytes],{type:'image/png'}));catalog.objectUrls.add(result);return result;
}
export function releasePhoto(catalog:LocalCatalog,url:string){URL.revokeObjectURL(url);catalog.objectUrls.delete(url);}
export function releaseCatalog(catalog:LocalCatalog|null){if(catalog)for(const url of catalog.objectUrls)URL.revokeObjectURL(url);catalog?.objectUrls.clear();}
