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
export default function AreaNav(props:Parameters<typeof NormalAreaNav>[0]){
 return document.body.classList.contains('pilot-first-access-detail')?null:<NormalAreaNav {...props}/>;
}
function NormalAreaNav({active,attentionHostId}:{attentionHostId?:string;active?:Area|'configuracoes'|'estoque'|'pedidos'|'financeiro'|'vendas'|'ajuda'}){
 const pilot=appName==='Artesão Digital', [host,setHost]=useState<HTMLElement|null>(null),[open,setOpen]=useState(false),toggle=useRef<HTMLButtonElement>(null);
 useEffect(()=>{
  if(!pilot)return;
  const find=()=>{const target=document.getElementById('pilot-navigation');if(target){setHost(target);return true;}return false;};
  if(find())return;
  const observer=new MutationObserver(()=>{if(find())observer.disconnect();});observer.observe(document.body,{childList:true,subtree:true});
  return ()=>observer.disconnect();
 },[pilot]);
 useEffect(()=>{if(!pilot)return;const media=matchMedia('(max-width:700px)'),reset=()=>setOpen(false);media.addEventListener('change',reset);return()=>media.removeEventListener('change',reset);},[pilot]);
 const navigation=pilot?<div className={`pilot-menu${open?' is-open':''}`} onKeyDown={event=>{if(event.key==='Escape'&&open){setOpen(false);toggle.current?.focus();}}}>
  <button ref={toggle} type="button" className="pilot-menu-toggle" aria-expanded={open} aria-controls="pilot-area-links" onClick={()=>setOpen(!open)}><BrandIcon name={open?'close':'menu'}/>{open?'Fechar menu':'Menu'}</button>
  <nav id="pilot-area-links" aria-label="Áreas">{pilotItems.filter(viewEnabled).map(item=><a key={item} href={`?view=${item}`} aria-current={active===item?'page':undefined}><BrandIcon name={item==='vendas'?'store':item}/>{item==='vendas'?'PDV':item==='configuracoes'?'Configurações':item==='ajuda'?'Ajuda':areaNames[item]}</a>)}</nav>
 </div>:<nav aria-label="Áreas">{(Object.keys(areaNames).filter(area=>area!=='estoque'&&area!=='pedidos'&&area!=='financeiro'&&area!=='vendas') as Area[]).map(area=><a key={area} href={`?view=${area}`} aria-current={active===area?'page':undefined} style={{fontWeight:active===area?750:400,marginRight:16}}>{areaNames[area]}</a>)}</nav>;
 return <>{host?createPortal(navigation,host):navigation}{pilot&&<>{active==='vendas'&&<PdvIdentity/>}<AttentionBell hostId={attentionHostId}/></>}</>;
}
export function SettingsLink({area}:{area:Area}){return appName==='Artesão Digital'?null:<a className="area-settings-link" href={`?view=configuracoes&area=${area}`}>Configurações</a>;}
