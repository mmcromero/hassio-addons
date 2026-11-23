import ActionButton from './ActionButton';
import BrandIcon from './BrandIcon';
import {appName} from './branding';
import ClientDetails from './ClientDetails';
import ValidatedForm from './FormValidation';
import RecordActions,{archiveRecord} from './RecordActions';
import ListPagination,{pageSizes,searchText} from './ListPagination';
import ModalClose from './ModalClose';
import ListRowActions from './ListRowActions';
import ListHeading from './ListHeading';
import {useEffect,useRef,useState,type FormEvent} from 'react';
import ClientFields from './ClientFields';
import {clientDraft,clientLabel,emptyClient,type ClientDraft} from './client-model';
import AreaNav,{SettingsLink} from './AreaNav';
import './products.css';
type Draft=ClientDraft;
type Client=Draft&{id:number;updatedAt:string};
const blank=emptyClient;
async function api(path:string,method='GET',body?:unknown){
 const response=await fetch(new URL(path,document.baseURI),{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});
 const data=await response.json();if(!response.ok)throw Error(data.message||'Não foi possível salvar o cliente.');return data;
}
export default function Clients(){
 const [batchSelection,setBatchSelection]=useState<number[]>([]);
 const [batchExpanded,setBatchExpanded]=useState(false);
 const [expandedClients,setExpandedClients]=useState<number[]>([]);
 const [clients,setClients]=useState<Client[]>([]),[draft,setDraft]=useState<Draft|null>(null),[id,setId]=useState<number|null>(null),[busy,setBusy]=useState(false),[dirty,setDirty]=useState(false),[message,setMessage]=useState('Carregando clientes…'),[error,setError]=useState('');
 const [search,setSearch]=useState(''),[page,setPage]=useState(1),[pageSize,setPageSize]=useState('10');
 const initial=useRef('');
 const filtered=clients.filter(c=>searchText(c.name+' '+c.contact).includes(searchText(search)));
 const size=pageSize==='all'?Math.max(1,filtered.length):Number(pageSize),pages=Math.max(1,Math.ceil(filtered.length/size)),currentPage=Math.min(page,pages);
 const visible=filtered.slice((currentPage-1)*size,currentPage*size);
 useEffect(()=>{api('api/settings/clientes').then(r=>setPageSize(pageSizes.includes(r.data.clientsPerPage)?r.data.clientsPerPage:'10')).catch(e=>setMessage(e.message));},[]);
 const [lookupBusy,setLookupBusy]=useState(false);
 const dialog=useRef<HTMLDialogElement>(null),trigger=useRef<HTMLElement|null>(null);
 const load=async()=>{const rows=await api('api/clients');setClients(rows);const id=new URLSearchParams(location.search).get('client');if(id){const c=rows.find((x:any)=>String(x.id)===id);if(c)open(c);}};
 useEffect(()=>{load().then(()=>setMessage('Cadastros salvos nesta instalação.')).catch(e=>setMessage(e.message));},[]);
 useEffect(()=>{if(draft&&!dialog.current?.open)dialog.current?.showModal();},[draft]);
 function open(client?:Client){trigger.current=document.activeElement as HTMLElement;setId(client?.id??null);setDraft(client?clientDraft(client):blank());initial.current=JSON.stringify(client?clientDraft(client):blank());setDirty(false);setError('');}
 function close(force=false){if(!force&&(busy||(dirty&&JSON.stringify(draft)!==initial.current&&!confirm('Descartar as alterações não salvas deste cliente?'))))return;dialog.current?.close();setDraft(null);trigger.current?.focus({preventScroll:true});}
 function update(key:keyof Draft,value:string){setDraft(previous=>previous?{...previous,[key]:value}:previous);setDirty(true);}
 async function save(event:FormEvent){event.preventDefault();if(!draft)return;setBusy(true);setError('');try{if(!draft.name.trim()&&!draft.contact.trim())throw Error('Informe o nome da empresa ou o nome do contato.');await api(id===null?'api/clients':`api/clients/${id}`,id===null?'POST':'PUT',{...draft,...(id===null?{registrationOrigin:'direct'}:{})});await load();close(true);setMessage('Cliente salvo.');}catch(e){setError(e instanceof Error?e.message:'Falha ao salvar.');}finally{setBusy(false);}}

 return <main className="products-screen"><header><span className="brand">{appName}</span></header><AreaNav active="clientes"/><h1>Clientes</h1><SettingsLink area="clientes"/><p>Cadastros persistentes nesta instalação e disponíveis na área Orçamentos.</p><p role="status">{message}</p><ActionButton disabled={busy} onClick={()=>open()}>{appName==='Artesão Digital'&&<BrandIcon name="plus"/>}Novo cliente</ActionButton><section><h2>Clientes cadastrados ({clients.length})</h2><label>Buscar clientes<input type="search" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}} placeholder="Empresa ou contato"/></label><ListHeading kind="clients" selection={batchExpanded}/>{!filtered.length&&<p>Nenhum cliente encontrado.</p>}{visible.map(client=><article key={client.id} className={`data-list-row clients-list-row${expandedClients.includes(client.id)?' has-details':''}${batchExpanded?' has-selection':''}`}>{batchExpanded&&<label className="list-selection"><input type="checkbox" aria-label={`Selecionar ${clientLabel(client)}`} checked={batchSelection.includes(client.id)} onChange={e=>setBatchSelection(previous=>e.target.checked?[...previous,client.id]:previous.filter(id=>id!==client.id))}/></label>}<div className="client-list-identity"><h3 className="record-title">{clientLabel(client)}</h3>{client.name.trim()&&client.contact.trim()&&<p>{client.contact}</p>}</div><ActionButton type="button" id={`client-toggle-${client.id}`} className="client-details-toggle" aria-expanded={expandedClients.includes(client.id)} aria-controls={`client-details-${client.id}`} onClick={()=>setExpandedClients(previous=>previous.includes(client.id)?previous.filter(id=>id!==client.id):[...previous,client.id])}>Ver dados do cliente</ActionButton><ListRowActions disabled={busy} onEdit={()=>open(client)} onArchive={()=>{return (async()=>{setBusy(true);try{if(await archiveRecord('clients',client)){await load();setMessage('Cliente arquivado. O histórico foi preservado.');}}catch(e){setMessage(e instanceof Error?e.message:'Falha ao arquivar.');}finally{setBusy(false);}})();}}/>{expandedClients.includes(client.id)&&<ClientDetails client={client}/>}</article>)}<ListPagination settingsArea="clientes" page={currentPage} pages={pages} total={filtered.length} size={pageSize} label="clientes" busy={busy} onPage={setPage}/><RecordActions onExpandedChange={setBatchExpanded} selection={{ids:batchSelection,setIds:setBatchSelection}} kind="clients" rows={filtered} visible={visible} onDone={load} disabled={busy}/></section>
 {draft&&<dialog ref={dialog} aria-labelledby="client-title" onCancel={e=>{e.preventDefault();close();}} style={{position:'fixed',inset:0,maxHeight:'90vh',overflow:'auto',width:'min(90vw,650px)'}}><ModalClose onClose={()=>close()} disabled={busy}/><h2 id="client-title">{id===null?'Novo cliente':'Editar cliente'}</h2><ValidatedForm onSubmit={save}>
 <ClientFields sectioned={appName==='Artesão Digital'} draft={draft} prefix="client-page" update={update} busy={busy} onLookupBusy={setLookupBusy}/><p>Documento e endereço podem ficar pendentes no cadastro; envio e validação fiscal ainda não estão implementados.</p>{error&&<p className="form-error" role="alert">{error}</p>}<ActionButton disabled={busy||lookupBusy}>Salvar cliente</ActionButton><ActionButton type="button" disabled={busy} onClick={()=>close()}>Cancelar</ActionButton></ValidatedForm></dialog>}
 </main>;
}
