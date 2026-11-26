import http from "node:http";
import {readFile} from "node:fs/promises";
import {normalizeSupervisorApp} from "./supervisor-data.mjs";
const TOKEN=process.env.SUPERVISOR_TOKEN||"";
const HOST="127.0.0.1",PORT=8098;
const UPSTREAM="http://supervisor";
const CONFIG="/app/config/home-assistant-addons.json";
function loopback(address){
 let value=String(address||"").toLowerCase().split("%")[0];
 if(value.startsWith("::ffff:"))value=value.slice(7);
 return value==="127.0.0.1"||value==="::1";
}
function respond(res,status,body){
 res.writeHead(status,{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"});
 res.end(JSON.stringify(body));
}
async function fetchApp(slug){
 const path="/addons/"+encodeURIComponent(slug)+"/info";
 const response=await fetch(UPSTREAM+path,{method:"GET",headers:{Authorization:"Bearer "+TOKEN,Accept:"application/json"},signal:AbortSignal.timeout(8000)});
 if(response.status===404)return null;
 if(!response.ok)throw new Error("SUPERVISOR_HTTP_"+response.status);
 const payload=await response.json();
 return normalizeSupervisorApp(payload,slug);
}
async function inventory(){
 const config=JSON.parse(await readFile(CONFIG,"utf8"));
 const slugs=[...new Set(config.inventorySlugs||[])].filter(slug=>typeof slug==="string"&&/^[a-z0-9_]+$/.test(slug));
 if(!slugs.length)throw new Error("INVENTORY_SLUGS_EMPTY");
 const apps=[];
 for(let i=0;i<slugs.length;i+=5){
  const batch=await Promise.all(slugs.slice(i,i+5).map(fetchApp));
  apps.push(...batch.filter(Boolean));
 }
 return apps;
}
const server=http.createServer(async(req,res)=>{
 if(!loopback(req.socket.remoteAddress)){respond(res,403,{error:{code:"LOCAL_ONLY"}});return;}
 if(req.method!=="GET"){respond(res,405,{error:{code:"METHOD_NOT_ALLOWED"}});return;}
 let pathname;
 try{pathname=new URL(req.url||"/","http://127.0.0.1").pathname;}catch{respond(res,400,{error:{code:"BAD_REQUEST"}});return;}
 if(pathname==="/healthz"){respond(res,TOKEN?200:503,{status:TOKEN?"ready":"not_configured"});return;}
 if(pathname!=="/v1/inventory"){respond(res,404,{error:{code:"NOT_FOUND"}});return;}
 if(!TOKEN){respond(res,503,{error:{code:"SUPERVISOR_TOKEN_UNAVAILABLE"}});return;}
 try{
  const apps=await inventory();
  respond(res,200,{source:"Home Assistant Supervisor API v1 /addons/{slug}/info (papel default)",checkedAt:new Date().toISOString(),apps});
 }catch(error){
  process.stderr.write("[supervisor-bridge] Leitura indisponível: "+(error?.message||error?.name||"Error")+"\n");
  respond(res,502,{error:{code:"SUPERVISOR_READ_FAILED"}});
 }
});
server.listen(PORT,HOST,()=>process.stdout.write("Supervisor read bridge ouvindo somente em loopback\n"));
