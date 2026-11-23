import {showValidation,RequiredMark} from './FormValidation';
import {useEffect,useRef,useState} from 'react';
type Tier='wholesale'|'factory'|'retail';
type Entry={id:number;name:string;prices:Record<Tier,number|null>};
type Props={catalog:Entry[];selected:number[];setSelected:(ids:number[])=>void;choices:Record<number,Tier|''>;setChoices:(choices:Record<number,Tier|''>)=>void;onAdd:()=>boolean;busy:boolean};
const tiers:Tier[]=['wholesale','factory','retail'];
const labels:Record<Tier,string>={wholesale:'Atacado',factory:'Loja de fábrica',retail:'Varejo'};
const money=(value:number)=>(value/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'});
export default function CatalogPicker({catalog,selected,setSelected,choices,setChoices,onAdd,busy}:Props){
 const [open,setOpen]=useState(false),[search,setSearch]=useState(''),[feedback,setFeedback]=useState(''),[space,setSpace]=useState({height:420,above:false,top:0,left:0,width:320});
 const root=useRef<HTMLDivElement>(null),trigger=useRef<HTMLButtonElement>(null),filter=useRef<HTMLInputElement>(null);
 function close(focus=false){setOpen(false);if(focus)trigger.current?.focus();}
 useEffect(()=>{
  if(!open)return;
  function position(){
   const rect=trigger.current?.getBoundingClientRect();if(!rect)return;
   const boundary=trigger.current?.closest('.quote-modal-body')?.getBoundingClientRect();
   if(boundary&&(rect.bottom<boundary.top||rect.top>boundary.bottom)){setOpen(false);return;}
   const below=window.innerHeight-rect.bottom-12,above=rect.top-12,isAbove=below<240&&above>below,width=Math.min(rect.width,window.innerWidth-16);
   const next={above:isAbove,height:Math.max(100,Math.min(440,isAbove?above:below)),top:isAbove?rect.top-6:rect.bottom+6,left:Math.max(8,Math.min(rect.left,window.innerWidth-width-8)),width};
   setSpace(previous=>JSON.stringify(previous)===JSON.stringify(next)?previous:next);
  }
  function outside(e:PointerEvent){if(!root.current?.contains(e.target as Node))setOpen(false);}
  position();filter.current?.focus();document.addEventListener('pointerdown',outside);window.addEventListener('resize',position);window.addEventListener('scroll',position,true);
  return()=>{document.removeEventListener('pointerdown',outside);window.removeEventListener('resize',position);window.removeEventListener('scroll',position,true);};
 },[open]);
 const visible=catalog.filter(p=>p.name.toLocaleLowerCase().includes(search.toLocaleLowerCase()));
 return <div ref={root} className="quote-catalog" onKeyDown={e=>{if(open&&e.key==='Escape'){e.preventDefault();e.stopPropagation();close(true);}}} onBlur={e=>{if(e.relatedTarget&&!e.currentTarget.contains(e.relatedTarget as Node))close();}}>
 <button ref={trigger} type="button" className="quote-catalog-toggle" aria-haspopup="dialog" aria-expanded={open} aria-controls={open?'quote-catalog-panel':undefined} disabled={busy} onClick={()=>{if(!open){setSearch('');setFeedback('');}setOpen(!open);}}>Selecionar produtos do catálogo <span aria-hidden="true">{open?'▴':'▾'}</span></button>
 {open&&<div id="quote-catalog-panel" className={`quote-catalog-panel${space.above?' quote-catalog-above':''}`} style={{maxHeight:space.height,top:space.top,left:space.left,width:space.width}} role="dialog" aria-label="Produtos do catálogo">
 <div className="quote-catalog-filter"><label htmlFor="quote-catalog-filter">Filtrar produtos</label><input ref={filter} id="quote-catalog-filter" value={search} onChange={e=>setSearch(e.target.value)} onKeyDown={e=>{if(e.key==='ArrowDown'){e.preventDefault();root.current?.querySelector<HTMLInputElement>('.quote-catalog-list input[type=checkbox]')?.focus();}}}/></div>
 <div className="quote-catalog-list" role="group" aria-label="Lista de produtos do catálogo">{!visible.length&&<p>Nenhum produto encontrado.</p>}{visible.map(p=>{const options=tiers.filter(k=>p.prices[k]!==null);return <div key={p.id} className="quote-catalog-option"><label><input type="checkbox" checked={selected.includes(p.id)} onChange={e=>setSelected(e.target.checked?[...selected,p.id]:selected.filter(id=>id!==p.id))}/>{p.name}</label>{selected.includes(p.id)&&(options.length===1?<p>Preço automático: {labels[options[0]]} — {money(p.prices[options[0]]!)}</p>:<label>Preço para {p.name}<RequiredMark/><select aria-required="true" data-required-for="add" aria-label={`Preço para ${p.name}`} value={choices[p.id]??''} onChange={e=>setChoices({...choices,[p.id]:e.target.value as Tier})}><option value="">Escolha o preço</option>{options.map(k=><option key={k} value={k}>{labels[k]} — {money(p.prices[k]!)}</option>)}</select></label>)}</div>;})}</div>
 <div className="quote-catalog-footer">{feedback&&<p role="alert">{feedback}</p>}<button type="button" disabled={busy||!selected.length} onClick={()=>{if(onAdd())close(true);else {const missing=Array.from(root.current!.querySelectorAll<HTMLSelectElement>('select')).find(control=>!control.value);if(missing)showValidation(root.current!,[{element:missing,message:'Escolha o preço deste produto antes de adicionar.'}]);else setFeedback('Confira a escolha de preço de cada produto selecionado.');}}}>Adicionar selecionados ({selected.length})</button><button type="button" onClick={()=>close(true)}>Fechar lista</button></div>
 </div>}
 </div>;
}
