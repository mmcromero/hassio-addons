export type RepositoryReference={fullName:string;role:string;path?:string;snapshot?:RepoSnapshot};
export type Project={id:string;name:string;domain:string;summary:string;repositories:RepositoryReference[]};
export type RepoSnapshot={
 fullName:string;status:string;htmlUrl?:string;isPrivate?:boolean;defaultBranch?:string;description?:string;
 pushedAt?:string;updatedAt?:string;branches?:{name:string;sha:string|null}[];branchesTruncated?:boolean;
 latestCommit?:{sha:string;message:string;date:string|null;url:string}|null;
 latestIssue?:{number:number;title:string;state:string;url:string;createdAt:string;updatedAt:string}|null;latestIssueState?:"unavailable"|"available"|"empty";
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

export type N8nWorkflow={id:string;name:string;active:boolean|null;createdAt:string|null;updatedAt:string|null;tags:string[];projectId:string|null};
export type N8nExecution={id:string;workflowId:string;workflowName:string|null;status:string;mode:string;startedAt:string|null;stoppedAt:string|null;waitTill:string|null};
export type N8nOverview={status:"ok"|"not_configured"|"unavailable";source:string;checkedAt:string;workflowCount?:number;activeCount?:number;inactiveCount?:number;executionCount?:number;failedExecutions?:number;workflows:N8nWorkflow[];executions:N8nExecution[];truncated?:{workflows:boolean;executions:boolean};cache?:"HIT"|"MISS";error?:{code:string;message:string}};
export async function getN8nOverview(refresh=false):Promise<N8nOverview>{
 const endpoint=new URL("api/v1/n8n/overview",document.baseURI);
 if(refresh)endpoint.searchParams.set("refresh","1");
 const response=await fetch(endpoint,{headers:{Accept:"application/json"},cache:"no-store"});
 const data=await response.json();
 if(!response.ok)throw Object.assign(new Error(data.error?.message||"HTTP "+response.status),{code:data.error?.code,status:response.status});
 return data as N8nOverview;
}

export type TimelineEvent={id:string;createdAt:string;eventId:string;occurredAt:string;confidence:"confirmed"|"estimated"|"unknown";category:string;sourceName:string;title:string;summary:string;projectId:string|null;repository:string|null;sha:string|null;sourceUrl:string|null;activeDays?:number|null;hash:string;previousHash:string};
export type ProjectTimelineResponse={events:TimelineEvent[];total:number;integrity:string;lastHash:string;serverNow?:string;timeZone?:string;collection?:{checkedAt:string;discovered:number;added:number;projectCount:number}};
export function getProjectTimeline(projectId:string):Promise<ProjectTimelineResponse>{return apiRequest<ProjectTimelineResponse>("api/v1/timeline?project="+encodeURIComponent(projectId));}
export function collectProjectTimeline(projectId:string,force=false):Promise<ProjectTimelineResponse>{return apiRequest<ProjectTimelineResponse>("api/v1/timeline/collect?project="+encodeURIComponent(projectId)+(force?"&force=1":""),{method:"POST",body:"{}"});}
export function endProjectTimeline(projectId:string):Promise<ProjectTimelineResponse>{return apiRequest<ProjectTimelineResponse>("api/v1/timeline/end",{method:"POST",body:JSON.stringify({projectId})});}
export function cancelProjectTimeline(projectId:string):Promise<ProjectTimelineResponse>{return apiRequest<ProjectTimelineResponse>("api/v1/timeline/cancel",{method:"POST",body:JSON.stringify({projectId})});}
export type PortalRecord={id:string;createdAt:string;type:"homologation"|"evidence"|"decision"|"agent_event"|"timeline_event"|"mission"|"mission_status";title:string;summary:string;status:string|null;projectId:string|null;repository:string|null;sha:string|null;version:string|null;environment:string|null;responsible:string|null;origin:string;evidenceKind:string|null;sourceUrl:string|null;previousHash:string;hash:string;eventId?:string|null;eventType?:string|null;agentId?:string|null;taskId?:string|null;deliverables?:string[];nextAction?:string|null;occurredAt?:string|null;confidence?:string|null;category?:string|null;sourceName?:string|null;activeDays?:number|null;missionStatus?:string|null;executionId?:string|null;runnerStatus?:string|null;dispatchError?:string|null;prompt?:string|null};
export type PortalLedger={records:PortalRecord[];total:number;integrity:string;lastHash:string};
export type BuildEvidence={schemaVersion:1;kind:"supervisor-addon-build";status:"PASS";builtAt:string;source:{repository:string;commit:string};addon:{version:string;architecture:"aarch64";nodeVersion:string};designSystem:{repository:string;commit:string};lockfile:{version:3;sha256:string};tests:{runner:"Vitest";status:"PASS";total:number;passed:number;failed:number;pending:number;todo:number;totalSuites:number;passedSuites:number;failedSuites:number;durationMs:number|null};build:{designSystem:"PASS";typescript:"PASS";vite:"PASS";strategy:string}};
export function getBuildEvidence():Promise<BuildEvidence>{return apiRequest<BuildEvidence>("build-evidence.json");}
export function getPortalRecords():Promise<PortalLedger>{return apiRequest<PortalLedger>("api/v1/records");}
export function appendPortalRecord(input:Partial<PortalRecord>):Promise<{record:PortalRecord}>{return apiRequest("api/v1/records",{method:"POST",body:JSON.stringify(input)});}

export type AgentEvent={id:string;createdAt:string;type:"agent_event";title:string;summary:string;projectId:string|null;eventId:string;eventType:"inicio"|"atualizacao"|"conclusao"|"impedimento"|"bastao";agentId:string;taskId:string;deliverables:string[];nextAction:string|null;responsible:string;origin:string;hash:string;previousHash:string};
export type AgentEventsResponse={events:AgentEvent[];total:number;lastUpdated:string|null};
export function getAgentEvents(params?:{project?:string;agent?:string;limit?:number}):Promise<AgentEventsResponse>{
 const search=new URLSearchParams();
 if(params?.project)search.set("project",params.project);
 if(params?.agent)search.set("agent",params.agent);
 if(params?.limit)search.set("limit",String(params.limit));
 const qs=search.toString();
 return apiRequest<AgentEventsResponse>("api/v1/agent-events"+(qs?"?"+qs:""));
}

export type SystemStatus={checkedAt:string;github:{configured:boolean;registrationConfigured:boolean;status:string};homeAssistant:{bridgeConfigured:boolean;status:string};n8n:{configured:boolean;status:string};agentProtocol:{status:string;totalEvents:number;lastEventAt:string|null}};
export function getSystemStatus():Promise<SystemStatus>{return apiRequest<SystemStatus>("api/v1/system-status");}

export type PortalMission={id:string;createdAt:string;title:string;summary:string;projectId:string|null;repository:string|null;prompt:string;missionStatus:"received"|"dispatched"|"planning"|"planned"|"partial"|"blocked"|"cancelled"|"dispatch_blocked";executionId:string|null;runnerStatus:string|null;dispatchError:string|null;planStatus:"PLANNED"|"PARTIAL"|"BLOCKED_SCOPE"|null;selectedCount:number|null;reusedCount:number|null;omittedCount:number|null;planDigest:string|null;receiptDigest:string|null;testsExecutionPerformed:boolean|null;authorizationVerified:boolean|null;nextRunnerAction:string|null;dispatchUpdatedAt:string|null};
export type MissionsResponse={missions:PortalMission[];total:number;lastUpdated:string|null};
export function getMissions():Promise<MissionsResponse>{return apiRequest<MissionsResponse>("api/v1/missions");}
export function createMission(input:{prompt:string;projectId:string;repository?:string}):Promise<{mission:PortalMission;dispatch:{status:"dispatched"|"blocked";executionId?:string;runnerStatus?:string;code?:string}}>{
 return apiRequest<{mission:PortalMission;dispatch:{status:"dispatched"|"blocked";executionId?:string;runnerStatus?:string;code?:string}}>("api/v1/missions",{method:"POST",body:JSON.stringify(input)});
}
