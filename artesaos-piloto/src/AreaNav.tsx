import {viewEnabled} from './module-access';
import AttentionBell from './AttentionBell';
import {useEffect,useRef,useState} from 'react';
import {createPortal} from 'react-dom';
import {appName} from './branding';
import BrandIcon from './BrandIcon';
import PdvIdentity from './PdvIdentity';
export type Area='fabricacao'|'orcamentos'|'clientes'|'produtos';
export const areaNames:Record<Area|'estoque'|'pedidos'|'financeiro'|'vendas',string>={fabricacao:'Fabricação',orcamentos:'Orçamentos',clientes:'Clientes',produtos:'Produtos',estoque:'Estoque',pedidos:'Pedidos',financeiro:'Financeiro',vendas:'Vendas'};
const pilotItems=['produtos','clientes','orcamentos','pedidos','estoque','vendas','financeiro','configuracoes','ajuda'] as const;
function areaHref(view:string){const url=new URL(location.href);url.searchParams.set('view',view);url.searchParams.delete('area');if(view!=='configuracoes')url.searchParams.delete('settings');url.hash='';return url.pathname+url.search;}
export default function AreaNav({global=false,...props}:Parameters<typeof NormalAreaNav>[0]&{global?:boolean}){
 const pilot=appName==='Artesão Digital';
 if(document.body.classList.contains('pilot-first-access-detail')||(pilot&&!global))return null;
 return <NormalAreaNav {...props}/>;
}
function NormalAreaNav({active,attentionHostId}:{attentionHostId?:string;active?:Area|'configuracoes'|'estoque'|'pedidos'|'financeiro'|'vendas'|'ajuda'}){
 const pilot=appName==='Artesão Digital', [host]=useState<HTMLElement|null>(()=>pilot?document.getElementById('pilot-navigation'):null),[open,setOpen]=useState(false),toggle=useRef<HTMLButtonElement>(null);
 useEffect(()=>{if(!pilot)return;const media=matchMedia('(max-width:700px)'),reset=()=>setOpen(false);media.addEventListener('change',reset);return()=>media.removeEventListener('change',reset);},[pilot]);
 const navigation=pilot?<div className={`pilot-menu${open?' is-open':''}`} onKeyDown={event=>{if(event.key==='Escape'&&open){setOpen(false);toggle.current?.focus();}}}>
  <button ref={toggle} type="button" className="pilot-menu-toggle" aria-expanded={open} aria-controls="pilot-area-links" onClick={()=>setOpen(!open)}><BrandIcon name={open?'close':'menu'}/>{open?'Fechar menu':'Menu'}</button>
  <nav id="pilot-area-links" aria-label="Áreas">{pilotItems.filter(viewEnabled).map(item=><a key={item} href={areaHref(item)} aria-current={active===item?'page':undefined}><BrandIcon name={item==='vendas'?'store':item}/>{item==='vendas'?'PDV':item==='configuracoes'?'Configurações':item==='ajuda'?'Ajuda':areaNames[item]}</a>)}</nav>
 </div>:<nav aria-label="Áreas">{(Object.keys(areaNames).filter(area=>area!=='estoque'&&area!=='pedidos'&&area!=='financeiro'&&area!=='vendas') as Area[]).map(area=><a key={area} href={areaHref(area)} aria-current={active===area?'page':undefined} style={{fontWeight:active===area?750:400,marginRight:16}}>{areaNames[area]}</a>)}</nav>;
 return <>{pilot?(host?createPortal(navigation,host):null):navigation}{pilot&&<>{active==='vendas'&&<PdvIdentity/>}<AttentionBell hostId={attentionHostId}/></>}</>;
}
export function SettingsLink({area}:{area:Area}){return appName==='Artesão Digital'?null:<a className="area-settings-link" href={`?view=configuracoes&area=${area}`}>Configurações</a>;}
