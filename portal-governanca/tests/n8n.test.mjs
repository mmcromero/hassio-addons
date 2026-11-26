import {describe,expect,it,vi} from "vitest";
import {createN8nClient} from "../server/n8n.mjs";
function response(payload,status=200){return{ok:status>=200&&status<300,status,json:async()=>payload};}
describe("conector n8n somente leitura",()=>{
 it("não consulta sem URL e chave",async()=>{
  const fetchImpl=vi.fn();const client=createN8nClient({fetchImpl});
  expect(client.configured).toBe(false);
  await expect(client.getOverview()).rejects.toMatchObject({code:"N8N_NOT_CONFIGURED"});
  expect(fetchImpl).not.toHaveBeenCalled();
 });
 it("consulta workflows e execuções por GET, sem carregar dados internos",async()=>{
  const fetchImpl=vi.fn(async(url,init)=>{
   expect(init.method).toBe("GET");expect(init.headers["X-N8N-API-KEY"]).toBe("secret-test-key");expect(init.body).toBeUndefined();
   if(url.pathname.endsWith("/workflows"))return response({data:[{id:"w1",name:"Workflow A",active:true,updatedAt:"2026-11-26T10:00:00Z",nodes:[{parameters:{secret:"never-return"}}],tags:[{name:"comercial"}]}]});
   return response({data:[{id:42,workflowId:"w1",status:"error",mode:"trigger",startedAt:"2026-11-26T10:01:00Z",data:{resultData:{secret:"never-return"}}}]});
  });
  const client=createN8nClient({baseUrl:"http://n8n.local:5678",apiKey:"secret-test-key",fetchImpl,now:()=>1_795_680_000_000});
  const result=await client.getOverview();
  expect(result.workflowCount).toBe(1);expect(result.activeCount).toBe(1);expect(result.failedExecutions).toBe(1);
  expect(result.workflows[0]).toMatchObject({id:"w1",name:"Workflow A",active:true,tags:["comercial"]});
  expect(result.executions[0]).toMatchObject({id:"42",workflowId:"w1",workflowName:"Workflow A",status:"error"});
  expect(JSON.stringify(result)).not.toContain("never-return");
  expect(fetchImpl).toHaveBeenCalledTimes(2);
  expect(fetchImpl.mock.calls.every(([,init])=>init.method==="GET")).toBe(true);
 });
 it("usa base path api/v1 informado ou acrescenta api/v1",async()=>{
  const seen=[];const fetchImpl=vi.fn(async(url)=>{seen.push(url.pathname);return response({data:[]});});
  await createN8nClient({baseUrl:"https://n8n.example/api/v1",apiKey:"k",fetchImpl}).getOverview();
  expect(seen).toEqual(["/api/v1/workflows","/api/v1/executions"]);
 });
 it("cacheia a leitura e permite refresh",async()=>{
  const fetchImpl=vi.fn(async()=>response({data:[]}));
  const client=createN8nClient({baseUrl:"https://n8n.example",apiKey:"k",fetchImpl});
  await client.getOverview();await client.getOverview();expect(fetchImpl).toHaveBeenCalledTimes(2);
  await client.getOverview(true);expect(fetchImpl).toHaveBeenCalledTimes(4);
 });
 it("traduz 401 e 403 sem expor payload de erro",async()=>{
  const unauthorized=createN8nClient({baseUrl:"https://n8n.example",apiKey:"k",fetchImpl:async()=>response({message:"secret payload"},401)});
  await expect(unauthorized.getOverview()).rejects.toMatchObject({status:401,code:"N8N_HTTP_401"});
  const forbidden=createN8nClient({baseUrl:"https://n8n.example",apiKey:"k",fetchImpl:async()=>response({message:"secret payload"},403)});
  await expect(forbidden.getOverview()).rejects.toMatchObject({status:403,code:"N8N_HTTP_403"});
 });
 it("rejeita URL com credenciais, query ou protocolo inseguro",()=>{
  expect(()=>createN8nClient({baseUrl:"ftp://n8n.example",apiKey:"k"})).toThrow("URL base");
  expect(()=>createN8nClient({baseUrl:"http://n8n.example",apiKey:"k"})).toThrow("HTTPS");
  expect(()=>createN8nClient({baseUrl:"https://user:pass@n8n.example",apiKey:"k"})).toThrow("URL base");
 });
});
