const API_ROOT="https://api.github.com";
const API_VERSION="2022-11-28";
const OWNER="mmcromero";
const MARKER=".portal-governanca.json";
export class GitHubApiError extends Error{
 constructor(message,status=502,code="GITHUB_API_ERROR"){super(message);this.name="GitHubApiError";this.status=status;this.code=code;}
}
export function createGitHubClient({token,writeToken="",fetchImpl=fetch,cacheMs=60_000,now=()=>new Date()}){
 let cached=null,inFlight=0;const waiters=[];
 async function limited(task){if(inFlight>=4)await new Promise(resolve=>waiters.push(resolve));inFlight++;try{return await task();}finally{inFlight--;const next=waiters.shift();if(next)next();}}
 async function request(path){
  return limited(async()=>{const response=await fetchImpl(new URL(path,API_ROOT),{method:"GET",headers:{Accept:"application/vnd.github+json",Authorization:"Bearer "+token,"X-GitHub-Api-Version":API_VERSION,"User-Agent":"mmcromero-portal-governanca"},signal:AbortSignal.timeout(12_000)});
   if(!response.ok){const status=response.status;const message=status===401?"Credencial GitHub inválida ou expirada.":status===403?"GitHub recusou a consulta: verifique permissões somente leitura e limite de requisições.":status===404?"Repositório ou recurso não encontrado ou sem acesso.":"GitHub respondeu HTTP "+status+".";throw new GitHubApiError(message,status===404?404:status===403?403:status===401?401:502,"GITHUB_HTTP_"+status);}
   return {data:await response.json(),link:response.headers?.get?.("link")||""};
  });
 }
 async function writeFile(path,body){
  if(!writeToken)throw new GitHubApiError("Cadastro indisponível: credencial GitHub de escrita não configurada.",503,"GITHUB_WRITE_NOT_CONFIGURED");
  return limited(async()=>{
   const response=await fetchImpl(new URL(path,API_ROOT),{method:"PUT",headers:{Accept:"application/vnd.github+json",Authorization:"Bearer "+writeToken,"X-GitHub-Api-Version":API_VERSION,"User-Agent":"mmcromero-portal-governanca","Content-Type":"application/json"},body:JSON.stringify(body),signal:AbortSignal.timeout(12_000)});
   if(!response.ok){const status=response.status;const message=status===401?"Credencial GitHub de escrita inválida ou expirada.":status===403?"GitHub recusou a escrita; confira Contents: Read and write no repositório.":status===409||status===422?"O marcador já existe ou o GitHub recusou a criação por conflito.":"GitHub respondeu HTTP "+status+" ao criar o marcador.";throw new GitHubApiError(message,status===401?401:status===403?403:status===409||status===422?409:502,status===409||status===422?"GITHUB_MARKER_CONFLICT":"GITHUB_WRITE_HTTP_"+status);}
   return response.json();
  });
 }
 async function settled(path){try{return{data:(await request(path)).data,error:null};}catch(error){return{data:null,error:{code:error.code||"GITHUB_REQUEST_FAILED",message:error.message}};}}
 async function listOwnedRepositories(){
  const all=[];let page=1;
  while(page<=20){const result=await request("/user/repos?visibility=all&affiliation=owner&per_page=100&sort=full_name&direction=asc&page="+page);
   if(!Array.isArray(result.data))throw new GitHubApiError("Resposta inválida ao listar repositórios.",502,"GITHUB_INVALID_REPOSITORY_LIST");
   all.push(...result.data.filter(r=>r.owner?.login?.toLowerCase()===OWNER));
   if(!result.link.includes('rel="next"'))break;page++;
  }
  if(page>20)throw new GitHubApiError("Descoberta excedeu o limite de segurança de páginas.",502,"GITHUB_REPOSITORY_LIMIT");
  return all;
 }
 function parseManifest(encoded,repo){
  let value;try{value=JSON.parse(Buffer.from(encoded,"base64").toString("utf8"));}catch{throw new GitHubApiError("JSON inválido em "+repo.full_name+"/"+MARKER,422,"GITHUB_INVALID_PROJECT_MANIFEST");}
  const valid=s=>typeof s==="string"&&s.trim().length>0&&s.trim().length<=120;
  const p=value?.project;
  if(value?.schema_version!==1||!valid(p?.id)||!valid(p?.name)||!valid(p?.domain)||!valid(p?.description)||(p.enabled!==undefined&&typeof p.enabled!=="boolean")||(p.repositories!==undefined&&!Array.isArray(p.repositories)))
   throw new GitHubApiError("Schema inválido em "+repo.full_name+"/"+MARKER,422,"GITHUB_INVALID_PROJECT_MANIFEST");
  if(p.enabled===false)return null;
  const own=p.repositories?.find(x=>x.full_name===repo.full_name);
  return{id:p.id.trim(),name:p.name.trim(),domain:p.domain.trim(),summary:p.description.trim(),role:valid(own?.role)?own.role.trim():"Repositório do projeto"};
 }
 async function discoverProjects(){
  const repos=await listOwnedRepositories(),projects=new Map(),warnings=[];
  for(const repo of repos){if(!repo.default_branch)continue;
   try{const result=await request("/repos/"+repo.full_name+"/contents/"+MARKER+"?ref="+encodeURIComponent(repo.default_branch));
    if(result.data?.type!=="file"||typeof result.data.content!=="string")continue;
    const item=parseManifest(result.data.content,repo);if(!item)continue;
    let p=projects.get(item.id);
    if(!p){p={id:item.id,name:item.name,domain:item.domain,summary:item.summary,repositories:[]};projects.set(item.id,p);}
    else if(p.name!==item.name||p.domain!==item.domain||p.summary!==item.summary)throw new GitHubApiError("Metadados divergentes para project.id "+item.id+" em "+repo.full_name,422,"GITHUB_PROJECT_METADATA_CONFLICT");
    p.repositories.push({fullName:repo.full_name,role:item.role});
   }catch(error){if(error.status!==404)warnings.push({repository:repo.full_name,code:error.code||"DISCOVERY_FAILED",message:error.message});}
  }
  return{projects:[...projects.values()].sort((a,b)=>a.name.localeCompare(b.name,"pt-BR")),scannedRepositories:repos.length,warnings};
 }
 async function getRepositoryCatalog(){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  const repos=await listOwnedRepositories();
  const items=await Promise.all(repos.filter(r=>r.default_branch).map(async repo=>{
   const base={fullName:repo.full_name,defaultBranch:repo.default_branch,description:repo.description||"",htmlUrl:repo.html_url,archived:Boolean(repo.archived),markerStatus:"available",projectId:null,projectName:null};
   try{
    const result=await request("/repos/"+repo.full_name+"/contents/"+MARKER+"?ref="+encodeURIComponent(repo.default_branch));
    if(result.data?.type!=="file"||typeof result.data.content!=="string")return base;
    let raw;try{raw=JSON.parse(Buffer.from(result.data.content,"base64").toString("utf8"));}catch{return{...base,markerStatus:"invalid"};}
    const item=parseManifest(result.data.content,repo);
    if(raw?.project?.enabled===false)return{...base,markerStatus:"disabled",projectId:raw.project.id||null,projectName:raw.project.name||null};
    return{...base,markerStatus:"registered",projectId:item?.id||null,projectName:item?.name||null};
   }catch(error){if(error.status===404)return base;if(error.code==="GITHUB_INVALID_PROJECT_MANIFEST")return{...base,markerStatus:"invalid",error:{code:error.code,message:error.message}};return{...base,markerStatus:"unavailable",error:{code:error.code||"REPOSITORY_LOOKUP_FAILED",message:error.message}};}
  }));
  return{owner:OWNER,canRegister:Boolean(writeToken),marker:MARKER,repositories:items};
 }
 async function registerProject(input){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  if(!writeToken)throw new GitHubApiError("Cadastro indisponível: credencial GitHub de escrita não configurada.",503,"GITHUB_WRITE_NOT_CONFIGURED");
  const fullName=input?.repositoryFullName,id=input?.project?.id,name=input?.project?.name,domain=input?.project?.domain,description=input?.project?.description;
  const validText=(value,max=120)=>typeof value==="string"&&value.trim().length>0&&value.trim().length<=max;
  if(typeof fullName!=="string"||!/^mmcromero\/[A-Za-z0-9_.-]+$/.test(fullName)||!validText(id,64)||!/^[a-z0-9]+(?:-[a-z0-9]+)*$/.test(id)||!validText(name)||!validText(domain)||!validText(description))
   throw new GitHubApiError("Dados inválidos. Informe repositório próprio e metadados válidos; o ID deve usar letras minúsculas, números e hífens.",400,"GITHUB_INVALID_REGISTRATION");
  const repos=await listOwnedRepositories(),repo=repos.find(r=>r.full_name===fullName);
  if(!repo)throw new GitHubApiError("O repositório selecionado não pertence ao owner autorizado ou não está acessível.",404,"GITHUB_REPOSITORY_NOT_ALLOWED");
  if(repo.archived)throw new GitHubApiError("Não é possível cadastrar repositório arquivado.",409,"GITHUB_REPOSITORY_ARCHIVED");
  if(!repo.default_branch)throw new GitHubApiError("O repositório não possui branch padrão consultável.",409,"GITHUB_DEFAULT_BRANCH_MISSING");
  try{
   const current=await request("/repos/"+fullName+"/contents/"+MARKER+"?ref="+encodeURIComponent(repo.default_branch));
   if(current.data?.type==="file")throw new GitHubApiError("Este repositório já possui um marcador. O Portal não sobrescreve arquivos existentes.",409,"GITHUB_MARKER_EXISTS");
  }catch(error){if(error.code==="GITHUB_MARKER_EXISTS")throw error;if(error.status!==404)throw error;}
  const existing=await discoverProjects(),group=existing.projects.find(p=>p.id===id);
  if(group&&(group.name!==name.trim()||group.domain!==domain.trim()||group.summary!==description.trim()))
   throw new GitHubApiError("Este ID já pertence a outro projeto com metadados diferentes. Reutilize exatamente os metadados existentes ou escolha outro ID.",409,"GITHUB_PROJECT_METADATA_CONFLICT");
  const manifest={schema_version:1,project:{id:id.trim(),name:name.trim(),domain:domain.trim(),description:description.trim(),enabled:true,repositories:[{full_name:fullName,role:"Repositório do projeto"}]}};
  await writeFile("/repos/"+fullName+"/contents/"+MARKER,{message:"chore(portfolio): cadastrar "+name.trim(),content:Buffer.from(JSON.stringify(manifest,null,2)+"\n","utf8").toString("base64"),branch:repo.default_branch});
  cached=null;
  return{success:true,repository:fullName,branch:repo.default_branch,marker:MARKER,projectId:id.trim()};
 }
 async function fetchRepository(fullName){
  let metadata;try{metadata=(await request("/repos/"+fullName)).data;}catch(error){return{fullName,status:error.status===404?"not_found_or_no_access":"unavailable",htmlUrl:"https://github.com/"+fullName,errors:[{code:error.code||"GITHUB_REQUEST_FAILED",message:error.message}]};}
  const prefix="/repos/"+fullName;
  const results=await Promise.all([settled(prefix+"/branches?per_page=100"),settled(prefix+"/issues?state=open&per_page=100"),settled(prefix+"/pulls?state=open&per_page=100"),settled(prefix+"/releases?per_page=5"),settled(prefix+"/actions/runs?per_page=1"),settled(prefix+"/commits?sha="+encodeURIComponent(metadata.default_branch)+"&per_page=1")]);
  const [branches,issues,pulls,releases,runs,commits]=results,errors=results.filter(x=>x.error).map(x=>x.error),asArray=x=>Array.isArray(x)?x:[];
  const openIssues=asArray(issues.data).filter(x=>!x.pull_request).map(x=>({number:x.number,title:x.title,state:x.state,url:x.html_url,updatedAt:x.updated_at,labels:(x.labels||[]).map(l=>l.name)}));
  const openPulls=asArray(pulls.data).map(x=>({number:x.number,title:x.title,state:x.state,draft:x.draft,url:x.html_url,updatedAt:x.updated_at,headSha:x.head?.sha||null,baseBranch:x.base?.ref||null}));
  const run=runs.data?.workflow_runs?.[0],release=asArray(releases.data).find(x=>!x.draft&&!x.prerelease),commit=asArray(commits.data)[0];
  return{fullName,status:errors.length?"partial":"ok",htmlUrl:metadata.html_url,isPrivate:metadata.private,defaultBranch:metadata.default_branch,description:metadata.description||"",pushedAt:metadata.pushed_at,updatedAt:metadata.updated_at,branches:asArray(branches.data).map(x=>({name:x.name,sha:x.commit?.sha||null})),branchesTruncated:asArray(branches.data).length===100,latestCommit:commit?{sha:commit.sha,message:(commit.commit?.message||"").split("\n")[0],date:commit.commit?.committer?.date||commit.commit?.author?.date||null,url:commit.html_url}:null,openIssues,openIssuesTruncated:asArray(issues.data).length===100,openPulls,openPullsTruncated:asArray(pulls.data).length===100,latestRelease:release?{tag:release.tag_name,name:release.name,publishedAt:release.published_at,draft:release.draft,prerelease:release.prerelease,url:release.html_url}:null,workflowRunState:runs.error?"unavailable":run?"available":"empty",releaseState:releases.error?"unavailable":release?"available":"empty",latestWorkflowRun:run?{id:run.id,name:run.name,event:run.event,status:run.status,conclusion:run.conclusion,createdAt:run.created_at,updatedAt:run.updated_at,headSha:run.head_sha,headBranch:run.head_branch,url:run.html_url}:null,errors};
 }

 async function getRecentAgentComments({since,perPage=100,maxPages=5}={}){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  const current=now(),candidate=since?new Date(since):new Date(current.getTime()-6*60*60*1000);
  if(!Number.isFinite(candidate.getTime())||candidate>new Date(current.getTime()+60_000)||candidate<new Date(current.getTime()-24*60*60*1000))
   throw new GitHubApiError("Janela de consulta de eventos inválida; use um timestamp recente (máximo 24 horas).",400,"GITHUB_INVALID_AGENT_EVENT_WINDOW");
  const pageSize=Math.min(Math.max(1,Number(perPage)||100),100),pageLimit=Math.min(Math.max(1,Number(maxPages)||5),5);
  const discovery=await discoverProjects(),repositories=[...new Set(discovery.projects.flatMap(p=>p.repositories.map(r=>r.fullName)))].sort();
  const events=[],warnings=[];
  for(const fullName of repositories){
   let page=1,hasNext=false;
   do{
    const path="/repos/"+fullName+"/issues/comments?since="+encodeURIComponent(candidate.toISOString())+"&per_page="+pageSize+"&sort=created&direction=asc&page="+page;
    const result=await request(path);
    if(!Array.isArray(result.data))throw new GitHubApiError("Resposta inválida ao listar comentários de "+fullName+".",502,"GITHUB_INVALID_ISSUE_COMMENTS");
    hasNext=result.link.includes('rel="next"');
    for(const comment of result.data){
     const body=typeof comment.body==="string"?comment.body:"";
     if(!body.includes("<!-- AGENT_PROTOCOL_EVENT -->"))continue;
     if(!["OWNER","MEMBER","COLLABORATOR"].includes(comment.author_association))continue;
     const created=Date.parse(comment.created_at||""),updated=Date.parse(comment.updated_at||"");
     if(!Number.isFinite(created)||!Number.isFinite(updated)||Math.abs(updated-created)>5000)continue;
     const issueNumber=Number(String(comment.issue_url||"").match(/\/issues\/(\d+)$/)?.[1]);
     if(!Number.isInteger(issueNumber)||issueNumber<1)continue;
     const issue=(await request("/repos/"+fullName+"/issues/"+issueNumber)).data;
     if(issue?.pull_request)continue;
     events.push({
      headers:{"x-github-event":"issue_comment","x-github-delivery":"poll-"+String(comment.id)},
      body:{
       action:"created",
       repository:{full_name:fullName,owner:{login:OWNER}},
       issue:{number:issue.number,title:issue.title,html_url:issue.html_url},
       comment:{id:comment.id,body,author_association:comment.author_association,user:{login:comment.user?.login||""},created_at:comment.created_at,html_url:comment.html_url}
      }
     });
    }
    page++;
   }while(hasNext&&page<=pageLimit);
   if(hasNext)warnings.push({repository:fullName,code:"GITHUB_AGENT_EVENT_PAGE_LIMIT",message:"Mais comentários recentes que o limite de páginas; a próxima consulta continuará na janela sobreposta."});
  }
  events.sort((a,b)=>String(a.body.comment.created_at).localeCompare(String(b.body.comment.created_at)));
  return{source:"GitHub REST API",checkedAt:current.toISOString(),since:candidate.toISOString(),repositoryCount:repositories.length,eventCount:events.length,events,warnings};
 }
 async function getPortfolio(_projects=[],{force=false}={}){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  if(!force&&cached&&Date.now()-cached.cachedAt<cacheMs)return{...cached.payload,cache:"HIT"};
  const discovery=await discoverProjects(),unique=[...new Set(discovery.projects.flatMap(p=>p.repositories.map(r=>r.fullName)))];
  const pairs=await Promise.all(unique.map(async name=>[name,await fetchRepository(name)])),snapshots=Object.fromEntries(pairs);
  const payload={source:"GitHub REST API",mode:"live-read-only-auto-discovery",checkedAt:now().toISOString(),cache:"MISS",discovery:{file:MARKER,owner:OWNER,scannedRepositories:discovery.scannedRepositories,projectsFound:discovery.projects.length,warnings:discovery.warnings},projects:discovery.projects.map(p=>({...p,repositories:p.repositories.map(r=>({...r,snapshot:snapshots[r.fullName]||{fullName:r.fullName,status:"not_queried",errors:[]}}))}))};
  cached={cachedAt:Date.now(),payload};return payload;
 }
 return{getPortfolio,discoverProjects,getRepositoryCatalog,registerProject,getRecentAgentComments};
}
