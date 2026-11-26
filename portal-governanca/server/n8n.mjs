const MAX_PAGES=3;
const PAGE_SIZE=100;
export class N8nApiError extends Error{
 constructor(message,status=502,code="N8N_API_ERROR"){super(message);this.name="N8nApiError";this.status=status;this.code=code;}
}
function normalizeBaseUrl(value){
 if(typeof value!=="string"||!value.trim())return null;
 let url;try{url=new URL(value.trim());}catch{throw new N8nApiError("URL base do n8n inválida.",400,"N8N_BASE_URL_INVALID");}
 if(!["http:","https:"].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw new N8nApiError("URL base do n8n deve usar HTTP(S), sem credenciais, query ou fragmento.",400,"N8N_BASE_URL_INVALID");
 const host=url.hostname.toLowerCase();
 const internalHttp=host==="localhost"||host.endsWith(".local")||!host.includes(".")||/^10\./.test(host)||/^192\.168\./.test(host)||/^172\.(1[6-9]|2[0-9]|3[0-1])\./.test(host)||host==="127.0.0.1";
 if(url.protocol==="http:"&&!internalHttp)throw new N8nApiError("Use HTTPS para uma URL n8n fora da rede interna.",400,"N8N_HTTPS_REQUIRED");
 let path=url.pathname.replace(/\/+$/,"");if(!path.endsWith("/api/v1"))path+="/api/v1";url.pathname=path;return url;
}
function workflowSummary(item){
 if(!item||typeof item!=="object"||typeof item.id!=="string")return null;
 return {id:item.id,name:typeof item.name==="string"?item.name:"Sem nome",active:typeof item.active==="boolean"?item.active:null,createdAt:typeof item.createdAt==="string"?item.createdAt:null,updatedAt:typeof item.updatedAt==="string"?item.updatedAt:null,tags:Array.isArray(item.tags)?item.tags.slice(0,20).map(tag=>typeof tag?.name==="string"?tag.name:null).filter(Boolean):[],projectId:typeof item.projectId==="string"?item.projectId:null};
}
function executionSummary(item){
 if(!item||typeof item!=="object"||item.id===undefined||typeof item.workflowId!=="string")return null;
 return {id:String(item.id),workflowId:item.workflowId,status:typeof item.status==="string"?item.status:"unknown",mode:typeof item.mode==="string"?item.mode:"unknown",startedAt:typeof item.startedAt==="string"?item.startedAt:null,stoppedAt:typeof item.stoppedAt==="string"?item.stoppedAt:null,waitTill:typeof item.waitTill==="string"?item.waitTill:null};
}
export function createN8nClient({baseUrl="",apiKey="",fetchImpl=fetch,cacheMs=30_000,now=()=>Date.now()}={}){
 const base=normalizeBaseUrl(baseUrl),key=typeof apiKey==="string"?apiKey.trim():"";let cache=null,inFlight=null;
 async function getPage(resource,params={}){
  if(!base||!key)throw new N8nApiError("Integração n8n não configurada.",503,"N8N_NOT_CONFIGURED");
  const url=new URL(resource,base.href.endsWith("/")?base.href:base.href+"/");for(const [k,v] of Object.entries(params))if(v!==undefined&&v!==null&&v!=="")url.searchParams.set(k,String(v));
  let response;try{response=await fetchImpl(url,{method:"GET",headers:{Accept:"application/json","X-N8N-API-KEY":key},signal:AbortSignal.timeout(10_000),cache:"no-store"});}catch{throw new N8nApiError("Não foi possível alcançar a API do n8n.",503,"N8N_UNREACHABLE");}
  if(!response.ok){const status=response.status;const message=status===401?"Credencial da API n8n inválida ou expirada.":status===403?"A API n8n recusou a leitura; verifique o acesso da conta e da chave.":status===404?"Endpoint da API n8n não encontrado; confira a URL base e a versão.":status===429?"Limite de consultas da API n8n atingido.":"API n8n respondeu HTTP "+status+".";throw new N8nApiError(message,status===401?401:status===403?403:status===404?404:status===429?429:502,"N8N_HTTP_"+status);}
  return response.json();
 }
 async function list(resource,params={}){const items=[];let cursor=null,pages=0;do{const payload=await getPage(resource,{limit:PAGE_SIZE,...params,cursor});items.push(...(Array.isArray(payload?.data)?payload.data:[]));cursor=typeof payload?.nextCursor==="string"&&payload.nextCursor?payload.nextCursor:null;pages++;}while(cursor&&pages<MAX_PAGES);return{items,truncated:Boolean(cursor)};}
 async function getOverview(force=false){
  if(!force&&cache&&now()-cache.at<cacheMs)return{...cache.data,cache:"HIT"};if(inFlight)return inFlight;
  inFlight=(async()=>{const [workflows,executions]=await Promise.all([list("workflows"),list("executions",{includeData:"false"})]);const workflowRows=workflows.items.map(workflowSummary).filter(Boolean),executionRows=executions.items.map(executionSummary).filter(Boolean);const names=new Map(workflowRows.map(w=>[w.id,w.name]));const data={source:"n8n Public API v1",checkedAt:new Date(now()).toISOString(),workflowCount:workflowRows.length,activeCount:workflowRows.filter(w=>w.active===true).length,inactiveCount:workflowRows.filter(w=>w.active===false).length,executionCount:executionRows.length,failedExecutions:executionRows.filter(e=>["error","crashed"].includes(e.status)).length,workflows:workflowRows,executions:executionRows.map(e=>({...e,workflowName:names.get(e.workflowId)||null})),truncated:{workflows:workflows.truncated,executions:executions.truncated},cache:"MISS"};cache={at:now(),data};return data;})();
  try{return await inFlight;}finally{inFlight=null;}
 }
 return{configured:Boolean(base&&key),getOverview};
}
