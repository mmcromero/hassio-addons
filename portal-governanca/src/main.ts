import '@mmcromero/ds-tokens/css';
import '@mmcromero/ds-components/styles.css';
import '@mmcromero/ds-components';
import {
  getPortfolio,
  getRepositoryCatalog,
  registerProject,
  getSupervisorInventory,
  getN8nOverview,
  getPortalRecords,
  appendPortalRecord,
  getAgentEvents,
  getMissions,
  createMission,
  getProjectTimeline,
  collectProjectTimeline,
  endProjectTimeline,
  type ProjectTimelineResponse,
  getSystemStatus,
  type PortalLedger,
  type PortfolioSnapshot,
  type RepoSnapshot,
  type Project,
  type RepositoryCatalog,
  type SupervisorInventory,
  type N8nOverview,
  type AgentEvent,
  type AgentEventsResponse,
  type MissionsResponse,
  type SystemStatus
} from './api/client';
import './styles.css';

type View =
  | 'overview'
  | 'agents'
  | 'missions'
  | 'projects'
  | 'register'
  | 'homologation'
  | 'evidence'
  | 'environments'
  | 'decisions'
  | 'automations';

const nav: { id: View; label: string }[] = [
  { id: 'overview', label: 'Visão geral' },
  { id: 'agents', label: 'Centro de comando' },
  { id: 'missions', label: 'Missões' },
  { id: 'projects', label: 'Projetos' },
  { id: 'register', label: 'Cadastrar projeto' },
  { id: 'homologation', label: 'Homologações' },
  { id: 'evidence', label: 'Evidências' },
  { id: 'environments', label: 'Ambientes' },
  { id: 'decisions', label: 'Decisões e histórico' },
  { id: 'automations', label: 'Automações n8n' }
];

const app = document.querySelector<HTMLDivElement>('#app');
if (!app) throw new Error('Elemento #app não encontrado.');

let view: View = 'overview';
let selected: Project | null = null;
let snapshot: PortfolioSnapshot | null = null;
let loading = false;
let lastError: string | null = null;
let lastErrorCode: string | null = null;
let lastChecked: string | null = null;

let catalog: RepositoryCatalog | null = null;
let catalogLoading = false;
let catalogError: string | null = null;
let registering = false;
let registerMessage: string | null = null;
let registerError: string | null = null;

let supervisorSnapshot: SupervisorInventory | null = null;
let supervisorLoading = false;
let supervisorError: string | null = null;

let n8nSnapshot: N8nOverview | null = null;
let n8nLoading = false;
let n8nError: string | null = null;

let ledgerSnapshot: PortalLedger | null = null;
let ledgerLoading = false;
let ledgerError: string | null = null;
let ledgerSaving = false;
let ledgerMessage: string | null = null;

let agentSnapshot: AgentEventsResponse | null = null;
let agentLoading = false;
let agentError: string | null = null;

let missionsSnapshot: MissionsResponse | null = null;
let missionsLoading = false;
let missionsError: string | null = null;
let missionSubmitting = false;
let missionDraft = "";
let missionMessage: string | null = null;
let missionError: string | null = null;

let timelineSnapshot: ProjectTimelineResponse | null = null;
let timelineProjectId: string | null = null;
let timelineLoading = false;
let timelineError: string | null = null;
let timelineServerOffset = 0;

let statusSnapshot: SystemStatus | null = null;
let statusLoading = false;

const projects = () => snapshot?.projects ?? [];
const esc = (s: string) =>
  s.replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c] ?? c));
const date = (v?: string | null) =>
  v ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'short' }).format(new Date(v)) : 'Não informado';

function isStale(isoDate?: string | null, maxHours = 1): boolean {
  if (!isoDate) return true;
  const diffMs = Date.now() - new Date(isoDate).getTime();
  return diffMs > maxHours * 3600 * 1000;
}

function repoFor(name: string): RepoSnapshot | null {
  for (const p of projects()) for (const r of p.repositories) if (r.fullName === name) return r.snapshot ?? null;
  return null;
}

function label(status?: string) {
  return (
    ({
      ok: 'Consultado',
      partial: 'Parcial',
      unavailable: 'Indisponível',
      not_found_or_no_access: 'Não encontrado / sem acesso',
      not_queried: 'Não consultado'
    } as Record<string, string>)[status || ''] || 'Não verificado'
  );
}

function variant(status?: string) {
  return status === 'ok'
    ? 'success'
    : status === 'partial'
    ? 'warning'
    : ['unavailable', 'not_found_or_no_access'].includes(status || '')
    ? 'error'
    : 'neutral';
}

function eventBadge(type: string): { variant: string; label: string } {
  switch (type) {
    case 'inicio':
      return { variant: 'info', label: 'Início' };
    case 'atualizacao':
      return { variant: 'warning', label: 'Atualização' };
    case 'conclusao':
      return { variant: 'success', label: 'Conclusão' };
    case 'impedimento':
      return { variant: 'error', label: 'Impedimento' };
    case 'bastao':
      return { variant: 'neutral', label: 'Passagem de bastão' };
    default:
      return { variant: 'neutral', label: type };
  }
}

function repoMarkup(ref: { fullName: string; role: string; path?: string }) {
  const d = repoFor(ref.fullName);
  if (!d)
    return (
      '<div class="repo-row"><div><strong>' +
      esc(ref.fullName) +
      '</strong><small>' +
      esc(ref.role) +
      (ref.path ? ' · ' + esc(ref.path) : '') +
      '</small></div><ds-badge variant="warning">Aguardando consulta</ds-badge></div>'
    );
  const c = d.latestCommit,
    r = d.latestWorkflowRun,
    rel = d.latestRelease;
  const branches = (d.branches || [])
    .slice(0, 6)
    .map(b => '<span><b>' + esc(b.name) + '</b> ' + esc((b.sha || '').slice(0, 7)) + '</span>')
    .join('');
  const issues = (d.openIssues || [])
    .slice(0, 5)
    .map(i => '<li><a href="' + esc(i.url) + '" target="_blank" rel="noopener noreferrer">#' + i.number + ' ' + esc(i.title) + '</a></li>')
    .join('');
  const pulls = (d.openPulls || [])
    .slice(0, 5)
    .map(p => '<li><a href="' + esc(p.url) + '" target="_blank" rel="noopener noreferrer">#' + p.number + ' ' + esc(p.title) + '</a>' + (p.draft ? ' · rascunho' : '') + '</li>')
    .join('');
  return (
    '<article class="repo-card"><div class="repo-top"><div><a href="' +
    esc(d.htmlUrl || 'https://github.com/' + ref.fullName) +
    '" target="_blank" rel="noopener noreferrer">' +
    esc(ref.fullName) +
    '</a><small>' +
    esc(ref.role) +
    (ref.path ? ' · ' + esc(ref.path) : '') +
    '</small></div><ds-badge variant="' +
    variant(d.status) +
    '">' +
    label(d.status) +
    '</ds-badge></div>' +
    '<div class="repo-facts"><span>Branch padrão: <b>' +
    esc(d.defaultBranch || '—') +
    '</b></span><span>Branches listadas: <b>' +
    (d.branches?.length ?? '—') +
    (d.branchesTruncated ? '+' : '') +
    '</b></span><span>Issues listadas: <b>' +
    (d.openIssues?.length ?? '—') +
    (d.openIssuesTruncated ? '+' : '') +
    '</b></span><span>PRs listados: <b>' +
    (d.openPulls?.length ?? '—') +
    (d.openPullsTruncated ? '+' : '') +
    '</b></span></div>' +
    '<div class="repo-facts"><span>Último commit: <b>' +
    (c ? esc(c.sha.slice(0, 7)) : '—') +
    '</b></span><span>Workflow: <b>' +
    (r ? esc(r.conclusion || r.status) : d.workflowRunState === 'empty' ? 'Nenhuma execução' : 'Não verificado') +
    '</b></span><span>Release estável: <b>' +
    (rel ? '<a href="' + esc(rel.url) + '" target="_blank" rel="noopener noreferrer">' + esc(rel.tag) + '</a>' : d.releaseState === 'empty' ? 'Nenhuma release' : 'Não verificada') +
    '</b></span></div>' +
    (c ? '<p class="repo-detail"><a href="' + esc(c.url) + '" target="_blank" rel="noopener noreferrer">' + esc(c.message) + '</a> · ' + date(c.date) + '</p>' : '') +
    (r ? '<p class="repo-detail">Última execução: <a href="' + esc(r.url) + '" target="_blank" rel="noopener noreferrer">' + esc(r.name || 'Workflow') + '</a> · ' + esc(r.status) + ' / ' + esc(r.conclusion || 'sem conclusão') + ' · ' + date(r.updatedAt) + '</p>' : '') +
    (branches ? '<details class="repo-details"><summary>Branches e SHAs</summary><div class="repo-facts">' + branches + '</div></details>' : '') +
    (issues ? '<details class="repo-details"><summary>Issues abertas (até 5 exibidas)</summary><ul>' + issues + '</ul></details>' : '') +
    (pulls ? '<details class="repo-details"><summary>Pull requests abertos (até 5 exibidos)</summary><ul>' + pulls + '</ul></details>' : '') +
    (d.errors?.length ? '<p class="repo-error">' + d.errors.map(e => esc(e.message)).join(' · ') + '</p>' : '') +
    '</article>'
  );
}

