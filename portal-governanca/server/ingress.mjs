const INGRESS_PREFIX="/api/hassio_ingress/";

export function normalizePeerAddress(value){
 if(typeof value!=="string")return "";
 let address=value.toLowerCase().split("%")[0];
 if(address.startsWith("::ffff:"))address=address.slice(7);
 return address;
}
export function isIngressPeer(value){return normalizePeerAddress(value)==="172.30.32.2";}
export function isLoopbackPeer(value){
 const address=normalizePeerAddress(value);
 return address==="127.0.0.1"||address==="::1";
}
export function getIngressBasePath(value){
 if(typeof value!=="string")return null;
 const candidate=value.trim().replace(/\/+$/,"");
 if(!candidate.startsWith(INGRESS_PREFIX))return null;
 const token=candidate.slice(INGRESS_PREFIX.length);
 if(!token||token==="."||token===".."||token.includes("/")||token.includes("\\")||token.includes("?")||token.includes("#"))return null;
 if(!/^[A-Za-z0-9._~=-]{1,512}$/.test(token))return null;
 return candidate;
}
export function stripIngressPath(pathname,basePath){
 if(typeof pathname!=="string"||typeof basePath!=="string")return null;
 if(pathname===basePath)return "/";
 if(pathname.startsWith(basePath+"/"))return pathname.slice(basePath.length)||"/";
 return null;
}
