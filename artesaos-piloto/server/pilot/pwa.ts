/** PWA-01: installation metadata only. No personal data or offline cache. */
export function pwaManifest(prefix:string){
 return {id:prefix,name:'Artesão Digital',short_name:'Artesão Digital',lang:'pt-BR',start_url:prefix,scope:prefix,display:'standalone',theme_color:'#205e47',background_color:'#f5f2e9',icons:[192,512].map(size=>({src:prefix+'pwa/icon-'+size+'.png',sizes:size+'x'+size,type:'image/png',purpose:'any'}))};
}
export function pwaHead(prefix:string){
 return `<link rel="manifest" href="${prefix}manifest.webmanifest"><meta name="theme-color" content="#205e47"><link rel="apple-touch-icon" href="${prefix}pwa/icon-192.png">`;
}
