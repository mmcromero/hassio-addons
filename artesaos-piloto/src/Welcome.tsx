import {useEffect,useRef,useState,type FormEvent} from 'react';
import CompanyLogo from './CompanyLogo';
import ValidatedForm,{showValidation,type ValidationIssue} from './FormValidation';
import ActionButton from './ActionButton';
import {normalizePixKey,validPixKey} from './pix-brcode';
import './welcome.css';
type Company={name:string;responsible:string;phone:string;email:string;pixKey:string};
const empty:Company={name:'',responsible:'',phone:'',email:'',pixKey:''};
const draftKey='artesao-welcome:'+new URL('.',document.baseURI).pathname+':'+(document.querySelector<HTMLMetaElement>('meta[name=pilot-context]')?.content??'local');
function restoreDraft(data:Company,revision:number){try{const draft=JSON.parse(sessionStorage.getItem(draftKey)??'null');if(draft?.revision===revision&&Object.keys(empty).every(key=>typeof draft.data?.[key]==='string'))return {...data,...draft.data} as Company;}catch{}return data;}
export default function Welcome(){
 const title=useRef<HTMLHeadingElement>(null);
 useEffect(()=>{document.body.classList.add('pilot-first-access');title.current?.focus();return()=>document.body.classList.remove('pilot-first-access');},[]);
 const [data,setData]=useState(empty),[revision,setRevision]=useState(0),[loaded,setLoaded]=useState(false),[busy,setBusy]=useState(false),[logoPending,setLogoPending]=useState(true),[error,setError]=useState('');
 useEffect(()=>{let active=true;fetch(new URL('api/company',document.baseURI)).then(async r=>{if(!r.ok)throw Error('Não foi possível carregar seu cadastro. Atualize a página para tentar novamente.');return r.json();}).then(r=>{if(active){setData(restoreDraft({...empty,...r.data},r.revision));setRevision(r.revision);setLoaded(true);}}).catch(e=>{if(active)setError(e.message);});return()=>{active=false;};},[]);
 useEffect(()=>{if(loaded)try{sessionStorage.setItem(draftKey,JSON.stringify({data,revision}));}catch{}},[data,revision,loaded]);
 async function enter(event:FormEvent<HTMLFormElement>){
  event.preventDefault();if(busy||!loaded||logoPending)return;
  const form=event.currentTarget;
  const submitter=(event.nativeEvent as SubmitEvent).submitter as HTMLButtonElement|null;
  const destination=submitter?.value==='pricing'?'?view=configuracoes&area=fabricacao#config-custos':'?view=produtos';
  setBusy(true);setError('');
  try{
   const issues:ValidationIssue[]=[];
   const fieldError=(name:string,message:string)=>{const element=form.querySelector<HTMLInputElement>(`input[name="${name}"]`);if(element)issues.push({element,message});};
   if(!data.responsible.trim())fieldError('responsible','Preencha seu nome.');
   if(!/^[\d+().\s-]+$/.test(data.phone)||data.phone.replace(/\D/g,'').length<7)fieldError('phone','Informe um telefone válido com DDD.');
   if(data.pixKey.trim()&&!validPixKey(normalizePixKey(data.pixKey)))fieldError('pixKey','Informe uma chave Pix válida.');
   if(!showValidation(form,issues))return;
   const saved=await fetch(new URL('api/company',document.baseURI),{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:{...data,pixKey:normalizePixKey(data.pixKey),name:data.name.trim()||data.responsible.trim()},expectedRevision:revision})});
   const result=await saved.json();if(!saved.ok)throw Error(result.message||'Não foi possível salvar seu cadastro.');setRevision(result.revision);
   const completed=await fetch(new URL('api/onboarding/complete',document.baseURI),{method:'POST'});const status=await completed.json();if(!completed.ok)throw Error(status.message||'Não foi possível concluir seu cadastro.');
   try{sessionStorage.removeItem(draftKey);}catch{}
   location.replace(new URL(destination,document.baseURI).href);
  }catch(e){setError(e instanceof Error?e.message:'Não foi possível salvar. Tente novamente.');}finally{setBusy(false);}
 }
 return <main className="pilot-welcome" aria-labelledby="welcome-title">
  <header><img className="welcome-brand" src={new URL('brand/logo.png',document.baseURI).href} alt="Artesão Digital"/><h1 ref={title} tabIndex={-1} id="welcome-title">Que bom ter você aqui!</h1><p>Vamos preparar seu espaço. É rapidinho!</p></header>
  <ValidatedForm onSubmit={enter} aria-busy={busy}><fieldset disabled={!loaded||busy}>
   <legend className="sr-only">Seu cadastro</legend><div className="welcome-fields">
    <input aria-label="Seu nome" placeholder="Seu nome" name="responsible" autoComplete="name" required maxLength={200} value={data.responsible} onChange={e=>setData({...data,responsible:e.target.value})}/>
    <input aria-label="Telefone" placeholder="Telefone" name="phone" type="tel" autoComplete="tel" required maxLength={40} value={data.phone} onChange={e=>setData({...data,phone:e.target.value})}/>
    <input aria-label="E-mail (opcional)" placeholder="E-mail (opcional)" name="email" type="email" autoComplete="email" maxLength={254} value={data.email} onChange={e=>setData({...data,email:e.target.value})}/>
    <input aria-label="Chave Pix (opcional)" placeholder="Chave Pix (opcional)" name="pixKey" autoComplete="off" maxLength={254} value={data.pixKey} onChange={e=>setData({...data,pixKey:e.target.value})}/>
   </div><p className="welcome-hint">Nome e telefone são obrigatórios. Os demais campos são opcionais.</p>
   <div className="welcome-logo" aria-label="Logotipo opcional"><CompanyLogo compact onPendingChange={setLogoPending} disabled={busy}/></div>
   <section aria-labelledby="welcome-paths-title"><h2 id="welcome-paths-title">Por onde você quer começar?</h2><div className="welcome-paths"><ActionButton className="welcome-card" type="submit" name="destination" value="products" disabled={logoPending}><span aria-hidden="true" className="welcome-icon"><svg viewBox="0 0 24 24"><path d="m3 7 9-5 9 5v10l-9 5-9-5Z M3 7l9 5 9-5 M12 12v10 M7 4.8l10 5.5"/></svg></span><span><strong>Cadastrar meus produtos</strong><span>Já sabe seus preços? Comece pelo catálogo.</span></span></ActionButton>
   <ActionButton className="welcome-card" type="submit" name="destination" value="pricing" disabled={logoPending}><span aria-hidden="true" className="welcome-icon"><svg viewBox="0 0 24 24"><rect x="4" y="2" width="16" height="20" rx="2"/><path d="M7 6h10v4H7z M7 14h1 M12 14h1 M17 14h.1 M7 18h1 M12 18h1 M17 18h.1"/></svg></span><span><strong>Calcular meus preços</strong><span>Calcule os custos e defina seus preços de fabricação.</span></span></ActionButton></div></section>
  </fieldset><p role="alert">{error}</p></ValidatedForm>
 </main>;
}
