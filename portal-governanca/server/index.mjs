import http from "node:http";
import {readFile,stat} from "node:fs/promises";
import path from "node:path";
import {fileURLToPath} from "node:url";
import {timingSafeEqual} from "node:crypto";
import {createGitHubClient} from "./github.mjs";
import {getIngressBasePath,isIngressPeer,isLoopbackPeer,stripIngressPath} from "./ingress.mjs";

if(process.env.NODE_ENV==="development")await import("dotenv/config");

const ROOT=path.resolve(path.dirname(fileURLToPath(import.meta.url)),"..");
const DIST=path.join(ROOT,"dist");
const ingressMode=process.env.PORTAL_MODE==="ingress";
const production=process.env.NODE_ENV!=="development";
const PORT=Number(process.env.PORT||(ingressMode?8099:production?8080:4174));
const HOST=process.env.PORTAL_HOST||(ingressMode?"0.0.0.0":"127.0.0.1");
const registry=JSON.parse(await readFile(path.join(ROOT,"config/portfolio.json"),"utf8"));
const github=createGitHubClient({token:process.env.GITHUB_TOKEN||""});

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
 const rawPath=requestUrl.pathname;
 const peer=req.socket.remoteAddress||"";

 // Docker health checks are local-only and reveal no configuration or credentials.
 if(rawPath==="/healthz"&&isLoopbackPeer(peer)){text(res,200,"ok");return;}

 let pathname=rawPath;
 if(ingressMode){
  if(!isIngressPeer(peer)){text(res,403,"Ingress access only");return;}
  const basePath=getIngressBasePath(req.headers["x-ingress-path"]);
  if(!basePath){text(res,403,"Valid Home Assistant Ingress session required");return;}
  pathname=stripIngressPath(rawPath,basePath);
  if(pathname===null){text(res,404,"Not found");return;}
  if(rawPath===basePath){res.writeHead(308,securityHeaders({Location:basePath+"/","Cache-Control":"no-store"}));res.end();return;}
  if(req.method!=="GET"&&req.method!=="HEAD"){text(res,405,"Method not allowed",{Allow:"GET, HEAD"});return;}
 }else if(!authorized(req)){
  text(res,401,"Autenticação necessária",{"WWW-Authenticate":'Basic realm="Portal de Governança", charset="UTF-8"'});
  return;
 }

 if(pathname.startsWith("/api/")&&req.method!=="GET"){
  json(res,405,{error:{code:"METHOD_NOT_ALLOWED",message:"Somente GET está disponível nesta fase."}},{Allow:"GET"});return;
 }
 if(pathname==="/api/health"){
  json(res,200,{status:"ok",checkedAt:new Date().toISOString(),github:{configured:Boolean(process.env.GITHUB_TOKEN),access:"read-only"},mode:ingressMode?"home-assistant-ingress":production?"production":"development"});return;
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
