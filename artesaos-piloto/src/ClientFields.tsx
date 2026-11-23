import SectionTabs from './SectionTabs';
import ActionButton from './ActionButton';
import {RequiredMark,showValidation} from './FormValidation';
import {useEffect,useRef,useState} from 'react';
import {addressFields,type ClientDraft} from './client-model';
type Props={draft:ClientDraft;prefix:string;update:(key:keyof ClientDraft,value:string)=>void;busy?:boolean;sectioned?:boolean;onLookupBusy?:(busy:boolean)=>void};
export default function ClientFields({draft,prefix,update,busy=false,sectioned=false,onLookupBusy}:Props){
 const [loading,setLoading]=useState(false),[message,setMessage]=useState('');
 const current=useRef(draft);current.current=draft;
 const request=useRef<AbortController|null>(null),ticket=useRef(0);
 useEffect(()=>{ticket.current++;request.current?.abort();setLoading(false);onLookupBusy?.(false);setMessage('');},[draft.postal,onLookupBusy]);
 useEffect(()=>()=>{ticket.current++;request.current?.abort();onLookupBusy?.(false);},[onLookupBusy]);
 async function lookup(){
  const postal=draft.postal.replace(/\D/g,'');if(postal.length!==8){const input=document.getElementById(`${prefix}-postal`)!;showValidation(input.closest('fieldset')!,[{element:input,message:'Informe um CEP com oito dígitos para consultar, ou preencha o endereço manualmente.'}]);setMessage('');return;}
  request.current?.abort();const controller=new AbortController();request.current=controller;const seq=++ticket.current;const before={...draft};setLoading(true);onLookupBusy?.(true);setMessage('Consultando CEP…');const timer=setTimeout(()=>controller.abort(),8000);
  try{
   const response=await fetch(`https://viacep.com.br/ws/${postal}/json/`,{signal:controller.signal,credentials:'omit',referrerPolicy:'no-referrer',redirect:'error'});
   if(!response.ok)throw Error('lookup');const data=await response.json();
   if(seq!==ticket.current||current.current.postal.replace(/\D/g,'')!==postal)return;
   if(data.erro||typeof data.cep!=='string'||data.cep.replace(/\D/g,'')!==postal){setMessage('CEP não encontrado. Você pode preencher todo o endereço manualmente.');return;}
   const fields=[['street','logradouro',200],['district','bairro',100],['city','localidade',100],['state','uf',2]] as const;
   for(const [key,source,max] of fields){if(typeof data[source]==='string'&&data[source].trim()&&current.current[key]===before[key])update(key,data[source].trim().slice(0,max));}
   setMessage('Consulta concluída. Confira os dados e informe número e complemento, se houver. Se algum campo vier vazio, preencha manualmente.');
  }catch{if(seq===ticket.current)setMessage('Não foi possível consultar o CEP. O preenchimento manual continua disponível.');}
  finally{clearTimeout(timer);if(seq===ticket.current){setLoading(false);onLookupBusy?.(false);}}
 }
 const identity=<><label>Tipo de cliente<select value={draft.commercialType} onChange={e=>update('commercialType',e.target.value)}><option value="wholesale">Atacado</option><option value="retail">Varejo</option><option value="undefined">Não definido</option></select></label><p>Classificação informativa; não altera preços ou descontos.</p><fieldset className="quote-content-fields" data-require-one="input[data-client-name]" data-require-message="Informe o nome da empresa ou o nome do contato."><legend>Identificação do cliente<RequiredMark/><span className="sr-only"> — pelo menos um campo obrigatório</span></legend><p>Preencha pelo menos um: nome da empresa ou nome do contato.</p><label htmlFor={`${prefix}-company`}>Nome da empresa</label><input data-client-name autoFocus id={`${prefix}-company`} maxLength={200} value={draft.name} onChange={e=>update('name',e.target.value)}/><label htmlFor={`${prefix}-contact`}>Nome do contato</label><input data-client-name id={`${prefix}-contact`} maxLength={200} value={draft.contact} onChange={e=>update('contact',e.target.value)}/></fieldset><label htmlFor={`${prefix}-phone`}>Telefone</label><input id={`${prefix}-phone`} type="tel" maxLength={50} value={draft.phone} onChange={e=>update('phone',e.target.value)}/><label htmlFor={`${prefix}-email`}>E-mail</label><input id={`${prefix}-email`} name="client-email" type="email" maxLength={254} value={draft.email} onChange={e=>update('email',e.target.value)}/><label htmlFor={`${prefix}-document`}>CPF ou CNPJ</label><input id={`${prefix}-document`} maxLength={40} value={draft.taxDocument} onChange={e=>update('taxDocument',e.target.value)}/></>;
 const address=<fieldset><legend>Endereço de entrega</legend><label htmlFor={`${prefix}-postal`}>CEP de entrega</label><input id={`${prefix}-postal`} inputMode="numeric" maxLength={20} value={draft.postal} onChange={e=>update('postal',e.target.value)}/><ActionButton type="button" disabled={busy||loading} onClick={()=>lookup()}>Buscar endereço pelo CEP</ActionButton><p>Consulta opcional ao ViaCEP usando apenas o CEP. Você também pode preencher todos os campos manualmente.</p>{message&&<p role="status">{message}</p>}{addressFields.map(([key,label,max])=><div key={key}><label htmlFor={`${prefix}-${key}`}>{label}</label><input id={`${prefix}-${key}`} maxLength={max} value={draft[key]} onChange={e=>update(key,e.target.value)}/></div>)}</fieldset>;
 return sectioned?<SectionTabs label="Seções do cliente" sections={[{id:'dados',label:'Dados',content:identity},{id:'endereco',label:'Endereço',content:address}]}/>:<>{identity}{address}</>;
}