function projectCard(p: Project) {
  const states = p.repositories.map(r => repoFor(r.fullName)?.status);
  const s = states.length && states.every(x => x === 'ok') ? 'ok' : states.some(x => x === 'ok' || x === 'partial') ? 'partial' : snapshot ? 'unavailable' : 'not_queried';
  return (
    '<ds-card class="project-card"><div class="project-head"><div><p class="eyebrow">' +
    esc(p.domain) +
    '</p><h3>' +
    esc(p.name) +
    '</h3></div><ds-badge variant="' +
    variant(s) +
    '">' +
    (snapshot ? label(s) : 'Aguardando consulta') +
    '</ds-badge></div><p>' +
    esc(p.summary) +
    '</p><p class="repo-count">' +
    p.repositories.length +
    ' referências de repositório</p><div class="actions"><ds-button variant="secondary" size="sm" data-project="' +
    p.id +
    '">Abrir projeto</ds-button></div></ds-card>'
  );
}

function timelineDate(value:string):string{return new Intl.DateTimeFormat("pt-BR",{dateStyle:"short",timeStyle:"short",timeZone:"America/Sao_Paulo"}).format(new Date(value))+" BRT";}
function elapsedLabel(start:string,end:string):string{
 const ms=Math.max(0,Date.parse(end)-Date.parse(start));
 const days=Math.floor(ms/86400000),years=Math.floor(days/365.2425),months=Math.floor((days-years*365.2425)/30.436875),remaining=Math.floor(days-years*365.2425-months*30.436875);
 return [years?years+"a":null,months?months+"m":null,remaining+"d"].filter(Boolean).join(" ");
}
function projectTimelineMarkup(p:Project):string{
 const data=timelineProjectId===p.id?timelineSnapshot:null,events=data?.events||[];
 const visibleEvents=events.filter(e=>!["activity_day","collection_cursor","activity_coverage"].includes(e.category));
 const startCandidates=visibleEvents.filter(e=>["project_start","first_issue","first_pull_request"].includes(e.category)).sort((a,b)=>Date.parse(a.occurredAt)-Date.parse(b.occurredAt));
 const startEvent=startCandidates[0]||null;
 const latest=visibleEvents.at(-1)||null;
 const activeDays=events.filter(e=>e.category==="activity_day").reduce((sum,e)=>sum+(e.activeDays||0),0);
 const activeDaysEstimated=events.some(e=>e.category==="activity_coverage"&&e.confidence==="estimated");
 const ended=visibleEvents.find(e=>e.category==="project_end")||null;
 const now=new Date(Date.now()+timelineServerOffset).toISOString(),counterEnd=ended?.occurredAt||now;
 const existence=startEvent?elapsedLabel(startEvent.occurredAt,counterEnd):"Não calculável";
 const lastActivity=events.filter(e=>e.category==="activity_day").at(-1)||visibleEvents.filter(e=>e.category!=="project_end").at(-1)||null;
 const activeSpan=startEvent&&lastActivity?elapsedLabel(startEvent.occurredAt,lastActivity.occurredAt):"Não calculável";
 const since=latest?elapsedLabel(latest.occurredAt,now):"Sem marcos";
 const confidence=(value:string)=>value==="confirmed"?"Confirmado":value==="estimated"?"Estimado":"Desconhecido";
 const confidenceVariant=(value:string)=>value==="confirmed"?"success":value==="estimated"?"warning":"neutral";
 const rows=visibleEvents.slice().sort((a,b)=>Date.parse(b.occurredAt)-Date.parse(a.occurredAt)).map(e=>'<article class="timeline-event"><div class="timeline-date">'+timelineDate(e.occurredAt)+'</div><div class="timeline-content"><div class="timeline-event-head"><strong>'+esc(e.title)+'</strong><ds-badge variant="'+confidenceVariant(e.confidence)+'">'+confidence(e.confidence)+'</ds-badge></div><p>'+esc(e.summary)+'</p><small>'+esc(e.sourceName)+' · '+esc(e.repository||'')+(e.sha?' · SHA '+esc(e.sha.slice(0,7)):'')+'</small>'+(e.sourceUrl?'<p><a href="'+esc(e.sourceUrl)+'" target="_blank" rel="noopener noreferrer">Abrir evidência</a></p>':'')+'</div></article>').join('');
 return '<section class="timeline-section"><div class="section-head"><div><h2>Histórico do projeto</h2><p>Marcos históricos coletados de fontes GitHub e preservados no ledger imutável.</p></div><div class="header-meta"><ds-badge variant="'+(data?.integrity==="valid"?"success":"neutral")+'">'+(data?.integrity==="valid"?"Integridade verificada":"Aguardando coleta")+'</ds-badge><button class="primary-action" data-timeline-refresh '+(timelineLoading?'disabled':'')+'>'+(timelineLoading?'Coletando…':'Atualizar histórico')+'</button>'+(ended?'<ds-badge variant="neutral">Projeto encerrado</ds-badge>':'<button class="primary-action timeline-end-action" data-timeline-end '+(timelineLoading?'disabled':'')+'>Registrar encerramento</button>')+'</div></div>'+
 (timelineError?'<ds-alert variant="warning" title="Histórico indisponível">'+esc(timelineError)+'</ds-alert>':'')+
 '<div class="metrics timeline-metrics"><ds-card><div class="stat-content"><small>Início identificado</small><strong class="metric-date">'+(startEvent?timelineDate(startEvent.occurredAt):'Não confirmado')+'</strong><small>'+(startEvent?confidence(startEvent.confidence):'Sem evidência suficiente')+'</small></div></ds-card><ds-card><div class="stat-content"><small>Tempo de existência</small><strong class="metric-word">'+existence+'</strong><small>'+(ended?'Congelado no encerramento':'Contador atualizado automaticamente')+'</small></div></ds-card><ds-card><div class="stat-content"><small>Período com atividade registrada</small><strong class="metric-word">'+activeSpan+'</strong><small>Entre a primeira e a última evidência</small></div></ds-card><ds-card><div class="stat-content"><small>Dias com commits</small><strong class="metric-word">'+(activeDays?activeDays+' dias':'Não identificado')+'</strong><small>'+(activeDaysEstimated?'Cobertura parcial':'Dias distintos com atividade observada')+'</small></div></ds-card><ds-card><div class="stat-content"><small>Desde o último marco</small><strong class="metric-word">'+since+'</strong><small>'+(latest?timelineDate(latest.occurredAt):'Nenhuma atividade registrada')+'</small></div></ds-card></div>'+
 (visibleEvents.length?'<div class="timeline-list">'+rows+'</div>':'<ds-card><h3>Histórico ainda não coletado</h3><p>Atualize para investigar commits, Issues, Pull Requests, releases e datas de criação dos repositórios vinculados.</p></ds-card>')+
 '<small class="repo-detail">'+(data?.total||0)+' eventos preservados · '+(data?.collection?'Última coleta: '+timelineDate(data.collection.checkedAt):'Coleta ainda não executada')+'</small></section>';
}
async function loadTimeline(projectId:string,force=false){
 if(timelineLoading)return;
 timelineLoading=true;timelineProjectId=projectId;timelineError=null;render();
 try{timelineSnapshot=await collectProjectTimeline(projectId,force);if(timelineSnapshot.serverNow)timelineServerOffset=Date.parse(timelineSnapshot.serverNow)-Date.now();}
 catch(e){timelineError=e instanceof Error?e.message:"Falha ao coletar histórico";try{timelineSnapshot=await getProjectTimeline(projectId);if(timelineSnapshot.serverNow)timelineServerOffset=Date.parse(timelineSnapshot.serverNow)-Date.now();}catch(readError){timelineError=readError instanceof Error?readError.message:timelineError;}}
 finally{timelineLoading=false;render();}
}

