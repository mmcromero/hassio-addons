import http from "node:http";
import {readFile,stat} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {timingSafeEqual} from "node:crypto";
import {createGitHubClient} from "./github.mjs";
import {createN8nClient} from "./n8n.mjs";
import {createLedger} from "./ledger.mjs";
import {createRunnerBridge} from "./runner-bridge.mjs";
import {filterUnrecordedAgentEvents} from "./agent-events.mjs";
import {getIngressBasePath,isIngressPeer,isLoopbackPeer,isN8nPeer,stripIngressPath} from "./ingress.mjs";

if(process.env.NODE_ENV==="development")await import("dotenv/config");
const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const DIST=path.join(ROOT,"dist");
const ingressMode=process.env.PORTAL_MODE==="ingress";
const production=process.env.NODE_ENV!=="development";
const PORT=Number(process.env.PORT||(ingressMode?8099:production?8080:4174));
const HOST=process.env.PORTAL_HOST||(ingressMode?"0.0.0.0":"127.0.0.1");
const registry=JSON.parse(await readFile(path.join(ROOT,"config/portfolio.json"),"utf8"));
const haConfig=JSON.parse(await readFile(path.join(ROOT,"config/home-assistant-addons.json"),"utf8"));
const haMappings=new Map((haConfig.mappings||[]).map(item=>[item.slug,item]));
const github=createGitHubClient({token:process.env.GITHUB_TOKEN||"",writeToken:process.env.GITHUB_WRITE_TOKEN||""});
const n8n=createN8nClient({baseUrl:process.env.N8N_BASE_URL||"",apiKey:process.env.N8N_API_KEY||""});
const ledger=createLedger({filePath:process.env.PORTAL_LEDGER_PATH||"/data/portal-ledger.ndjson"});
const runnerBridge=createRunnerBridge({token:process.env.FACTORY_RUNNER_DISPATCH_TOKEN||""});
const RUNNER_PROJECTS={
 avisaqui:{repository:"mmcromero/pager-virtual"},
 artesao_digital:{repository:"mmcromero/fabricacao_e_orcamentos"}
};
const haBridgeUrl=process.env.HA_BRIDGE_URL||"";
const n8nInternalPeer=process.env.N8N_INTERNAL_PEER||"";
let haCache=null;
const HA_CACHE_MS=30_000;
const timelineCollectionCache=new Map();
const TIMELINE_CACHE_MS=10*60_000;

if(production&&!ingressMode&&(!process.env.GITHUB_TOKEN||!process.env.PORTAL_BASIC_USER||!process.env.PORTAL_BASIC_PASSWORD))
 throw new Error("Produção standalone exige GITHUB_TOKEN, PORTAL_BASIC_USER e PORTAL_BASIC_PASSWORD.");
if(production&&!ingressMode&&process.env.PORTAL_BASIC_PASSWORD.length<16)
 throw new Error("PORTAL_BASIC_PASSWORD deve ter pelo menos 16 caracteres.");

function equal(a,b){
 const x=Buffer.from(a),y=Buffer.from(b);
 return x.length===y.length&&timingSafeEqual(x,y);
}
function authorized(req){
 if(!production||ingressMode)return true;
 const header=req.headers.authorization||"";
 if(!header.startsWith("Basic "))return false;
 try{
  const decoded=Buffer.from(header.slice(6),"base64").toString("utf8"),i=decoded.indexOf(":");
  return i>=0&&equal(decoded.slice(0,i),process.env.PORTAL_BASIC_USER)&&equal(decoded.slice(i+1),process.env.PORTAL_BASIC_PASSWORD);
 }catch{return false;}
}
function sameOrigin(req){
 const origin=req.headers.origin,host=req.headers.host;
 if(typeof origin!=="string"||typeof host!=="string")return false;
 try{return new URL(origin).host===host;}catch{return false;}
}
async function readJson(req,maxBytes=12_000){
 const chunks=[];let size=0;
 for await(const chunk of req){size+=chunk.length;if(size>maxBytes)throw Object.assign(new Error("Corpo da solicitação excede o limite permitido."),{status:413,code:"REQUEST_TOO_LARGE"});chunks.push(chunk);}
 try{return JSON.parse(Buffer.concat(chunks).toString("utf8"));}catch{throw Object.assign(new Error("JSON inválido."),{status:400,code:"INVALID_JSON"});}
}

