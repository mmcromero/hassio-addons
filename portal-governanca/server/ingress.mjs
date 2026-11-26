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
 // Supervisor/proxy variants: some preserve the external Ingress prefix in
 // the upstream path; others strip it before forwarding. The caller MUST
 // validate both the trusted proxy peer and X-Ingress-Path before using this.
 if(pathname===basePath||pathname===basePath+"/")return "/";
 if(pathname.startsWith(basePath+"/"))return pathname.slice(basePath.length)||"/";
 // A different dynamic Ingress token is never an app-relative path.
 if(pathname.startsWith(INGRESS_PREFIX))return null;
 // The session header is the authority for the dynamic base path. When the
 // trusted proxy has already stripped that prefix, retain the app-relative path.
 if(pathname.startsWith("/")&&!pathname.startsWith("//"))return pathname;
 // Normalize the duplicated root slash defensively, without accepting other
 // doubled path segments or an unrelated Ingress prefix.
 if(pathname==="//")return "/";
 return null;
}

export function isN8nPeer(value,allowedPeer){
 const expected=normalizePeerAddress(allowedPeer);
 return Boolean(expected&&normalizePeerAddress(value)===expected);
}