function projectDetail(p: Project) {
  return (
    '<section><button class="back" data-back>← Voltar aos projetos</button><div class="intro"><div><p class="eyebrow">' +
    esc(p.domain) +
    '</p><h2>' +
    esc(p.name) +
    '</h2><p>' +
    esc(p.summary) +
    '</p></div><ds-badge variant="info">Cadastro controlado</ds-badge></div>' + projectTimelineMarkup(p) + '<div class="repo-list">' +
    p.repositories.map(repoMarkup).join('') +
    '</div></section>'
  );
}

function integrationsPanel() {
  const gh = statusSnapshot?.github;
  const ha = statusSnapshot?.homeAssistant;
  const n8 = statusSnapshot?.n8n;
  const ag = statusSnapshot?.agentProtocol;

  return (
    '<div class="section-head"><div><h2>Estado das Integrações</h2><p>Monitoramento unificado dos canais da Fábrica de Ideias.</p></div></div>' +
    '<div class="metrics">' +
    '<ds-card><div class="stat-content"><small>GitHub REST API</small><strong>' +
    (gh?.configured ? 'Conectado' : 'Não configurado') +
    '</strong><small>' +
    (snapshot ? date(snapshot.checkedAt) : 'Sem consulta') +
    '</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>Supervisor Bridge</small><strong>' +
    (ha?.bridgeConfigured ? 'Ativo' : 'Offline') +
    '</strong><small>' +
    (supervisorSnapshot ? supervisorSnapshot.total + ' add-ons' : 'Sem inventário') +
    '</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>n8n API</small><strong>' +
    (n8?.configured ? 'Configurado' : 'Pendente') +
    '</strong><small>' +
    (n8nSnapshot?.status === 'ok' ? n8nSnapshot.workflowCount + ' workflows' : 'Read-only') +
    '</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>Protocolo Agentes</small><strong>' +
    (ag?.status === 'active' ? 'Ativo' : 'Aguardando') +
    '</strong><small>' +
    (ag?.totalEvents ?? agentSnapshot?.total ?? 0) +
    ' eventos registrados</small></div></ds-card>' +
    '</div>'
  );
}

function overview() {
  const currentProjects = projects();
  const all = [...new Set(currentProjects.flatMap(p => p.repositories.map(r => r.fullName)))];
  const ok = all.filter(n => repoFor(n)?.status === 'ok').length,
    partial = all.filter(n => repoFor(n)?.status === 'partial').length;
  const bad = all.filter(n => ['unavailable', 'not_found_or_no_access'].includes(repoFor(n)?.status || '')).length;

  return (
    '<section><div class="intro"><div><h2>Centro de Comando da Governança</h2><p>Visão executiva e acompanhamento automatizado do ecossistema Fábrica de Ideias.</p></div><ds-badge variant="' +
    (lastError ? 'warning' : snapshot ? 'success' : 'warning') +
    '">' +
    (lastError ? (snapshot ? 'Dados anteriores · falha ao atualizar' : 'Falha de consulta') : snapshot ? 'Consulta realizada' : 'Aguardando conexão') +
    '</ds-badge></div>' +
    (lastError ? '<ds-alert variant="warning" title="Integração GitHub">' + esc(lastError) + '</ds-alert>' : '') +
    integrationsPanel() +
    '<div class="metrics"><ds-card><div class="metric-content"><small>Projetos no escopo</small><strong>' +
    currentProjects.length +
    '</strong><small>Descoberta automática</small></div></ds-card><ds-card><div class="metric-content"><small>Repositórios consultados</small><strong>' +
    (snapshot ? ok + '/' + all.length : '—') +
    '</strong><small>' +
    partial +
    ' parciais · ' +
    bad +
    ' indisponíveis</small></div></ds-card><ds-card><div class="metric-content"><small>Última consulta</small><strong class="metric-date">' +
    (snapshot ? date(snapshot.checkedAt) : '—') +
    '</strong><small>' +
    (snapshot?.cache === 'HIT' ? 'Cache de 60 segundos' : 'Consulta à API GitHub') +
    '</small></div></ds-card><ds-card><div class="metric-content"><small>Modo de acesso</small><strong class="metric-word">Cadastro restrito</strong><small>Somente marcador de projeto</small></div></ds-card></div>' +
    '<div class="section-head"><div><h2>Projetos acompanhados</h2><p>Estado do Git separado de publicação, instalação e homologação em runtime.</p></div><ds-button variant="secondary" size="sm" data-view="projects">Ver todos</ds-button></div><div class="projects">' +
    (currentProjects.length ? currentProjects.map(projectCard).join('') : '<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório ou use Cadastrar projeto.</p></ds-card>') +
    '</div>' +
    '<p class="repo-detail">Descoberta: ' +
    (snapshot?.discovery.scannedRepositories ?? 0) +
    ' repositórios examinados; arquivo de identificação ' +
    esc(snapshot?.discovery.file || '.portal-governanca.json') +
    '.</p>' +
    (snapshot?.discovery.warnings.length
      ? '<ds-alert variant="warning" title="Avisos na descoberta">' +
        snapshot.discovery.warnings.map(w => esc(w.repository + ': ' + w.message)).join('<br>') +
        '</ds-alert>'
      : '') +
    '<div class="section-head"><div><h2>Repositórios de origem</h2><p>Resumo da última leitura, sem executar workflows.</p></div></div><div class="repo-list">' +
    all.map(n => repoMarkup({ fullName: n, role: 'Fonte cadastrada' })).join('') +
    '</div></section>'
  );
}


function missionStatusInfo(status: string): { label: string; variant: string } {
  const values: Record<string, { label: string; variant: string }> = {
    received: { label: 'Recebida', variant: 'neutral' },
    dispatched: { label: 'Enviada ao Runner', variant: 'info' },
    planning: { label: 'Planejando', variant: 'warning' },
    planned: { label: 'Plano gerado', variant: 'success' },
    partial: { label: 'Plano pronto · testes pendentes', variant: 'warning' },
    blocked: { label: 'Impedida', variant: 'error' },
    cancelled: { label: 'Cancelada', variant: 'neutral' },
    dispatch_blocked: { label: 'Despacho bloqueado', variant: 'error' }
  };
  return values[status] || { label: 'Não verificado', variant: 'neutral' };
}

