import '@mmcromero/ds-tokens/css';
import '@mmcromero/ds-components/styles.css';
import '@mmcromero/ds-components';
import {getPortfolio,getRepositoryCatalog,registerProject,getSupervisorInventory,type PortfolioSnapshot,type RepoSnapshot,type Project,type RepositoryCatalog,type SupervisorInventory} from './api/client';
import './styles.css';

type View='overview'|'projects'|'register'|'homologation'|'evidence'|'environments'|'decisions';
const nav:{id:View;label:string}[]=[{id:'overview',label:'Visão geral'},{id:'projects',label:'Projetos'},{id:'register',label:'Cadastrar projeto'},{id:'homologation',label:'Homologações'},{id:'evidence',label:'Evidências'},{id:'environments',label:'Ambientes'},{id:'decisions',label:'Decisões e histórico'}];
const app=document.querySelector<HTMLDivElement>('#app');if(!app)throw new Error('Elemento #app não encontrado.');
let view:View='overview',selected:Project|null=null,snapshot:PortfolioSnapshot|null=null,loading=false,lastError:string|null=null,lastErrorCode:string|null=null,lastChecked:string|null=null;
let catalog:RepositoryCatalog|null=null,catalogLoading=false,catalogError:string|null=null,registering=false,registerMessage:string|null=null,registerError:string|null=null;
let supervisorSnapshot:SupervisorInventory|null=null,supervisorLoading=false,supervisorError:string|null=null;
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
 return '<section><button class="back" data-back>← Voltar aos projetos</button><div class="intro"><div><p class="eyebrow">'+esc(p.domain)+'</p><h2>'+esc(p.name)+'</h2><p>'+esc(p.summary)+'</p></div><ds-badge variant="info">Cadastro controlado</ds-badge></div><div class="repo-list">'+p.repositories.map(repoMarkup).join('')+'</div></section>';
}
function overview(){
 const currentProjects=projects();const all=[...new Set(currentProjects.flatMap(p=>p.repositories.map(r=>r.fullName)))];
 const ok=all.filter(n=>repoFor(n)?.status==='ok').length,partial=all.filter(n=>repoFor(n)?.status==='partial').length;
 const bad=all.filter(n=>['unavailable','not_found_or_no_access'].includes(repoFor(n)?.status||'')).length;
 return '<section><div class="intro"><div><h2>Visão consolidada do portfólio</h2><p>Estado obtido diretamente das fontes GitHub, sem substituir os registros canônicos.</p></div><ds-badge variant="'+(lastError?'warning':snapshot?'success':'warning')+'">'+(lastError?(snapshot?'Dados anteriores · falha ao atualizar':'Falha de consulta'):snapshot?'Consulta realizada':'Aguardando conexão')+'</ds-badge></div>'+
 (lastError?'<ds-alert variant="warning" title="Integração GitHub">'+esc(lastError)+'</ds-alert>':'')+
 '<div class="metrics"><ds-card><div class="metric-content"><small>Projetos no escopo</small><strong>'+currentProjects.length+'</strong><small>Descoberta automática</small></div></ds-card><ds-card><div class="metric-content"><small>Repositórios consultados</small><strong>'+(snapshot?ok+'/'+all.length:'—')+'</strong><small>'+partial+' parciais · '+bad+' indisponíveis</small></div></ds-card><ds-card><div class="metric-content"><small>Última consulta</small><strong class="metric-date">'+(snapshot?date(snapshot.checkedAt):'—')+'</strong><small>'+(snapshot?.cache==='HIT'?'Cache de 60 segundos':'Consulta à API GitHub')+'</small></div></ds-card><ds-card><div class="metric-content"><small>Modo de acesso</small><strong class="metric-word">Cadastro restrito</strong><small>Somente marcador de projeto</small></div></ds-card></div>'+
 '<div class="section-head"><div><h2>Projetos acompanhados</h2><p>Estado do Git separado de publicação, instalação e homologação em runtime.</p></div><ds-button variant="secondary" size="sm" data-view="projects">Ver todos</ds-button></div><div class="projects">'+(currentProjects.length?currentProjects.map(projectCard).join(''):'<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório ou use Cadastrar projeto.</p></ds-card>')+'</div>'+
 '<p class="repo-detail">Descoberta: '+(snapshot?.discovery.scannedRepositories??0)+' repositórios examinados; arquivo de identificação '+esc(snapshot?.discovery.file||'.portal-governanca.json')+'.</p>'+(snapshot?.discovery.warnings.length?'<ds-alert variant="warning" title="Avisos na descoberta">'+snapshot.discovery.warnings.map(w=>esc(w.repository+': '+w.message)).join('<br>')+'</ds-alert>':'')+'<div class="section-head"><div><h2>Repositórios de origem</h2><p>Resumo da última leitura, sem executar workflows.</p></div></div><div class="repo-list">'+all.map(n=>repoMarkup({fullName:n,role:'Fonte cadastrada'})).join('')+'</div></section>';
}

