import {useEffect,useState,type ReactNode} from 'react';
import Welcome from './Welcome';
export default function PilotGate({children,allowBeforeSetup=false}:{children:ReactNode;allowBeforeSetup?:boolean}){
 const [complete,setComplete]=useState<boolean|null>(null),[error,setError]=useState('');
 useEffect(()=>{let active=true;fetch(new URL('api/onboarding',document.baseURI)).then(async response=>{if(!response.ok)throw Error('Não foi possível verificar os dados iniciais. Atualize a página para tentar novamente.');return response.json();}).then(result=>{if(active)setComplete(result.complete);}).catch(reason=>{if(active)setError(reason.message);});return()=>{active=false;};},[]);
 if(allowBeforeSetup||complete)return children;
 if(complete===null)return <main className="products-screen"><h1>Preparando seu acesso</h1><p role={error?'alert':'status'}>{error||'Verificando os dados iniciais…'}</p></main>;
 return <Welcome/>;
}
