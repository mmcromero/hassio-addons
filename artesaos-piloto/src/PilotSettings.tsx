import ModuleHeading from './ModuleHeading';
import {moduleEnabled} from './module-access';
import {useEffect,useRef,useState,type MouseEvent,type ReactNode} from 'react';
import OperationalPreferences from './OperationalPreferences';
import CompanyLogo from './CompanyLogo';
import SupportHub from './SupportHub';
import CompanySettings from './CompanySettings';
import AreaNav from './AreaNav';
import Settings from './Settings';
import {PdvColorSettings} from './pdv-theme';
import {resolveSettingsGroup,settingsUrl,type SettingsGroup} from './settings-navigation';
import './settings-navigation.css';

type Group={id:SettingsGroup;title:string;description:string;content:ReactNode};
export default function PilotSettings(){
 const groups:Group[]=[
  {id:'geral',title:'Geral',description:'Dados da empresa e logotipo.',content:<><CompanySettings/><CompanyLogo/></>},
  {id:'preferencias',title:'Preferências',description:'Tela inicial e opções de acesso.',content:<OperationalPreferences/>},
  ...(moduleEnabled('fabricacao')?[{id:'custos' as const,title:'Custos e precificação',description:'Parâmetros de cálculo e planejamento.',content:<><p><a href="?view=fabricacao">Cadastrar produto e calcular preços</a> · <a href="?view=materiais">Gerenciar materiais da fabricação</a></p><p>Parâmetros de cálculo e anotações de planejamento. Despesas mensais estimadas não são contas pagas no Financeiro. Alterar sugestões não substitui preços comerciais já aplicados.</p><Settings area="fabricacao" embedded/></>}]:[]),
  ...(moduleEnabled('vendas')?[{id:'vendas' as const,title:'Vendas e pagamentos',description:'Acesso aos parâmetros das operações de venda.',content:<><PdvColorSettings/><p>Contas, formas de pagamento, taxas e prazos são mantidos no Financeiro. Seus padrões são aplicados às novas operações; pagamentos históricos preservam os valores registrados.</p><p><a href={moduleEnabled('financeiro')?'?view=financeiro&tab=entries#finance-settings':'?view=pagamentos'}>Abrir contas e formas de pagamento</a></p><p><a href="?view=vendas">Cupons, locais e sessões de venda</a></p></>}]:[]),
  ...(moduleEnabled('orcamentos')?[{id:'frete' as const,title:'Orçamentos e frete',description:'Preferências de orçamento e envio.',content:<><Settings area="orcamentos" embedded/><p>Caixas, proteção, dimensões e saldos são gerenciados no Estoque. A estimativa está no orçamento e no pedido; somente confirmar preparo real no pedido consome materiais.</p><a href={moduleEnabled('estoque')?'?view=estoque&section=materiais':'?view=materiais'}>Gerenciar embalagens e materiais de envio</a></>}]:[]),
  ...(moduleEnabled('catalogo')?[{id:'produtos' as const,title:'Produtos',description:'Categorias, importação e lista.',content:<div id="config-products"><Settings area="produtos" embedded/></div>}]:[]),
  ...(moduleEnabled('clientes')?[{id:'clientes' as const,title:'Clientes',description:'Lista e importação.',content:<div id="config-clients"><Settings area="clientes" embedded/></div>}]:[]),
  {id:'materiais',title:'Materiais e estoque',description:'Acesso aos cadastros relacionados.',content:<p><a href={moduleEnabled('estoque')?'?view=estoque&section=materiais':'?view=materiais'}>Materiais, insumos e categorias</a>{moduleEnabled('estoque')&&<> · <a href="?view=estoque">Distribuição em pontos parceiros</a></>}</p>},
  {id:'suporte',title:'Suporte e diagnóstico',description:'Chamados e diagnóstico da instalação.',content:<><div id="config-support"><SupportHub embedded/></div><a href="?view=diagnostico">Abrir diagnóstico da instalação</a></>}
 ];
 const available=groups.map(group=>group.id);
 const [active,setActive]=useState<SettingsGroup|null>(()=>resolveSettingsGroup(new URL(location.href),available));
 const [visited,setVisited]=useState<SettingsGroup[]>(()=>active?[active]:[]);
 const moveFocus=useRef(false);
 const indexTitle=useRef<HTMLHeadingElement>(null);
 const panelTitle=useRef<HTMLHeadingElement>(null);
 const lastIndexLink=useRef<SettingsGroup|null>(null);
 const indexLinks=useRef<Partial<Record<SettingsGroup,HTMLAnchorElement|null>>>({});
 const visit=(group:SettingsGroup|null)=>{
  if(group)setVisited(old=>old.includes(group)?old:[...old,group]);
  setActive(group);
 };
 const select=(event:MouseEvent<HTMLAnchorElement>,group:SettingsGroup|null)=>{
  if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
  event.preventDefault();
  if(group===active)return;
  if(group)lastIndexLink.current=group;
  history.pushState(null,'',settingsUrl(new URL(location.href),group));
  moveFocus.current=true;
  visit(group);
 };
 useEffect(()=>{
  const sync=()=>{moveFocus.current=true;visit(resolveSettingsGroup(new URL(location.href),available));};
  window.addEventListener('popstate',sync);
  window.addEventListener('hashchange',sync);
  return()=>{window.removeEventListener('popstate',sync);window.removeEventListener('hashchange',sync);};
 },[available.join(',')]);
 useEffect(()=>{
  if(!moveFocus.current)return;
  moveFocus.current=false;
  const target=active?panelTitle.current:(lastIndexLink.current?indexLinks.current[lastIndexLink.current]:null)??indexTitle.current;
  target?.focus({preventScroll:true});target?.scrollIntoView({block:'nearest'});
 },[active]);
 const href=(group:SettingsGroup|null)=>settingsUrl(new URL(location.href),group).href;
 return <main className="products-screen pilot-settings ad-module-screen">
  <AreaNav active="configuracoes"/>
  <ModuleHeading headingRef={indexTitle} symbol="configuracoes" title="Configurações" description={!active?'Escolha a categoria que deseja configurar.':undefined}/>
  {!active&&<><nav aria-label="Grupos de configurações" className="settings-index">
   {groups.map(group=><a key={group.id} ref={node=>{indexLinks.current[group.id]=node;}} href={href(group.id)} aria-label={group.title} aria-describedby={"settings-description-"+group.id} onClick={event=>select(event,group.id)}><strong>{group.title}</strong><span id={"settings-description-"+group.id}>{group.description}</span><span aria-hidden="true" className="settings-index-arrow">›</span></a>)}
  </nav></>}
  {active&&<nav className="settings-return" aria-label="Navegação de configurações"><a href={href(null)} onClick={event=>select(event,null)}>‹ Todas as configurações</a></nav>}
  {groups.filter(group=>visited.includes(group.id)||group.id===active).map(group=><section key={group.id} id={'config-'+group.id} className="settings-panel" hidden={active!==group.id}>
   <h2 ref={active===group.id?panelTitle:undefined} tabIndex={-1}>{group.title}</h2>{group.content}
  </section>)}
 </main>;
}