async function loadCatalog(){
 if(catalogLoading)return;catalogLoading=true;catalogError=null;render();
 try{catalog=await getRepositoryCatalog();}
 catch(error){catalogError=error instanceof Error?error.message:"Falha ao consultar repositórios.";catalog=null;}
 finally{catalogLoading=false;render();}
}
function registrationPage(){
 const repos=catalog?.repositories??[];
 const options=repos.map(r=>'<option value="'+esc(r.fullName)+'" '+(r.markerStatus!=="available"||r.archived?'disabled':'')+'>'+esc(r.fullName)+' — '+(r.markerStatus==="available"&&!r.archived?'Disponível':r.markerStatus==="registered"?'Já cadastrado':r.markerStatus==="disabled"?'Marcador desativado':r.markerStatus==="invalid"?'Marcador inválido':r.archived?'Arquivado':'Indisponível')+'</option>').join('');
 const list=repos.map(r=>'<div class="repo-row"><div><strong>'+esc(r.fullName)+'</strong><small>Branch padrão: '+esc(r.defaultBranch)+'</small></div><ds-badge variant="'+(r.markerStatus==="registered"?"success":r.markerStatus==="available"&&!r.archived?"info":"warning")+'">'+(r.markerStatus==="registered"?'Cadastrado':r.markerStatus==="available"&&!r.archived?'Disponível':r.markerStatus==="disabled"?'Desativado':r.markerStatus==="invalid"?'Inválido':r.archived?'Arquivado':'Indisponível')+'</ds-badge></div>').join('');
 return '<section><div class="intro"><div><h2>Cadastrar projeto</h2><p>Escolha um repositório e crie nele o marcador que habilita a descoberta automática.</p></div><ds-badge variant="info">Escrita controlada</ds-badge></div>'+
 (catalogError?'<ds-alert variant="warning" title="Consulta ao GitHub">'+esc(catalogError)+'</ds-alert>':'')+
 (registerMessage?'<ds-alert variant="success" title="Cadastro concluído">'+esc(registerMessage)+'</ds-alert>':'')+
 (registerError?'<ds-alert variant="warning" title="Não foi possível cadastrar">'+esc(registerError)+'</ds-alert>':'')+
 (!catalog?.canRegister?'<ds-alert variant="warning" title="Cadastro ainda não habilitado">A credencial GitHub de escrita separada não está configurada. A consulta continua somente leitura; nenhuma permissão foi ampliada automaticamente.</ds-alert>':'')+
 '<ds-card><form class="registration-form" data-register-form>'+
 '<label for="register-repository">Repositório GitHub</label><select id="register-repository" name="repositoryFullName" required><option value="">Selecione um repositório</option>'+options+'</select>'+
 '<label for="register-id">Identificador do projeto</label><input id="register-id" name="id" required maxlength="64" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="exemplo: portal-governanca">'+
 '<small>Use letras minúsculas, números e hífens. O mesmo ID agrupa vários repositórios.</small>'+
 '<label for="register-name">Nome do projeto</label><input id="register-name" name="name" required maxlength="120" placeholder="Nome que aparecerá no Portal">'+
 '<label for="register-domain">Área / domínio</label><input id="register-domain" name="domain" required maxlength="120" placeholder="Ex.: Produto, Infraestrutura, Governança">'+
 '<label for="register-description">Descrição curta</label><textarea id="register-description" name="description" required maxlength="120" rows="3" placeholder="Explique em uma frase o que é este projeto"></textarea>'+
 '<div class="registration-actions"><button type="submit" class="primary-action" '+(!catalog?.canRegister||registering||!repos.some(r=>r.markerStatus==="available"&&!r.archived)?'disabled':'')+'>'+(registering?'Criando marcador…':'Criar marcador no GitHub')+'</button></div>'+
 '<p class="repo-detail">O arquivo será criado na raiz da branch padrão. Se já existir um marcador, o Portal não o sobrescreverá.</p></form></ds-card>'+
 '<div class="section-head"><div><h2>Repositórios encontrados</h2><p>'+repos.length+' repositórios acessíveis no owner mmcromero.</p></div><ds-button variant="secondary" size="sm" data-catalog-refresh '+(catalogLoading?'disabled':'')+'>Atualizar lista</ds-button></div>'+
 (catalogLoading?'<p>Consultando GitHub…</p>':list?'<div class="repo-list">'+list+'</div>':'<ds-card><p>Nenhum repositório disponível para exibição.</p></ds-card>')+
 '</section>';
}
async function submitRegistration(input:{repositoryFullName:string;project:{id:string;name:string;domain:string;description:string}}){
 if(registering)return;registering=true;registerMessage=null;registerError=null;render();
 try{const result=await registerProject(input);registerMessage=result.repository+" cadastrado na branch "+result.branch+". O marcador "+result.marker+" foi criado.";catalog=null;await refresh(true);await loadCatalog();}
 catch(error){registerError=error instanceof Error?error.message:"Falha desconhecida ao cadastrar.";}
 finally{registering=false;render();}
}

