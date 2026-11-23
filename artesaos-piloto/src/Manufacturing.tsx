import {appName} from './branding';
import MaterialUpgradeNotice from './MaterialUpgradeNotice';
import {useState} from 'react';
import AreaNav,{SettingsLink} from './AreaNav';
import ProductForm from './ProductForm';
import './products.css';
export default function Manufacturing(){
 const [cycle,setCycle]=useState(0),[dirty,setDirty]=useState(false);
 return <main className="products-screen"><header><span className="brand">{appName}</span></header><AreaNav active="fabricacao"/><h1>Fabricação</h1><SettingsLink area="fabricacao"/><p>Cadastre um produto completo, começando pelos dados de fabricação. Para editar produtos existentes, use a lista de Produtos.</p><MaterialUpgradeNotice/><ProductForm key={cycle} context="fabricacao" onDirtyChange={setDirty} onSaved={()=>setDirty(false)}/><button type="button" onClick={()=>{if(dirty&&!confirm('Descartar as alterações não salvas?'))return;setDirty(false);setCycle(n=>n+1);}}>Novo produto</button></main>;
}
