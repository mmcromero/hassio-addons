import {moduleEnabled} from './module-access';
import ActionButton from './ActionButton';
import ValidatedForm,{RequiredMark} from './FormValidation';
import ModalClose from './ModalClose';
import ClientFields from './ClientFields';
import {clientDraft,clientLabel,emptyClient,type Client,type ClientDraft} from './client-model';
export type {Client} from './client-model';
import { useEffect, useRef, useState, type FormEvent } from 'react';

const examples: Client[] = [
  { ...emptyClient(), id: 1, name: 'Cliente de demonstração' },
  { ...emptyClient(), id: 2, name: 'Empresa de demonstração', contact: 'Contato de exemplo' },
];

export default function ClientPicker({ selected, onSelect, persistent=false,context='quote',sessionId }: { selected: Client | null; onSelect: (client: Client | null) => void; persistent?:boolean;context?:'quote'|'sale';sessionId?:string }) {
  const [clients, setClients] = useState<Client[]>(persistent?[]:examples);
  const [draft, setDraft] = useState<ClientDraft>(emptyClient);
  const [editing, setEditing] = useState<number | null>(null);
  const [dirty, setDirty] = useState(false);
  const [error, setError] = useState('');
  const [message, setMessage] = useState('');
  const dialog = useRef<HTMLDialogElement>(null);
  const trigger = useRef<HTMLElement | null>(null);
  const initial=useRef(JSON.stringify(emptyClient()));
  const nextId = useRef(3);
  const selector=useRef<HTMLSelectElement>(null),card=useRef<HTMLDivElement>(null);
  const focusSelector=useRef(false),focusCard=useRef(false);
  useEffect(()=>{if(!selected&&focusSelector.current){selector.current?.focus();focusSelector.current=false;}if(selected&&focusCard.current){card.current?.focus();focusCard.current=false;}},[selected]);
  function changeClient(){focusSelector.current=true;onSelect(null);setMessage('Selecione outro cliente ou cadastre um novo. Os demais dados do orçamento foram preservados.');}
  const [busy,setBusy]=useState(false);
  const [lookupBusy,setLookupBusy]=useState(false);
  const [openCycle,setOpenCycle]=useState(0);
  async function clientRequest(path:string,method='GET',body?:unknown){const r=await fetch(new URL(context==='sale'?path.replace(/^api\/clients/,'api/context/pdv/clients'):path,document.baseURI),{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.message||'Não foi possível salvar o cliente.');return data;}
  useEffect(()=>{if(persistent)clientRequest('api/clients').then(setClients).catch(e=>setMessage(e.message));},[persistent]);

  function open(client?: Client) {
    setOpenCycle(n=>n+1);setLookupBusy(false);
    trigger.current = document.activeElement as HTMLElement;
    const value=client ? clientDraft(client) : {...emptyClient(),commercialType:context==='quote'?'wholesale':'retail'};initial.current=JSON.stringify(value);setDraft(value);
    setEditing(client?.id ?? null); setDirty(false); setError('');
    dialog.current?.showModal();
  }
  function close(force = false) {
    if(!force&&busy)return;
    if (!force && dirty && JSON.stringify(draft)!==initial.current && !window.confirm('Descartar as alterações não salvas deste cliente?')) return;
    dialog.current?.close(); trigger.current?.focus({preventScroll:true});
  }
  function update(key: keyof ClientDraft, value: string) {
    setDraft(previous => ({ ...previous, [key]: value })); setDirty(true);
  }
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!draft.name.trim()&&!draft.contact.trim()) { setError('Informe o nome da empresa ou o nome do contato.'); return; }
    const email = event.currentTarget.elements.namedItem('client-email') as HTMLInputElement;
    if (email.validity.typeMismatch) { setError('Confira o formato do e-mail informado.'); return; }
    if(persistent){
      setBusy(true);
      try{
        const body={...clientDraft(draft),...(editing===null?{registrationOrigin:context,...(context==='sale'&&sessionId?{captureSessionId:sessionId}:{})}:{}),name:draft.name.trim(),contact:draft.contact.trim()};
        const result=await clientRequest(editing===null?'api/clients':`api/clients/${editing}`,editing===null?'POST':'PUT',body);
        const list:Client[]=await clientRequest('api/clients');setClients(list);
        if(editing===null)focusCard.current=true;
        onSelect(list.find(c=>c.id===(editing??result.id))??null);
        setMessage('Cliente salvo no cadastro e selecionado nesta operação.');close(true);
      }catch(e){setError(e instanceof Error?e.message:'Falha ao salvar.');}finally{setBusy(false);}
      return;
    }
    const client: Client = { ...draft, name: draft.name.trim(), id: editing ?? nextId.current++ };
    setClients(previous => editing === null ? [...previous, client] : previous.map(c => c.id === editing ? client : c));
    if(editing===null)focusCard.current=true;
    onSelect(client);
    setMessage(editing === null ? 'Cliente adicionado à lista simulada e selecionado nesta operação.' : 'Cadastro simulado atualizado. Os itens do orçamento foram preservados.');
    close(true);
  }
  return <div className="wf-client-picker">
    {!selected&&<div className="wf-client-select"><div><label htmlFor="wf-client-select">Selecionar cliente{persistent&&context==='quote'&&<RequiredMark/>}</label><select aria-required={persistent&&context==='quote'||undefined} data-required-for={context==='quote'?'finalize':undefined} aria-describedby={persistent?'quote-finalize-hint':undefined} ref={selector} id="wf-client-select" value="" onChange={e => { focusCard.current=true;onSelect(clients.find(c => c.id === Number(e.target.value)) ?? null); setMessage(''); }}><option value="">Escolha um cliente da lista</option>{clients.map(client => <option value={client.id} key={client.id}>{clientLabel(client)}</option>)}</select></div>{(moduleEnabled('clientes')||(context==='sale'&&moduleEnabled('vendas')))&&<ActionButton type="button" onClick={() => open()}>+ Novo cliente</ActionButton>}</div>}
    {selected ? <div ref={card} tabIndex={-1} className="wf-selected-client"><strong>{clientLabel(selected)}</strong><p>Contato: {selected.contact || 'a informar'} · CEP: {selected.postal || 'pendente'}</p><details><summary>Ver dados do cliente</summary><dl className="wf-client-details">{([
      ['Nome da empresa', selected.name], ['Nome do contato', selected.contact],
      ['Telefone', selected.phone], ['E-mail', selected.email], ['CPF ou CNPJ', selected.taxDocument], ['CEP de entrega', selected.postal],['Rua / logradouro',selected.street],['Número',selected.number],['Complemento',selected.complement],['Bairro',selected.district],['Cidade',selected.city],['Estado (UF)',selected.state],
    ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{value || 'Não informado'}</dd></div>)}</dl><p className="wf-muted">Dados para consulta. CPF/CNPJ ainda não validado neste protótipo.</p></details>{(moduleEnabled('clientes')||(context==='sale'&&moduleEnabled('vendas')))&&<ActionButton type="button" className="wf-quiet" onClick={() => open(selected)}>Editar cadastro do cliente</ActionButton>}<ActionButton type="button" className="wf-secondary" onClick={changeClient}>Trocar cliente</ActionButton></div>
      : <p className="wf-pending">Cliente a selecionar. {context==='quote'?'O orçamento pode continuar como rascunho.':'A venda pode continuar sem identificação.'}</p>}
    <p className="wf-muted">{persistent?'O cadastro de clientes é persistente. A seleção é utilizada nesta operação.':'A lista e os cadastros são simulados nesta página; recarregar descarta as alterações.'}</p>
    <p role="status">{message}</p>
    <dialog ref={dialog} className="wf-dialog" aria-labelledby="wf-client-modal-title" onCancel={e => { e.preventDefault(); e.stopPropagation(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
      <ValidatedForm noValidate onSubmit={save}><div className="wf-modal-header"><div><small>{context==='quote'?'CADASTRO SEM SAIR DO ORÇAMENTO':'CADASTRO SEM SAIR DA VENDA'}</small><h2 id="wf-client-modal-title">{editing === null ? 'Novo cliente' : 'Editar cliente'}</h2></div><ModalClose onClose={()=>close()} disabled={busy}/></div>
        <div className="wf-modal-body"><p>Os produtos, embalagens e observações do pedido continuam preservados.</p>{error && <div className="wf-error" role="alert">{error}</div>}
          <ClientFields key={openCycle} draft={draft} prefix="wf-client" update={update} busy={busy} onLookupBusy={setLookupBusy}/>
          <p className="wf-muted">CPF/CNPJ será necessário para preparar o envio, sem bloquear o rascunho ou a cotação. Validação fiscal e consulta de frete ainda não implementadas.</p>
        </div><div className="wf-modal-footer"><ActionButton type="button" className="wf-secondary" onClick={() => close()}>Cancelar</ActionButton><ActionButton type="submit" disabled={busy||lookupBusy}>{editing === null ? 'Salvar e selecionar cliente' : 'Salvar cadastro do cliente'}</ActionButton></div>
      </ValidatedForm>
    </dialog>
  </div>;
}