function missionsPage() {
  const missions = missionsSnapshot?.missions ?? [];
  const rows = missions.map(m => {
    const status = missionStatusInfo(m.missionStatus || 'received');
    const planDetail = m.planStatus
      ? '<p class="repo-detail"><b>Plano:</b> ' + esc(m.planStatus) + ' · Selecionados: ' + esc(String(m.selectedCount ?? 0)) + ' · Reutilizados: ' + esc(String(m.reusedCount ?? 0)) + ' · Omitidos: ' + esc(String(m.omittedCount ?? 0)) + '</p>' +
        '<p class="repo-detail">Testes executados: <b>não</b> · Autorização verificada: <b>não</b> · Próxima ação: ' + esc(m.nextRunnerAction || 'nenhuma') + '</p>' +
        '<p class="repo-detail">Recibo SHA-256: <code>' + esc((m.receiptDigest || '').slice(0, 16)) + '…</code></p>'
      : '';
    const dispatchDetail = (m.executionId
      ? '<p class="repo-detail"><b>Job Runner:</b> <code>' + esc(m.executionId) + '</code> · Estado: ' + esc(m.runnerStatus || 'Não verificado') + '</p>'
      : m.dispatchError
      ? '<p class="repo-detail"><b>Despacho bloqueado:</b> ' + esc(m.dispatchError) + '. O Portal tentará novamente quando a conexão estiver disponível.</p>'
      : '<p class="repo-detail"><b>Despacho:</b> aguardando conexão com o Runner.</p>') + planDetail;
    return (
      '<article class="repo-card"><div class="repo-top"><div><strong>' +
      esc(m.title) +
      '</strong><small>' + date(m.createdAt) + ' · ID <code>' + esc(m.id) + '</code></small></div>' +
      '<ds-badge variant="' + status.variant + '">' + esc(status.label) + '</ds-badge></div>' +
      '<p>' + esc(m.summary) + '</p>' +
      (m.repository ? '<p class="repo-detail">Projeto: <b>' + esc(m.projectId || '') + '</b> · Repositório: <b>' + esc(m.repository) + '</b></p>' : '') +
      dispatchDetail +
      '<details class="repo-details"><summary>Ver prompt cadastrado</summary><pre class="mission-prompt">' + esc(m.prompt) + '</pre></details></article>'
    );
  }).join('');
  return (
    '<section><div class="intro"><div><h2>Cadastrar missão</h2><p>O Portal preserva o prompt integral; o Runner recebe apenas o primeiro trecho (até 900 caracteres) e o hash para planejamento read-only. Nenhum código ou teste do projeto será executado.</p></div>' +
    '<div class="header-meta"><ds-badge variant="info">Planejamento read-only</ds-badge><ds-button variant="secondary" size="sm" data-mission-refresh ' + (missionsLoading ? 'disabled' : '') + '>' + (missionsLoading ? 'Consultando…' : 'Atualizar') + '</ds-button></div></div>' +
    (missionsError ? '<ds-alert variant="warning" title="Falha ao consultar missões">' + esc(missionsError) + '</ds-alert>' : '') +
    (missionMessage ? '<ds-alert variant="' + (missionMessage.includes('despacho está bloqueado') ? 'warning' : 'success') + '" title="Missão registrada">' + esc(missionMessage) + '</ds-alert>' : '') +
    (missionError ? '<ds-alert variant="warning" title="Não foi possível cadastrar">' + esc(missionError) + '</ds-alert>' : '') +
    '<ds-card><form class="registration-form" data-mission-form>' +
    '<label for="mission-project">Projeto compatível com o Runner HA</label>' +
    '<select id="mission-project" name="projectId" required><option value="">Selecione o projeto</option><option value="avisaqui">Avisaqui — mmcromero/pager-virtual</option><option value="artesao_digital">Artesão Digital — mmcromero/fabricacao_e_orcamentos</option></select>' +
    '<label for="mission-prompt">Prompt de ativação</label>' +
    '<textarea id="mission-prompt" name="prompt" rows="12" maxlength="8000" minlength="30" required placeholder="Cole aqui o prompt completo gerado pelo agente.">' + esc(missionDraft) + '</textarea>' +
    '<small>Máximo de 8.000 caracteres. Não inclua senhas, tokens ou chaves de acesso.</small>' +
    '<div class="registration-actions"><button type="submit" class="primary-action" ' + (missionSubmitting ? 'disabled' : '') + '>' + (missionSubmitting ? 'Enviando…' : 'Cadastrar e despachar') + '</button></div>' +
    '</form></ds-card>' +
    '<div class="section-head"><div><h2>Missões cadastradas</h2><p>' + (missionsSnapshot?.total ?? 0) + ' solicitações persistidas.</p></div></div>' +
    (rows ? '<div class="repo-list">' + rows + '</div>' : '<ds-card><p>Nenhuma missão cadastrada.</p></ds-card>') +
    '</section>'
  );
}

function agentsPage() {
  const events = agentSnapshot?.events ?? [];
  const total = agentSnapshot?.total ?? 0;
  const lastUp = agentSnapshot?.lastUpdated;
  const stale = isStale(lastUp);

  const eventRows = events.map(e => {
    const b = eventBadge(e.eventType);
    const delivs = (e.deliverables || []).map(d => '<code>' + esc(d) + '</code>').join(' · ');
    return (
      '<article class="repo-card"><div class="repo-top"><div><strong>' +
      esc(e.title) +
      '</strong><small>' +
      date(e.createdAt) +
      ' · Agente: <b>' +
      esc(e.agentId) +
      '</b> · Tarefa: <b>' +
      esc(e.taskId) +
      '</b> · Projeto: <b>' +
      esc(e.projectId || 'Geral') +
      '</b></small></div><ds-badge variant="' +
      b.variant +
      '">' +
      esc(b.label) +
      '</ds-badge></div>' +
      '<p>' +
      esc(e.summary) +
      '</p>' +
      (delivs ? '<div class="repo-facts"><span>Entregas: ' + delivs + '</span></div>' : '') +
      (e.nextAction ? '<p class="repo-detail"><b>Próxima ação:</b> ' + esc(e.nextAction) + '</p>' : '') +
      '<small class="repo-detail">Event ID: <code>' +
      esc(e.eventId) +
      '</code> · Hash: <code>' +
      esc(e.hash?.slice(0, 16) || '—') +
      '…</code></small></article>'
    );
  });

  return (
    '<section><div class="intro"><div><h2>Centro de Comando — Atividade dos Agentes</h2><p>Relato automatizado do ciclo de vida dos agentes autônomos sem intermediação manual.</p></div>' +
    '<div class="header-meta"><ds-badge variant="' +
    (events.length ? (stale ? 'warning' : 'success') : 'neutral') +
    '">' +
    (events.length ? (stale ? 'Dados obsoletos (> 1h)' : 'Em tempo real') : 'Aguardando dados') +
    '</ds-badge><ds-button variant="secondary" size="sm" data-agent-refresh ' +
    (agentLoading ? 'disabled' : '') +
    '>' +
    (agentLoading ? 'Consultando…' : 'Atualizar eventos') +
    '</ds-button></div></div>' +
    (agentError ? '<ds-alert variant="warning" title="Falha ao consultar eventos">' + esc(agentError) + '</ds-alert>' : '') +
    '<div class="metrics">' +
    '<ds-card><div class="stat-content"><small>Total de eventos</small><strong>' +
    total +
    '</strong><small>No ledger append-only</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>Último evento</small><strong class="metric-date">' +
    (lastUp ? date(lastUp) : 'Nenhum') +
    '</strong><small>' +
    (stale && lastUp ? 'Sem atividade recente' : 'Ativo recentemente') +
    '</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>Protocolo</small><strong class="metric-word">v1.0 Oficial</strong><small>Idempotência via UUID</small></div></ds-card>' +
    '<ds-card><div class="stat-content"><small>Ingestão</small><strong class="metric-word">GitHub + n8n</strong><small>Webhook assíncrono</small></div></ds-card>' +
    '</div>' +
    '<div class="section-head"><div><h2>Eventos recentes dos agentes</h2><p>' +
    events.length +
    ' eventos exibidos ordenados por data decrescente.</p></div></div>' +
    (events.length
      ? '<div class="repo-list">' + eventRows.join('') + '</div>'
      : '<ds-card><h3>Aguardando dados dos agentes</h3><p>Nenhum evento registrado ainda via protocolo. Os agentes reportam automaticamente através de comentários em Issues com a tag <code>&lt;!-- AGENT_PROTOCOL_EVENT --&gt;</code> ou via webhook n8n.</p></ds-card>') +
    '</section>'
  );
}

async function loadCatalog() {
  if (catalogLoading) return;
  catalogLoading = true;
  catalogError = null;
  render();
  try {
    catalog = await getRepositoryCatalog();
  } catch (error) {
    catalogError = error instanceof Error ? error.message : 'Falha ao consultar repositórios.';
    catalog = null;
  } finally {
    catalogLoading = false;
    render();
  }
}

