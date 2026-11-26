import {describe,expect,it,vi} from "vitest";
import {createGitHubClient} from "../server/github.mjs";
const response=(data,status=200,link="")=>({ok:status>=200&&status<300,status,json:async()=>data,headers:{get:name=>name.toLowerCase()==="link"?link:null}});
describe("GitHub auto-discovery read-only client",()=>{
 it("não consulta sem token",async()=>{const fetchImpl=vi.fn();const client=createGitHubClient({token:"",fetchImpl});await expect(client.getPortfolio()).rejects.toMatchObject({code:"GITHUB_NOT_CONFIGURED",status:503});expect(fetchImpl).not.toHaveBeenCalled();});
 it("inclui somente repositórios com marcador e agrupa por project.id",async()=>{
  const manifests={
   "mmcromero/app-a":{schema_version:1,project:{id:"produto-x",name:"Produto X",domain:"Produto",description:"Projeto de teste"}},
   "mmcromero/app-b":{schema_version:1,project:{id:"produto-x",name:"Produto X",domain:"Produto",description:"Projeto de teste",repositories:[{full_name:"mmcromero/app-b",role:"Distribuição"}]}},
   "mmcromero/off":{schema_version:1,project:{enabled:false,id:"off",name:"Off",domain:"Lab",description:"Desativado"}}
  };
  const fetchImpl=vi.fn(async(input,init)=>{const u=new URL(String(input));expect(init.method).toBe("GET");
   if(u.pathname==="/user/repos")return response(["app-a","app-b","off","sem-marker"].map(n=>({full_name:"mmcromero/"+n,owner:{login:"mmcromero"},default_branch:"main"})).concat([{full_name:"other/repo",owner:{login:"other"},default_branch:"main"}]));
   const m=u.pathname.match(/^\/repos\/(mmcromero\/[^/]+)\/contents\/.portal-governanca\.json$/);
   if(m){const value=manifests[m[1]];return value?response({type:"file",content:Buffer.from(JSON.stringify(value)).toString("base64")}):response({message:"Not Found"},404);}
   const name=u.pathname.match(/^\/repos\/(mmcromero\/[^/]+)$/)?.[1];
   if(name)return response({full_name:name,html_url:"https://github.com/"+name,private:true,default_branch:"main"});
   if(u.pathname.endsWith("/branches"))return response([{name:"main",commit:{sha:"abc"}}]);
   if(u.pathname.endsWith("/issues")||u.pathname.endsWith("/pulls")||u.pathname.endsWith("/releases")||u.pathname.endsWith("/commits"))return response([]);
   if(u.pathname.endsWith("/actions/runs"))return response({workflow_runs:[]});
   return response({message:"Not Found"},404);
  });
  const result=await createGitHubClient({token:"test-token",fetchImpl}).getPortfolio();
  expect(result.projects).toHaveLength(1);expect(result.projects[0].id).toBe("produto-x");
  expect(result.projects[0].repositories.map(r=>r.fullName)).toEqual(["mmcromero/app-a","mmcromero/app-b"]);
  expect(result.projects[0].repositories[1].role).toBe("Distribuição");
  expect(result.discovery.scannedRepositories).toBe(4);
 });
 it("consulta marcadores em paralelo respeitando o limite global de quatro requisições",async()=>{
  let active=0,maxActive=0;
  const repos=Array.from({length:8},(_,i)=>({full_name:"mmcromero/repo-"+i,owner:{login:"mmcromero"},default_branch:"main"}));
  const fetchImpl=vi.fn(async(input)=>{
   const u=new URL(String(input));
   if(u.pathname==="/user/repos")return response(repos);
   if(u.pathname.includes("/contents/.portal-governanca.json")){
    active++;maxActive=Math.max(maxActive,active);
    await new Promise(resolve=>setTimeout(resolve,5));
    active--;return response({message:"Not Found"},404);
   }
   return response({message:"Not Found"},404);
  });
  const result=await createGitHubClient({token:"test-token",fetchImpl}).getPortfolio();
  expect(result.projects).toEqual([]);
  expect(maxActive).toBeGreaterThan(1);
  expect(maxActive).toBeLessThanOrEqual(4);
 });
 it("retorna lista vazia quando nenhum repositório possui marcador",async()=>{
  const fetchImpl=vi.fn(async(input)=>{const u=new URL(String(input));if(u.pathname==="/user/repos")return response([{full_name:"mmcromero/no-marker",owner:{login:"mmcromero"},default_branch:"main"}]);return response({message:"Not Found"},404);});
  const result=await createGitHubClient({token:"test-token",fetchImpl}).getPortfolio();
  expect(result.projects).toEqual([]);expect(result.discovery.projectsFound).toBe(0);
 });
 it("rejeita JSON inválido sem incluir o repositório",async()=>{
  const fetchImpl=vi.fn(async(input)=>{const u=new URL(String(input));if(u.pathname==="/user/repos")return response([{full_name:"mmcromero/bad",owner:{login:"mmcromero"},default_branch:"main"}]);return response({type:"file",content:Buffer.from("{bad").toString("base64")});});
  const result=await createGitHubClient({token:"test-token",fetchImpl}).getPortfolio();
  expect(result.projects).toEqual([]);expect(result.discovery.warnings[0].code).toBe("GITHUB_INVALID_PROJECT_MANIFEST");
 });
 it("reutiliza cache e força nova descoberta quando solicitado",async()=>{
  const fetchImpl=vi.fn(async(input)=>{const u=new URL(String(input));if(u.pathname==="/user/repos")return response([]);return response([]);});
  const client=createGitHubClient({token:"test-token",fetchImpl});await client.getPortfolio();const n=fetchImpl.mock.calls.length;
  await client.getPortfolio();expect(fetchImpl.mock.calls.length).toBe(n);await client.getPortfolio([],{force:true});expect(fetchImpl.mock.calls.length).toBeGreaterThan(n);
 });
});

