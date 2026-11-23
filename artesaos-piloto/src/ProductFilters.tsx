import ValidatedForm from './FormValidation';
import {useId,useRef,useState,type ReactNode} from 'react';

type Filters={origin:string;category:string};
type Props={search:string;onSearch:(value:string)=>void;value:Filters;onChange:(value:Filters)=>void;categories:string[];total:number;batchAction?:ReactNode;onOpenFilters?:()=>void};
const originLabel=(value:string)=>value==='own'?'Próprios':'De cliente';
const categoryLabel=(value:string)=>value==='__pending__'?'Categoria pendente':value;

export default function ProductFilters({search,onSearch,value,onChange,categories,total,batchAction,onOpenFilters}:Props){
 const dialog=useRef<HTMLDialogElement>(null);
 const headingId=useId();
 const [draft,setDraft]=useState(value);
 const active=Number(!!value.origin)+Number(!!value.category);
 function controls(current:Filters,change:(next:Filters)=>void){return <>
  <label>Origem<select aria-label="Origem" value={current.origin} onChange={event=>change({...current,origin:event.target.value})}><option value="">Todas as origens</option><option value="own">Próprios</option><option value="client">De cliente</option></select></label>
  <label>Categoria<select aria-label="Categoria" value={current.category} onChange={event=>change({...current,category:event.target.value})}><option value="">Todas as categorias</option><option value="__pending__">Categoria pendente</option>{categories.map(path=><option key={path} value={path}>{path}</option>)}</select></label>
 </>;}
 return <div className="product-filters">
  <div className="product-filter-toolbar">
   <label className="product-filter-search">Buscar produtos<input type="search" value={search} onChange={event=>onSearch(event.target.value)} placeholder="Nome ou código/SKU"/></label>
   <div className="product-filter-desktop">{controls(value,onChange)}</div>
   <div className="product-filter-actions"><button type="button" className="product-filter-toggle" aria-haspopup="dialog" onClick={()=>{onOpenFilters?.();setDraft(value);dialog.current?.showModal();}}>Filtros{active>0?` (${active})`:''}</button>{batchAction}</div>
  </div>
  <div className="product-filter-status">
   <span role="status">{total} {total===1?'produto encontrado':'produtos encontrados'}</span>
   <div className="product-filter-chips" role="group" aria-label="Filtros ativos">
    {search&&<button type="button" aria-label="Remover busca" onClick={()=>onSearch('')}>Busca: {search}<span aria-hidden="true"> ×</span></button>}
    {value.origin&&<button type="button" aria-label="Remover filtro de origem" onClick={()=>onChange({...value,origin:''})}>{originLabel(value.origin)}<span aria-hidden="true"> ×</span></button>}
    {value.category&&<button type="button" aria-label="Remover filtro de categoria" onClick={()=>onChange({...value,category:''})}>{categoryLabel(value.category)}<span aria-hidden="true"> ×</span></button>}
   </div>
   {(search||active>0)&&<button type="button" className="product-filter-clear" onClick={()=>{onSearch('');onChange({origin:'',category:''});}}>Limpar filtros</button>}
  </div>
  <dialog ref={dialog} className="product-filter-dialog" aria-labelledby={headingId}>
   <ValidatedForm onSubmit={event=>{event.preventDefault();onChange(draft);dialog.current?.close();}}>
    <h2 id={headingId}>Filtrar produtos</h2>
    {controls(draft,setDraft)}
    <div className="product-filter-dialog-actions"><button type="submit">Aplicar filtros</button><button type="button" onClick={()=>dialog.current?.close()}>Cancelar</button><button type="button" onClick={()=>setDraft({origin:'',category:''})}>Limpar opções</button></div>
   </ValidatedForm>
  </dialog>
 </div>;
}
