import http from "node:http";
import {normalizeSupervisorInventory} from "./supervisor-data.mjs";
const TOKEN=process.env.SUPERVISOR_TOKEN||"";
const HOST="127.0.0.1",PORT=8098;
const UPSTREAM="http://supervisor/v2/apps/status";
function loopback(address){
 let value=String(address||"").toLowerCase().split("%")[0];
 if(value.startsWith("::ffff:"))value=value.slice(7);
 return value==="127.0.0.1"||value==="::1";
}
function respond(res,status,body){
 res.writeHead(status,{"Content-Type":"application/json; charset=utf-8","Cache-Control":"no-store","X-Content-Type-Options":"nosniff"});
 res.end(JSON.stringify(body));
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
  const upstream=await fetch(UPSTREAM,{method:"GET",headers:{Authorization:"Bearer "+TOKEN,Accept:"application/json"},signal:AbortSignal.timeout(10000)});
  if(!upstream.ok){process.stderr.write("[supervisor-bridge] Supervisor HTTP "+upstream.status+"\n");respond(res,502,{error:{code:"SUPERVISOR_READ_FAILED"}});return;}
  const payload=await upstream.json();
  const apps=normalizeSupervisorInventory(payload);
  respond(res,200,{source:"Home Assistant Supervisor API v2 /apps/status",checkedAt:new Date().toISOString(),apps});
 }catch(error){
  process.stderr.write("[supervisor-bridge] Leitura indisponível: "+(error?.name||"Error")+"\n");
  respond(res,502,{error:{code:"SUPERVISOR_UNAVAILABLE"}});
 }
});
server.listen(PORT,HOST,()=>process.stdout.write("Supervisor read bridge ouvindo somente em loopback\n"));
