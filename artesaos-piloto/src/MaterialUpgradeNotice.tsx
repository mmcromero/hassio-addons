import ActionButton from './ActionButton';
import {appName} from './branding';
import {useEffect,useState} from 'react';
type Upgrade={complete:boolean;changed:number;reason:string;reference?:{id:number;name:string}};
export default function MaterialUpgradeNotice({refresh=0}:{refresh?:number}){
 const [state,setState]=useState<Upgrade|null>(null),[error,setError]=useState(''),[busy,setBusy]=useState(false);
 async function load(method='GET'){const r=await fetch(new URL('api/manufacturing/material-upgrade',document.baseURI),{method});if(!r.ok)throw Error('Não foi possível consultar a atualização dos materiais antigos.');setState(await r.json());}
 useEffect(()=>{void load().catch(e=>setError(e.message));},[refresh]);
 if(error)return <p className="form-error" role="alert">{error}</p>;
 if(!state||state.complete&&!state.changed)return null;
 return <aside className={state.complete?'upgrade-notice':'form-error'} aria-label="Atualização dos materiais antigos"><p>{state.complete?`${state.changed} produto(s) antigo(s) atualizado(s) com a referência de ${state.reference?.name}. Preços comerciais e histórico foram preservados.`:state.reason}</p>{!state.complete&&<><a href={appName==='Artesão Digital'?'?view=configuracoes&area=produtos#materiais':'?view=configuracoes&area=fabricacao#materiais'}>Gerenciar materiais</a><ActionButton type="button" disabled={busy} onClick={()=>{setBusy(true);return load('POST').catch(e=>setError(e.message)).finally(()=>setBusy(false));}}>Verificar atualização dos produtos antigos</ActionButton></>}</aside>;
}