function registrationPage() {
  const repos = catalog?.repositories ?? [];
  const options = repos
    .map(
      r =>
        '<option value="' +
        esc(r.fullName) +
        '" ' +
        (r.markerStatus !== 'available' || r.archived ? 'disabled' : '') +
        '>' +
        esc(r.fullName) +
        ' — ' +
        (r.markerStatus === 'available' && !r.archived
          ? 'Disponível'
          : r.markerStatus === 'registered'
          ? 'Já cadastrado'
          : r.markerStatus === 'disabled'
          ? 'Marcador desativado'
          : r.markerStatus === 'invalid'
          ? 'Marcador inválido'
          : r.archived
          ? 'Arquivado'
          : 'Indisponível') +
        '</option>'
    )
    .join('');
  const list = repos
    .map(
      r =>
        '<div class="repo-row"><div><strong>' +
        esc(r.fullName) +
        '</strong><small>Branch padrão: ' +
        esc(r.defaultBranch) +
        '</small></div><ds-badge variant="' +
        (r.markerStatus === 'registered' ? 'success' : r.markerStatus === 'available' && !r.archived ? 'info' : 'warning') +
        '">' +
        (r.markerStatus === 'registered'
          ? 'Cadastrado'
          : r.markerStatus === 'available' && !r.archived
          ? 'Disponível'
          : r.markerStatus === 'disabled'
          ? 'Desativado'
          : r.markerStatus === 'invalid'
          ? 'Inválido'
          : r.archived
          ? 'Arquivado'
          : 'Indisponível') +
        '</ds-badge></div>'
    )
    .join('');
  return (
    '<section><div class="intro"><div><h2>Cadastrar projeto</h2><p>Escolha um repositório e crie nele o marcador que habilita a descoberta automática.</p></div><ds-badge variant="info">Escrita controlada</ds-badge></div>' +
    (catalogError ? '<ds-alert variant="warning" title="Consulta ao GitHub">' + esc(catalogError) + '</ds-alert>' : '') +
    (registerMessage ? '<ds-alert variant="success" title="Cadastro concluído">' + esc(registerMessage) + '</ds-alert>' : '') +
    (registerError ? '<ds-alert variant="warning" title="Não foi possível cadastrar">' + esc(registerError) + '</ds-alert>' : '') +
    (!catalog?.canRegister ? '<ds-alert variant="warning" title="Cadastro ainda não habilitado">A credencial GitHub de escrita separada não está configurada. A consulta continua somente leitura; nenhuma permissão foi ampliada automaticamente.</ds-alert>' : '') +
    '<ds-card><form class="registration-form" data-register-form>' +
    '<label for="register-repository">Repositório GitHub</label><select id="register-repository" name="repositoryFullName" required><option value="">Selecione um repositório</option>' +
    options +
    '</select>' +
    '<label for="register-id">Identificador do projeto</label><input id="register-id" name="id" required maxlength="64" pattern="[a-z0-9]+(-[a-z0-9]+)*" placeholder="exemplo: portal-governanca">' +
    '<small>Use letras minúsculas, números e hífens. O mesmo ID agrupa vários repositórios.</small>' +
    '<label for="register-name">Nome do projeto</label><input id="register-name" name="name" required maxlength="120" placeholder="Nome que aparecerá no Portal">' +
    '<label for="register-domain">Área / domínio</label><input id="register-domain" name="domain" required maxlength="120" placeholder="Ex.: Produto, Infraestrutura, Governança">' +
    '<label for="register-description">Descrição curta</label><textarea id="register-description" name="description" required maxlength="120" rows="3" placeholder="Explique em uma frase o que é este projeto"></textarea>' +
    '<div class="registration-actions"><button type="submit" class="primary-action" ' +
    (!catalog?.canRegister || registering || !repos.some(r => r.markerStatus === 'available' && !r.archived) ? 'disabled' : '') +
    '>' +
    (registering ? 'Criando marcador…' : 'Criar marcador no GitHub') +
    '</button></div>' +
    '<p class="repo-detail">O arquivo será criado na raiz da branch padrão. Se já existir um marcador, o Portal não o sobrescreverá.</p></form></ds-card>' +
    '<div class="section-head"><div><h2>Repositórios encontrados</h2><p>' +
    repos.length +
    ' repositórios acessíveis no owner mmcromero.</p></div><ds-button variant="secondary" size="sm" data-catalog-refresh ' +
    (catalogLoading ? 'disabled' : '') +
    '>Atualizar lista</ds-button></div>' +
    (catalogLoading ? '<p>Consultando GitHub…</p>' : list ? '<div class="repo-list">' + list + '</div>' : '<ds-card><p>Nenhum repositório disponível para exibição.</p></ds-card>') +
    '</section>'
  );
}

async function submitRegistration(input: { repositoryFullName: string; project: { id: string; name: string; domain: string; description: string } }) {
  if (registering) return;
  registering = true;
  registerMessage = null;
  registerError = null;
  render();
  try {
    const result = await registerProject(input);
    registerMessage = result.repository + ' cadastrado na branch ' + result.branch + '. O marcador ' + result.marker + ' foi criado.';
    catalog = null;
    await refresh(true);
    await loadCatalog();
  } catch (error) {
    registerError = error instanceof Error ? error.message : 'Falha desconhecida ao cadastrar.';
  } finally {
    registering = false;
    render();
  }
}

function environments() {
  const apps = supervisorSnapshot?.apps ?? [];
  const mapped = apps.filter(a => a.projectId),
    updates = apps.filter(a => a.updateAvailable === true),
    stopped = apps.filter(a => a.state !== 'started');
  const rows = apps
    .map(
      a =>
        '<article class="repo-card"><div class="repo-top"><div><strong>' +
        esc(a.name) +
        '</strong><small>' +
        esc(a.slug) +
        (a.projectName ? ' · ' + esc(a.projectName) : ' · Não vinculado ao portfólio') +
        '</small></div><ds-badge variant="' +
        (a.state === 'started' ? 'success' : a.state === 'stopped' ? 'warning' : 'error') +
        '">' +
        esc(a.state) +
        '</ds-badge></div><div class="repo-facts"><span>Instalada: <b>' +
        esc(a.version || '—') +
        '</b></span><span>Disponível: <b>' +
        esc(a.versionLatest || '—') +
        '</b></span><span>Atualização: <b>' +
        (a.updateAvailable === true ? 'Disponível' : a.updateAvailable === false ? 'Não' : 'Não verificada') +
        '</b></span><span>Proteção: <b>' +
        (a.protected === true ? 'Ativa' : a.protected === false ? 'Desativada' : '—') +
        '</b></span></div></article>'
    )
    .join('');
  return (
    '<section><div class="intro"><div><h2>Ambientes Home Assistant</h2><p>Inventário consultado diretamente no Supervisor, sem executar ações nos add-ons.</p></div><ds-button variant="secondary" size="sm" data-ha-refresh ' +
    (supervisorLoading ? 'disabled' : '') +
    '>' +
    (supervisorLoading ? 'Consultando…' : 'Atualizar inventário') +
    '</ds-button></div>' +
    (supervisorError ? '<ds-alert variant="warning" title="Supervisor indisponível">' + esc(supervisorError) + '</ds-alert>' : '') +
    (supervisorSnapshot
      ? '<div class="metrics"><ds-card><div class="metric-content"><small>Apps listados</small><strong>' +
        supervisorSnapshot.total +
        '</strong><small>Instalados + operações pendentes</small></div></ds-card><ds-card><div class="metric-content"><small>Vinculados a projetos</small><strong>' +
        mapped.length +
        '</strong><small>' +
        (supervisorSnapshot.total - mapped.length) +
        ' sem vínculo</small></div></ds-card><ds-card><div class="metric-content"><small>Atualizações disponíveis</small><strong>' +
        updates.length +
        '</strong><small>Sem executar atualização</small></div></ds-card><ds-card><div class="metric-content"><small>Fora de started</small><strong>' +
        stopped.length +
        '</strong><small>Estado diferente de started</small></div></ds-card></div><p class="repo-detail">Fonte: ' +
        esc(supervisorSnapshot.source) +
        ' · Consulta: ' +
        date(supervisorSnapshot.checkedAt) +
        ' · Cache: ' +
        supervisorSnapshot.cache +
        '</p><div class="repo-list">' +
        rows +
        '</div>'
      : '<ds-card><p>O inventário ainda não foi consultado. Use “Atualizar inventário” para buscar os add-ons instalados.</p></ds-card>') +
    '</section>'
  );
}

