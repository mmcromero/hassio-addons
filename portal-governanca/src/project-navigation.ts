export type PortalView = "overview" | "agents" | "missions" | "projects" | "register" | "environments" | "automations";
export type ProjectSection = "overview" | "development" | "homologation" | "evidence" | "decisions" | "agents" | "environments" | "resources";
export type PortalRoute = { view: PortalView; projectId: string | null; section: ProjectSection };

const views = new Set<PortalView>(["overview","agents","missions","projects","register","environments","automations"]);
const sections = new Set<ProjectSection>(["overview","development","homologation","evidence","decisions","agents","environments","resources"]);
const idPattern = /^[a-z0-9]+(?:[-_][a-z0-9]+)*$/;

export function parsePortalHash(hash: string): PortalRoute {
  const raw = String(hash || "").replace(/^#/, "");
  if (raw.startsWith("project/")) {
    const parts = raw.split("/");
    let projectId = "";
    try { projectId = decodeURIComponent(parts[1] || ""); } catch { projectId = ""; }
    const section = (parts[2] || "overview") as ProjectSection;
    return {
      view: "projects",
      projectId: idPattern.test(projectId) ? projectId : null,
      section: sections.has(section) ? section : "overview"
    };
  }
  const [path, query = ""] = raw.split("?", 2);
  const view = (path || "overview") as PortalView;
  const params = new URLSearchParams(query);
  const projectId = params.get("project");
  return {
    view: views.has(view) ? view : "overview",
    projectId: projectId && idPattern.test(projectId) ? projectId : null,
    section: "overview"
  };
}

export function buildPortalHash(route: PortalRoute): string {
  if (route.view === "projects" && route.projectId) {
    const section = sections.has(route.section) ? route.section : "overview";
    return "#project/" + encodeURIComponent(route.projectId) + "/" + section;
  }
  const view = views.has(route.view) ? route.view : "overview";
  if (!route.projectId || view === "register") return "#" + view;
  return "#" + view + "?project=" + encodeURIComponent(route.projectId);
}

const projectIdAliasGroups = [
  new Set(["artesao-digital","artesao_digital"])
];

export function projectIdsMatch(left:string|null|undefined,right:string|null|undefined):boolean {
  if(!left||!right)return false;
  if(left===right)return true;
  return projectIdAliasGroups.some(group=>group.has(left)&&group.has(right));
}

export function runnerProjectId(projectId:string):string|null {
  if(projectId==="artesao-digital")return "artesao_digital";
  if(projectId==="artesao_digital")return "artesao_digital";
  if(projectId==="avisaqui")return "avisaqui";
  return null;
}
