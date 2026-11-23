import {moduleEnabled} from './module-access';
import ActionButton from './ActionButton';
import ClientPicker from './ClientPicker';
import SalesSessions from './SalesSessions';
import PixQr from './PixQr';
import {useEffect,useRef,useState} from 'react';
import type {Cart, SaleLine} from '../server/sales';
import AreaNav from './AreaNav';
import ValidatedForm from './FormValidation';
import ModuleHeading from './ModuleHeading';
import {PdvColorSettings,pdvTheme} from './pdv-theme';
import BrandIcon from './BrandIcon';
import {productCategory} from './product-category';

const stepTitles = ['PDV – Ponto de Venda', 'Selecionar produtos', 'Carrinho de venda', 'Pagamento', 'Concluir venda'] as const;
type Step = 0 | 1 | 2 | 3 | 4;
type PaymentMode = 'integral' | 'partial' | 'split';
const paymentModes = {integral:'Integral',partial:'Parcial',split:'Dividido'} as const;
const paymentChoices = {pix:'Pix',card:'Cartão (Débito / Crédito)',cash:'Dinheiro',other:'Outros'} as const;
type PaymentChoice = keyof typeof paymentChoices;
type SaleSession = {id:string; name:string; date_on:string; tier:string; financial_closed_at:string|null};
type Panel = 'options' | 'tier' | 'item' | 'client' | 'categories' | 'coupon' | 'sessions' | 'coupons' | 'payment' | 'history' | 'receipt';
const panelTitles: Record<Panel,string> = {
 options:'Opções do PDV', tier:'Tabela de preços', item:'Editar item', client:'Cliente da venda',
 categories:'Categorias', coupon:'Cupom', sessions:'Sessões de venda', coupons:'Cupons',
 payment:'Pagamento', history:'Vendas confirmadas', receipt:'Comprovante não fiscal',
};
type PaymentRow = {
 id: number; amount: string; methodId: string; accountId: string; fee: string;
 expectedOn: string; settleNow: boolean; saved: boolean;
};
type CompletedSale = {id:string;number:number;total:number;change:number;attentions:string[]};
type SaleConfirmation = CompletedSale & {received:number;remaining:number;scheduled:number;sessionName?:string};

