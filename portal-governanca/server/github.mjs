const API_ROOT="https://api.github.com";
const API_VERSION="2022-11-28";
const OWNER="mmcromero";
const MARKER=".portal-governanca.json";
export class GitHubApiError extends Error{
 constructor(message,status=502,code="GITHUB_API_ERROR"){super(message);this.name="GitHubApiError";this.status=status;this.code=code;}
}
export function createGitHubClient({token,fetchImpl=fetch,cacheMs=60_000,now=()=>new Date()}){
 let cached=null,inFlight=0;const waiters=[];
 async function limited(task){if(inFlight>=4)await new Promise(resolve=>waiters.push(resolve));inFlight++;try{return await task();}finally{inFlight--;const next=waiters.shift();if(next)next();}}
 async function request(path){
  return limited(async()=>{const response=await fetchImpl(new URL(path,API_ROOT),{method:"GET",headers:{Accept:"application/vnd.github+json",Authorization:"Bearer "+token,"X-GitHub-Api-Version":API_VERSION,"User-Agent":"mmcromero-portal-governanca"},signal:AbortSignal.timeout(12_000)});
   if(!response.ok){const status=response.status;const message=status===401?"Credencial GitHub inválida ou expirada.":status===403?"GitHub recusou a consulta: verifique permissões somente leitura e limite de requisições.":status===404?"Repositório ou recurso não encontrado ou sem acesso.":"GitHub respondeu HTTP "+status+".";throw new GitHubApiError(message,status===404?404:status===403?403:status===401?401:502,"GITHUB_HTTP_"+status);}
   return {data:await response.json(),link:response.headers?.get?.("link")||""};
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
 async function getPortfolio(_projects=[],{force=false}={}){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  if(!force&&cached&&Date.now()-cached.cachedAt<cacheMs)return{...cached.payload,cache:"HIT"};
  const discovery=await discoverProjects(),unique=[...new Set(discovery.projects.flatMap(p=>p.repositories.map(r=>r.fullName)))];
  const pairs=await Promise.all(unique.map(async name=>[name,await fetchRepository(name)])),snapshots=Object.fromEntries(pairs);
  const payload={source:"GitHub REST API",mode:"live-read-only-auto-discovery",checkedAt:now().toISOString(),cache:"MISS",discovery:{file:MARKER,owner:OWNER,scannedRepositories:discovery.scannedRepositories,projectsFound:discovery.projects.length,warnings:discovery.warnings},projects:discovery.projects.map(p=>({...p,repositories:p.repositories.map(r=>({...r,snapshot:snapshots[r.fullName]||{fullName:r.fullName,status:"not_queried",errors:[]}}))}))};
  cached={cachedAt:Date.now(),payload};return payload;
 }
 return{getPortfolio,discoverProjects};
}
