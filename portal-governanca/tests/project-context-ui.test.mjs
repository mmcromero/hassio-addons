import {describe,expect,it} from "vitest";
import fs from "node:fs";

const main=fs.readFileSync(new URL("../src/main.ts",import.meta.url),"utf8");
const api=fs.readFileSync(new URL("../src/api/client.ts",import.meta.url),"utf8");
const server=fs.readFileSync(new URL("../server/index.mjs",import.meta.url),"utf8");

describe("central de projeto e contexto universal",()=>{
 it("mantém apenas operações globais no menu principal",()=>{
  const nav=main.slice(main.indexOf("const nav:"),main.indexOf("const app ="));
  expect(nav).toContain("Visão geral");
  expect(nav).toContain("Portfólio");
  expect(nav).toContain("Missões");
  expect(nav).toContain("Automações");
  expect(nav).toContain("Ambientes");
  expect(nav).not.toContain("Homologações");
  expect(nav).not.toContain("Evidências");
  expect(nav).not.toContain("Decisões e histórico");
  expect(nav).not.toContain("Cadastrar projeto");
 });
 it("preserva contexto na URL e oferece seletor universal",()=>{
  expect(main).toContain("projectContextSelector()");
  expect(main).toContain("data-project-context");
  expect(main).toContain("syncRoute()");
  expect(main).toContain("parsePortalHash");
  expect(main).toContain("data-project-section");
 });
 it("agrupa homologações, evidências e decisões dentro da central do projeto",()=>{
  expect(main).toContain("recordsPage('homologation',p.id)");
  expect(main).toContain("recordsPage('evidence',p.id)");
  expect(main).toContain("recordsPage('decision',p.id)");
  expect(main).toContain("value=\"' + esc(projectId) + '\"");
 });
 it("mantém atalho direto ao GitHub no card do projeto",()=>{
  expect(main).toContain("Abrir GitHub ↗");
  expect(main).toContain("repoFor(p.repositories[0].fullName)?.htmlUrl");
 });
 it("permite consultar registros e missões por projeto no cliente e no BFF",()=>{
  expect(api).toContain('getPortalRecords(projectId?:string)');
  expect(api).toContain('getMissions(projectId?:string)');
  expect(server).toContain('ledger.list({projectId})');
  expect(server).toContain('ledger.listMissions({projectId,limit:100})');
 });
 it("preserva o contexto ao voltar à Visão geral e recarrega a central ao trocar de projeto",()=>{
  expect(main).toContain("projectId: view === 'register' ? null : contextProjectId");
  expect(main).not.toContain("if (view === 'overview') { contextProjectId = null");
  expect(main).toContain("if (projectSection === 'agents') void loadAgentEvents(selected.id)");
  expect(main).toContain("if (projectSection === 'environments') void loadSupervisor(false)");
  expect(main).toContain("Nenhum app do Home Assistant está vinculado a este projeto.");
  expect(main).toContain("if (projectSection === 'resources') { void loadSupervisor(false); void loadN8n(false); }");
  expect(main).toContain("if (['homologation','evidence','decisions'].includes(projectSection)) void loadRecords(selected.id)");
 });
 it("protege consultas contextuais contra respostas antigas fora de ordem",()=>{
  expect(main).toContain("let ledgerRequestVersion = 0");
  expect(main).toContain("if (requestVersion === ledgerRequestVersion) ledgerSnapshot = result");
  expect(main).toContain("let missionsRequestVersion = 0");
  expect(main).toContain("if (requestVersion === missionsRequestVersion) missionsSnapshot = result");
  expect(main).toContain("let agentRequestVersion = 0");
  expect(main).toContain("if (requestVersion === agentRequestVersion) agentSnapshot = result");
 });
 it("exibe recursos externos com estado e proveniência sem afirmar atividade atual",()=>{
  const resources=fs.readFileSync(new URL("../src/data/project-resources.ts",import.meta.url),"utf8");
  expect(resources).toContain("artesao-digital-cloudflare-tunnel");
  expect(resources).toContain("forja-01-artesao");
  expect(resources).toContain("last_observed_active");
  expect(resources).toContain("requer revalidação direta");
  expect(main).toContain("GitHub Codespaces");
  expect(main).toContain("runnerProjectId(p.id)");
  expect(main).toContain("projectIdsMatch(m.projectId, projectId)");
 });
 it("não mostra evidência de build do Portal dentro de outros projetos",()=>{
  expect(main).toContain("projectId === 'portal-governanca' ? buildEvidencePanel()");
 });
});