function environments(){
 const apps=supervisorSnapshot?.apps??[];
 const mapped=apps.filter(a=>a.projectId),updates=apps.filter(a=>a.updateAvailable===true),stopped=apps.filter(a=>a.state!=="started");
 const rows=apps.map(a=>'<article class="repo-card"><div class="repo-top"><div><strong>'+esc(a.name)+'</strong><small>'+esc(a.slug)+(a.projectName?' · '+esc(a.projectName):' · Não vinculado ao portfólio')+'</small></div><ds-badge variant="'+(a.state==='started'?'success':a.state==='stopped'?'warning':'error')+'">'+esc(a.state)+'</ds-badge></div><div class="repo-facts"><span>Instalada: <b>'+esc(a.version||'—')+'</b></span><span>Disponível: <b>'+esc(a.versionLatest||'—')+'</b></span><span>Atualização: <b>'+(a.updateAvailable===true?'Disponível':a.updateAvailable===false?'Não':'Não verificada')+'</b></span><span>Proteção: <b>'+(a.protected===true?'Ativa':a.protected===false?'Desativada':'—')+'</b></span></div></article>').join('');
 return '<section><div class="intro"><div><h2>Ambientes Home Assistant</h2><p>Inventário consultado diretamente no Supervisor, sem executar ações nos add-ons.</p></div><ds-button variant="secondary" size="sm" data-ha-refresh '+(supervisorLoading?'disabled':'')+'>'+(supervisorLoading?'Consultando…':'Atualizar inventário')+'</ds-button></div>'+(supervisorError?'<ds-alert variant="warning" title="Supervisor indisponível">'+esc(supervisorError)+'</ds-alert>':'')+(supervisorSnapshot?'<div class="metrics"><ds-card><div class="metric-content"><small>Apps listados</small><strong>'+supervisorSnapshot.total+'</strong><small>Instalados + operações pendentes</small></div></ds-card><ds-card><div class="metric-content"><small>Vinculados a projetos</small><strong>'+mapped.length+'</strong><small>'+(supervisorSnapshot.total-mapped.length)+' sem vínculo</small></div></ds-card><ds-card><div class="metric-content"><small>Atualizações disponíveis</small><strong>'+updates.length+'</strong><small>Sem executar atualização</small></div></ds-card><ds-card><div class="metric-content"><small>Fora de started</small><strong>'+stopped.length+'</strong><small>Estado diferente de started</small></div></ds-card></div><p class="repo-detail">Fonte: '+esc(supervisorSnapshot.source)+' · Consulta: '+date(supervisorSnapshot.checkedAt)+' · Cache: '+supervisorSnapshot.cache+'</p><div class="repo-list">'+rows+'</div>':'<ds-card><p>O inventário ainda não foi consultado. Use “Atualizar inventário” para buscar os add-ons instalados.</p></ds-card>')+'</section>';
}
async function loadSupervisor(force=false){if(supervisorLoading)return;supervisorLoading=true;supervisorError=null;render();try{supervisorSnapshot=await getSupervisorInventory(force);}catch(error){supervisorError=error instanceof Error?error.message:'Falha ao consultar Supervisor';}finally{supervisorLoading=false;render();}}
function body(){
 if(view==='overview')return overview();
 if(view==='projects'&&selected)return projectDetail(selected);
 if(view==='projects')return '<section><div class="intro"><div><h2>Projetos</h2><p>Projetos identificados automaticamente nos repositórios.</p></div><ds-button data-view="register">Cadastrar projeto</ds-button></div><div class="projects">'+(projects().length?projects().map(projectCard).join(''):'<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório ou use Cadastrar projeto.</p></ds-card>')+'</div></section>';
 if(view==='register')return registrationPage();
 if(view==='environments')return environments();
 const pages:Record<string,[string,string,string]>={homologation:['Homologações','Critérios de aceite e evidências por produto, versão e ambiente.','O GitHub informa código, branches, PRs e workflows. Isso não comprova instalação nem homologação no Home Assistant ou execução real no n8n.'],evidence:['Evidências','Origem, horário, SHA/versão, ambiente e responsável.','A consulta GitHub fornece metadados e links. Logs de runtime e evidências operacionais serão integrados em etapa posterior, sem copiar payloads de mensagens.'],decisions:['Decisões e histórico','Registros imutáveis por acréscimo, com links às fontes canônicas.','As decisões continuam nas Issues e documentos de origem. O Portal começa por apresentá-las sem criar ou alterar registros.']};
 const [title,desc,text]=pages[view];
 return '<section><div class="intro"><div><h2>'+title+'</h2><p>'+desc+'</p></div><ds-badge variant="warning">Escopo Fase 1</ds-badge></div><ds-card title="'+title+'">'+text+'</ds-card></section>';
}
function render(){
 const status=lastError?(snapshot?'Atualização falhou · dados anteriores':lastErrorCode==='GITHUB_NOT_CONFIGURED'?'GitHub não configurado':'GitHub indisponível'):snapshot?'GitHub consultado':'GitHub não consultado';
 app!.innerHTML='<a class="skip" href="#main">Pular para o conteúdo</a><div class="shell"><aside class="sidebar"><a class="brand" href="#overview"><img class="brand-mark" src="./brand-icon.png" alt="Fábrica de Ideias"><span><b>Governança</b><small>PORTFÓLIO · HOMOLOGAÇÃO</small></span></a><p class="nav-label">Acompanhamento</p><nav aria-label="Seções principais">'+nav.map(n=>'<button data-view="'+n.id+'" '+(view===n.id?'aria-current="page"':'')+'>'+n.label+'</button>').join('')+'</nav><div class="side-foot"><ds-badge variant="info">GitHub integrado</ds-badge><p>Escrita restrita ao cadastro</p></div></aside><div class="workspace"><header><div><p class="eyebrow">ECOSSISTEMA MMCROMERO</p><h1>'+nav.find(n=>n.id===view)?.label+'</h1></div><div class="header-meta"><ds-badge variant="info">Design System 0.1.0 · desenvolvimento</ds-badge><small>'+esc(status)+' · '+(lastChecked?date(lastChecked):'sem consulta')+'</small><ds-button size="sm" variant="secondary" '+(loading?'disabled':'')+' data-refresh>'+(loading?'Consultando…':'Atualizar GitHub')+'</ds-button></div></header><main id="main" tabindex="-1">'+body()+'</main><footer>Portal de Governança · Portfólio e Ambientes <span>GitHub · leitura e cadastro restrito · Supervisor somente leitura · n8n na Fase 4</span></footer></div></div>';
 app!.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b=>b.addEventListener('click',()=>{view=b.dataset.view as View;selected=null;registerMessage=null;registerError=null;render();document.querySelector<HTMLElement>('#main')?.focus();if(view==='register'&&!catalog&&!catalogLoading)void loadCatalog();if(view==='environments'&&!supervisorSnapshot&&!supervisorLoading&&!supervisorError)void loadSupervisor(false);}));
 app!.querySelectorAll<HTMLElement>('[data-project]').forEach(b=>b.addEventListener('click',()=>{selected=projects().find(p=>p.id===b.dataset.project)||null;view='projects';render();document.querySelector<HTMLElement>('#main')?.focus()}));
 app!.querySelector<HTMLElement>('[data-back]')?.addEventListener('click',()=>{selected=null;render();document.querySelector<HTMLElement>('#main')?.focus()});
 app!.querySelector<HTMLElement>('[data-refresh]')?.addEventListener('click',()=>void refresh(true));
 app!.querySelector<HTMLElement>('[data-ha-refresh]')?.addEventListener('click',()=>void loadSupervisor(true));
 app!.querySelector<HTMLElement>('[data-catalog-refresh]')?.addEventListener('click',()=>{catalog=null;void loadCatalog();});
 const form=app!.querySelector<HTMLFormElement>('[data-register-form]');
 form?.addEventListener('submit',event=>{event.preventDefault();const data=new FormData(form!);void submitRegistration({repositoryFullName:String(data.get('repositoryFullName')||''),project:{id:String(data.get('id')||''),name:String(data.get('name')||''),domain:String(data.get('domain')||''),description:String(data.get('description')||'')}});});
}
async function refresh(force=false){
 if(loading)return;loading=true;lastError=null;lastErrorCode=null;render();
 try{snapshot=await getPortfolio(force);lastChecked=snapshot.checkedAt;}
 catch(error){lastError=error instanceof Error?error.message:'Falha desconhecida na consulta GitHub';lastErrorCode=(error as {code?:string})?.code||null;}
 finally{loading=false;render();}
}
render();void refresh(false);