async function loadSupervisor(force = false) {
  if (supervisorLoading) return;
  supervisorLoading = true;
  supervisorError = null;
  render();
  try {
    supervisorSnapshot = await getSupervisorInventory(force);
  } catch (error) {
    supervisorError = error instanceof Error ? error.message : 'Falha ao consultar Supervisor';
  } finally {
    supervisorLoading = false;
    render();
  }
}

function automations() {
  const workflows = n8nSnapshot?.workflows ?? [],
    executions = n8nSnapshot?.executions ?? [];
  const rows = workflows
    .map(
      w =>
        '<article class="repo-card"><div class="repo-top"><div><strong>' +
        esc(w.name) +
        '</strong><small>ID ' +
        esc(w.id) +
        (w.projectId ? ' · Projeto n8n ' + esc(w.projectId) : ' · Projeto não identificado') +
        '</small></div><ds-badge variant="' +
        (w.active === true ? 'success' : w.active === false ? 'neutral' : 'warning') +
        '">' +
        (w.active === true ? 'Ativo' : w.active === false ? 'Inativo' : 'Não verificado') +
        '</ds-badge></div><div class="repo-facts"><span>Atualizado: <b>' +
        date(w.updatedAt) +
        '</b></span><span>Tags: <b>' +
        esc(w.tags.join(', ') || '—') +
        '</b></span></div></article>'
    )
    .join('');
  const executionRows = executions
    .map(
      e =>
        '<article class="repo-row"><div><strong>' +
        esc(e.workflowName || 'Workflow ' + e.workflowId) +
        '</strong><small>Execução #' +
        esc(e.id) +
        ' · ' +
        esc(e.mode) +
        ' · ' +
        date(e.startedAt) +
        '</small></div><ds-badge variant="' +
        (e.status === 'success' ? 'success' : ['error', 'crashed'].includes(e.status) ? 'error' : ['running', 'waiting', 'new'].includes(e.status) ? 'warning' : 'neutral') +
        '">' +
        esc(e.status) +
        '</ds-badge></article>'
    )
    .join('');
  if (n8nError)
    return (
      '<section><div class="intro"><div><h2>Automações n8n</h2><p>Consulta somente leitura de workflows e execuções.</p></div><ds-button variant="secondary" size="sm" data-n8n-refresh>Consultar novamente</ds-button></div><ds-alert variant="warning" title="Falha na consulta n8n">' +
      esc(n8nError) +
      '</ds-alert></section>'
    );
  if (!n8nSnapshot || n8nSnapshot.status === 'not_configured')
    return (
      '<section><div class="intro"><div><h2>Automações n8n</h2><p>Consulta somente leitura de workflows e execuções.</p></div><ds-badge variant="warning">Não configurado</ds-badge></div><ds-card><h3>Integração n8n ainda não configurada</h3><p>O conector usa URL base e chave de API em opções protegidas do add-on. Nenhuma credencial é solicitada ao navegador.</p></ds-card></section>'
    );
  if (n8nSnapshot.status === 'unavailable')
    return (
      '<section><div class="intro"><div><h2>Automações n8n</h2><p>Consulta somente leitura de workflows e execuções.</p></div><ds-button variant="secondary" size="sm" data-n8n-refresh>Consultar novamente</ds-button></div><ds-alert variant="warning" title="n8n indisponível">' +
      esc(n8nSnapshot.error?.message || 'A consulta não pôde ser concluída.') +
      '</ds-alert></section>'
    );
  return (
    '<section><div class="intro"><div><h2>Automações n8n</h2><p>Dados obtidos pela API pública do n8n; nenhuma execução ou alteração é disparada.</p></div><ds-button variant="secondary" size="sm" data-n8n-refresh ' +
    (n8nLoading ? 'disabled' : '') +
    '>' +
    (n8nLoading ? 'Consultando…' : 'Atualizar inventário') +
    '</ds-button></div>' +
    '<div class="metrics"><ds-card><div class="metric-content"><small>Workflows</small><strong>' +
    n8nSnapshot.workflowCount +
    '</strong><small>Consultados</small></div></ds-card><ds-card><div class="metric-content"><small>Ativos</small><strong>' +
    n8nSnapshot.activeCount +
    '</strong><small>Sem ativar ou desativar</small></div></ds-card><ds-card><div class="metric-content"><small>Inativos</small><strong>' +
    n8nSnapshot.inactiveCount +
    '</strong><small>Sem alterar estado</small></div></ds-card><ds-card><div class="metric-content"><small>Falhas recentes</small><strong>' +
    n8nSnapshot.failedExecutions +
    '</strong><small>Nas execuções listadas</small></div></ds-card></div>' +
    '<p class="repo-detail">Fonte: ' +
    esc(n8nSnapshot.source) +
    ' · Consulta: ' +
    date(n8nSnapshot.checkedAt) +
    ' · Cache: ' +
    (n8nSnapshot.cache || '—') +
    '</p>' +
    '<div class="section-head"><div><h2>Workflows</h2><p>' +
    workflows.length +
    ' listados' +
    (n8nSnapshot.truncated?.workflows ? ' · resultado parcial (limite de páginas)' : '') +
    '</p></div></div>' +
    (rows ? '<div class="repo-list">' + rows + '</div>' : '<ds-card><p>Nenhum workflow retornado.</p></ds-card>') +
    '<div class="section-head"><div><h2>Execuções recentes</h2><p>' +
    executions.length +
    ' registros, sem carregar dados internos das execuções' +
    (n8nSnapshot.truncated?.executions ? ' · resultado parcial (limite de páginas)' : '') +
    '</p></div></div>' +
    (executionRows ? '<div class="repo-list">' + executionRows + '</div>' : '<ds-card><p>Nenhuma execução retornada.</p></ds-card>') +
    '</section>'
  );
}

async function loadN8n(force = false) {
  if (n8nLoading) return;
  n8nLoading = true;
  n8nError = null;
  render();
  try {
    n8nSnapshot = await getN8nOverview(force);
    if (n8nSnapshot.status === 'unavailable') n8nError = n8nSnapshot.error?.message || 'n8n indisponível';
  } catch (error) {
    n8nError = error instanceof Error ? error.message : 'Falha ao consultar n8n';
  } finally {
    n8nLoading = false;
    render();
  }
}

async function loadRecords() {
  if (ledgerLoading) return;
  ledgerLoading = true;
  ledgerError = null;
  render();
  try {
    ledgerSnapshot = await getPortalRecords();
  } catch (e) {
    ledgerError = e instanceof Error ? e.message : 'Falha ao consultar histórico';
  } finally {
    ledgerLoading = false;
    render();
  }
}

async function loadMissions() {
  if (missionsLoading) return;
  missionsLoading = true;
  missionsError = null;
  render();
  try {
    missionsSnapshot = await getMissions();
  } catch (e) {
    missionsError = e instanceof Error ? e.message : 'Falha ao consultar missões';
  } finally {
    missionsLoading = false;
    render();
  }
}

async function submitMission(form: HTMLFormElement) {
  if (missionSubmitting) return;
  const data = new FormData(form);
  missionDraft = String(data.get('prompt') || '');
  missionSubmitting = true;
  missionMessage = null;
  missionError = null;
  missionsError = null;
  render();
  try {
    const projectId = String(data.get('projectId') || '');
    const repository = projectId === 'avisaqui'
      ? 'mmcromero/pager-virtual'
      : projectId === 'artesao_digital'
      ? 'mmcromero/fabricacao_e_orcamentos'
      : '';
    const result = await createMission({ prompt: missionDraft, projectId, repository });
    missionDraft = "";
    missionMessage = result.dispatch.status === 'dispatched'
      ? 'Missão ' + result.mission.id.slice(0, 8) + ' enviada ao Runner para planejamento read-only. Job ' + (result.dispatch.executionId || '').slice(0, 8) + '.'
      : 'Missão ' + result.mission.id.slice(0, 8) + ' registrada, mas o despacho está bloqueado: ' + (result.dispatch.code || 'runner_dispatch_failed') + '.';
  } catch (e) {
    missionError = e instanceof Error ? e.message : 'Falha ao cadastrar missão';
  } finally {
    missionSubmitting = false;
    render();
  }
  if (missionMessage) {
    try {
      missionsSnapshot = await getMissions();
    } catch (e) {
      missionsError = e instanceof Error ? e.message : 'Missão recebida, mas não foi possível atualizar a lista.';
    }
    render();
  }
}

