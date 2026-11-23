import {useEffect,useState} from 'react';
import {createPortal} from 'react-dom';

// Original PDV identity: customer image only when registered; otherwise keep Artesão Digital.
// Mounted only in Sales; the shared navigation and public identity are not replaced.
export default function PdvIdentity(){
 const [host,setHost]=useState<HTMLElement|null>(null);
 const [identity,setIdentity]=useState<{name:string;logo:string}>({name:'',logo:''});
 const [loadedLogo,setLoadedLogo]=useState('');
 useEffect(()=>{
  const find=()=>{const node=document.querySelector<HTMLElement>('#pilot-shell .pilot-account-title');if(node){setHost(node);return true;}return false;};
  if(find())return;
  const observer=new MutationObserver(()=>{if(find())observer.disconnect();});
  observer.observe(document.body,{childList:true,subtree:true});return()=>observer.disconnect();
 },[]);
 useEffect(()=>{
  if(!host)return;
  let controller:AbortController|undefined,objectUrl='';
  async function refresh(){
   controller?.abort();const active=new AbortController();controller=active;
   const read=(path:string)=>fetch(new URL('api/company'+path,document.baseURI),{signal:active.signal});
   try{
    const [company,meta]=await Promise.all([read(''),read('/logo/meta')]);
    if(!company.ok||!meta.ok)return;
    const {data}=await company.json(),{present,revision}=await meta.json();
    const name=typeof data?.name==='string'?data.name.trim():'';
    let next='';
    if(present){const image=await read('/logo?revision='+revision);if(image.ok){const blob=await image.blob();if(active.signal.aborted)return;next=URL.createObjectURL(blob);}}
    if(active.signal.aborted){if(next)URL.revokeObjectURL(next);return;}
    if(objectUrl)URL.revokeObjectURL(objectUrl);
    objectUrl=next;setLoadedLogo('');setIdentity({name,logo:next});
   }catch{/* Preserve the previous confirmed or default identity on read failure. */}
  }
  void refresh();window.addEventListener('pilot-setup-saved',refresh);window.addEventListener('pilot-company-identity-changed',refresh);
  return()=>{controller?.abort();if(objectUrl)URL.revokeObjectURL(objectUrl);window.removeEventListener('pilot-setup-saved',refresh);window.removeEventListener('pilot-company-identity-changed',refresh);};
 },[host]);
 if(!host||!identity.logo)return null;
 return createPortal(<span className="ad-company-identity" data-ready={loadedLogo===identity.logo?'true':'false'}><img src={identity.logo} alt={identity.name||'Logo do negócio'} onLoad={()=>setLoadedLogo(identity.logo)} onError={()=>{setLoadedLogo('');setIdentity(old=>old.logo===identity.logo?{...old,logo:''}:old);}}/></span>,host);
}
