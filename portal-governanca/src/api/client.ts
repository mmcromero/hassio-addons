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