async function loadAgentEvents() {
  if (agentLoading) return;
  agentLoading = true;
  agentError = null;
  render();
  try {
    agentSnapshot = await getAgentEvents({ limit: 100 });
  } catch (e) {
    agentError = e instanceof Error ? e.message : 'Falha ao consultar eventos de agentes';
  } finally {
    agentLoading = false;
    render();
  }
}

async function loadSystemStatus() {
  if (statusLoading) return;
  statusLoading = true;
  try {
    statusSnapshot = await getSystemStatus();
  } catch {
    // Silently fall back to cached state
  } finally {
    statusLoading = false;
    render();
  }
}

async function saveRecord(form: HTMLFormElement) {
  if (ledgerSaving) return;
  ledgerSaving = true;
  ledgerMessage = null;
  ledgerError = null;
  render();
  const d = new FormData(form),
    type = String(d.get('type') || '') as 'homologation' | 'evidence' | 'decision';
  try {
    await appendPortalRecord({
      type,
      title: String(d.get('title') || ''),
      summary: String(d.get('summary') || ''),
      status: String(d.get('status') || ''),
      projectId: String(d.get('projectId') || ''),
      repository: String(d.get('repository') || ''),
      sha: String(d.get('sha') || ''),
      version: String(d.get('version') || ''),
      environment: String(d.get('environment') || ''),
      responsible: String(d.get('responsible') || ''),
      origin: 'Portal',
      evidenceKind: String(d.get('evidenceKind') || 'synthetic'),
      sourceUrl: String(d.get('sourceUrl') || '')
    });
    ledgerMessage = 'Registro acrescentado ao histórico com integridade SHA-256.';
    ledgerSnapshot = await getPortalRecords();
  } catch (e) {
    ledgerError = e instanceof Error ? e.message : 'Falha ao salvar registro';
  } finally {
    ledgerSaving = false;
    render();
  }
}

function recordsPage(type: 'homologation' | 'evidence' | 'decision') {
  const title = type === 'homologation' ? 'Homologações' : type === 'evidence' ? 'Evidências' : 'Decisões e histórico';
  const records = (ledgerSnapshot?.records || []).filter(r => (type === 'decision' ? r.type === 'decision' : r.type === type));
  const statusOptions = ['PASS', 'FAIL', 'NAO_EXECUTADO', 'NAO_VERIFICADO', 'BLOQUEADO', 'INDISPONIVEL']
    .map(x => '<option value="' + x + '">' + x.replaceAll('_', ' ') + '</option>')
    .join('');

  const note =
    '<p class="repo-detail"><b>Nota de automação:</b> Atividades rotineiras dos agentes são registradas automaticamente via protocolo no Centro de Comando. Use este formulário para decisões humanas, homologações manuais, critérios de aceite e aprovações formais.</p>';

  const form =
    '<ds-card><form class="registration-form" data-ledger-form><input type="hidden" name="type" value="' +
    type +
    '">' +
    note +
    '<label for="record-title">Título</label><input id="record-title" name="title" maxlength="160" required placeholder="Ex.: Homologação da release candidate dev.27">' +
    '<label for="record-summary">Descrição / justificativa</label><textarea id="record-summary" name="summary" rows="3" maxlength="2000" required placeholder="Descreva os critérios, escopo e decisão humana realizada"></textarea>' +
    (type === 'homologation' ? '<label for="record-status">Estado</label><select id="record-status" name="status" required>' + statusOptions + '</select>' : '') +
    (type === 'evidence' ? '<label for="record-kind">Tipo de evidência</label><select id="record-kind" name="evidenceKind"><option value="real">Real / operacional</option><option value="synthetic">Sintética / automatizada</option></select>' : '') +
    '<label for="record-project">ID do projeto (opcional)</label><input id="record-project" name="projectId" maxlength="64" placeholder="Ex.: portal-governanca">' +
    '<label for="record-repo">Repositório (opcional)</label><input id="record-repo" name="repository" maxlength="160" placeholder="Ex.: mmcromero/portal-governanca">' +
    '<label for="record-sha">SHA (opcional)</label><input id="record-sha" name="sha" maxlength="64" pattern="[a-fA-F0-9]{7,64}" placeholder="Ex.: 8b23be1">' +
    '<label for="record-version">Versão (opcional)</label><input id="record-version" name="version" maxlength="64" placeholder="Ex.: 0.1.0-dev.27">' +
    '<label for="record-env">Ambiente</label><input id="record-env" name="environment" maxlength="80" placeholder="Ex.: Home Assistant ARM64, Raspberry Pi 4">' +
    '<label for="record-owner">Responsável humano</label><input id="record-owner" name="responsible" maxlength="80" placeholder="Ex.: Proprietário / QA">' +
    '<label for="record-url">Link da fonte (opcional)</label><input id="record-url" name="sourceUrl" type="url" maxlength="500" placeholder="https://...">' +
    '<div class="registration-actions"><button class="primary-action" type="submit" ' +
    (ledgerSaving ? 'disabled' : '') +
    '>' +
    (ledgerSaving ? 'Registrando…' : 'Registrar no histórico') +
    '</button></div><small>Registros são somente acréscimo. Não há edição ou exclusão pela interface.</small></form></ds-card>';

  const list = records
    .map(
      r =>
        '<article class="repo-card"><div class="repo-top"><div><strong>' +
        esc(r.title) +
        '</strong><small>' +
        date(r.createdAt) +
        ' · ' +
        esc(r.responsible || 'Responsável não informado') +
        ' · ' +
        (r.evidenceKind === 'real' ? 'Evidência real' : r.evidenceKind === 'synthetic' ? 'Evidência sintética' : esc(r.type)) +
        '</small></div><ds-badge variant="' +
        (r.status === 'PASS' ? 'success' : r.status === 'FAIL' ? 'error' : 'neutral') +
        '">' +
        esc((r.status || r.type).replaceAll('_', ' ')) +
        '</ds-badge></div><p>' +
        esc(r.summary) +
        '</p><div class="repo-facts"><span>Projeto: <b>' +
        esc(r.projectId || '—') +
        '</b></span><span>Ambiente: <b>' +
        esc(r.environment || '—') +
        '</b></span><span>Versão: <b>' +
        esc(r.version || '—') +
        '</b></span><span>SHA: <b>' +
        esc(r.sha || '—') +
        '</b></span></div><small class="repo-detail">Hash: <code>' +
        esc(r.hash.slice(0, 16)) +
        '…</code> · Anterior: <code>' +
        esc(r.previousHash.slice(0, 16)) +
        '…</code></small>' +
        (r.sourceUrl ? '<p><a href="' + esc(r.sourceUrl) + '" target="_blank" rel="noopener noreferrer">Abrir fonte</a></p>' : '') +
        '</article>'
    )
    .join('');

  return (
    '<section><div class="intro"><div><h2>' +
    title +
    '</h2><p>Registros persistentes em /data, com encadeamento SHA-256 e sem operações de edição/exclusão.</p></div><ds-badge variant="' +
    (ledgerSnapshot?.integrity === 'valid' ? 'success' : 'warning') +
    '">' +
    (ledgerSnapshot?.integrity === 'valid' ? 'Integridade verificada' : 'Aguardando verificação') +
    '</ds-badge></div>' +
    (ledgerError ? '<ds-alert variant="warning" title="Histórico">' + esc(ledgerError) + '</ds-alert>' : '') +
    (ledgerMessage ? '<ds-alert variant="success" title="Registro salvo">' + esc(ledgerMessage) + '</ds-alert>' : '') +
    form +
    '<div class="section-head"><div><h2>Registros</h2><p>' +
    records.length +
    ' exibidos · ' +
    (ledgerSnapshot?.total ?? 0) +
    ' no ledger · últimos 500 disponíveis</p></div><ds-button variant="secondary" size="sm" data-ledger-refresh>Atualizar</ds-button></div>' +
    (list ? '<div class="repo-list">' + list + '</div>' : '<ds-card><p>Nenhum registro deste tipo ainda.</p></ds-card>') +
    '</section>'
  );
}

