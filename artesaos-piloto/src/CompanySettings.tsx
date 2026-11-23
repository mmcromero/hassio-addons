import ActionButton from './ActionButton';
import {useEffect,useId,useState,type FormEvent} from 'react';
import ValidatedForm from './FormValidation';
type Company={name:string;responsible:string;phone:string;email:string};
const empty:Company={name:'',responsible:'',phone:'',email:''};
export default function CompanySettings(){
 const id=useId(),[data,setData]=useState<Company>(empty),[revision,setRevision]=useState(0),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState(false),[message,setMessage]=useState('Carregando dados da empresa…');
 useEffect(()=>{let active=true;fetch(new URL('api/company',document.baseURI)).then(async response=>{if(!response.ok)throw Error('Não foi possível carregar os dados da empresa. Atualize a página para tentar novamente.');return response.json();}).then(result=>{if(active){setData({...empty,...result.data});setRevision(result.revision);setLoaded(true);setMessage('');}}).catch(reason=>{if(active){setError(true);setMessage(reason.message);}});return()=>{active=false;};},[]);
 async function save(event:FormEvent){event.preventDefault();setBusy(true);setError(false);try{
  const response=await fetch(new URL('api/company',document.baseURI),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({data,expectedRevision:revision})});const result=await response.json();if(!response.ok)throw Error(result.message||'Não foi possível salvar os dados da empresa.');setRevision(result.revision);setData(previous=>Object.fromEntries(Object.entries(previous).map(([key,value])=>[key,value.trim()])) as Company);setMessage('Dados da empresa salvos.');dispatchEvent(new Event('pilot-setup-saved'));
 }catch(reason){setError(true);setMessage(reason instanceof Error?reason.message:'Não foi possível salvar os dados da empresa.');}finally{setBusy(false);}}
 return <section className="company-settings" aria-labelledby={`${id}-title`}><h3 id={`${id}-title`}>Dados da empresa</h3><p>Identificação de quem utiliza esta conta. Nome e telefone são obrigatórios. Os demais dados podem ser completados depois.</p><ValidatedForm onSubmit={save}><fieldset disabled={!loaded||busy}><div className="company-fields">
 <label>Nome da empresa<input name="companyName" value={data.name} maxLength={200} autoComplete="organization" onChange={event=>setData({...data,name:event.target.value})}/></label>
 <label>Nome da pessoa responsável<input required name="companyResponsible" value={data.responsible} maxLength={200} autoComplete="name" onChange={event=>setData({...data,responsible:event.target.value})}/></label>
 <label>Telefone para contato<input required name="companyPhone" type="tel" value={data.phone} maxLength={40} autoComplete="tel" onChange={event=>setData({...data,phone:event.target.value})}/></label>
 <label>E-mail para contato (opcional)<input name="companyEmail" type="email" value={data.email} maxLength={254} autoComplete="email" onChange={event=>setData({...data,email:event.target.value})}/></label>
 </div><ActionButton disabled={!loaded||busy}>Salvar dados da empresa</ActionButton></fieldset></ValidatedForm><p role={error?'alert':'status'}>{message}</p></section>;
}
