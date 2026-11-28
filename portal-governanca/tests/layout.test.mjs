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
  expect(main).not.toContain("shell.classList.toggle('project-shell'");
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
 it("usa toda a largura disponível e separa sidebar do conteúdo no desktop",()=>{
  expect(css).toContain("grid-template-columns:13.25rem minmax(0,1fr)");
  expect(css).toContain("column-gap:1.5rem");
  expect(css).toContain("max-width:none");
  expect(css).toContain("margin:0");
  expect(css).toContain("min-height:100dvh");
  expect(css).toContain("grid-row:1/4");
  expect(css).toContain(".workspace header{align-items:center;padding-bottom:.8rem;margin-bottom:1rem}");
 });
 it("preserva o cabeçalho aprovado e os ícones das integrações",()=>{
  expect(main).toContain("header.className = 'topbar'");
  expect(main).toContain('class="top-actions"');
  expect(main).toContain("uiIcon('refresh')");
  expect(main).toContain("card('github','GitHub REST API'");
  expect(main).toContain("card('layers','Supervisor Bridge'");
  expect(main).toContain("card('n8n','n8n API'");
  expect(main).toContain("card('bot','Protocolo de Agentes'");
  expect(main).toContain("uiIcon('check')");
  expect(css).toContain(".workspace > header.topbar");
  expect(css).toContain(".integration-grid{display:grid;grid-template-columns:repeat(4");
  expect(css).toContain(".integration-card > .ds-card > .ds-card-body{");
  expect(css).toContain("display:flex;flex-direction:row;align-items:center");
 });
 it("mantém as oito abas da central individual",()=>{
  for(const id of ["overview","development","homologation","evidence","decisions","resources","agents","environments"])expect(main).toContain("id:'"+id+"'");
  expect(main).toContain("project-section-content");
 });
 it("preserva header, navegação e footer e atualiza apenas main entre rotas",()=>{
  expect(main).toContain("if (!app!.querySelector");
  expect(main).toContain("main.innerHTML = body()");
  expect(main).toContain("globalNav.hidden = false");
  expect(main).not.toContain("globalNav.hidden = projectFocused");
  expect(css).not.toContain(".project-shell");
  expect(css).toContain(".workspace > nav[data-ds-region=\"navigation\"]{");
  expect(css).toContain("position:sticky;top:0;height:100vh");
  expect(main).toContain("navOnce.addEventListener");
  expect(main).toContain("main.innerHTML = body()");
  expect(main).toContain("Header, navegação e footer são regiões globais permanentes");
 });
 it("preserva o catálogo de repositórios no Portfólio e o fluxo de cadastro manual",()=>{
  expect(main).toContain("function portfolioRepositoryCatalog()");
  expect(main).toContain("portfolioRepositoryCatalog() + '</section>'");
  expect(main).toContain('<h3>Já cadastrados</h3>');
  expect(main).toContain('<h3>Ainda não cadastrados</h3>');
  expect(main).toContain('data-view="register">Cadastrar projeto</ds-button>');
  expect(main).toContain("main.querySelectorAll<HTMLElement>('[data-view]')");
  expect(main).toContain("if (view === 'register') return registrationPage();");
  expect(main).toContain("data-register-form");
  expect(main).toContain("if ((view === 'register' || (view === 'projects' && !selected)) && !catalog && !catalogLoading) void loadCatalog();");
 });
 it("oferece cadastro e descadastro rápidos sem remover o cadastro manual",()=>{
  expect(main).toContain('data-repository-action="unregister"');
  expect(main).toContain('data-repository-action="register"');
  expect(main).toContain("runRepositoryAction(action, repository)");
  expect(main).toContain("function registrationPage()");
  expect(main).toContain("data-register-form");
  expect(main).toContain("markerStatus === 'disabled'");
 });
 it("aplica regras visuais compartilhadas às telas e aos formulários",()=>{
  for(const selector of [".workspace main > section",".workspace main .registration-form",".workspace main :is(ds-card,.repo-card,.repo-row)",".workspace main .project-tabs","@media(max-width:650px)","@media(max-width:420px)"])expect(css).toContain(selector);
 });
 it("mantém a navegação global no fluxo normal do App Shell",()=>{
  expect(css).toContain('.workspace > nav[data-ds-region="navigation"]{');
  expect(css).toContain("position:sticky;top:0;height:100vh");
 });
 it("move o foco para o conteúdo sem provocar rolagem automática da página",()=>{
  expect(main).toContain("focus({preventScroll:true})");
  expect(main).not.toContain("document.querySelector<HTMLElement>('#main-content')?.focus();");
 });
 it("mantém o App Shell utilizável em mobile após todas as regras do header",()=>{
  const mobileShell=css.slice(css.lastIndexOf("@media(max-width:900px)"));
  expect(css.lastIndexOf(".workspace > header.topbar{")).toBeGreaterThan(css.lastIndexOf("@media(max-width:900px)"));
  expect(mobileShell).toContain("grid-template-columns:minmax(0,1fr)");
  expect(mobileShell).toContain('.workspace > header.topbar{grid-column:1;grid-row:1}');
  expect(mobileShell).toContain('.workspace > nav[data-ds-region="navigation"]{');
  expect(mobileShell).toContain("grid-column:1;grid-row:2;position:static");
  expect(mobileShell).toContain(".sidebar-links{display:flex;overflow-x:auto");
  expect(mobileShell).toContain('.workspace > main[data-ds-region="main"]{grid-column:1;grid-row:3}');
  expect(mobileShell).toContain('.workspace > footer[data-ds-region="footer"]{grid-column:1;grid-row:4}');
 });

});