function body() {
  if (view === 'overview') return overview();
  if (view === 'agents') return agentsPage();
  if (view === 'missions') return missionsPage();
  if (view === 'projects' && selected) return projectDetail(selected);
  if (view === 'projects')
    return (
      '<section><div class="intro"><div><h2>Projetos</h2><p>Projetos identificados automaticamente nos repositórios.</p></div><ds-button data-view="register">Cadastrar projeto</ds-button></div><div class="projects">' +
      (projects().length ? projects().map(projectCard).join('') : '<ds-card><h3>Nenhum projeto identificado</h3><p>Adicione <code>.portal-governanca.json</code> à raiz de um repositório ou use Cadastrar projeto.</p></ds-card>') +
      '</div></section>'
    );
  if (view === 'register') return registrationPage();
  if (view === 'environments') return environments();
  if (view === 'automations') return automations();
  if (view === 'homologation') return recordsPage('homologation');
  if (view === 'evidence') return recordsPage('evidence');
  if (view === 'decisions') return recordsPage('decision');

  return '<section><div class="intro"><div><h2>Não encontrado</h2></div></div></section>';
}

function render() {
  const status = lastError
    ? snapshot
      ? 'Atualização falhou · dados anteriores'
      : lastErrorCode === 'GITHUB_NOT_CONFIGURED'
      ? 'GitHub não configurado'
      : 'GitHub indisponível'
    : snapshot
    ? 'GitHub consultado'
    : 'GitHub não consultado';

  app!.innerHTML =
    '<a class="skip" href="#main">Pular para o conteúdo</a><div class="shell"><aside class="sidebar"><a class="brand" href="#overview"><img class="brand-mark" src="./brand-icon.png" alt="Fábrica de Ideias"><span><b>Governança</b><small>CENTRO DE COMANDO</small></span></a><p class="nav-label">Acompanhamento</p><nav aria-label="Seções principais">' +
    nav.map(n => '<button data-view="' + n.id + '" ' + (view === n.id ? 'aria-current="page"' : '') + '>' + n.label + '</button>').join('') +
    '</nav><div class="side-foot"><ds-badge variant="info">GitHub integrado</ds-badge><p>Protocolo de agentes ativo</p></div></aside><div class="workspace"><header><div><p class="eyebrow">ECOSSISTEMA MMCROMERO</p><h1>' +
    nav.find(n => n.id === view)?.label +
    '</h1></div><div class="header-meta"><ds-badge variant="info">Centro de Comando · v0.1.0</ds-badge><small>' +
    esc(status) +
    ' · ' +
    (lastChecked ? date(lastChecked) : 'sem consulta') +
    '</small><ds-button size="sm" variant="secondary" ' +
    (loading ? 'disabled' : '') +
    ' data-refresh>' +
    (loading ? 'Consultando…' : 'Atualizar GitHub') +
    '</ds-button></div></header><main id="main" tabindex="-1">' +
    body() +
    '</main><footer>Portal de Governança · Centro de Comando e Portfólio <span>GitHub · Ingress · Supervisor · n8n · Protocolo de Agentes</span></footer></div></div>';

  app!.querySelectorAll<HTMLButtonElement>('[data-view]').forEach(b =>
    b.addEventListener('click', () => {
      view = b.dataset.view as View;
      selected = null;
      registerMessage = null;
      registerError = null;
      render();
      document.querySelector<HTMLElement>('#main')?.focus();
      if (view === 'register' && !catalog && !catalogLoading) void loadCatalog();
      if (view === 'environments' && !supervisorSnapshot && !supervisorLoading && !supervisorError) void loadSupervisor(false);
      if (view === 'automations' && !n8nSnapshot && !n8nLoading && !n8nError) void loadN8n(false);
      if (['homologation', 'evidence', 'decisions'].includes(view) && !ledgerSnapshot && !ledgerLoading && !ledgerError) void loadRecords();
      if (view === 'agents' && !agentSnapshot && !agentLoading && !agentError) void loadAgentEvents();
      if (view === 'missions' && !missionsSnapshot && !missionsLoading && !missionsError) void loadMissions();
    })
  );

  app!.querySelectorAll<HTMLElement>('[data-project]').forEach(b =>
    b.addEventListener('click', () => {
      selected = projects().find(p => p.id === b.dataset.project) || null;
      view = 'projects';
      render();
      document.querySelector<HTMLElement>('#main')?.focus();
      if(selected)void loadTimeline(selected.id);
    })
  );

  app!.querySelector<HTMLElement>('[data-back]')?.addEventListener('click', () => {
    selected = null;
    render();
    document.querySelector<HTMLElement>('#main')?.focus();
  });

  app!.querySelector<HTMLElement>('[data-refresh]')?.addEventListener('click', () => void refresh(true));
  app!.querySelector<HTMLElement>('[data-ha-refresh]')?.addEventListener('click', () => void loadSupervisor(true));
  app!.querySelector<HTMLElement>('[data-n8n-refresh]')?.addEventListener('click', () => void loadN8n(true));
  app!.querySelector<HTMLElement>('[data-ledger-refresh]')?.addEventListener('click', () => void loadRecords());
  app!.querySelector<HTMLElement>('[data-timeline-refresh]')?.addEventListener('click', () => { if(selected)void loadTimeline(selected.id,true); });
  app!.querySelector<HTMLElement>('[data-timeline-end]')?.addEventListener('click', async () => {
    if(!selected||!window.confirm('Registrar o encerramento deste projeto? O evento será permanente no histórico e congelará o contador de existência.'))return;
    timelineLoading=true;timelineError=null;render();
    try{timelineSnapshot=await endProjectTimeline(selected.id);if(timelineSnapshot.serverNow)timelineServerOffset=Date.parse(timelineSnapshot.serverNow)-Date.now();}
    catch(error){timelineError=error instanceof Error?error.message:'Não foi possível registrar o encerramento.';}
    finally{timelineLoading=false;render();}
  });
  app!.querySelector<HTMLElement>('[data-agent-refresh]')?.addEventListener('click', () => void loadAgentEvents());
  app!.querySelector<HTMLElement>('[data-mission-refresh]')?.addEventListener('click', () => void loadMissions());

  const missionForm = app!.querySelector<HTMLFormElement>('[data-mission-form]');
  missionForm?.addEventListener('submit', event => {
    event.preventDefault();
    void submitMission(missionForm);
  });

  const ledgerForm = app!.querySelector<HTMLFormElement>('[data-ledger-form]');
  ledgerForm?.addEventListener('submit', event => {
    event.preventDefault();
    void saveRecord(ledgerForm);
  });

  app!.querySelector<HTMLElement>('[data-catalog-refresh]')?.addEventListener('click', () => {
    catalog = null;
    void loadCatalog();
  });

  const form = app!.querySelector<HTMLFormElement>('[data-register-form]');
  form?.addEventListener('submit', event => {
    event.preventDefault();
    const data = new FormData(form!);
    void submitRegistration({
      repositoryFullName: String(data.get('repositoryFullName') || ''),
      project: {
        id: String(data.get('id') || ''),
        name: String(data.get('name') || ''),
        domain: String(data.get('domain') || ''),
        description: String(data.get('description') || '')
      }
    });
  });
}

async function refresh(force = false) {
  if (loading) return;
  loading = true;
  lastError = null;
  lastErrorCode = null;
  render();
  try {
    snapshot = await getPortfolio(force);
    lastChecked = snapshot.checkedAt;
  } catch (error) {
    lastError = error instanceof Error ? error.message : 'Falha desconhecida na consulta GitHub';
    lastErrorCode = (error as { code?: string })?.code || null;
  } finally {
    loading = false;
    render();
  }
}

// Inicialização
render();
void refresh(false);
void loadSystemStatus();
void loadAgentEvents();

// Polling suave de eventos de agentes a cada 60s
setInterval(() => {
  if (!agentLoading) void loadAgentEvents();
}, 60_000);

// Atualiza os contadores temporais sem nova consulta enquanto o detalhe está aberto.
setInterval(() => { if(view==='projects'&&selected&&timelineSnapshot&&timelineProjectId===selected.id&&!timelineLoading)render(); },60_000);
