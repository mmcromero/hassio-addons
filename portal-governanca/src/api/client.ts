export type RepositoryReference={fullName:string;role:string;path?:string;snapshot?:RepoSnapshot};
export type Project={id:string;name:string;domain:string;summary:string;repositories:RepositoryReference[]};
export type RepoSnapshot={
 fullName:string;status:string;htmlUrl?:string;isPrivate?:boolean;defaultBranch?:string;description?:string;
 pushedAt?:string;updatedAt?:string;branches?:{name:string;sha:string|null}[];branchesTruncated?:boolean;
 latestCommit?:{sha:string;message:string;date:string|null;url:string}|null;
 openIssues?:{number:number;title:string;state:string;url:string;updatedAt:string;labels:string[]}[];openIssuesTruncated?:boolean;
 openPulls?:{number:number;title:string;state:string;draft:boolean;url:string;updatedAt:string;headSha:string|null;baseBranch:string|null}[];openPullsTruncated?:boolean;
 latestRelease?:{tag:string;name:string|null;publishedAt:string|null;draft:boolean;prerelease:boolean;url:string}|null;
 latestWorkflowRun?:{id:number;name:string;event:string;status:string;conclusion:string|null;createdAt:string;updatedAt:string;headSha:string;headBranch:string;url:string}|null;
 workflowRunState?:"unavailable"|"available"|"empty";releaseState?:"unavailable"|"available"|"empty";
 errors?:{code:string;message:string}[];
};
export type PortfolioSnapshot={source:string;mode:string;checkedAt:string;cache:"HIT"|"MISS";
 discovery:{file:string;owner:string;scannedRepositories:number;projectsFound:number;warnings:{repository:string;code:string;message:string}[]};
 projects:Project[]};
export async function getPortfolio(refresh=false):Promise<PortfolioSnapshot>{
 const endpoint=new URL("api/v1/portfolio",document.baseURI);
 if(refresh)endpoint.searchParams.set("refresh","1");
 const response=await fetch(endpoint,{headers:{Accept:"application/json"},cache:"no-store"});
 const data=await response.json();
 if(!response.ok)throw Object.assign(new Error(data.error?.message||"HTTP "+response.status),{code:data.error?.code,status:response.status});
 return data as PortfolioSnapshot;
}

export type RepositoryCatalogItem={fullName:string;defaultBranch:string;description:string;htmlUrl:string;archived:boolean;markerStatus:"available"|"registered"|"disabled"|"invalid"|"unavailable";projectId:string|null;projectName:string|null;error?:{code:string;message:string}};
export type RepositoryCatalog={owner:string;canRegister:boolean;marker:string;repositories:RepositoryCatalogItem[]};
async function apiRequest<T>(url:string,init?:RequestInit):Promise<T>{
 const headers:Record<string,string>={Accept:"application/json"};
 if(init?.body)headers["Content-Type"]="application/json";
 const response=await fetch(new URL(url,document.baseURI),{...init,headers,cache:"no-store"});
 const data=await response.json();
 if(!response.ok)throw Object.assign(new Error(data.error?.message||"HTTP "+response.status),{code:data.error?.code,status:response.status});
 return data as T;
}
export function getRepositoryCatalog():Promise<RepositoryCatalog>{return apiRequest<RepositoryCatalog>("api/v1/repositories");}
export function registerProject(input:{repositoryFullName:string;project:{id:string;name:string;domain:string;description:string}}):Promise<{success:boolean;repository:string;branch:string;marker:string;projectId:string}>{
 return apiRequest<{success:boolean;repository:string;branch:string;marker:string;projectId:string}>("api/v1/projects/register",{method:"POST",body:JSON.stringify(input)});
}

export type SupervisorApp={slug:string;name:string;state:string;version:string|null;versionLatest:string|null;updateAvailable:boolean|null;boot:string|null;watchdog:boolean|null;ingressPanel:boolean|null;protected:boolean|null;autoUpdate:boolean|null;projectId:string|null;projectName:string|null};
export type SupervisorInventory={source:string;checkedAt:string;total:number;updatesAvailable:number;cache:"HIT"|"MISS";apps:SupervisorApp[]};
export function getSupervisorInventory(refresh=false):Promise<SupervisorInventory>{
 return apiRequest<SupervisorInventory>("api/v1/home-assistant/apps"+(refresh?"?refresh=1":""));
}
