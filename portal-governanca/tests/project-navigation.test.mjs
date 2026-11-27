import {describe,expect,it} from "vitest";
import {buildPortalHash,parsePortalHash,projectIdsMatch,runnerProjectId} from "../src/project-navigation";

describe("project-aware portal navigation",()=>{
 it("restores a project detail section from the URL",()=>{
  expect(parsePortalHash("#project/avisaqui/evidence")).toEqual({view:"projects",projectId:"avisaqui",section:"evidence"});
 });
 it("preserves a selected project in global operations",()=>{
  expect(parsePortalHash("#missions?project=avisaqui")).toEqual({view:"missions",projectId:"avisaqui",section:"overview"});
 });
 it("uses the portfolio list for an all-projects context",()=>{
  expect(parsePortalHash("#projects")).toEqual({view:"projects",projectId:null,section:"overview"});
 });
 it("falls back safely for invalid views, ids and sections",()=>{
  expect(parsePortalHash("#not-a-view?project=bad%20id")).toEqual({view:"overview",projectId:null,section:"overview"});
  expect(parsePortalHash("#project/avisaqui/not-a-section").section).toBe("overview");
  expect(parsePortalHash("#project/%E0%A4%A/evidence").projectId).toBeNull();
  expect(parsePortalHash("#missions?project=artesao_digital").projectId).toBe("artesao_digital");
 });
 it("reconhece o ID legado do Artesão e o ID aceito pelo Runner",()=>{
  expect(projectIdsMatch("artesao-digital","artesao_digital")).toBe(true);
  expect(runnerProjectId("artesao-digital")).toBe("artesao_digital");
  expect(runnerProjectId("avisaqui")).toBe("avisaqui");
  expect(runnerProjectId("outro-projeto")).toBeNull();
 });
 it("preserves project context on the global overview route",()=>{
  expect(parsePortalHash("#overview?project=avisaqui")).toEqual({view:"overview",projectId:"avisaqui",section:"overview"});
  expect(buildPortalHash({view:"overview",projectId:"avisaqui",section:"overview"})).toBe("#overview?project=avisaqui");
 });
 it("builds stable, reloadable routes",()=>{
  expect(buildPortalHash({view:"projects",projectId:"avisaqui",section:"decisions"})).toBe("#project/avisaqui/decisions");
  expect(buildPortalHash({view:"missions",projectId:"avisaqui",section:"overview"})).toBe("#missions?project=avisaqui");
 });
});