const money=(n:number)=>(n/100).toLocaleString('pt-BR',{style:'currency',currency:'BRL'}),cents=(s:string)=>Math.round(Number(s.replace(',','.'))*100);
const tiers=['wholesale','factory','retail'] as const,labels={wholesale:'Atacado',factory:'Loja de fábrica',retail:'Varejo',custom:'Personalizado'};
async function api(path:string,method='GET',body?:unknown){const r=await fetch(new URL('api/'+path,document.baseURI),{method,headers:{'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body)});const data=await r.json();if(!r.ok)throw Error(data.message||'Não foi possível concluir.');if(method!=='GET')window.dispatchEvent(new Event('artesao-data-changed'));return data;}
export default function Sales(){
 const [catalog,setCatalog]=useState<any[]>([]),[clients,setClients]=useState<any[]>([]),[accounts,setAccounts]=useState<any[]>([]),[methods,setMethods]=useState<any[]>([]),[sales,setSales]=useState<any[]>([]),[coupons,setCoupons]=useState<any[]>([]),[search,setSearch]=useState(''),[page,setPage]=useState(1),[tier,setTier]=useState('retail'),[cart,setCart]=useState<Cart>({...(new URLSearchParams(location.search).get('session')&&!new URLSearchParams(location.search).get('attention')?{sessionId:new URLSearchParams(location.search).get('session')??undefined}:{}),clientId:null,items:[],discount:null,couponCode:'',discountChoice:'manual'}),[pricing,setPricing]=useState<{cart:Cart;data:any}|null>(null),[payments,setPayments]=useState<PaymentRow[]>([]),[receipt,setReceipt]=useState<any>(null),[receiptText,setReceiptText]=useState(''),[file,setFile]=useState<File|null>(null),[fileUrl,setFileUrl]=useState(''),[couponForm,setCouponForm]=useState<any>(null),[couponHistory,setCouponHistory]=useState<any[]|null>(null),[busy,setBusy]=useState(false),[message,setMessage]=useState('');
 const [step,setStep] = useState<Step>(0);
 const [theme,setTheme] = useState(pdvTheme);
 const [completed,setCompleted] = useState<SaleConfirmation|null>(null);
 const [panel,setPanel] = useState<Panel|null>(() => new URLSearchParams(location.search).has('session') ? 'sessions' : null);
 const [sessions,setSessions] = useState<SaleSession[]>([]);
 const [sessionAction,setSessionAction] = useState<'open'|'resume'|'close'|undefined>();
 const [category,setCategory] = useState('');
 const [paymentMode,setPaymentMode] = useState<PaymentMode>('integral');
 const [paymentChoice,setPaymentChoice] = useState<PaymentChoice>('pix');
 const [lineIndex,setLineIndex] = useState(0);
 const [paymentId,setPaymentId] = useState<number|null>(null);
 const [panelMessage,setPanelMessage] = useState('');
 const nextPayment = useRef(0);
 const dialog = useRef<HTMLDialogElement>(null);
 const scroll = useRef<HTMLDivElement>(null);
 const stageChanged = useRef(false);
 const preview = pricing?.cart === cart ? pricing.data : null;

 function goTo(next: Step) {
  if (next === step) return;
  stageChanged.current = true;
  setStep(next);
 }
 function openPanel(next: Panel) {
  setPanelMessage('');
  setPanel(next);
 }
 function openSessions(action?: 'open'|'resume'|'close') {
  setSessionAction(action);
  openPanel('sessions');
 }
 function closePanel() {
  setPanelMessage('');
  setPanel(null);
 }
 useEffect(() => {
  const sheet = dialog.current;
  if (!sheet) return;
  if (!panel) {
   if (sheet.open) sheet.close();
   return;
  }
  if (!sheet.open) sheet.showModal();
  sheet.scrollTop = 0;
  sheet.querySelector<HTMLButtonElement>('.pdv-close')?.focus({preventScroll:true});
 }, [panel]);
 useEffect(() => {
  if (!stageChanged.current) return;
  stageChanged.current = false;
  if (scroll.current) window.scrollTo({top:0,behavior:'auto'});
  document.getElementById('pdv-stage-title')?.focus({preventScroll:true});
 }, [step]);

 const keys=useRef<Record<string,{signature:string;key:string}>>({});function key(name:string,input:unknown){const signature=JSON.stringify(input);if(keys.current[name]?.signature!==signature)keys.current[name]={signature,key:crypto.randomUUID()};return keys.current[name].key;}
 async function load(){const [p,stock,c,a,m,s,u,third,recent]=await Promise.all([api('products'),api('inventory/product-stock'),api('clients'),api('finance/accounts'),api('finance/methods'),api('sales'),api('sale-coupons'),api('inventory/consigned'),api('sales-sessions').catch(()=>null)]);setCatalog([...p.filter((x:any)=>x.origin==='own').map((x:any)=>({...x,kind:'own',prices:stock.find((r:any)=>r.product_id===x.id&&r.kind==='own')?.prices??x.prices})),...third.filter((x:any)=>x.active).map((x:any)=>({...x,kind:'consigned',imageUrl:x.image_url,prices:{wholesale:null,factory:null,retail:x.sale_price}}))]);setClients(c);setAccounts(a);setMethods(m);setSales(s);setCoupons(u);if(recent)setSessions(recent);}
 useEffect(()=>{void load().catch(e=>setMessage(e.message));},[]);
 useEffect(()=>{if(!cart.items.length){return;}let active=true;const timer=setTimeout(()=>void api('sales/preview','POST',cart).then(p=>{if(active){setPricing({cart,data:p});setMessage('');}}).catch(e=>{if(active)setMessage(e.message);}),150);return()=>{active=false;clearTimeout(timer);};},[cart]);
 useEffect(()=>{if(!file){setFileUrl('');return;}const url=URL.createObjectURL(file);setFileUrl(url);return()=>URL.revokeObjectURL(url);},[file]);
 async function run(work:()=>Promise<void>){
  setBusy(true);
  setMessage('');
  try {await work(); await load();}
  catch(error) {setMessage((error as Error).message);}
  finally {setBusy(false);}
 }

 function changeLine(index: number, patch: Partial<SaleLine>) {
  setCart(old=>({...old,items:old.items.map((line,i)=>i===index?{...line,...patch}:line)}));
 }
 function removeLine(index: number) {
  setCart(old=>({...old,items:old.items.filter((_,i)=>i!==index)}));
 }
 function add(product: any) {
  const priceKey = product.prices[tier]!=null ? tier : tiers.find(t=>product.prices[t]!=null)??'custom';
  setCart(old=>{
   const ref = String(product.id);
   const index = old.items.findIndex(line=>line.ref===ref && line.kind===product.kind && line.priceKey===priceKey && line.customPriceCents===null && !line.discount);
   const line = old.items[index];
   if (line ? line.quantity>=1000000 : old.items.length>=100) return old;
   const items = line
    ? old.items.map((item,i)=>i===index?{...item,quantity:item.quantity+1}:item)
    : [...old.items,{kind:product.kind,ref,quantity:1,priceKey,customPriceCents:null,discount:null} as SaleLine];
   return {...old,items};
  });
 }
 function productFor(line: SaleLine) {
  return catalog.find(product=>product.kind===line.kind && String(product.id)===line.ref);
 }
 function unitPrice(line: SaleLine) {
  return line.priceKey==='custom' ? line.customPriceCents : productFor(line)?.prices[line.priceKey];
 }
 function resetSale() {
  setCart(old=>({...old,items:[],discount:null,couponCode:'',discountChoice:'manual'}));
  setPayments([]);
  setPaymentMode('integral');
  setPaymentChoice('pix');
  setMessage('');
 }
 function newSale() {
  resetSale();
  setCompleted(null);
  setFile(null);
  goTo(cart.sessionId ? 1 : 0);
 }

 const entered = payments.filter(row=>row.saved && cents(row.amount)>0);
 const paymentName = (row: PaymentRow) => methods.find(method=>method.id===row.methodId)?.name ?? row.methodId;
 const paymentStatus = (row: PaymentRow) => !row.saved
  ? 'Em edição'
  : row.settleNow ? 'Recebimento confirmado' : 'Agendado · a receber';
 const total = preview?.total ?? 0;
 const itemCount = cart.items.reduce((count,line)=>count+line.quantity,0);
 const gross = cart.items.reduce((sum,line)=>sum+(unitPrice(line)??0)*line.quantity,0);
 const enteredAmount = entered.reduce((sum,row)=>sum+cents(row.amount),0);
 const nonCash = entered.filter(row=>row.methodId!=='cash').reduce((sum,row)=>sum+cents(row.amount),0);
 let cashAvailable = Math.max(0,total-nonCash);
 let received = 0, scheduled = 0, change = 0;
 for (const row of entered.filter(row=>row.methodId!=='cash').concat(entered.filter(row=>row.methodId==='cash'))) {
  const amount = cents(row.amount);
  const applied = row.methodId==='cash' ? Math.min(amount,cashAvailable) : amount;
  if (row.methodId==='cash') {
   cashAvailable -= applied;
   change += amount-applied;
  }
  if (row.settleNow) received += applied;
  else scheduled += applied;
 }
 const remaining = Math.max(0,total-received);
 const paymentReady = !!preview && payments.every(row=>row.saved) && nonCash<=total;
 useEffect(()=>{if(!itemCount||completed)return;const warn=(event:BeforeUnloadEvent)=>{event.preventDefault();event.returnValue='';};window.addEventListener('beforeunload',warn);return()=>window.removeEventListener('beforeunload',warn);},[itemCount,completed]);

 function editPayment(row: PaymentRow) {
  setPaymentId(row.id);
  openPanel('payment');
 }
 const choiceMethod = (choice: PaymentChoice) => choice==='card'
  ? methods.find(m=>m.id==='debit') ?? methods.find(m=>m.id==='credit')
  : choice==='other' ? methods.find(m=>!['pix','debit','credit','cash'].includes(m.id)) ?? methods.find(m=>m.id==='cash') ?? methods[0]
  : methods.find(m=>m.id===choice);
 function addPayment() {
  const method = choiceMethod(paymentChoice);
  const pix = method?.id==='pix';
  const account = accounts.find(a=>a.active && a.id==='general') ?? accounts.find(a=>a.active);
  if (!method || !account) return;
  const row = {
   id:++nextPayment.current, amount:paymentMode==='integral' && total>enteredAmount ? ((total-enteredAmount)/100).toFixed(2) : '',
   methodId:method.id,accountId:account.id,fee:'',expectedOn:'',settleNow:!pix&&method.delay_days===0,saved:false,
  };
  setPayments(old=>[...old,row]);
  editPayment(row);
 }
 function changePayment(id: number, patch: Partial<PaymentRow>) {
  setPayments(old=>old.map(row=>row.id===id?{...row,saved:false,...patch}:row));
 }

 async function readReceiptAction(work:()=>Promise<void>) {
  setBusy(true);
  setPanelMessage('');
  try {await work();}
  catch(error) {setPanelMessage((error as Error).message);}
  finally {setBusy(false);}
 }
 async function openReceipt(id: string, withPdf = false) {
  await readReceiptAction(async()=>{
   const [sale,receiptData] = await Promise.all([api('sales/'+id),api('sales/'+id+'/receipt')]);
   setReceipt(sale);
   setReceiptText(receiptData.text);
   setFile(null);
   openPanel('receipt');
   if(withPdf)await prepare(id,sale.number);
  });
 }
 async function finalize(){
  if (!paymentReady || !preview) return;
  if (remaining>0 && !confirm('Esta venda ficará com saldo a receber de '+money(remaining)+'. Concluir mesmo assim?')) return;
  await run(async()=>{
   const input = {...cart,previewToken:preview.previewToken,payments:entered.map(p=>({
    amountCents:cents(p.amount),methodId:p.methodId,accountId:p.accountId,
    ...(p.fee!==''?{feeCents:cents(p.fee)}:{}),...(p.expectedOn?{expectedOn:p.expectedOn}:{}),settleNow:p.settleNow,
   }))};
   const result: CompletedSale = await api('sales','POST',{...input,requestKey:key('sale',input)});
   delete keys.current.sale;
   window.dispatchEvent(new Event('artesao-sale-finalized'));
   resetSale();
   setCompleted({...result,received,remaining,scheduled,sessionName:sessions.find(session=>session.id===cart.sessionId)?.name});
  });
 }
 async function prepare(id=receipt?.id,number=receipt?.number){if(!id)return;const response=await fetch(new URL('api/sales/'+id+'/receipt.pdf',document.baseURI));if(!response.ok)throw Error('Não foi possível preparar o comprovante.');setFile(new File([await response.blob()],`comprovante-venda-${number}.pdf`,{type:'application/pdf'}));}
 function discountFields(value:any,onChange:(v:any)=>void){return <><select aria-label="Tipo de desconto" value={value?.kind??''} onChange={e=>onChange(e.target.value?{kind:e.target.value,value:0}:null)}><option value="">Sem desconto</option><option value="percent">Percentual (%)</option><option value="fixed">Valor (R$)</option></select>{value&&<input aria-label="Valor do desconto" type="number" min="0" step="0.01" max={value.kind==='percent'?'100':'100000000'} value={value.kind==='percent'?value.value/100:value.value/100} onChange={e=>onChange({...value,value:cents(e.target.value)})}/>}</>;}
 const categories=[...new Set(catalog.map(productCategory).filter(Boolean))];
 const filtered=catalog.filter(p=>(!category||productCategory(p)===category)&&`${p.name} ${p.sku??''}`.toLocaleLowerCase('pt-BR').includes(search.toLocaleLowerCase('pt-BR'))),pages=Math.max(1,Math.ceil(filtered.length/20)),current=Math.min(page,pages);
 const line = cart.items[lineIndex];
 const selectedClient = clients.find(client=>client.id===cart.clientId);
 const productImage = (product:any) => <span className="pdv-thumb" aria-hidden="true">
  {product?.imageUrl ? <img src={product.imageUrl} alt="" loading="lazy" referrerPolicy="no-referrer"/> : <BrandIcon name="produtos"/>}
 </span>;
 const currentSession=sessions.find(session=>session.id===cart.sessionId && !session.financial_closed_at);
 const totalText = preview ? money(total) : '—';
 const paymentLabel = paymentId===null ? panelTitles.payment : payments.find(row=>row.id===paymentId)?.methodId==='pix' ? 'Receber por Pix' : 'Outro meio de pagamento';

 return <main className="products-screen pdv ad-module-screen" style={theme} aria-labelledby="pdv-stage-title" data-pdv-step={step}>
  <AreaNav active="vendas"/>
  <div ref={scroll} className="pdv-scroll">
   <ModuleHeading id="pdv-stage-title" symbol={step>=1&&step<=3?'store':(['store','produtos','cart','card','orcamentos'] as const)[step]} title={completed?'Venda concluída!':step>=1&&step<=3?<><span className="pdv-title-desktop">Vendas</span><span className="pdv-title-mobile">{stepTitles[step]}</span></>:stepTitles[step]} description={step===0?'Inicie um novo evento, retome um evento existente ou faça uma venda avulsa.':undefined}
    action={step===0?<ActionButton className="pdv-secondary" disabled={busy} onClick={()=>openPanel('options')}>Opções do PDV</ActionButton>:<div className="pdv-context-actions">
      <ActionButton className="pdv-secondary" disabled={busy} aria-label="Voltar uma etapa" onClick={()=>{if(completed){setCompleted(null);goTo(0);}else goTo(Math.max(0,step-1) as Step);}}><BrandIcon name="back"/>Voltar</ActionButton>
      {step===2&&itemCount>0&&<ActionButton className="pdv-ghost pdv-clear" aria-label="Esvaziar carrinho" onClick={()=>{if(confirm('Cancelar este carrinho sem alterar estoque ou caixa?')){resetSale();goTo(1);}}}><BrandIcon name="trash"/></ActionButton>}
    </div>}/>
   <p className="pdv-message" role="status">{message}</p>
   {step>=1&&step<=3&&!completed&&<div className="pdv-workspace-context"><strong>{currentSession?'Venda por sessão':'Venda rápida'}</strong>{currentSession?<><span>{currentSession.name}</span><span>{currentSession.date_on.split('-').reverse().join('/')}</span><span className="pdv-context-status">Sessão ativa</span></>:<span>Venda avulsa</span>}</div>}
   {step===0 && <div className="pdv-stack">
    <section className="pdv-entry-actions" aria-label="Iniciar venda">
     <ActionButton className="pdv-entry-action pdv-primary" aria-label={currentSession||itemCount?'Continuar venda':'Nova sessão'} aria-describedby="pdv-entry-first-description" disabled={busy} onClick={()=>currentSession||itemCount?goTo(1):openSessions('open')}>
      <span className="pdv-entry-icon"><BrandIcon name={currentSession||itemCount?'clock':'store'}/></span><span className="pdv-entry-copy"><strong>{currentSession||itemCount?'Continuar venda':'Nova sessão'}</strong><small id="pdv-entry-first-description">{currentSession?.name??(itemCount?'Retomar o carrinho em andamento':'Iniciar um evento de vendas')}</small></span><span aria-hidden="true">›</span>
     </ActionButton>
     <ActionButton className="pdv-entry-action pdv-secondary" aria-label="Retomar sessão" aria-describedby="pdv-entry-resume-description" disabled={busy} onClick={()=>openSessions('resume')}><span className="pdv-entry-icon"><BrandIcon name="clock"/></span><span className="pdv-entry-copy"><strong>Retomar sessão</strong><small id="pdv-entry-resume-description">Continuar um evento em andamento</small></span><span aria-hidden="true">›</span></ActionButton>
     <ActionButton className="pdv-entry-action pdv-soft" aria-label="Venda avulsa" aria-describedby="pdv-entry-walkin-description" disabled={busy||!!currentSession} onClick={()=>goTo(1)}><span className="pdv-entry-icon"><BrandIcon name="cart"/></span><span className="pdv-entry-copy"><strong>Venda avulsa</strong><small id="pdv-entry-walkin-description">Venda rápida, sem evento</small></span><span aria-hidden="true">›</span></ActionButton>
    </section>
    <div className="pdv-card pdv-stack pdv-recent">
     <div className="pdv-row"><h2>Sessões recentes</h2><ActionButton className="pdv-ghost pdv-inline" onClick={()=>openSessions('resume')}>Ver todas ›</ActionButton></div>
     {!sessions.length && <p className="pdv-muted">Nenhuma sessão registrada.</p>}
     {sessions.slice(0,3).map(session=><div className="pdv-row pdv-divider" key={session.id}>
      <div><strong>{session.name}</strong><div className="pdv-muted">{session.date_on.split('-').reverse().join('/')} · {session.financial_closed_at?'Encerrada':'Aberta'}</div></div>
      {!session.financial_closed_at && <ActionButton className="pdv-ghost pdv-inline" onClick={()=>{
       setCart(old=>({...old,sessionId:session.id}));setTier(session.tier);goTo(1);
      }}>Retomar ›</ActionButton>}
     </div>)}
    </div>
   </div>}

   {step>=1&&step<=3&&!completed&&<div className="pdv-desktop-workspace"><section className="pdv-desktop-panel pdv-panel-catalog" data-mobile-active={step===1}><div className="pdv-stack">
    <div className="pdv-row pdv-search-row">
     <label>Buscar produto<input placeholder="Nome ou código" value={search} onChange={e=>{setSearch(e.target.value);setPage(1);}}/></label>
     <ActionButton className="pdv-secondary" aria-label={'Tabela de preços: '+labels[tier as keyof typeof labels]} onClick={()=>openPanel('tier')}>{labels[tier as keyof typeof labels]} ▾</ActionButton>
    </div>
    <div className="pdv-category-row">
     <div className="pdv-category-chips" role="group" aria-label="Categorias do catálogo">
      {['',...categories.slice(0,2)].map(name=><ActionButton key={name} className={category===name?'pdv-primary':'pdv-secondary'} aria-pressed={category===name}
       onClick={()=>{setCategory(name);setPage(1);}}>{name||'Todos'}</ActionButton>)}
      {categories.length>2 && <ActionButton className="pdv-secondary" onClick={()=>openPanel('categories')}>Mais ▾</ActionButton>}
     </div>
    </div>
    <div className="pdv-catalog-grid">
     {filtered.slice((current-1)*20,current*20).map(product=><article className="pdv-card pdv-product" key={product.kind+':'+product.id}>
      {productImage(product)}
      <strong title={product.name}>{product.name}</strong>
      {product.sku&&<span className="pdv-muted">SKU: {product.sku}</span>}
      {product.kind==='consigned' && <span className="pdv-muted">Consignado</span>}
      <div className="pdv-row">
       <b>{product.prices[tier]==null?'Definir preço':money(product.prices[tier])}</b>
       <ActionButton className="pdv-primary" disabled={busy} aria-label={'Adicionar '+product.name} onClick={()=>add(product)}>+</ActionButton>
      </div>
     </article>)}
    </div>
    {!filtered.length && <p className="pdv-muted">Nenhum produto encontrado.</p>}
    {pages>1 && <div className="pdv-row">
     <ActionButton disabled={current<=1} onClick={()=>setPage(current-1)}>Anterior</ActionButton>
     <span>Página {current} de {pages}</span>
     <ActionButton disabled={current>=pages} onClick={()=>setPage(current+1)}>Próxima</ActionButton>
    </div>}
   </div></section>

   <section className="pdv-desktop-panel pdv-panel-cart" data-mobile-active={step===2}><div className="pdv-stack">
    <div className="pdv-row"><h2>Itens da venda</h2><ActionButton className="pdv-ghost" onClick={()=>goTo(1)}>+ Produtos</ActionButton></div>
    {!cart.items.length && <p className="pdv-muted">Adicione produtos para começar a venda.</p>}
    {cart.items.map((item,index)=>{
     const product = productFor(item);
     const name = product?.name ?? 'Produto';
     const price = unitPrice(item);
     return <article className="pdv-card pdv-item pdv-cart-item" key={index}>
      {productImage(product)}
      <div className="pdv-grow"><strong>{name}</strong><div className="pdv-muted">{product?.sku?'SKU: '+product.sku+' · ':''}{item.kind==='consigned'?'Consignado':'Próprio'}</div><div className="pdv-muted">{price==null?'Preço a definir':money(price)+' / un.'}</div>
       <ActionButton className="pdv-ghost pdv-inline" aria-label={'Editar preço de '+name} onClick={()=>{setLineIndex(index);openPanel('item');}}>Editar preço</ActionButton>
      </div>
      <div className="pdv-quantity">
       <ActionButton aria-label={'Diminuir quantidade de '+name} onClick={()=>item.quantity===1?removeLine(index):changeLine(index,{quantity:item.quantity-1})}>−</ActionButton>
       <strong aria-label={'Quantidade: '+item.quantity}>{item.quantity}</strong>
       <ActionButton disabled={item.quantity>=1000000} aria-label={'Aumentar quantidade de '+name} onClick={()=>changeLine(index,{quantity:item.quantity+1})}>+</ActionButton>
      </div>
      <b className="pdv-line-total">{price==null?'—':money(preview?.lines[index]?.total??price*item.quantity)}</b>
      <ActionButton className="pdv-ghost pdv-inline" aria-label={'Remover '+name+' do carrinho'} onClick={()=>removeLine(index)}><BrandIcon name="trash"/></ActionButton>
     </article>;
    })}
    <div className="pdv-card pdv-summary pdv-stack">
     <div className="pdv-row"><span>Cliente</span><ActionButton className="pdv-ghost" onClick={()=>openPanel('client')}>{selectedClient?.name || selectedClient?.companyName || 'Selecionar (opcional)'} ✎</ActionButton></div>
     <div className="pdv-row pdv-discount">
      <span>Desconto</span>
      <div className="pdv-toggle">
       {(['percent','fixed'] as const).map(kind=><ActionButton key={kind} className={cart.discount?.kind===kind?'pdv-primary':'pdv-secondary'}
        aria-label={kind==='percent'?'Desconto percentual':'Desconto em reais'} aria-pressed={cart.discount?.kind===kind}
        onClick={()=>setCart(old=>({...old,discount:{kind,value:old.discount?.kind===kind?old.discount.value:0}}))}>{kind==='percent'?'%':'R$'}</ActionButton>)}
      </div>
      <input aria-label="Valor do desconto da venda" type="number" min="0" step="0.01" max={cart.discount?.kind==='fixed'?100000000:100}
       value={cart.discount ? cart.discount.value/100 : ''} placeholder="0,00" onChange={e=>setCart(old=>({...old,
        discount:e.target.value===''?null:{kind:old.discount?.kind??'percent',value:cents(e.target.value)}}))}/>
     </div>
     <div className="pdv-row"><span>Cupom</span><ActionButton className="pdv-ghost" onClick={()=>openPanel('coupon')}>{cart.couponCode || 'Adicionar cupom'}</ActionButton></div>
     <div className="pdv-row pdv-divider"><span>Subtotal</span><strong>{preview?money(preview.subtotal):'—'}</strong></div>
     {!!(preview?.itemDiscount || preview?.saleDiscount || preview?.couponDiscount) && <div className="pdv-row"><span>Descontos</span><strong className="pdv-accent-text">− {money(preview.itemDiscount+preview.saleDiscount+preview.couponDiscount)}</strong></div>}
     <div className="pdv-row pdv-total-highlight"><strong>Total a pagar</strong><strong>{totalText}</strong></div>
    </div>
    {preview?.warnings.length>0 && <p className="pdv-hint">Há divergência no saldo registrado. A venda pode ser concluída e ficará registrada para conferência.</p>}
    {preview?.lines.some((item:any)=>item.kind==='consigned'&&item.finalTotal<item.quantity*(item.repass??0)) && <p className="pdv-hint">O repasse fixo do fornecedor será preservado mesmo com o desconto.</p>}
   </div></section>

   <section className="pdv-desktop-panel pdv-panel-payment" data-mobile-active={step===3}><div className="pdv-stack">
    <div className="pdv-card pdv-payment-summary">
     <div>Total da venda</div><strong className="pdv-total">{totalText}</strong>
     <div className="pdv-row pdv-payment-totals"><span className="pdv-muted">Registrado: {money(received)}</span><strong className={remaining?'pdv-amber':'pdv-accent-text'}>Falta {money(remaining)}</strong></div>
     {scheduled>0 && <p className="pdv-muted">Agendado: {money(scheduled)}</p>}
     {change>0 && <p className="pdv-muted">Troco previsto: {money(change)}</p>}
    </div>
    <div className="pdv-payment-modes" aria-label="Modo de pagamento" role="group">
     {(Object.entries(paymentModes) as [PaymentMode,string][]).map(([mode,label],index)=><ActionButton key={mode}
      className={mode===paymentMode?'pdv-primary':'pdv-secondary'} aria-pressed={mode===paymentMode} onClick={()=>setPaymentMode(mode)}>
      <BrandIcon name={(['card','clock','layers'] as const)[index]}/>{label}
     </ActionButton>)}
    </div>
    {paymentMode==='partial' && <p className="pdv-muted">Informe quanto recebeu agora.</p>}
    {paymentMode==='split' && <p className="pdv-muted">Adicione um lançamento para cada meio utilizado.</p>}
    <h2>Forma de pagamento</h2>
    <div className="pdv-card pdv-payment-methods" role="radiogroup" aria-label="Forma de pagamento">
     {(Object.entries(paymentChoices) as [PaymentChoice,string][]).filter(([choice])=>choiceMethod(choice)).map(([choice,label],index)=><label key={choice}>
      <BrandIcon name={(['pix','card','cash','menu'] as const)[index]}/>{label}
      <input type="radio" name="pdv-payment-method" checked={choice===paymentChoice} onChange={()=>setPaymentChoice(choice)}/>
     </label>)}
    </div>
    <ActionButton className="pdv-primary" disabled={!preview||!choiceMethod(paymentChoice)||!accounts.some(a=>a.active)||payments.length>=20} onClick={addPayment}>
     {paymentChoice==='pix'?'Gerar pagamento Pix':'Adicionar pagamento'}
    </ActionButton>
    {!!payments.length && <h2>Recebimentos</h2>}
    {payments.map(row=><article className="pdv-card pdv-row" key={row.id}>
     <div className="pdv-grow"><strong>{paymentName(row)}</strong><div className="pdv-muted">{paymentStatus(row)}</div>
      <ActionButton className="pdv-ghost pdv-inline" onClick={()=>editPayment(row)}>Editar</ActionButton>
     </div>
     <div className="pdv-end"><strong>{money(cents(row.amount)||0)}</strong><br/>
      <ActionButton className="pdv-ghost pdv-inline" aria-label={'Remover pagamento em '+paymentName(row)} onClick={()=>setPayments(old=>old.filter(item=>item.id!==row.id))}>Remover</ActionButton>
     </div>
    </article>)}
    {payments.some(row=>!row.saved) && <p className="pdv-hint">Salve ou remova os pagamentos em edição para revisar a venda.</p>}
    {preview && nonCash>total && <p className="pdv-hint">Os pagamentos sem dinheiro superam o total da venda.</p>}
    <p className="pdv-hint">Confira o recebimento do Pix antes de registrá-lo. A venda pode ficar com saldo pendente.</p>
    <ActionButton className="pdv-primary pdv-full pdv-desktop-review" disabled={!paymentReady||busy} onClick={()=>goTo(4)}>Revisar conclusão</ActionButton>
   </div></section></div>}

   {step===4 && (completed ? <div className="pdv-stack">
    <div className="pdv-success" role="status">
     <span className="pdv-success-mark" aria-hidden="true">✓</span>
     <p className="pdv-confirmation-title">Venda concluída!</p>
     <p>{completed.sessionName || 'Venda avulsa'} · Nº {completed.number}</p>
    </div>
    <div className="pdv-card pdv-completed">
     <div className="pdv-row"><span>Total da venda</span><strong>{money(completed.total)}</strong></div>
     <div className="pdv-row pdv-divider"><span>Pago agora</span><strong>{money(completed.received)}</strong></div>
     {completed.scheduled>0 && <div className="pdv-row"><span>Agendado</span><strong>{money(completed.scheduled)}</strong></div>}
     <div className="pdv-row pdv-total-highlight"><strong>Saldo a receber</strong><strong>{money(completed.remaining)}</strong></div>
     {completed.change>0 && <p>Troco: {money(completed.change)}</p>}
    </div>
    <div className="pdv-stack pdv-receipt-actions">
     <ActionButton className="pdv-primary" disabled={busy} onClick={()=>openReceipt(completed.id,true)}><BrandIcon name="share"/>Enviar comprovante</ActionButton>
     <ActionButton className="pdv-secondary" disabled={busy} onClick={()=>openReceipt(completed.id,true)}><BrandIcon name="print"/>Imprimir</ActionButton>
     <ActionButton className="pdv-secondary" disabled={busy} onClick={newSale}><BrandIcon name="cart"/>Nova venda</ActionButton>
     {currentSession && <ActionButton className="pdv-secondary" disabled={busy} onClick={()=>openSessions('close')}>Fechar sessão</ActionButton>}
    </div>
    {!!completed.attentions.length && <p className="pdv-hint">Divergência registrada para conferência.</p>}
   </div> : <div className="pdv-stack">
    <h2>Revisão final</h2>
    <div className="pdv-card pdv-stack">
     <div className="pdv-row"><span>Itens</span><strong>{itemCount}</strong></div>
     {preview?.lines.map((item:any,index:number)=><div className="pdv-row pdv-muted" key={index}><span>{item.quantity} × {item.name}</span><strong>{money(item.finalTotal)}</strong></div>)}
     <div className="pdv-row"><span>Cliente</span><strong>{selectedClient?.name || selectedClient?.companyName || 'Não informado'}</strong></div>
     <div className="pdv-row"><span>Total</span><strong className="pdv-total">{totalText}</strong></div>
     {(preview?.itemDiscount>0 || preview?.saleDiscount>0 || preview?.couponDiscount>0) && <p className="pdv-muted">Descontos: {money(preview.itemDiscount+preview.saleDiscount)} · Cupom: {money(preview.couponDiscount)}</p>}
     <div className="pdv-divider"/>
     {entered.map(row=><div className="pdv-row" key={row.id}><span>{paymentName(row)} <small className="pdv-muted">· {paymentStatus(row)}</small></span><strong>{money(cents(row.amount))}</strong></div>)}
     {change>0 && <div className="pdv-row"><span>Troco</span><strong>{money(change)}</strong></div>}
     {scheduled>0 && <div className="pdv-row"><span>Agendado</span><strong>{money(scheduled)}</strong></div>}
     <div className="pdv-row"><span>Saldo a receber</span><strong className={remaining?'pdv-amber':'pdv-accent-text'}>{money(remaining)}</strong></div>
    </div>
    {remaining>0 && <p className="pdv-hint">Confirme o saldo a receber ao concluir a venda.</p>}
   </div>)}
  </div>

  {step>0&&!completed&& <footer className="pdv-footer">
   {step===1 && <ActionButton className="pdv-primary pdv-full" disabled={busy||!itemCount} onClick={()=>goTo(2)}>
    <BrandIcon name="cart"/> {itemCount} {itemCount===1?'item':'itens'} · {money(preview?.subtotal??gross)} ›
   </ActionButton>}
   {step===2 && <ActionButton className="pdv-primary pdv-full" disabled={busy||!preview} onClick={()=>goTo(3)}>Avançar para pagamento</ActionButton>}
   {step===3 && <div className="pdv-actions">
    <ActionButton className="pdv-secondary" disabled={busy} onClick={()=>goTo(2)}>Voltar</ActionButton>
    <ActionButton className="pdv-primary" disabled={busy||!paymentReady} onClick={()=>goTo(4)}>Revisar conclusão</ActionButton>
   </div>}
   {step===4 && <div className="pdv-actions">
    <ActionButton className="pdv-secondary" disabled={busy} onClick={()=>goTo(3)}>Voltar</ActionButton>
    <ActionButton className="pdv-primary" disabled={!paymentReady||busy} onClick={finalize}>Concluir venda</ActionButton>
   </div>}
  </footer>}
  {step>0&&!completed&&<nav className="pdv-nav" aria-label="Navegação do PDV">
    <ActionButton disabled={busy} onClick={()=>goTo(0)}><BrandIcon name="store"/>PDV</ActionButton>
    <ActionButton disabled={busy} aria-current={step===1?'page':undefined} onClick={()=>goTo(1)}><BrandIcon name="produtos"/>Catálogo</ActionButton>
    <ActionButton disabled={busy} aria-current={step>=2?'page':undefined} onClick={()=>goTo(2)}><BrandIcon name="cart"/>Carrinho</ActionButton>
    <ActionButton disabled={busy} onClick={()=>openPanel('options')}><BrandIcon name="menu"/>Mais</ActionButton>
  </nav>}

  <dialog ref={dialog} className="pdv-sheet" aria-labelledby="pdv-sheet-title"
   onCancel={event=>{event.preventDefault();closePanel();}}
   onClick={event=>{if(event.target===event.currentTarget){const rect=event.currentTarget.getBoundingClientRect();if(event.clientX<rect.left||event.clientX>rect.right||event.clientY<rect.top||event.clientY>rect.bottom)closePanel();}}}>
   <div className="pdv-row pdv-sheet-head"><h2 id="pdv-sheet-title">{panel==='payment'?paymentLabel:panel?panelTitles[panel]:''}</h2>
    <ActionButton className="pdv-close" aria-label="Fechar janela" onClick={closePanel}>×</ActionButton></div>
   <p className="pdv-message" role="status">{panelMessage || ((panel==='coupons'||panel==='history')?message:'')}</p>
   {panel==='options' && <div className="pdv-stack">
    <ActionButton onClick={()=>{closePanel();setCompleted(null);goTo(0);}}>Início do PDV</ActionButton>
    <ActionButton onClick={()=>openPanel('history')}>Vendas anteriores</ActionButton>
    <ActionButton onClick={()=>openSessions()}>{cart.sessionId?'Sessão selecionada':'Sessão de venda'}</ActionButton>
    <ActionButton onClick={()=>openPanel('coupons')}>Gerenciar cupons</ActionButton>
    {itemCount>0 && <ActionButton onClick={()=>{if(confirm('Cancelar este carrinho sem alterar estoque ou caixa?')){resetSale();closePanel();goTo(0);}}}>Cancelar carrinho</ActionButton>}
    <details><summary>Configurações do PDV</summary><PdvColorSettings onSaved={()=>setTheme(pdvTheme())}/></details>
    <details><summary>Outras operações</summary>
  <p><a href="?view=consignados">Cadastrar e receber consignados</a></p>
  <p><a href="?view=pagamentos">Configurar contas e formas de pagamento</a></p>
  {moduleEnabled('pedidos') && <p><a href="?view=pedidos">Pedido direto</a></p>}
  {moduleEnabled('orcamentos') && <p><a href="?view=orcamentos">Orçamento</a></p>}
 </details>
   </div>}
   {panel==='tier' && <div className="pdv-stack">{[...tiers].reverse().map(value=><ActionButton key={value} className={tier===value?'pdv-primary':'pdv-secondary'} aria-pressed={tier===value}
    onClick={()=>{setTier(value);closePanel();}}>{labels[value]}</ActionButton>)}</div>}
   {panel==='item' && line && <div className="pdv-stack">
    <strong>{productFor(line)?.name??'Produto'}</strong>
    <label>Quantidade<input type="number" min="1" max="1000000" step="1" value={line.quantity} onChange={e=>changeLine(lineIndex,{quantity:Number(e.target.value)})}/></label>
    <label>Faixa do item<select aria-label="Faixa do item" value={line.priceKey} onChange={e=>changeLine(lineIndex,{priceKey:e.target.value as SaleLine['priceKey']})}>
     {[...tiers,'custom' as const].map(value=><option key={value} value={value}>{labels[value]}{value!=='custom'&&productFor(line)?.prices[value]!=null?' · '+money(productFor(line).prices[value]):''}</option>)}
    </select></label>
    {line.priceKey==='custom' && <label>Preço personalizado unitário (R$)<input type="number" min="0" step="0.01" value={line.customPriceCents===null?'':line.customPriceCents/100}
     onChange={e=>changeLine(lineIndex,{customPriceCents:e.target.value===''?null:cents(e.target.value)})}/></label>}
    <span>Desconto do item (total da linha)</span>{discountFields(line.discount,value=>changeLine(lineIndex,{discount:value}))}
    <ActionButton className="pdv-primary" onClick={closePanel}>Concluir ajuste</ActionButton>
    <ActionButton className="pdv-ghost" onClick={()=>{removeLine(lineIndex);closePanel();}}>Remover item</ActionButton>
   </div>}
   {panel==='client' && <ClientPicker persistent context="sale" sessionId={cart.sessionId} selected={selectedClient??null} onSelect={client=>{
    if(client)setClients(old=>old.some(item=>item.id===client.id)?old.map(item=>item.id===client.id?client:item):[...old,client]);
    setCart(old=>({...old,clientId:client?.id??null}));
   }}/>}
   {panel==='categories' && <div className="pdv-stack">{categories.map(name=><ActionButton key={name} className={category===name?'pdv-primary':'pdv-secondary'}
    onClick={()=>{setCategory(name);setPage(1);closePanel();}}>{name}</ActionButton>)}</div>}
   {panel==='coupon' && <div className="pdv-stack">
    <label>Código do cupom<input maxLength={40} value={cart.couponCode} onChange={e=>setCart(old=>({...old,couponCode:e.target.value,discountChoice:e.target.value?'coupon':'manual'}))}/></label>
    {cart.couponCode && <label>Como aplicar descontos<select value={cart.discountChoice} onChange={e=>setCart(old=>({...old,discountChoice:e.target.value as Cart['discountChoice']}))}>
     <option value="coupon">Usar somente cupom</option><option value="manual">Usar somente desconto manual</option><option value="combine">Combinar (somente se o cupom permitir)</option>
    </select></label>}
    <ActionButton className="pdv-primary" onClick={closePanel}>Aplicar cupom</ActionButton>
   </div>}
   {panel==='sessions' && <SalesSessions initialAction={sessionAction==='resume'?undefined:sessionAction} sessionId={cart.sessionId} catalog={catalog} onSelect={(id, selectedTier) => {
    setCart(old => {
     const next = {...old};
     if (id) next.sessionId = id;
     else delete next.sessionId;
     return next;
    });
    if (selectedTier) setTier(selectedTier);
    if(step===0&&(sessionAction==='open'||sessionAction==='resume')){closePanel();goTo(1);}
   }} onDone={load}/>}
   {panel==='history' && <div className="pdv-stack">{!sales.length && <p className="pdv-muted">Nenhuma venda confirmada.</p>}{sales.map(s=><p key={s.id}>Venda {s.number} · {s.registered_at} · {money(s.total_cents)} <ActionButton disabled={busy} onClick={()=>openReceipt(s.id)}>Consultar comprovante</ActionButton></p>)}{sales.length>=200&&<ActionButton disabled={busy} onClick={()=>{setBusy(true);return api('sales?before='+sales[sales.length-1].number).then(rows=>setSales(old=>[...old,...rows])).catch(e=>setMessage(e.message)).finally(()=>setBusy(false));}}>Carregar vendas anteriores</ActionButton>}</div>}
   {panel==='coupons' && <div className="pdv-stack"><ActionButton disabled={busy} onClick={()=>setCouponForm({code:'',kind:'percent',value:'',startsOn:'',endsOn:'',maxUses:'',active:true,allowManual:false})}>Cadastrar cupom</ActionButton>{coupons.map(c=><p key={c.id}>{c.code} · {c.kind==='percent'?c.value/100+'%':money(c.value)} · Usos {c.uses}/{c.max_uses??'sem limite'} · {c.active?'Ativo':'Inativo'} <ActionButton disabled={busy} onClick={()=>setCouponForm({id:c.id,expectedRevision:c.revision,code:c.code,kind:c.kind,value:String(c.value/100),startsOn:c.starts_on??'',endsOn:c.ends_on??'',maxUses:c.max_uses===null?'':String(c.max_uses),active:!!c.active,allowManual:!!c.allow_manual})}>Editar cupom</ActionButton><ActionButton disabled={busy} onClick={()=>run(async()=>setCouponHistory(await api('sale-coupons/'+c.id+'/history')))}>Histórico de usos</ActionButton></p>)}{couponHistory&&<section><h3>Aplicações confirmadas</h3>{couponHistory.map(u=><p key={u.id}>Venda {u.number} · {u.registered_at} · Desconto {money(u.discount_cents)}</p>)}</section>}{couponForm&&<ValidatedForm onSubmit={e=>{e.preventDefault();const body={...couponForm,value:cents(couponForm.value),maxUses:couponForm.maxUses===''?null:Number(couponForm.maxUses)};return run(async()=>{await api('sale-coupons','POST',{...body,requestKey:key('coupon',body)});delete keys.current.coupon;setCouponForm(null);});}}><fieldset disabled={busy}><label>Código do cupom<input required minLength={3} maxLength={40} pattern="[A-Za-z0-9_-]+" value={couponForm.code} onChange={e=>setCouponForm({...couponForm,code:e.target.value})}/></label><label>Tipo<select value={couponForm.kind} onChange={e=>setCouponForm({...couponForm,kind:e.target.value})}><option value="percent">Percentual (%)</option><option value="fixed">Valor fixo (R$)</option></select></label><label>Valor do cupom<input required type="number" min="0" max={couponForm.kind==='percent'?'100':'100000000'} step="0.01" value={couponForm.value} onChange={e=>setCouponForm({...couponForm,value:e.target.value})}/></label><label>Início (opcional)<input type="date" value={couponForm.startsOn} onChange={e=>setCouponForm({...couponForm,startsOn:e.target.value})}/></label><label>Fim (opcional)<input type="date" value={couponForm.endsOn} onChange={e=>setCouponForm({...couponForm,endsOn:e.target.value})}/></label><label>Limite de usos (opcional)<input type="number" min="1" step="1" value={couponForm.maxUses} onChange={e=>setCouponForm({...couponForm,maxUses:e.target.value})}/></label><label><input type="checkbox" checked={couponForm.active} onChange={e=>setCouponForm({...couponForm,active:e.target.checked})}/>Ativo</label><label><input type="checkbox" checked={couponForm.allowManual} onChange={e=>setCouponForm({...couponForm,allowManual:e.target.checked})}/>Permitir combinar com desconto manual (desativado por padrão)</label><ActionButton>Salvar cupom</ActionButton><ActionButton type="button" onClick={()=>setCouponForm(null)}>Cancelar</ActionButton></fieldset></ValidatedForm>}</div>}
   {panel==='receipt' && receipt && <div className="pdv-stack sales-receipt"><h3>Venda {receipt.number}</h3><pre className="stock-snapshot">{receiptText}</pre><ActionButton disabled={busy} onClick={()=>readReceiptAction(prepare)}>Preparar comprovante PDF</ActionButton>{file&&fileUrl&&<><p><a href={fileUrl} download={file.name}>Baixar PDF</a> · <a href={fileUrl} target="_blank" rel="noopener">Abrir para impressão</a></p>{navigator.canShare?.({files:[file]})&&<ActionButton onClick={()=>navigator.share({files:[file],title:'Comprovante não fiscal'}).catch(()=>setPanelMessage('Compartilhamento cancelado ou indisponível. Use Baixar PDF.'))}>Compartilhar PDF</ActionButton>}<a href={'https://wa.me/?text='+encodeURIComponent(receiptText)} target="_blank" rel="noopener">Abrir texto no WhatsApp</a><p>O WhatsApp abre com o texto; anexe o PDF baixado se desejar. Não há envio automático.</p></>}</div>}
   {payments.map(row=><div key={row.id} hidden={panel!=='payment'||paymentId!==row.id}>
    <ValidatedForm onSubmit={event=>{
     event.preventDefault();
     if(row.methodId==='pix'&&!row.settleNow&&!row.expectedOn){
      setPanelMessage('Confirme o recebimento do Pix no banco ou informe uma data prevista.');
      return;
     }
     changePayment(row.id,{saved:true});
     closePanel();
    }}>
     <div className="pdv-stack">
      {row.methodId==='pix' && <div className="pdv-row"><span>Valor a receber</span><strong className="pdv-total">{money(cents(row.amount)||0)}</strong></div>}
      <label>Forma de pagamento<select aria-label="Forma de pagamento" value={row.methodId} onChange={e=>{
       const method=methods.find(m=>m.id===e.target.value);
       if(method)changePayment(row.id,{methodId:method.id,fee:'',expectedOn:'',settleNow:method.id!=='pix'&&method.delay_days===0});
      }}>{methods.map(m=><option key={m.id} value={m.id}>{m.name}</option>)}</select></label>
      <label>Valor (R$)<input aria-label="Valor (R$)" required type="number" min="0.01" step="0.01" value={row.amount} onChange={e=>changePayment(row.id,{amount:e.target.value,...(row.methodId==='pix'?{settleNow:false}:{})})}/></label>
      <label>Conta<select aria-label="Conta" required value={row.accountId} onChange={e=>changePayment(row.id,{accountId:e.target.value})}>{accounts.filter(a=>a.active).map(a=><option key={a.id} value={a.id}>{a.name}</option>)}</select></label>
      {row.methodId==='pix' && Number.isFinite(cents(row.amount)) && cents(row.amount)>0 && <PixQr amountCents={cents(row.amount)} onPaid={()=>{
       setPayments(old=>old.map(item=>item.id===row.id?{...item,settleNow:true}:item));
      }}/>}
      <details><summary>Taxa e prazo</summary>
       <label>Taxa (R$; vazio usa padrão)<input type="number" min="0" step="0.01" value={row.fee} onChange={e=>changePayment(row.id,{fee:e.target.value})}/></label>
       <label>Data prevista<input type="date" value={row.expectedOn} onChange={e=>changePayment(row.id,{expectedOn:e.target.value,settleNow:row.methodId!=='pix'&&!!e.target.value&&e.target.value<=new Date().toISOString().slice(0,10)})}/></label>
      </details>
      <label className="pdv-check"><input type="checkbox" checked={row.settleNow} onChange={e=>changePayment(row.id,{settleNow:e.target.checked})}/>
       {row.methodId==='pix'?'Confirmei o recebimento no banco':'Liquidado na conta'}
      </label>
      <ActionButton className="pdv-primary" disabled={busy}>Salvar pagamento</ActionButton>
     </div>
    </ValidatedForm>
   </div>)}
  </dialog>
 </main>;
}