function runnerMissionStatus(status){
 return ({RECEBIDA:"dispatched",PLANEJADA:"planning",EXECUTANDO:"planning",VALIDANDO:"planning",CONCLUIDA:"planned",PARCIAL:"partial",IMPEDIDA:"blocked",CANCELADA:"cancelled"})[status]||"planning";
}
function safeRunnerCode(error){
 const code=error?.code;
 return typeof code==="string"&&/^[a-z][a-z0-9_]{0,63}$/.test(code)?code:"runner_dispatch_failed";
}

function runnerPlanSummary(job){
 const result=job?.result;
 if(result===null||result===undefined)return {};
 if(!result||typeof result!=="object"||Array.isArray(result)||result.tests_execution_performed!==false||result.authorization_verified!==false)throw Object.assign(new Error("Resultado do Runner não comprovou modo read-only."),{code:"runner_result_not_read_only"});
 const planStatus=result.plan_status,selectedCount=result.selected_count,reusedCount=result.reused_count,omittedCount=result.omitted_count,planDigest=result.plan_digest,receiptDigest=result.receipt_digest;
 if(!["PLANNED","PARTIAL","BLOCKED_SCOPE"].includes(planStatus)||![selectedCount,reusedCount,omittedCount].every(Number.isSafeInteger)||[selectedCount,reusedCount,omittedCount].some(n=>n<0)||! /^[0-9a-f]{64}$/.test(planDigest||"")||! /^[0-9a-f]{64}$/.test(receiptDigest||""))throw Object.assign(new Error("Resumo do plano do Runner inválido."),{code:"runner_plan_summary_invalid"});
 return {planStatus,selectedCount,reusedCount,omittedCount,planDigest,receiptDigest,testsExecutionPerformed:false,authorizationVerified:false,nextRunnerAction:typeof result.next_action==="string"?result.next_action:null};
}
async function dispatchMission(mission){
 try{
  const result=await runnerBridge.submitMission({missionId:mission.id,projectId:mission.projectId,prompt:mission.prompt,createdAt:mission.createdAt});
  const job=result?.job,executionId=job?.execution_id,runnerStatus=job?.status;
  if(typeof executionId!=="string"||typeof runnerStatus!=="string")throw Object.assign(new Error("Resposta inválida do Runner."),{code:"runner_invalid_response"});
  const missionStatus=runnerMissionStatus(runnerStatus);
  const planSummary=runnerPlanSummary(job);
  await ledger.appendMissionStatus({missionId:mission.id,missionStatus,executionId,runnerStatus,...planSummary});
  return {...mission,missionStatus,executionId,runnerStatus,dispatchError:null,...planSummary};
 }catch(error){
  const code=safeRunnerCode(error);
  await ledger.appendMissionStatus({missionId:mission.id,missionStatus:"dispatch_blocked",dispatchError:code});
  return {...mission,missionStatus:"dispatch_blocked",executionId:null,runnerStatus:null,dispatchError:code};
 }
}
async function refreshMissionStatuses(missions){
 await Promise.all(missions.slice(0,5).map(async mission=>{
  if(mission.executionId){
   try{
    const result=await runnerBridge.getJob(mission.executionId),job=result?.job;
    if(!job||typeof job.status!=="string")return;
    const missionStatus=runnerMissionStatus(job.status);
    const planSummary=runnerPlanSummary(job);
    const summaryChanged=Object.entries(planSummary).some(([key,value])=>mission[key]!==value);
    if(missionStatus!==mission.missionStatus||job.status!==mission.runnerStatus||summaryChanged){
     await ledger.appendMissionStatus({missionId:mission.id,missionStatus,executionId:mission.executionId,runnerStatus:job.status,...planSummary});
    }
   }catch{}
  }else if(runnerBridge.configured&&["received","dispatch_blocked"].includes(mission.missionStatus)){
   await dispatchMission(mission);
  }
 }));
}
function securityHeaders(extra={}){
 return {
  "X-Content-Type-Options":"nosniff",
  "Referrer-Policy":"no-referrer",
  "Content-Security-Policy":"default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; object-src 'none'; base-uri 'self'; frame-ancestors 'self'",
  ...extra
 };
}
function json(res,status,body,headers={}){
 res.writeHead(status,securityHeaders({"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store",...headers}));
 res.end(JSON.stringify(body));
}
function text(res,status,body,headers={}){
 res.writeHead(status,securityHeaders({"Content-Type":"text/plain; charset=utf-8","Cache-Control":"no-store",...headers}));
 res.end(body);
}
async function getHomeAssistantApps(force=false){
 if(!haBridgeUrl)throw Object.assign(new Error("Integração Home Assistant não configurada."),{status:503,code:"SUPERVISOR_NOT_CONFIGURED"});
 if(!force&&haCache&&Date.now()-haCache.cachedAt<HA_CACHE_MS)return {...haCache.data,cache:"HIT"};
 let response;
 try{response=await fetch(new URL("/v1/inventory",haBridgeUrl),{headers:{Accept:"application/json"},signal:AbortSignal.timeout(12000)});}
 catch{throw Object.assign(new Error("Não foi possível consultar o bridge local do Supervisor."),{status:503,code:"SUPERVISOR_BRIDGE_UNAVAILABLE"});}
 const payload=await response.json().catch(()=>({}));
 if(!response.ok)throw Object.assign(new Error(payload.error?.code==="SUPERVISOR_TOKEN_UNAVAILABLE"?"Token de leitura do Supervisor indisponível.":"Supervisor indisponível para consulta."),{status:503,code:payload.error?.code||"SUPERVISOR_UNAVAILABLE"});
 const apps=(payload.apps||[]).map(app=>{
  const mapping=haMappings.get(app.slug);
  return {...app,projectId:mapping?.projectId||null,projectName:mapping?.projectName||null};
 });
 const data={source:payload.source||"Home Assistant Supervisor",checkedAt:payload.checkedAt||new Date().toISOString(),total:apps.length,updatesAvailable:apps.filter(app=>app.updateAvailable===true).length,apps,cache:"MISS"};
 haCache={cachedAt:Date.now(),data};
 return data;
}
async function serveStatic(res,pathname){
 let requested;
 try{requested=decodeURIComponent(pathname);}catch{text(res,400,"Bad request");return;}
 if(requested==="/")requested="/index.html";
 const target=path.resolve(DIST,"."+requested);
 if(!target.startsWith(DIST+path.sep)&&target!==path.join(DIST,"index.html")){text(res,400,"Bad request");return;}
 let file=target;
 try{if(!(await stat(file)).isFile())throw new Error("not a file");}
 catch{
  if(path.extname(requested)){text(res,404,"Not found");return;}
  file=path.join(DIST,"index.html");
 }
 try{
  const body=await readFile(file),ext=path.extname(file);
  const types={".html":"text/html; charset=utf-8",".js":"text/javascript; charset=utf-8",".css":"text/css; charset=utf-8",".svg":"image/svg+xml",".json":"application/json; charset=utf-8",".png":"image/png",".ico":"image/x-icon",".webp":"image/webp",".jpg":"image/jpeg",".jpeg":"image/jpeg",".gif":"image/gif",".woff2":"font/woff2",".woff":"font/woff",".ttf":"font/ttf"};
  const immutable=ext!==".html";
  res.writeHead(200,securityHeaders({"Content-Type":types[ext]||"application/octet-stream","Cache-Control":immutable?"public, max-age=31536000, immutable":"no-store"}));
  res.end(body);
 }catch{text(res,503,"Portal ainda não compilado. Execute npm run build.");}
}
const server=http.createServer(async(req,res)=>{
 let requestUrl;
 try{requestUrl=new URL(req.url||"/","http://localhost");}
 catch{text(res,400,"Bad request");return;}
 const rawPath=requestUrl.pathname,peer=req.socket.remoteAddress||"";
 if(rawPath==="/healthz"&&isLoopbackPeer(peer)){text(res,200,"ok");return;}
 const internalAgentEventRequest=rawPath==="/internal/agent-events"&&req.method==="POST"&&ingressMode&&isN8nPeer(peer,n8nInternalPeer);
 const internalAgentCommentsRequest=rawPath==="/internal/agent-comments"&&req.method==="GET"&&ingressMode&&isN8nPeer(peer,n8nInternalPeer);
 const internalAgentRequest=internalAgentEventRequest||internalAgentCommentsRequest;
 if(rawPath==="/internal/agent-events"||rawPath==="/internal/agent-comments"){
  const allowedMethod=rawPath==="/internal/agent-events"?"POST":"GET";
  if(req.method!==allowedMethod){json(res,405,{error:{code:"METHOD_NOT_ALLOWED",message:"Método não permitido."}},{Allow:allowedMethod});return;}
  if(!internalAgentRequest){json(res,403,{error:{code:"INTERNAL_PEER_NOT_ALLOWED",message:"Origem interna não autorizada."}});return;}
 }
 let pathname=internalAgentEventRequest?"/api/v1/agent-events":internalAgentCommentsRequest?"/api/v1/internal-agent-comments":rawPath;
 if(internalAgentRequest){
  // Dedicated internal routes: only the exact configured n8n container peer is trusted.
 }else if(ingressMode){
  if(!isIngressPeer(peer)){text(res,403,"Ingress access only");return;}
  const basePath=getIngressBasePath(req.headers["x-ingress-path"]);
  if(!basePath){text(res,403,"Valid Home Assistant Ingress session required");return;}
  pathname=stripIngressPath(rawPath,basePath);
  if(pathname===null){text(res,404,"Not found");return;}
  if(rawPath===basePath){res.writeHead(308,securityHeaders({Location:basePath+"/","Cache-Control":"no-store"}));res.end();return;}
  if(req.method!=="GET"&&req.method!=="HEAD"&&!(req.method==="POST"&&(rawPath.endsWith("/api/v1/projects/register")||rawPath.endsWith("/api/v1/projects/quick-register")||rawPath.endsWith("/api/v1/projects/unregister")||rawPath.endsWith("/api/v1/records")||rawPath.endsWith("/api/v1/agent-events")||rawPath.endsWith("/api/v1/missions")||rawPath.endsWith("/api/v1/timeline/collect")||rawPath.endsWith("/api/v1/timeline/end")||rawPath.endsWith("/api/v1/timeline/cancel")))){text(res,405,"Method not allowed",{Allow:"GET, HEAD, POST"});return;}
 }else if(!authorized(req)){
  text(res,401,"Autenticação necessária",{"WWW-Authenticate":'Basic realm="Portal de Governança", charset="UTF-8"'});
  return;
 }
 if(pathname.startsWith("/api/")&&req.method!=="GET"&&!((pathname==="/api/v1/projects/register"||pathname==="/api/v1/projects/quick-register"||pathname==="/api/v1/projects/unregister"||pathname==="/api/v1/records"||pathname==="/api/v1/agent-events"||pathname==="/api/v1/missions"||pathname==="/api/v1/timeline/collect"||pathname==="/api/v1/timeline/end"||pathname==="/api/v1/timeline/cancel")&&req.method==="POST")){
  json(res,405,{error:{code:"METHOD_NOT_ALLOWED",message:"Método não permitido para este endpoint."}},{Allow:pathname==="/api/v1/projects/register"||pathname==="/api/v1/projects/quick-register"||pathname==="/api/v1/projects/unregister"||pathname==="/api/v1/records"||pathname==="/api/v1/agent-events"||pathname==="/api/v1/missions"||pathname==="/api/v1/timeline/collect"||pathname==="/api/v1/timeline/end"||pathname==="/api/v1/timeline/cancel"?"GET, POST":"GET"});return;
 }
 if(pathname==="/api/v1/projects/register"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem da solicitação não autorizada."}});return;}
  try{const result=await github.registerProject(await readJson(req));json(res,201,result);}
  catch(error){json(res,error.status||502,{error:{code:error.code||"PROJECT_REGISTRATION_FAILED",message:error.message}});}
  return;
 }

 if(pathname==="/api/v1/projects/quick-register"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem da solicitação não autorizada."}});return;}
  try{const result=await github.quickRegisterProject(await readJson(req));json(res,201,result);}
  catch(error){json(res,error.status||502,{error:{code:error.code||"PROJECT_QUICK_REGISTRATION_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/projects/unregister"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem da solicitação não autorizada."}});return;}
  try{const result=await github.unregisterProject(await readJson(req));json(res,200,result);}
  catch(error){json(res,error.status||502,{error:{code:error.code||"PROJECT_UNREGISTRATION_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/timeline"&&req.method==="GET"){
  try{const projectId=requestUrl.searchParams.get("project")||"";if(typeof projectId!=="string"||!projectId.trim()||projectId.length>120||/[\\u0000-\\u001f]/.test(projectId)){json(res,400,{error:{code:"INVALID_PROJECT_ID",message:"Informe um ID de projeto válido."}});return;}json(res,200,{...await ledger.listTimelineEvents({projectId,limit:2000}),serverNow:new Date().toISOString(),timeZone:"America/Sao_Paulo"});}
  catch(error){json(res,error.status||503,{error:{code:error.code||"TIMELINE_UNAVAILABLE",message:error.message}});}return;
 }
 if(pathname==="/api/v1/timeline/collect"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;}
  try{
   const projectId=requestUrl.searchParams.get("project")||"";
   const force=requestUrl.searchParams.get("force")==="1";
   const cached=timelineCollectionCache.get(projectId);
   if(!force&&cached&&Date.now()-cached.cachedAt<TIMELINE_CACHE_MS){json(res,200,{...await ledger.listTimelineEvents({projectId,limit:2000}),serverNow:new Date().toISOString(),timeZone:"America/Sao_Paulo",collection:cached.collection});return;}
   const portfolio=await github.getPortfolio(registry.projects||[],{force:false});
   const project=portfolio.projects.find(p=>p.id===projectId);
   if(!project){json(res,404,{error:{code:"PROJECT_NOT_FOUND",message:"Projeto não encontrado no portfólio atual."}});return;}
   const existingTimeline=await ledger.listTimelineEvents({projectId,limit:2000}),sinceByRepo={};
   for(const event of existingTimeline.events){if(event.category==="collection_cursor"&&event.repository&&(!sinceByRepo[event.repository]||Date.parse(event.occurredAt)>Date.parse(sinceByRepo[event.repository])))sinceByRepo[event.repository]=event.occurredAt;}
   const collected=await github.getProjectHistory([project],{sinceByRepo});
   let added=0;
   for(const event of collected.events){
    if(!await ledger.hasEvent(event.eventId))added++;
    await ledger.append({type:"timeline_event",eventId:event.eventId,occurredAt:event.occurredAt,confidence:event.confidence,category:event.category,sourceName:event.sourceName,title:event.title,summary:event.summary,projectId:event.projectId,repository:event.repository,sha:event.sha||"",origin:"GitHubHistoryCollector",sourceUrl:event.sourceUrl||"",activeDays:event.activeDays});
   }
   const result=await ledger.listTimelineEvents({projectId,limit:2000});
   const collection={checkedAt:collected.checkedAt,discovered:collected.events.length,added,projectCount:collected.projectCount};
   timelineCollectionCache.set(projectId,{cachedAt:Date.now(),collection});
   json(res,200,{...result,serverNow:new Date().toISOString(),timeZone:"America/Sao_Paulo",collection});
  }catch(error){json(res,error.status||502,{error:{code:error.code||"TIMELINE_COLLECTION_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/timeline/end"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;}
  try{
   const body=await readJson(req,2000),projectId=typeof body?.projectId==="string"?body.projectId:"";
   if(typeof projectId!=="string"||!projectId.trim()||projectId.length>120||/[\u0000-\u001f]/.test(projectId)){json(res,400,{error:{code:"INVALID_PROJECT_ID",message:"Informe um ID de projeto válido."}});return;}
   const portfolio=await github.getPortfolio(registry.projects||[],{force:false}),project=portfolio.projects.find(p=>p.id===projectId);
   if(!project){json(res,404,{error:{code:"PROJECT_NOT_FOUND",message:"Projeto não encontrado no portfólio atual."}});return;}
   const eventId="owner:project_end:"+projectId;
   if(await ledger.hasEvent(eventId)||await ledger.hasEvent("owner:project_cancelled:"+projectId)){json(res,409,{error:{code:"PROJECT_ALREADY_TERMINAL",message:"Este projeto já possui encerramento ou cancelamento registrado."}});return;}
   await ledger.append({type:"timeline_event",eventId,occurredAt:new Date().toISOString(),confidence:"confirmed",category:"project_end",sourceName:"Decisão registrada no Portal",title:"Projeto encerrado",summary:"Encerramento declarado pelo proprietário no Portal de Governança.",projectId,origin:"OwnerTimelineAction"});
   timelineCollectionCache.delete(projectId);
   json(res,201,{...await ledger.listTimelineEvents({projectId,limit:2000}),serverNow:new Date().toISOString(),timeZone:"America/Sao_Paulo"});
  }catch(error){json(res,error.status||503,{error:{code:error.code||"TIMELINE_END_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/timeline/cancel"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;}
  try{
   const body=await readJson(req,2000),projectId=typeof body?.projectId==="string"?body.projectId:"";
   if(!projectId.trim()||projectId.length>120||/[\\u0000-\\u001f]/.test(projectId)){json(res,400,{error:{code:"INVALID_PROJECT_ID",message:"Informe um ID de projeto válido."}});return;}
   const portfolio=await github.getPortfolio(registry.projects||[],{force:false}),project=portfolio.projects.find(p=>p.id===projectId);
   if(!project){json(res,404,{error:{code:"PROJECT_NOT_FOUND",message:"Projeto não encontrado no portfólio atual."}});return;}
   if(await ledger.hasEvent("owner:project_end:"+projectId)||await ledger.hasEvent("owner:project_cancelled:"+projectId)){json(res,409,{error:{code:"PROJECT_ALREADY_TERMINAL",message:"Este projeto já possui encerramento ou cancelamento registrado."}});return;}
   const eventId="owner:project_cancelled:"+projectId;
   await ledger.append({type:"timeline_event",eventId,occurredAt:new Date().toISOString(),confidence:"confirmed",category:"project_cancelled",sourceName:"Decisão registrada no Portal",title:"Projeto cancelado",summary:"Cancelamento declarado explicitamente pelo proprietário no Portal de Governança.",projectId,origin:"OwnerTimelineAction"});
   timelineCollectionCache.delete(projectId);
   json(res,201,{...await ledger.listTimelineEvents({projectId,limit:2000}),serverNow:new Date().toISOString(),timeZone:"America/Sao_Paulo"});
  }catch(error){json(res,error.status||503,{error:{code:error.code||"TIMELINE_CANCEL_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/records"&&req.method==="GET"){
  const projectId=requestUrl.searchParams.get("project");
  if(projectId&&!/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(projectId)){json(res,400,{error:{code:"INVALID_PROJECT_FILTER",message:"Filtro de projeto inválido."}});return;}
  try{json(res,200,await ledger.list({projectId}));}catch(error){json(res,error.status||503,{error:{code:error.code||"LEDGER_UNAVAILABLE",message:error.message}});}return;
 }
 if(pathname==="/api/v1/missions"&&req.method==="GET"){
  const projectId=requestUrl.searchParams.get("project");
  if(projectId&&!/^[a-z0-9]+(?:[-_][a-z0-9]+)*$/.test(projectId)){json(res,400,{error:{code:"INVALID_PROJECT_FILTER",message:"Filtro de projeto inválido."}});return;}
  try{
   const current=await ledger.listMissions({projectId,limit:100});
   await refreshMissionStatuses(current.missions);
   json(res,200,await ledger.listMissions({projectId,limit:100}));
  }catch(error){json(res,error.status||503,{error:{code:error.code||"MISSIONS_UNAVAILABLE",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/missions"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;}
  let body;
  try{body=await readJson(req,40_000);}catch(error){json(res,error.status||400,{error:{code:error.code||"INVALID_JSON",message:error.message}});return;}
  if(!body||typeof body!=="object"||Array.isArray(body)||typeof body.prompt!=="string"||typeof body.projectId!=="string"||!RUNNER_PROJECTS[body.projectId]){
   json(res,400,{error:{code:"INVALID_MISSION_PAYLOAD",message:"Informe o prompt completo e selecione um projeto compatível com o planejamento read-only."}});return;
  }
  const project=RUNNER_PROJECTS[body.projectId];
  if(body.repository&&body.repository!==project.repository){
   json(res,400,{error:{code:"PROJECT_REPOSITORY_MISMATCH",message:"O repositório não corresponde ao perfil aprovado do Runner."}});return;
  }
  try{
   const row=await ledger.append({
    type:"mission",
    title:"Missão recebida",
    summary:"Prompt integral preservado no Portal. O Runner recebe somente o primeiro trecho limitado a 900 caracteres e o digest SHA-256 para planejamento read-only.",
    prompt:body.prompt,
    projectId:body.projectId,
    repository:project.repository,
    origin:"PortalMissionIntake"
   });
   const mission=await dispatchMission(row);
   const dispatch=mission.executionId?{status:"dispatched",executionId:mission.executionId,runnerStatus:mission.runnerStatus}:{status:"blocked",code:mission.dispatchError};
   json(res,202,{mission,dispatch});
  }catch(error){json(res,error.status||503,{error:{code:error.code||"MISSION_DISPATCH_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/records"&&req.method==="POST"){
  if(!sameOrigin(req)){json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;}
  try{const row=await ledger.append(await readJson(req));json(res,201,{record:row});}
  catch(error){json(res,error.status||503,{error:{code:error.code||"LEDGER_WRITE_FAILED",message:error.message}});}return;
 }
 if(pathname==="/api/v1/internal-agent-comments"&&req.method==="GET"){
  const since=requestUrl.searchParams.get("since")||undefined;
  try{
   const result=await github.getRecentAgentComments({since});
   const filtered=await filterUnrecordedAgentEvents(result.events,ledger);
   json(res,200,{...result,events:filtered.events,eventCount:filtered.events.length,alreadyRecorded:filtered.alreadyRecorded});
  }catch(error){json(res,error.status||502,{error:{code:error.code||"GITHUB_AGENT_COMMENTS_FAILED",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/agent-events"&&req.method==="GET"){
  const projectId=requestUrl.searchParams.get("project")||undefined;
  const agentId=requestUrl.searchParams.get("agent")||undefined;
  const limit=Math.min(Math.max(1,Number(requestUrl.searchParams.get("limit")||50)),500);
  try{json(res,200,await ledger.listEvents({projectId,agentId,limit}));}
  catch(error){json(res,error.status||503,{error:{code:error.code||"AGENT_EVENTS_UNAVAILABLE",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/agent-events"&&req.method==="POST"){
  if(!internalAgentEventRequest&&!sameOrigin(req)&&!isLoopbackPeer(peer)&&!(ingressMode&&isIngressPeer(peer))){
   json(res,403,{error:{code:"ORIGIN_NOT_ALLOWED",message:"Origem não autorizada."}});return;
  }
  let body;
  try{body=await readJson(req);}catch(error){json(res,error.status||400,{error:{code:error.code||"INVALID_JSON",message:error.message}});return;}
  if(!body||typeof body!=="object"||Array.isArray(body)){
   json(res,400,{error:{code:"INVALID_PAYLOAD",message:"Payload inválido."}});return;
  }
  if(body.protocol_version!=="1.0"){
   json(res,400,{error:{code:"INVALID_PROTOCOL_VERSION",message:"protocol_version deve ser '1.0'."}});return;
  }
  const eventId=typeof body.event_id==="string"?body.event_id.trim():"";
  if(!eventId||!/^[a-f0-9\-]{8,64}$/i.test(eventId)){
   json(res,400,{error:{code:"INVALID_EVENT_ID",message:"event_id deve ser um identificador válido (UUID)."}});return;
  }
  const validTypes=new Set(["inicio","atualizacao","conclusao","impedimento","bastao"]);
  const eventType=typeof body.event_type==="string"?body.event_type.trim():"";
  if(!validTypes.has(eventType)){
   json(res,400,{error:{code:"INVALID_EVENT_TYPE",message:"event_type deve ser: inicio, atualizacao, conclusao, impedimento ou bastao."}});return;
  }
  const projectId=typeof body.project_id==="string"?body.project_id.trim():"";
  const agentId=typeof body.agent_id==="string"?body.agent_id.trim():"";
  const taskId=typeof body.task_id==="string"?body.task_id.trim():"";
  const summary=typeof body.summary==="string"?body.summary.trim():"";
  if(!projectId||!agentId||!taskId||!summary){
   json(res,400,{error:{code:"REQUIRED_FIELDS",message:"project_id, agent_id, task_id e summary são obrigatórios."}});return;
  }
  if(await ledger.hasEvent(eventId)){
   json(res,409,{error:{code:"DUPLICATE_EVENT",message:"Evento com event_id já registrado anteriormente."}});return;
  }
  try{
   const title="["+eventType.toUpperCase()+"] "+projectId+" · "+taskId;
   const deliverables=Array.isArray(body.deliverables)?body.deliverables.map(x=>String(x).slice(0,200)):[];
   const nextAction=typeof body.next_action==="string"?body.next_action.trim():"";
   const row=await ledger.append({
    type:"agent_event",
    title,
    summary,
    projectId,
    eventId,
    eventType,
    agentId,
    taskId,
    deliverables,
    nextAction,
    responsible:agentId,
    origin:"AgentProtocol"
   });
   json(res,201,{success:true,event:row});
  }catch(error){
   json(res,error.status||503,{error:{code:error.code||"AGENT_EVENT_SAVE_FAILED",message:error.message}});
  }
  return;
 }
 if(pathname==="/api/v1/system-status"&&req.method==="GET"){
  try{
   const agentStats=await ledger.listEvents({limit:1});
   json(res,200,{
    checkedAt:new Date().toISOString(),
    github:{configured:Boolean(process.env.GITHUB_TOKEN),registrationConfigured:Boolean(process.env.GITHUB_WRITE_TOKEN),status:process.env.GITHUB_TOKEN?"connected":"not_configured"},
    homeAssistant:{bridgeConfigured:Boolean(haBridgeUrl),status:haBridgeUrl?"connected":"not_configured"},
    n8n:{configured:n8n.configured,status:n8n.configured?"connected":"not_configured"},
    agentProtocol:{status:"active",totalEvents:agentStats.total,lastEventAt:agentStats.lastUpdated}
   });
  }catch(error){
   json(res,500,{error:{code:"SYSTEM_STATUS_FAILED",message:error.message}});
  }
  return;
 }
 if(pathname==="/api/v1/repositories"&&req.method==="GET"){
  try{json(res,200,await github.getRepositoryCatalog());}
  catch(error){json(res,error.status||502,{error:{code:error.code||"REPOSITORY_CATALOG_UNAVAILABLE",message:error.message}});}
  return;
 }
 if(pathname==="/api/v1/home-assistant/apps"&&req.method==="GET"){
  try{json(res,200,await getHomeAssistantApps(requestUrl.searchParams.get("refresh")==="1"));}
  catch(error){json(res,error.status||503,{error:{code:error.code||"SUPERVISOR_UNAVAILABLE",message:error.message},source:"Home Assistant Supervisor",checkedAt:new Date().toISOString()});}
  return;
 }
 if(pathname==="/api/v1/n8n/overview"&&req.method==="GET"){
  if(!n8n.configured){json(res,200,{status:"not_configured",source:"n8n Public API",checkedAt:new Date().toISOString(),workflows:[],executions:[]});return;}
  try{json(res,200,{status:"ok",...await n8n.getOverview(requestUrl.searchParams.get("refresh")==="1")});}
  catch(error){json(res,error.status||503,{status:"unavailable",error:{code:error.code||"N8N_UNAVAILABLE",message:error.message},source:"n8n Public API",checkedAt:new Date().toISOString()});}
  return;
 }
 if(pathname==="/api/health"){
  json(res,200,{status:"ok",checkedAt:new Date().toISOString(),github:{configured:Boolean(process.env.GITHUB_TOKEN),access:"read-only",registrationConfigured:Boolean(process.env.GITHUB_WRITE_TOKEN)},homeAssistant:{bridgeConfigured:Boolean(haBridgeUrl),access:"read-only-default-role"},mode:ingressMode?"home-assistant-ingress":production?"production":"development"});return;
 }
 if(pathname==="/api/v1/portfolio"){
  try{json(res,200,await github.getPortfolio(registry.projects,{force:requestUrl.searchParams.get("refresh")==="1"}));}
  catch(error){json(res,error.status||502,{error:{code:error.code||"PORTFOLIO_UNAVAILABLE",message:error.message},source:"GitHub REST API",checkedAt:new Date().toISOString()});}
  return;
 }
 if(pathname.startsWith("/api/")){json(res,404,{error:{code:"NOT_FOUND",message:"Endpoint não encontrado."}});return;}
 if(req.method!=="GET"&&req.method!=="HEAD"){text(res,405,"Method not allowed",{Allow:"GET, HEAD"});return;}
 await serveStatic(res,pathname);
});
server.listen(PORT,HOST,()=>process.stdout.write("Portal ouvindo em "+HOST+":"+PORT+" ("+(ingressMode?"Home Assistant Ingress":production?"produção":"desenvolvimento")+")\n"));
