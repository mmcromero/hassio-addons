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
