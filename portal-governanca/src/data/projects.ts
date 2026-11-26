import registry from "../../config/portfolio.json";
export type RepositoryReference={fullName:string;role:string;path?:string};
export type Project={id:string;name:string;domain:string;summary:string;repositories:RepositoryReference[]};
export const projects=registry.projects as Project[];
