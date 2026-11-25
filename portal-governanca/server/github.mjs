const API_ROOT="https://api.github.com";
const API_VERSION="2022-11-28";
export class GitHubApiError extends Error{
 constructor(message,status=502,code="GITHUB_API_ERROR"){super(message);this.name="GitHubApiError";this.status=status;this.code=code;}
}
export function createGitHubClient({token,fetchImpl=fetch,cacheMs=60_000,now=()=>new Date()}){
 let cached=null,inFlight=0;const waiters=[];
 async function limited(task){
  if(inFlight>=4)await new Promise(resolve=>waiters.push(resolve));
  inFlight++;
  try{return await task();}finally{inFlight--;const next=waiters.shift();if(next)next();}
 }
 async function request(path){
  return limited(async()=>{
   const response=await fetchImpl(new URL(path,API_ROOT),{method:"GET",headers:{
    Accept:"application/vnd.github+json",Authorization:"Bearer "+token,
    "X-GitHub-Api-Version":API_VERSION,"User-Agent":"mmcromero-portal-governanca"
   },signal:AbortSignal.timeout(12_000)});
   if(!response.ok){
    const status=response.status;
    const message=status===401?"Credencial GitHub inválida ou expirada.":status===403?
     "GitHub recusou a consulta: verifique permissões somente leitura e limite de requisições.":status===404?
     "Repositório ou recurso não encontrado ou sem acesso.":"GitHub respondeu HTTP "+status+".";
    throw new GitHubApiError(message,status===404?404:status===403?403:status===401?401:502,"GITHUB_HTTP_"+status);
   }
   return response.json();
  });
 }
 async function settled(path){try{return{data:await request(path),error:null};}
  catch(error){return{data:null,error:{code:error.code||"GITHUB_REQUEST_FAILED",message:error.message}};}}
 async function fetchRepository(fullName){
  let metadata;try{metadata=await request("/repos/"+fullName);}
  catch(error){return{fullName,status:error.status===404?"not_found_or_no_access":"unavailable",
   htmlUrl:"https://github.com/"+fullName,errors:[{code:error.code||"GITHUB_REQUEST_FAILED",message:error.message}]};}
  const prefix="/repos/"+fullName;
  const results=await Promise.all([
   settled(prefix+"/branches?per_page=100"),settled(prefix+"/issues?state=open&per_page=100"),
   settled(prefix+"/pulls?state=open&per_page=100"),settled(prefix+"/releases?per_page=5"),
   settled(prefix+"/actions/runs?per_page=1"),
   settled(prefix+"/commits?sha="+encodeURIComponent(metadata.default_branch)+"&per_page=1")
  ]);
  const [branches,issues,pulls,releases,runs,commits]=results;
  const errors=results.filter(x=>x.error).map(x=>x.error);
  const asArray=x=>Array.isArray(x)?x:[];
  const openIssues=asArray(issues.data).filter(item=>!item.pull_request).map(item=>({
   number:item.number,title:item.title,state:item.state,url:item.html_url,updatedAt:item.updated_at,
   labels:(item.labels||[]).map(label=>label.name)
  }));
  const openPulls=asArray(pulls.data).map(item=>({
   number:item.number,title:item.title,state:item.state,draft:item.draft,url:item.html_url,
   updatedAt:item.updated_at,headSha:item.head?.sha||null,baseBranch:item.base?.ref||null
  }));
  const latestRun=runs.data?.workflow_runs?.[0],latestRelease=asArray(releases.data).find(x=>!x.draft&&!x.prerelease),latestCommit=asArray(commits.data)[0];
  return{fullName,status:errors.length?"partial":"ok",htmlUrl:metadata.html_url,isPrivate:metadata.private,
   defaultBranch:metadata.default_branch,description:metadata.description||"",pushedAt:metadata.pushed_at,updatedAt:metadata.updated_at,
   branches:asArray(branches.data).map(branch=>({name:branch.name,sha:branch.commit?.sha||null})),
   branchesTruncated:asArray(branches.data).length===100,
   latestCommit:latestCommit?{sha:latestCommit.sha,message:(latestCommit.commit?.message||"").split("\n")[0],
    date:latestCommit.commit?.committer?.date||latestCommit.commit?.author?.date||null,url:latestCommit.html_url}:null,
   openIssues,openIssuesTruncated:asArray(issues.data).length===100,openPulls,openPullsTruncated:asArray(pulls.data).length===100,
   latestRelease:latestRelease?{tag:latestRelease.tag_name,name:latestRelease.name,publishedAt:latestRelease.published_at,
    draft:latestRelease.draft,prerelease:latestRelease.prerelease,url:latestRelease.html_url}:null,
   workflowRunState:runs.error?"unavailable":latestRun?"available":"empty",
   releaseState:releases.error?"unavailable":latestRelease?"available":"empty",
   latestWorkflowRun:latestRun?{id:latestRun.id,name:latestRun.name,event:latestRun.event,status:latestRun.status,
    conclusion:latestRun.conclusion,createdAt:latestRun.created_at,updatedAt:latestRun.updated_at,
    headSha:latestRun.head_sha,headBranch:latestRun.head_branch,url:latestRun.html_url}:null,errors};
 }
 async function getPortfolio(projects,{force=false}={}){
  if(!token)throw new GitHubApiError("Integração GitHub ainda não configurada no servidor.",503,"GITHUB_NOT_CONFIGURED");
  if(!force&&cached&&Date.now()-cached.cachedAt<cacheMs)return{...cached.payload,cache:"HIT"};
  const unique=[...new Set(projects.flatMap(project=>project.repositories.map(repo=>repo.fullName)))];
  const pairs=await Promise.all(unique.map(async name=>[name,await fetchRepository(name)]));
  const repositories=Object.fromEntries(pairs),checkedAt=now().toISOString();
  const payload={source:"GitHub REST API",mode:"live-read-only",checkedAt,cache:"MISS",
   projects:projects.map(project=>({id:project.id,name:project.name,repositories:project.repositories.map(reference=>({
    ...reference,snapshot:repositories[reference.fullName]||{fullName:reference.fullName,status:"not_queried",errors:[]}
   }))}))};
  cached={cachedAt:Date.now(),payload};return payload;
 }
 return{getPortfolio};
}
