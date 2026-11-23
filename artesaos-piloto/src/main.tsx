import MaterialSettings from './MaterialSettings';
import {viewEnabled} from './module-access';
import OfflineBoundary from './OfflineBoundary';
import ActionButton from './ActionButton';
import Help from './Help';
import LegalGate from './LegalGate';
import {appName} from './branding';
import ValidatedForm from './FormValidation';
import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './style.css';
import Quotes from './Quotes';
import Settings from './Settings';
import PilotSettings from './PilotSettings';
import PilotGate from './PilotGate';
import SupportHub from './SupportHub';
import Manufacturing from './Manufacturing';
import AreaNav,{areaNames,type Area} from './AreaNav';
import Clients from './Clients';
import Products from './Products';
import QuoteWireframe from './QuoteWireframe';

const Sales=React.lazy(()=>import('./Sales'));
const Finance=React.lazy(()=>import('./Finance'));
const Orders=React.lazy(()=>import('./Orders'));

const ConsignedInventory=React.lazy(()=>import('./ConsignedInventory'));
const PaymentSettings=React.lazy(()=>import('./PaymentSettings'));
const ProductInventory=React.lazy(()=>import('./ProductInventory'));

async function request(path: string, options?: RequestInit) {
  const response = await fetch(new URL(path, document.baseURI), options);
  if (!response.ok) throw new Error('Não foi possível concluir a operação. Verifique os logs do aplicativo.');
  return response.json();
}
function App() {
  const [health, setHealth] = useState<{status:string;database:string;arch:string;node:string}>();
  const [text, setText] = useState('');
  const [saved, setSaved] = useState<string | null>(null);
  const [message, setMessage] = useState('Carregando diagnóstico…');
  const [busy, setBusy] = useState(true);
  useEffect(() => {
    Promise.all([request('api/health'), request('api/note')])
      .then(([h, n]) => { setHealth(h); setText(n.text); setSaved(n.updated_at); setMessage('Ambiente conectado.'); })
      .catch(e => setMessage(e.message)).finally(() => setBusy(false));
  }, []);
  async function save(event: React.FormEvent) {
    event.preventDefault(); setBusy(true);
    try {
      const n = await request('api/note', { method:'PUT', headers:{'Content-Type':'application/json'}, body:JSON.stringify({text}) });
      setSaved(n.updated_at); setMessage('Anotação salva. Reinicie o aplicativo e abra esta tela para conferir a persistência.');
    } catch(e) { setMessage(e instanceof Error ? e.message : 'Falha ao salvar.'); }
    finally { setBusy(false); }
  }
  return <main>
    <header><span className="brand">{appName}</span><span className="badge">Validação da instalação</span></header>
    <AreaNav/><h1>Diagnóstico da instalação</h1><section><h2>Catálogo persistente</h2><a href="?view=orcamentos">Abrir Orçamentos</a> · <a href="?view=produtos">Abrir Produtos</a> · <a href="?view=clientes">Abrir Clientes</a></section>
    <section><h2>Fluxo em avaliação</h2><p>Experimente cadastrar um produto dentro do orçamento. O wireframe usa dados temporários e não altera a anotação do banco.</p><a href="?view=produto">Abrir wireframe: produto no orçamento</a></section>
    <p>Esta tela verifica interface, servidor e banco. Orçamentos e cadastros são persistentes. Fabricação calcula custos configurados; frete e envio continuam manuais.</p>
    <section aria-labelledby="diagnostic"><h2 id="diagnostic">Diagnóstico</h2>
      <dl><div><dt>API</dt><dd>{health?.status ?? 'Não verificada'}</dd></div>
      <div><dt>SQLite</dt><dd>{health?.database ?? 'Não verificado'}</dd></div>
      <div><dt>Arquitetura</dt><dd>{health?.arch ?? '—'}</dd></div>
      <div><dt>Node.js</dt><dd>{health?.node ?? '—'}</dd></div></dl>
    </section>
    <section><h2>Teste de persistência</h2><p>Escreva algo sem dados pessoais, salve e reinicie o aplicativo pelo Home Assistant. A anotação deve continuar aqui.</p>
      <ValidatedForm onSubmit={save}><label htmlFor="note">Anotação de teste</label>
      <textarea id="note" maxLength={500} value={text} onChange={e => setText(e.target.value)} disabled={busy || !health} />
      <ActionButton disabled={busy || !health}>{busy ? 'Aguarde…' : 'Salvar anotação'}</ActionButton></ValidatedForm>
      <p>Última gravação: {saved ? new Date(saved).toLocaleString('pt-BR') : 'nenhuma'}</p>
    </section><p role="status">{message}</p>
  </main>;
}
declare const __APP_VERSION__: string;
const query=new URLSearchParams(window.location.search);
const view=query.get('view');
const area=query.get('area');
function StartupRoute({children}:{children:React.ReactNode}){const [ready,setReady]=useState(!!view);useEffect(()=>{if(view)return;let active=true;fetch(new URL('api/operational-preferences',document.baseURI)).then(async response=>{if(!response.ok)throw Error();return response.json();}).then(data=>{if(!active)return;const prefer=data.preferences.prioritize_sales&&data.openSession;const chosen=prefer?'vendas':data.preferences.home_view;const target=viewEnabled(chosen)?chosen:'produtos';if(target!=='produtos'){const url=new URL(location.href);url.searchParams.set('view',target);if(prefer)url.searchParams.set('session',data.openSession.id);location.replace(url.href);}else setReady(true);}).catch(()=>{if(active)setReady(true);});return()=>{active=false;};},[]);return ready?children:<main><p role="status">Carregando tela inicial…</p></main>;}
const pilotPage=!viewEnabled(view??'produtos')?<main className="products-screen"><AreaNav/><h1>Módulo ainda não liberado</h1><p>Solicite a liberação ao administrador. Seus dados foram preservados.</p><a href="?view=suporte">Abrir suporte</a></main>:view==='consignados'?<main className="products-screen"><AreaNav active="vendas"/><ConsignedInventory contextual/></main>:view==='materiais'?<main className="products-screen"><AreaNav/><h1>Materiais da fabricação</h1><MaterialSettings/></main>:view==='pagamentos'?<PaymentSettings/>:view==='fabricacao'?<Manufacturing/>:view==='ajuda'?<Help/>:view==='vendas'?<Sales/>:view==='financeiro'?<Finance/>:view==='pedidos'?<Orders/>:view==='estoque'?<ProductInventory/>:view==='suporte'?<SupportHub/>:view==='configuracoes'?<PilotSettings/>:view==='orcamentos'?<Quotes/>:view==='clientes'?<Clients/>:view==='produto'?<QuoteWireframe/>:view==='diagnostico'?<App/>:<Products/>;
const page = appName==='Artesão Digital'?<LegalGate><PilotGate allowBeforeSetup={view==='suporte'||view==='ajuda'}><StartupRoute><React.Suspense fallback={<main><p role="status">Carregando área…</p></main>}>{pilotPage}</React.Suspense></StartupRoute></PilotGate></LegalGate>:(view==='configuracoes'&&area&&Object.hasOwn(areaNames,area)?<Settings area={area as Area}/>:view==='fabricacao'?<Manufacturing/>:view==='orcamentos'?<Quotes/>:view==='clientes'?<Clients/>:view==='produtos'?<Products/>:view==='produto'?<QuoteWireframe/>:view==='diagnostico'?<App/>:<Quotes/>);
createRoot(document.getElementById('root')!).render(<><small className="app-version" aria-label={`Versão ${__APP_VERSION__}`}>v{__APP_VERSION__}</small>{appName==='Artesão Digital'?<OfflineBoundary>{page}</OfflineBoundary>:page}</>);
