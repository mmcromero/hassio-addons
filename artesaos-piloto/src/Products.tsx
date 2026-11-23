import {moduleEnabled} from './module-access';
import OfflinePanel from './OfflinePanel';
import type {LocalCatalog} from './offline-storage';
import ActionButton from './ActionButton';
import ManufactureDialog from './ManufactureDialog';
import BrandIcon from './BrandIcon';
import ModuleHeading from './ModuleHeading';
import MaterialUpgradeNotice from './MaterialUpgradeNotice';
import {appName} from './branding';
import ProductFilters from './ProductFilters';
import ProductForm,{ProductPhoto,emptyProduct,type EditableProduct} from './ProductForm';
import RecordActions,{archiveRecord} from './RecordActions';
import ListPagination,{pageSizes,searchProducts} from './ListPagination';
import ModalClose from './ModalClose';
import ListRowActions from './ListRowActions';
import ListHeading from './ListHeading';
import './products.css';
import {productCategory} from './product-category';
import AreaNav,{SettingsLink} from './AreaNav';
import React, {useEffect,useState,useRef} from 'react';
type Product=EditableProduct&{archived?:boolean};
async function api(path:string,method='GET',body?:unknown,expectedUpdatedAt?:string){const r=await fetch(new URL(path,document.baseURI),{method,headers:{'Content-Type':'application/json',...(expectedUpdatedAt?{'X-Expected-Updated-At':expectedUpdatedAt}:{})},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.message||'Não foi possível concluir.');return data;}
export default function Products({offlineCatalog}:{offlineCatalog?:LocalCatalog}){
 const readOnly=!!offlineCatalog;const [showArchived,setShowArchived]=useState(false);
 const [fabricate,setFabricate]=useState<number|null>(null);
 const [batchSelection,setBatchSelection]=useState<number[]>([]);
 const [batchExpanded,setBatchExpanded]=useState(false);
 const [products,setProducts]=useState<Product[]>(offlineCatalog?.products??[]),[edit,setEdit]=useState<Product|null>(null),[message,setMessage]=useState(offlineCatalog?'Cópia local preparada — somente consulta.':'Carregando…'),[busy,setBusy]=useState(false);
 const [formDirty,setFormDirty]=useState(false);
 const [filter,setFilter]=useState(''),[categoryFilter,setCategoryFilter]=useState(''),[categories,setCategories]=useState<{path:string}[]>(offlineCatalog?.categories??[]);
 useEffect(()=>{if(readOnly)return;api('api/categories').then(setCategories).catch(e=>setMessage(e.message));},[]);
 const [search,setSearch]=useState(''),[page,setPage]=useState(1),[pageSize,setPageSize]=useState('10');
 const trigger=useRef<HTMLElement|null>(null);
 function openProduct(product?:Product){trigger.current=document.activeElement as HTMLElement;const value=product?structuredClone(product):emptyProduct();setFormDirty(false);setEdit(value);}
 function closeProduct(force=false){if(!force&&(busy||(formDirty&&!confirm('Descartar as alterações não salvas deste produto?'))))return;dialog.current?.close();setEdit(null);trigger.current?.focus({preventScroll:true});}
 useEffect(()=>{if(readOnly)return;api('api/settings/produtos').then(r=>setPageSize(pageSizes.includes(r.data.productsPerPage)?r.data.productsPerPage:'10')).catch(e=>setMessage(e.message));},[]);
 const filtered=searchProducts(products.filter(p=>(!p.archived||showArchived)&&(!filter||p.origin===filter)&&(categoryFilter===''||(categoryFilter==='__pending__'?!productCategory(p):productCategory(p)===categoryFilter))),search);
 const size=pageSize==='all'?Math.max(1,filtered.length):Number(pageSize),pages=Math.max(1,Math.ceil(filtered.length/size)),currentPage=Math.min(page,pages);
 const visible=filtered.slice((currentPage-1)*size,currentPage*size);
 const dialog=useRef<HTMLDialogElement>(null);
 useEffect(()=>{if(edit && dialog.current && !dialog.current.open)dialog.current.showModal();},[edit]);
 const load=async()=>{const [list,cats]=await Promise.all([api('api/products'),api('api/categories')]);setProducts(list);setCategories(cats);};
 useEffect(()=>{if(readOnly)return;load().then(()=>setMessage('Catálogo persistente.')).catch(e=>setMessage(e.message));},[]);
 async function run(work:()=>Promise<void>){setBusy(true);try{await work();}catch(e){setMessage(e instanceof Error?e.message:'Falha na operação.');}finally{setBusy(false);}}
 return <main className={appName==='Artesão Digital'?'products-screen ad-module-screen':'products-screen'}><header><span className="brand">{appName}</span></header><>{readOnly?<nav aria-label="Áreas">Produtos — consulta offline</nav>:<AreaNav active="produtos"/>}</>
 {appName==='Artesão Digital'?<ModuleHeading symbol="produtos" title="Produtos" description={appName==='Artesão Digital'?'Organize o catálogo, os preços, o estoque e a origem dos seus produtos.':'Cadastro salvo no banco desta instalação e disponível na área Orçamentos.'} action={<ActionButton disabled={busy||readOnly} onClick={()=>openProduct()}>{appName==='Artesão Digital'&&<BrandIcon name="plus"/>}Novo produto</ActionButton>}/>:<><h1>Produtos</h1><p>Cadastro salvo no banco desta instalação e disponível na área Orçamentos.</p><ActionButton disabled={busy||readOnly} onClick={()=>openProduct()}>Novo produto</ActionButton></>}{!readOnly&&<SettingsLink area="produtos"/>}{appName==='Artesão Digital'&&moduleEnabled('fabricacao')&&!readOnly&&<MaterialUpgradeNotice/>}{readOnly&&<label><input type="checkbox" checked={showArchived} onChange={e=>{setShowArchived(e.target.checked);setPage(1);}}/>Mostrar produtos arquivados</label>}<p role="status">{message}</p>
 <section><h2>Catálogo ({filtered.length})</h2><ProductFilters search={search} onSearch={value=>{setSearch(value);setPage(1);}} value={{origin:filter,category:categoryFilter}} onChange={value=>{setFilter(value.origin);setCategoryFilter(value.category);setPage(1);}} categories={Array.from(new Set([...categories.map(c=>c.path),...products.map(productCategory).filter(Boolean)])).sort((a,b)=>a.localeCompare(b,'pt-BR'))} total={filtered.length} batchAction={appName==='Artesão Digital'&&!readOnly?<button type="button" className="product-batch-toggle" aria-expanded={batchExpanded} aria-controls="product-batch-actions" onClick={()=>setBatchExpanded(value=>!value)}>Ações em lote</button>:undefined} onOpenFilters={()=>setBatchExpanded(false)}/><div id="product-batch-actions" hidden={appName==='Artesão Digital'&&!batchExpanded}>{!readOnly&&<RecordActions expanded={appName==='Artesão Digital'?batchExpanded:undefined} onExpandedChange={setBatchExpanded} selection={{ids:batchSelection,setIds:setBatchSelection}} kind="products" rows={filtered as {id:number;updatedAt:string;name:string}[]} visible={visible as {id:number;updatedAt:string;name:string}[]} onDone={load} disabled={busy||readOnly}/>}</div><ListHeading kind="products" selection={batchExpanded}/>{!filtered.length&&<p>Nenhum produto encontrado.</p>}{visible.map(p=><article key={p.id} className={`data-list-row products-list-row${batchExpanded?' has-selection':''}`}>
 {batchExpanded&&<label className="list-selection"><input type="checkbox" aria-label={`Selecionar ${p.name}`} checked={batchSelection.includes(p.id!)} onChange={e=>setBatchSelection(previous=>e.target.checked?[...previous,p.id!]:previous.filter(id=>id!==p.id))}/></label>}
 <div className="product-list-identity"><div className="product-list-photo">{p.imageUrl?<ProductPhoto url={p.imageUrl} name={p.name} offlineCatalog={offlineCatalog}/>:<span className="product-photo-empty">Sem foto</span>}</div>
 <div className="product-list-details"><h3 className="record-title">{p.name}</h3>{p.archived&&<p>Arquivado</p>}{p.sku&&<p>SKU: {p.sku}</p>}{appName==='Artesão Digital'&&moduleEnabled('fabricacao')&&p.origin==='own'&&<ActionButton disabled={busy||readOnly} onClick={()=>setFabricate(p.id!)}>Fabricar</ActionButton>}{(['wholesale','factory','retail'] as const).map(key=><p key={key}>{({wholesale:'Atacado',factory:'Loja de fábrica',retail:'Varejo'})[key]}: {p.prices[key]===null?'Não informado':(p.prices[key]!/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'})}</p>)}</div></div>
 <p className={`product-list-category${!productCategory(p)?' category-pending':''}`}><span className="list-mobile-label">Categoria: </span>{productCategory(p)||'Categoria pendente'}</p>
 <div className="product-list-origin"><p>{p.origin==='own'?'Próprio':'De cliente'}</p><p>{p.publicAllowed?'Divulgação autorizada':'Privado'}</p></div>
 {appName==='Artesão Digital'&&p.origin==='client'?<span className="product-list-catalog">Não disponível para produtos de cliente</span>:<label className="product-list-catalog"><span className="list-mobile-label">No catálogo</span><input type="checkbox" aria-label={`Exibir ${p.name} no catálogo`} checked={p.catalogVisible??false} disabled={busy||readOnly} onChange={e=>{const include=e.target.checked;return run(async()=>{await api('api/records/products/actions','POST',{action:include?'catalog_include':'catalog_remove',records:[{id:p.id,updatedAt:p.updatedAt}],confirm:true});await load();setMessage(include?'Produto incluído na seleção para catálogo. Privacidade preservada.':'Produto retirado da seleção para catálogo.');});}}/></label>}
 <ListRowActions disabled={busy||readOnly} onEdit={()=>openProduct(p)} onArchive={()=>{return run(async()=>{if(await archiveRecord('products',p as {id:number;updatedAt:string;name:string})){await load();setMessage('Produto arquivado. O histórico foi preservado.');}});}}/>
 </article>)}<ListPagination readOnly={readOnly} settingsArea="produtos" page={currentPage} pages={pages} total={filtered.length} size={pageSize} label="produtos" busy={busy} onPage={setPage}/>{appName==='Artesão Digital'&&!readOnly&&<details className="product-offline-group"><summary>Consulta offline</summary><OfflinePanel/></details>}</section>
 {edit&&<dialog ref={dialog} onCancel={e=>{e.preventDefault();closeProduct();}} aria-labelledby="product-title" style={{position:'fixed',inset:0,maxHeight:'90vh',overflow:'auto',width:'min(90vw,650px)',zIndex:5}}><ModalClose onClose={()=>closeProduct()} disabled={busy||readOnly}/><h2 id="product-title">{edit.id?'Editar produto':'Novo produto'}</h2><ProductForm key={edit.id??'new'} initial={edit.id?edit:undefined} context="produtos" onBusyChange={setBusy} onDirtyChange={setFormDirty} onCancel={()=>closeProduct()} onSaved={async()=>{await load();closeProduct(true);setMessage('Produto salvo.');}}/></dialog>}
 {fabricate!==null&&<ManufactureDialog productId={fabricate} onClose={()=>setFabricate(null)} onDone={load}/>}
 </main>;
}