describe("cadastro controlado de marcadores",()=>{
 it("não permite escrita sem credencial separada",async()=>{
  const client=createGitHubClient({token:"read-token",fetchImpl:vi.fn()});
  await expect(client.registerProject({repositoryFullName:"mmcromero/demo",project:{id:"demo",name:"Demo",domain:"Produto",description:"Projeto demo"}})).rejects.toMatchObject({code:"GITHUB_WRITE_NOT_CONFIGURED",status:503});
 });
 it("cria marcador somente com token de escrita e na branch padrão",async()=>{
  const calls=[];
  const fetchImpl=vi.fn(async(input,init)=>{
   const u=new URL(String(input));calls.push({path:u.pathname,method:init.method,headers:init.headers,body:init.body});
   if(u.pathname==="/user/repos")return response([{full_name:"mmcromero/demo",owner:{login:"mmcromero"},default_branch:"main",archived:false}]);
   if(u.pathname==="/repos/mmcromero/demo/contents/.portal-governanca.json"&&init.method==="GET")return response({message:"Not Found"},404);
   if(u.pathname==="/repos/mmcromero/demo/contents/.portal-governanca.json"&&init.method==="PUT")return response({content:{path:".portal-governanca.json"}});
   return response({message:"Not Found"},404);
  });
  const client=createGitHubClient({token:"read-token",writeToken:"write-token",fetchImpl});
  const result=await client.registerProject({repositoryFullName:"mmcromero/demo",project:{id:"demo",name:"Demo",domain:"Produto",description:"Projeto demo"}});
  const write=calls.find(c=>c.method==="PUT");
  expect(result).toMatchObject({success:true,repository:"mmcromero/demo",branch:"main",marker:".portal-governanca.json"});
  expect(write.headers.Authorization).toBe("Bearer write-token");
  const body=JSON.parse(write.body),manifest=JSON.parse(Buffer.from(body.content,"base64").toString("utf8"));
  expect(body.branch).toBe("main");expect(manifest.project.id).toBe("demo");
  expect(calls.filter(c=>c.method==="GET").every(c=>c.headers.Authorization==="Bearer read-token")).toBe(true);
 });
 it("recusa sobrescrever marcador existente",async()=>{
  const fetchImpl=vi.fn(async(input,init)=>{const u=new URL(String(input));if(u.pathname==="/user/repos")return response([{full_name:"mmcromero/demo",owner:{login:"mmcromero"},default_branch:"main"}]);if(u.pathname.endsWith("/contents/.portal-governanca.json"))return response({type:"file",content:Buffer.from("{}").toString("base64")});return response([],200);});
  const client=createGitHubClient({token:"read-token",writeToken:"write-token",fetchImpl});
  await expect(client.registerProject({repositoryFullName:"mmcromero/demo",project:{id:"demo",name:"Demo",domain:"Produto",description:"Projeto demo"}})).rejects.toMatchObject({code:"GITHUB_MARKER_EXISTS",status:409});
  expect(fetchImpl.mock.calls.some(([,init])=>init.method==="PUT")).toBe(false);
 });
 it("rejeita repositório fora do owner autorizado",async()=>{
  const fetchImpl=vi.fn(async(input)=>{const u=new URL(String(input));if(u.pathname==="/user/repos")return response([]);return response({message:"Not Found"},404);});
  const client=createGitHubClient({token:"read-token",writeToken:"write-token",fetchImpl});
  await expect(client.registerProject({repositoryFullName:"other/demo",project:{id:"demo",name:"Demo",domain:"Produto",description:"Projeto demo"}})).rejects.toMatchObject({code:"GITHUB_INVALID_REGISTRATION",status:400});
 });
});

