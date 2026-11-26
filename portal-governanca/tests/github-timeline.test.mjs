import {describe,it,expect,vi} from "vitest";
import {createGitHubClient} from "../server/github.mjs";

function response(data,link=""){
 return {ok:true,status:200,json:async()=>data,headers:{get:(name)=>name.toLowerCase()==="link"?link:null}};
}
describe("coleta histórica GitHub",()=>{
 it("descobre início, repositório, primeira Issue/PR e primeira release sem tratar criação do repo como início",async()=>{
  const calls=[];
  const fetchImpl=vi.fn(async url=>{
   const u=new URL(url);calls.push(u.pathname+u.search);
   if(u.pathname==="/repos/mmcromero/projeto")return response({created_at:"2024-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto"});
   if(u.pathname.endsWith("/commits"))return response([{sha:"abc1234567890",html_url:"https://github.com/mmcromero/projeto/commit/abc1234567890",commit:{author:{date:"2024-02-01T10:00:00Z"},message:"Initial project"}}]);
   if(u.pathname.endsWith("/issues"))return response([{number:2,title:"Primeira issue",created_at:"2024-01-20T10:00:00Z",html_url:"https://github.com/mmcromero/projeto/issues/2"}]);
   if(u.pathname.endsWith("/pulls"))return response([{number:3,title:"Primeiro PR",created_at:"2024-02-02T10:00:00Z",html_url:"https://github.com/mmcromero/projeto/pull/3"}]);
   if(u.pathname.endsWith("/releases"))return response([{id:7,tag_name:"v1.0.0",name:"Primeira versão",published_at:"2024-03-01T10:00:00Z",html_url:"https://github.com/mmcromero/projeto/releases/tag/v1.0.0"}]);
   throw new Error("Unexpected request "+u);
  });
  const client=createGitHubClient({token:"test",fetchImpl});
  const result=await client.getProjectHistory([{id:"projeto",repositories:[{fullName:"mmcromero/projeto"}]}]);
  expect(result.events.find(e=>e.category==="project_start")).toMatchObject({occurredAt:"2024-02-01T10:00:00Z",confidence:"confirmed"});
  expect(result.events.find(e=>e.category==="repository_created").category).toBe("repository_created");
  expect(result.events.find(e=>e.category==="first_issue")).toMatchObject({occurredAt:"2024-01-20T10:00:00Z",confidence:"confirmed",sourceUrl:"https://github.com/mmcromero/projeto/issues/2"});
  expect(result.events.find(e=>e.category==="first_pull_request")).toBeTruthy();
  expect(result.events.find(e=>e.category==="release")).toBeTruthy();
  expect(result.events.find(e=>e.category==="activity_day")).toMatchObject({activeDays:1,confidence:"confirmed"});
  expect(calls).toHaveLength(5);
 });
 it("usa o cursor persistido para buscar somente commits posteriores",async()=>{
  const requested=[];
  const fetchImpl=vi.fn(async url=>{
   const u=new URL(url);requested.push(u);
   if(u.pathname==="/repos/mmcromero/projeto")return response({created_at:"2024-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto"});
   if(u.pathname.endsWith("/commits")){const delta=u.searchParams.has("since");const sha=delta?"sha222222222":"sha111111111";const date=delta?"2024-02-02T10:00:00Z":"2024-02-01T10:00:00Z";return response([{sha,html_url:"https://github.com/mmcromero/projeto/commit/"+sha,commit:{committer:{date},message:"Change"}}]);}
   if(u.pathname.endsWith("/issues")||u.pathname.endsWith("/pulls")||u.pathname.endsWith("/releases"))return response([]);
   throw new Error("Unexpected request "+u);
  });
  const client=createGitHubClient({token:"test",fetchImpl});
  const project=[{id:"projeto",repositories:[{fullName:"mmcromero/projeto"}]}];
  const initial=await client.getProjectHistory(project);
  expect(initial.events.some(e=>e.category==="project_start")).toBe(true);
  const delta=await client.getProjectHistory(project,{sinceByRepo:{"mmcromero/projeto":"2024-02-01T10:00:00Z"}});
  expect(requested.find(u=>u.pathname.endsWith("/commits")&&u.searchParams.has("since"))?.searchParams.get("since")).toBe("2024-02-01T10:00:00Z");
  expect(delta.events.some(e=>e.category==="project_start")).toBe(false);
  expect(delta.events.some(e=>e.category==="collection_cursor"&&e.eventId.endsWith("sha222222222"))).toBe(true);
  expect(delta.events.some(e=>e.category==="activity_day"&&e.eventId.endsWith("2024-02-02"))).toBe(true);
 });
 it("usa o dia local de São Paulo e mantém início desconhecido quando não há evidência",async()=>{
  const fetchImpl=vi.fn(async url=>{
   const u=new URL(url),repoName=u.pathname.split("/").slice(2,4).join("/");
   if(u.pathname.endsWith("/commits"))return response(repoName==="mmcromero/projeto-a"?[{sha:"localday123",html_url:"https://github.com/mmcromero/projeto-a/commit/localday123",commit:{committer:{date:"2024-02-01T01:00:00Z"},message:"Initial"}}]:[]);
   if(u.pathname.endsWith("/issues")||u.pathname.endsWith("/pulls")||u.pathname.endsWith("/releases"))return response([]);
   if(u.pathname.startsWith("/repos/"))return response({created_at:"2024-01-01T00:00:00Z",html_url:"https://github.com/"+repoName});
   throw new Error("Unexpected request "+u);
  });
  const client=createGitHubClient({token:"test",fetchImpl});
  const result=await client.getProjectHistory([
   {id:"projeto-a",repositories:[{fullName:"mmcromero/projeto-a"}]},
   {id:"projeto-b",repositories:[{fullName:"mmcromero/projeto-b"}]}
  ]);
  expect(result.events.find(e=>e.category==="activity_day")).toMatchObject({eventId:"github:activity-day:projeto-a:2024-01-31",activeDays:1,sourceUrl:"https://github.com/mmcromero/projeto-a/commit/localday123"});
  expect(result.events.some(e=>e.projectId==="projeto-b"&&e.category==="project_start")).toBe(false);
  expect(result.events.some(e=>e.projectId==="projeto-b"&&e.category==="first_issue")).toBe(false);
 });
 it("localiza a primeira release na última página quando há mais de 100 releases",async()=>{
  const fetchImpl=vi.fn(async url=>{
   const u=new URL(url);
   if(u.pathname==="/repos/mmcromero/projeto")return response({created_at:"2024-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto"});
   if(u.pathname.endsWith("/commits"))return response([]);
   if(u.pathname.endsWith("/issues")||u.pathname.endsWith("/pulls"))return response([]);
   if(u.pathname.endsWith("/releases")&&u.searchParams.get("page")==="2")return response([{id:1,tag_name:"v0.1",name:"Mais antiga",published_at:"2020-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto/releases/tag/v0.1"}]);
   if(u.pathname.endsWith("/releases"))return response([{id:99,tag_name:"v9.9",name:"Mais nova",published_at:"2026-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto/releases/tag/v9.9"}],'<https://api.github.com/repos/mmcromero/projeto/releases?per_page=100&page=2>; rel="next", <https://api.github.com/repos/mmcromero/projeto/releases?per_page=100&page=2>; rel="last"');
   throw new Error("Unexpected request "+u);
  });
  const client=createGitHubClient({token:"test",fetchImpl});
  const result=await client.getProjectHistory([{id:"projeto",repositories:[{fullName:"mmcromero/projeto"}]}]);
  expect(result.events.find(e=>e.category==="release")).toMatchObject({eventId:"github:release:mmcromero/projeto:1",confidence:"confirmed"});
 });
 it("não presume início confirmado quando a paginação de commits não foi totalmente percorrida",async()=>{
  let commitPage=0;
  const fetchImpl=vi.fn(async url=>{
   const u=new URL(url);
   if(u.pathname==="/repos/mmcromero/projeto")return response({created_at:"2024-01-01T00:00:00Z",html_url:"https://github.com/mmcromero/projeto"});
   if(u.pathname.endsWith("/commits")){commitPage++;return response([{sha:"sha"+commitPage,html_url:"https://github.com/mmcromero/projeto/commit/sha"+commitPage,commit:{author:{date:"2024-02-01T10:00:00Z"},message:"Change"}}],commitPage<=11?'<https://api.github.com/repos/mmcromero/projeto/commits?page='+(commitPage+1)+'>; rel="next"':"");}
   if(u.pathname.endsWith("/issues"))return response([{number:4,title:"Issue mais antiga",created_at:"2024-01-10T10:00:00Z",html_url:"https://github.com/mmcromero/projeto/issues/4"}]);
   if(u.pathname.endsWith("/pulls"))return response([]);
   if(u.pathname.endsWith("/releases"))return response([]);
   throw new Error("Unexpected request "+u);
  });
  const client=createGitHubClient({token:"test",fetchImpl});
  const result=await client.getProjectHistory([{id:"projeto",repositories:[{fullName:"mmcromero/projeto"}]}]);
  expect(result.events.find(e=>e.category==="project_start").confidence).toBe("estimated");
  expect(result.events.find(e=>e.category==="first_issue").confidence).toBe("confirmed");
  expect(commitPage).toBe(11);
 });
});
