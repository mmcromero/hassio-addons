/** OFF-01 format: shared by the page and its existing scoped worker. */
export const OFFLINE_FORMAT=1;
export const offlineDatabase=(prefix:string)=>'artesao-offline:'+prefix;
export const offlineCachePrefix=(prefix:string)=>'artesao-offline-assets:'+encodeURIComponent(prefix)+':';
export const offlineStores=['access','heads','snapshots','photos','state'] as const;
export type OfflineIdentity={account:string;tenant:string;namespace:string;key:string;keyId:string;label:string;version:string};
export type OfflineAssets={version:string;shell:string;assets:{url:string;sha256?:string;bytes?:number}[]};
export const OFFLINE_BINDING_COOKIE='__Secure-artesaos_offline_binding';