describe("GitHub issue-comment polling for Agent Protocol",()=>{
 it("retorna somente comentários marcados de Issues autorizadas",async()=>{
  const repo="mmcromero/portal-governanca";
  const marker={schema_version:1,project:{id:"portal-governanca",name:"Portal",domain:"platform",description:"Portal"}};
  const comment={id:77,body:"<!-- AGENT_PROTOCOL_EVENT --> payload",author_association:"OWNER",created_at:"2026-11-26T10:00:00Z",updated_at:"2026-11-26T10:00:00Z",issue_url:"https://api.github.com/repos/"+repo+"/issues/9",html_url:"https://github.com/"+repo+"/issues/9#issuecomment-77",user:{login:"mmcromero"}};
  const fetchImpl=vi.fn(async(input)=>{
   const u=new URL(String(input));
   if(u.pathname==="/user/repos")return response([{full_name:repo,owner:{login:"mmcromero"},default_branch:"main"}]);
   if(u.pathname==="/repos/"+repo+"/contents/.portal-governanca.json")return response({type:"file",content:Buffer.from(JSON.stringify(marker)).toString("base64")});
   if(u.pathname==="/repos/"+repo+"/issues/comments")return response([comment]);
   if(u.pathname==="/repos/"+repo+"/issues/9")return response({number:9,title:"Teste",html_url:"https://github.com/"+repo+"/issues/9"});
   return response({message:"Not Found"},404);
  });
  const result=await createGitHubClient({token:"read-token",fetchImpl,now:()=>new Date("2026-11-26T10:05:00Z")}).getRecentAgentComments({since:"2026-11-26T09:55:00Z"});
  expect(result.eventCount).toBe(1);
  expect(result.events[0].headers["x-github-event"]).toBe("issue_comment");
  expect(result.events[0].body.comment.id).toBe(77);
  expect(result.events[0].body.issue.number).toBe(9);
 });
 it("ignora comentário editado e comentário de Pull Request",async()=>{
  const repo="mmcromero/portal-governanca";
  const marker={schema_version:1,project:{id:"portal-governanca",name:"Portal",domain:"platform",description:"Portal"}};
  const base={body:"<!-- AGENT_PROTOCOL_EVENT --> payload",author_association:"OWNER",created_at:"2026-11-26T10:00:00Z",issue_url:"https://api.github.com/repos/"+repo+"/issues/9",user:{login:"mmcromero"}};
  const fetchImpl=vi.fn(async(input)=>{
   const u=new URL(String(input));
   if(u.pathname==="/user/repos")return response([{full_name:repo,owner:{login:"mmcromero"},default_branch:"main"}]);
   if(u.pathname==="/repos/"+repo+"/contents/.portal-governanca.json")return response({type:"file",content:Buffer.from(JSON.stringify(marker)).toString("base64")});
   if(u.pathname==="/repos/"+repo+"/issues/comments")return response([{...base,id:1,updated_at:"2026-11-26T10:01:00Z"},{...base,id:2,updated_at:"2026-11-26T10:00:00Z",issue_url:"https://api.github.com/repos/"+repo+"/issues/10"}]);
   if(u.pathname==="/repos/"+repo+"/issues/10")return response({number:10,pull_request:{url:"https://api.github.com/repos/"+repo+"/pulls/10"}});
   return response({message:"Not Found"},404);
  });
  const result=await createGitHubClient({token:"read-token",fetchImpl,now:()=>new Date("2026-11-26T10:05:00Z")}).getRecentAgentComments({since:"2026-11-26T09:55:00Z"});
  expect(result.eventCount).toBe(0);
 });
 it("rejeita janela de polling acima de 24 horas",async()=>{
  const fetchImpl=vi.fn();
  const client=createGitHubClient({token:"read-token",fetchImpl,now:()=>new Date("2026-11-26T10:05:00Z")});
  await expect(client.getRecentAgentComments({since:"2026-11-24T00:00:00Z"})).rejects.toMatchObject({code:"GITHUB_INVALID_AGENT_EVENT_WINDOW",status:400});
  expect(fetchImpl).not.toHaveBeenCalled();
 });
});
