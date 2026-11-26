import '@mmcromero/ds-tokens/css';
import '@mmcromero/ds-components/styles.css';
import '@mmcromero/ds-components';
import {getPortfolio,type PortfolioSnapshot,type RepoSnapshot,type Project} from './api/client';
import './styles.css';

type View='overview'|'projects'|'homologation'|'evidence'|'environments'|'decisions';
const nav:{id:View;label:string}[]=[{id:'overview',label:'Visão geral'},{id:'projects',label:'Projetos'},{id:'homologation',label:'Homologações'},{id:'evidence',label:'Evidências'},{id:'environments',label:'Ambientes'},{id:'decisions',label:'Decisões e histórico'}];
const app=document.querySelector<HTMLDivElement>('#app');if(!app)throw new Error('Elemento #app não encontrado.');
let view:View='overview',selected:Project|null=null,snapshot:PortfolioSnapshot|null=null,loading=false,lastError:string|null=null,lastErrorCode:string|null=null,lastChecked:string|null=null;
const projects=()=>snapshot?.projects??[];
const esc=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]??c));
const date=(v?:string|null)=>v?new Intl.DateTimeFormat('pt-BR',{dateStyle:'short',timeStyle:'short'}).format(new Date(v)):'Não informado';
function repoFor(name:string):RepoSnapshot|null{for(const p of projects())for(const r of p.repositories)if(r.fullName===name)return r.snapshot??null;return null;}
function label(status?:string){return ({ok:'Consultado',partial:'Parcial',unavailable:'Indisponível',not_found_or_no_access:'Não encontrado / sem acesso',not_queried:'Não consultado'} as Record<string,string>)[status||'']||'Não verificado';}
function variant(status?:string){return status==='ok'?'success':status==='partial'?'warning':['unavailable','not_found_or_no_access'].includes(status||'')?'error':'neutral';}
function repoMarkup(ref:{fullName:string;role:string;path?:string}){
 const d=repoFor(ref.fullName);
 if(!d)return '<div class="repo-row"><div><strong>'+esc(ref.fullName)+'</strong><small>'+esc(ref.role)+(ref.path?' · '+esc(ref.path):'')+'</small></div><ds-badge variant="warning">Aguardando consulta</ds-badge></div>';
 const c=d.latestCommit,r=d.latestWorkflowRun,rel=d.latestRelease;
 const branches=(d.branches||[]).slice(0,6).map(b=>'<span><b>'+esc(b.name)+'</b> '+esc((b.sha||'').slice(0,7))+'</span>').join('');
 const issues=(d.openIssues||[]).slice(0,5).map(i=>'<li><a href="'+esc(i.url)+'" target="_blank" rel="noopener noreferrer">#'+i.number+' '+esc(i.title)+'</a></li>').join('');
 const pulls=(d.openPulls||[]).slice(0,5).map(p=>'<li><a href="'+esc(p.url)+'" target="_blank" rel="noopener noreferrer">#'+p.number+' '+esc(p.title)+'</a>'+(p.draft?' · rascunho':'')+'</li>').join('');
 return '<article class="repo-card"><div class="repo-top"><div><a href="'+esc(d.htmlUrl||'https://github.com/'+ref.fullName)+'" target="_blank" rel="noopener noreferrer">'+esc(ref.fullName)+'</a><small>'+esc(ref.role)+(ref.path?' · '+esc(ref.path):'')+'</small></div><ds-badge variant="'+variant(d.status)+'">'+label(d.status)+'</ds-badge></div>'+
 '<div class="repo-facts"><span>Branch padrão: <b>'+esc(d.defaultBranch||'—')+'</b></span><span>Branches listadas: <b>'+(d.branches?.length??'—')+(d.branchesTruncated?'+':'')+'</b></span><span>Issues listadas: <b>'+(d.openIssues?.length??'—')+(d.openIssuesTruncated?'+':'')+'</b></span><span>PRs listados: <b>'+(d.openPulls?.length??'—')+(d.openPullsTruncated?'+':'')+'</b></span></div>'+
 '<div class="repo-facts"><span>Último commit: <b>'+(c?esc(c.sha.slice(0,7)):'—')+'</b></span><span>Workflow: <b>'+(r?esc(r.conclusion||r.status):d.workflowRunState==='empty'?'Nenhuma execução':'Não verificado')+'</b></span><span>Release estável: <b>'+(rel?'<a href="'+esc(rel.url)+'" target="_blank" rel="noopener noreferrer">'+esc(rel.tag)+'</a>':d.releaseState==='empty'?'Nenhuma release':'Não verificada')+'</b></span></div>'+
 (c?'<p class="repo-detail"><a href="'+esc(c.url)+'" target="_blank" rel="noopener noreferrer">'+esc(c.message)+'</a> · '+date(c.date)+'</p>':'')+
 (r?'<p class="repo-detail">Última execução: <a href="'+esc(r.url)+'" target="_blank" rel="noopener noreferrer">'+esc(r.name||'Workflow')+'</a> · '+esc(r.status)+' / '+esc(r.conclusion||'sem conclusão')+' · '+date(r.updatedAt)+'</p>':'')+
 (branches?'<details class="repo-details"><summary>Branches e SHAs</summary><div class="repo-facts">'+branches+'</div></details>':'')+
 (issues?'<details class="repo-details"><summary>Issues abertas (até 5 exibidas)</summary><ul>'+issues+'</ul></details>':'')+
 (pulls?'<details class="repo-details"><summary>Pull requests abertos (até 5 exibidos)</summary><ul>'+pulls+'</ul></details>':'')+
 (d.errors?.length?'<p class="repo-error">'+d.errors.map(e=>esc(e.message)).join(' · ')+'</p>':'')+'</article>';
}
function projectCard(p:Project){
 const states=p.repositories.map(r=>repoFor(r.fullName)?.status);
 const s=states.length&&states.every(x=>x==='ok')?'ok':states.some(x=>x==='ok'||x==='partial')?'partial':snapshot?'unavailable':'not_queried';
 return '<ds-card class="project-card"><div class="project-head"><div><p class="eyebrow">'+esc(p.domain)+'</p><h3>'+esc(p.name)+'</h3></div><ds-badge variant="'+variant(s)+'">'+(snapshot?label(s):'Aguardando consulta')+'</ds-badge></div><p>'+esc(p.summary)+'</p><p class="repo-count">'+p.repositories.length+' referências de repositório</p><div class="actions"><ds-button variant="secondary" size="sm" data-project="'+p.id+'">Abrir projeto</ds-button></div></ds-card>';
}
function projectDetail(p:Project){
 return '<section><button class="back" data-back>← Voltar aos projetos</button><div class="intro"><div><p class="eyebrow">'+esc(p.domain)+'</p><h2>'+esc(p.name)+'</h2><p>'+esc(p.summary)+'</p></div><ds-badge variant="info">GitHub somente leitura</ds-badge></div><div class="repo-list">'+p.repositories.map(repoMarkup).join('')+'</div></section>';
}
function overview(){
 const currentProjects=projects();const all=[...new Set(currentProjects.flatMap(p=>p.repositories.map(r=>r.fullName)))];
 const ok=all.filter(n=>repoFor(n)?.status==='ok').length,partial=all.filter(n=>repoFor(n)?.status==='partial').length;
 const bad=all.filter(n=>['unavailable','not_found_or_no_access'].includes(repoFor(n)?.status||'')).length;
 return '<section><div class="intro"><div><h2>Visão consolidada do portfólio</h2><p>Estado obtido diretamente das fontes GitHub, sem substituir os registros canônicos.</p></div><ds-badge variant="'+(lastError?'warning':snapshot?'success':'warning')+'">'+(lastError?(snapshot?'Dados anteriores · falha ao atualizar':'Falha de consulta'):snapshot?'Consulta realizada':'Aguardando conexão')+'</ds-badge></div>'+
 (lastError?'<ds-alert variant="warning" title="Integração GitHub">'+esc(lastError)+'</ds-alert>':'')+
 '<div class="metrics"><ds-card><small>Projetos no escopo</small><strong>'+currentProjects.length+'</strong><small>Descoberta automática</small></ds-card><ds-card><small>Repositórios consultados</small><strong>'+(snapshot?ok+'/'+all.length:'—')+'</strong><small>'+partial+' parciais · '+bad+' indisponíveis</small></ds-card><ds-card><small>Última consulta</small><strong class="metric-date">'+(snapshot?date(snapshot.checkedAt):'—')+'</strong><small>'+(snapshot?.cache==='HIT'?'Cache de 60 segundos':'Consulta à API GitHub')+'</small></ds-card><ds-card><small>Modo de acesso</small><strong class="metric-word">Somente leitura</strong><small>Sem ações de escrita</small></ds-card></div>'+
 '<div class="section-head"><div><h2>Projetos acompanhados</h2><p>Estado do Git separado de publicação, instalação e homologação em runtime.</p></div><ds-button variant="secondary" size="sm" data-view="projects">Ver todos</ds-button></div><div class="projects">'+(currentProjects.length?currentProjects.map(projectCard).join(''):'<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório para incluí-lo no portfólio. Depois, use Atualizar GitHub.</p></ds-card>')+'</div>'+
 '<p class="repo-detail">Descoberta: '+(snapshot?.discovery.scannedRepositories??0)+' repositórios examinados; arquivo de identificação '+esc(snapshot?.discovery.file||'.portal-governanca.json')+'.</p>'+(snapshot?.discovery.warnings.length?'<ds-alert variant="warning" title="Avisos na descoberta">'+snapshot.discovery.warnings.map(w=>esc(w.repository+': '+w.message)).join('<br>')+'</ds-alert>':'')+'<div class="section-head"><div><h2>Repositórios de origem</h2><p>Resumo da última leitura, sem executar workflows.</p></div></div><div class="repo-list">'+all.map(n=>repoMarkup({fullName:n,role:'Fonte cadastrada'})).join('')+'</div></section>';
}
function body(){
 if(view==='overview')return overview();
 if(view==='projects'&&selected)return projectDetail(selected);
 if(view==='projects')return '<section><div class="intro"><div><h2>Projetos</h2><p>Projetos identificados automaticamente nos repositórios.</p></div></div><div class="projects">'+(projects().length?projects().map(projectCard).join(''):'<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório e atualize o GitHub.</p></ds-card>')+'</div></section>';
 const pages:Record<string,[string,string,string]>={homologation:['Homologações','Critérios de aceite e evidências por produto, versão e ambiente.','O GitHub informa código, branches, PRs e workflows. Isso não comprova instalação nem homologação no Home Assistant ou execução real no n8n.'],evidence:['Evidências','Origem, horário, SHA/versão, ambiente e responsável.','A consulta GitHub fornece metadados e links. Logs de runtime e evidências operacionais serão integrados em etapa posterior, sem copiar payloads de mensagens.'],environments:['Ambientes','Desenvolvimento, release candidate, Home Assistant e n8n.','GitHub não comprova estado do runtime. Home Assistant e n8n permanecem não consultados nesta fase.'],decisions:['Decisões e histórico','Registros imutáveis por acréscimo, com links às fontes canônicas.','As decisões continuam nas Issues e documentos de origem. O Portal começa por apresentá-las sem criar ou alterar registros.']};
 const [title,desc,text]=pages[view];
 return '<section><div class="intro"><div><h2>'+title+'</h2><p>'+desc+'</p></div><ds-badge variant="warning">Escopo Fase 1</ds-badge></div><ds-card title="'+title+'">'+text+'</ds-card></section>';
}
function render(){
 const status=lastError?(snapshot?'Atualização falhou · dados anteriores':lastErrorCode==='GITHUB_NOT_CONFIGURED'?'GitHub não configurado':'GitHub indisponível'):snapshot?'GitHub consultado':'GitHub não consultado';
 app!.innerHTML='<a class="skip" href="#main">Pular para o conteúdo</a><div class="shell"><aside class="sidebar"><a class="brand" href="#overview"><span class="mark">G</span><span><b>Governança</b><small>PORTFÓLIO · HOMOLOGAÇÃO</small></span></a><p class="nav-label">Acompanhamento</p><nav aria-label="Seções principais">'+nav.map(n=>'<button data-view="'+n.id+'" '+(view===n.id?'aria-current="page"':'')+'>'+n.label+'</button>').join('')+'</nav><div class="side-foot"><ds-badge variant="info">GitHub somente leitura</ds-badge><p>Sem acesso de escrita</p></div></aside><div class="workspace"><header><div><p class="eyebrow">ECOSSISTEMA MMCROMERO</p><h1>'+nav.find(n=>n.id===view)?.label+'</h1></div><div class="header-meta"><ds-badge variant="info">Design System 0.1.0 · desenvolvimento</ds-badge><small>'+esc(status)+' · '+(lastChecked?date(lastChecked):'sem consulta')+'</small><ds-button size="sm" variant="secondary" '+(loading?'disabled':'')+' data-refresh>'+(loading?'Consultando…':'Atualizar GitHub')+'</ds-button></div></header><main id="main" tabindex="-1">'+body()+'</main><footer>Portal de Governança · Fase 1 <span>GitHub read-only · HA/n8n fora desta etapa</span></footer></div></div>';
 app!.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.view as View;selected=null;render();document.querySelector<HTMLElement>('#main')?.focus()}));
 app!.querySelectorAll<HTMLElement>('[data-project]').forEach(b=>b.addEventListener('click',()=>{selected=projects().find(p=>p.id===b.dataset.project)||null;view='projects';render();document.querySelector<HTMLElement>('#main')?.focus()}));
 app!.querySelector<HTMLElement>('[data-back]')?.addEventListener('click',()=>{selected=null;render();document.querySelector<HTMLElement>('#main')?.focus()});
 app!.querySelector<HTMLElement>('[data-refresh]')?.addEventListener('click',()=>void refresh(true));
}
async function refresh(force=false){
 if(loading)return;loading=true;lastError=null;lastErrorCode=null;render();
 try{snapshot=await getPortfolio(force);lastChecked=snapshot.checkedAt;}
 catch(error){lastError=error instanceof Error?error.message:'Falha desconhecida na consulta GitHub';lastErrorCode=(error as {code?:string})?.code||null;}
 finally{loading=false;render();}
}
render();void refresh(false);
