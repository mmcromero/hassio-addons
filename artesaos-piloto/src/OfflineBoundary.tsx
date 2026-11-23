import {useEffect,useRef,useState,type ReactNode} from 'react';
import Products from './Products';
import {createPortal} from 'react-dom';
import {authorize,OfflineNetworkError,OfflineLoginError,OfflineAccountError} from './offline-catalog';
import {loadCatalog,releaseCatalog,listenAccess,read,lockAccess,currentBinding,prefix,type LocalCatalog,type Access} from './offline-storage';
declare global{interface Window{artesaoOffline?:{lock:()=>Promise<void>};}}
type Mode='checking'|'online'|'local'|'locked'|'review';
export default function OfflineBoundary({children}:{children:ReactNode}){
 const [mode,setMode]=useState<Mode>('checking'),[message,setMessage]=useState(''),[catalog,setCatalog]=useState<LocalCatalog|null>(null);
 const current=useRef<LocalCatalog|null>(null),active=useRef(true),checking=useRef(false),modeRef=useRef(mode),edited=useRef(false),onlineContent=useRef<HTMLDivElement>(null),openLocal=useRef<()=>Promise<void>>(async()=>{});modeRef.current=mode;
 useEffect(()=>{
  active.current=true;const context=document.querySelector<HTMLMetaElement>('meta[name="pilot-context"]')?.content;
  let authorizedAccount:string|undefined,authorizedNamespace:string|undefined,hadOnline=false,recheck=false;
  window.artesaoOffline={lock:async()=>{const account=context??current.current?.account;if(account)await lockAccess(account);}};
  const clear=()=>{releaseCatalog(current.current);current.current=null;setCatalog(null);};
  const display=async()=>{const next=await loadCatalog();if(!active.current){releaseCatalog(next);return;}clear();current.current=next;setCatalog(next);setMode('local');};
  openLocal.current=async()=>{if(!confirm('Ao abrir a cópia preparada, informações ainda não salvas poderão ser perdidas. Revise ou copie antes de continuar. Abrir a consulta local?'))return;try{await display();setMessage('Offline — somente consulta dos dados preparados.');}catch(e){setMessage(e instanceof Error?e.message:'Não foi possível abrir a cópia. O preenchimento foi preservado.');}};
  const fallback=async(reason:Error)=>{
   if(hadOnline&&(edited.current||document.querySelector('form[aria-busy="true"]'))&&(modeRef.current==='online'||modeRef.current==='review')){setMode('review');setMessage('Sem conexão. Salvar e outras alterações estão bloqueados. Revise ou copie informações ainda não salvas antes de abrir a consulta preparada.');return;}
   try{await display();setMessage(reason instanceof OfflineLoginError?'Sessão online expirada. A cópia local continua disponível; entre novamente para atualizar.':'Offline — somente consulta dos dados preparados.');}catch(e){clear();setMode('locked');setMessage(e instanceof Error?e.message:'Nenhuma cópia disponível.');}
  };
  const check=async()=>{if(checking.current||!active.current)return;checking.current=true;
   try{
    const access=await authorize();authorizedAccount=access.account;authorizedNamespace=access.namespace;if(!active.current)return;
    if(document.documentElement.dataset.offlineShell==='true'){
     const explicit=location.pathname===prefix()+'offline';let tried=false;try{tried=sessionStorage.getItem('artesao-offline-return:'+prefix())==='1';}catch{tried=true;}
     if(!explicit&&!tried){try{sessionStorage.setItem('artesao-offline-return:'+prefix(),'1');}catch{}location.replace(prefix()+'?view=produtos');return;}
     await display();setMessage('Consulta local. A conexão está disponível para entrar ou atualizar pelo modo online.');
    }else{try{sessionStorage.removeItem('artesao-offline-return:'+prefix());}catch{}clear();hadOnline=true;setMode('online');}
   }catch(e){if(!active.current)return;
    if(e instanceof OfflineNetworkError||e instanceof OfflineLoginError)await fallback(e);
    else if(e instanceof OfflineAccountError){clear();setMode('locked');setMessage(e.message);}
    else if(document.documentElement.dataset.offlineShell==='true'){clear();setMode('locked');setMessage(e instanceof Error?e.message:'Armazenamento indisponível.');}
    else{hadOnline=true;setMode('online');}
   }finally{checking.current=false;if(recheck&&active.current){recheck=false;void check();}}
  };
  const guard=(event:Event)=>{
   const expected=current.current?.namespace??authorizedNamespace;
   if(modeRef.current!=='locked'&&expected&&currentBinding()!==expected){event.preventDefault();event.stopImmediatePropagation();clear();setMode('locked');setMessage('A conta mudou. Entre novamente para consultar a cópia correspondente.');return;}
   if(modeRef.current==='review'&&onlineContent.current?.contains(event.target as Node)){
    const target=event.target as HTMLElement;if(target.closest('[data-offline-review]'))return;if(event.type==='keydown'&&(event as KeyboardEvent).key==='Tab')return;
    if(event.type!=='keydown'||target.matches('select,input[type=checkbox],input[type=radio]')){if(event.type==='click'&&!target.closest('button,a,input[type=checkbox],input[type=radio],select'))return;event.preventDefault();event.stopImmediatePropagation();}
   }
  };
  const recordEdit=(event:Event)=>{if(modeRef.current==='online'&&(event.target as HTMLElement).closest('form'))edited.current=true;};
  const verify=async()=>{try{const access=await read<Access>('access','current'),expected=current.current?.account??authorizedAccount;if(expected&&(!access||access.account!==expected||currentBinding()!==access.namespace||current.current&&current.current.namespace!==access.namespace)){clear();setMode('locked');setMessage('Consulta local bloqueada. Entre novamente com a conta correspondente; a cópia foi preservada.');}}catch{if(modeRef.current==='local'){clear();setMode('locked');setMessage('Não foi possível conferir a conta da cópia local.');}}};
  const changed=()=>{if(modeRef.current!=='checking')void verify();};const unlisten=listenAccess(changed);
  const network=(event:Event)=>{if(checking.current){if(event.type==='online'||event.type==='offline')recheck=true;return;}void check();},visible=()=>{if(document.visibilityState==='visible'){void verify();if(modeRef.current==='local'&&navigator.onLine)void check();}};
  for(const type of ['click','input','change','submit','keydown'])document.addEventListener(type,guard,true);
  document.addEventListener('input',recordEdit,true);document.addEventListener('change',recordEdit,true);
  addEventListener('offline',network);addEventListener('online',network);addEventListener('artesao-server-unavailable',network);document.addEventListener('visibilitychange',visible);void check();
  return()=>{active.current=false;unlisten();for(const type of ['click','input','change','submit','keydown'])document.removeEventListener(type,guard,true);document.removeEventListener('input',recordEdit,true);document.removeEventListener('change',recordEdit,true);removeEventListener('offline',network);removeEventListener('online',network);removeEventListener('artesao-server-unavailable',network);document.removeEventListener('visibilitychange',visible);releaseCatalog(current.current);current.current=null;};
 },[]);
 useEffect(()=>{document.documentElement.dataset.offlineMode=mode;return()=>{delete document.documentElement.dataset.offlineMode;};},[mode]);
 useEffect(()=>{
  if(mode!=='review'||!onlineContent.current)return;const originals=new Map<HTMLInputElement|HTMLTextAreaElement,boolean>();
  const mark=()=>{for(const el of Array.from(onlineContent.current!.querySelectorAll<HTMLInputElement|HTMLTextAreaElement>('input:not([type=checkbox]):not([type=radio]),textarea'))){if(!originals.has(el))originals.set(el,el.readOnly);if(!el.readOnly)el.readOnly=true;}};mark();const observer=new MutationObserver(mark);observer.observe(onlineContent.current,{childList:true,subtree:true});return()=>{observer.disconnect();for(const [el,value] of originals)el.readOnly=value;};
 },[mode]);
 const review=<aside data-offline-review aria-disabled="false" className="products-screen" aria-label="Revisar antes da consulta offline"><p role="alert">{message}</p><button type="button" onClick={()=>void openLocal.current()}>Abrir consulta preparada</button></aside>;
 const dialog=mode==='review'?onlineContent.current?.querySelector('dialog[open]'):null;
 return <>
  {mode==='checking'&&<main className="products-screen"><p role="status">Preparando acesso ao aplicativo…</p></main>}
  {mode==='review'&&(dialog?createPortal(review,dialog):review)}
  <div ref={onlineContent} className={mode==='review'?'offline-review':undefined} aria-disabled={mode==='review'||undefined}>{(mode==='online'||mode==='review')&&children}</div>
  {mode==='locked'&&<main className="products-screen"><h1>Produtos offline</h1><p role="alert">{message}</p><a href={prefix()+'login'}>Entrar online</a></main>}
  {mode==='local'&&catalog&&<><aside className="products-screen" aria-label="Estado da consulta offline"><p role="status">{message}</p><p>{catalog.label} · Última preparação: {new Date(catalog.preparedAt).toLocaleString('pt-BR')}{catalog.recovered?' · Cópia anterior recuperada.':''}</p><p>Criação, edição, exclusão e outras operações estão desativadas nesta consulta. Fotos externas antigas podem estar indisponíveis.</p><a href={prefix()+'?view=produtos'}>Voltar ao modo online</a></aside><Products offlineCatalog={catalog}/></>}
 </>;
}
