// @vitest-environment happy-dom
import {readFile} from "node:fs/promises";
import path from "node:path";
import {describe,expect,it} from "vitest";
import {validateAppShell} from "../vendor/design-system/packages/components/src/testing/app-shell";
const css=await readFile(path.join(process.cwd(),"src/styles.css"),"utf8");
const main=await readFile(path.join(process.cwd(),"src/main.ts"),"utf8");
describe("estrutura vertical do Portal",()=>{
 it("usa App Shell em grid e preserva a ordem semântica",()=>{
  expect(css).toContain("ds-app-shell.workspace.shell{display:grid");
  expect(main).toContain("const projectFocused = view === 'projects' && !!activeProject()");
  expect(main).toContain("shell.classList.toggle('project-shell', projectFocused)");
  expect(main).toContain('<header data-ds-region="header">');
  expect(main).toContain('<nav data-ds-region="navigation" aria-label="Seções principais" class="sidebar">');
  expect(main).toContain('<main data-ds-region="main" id="main-content" tabindex="-1">');
  expect(main).toContain('<footer data-ds-region="footer">');
 });
 it("faz o conteúdo crescer e mantém o rodapé na última região",()=>{
  expect(css).toContain("grid-template-rows:auto minmax(min-content,1fr) auto");
  expect(css).toContain("margin-top:auto");
 });
 it("valida a estrutura DOM real do App Shell",()=>{
  document.body.innerHTML='<ds-app-shell><header data-ds-region="header">Topo</header><nav data-ds-region="navigation" aria-label="Seções principais">Navegação</nav><main data-ds-region="main">Conteúdo</main><footer data-ds-region="footer">Rodapé</footer></ds-app-shell>';
  const result=validateAppShell(document.querySelector("ds-app-shell"));
  expect(result.valid,result.errors.join("\n")).toBe(true);
 });
 it("mantém as oito abas da central individual",()=>{
  for(const id of ["overview","development","homologation","evidence","decisions","resources","agents","environments"])expect(main).toContain("id:'"+id+"'");
  expect(main).toContain("project-section-content");
 });
 it("preserva header, navegação e footer e atualiza apenas main entre rotas",()=>{
  expect(main).toContain("if (!app!.querySelector");
  expect(main).toContain("main.innerHTML = body()");
  expect(main).toContain("globalNav.hidden = projectFocused");
  expect(main).toContain("navOnce.addEventListener");
  expect(css).toContain("ds-app-shell.workspace.shell.project-shell{grid-template-columns:minmax(0,1fr)");
 });
 it("aplica regras visuais compartilhadas às telas e aos formulários",()=>{
  for(const selector of [".workspace main > section",".workspace main .registration-form",".workspace main :is(ds-card,.repo-card,.repo-row)",".workspace main .project-tabs","@media(max-width:650px)","@media(max-width:420px)"])expect(css).toContain(selector);
 });
 it("mantém a navegação global no fluxo normal do App Shell",()=>{
  expect(css).toContain('.workspace > nav[data-ds-region="navigation"]{position:relative;height:auto');
 });
 it("move o foco para o conteúdo sem provocar rolagem automática da página",()=>{
  expect(main).toContain("focus({preventScroll:true})");
  expect(main).not.toContain("document.querySelector<HTMLElement>('#main-content')?.focus();");
 });
});
