import {appName} from './branding';
import ValidatedForm,{showValidation} from './FormValidation';
import ModalClose from './ModalClose';
import { useEffect, useRef, useState, type FormEvent } from 'react';
import './wireframe.css';
import {clientLabel} from './client-model';
import ClientPicker, { type Client } from './ClientPicker';

type ProductData = {
  name: string; description: string; price: string; included: string;
  length: string; width: string; height: string; weight: string;
  private: boolean;
  origin: '' | 'own' | 'client';
};
type ProductForm = ProductData & { quantity: string; catalog: boolean };
type CatalogProduct = ProductData & { id: number };
type Item = ProductForm & {
  id: number;
  individualPackaging: '' | 'none' | 'with';
  packagingType: string;
  packagingPrice: string;
  packagingIncluded: boolean;
};
const productData = (value: ProductData): ProductData => ({
  name: value.name, description: value.description, price: value.price, included: value.included,
  length: value.length, width: value.width, height: value.height, weight: value.weight,
  private: value.private, origin: value.origin,
});
const emptyPackaging = () => ({ individualPackaging: '' as Item['individualPackaging'], packagingType: '', packagingPrice: '', packagingIncluded: false });
const emptyProduct = (): ProductForm => ({
  name: '', description: '', price: '', included: '', length: '', width: '',
  height: '', weight: '', quantity: '1', private: true, catalog: false, origin: '',
});
const validOrigin = (origin: ProductForm['origin']) => origin === 'own' || origin === 'client';
const originLabel = (origin: ProductForm['origin']) => origin === 'own' ? 'Próprio' : origin === 'client' ? 'De cliente' : 'Origem não informada';
const packagingLabel = (product: Item) => product.individualPackaging === 'none'
  ? 'Sem embalagem individual'
  : product.individualPackaging === 'with'
    ? `Com embalagem individual: ${product.packagingType.trim() || 'tipo a definir'}`
    : 'Embalagem individual a definir';
const money = (cents: number) => (cents / 100).toLocaleString('pt-BR', { style: 'currency', currency: 'BRL' });
const cents = (value: string): number | null => {
  if (!/^\d+(?:[.,]\d{1,2})?$/.test(value.trim())) return null;
  const [whole, fraction = ''] = value.trim().replace(',', '.').split('.');
  const result = Number(whole) * 100 + Number(fraction.padEnd(2, '0'));
  return Number.isSafeInteger(result) ? result : null;
};
const packagingCents = (item: Item) => item.individualPackaging === 'none' || (item.individualPackaging === 'with' && item.packagingIncluded)
  ? 0 : item.individualPackaging === 'with' ? cents(item.packagingPrice) : null;
const quantityNumber = (value: string): number | null => {
  const number = Number(value);
  return /^\d+$/.test(value.trim()) && Number.isSafeInteger(number) && number > 0 ? number : null;
};
const lineAmount = (unitCents: number | null, quantity: string): number | null => {
  const number = quantityNumber(quantity);
  if (unitCents === null || number === null) return null;
  const amount = unitCents * number;
  return Number.isSafeInteger(amount) ? amount : null;
};

export default function QuoteWireframe() {
  const [screen, setScreen] = useState<'editor' | 'list' | 'catalog'>('editor');
  const [selectedClient, setSelectedClient] = useState<Client | null>(null);
  const client = selectedClient?clientLabel(selectedClient):'';
  const taxDocument = selectedClient?.taxDocument ?? '';
  const postal = selectedClient?.postal ?? '';
  const [notes, setNotes] = useState('');
  const [items, setItems] = useState<Item[]>([]);
  const [catalog, setCatalog] = useState<CatalogProduct[]>([]);
  const [catalogSearch, setCatalogSearch] = useState('');
  const [selectedCatalogIds, setSelectedCatalogIds] = useState<number[]>([]);
  const [draft, setDraft] = useState<ProductForm>(emptyProduct);
  const [editing, setEditing] = useState<number | null>(null);
  const [error, setError] = useState('');
  const [status, setStatus] = useState('');
  const initial=useRef('');
  const [dirty, setDirty] = useState(false);
  const [recentlyAddedId, setRecentlyAddedId] = useState<number | null>(null);
  const dialog = useRef<HTMLDialogElement>(null);
  const catalogDropdown = useRef<HTMLDetailsElement>(null);
  useEffect(() => {
    const closeOnOutsideClick = (event: PointerEvent) => {
      const dropdown = catalogDropdown.current;
      if (dropdown?.open && !dropdown.contains(event.target as Node)) dropdown.open = false;
    };
    document.addEventListener('pointerdown', closeOnOutsideClick);
    return () => document.removeEventListener('pointerdown', closeOnOutsideClick);
  }, []);
  useEffect(() => {
    if (recentlyAddedId === null) return;
    const item = document.getElementById(`wf-item-${recentlyAddedId}`);
    item?.scrollIntoView({ behavior: window.matchMedia('(prefers-reduced-motion: reduce)').matches ? 'auto' : 'smooth', block: 'start' });
    item?.focus({ preventScroll: true });
  }, [recentlyAddedId]);
  const nextId = useRef(1);
  const trigger = useRef<HTMLElement | null>(null);
  const subtotal = items.reduce((sum, p) => sum + (lineAmount(cents(p.price), p.quantity) ?? 0), 0);
  const packagingSubtotal = items.reduce((sum, p) => sum + (lineAmount(packagingCents(p), p.quantity) ?? 0), 0);
  const totalsPending = items.some(p => lineAmount(cents(p.price), p.quantity) === null || lineAmount(packagingCents(p), p.quantity) === null);
  const physicalPending = items.some(p => !p.length || !p.width || !p.height || !p.weight);
  const packagingSummary = items.length === 0 || items.some(p => !p.individualPackaging)
    ? 'há itens a definir'
    : items.every(p => p.individualPackaging === 'none')
      ? 'sem embalagem individual nos itens'
      : 'definidas por produto; conferir custos e compatibilidade';

  function open(item?: Item) {
    trigger.current = document.activeElement as HTMLElement;
    const value=item ? { ...productData(item), quantity: item.quantity, catalog: item.catalog, private: item.origin !== 'own' || item.private } : emptyProduct();initial.current=JSON.stringify(value);setDraft(value);
    setEditing(item?.id ?? null); setError(''); setDirty(false);
    dialog.current?.showModal();
  }
  function close(force = false) {
    if (!force && dirty && JSON.stringify(draft)!==initial.current && !window.confirm('Descartar as alterações não salvas deste produto?')) return;
    dialog.current?.close();
    trigger.current?.focus({preventScroll:true});
  }
  function update<K extends keyof ProductForm>(key: K, value: ProductForm[K]) {
    setDraft(previous => ({ ...previous, [key]: value, ...(key === 'origin' ? { private: true } : {}) })); setDirty(true);
  }
  function example() {
    setDraft(previous => ({ ...previous, name: 'Quebra-cabeça deslizante de duas faces',
      description: 'Até quatro cores. Exemplo histórico para avaliar a tela.',
      price: '32,50', included: 'Custos, trabalho e margem. Saquinho individual não incluído.',
      length: '9,6', width: '9,6', height: '0,7', weight: '39', quantity: '45' }));
    setDirty(true); setError('');
  }
  function save(event: FormEvent) {
    event.preventDefault();
    if (!draft.name.trim()) { setError('Informe o nome do produto.'); return; }
    if (!validOrigin(draft.origin)) { setError('Selecione a origem do produto: Próprio ou De cliente.'); return; }
    if (draft.price.trim() && cents(draft.price) === null) {
      showValidation(event.currentTarget as HTMLElement,[{element:document.getElementById('wf-price')!,message:'Informe um preço válido, com até duas casas decimais, ou deixe pendente.'}]); return;
    }
    for (const key of ['length', 'width', 'height', 'weight'] as const) {
      if (draft[key].trim() && (!/^\d+(?:[.,]\d+)?$/.test(draft[key].trim()) || Number(draft[key].replace(',', '.')) <= 0)) {
        const field=(event.currentTarget as HTMLElement).querySelector<HTMLElement>(`#wf-${key}`);if(field)showValidation(event.currentTarget as HTMLElement,[{element:field,message:'Dimensões e peso devem ser maiores que zero. Você também pode deixá-los pendentes.'}]);return;
      }
    }
    const previousItem = items.find(p => p.id === editing);
    const item: Item = { ...emptyPackaging(), ...previousItem, ...productData(draft), quantity: draft.quantity, catalog: draft.catalog, private: draft.origin !== 'own' || draft.private, name: draft.name.trim(), id: editing ?? nextId.current++ };
    setItems(previous => editing === null ? [...previous, item] : previous.map(p => p.id === editing ? item : p));
    if (editing === null) setRecentlyAddedId(item.id);
    if (draft.catalog) setCatalog(previous => [...previous.filter(p => p.id !== item.id), { ...productData(item), id: item.id }]);
    else if (editing !== null) setCatalog(previous => previous.filter(p => p.id !== editing));
    setStatus(`${item.name} ${editing === null ? 'adicionado' : 'atualizado'}. ${draft.catalog ? 'Incluído também no catálogo simulado.' : 'Usado somente neste orçamento.'} ${item.private ? 'Privado: bloqueado para divulgação no site.' : 'Elegível para divulgação futura; nada foi publicado.'}`);
    close(true);
  }
  function remove(item: Item) {
    if (!window.confirm('Remover este item do orçamento?')) return;
    setItems(previous => previous.filter(p => p.id !== item.id));
    setStatus('Item removido do orçamento. O catálogo simulado foi preservado.');
  }
  function addFromCatalog(product: CatalogProduct) {
    if (!validOrigin(product.origin)) {
      setStatus('Produto com origem não informada. Defina Próprio ou De cliente no cadastro antes de adicionar.'); return;
    }
    setItems(previous => [...previous, { ...productData(product), ...emptyPackaging(), id: nextId.current++, quantity: '1', catalog: false }]);
    setScreen('editor'); setStatus('Produto adicionado do catálogo. Escolha a embalagem individual para este item do orçamento.');
  }
  function addSelectedFromCatalog() {
    const selected = catalog.filter(product => selectedCatalogIds.includes(product.id));
    if (selected.length === 0) return;
    if (selected.some(product => !validOrigin(product.origin))) {
      setStatus('Há produto selecionado sem origem. Defina Próprio ou De cliente no cadastro antes de adicionar.'); return;
    }
    const additions = selected.map(product => ({ ...productData(product), ...emptyPackaging(), id: nextId.current++, quantity: '1', catalog: false }));
    setItems(previous => [...previous, ...additions]);
    setSelectedCatalogIds([]); setCatalogSearch('');
    if (catalogDropdown.current) {
      catalogDropdown.current.open = false;
      catalogDropdown.current.querySelector('summary')?.focus();
    }
    setStatus(`${additions.length} ${additions.length === 1 ? 'produto adicionado' : 'produtos adicionados'} do catálogo. Quantidades e embalagens são independentes por item deste orçamento.`);
  }
  function toggleCatalogProduct(id: number, checked: boolean) {
    setSelectedCatalogIds(previous => checked ? [...previous.filter(value => value !== id), id] : previous.filter(value => value !== id));
  }
  function updatePackaging<K extends 'individualPackaging' | 'packagingType' | 'packagingPrice' | 'packagingIncluded'>(id: number, key: K, value: Item[K]) {
    setItems(previous => previous.map(item => item.id === id ? { ...item, [key]: value } : item));
  }
  function updateQuantity(id: number, value: string) {
    setItems(previous => previous.map(item => item.id === id ? { ...item, quantity: value } : item));
  }
  function packagingControls(item: Item) {
    return <fieldset className="wf-item-packaging"><legend>Embalagem individual neste orçamento</legend>
      <label htmlFor={`wf-packaging-${item.id}`}>Embalar cada unidade deste item?</label>
      <select id={`wf-packaging-${item.id}`} value={item.individualPackaging} onChange={e => updatePackaging(item.id, 'individualPackaging', e.target.value as Item['individualPackaging'])}>
        <option value="">A definir</option><option value="none">Não — sem embalagem individual</option><option value="with">Sim — com embalagem individual</option>
      </select><p className="wf-muted">Esta escolha vale só para este item do orçamento. O produto no catálogo permanece inalterado.</p>
      {item.individualPackaging === 'with' && <>
        <label htmlFor={`wf-packaging-type-${item.id}`}>Tipo de embalagem individual</label><input id={`wf-packaging-type-${item.id}`} value={item.packagingType} placeholder="Ex.: saquinho autoadesivo ou caixa individual" onChange={e => updatePackaging(item.id, 'packagingType', e.target.value)} />
        <label className="wf-choice"><input type="checkbox" checked={item.packagingIncluded} onChange={e => updatePackaging(item.id, 'packagingIncluded', e.target.checked)} />Embalagem já incluída no preço de venda informado</label>
        {!item.packagingIncluded && <><label htmlFor={`wf-packaging-price-${item.id}`}>Acréscimo por embalagem individual (R$)</label><input id={`wf-packaging-price-${item.id}`} inputMode="decimal" value={item.packagingPrice} placeholder="Valor cobrado por unidade, informado" onChange={e => updatePackaging(item.id, 'packagingPrice', e.target.value)} />
          {item.packagingPrice.trim() && cents(item.packagingPrice) === null && <p className="wf-error" role="alert">Informe um valor válido com até duas casas decimais. A embalagem continua pendente.</p>}</>}
        <p>{item.packagingIncluded ? 'Sem acréscimo: a embalagem já está no preço informado.' : lineAmount(packagingCents(item), item.quantity) === null ? 'Valor da embalagem ou quantidade pendente.' : `${money(packagingCents(item)!)} × ${item.quantity} ${quantityNumber(item.quantity) === 1 ? 'unidade' : 'unidades'} = ${money(lineAmount(packagingCents(item), item.quantity)!)} de embalagem.`}</p>
        <p className="wf-muted">Cobrança pelas unidades utilizadas neste cenário. Peso e compatibilidade ainda precisam ser conferidos; não houve pesquisa de fornecedor.</p>
      </>}
    </fieldset>;
  }

  return <div className="wf-shell">
    <div className="wf-banner"><strong>Wireframe navegável</strong><span>Dados de demonstração nesta página. Recarregar descarta as alterações. O banco não é usado.</span></div>
    <header className="wf-header"><div><strong>{appName}</strong><small>Seu trabalho comercial, em um só lugar.</small></div><a href="?view=diagnostico">Voltar ao diagnóstico</a></header>
    <nav className="wf-nav" aria-label="Áreas"><button onClick={() => setScreen('list')} aria-current={screen !== 'catalog' ? 'page' : undefined}>Orçamentos</button><button onClick={() => setScreen('catalog')} aria-current={screen === 'catalog' ? 'page' : undefined}>Catálogo simulado</button><span>Fabricação: a detalhar</span></nav>
    <main className="wf-main">
      {screen === 'list' && <><div className="wf-title"><div><small>ORÇAMENTOS</small><h1>Rascunhos da demonstração</h1></div><button onClick={() => setScreen('editor')}>Abrir orçamento</button></div><section className="wf-card"><h2>Orçamento em preparação</h2><p>{client || 'Cliente a definir'} · {items.length} {items.length === 1 ? 'item' : 'itens'}</p><p>Não salvo no banco, não enviado. Todos os dados são desta demonstração.</p><button onClick={() => setScreen('editor')}>Continuar preenchendo</button></section></>}
      {screen === 'catalog' && <><div className="wf-title"><div><small>CATÁLOGO SIMULADO</small><h1>Produtos desta sessão</h1></div><button onClick={() => setScreen('editor')}>Voltar ao orçamento</button></div><p>Salvar no catálogo não autoriza publicar no site. A integração com o site ainda não existe.</p>{catalog.length === 0 ? <section className="wf-card"><h2>Nenhum produto salvo no catálogo</h2><p>Cadastre pelo orçamento e marque a opção de salvar também no catálogo.</p></section> : catalog.map(p => <section className="wf-card" key={p.id}><h2>{p.name}</h2><span className="wf-tag">{p.private ? 'Privado · não exportar para site' : 'Divulgação autorizada · não publicado'}</span><p>{originLabel(p.origin)} · {cents(p.price) === null ? 'Preço pendente' : `${money(cents(p.price)!)} por unidade`}</p><button onClick={() => addFromCatalog(p)}>Usar no orçamento</button></section>)}</>}
      {screen === 'editor' && <>
        <div className="wf-title"><div><small>ORÇAMENTOS / NOVO RASCUNHO</small><h1>Vamos montar o pedido.</h1><p>Comece com o cliente e adicione um produto, mesmo que ele ainda não esteja no catálogo.</p></div><span className="wf-tag">Demonstração · não enviado</span></div>
        <div className="wf-grid"><div>
          <section className="wf-card"><h2><span className="wf-step">1</span>Cliente do orçamento</h2><ClientPicker selected={selectedClient} onSelect={setSelectedClient} /><label htmlFor="wf-notes">Observações do pedido</label><textarea id="wf-notes" value={notes} onChange={e => setNotes(e.target.value)} placeholder="Observações deste pedido, separadas do cadastro do cliente." /></section>
          <section className="wf-card"><div className="wf-row"><h2><span className="wf-step">2</span>Produtos do orçamento</h2><button onClick={() => open()}>+ Novo produto</button></div><p>Informe o preço de venda que você já calculou. Fabricação e precificação serão detalhadas depois.</p>
            {catalog.length > 0 && <details ref={catalogDropdown} className="wf-product-picker wf-catalog-dropdown" onToggle={e => { if (e.currentTarget.open) setCatalogSearch(''); }} onKeyDown={e => { if (e.key === 'Escape') { e.preventDefault(); e.currentTarget.open = false; e.currentTarget.querySelector('summary')?.focus(); } }}><summary id="wf-catalog-toggle">Selecionar produtos do catálogo <span>{selectedCatalogIds.length > 0 ? `— ${selectedCatalogIds.length} selecionado(s)` : '— abrir lista'}</span></summary><label htmlFor="wf-catalog-search">Filtrar lista de produtos (opcional)</label><input id="wf-catalog-search" type="search" value={catalogSearch} onChange={e => setCatalogSearch(e.target.value)} placeholder="Todos os produtos aparecem abaixo; digite para filtrar" /><p className="wf-muted">A lista mostra os produtos salvos no catálogo desta demonstração. Explore a lista ou use o filtro opcional. Marque um ou vários produtos. Para uma peça nova, use Novo produto.</p><fieldset className="wf-catalog-options"><legend>Produtos disponíveis</legend>{catalog.filter(p => p.name.toLocaleLowerCase('pt-BR').includes(catalogSearch.trim().toLocaleLowerCase('pt-BR'))).map(p => <label className="wf-choice wf-product-option" key={p.id}><input type="checkbox" checked={selectedCatalogIds.includes(p.id)} onChange={e => toggleCatalogProduct(p.id, e.target.checked)} /><span><strong>{p.name}</strong><small>{cents(p.price) === null ? 'Preço de venda a informar' : `${money(cents(p.price)!)} por unidade`} · {p.private ? 'Privado' : 'Divulgação autorizada'}</small></span></label>)}{!catalog.some(p => p.name.toLocaleLowerCase('pt-BR').includes(catalogSearch.trim().toLocaleLowerCase('pt-BR'))) && <p>Nenhum produto encontrado. Você pode cadastrar pelo botão Novo produto.</p>}</fieldset><div className="wf-actions"><button type="button" disabled={selectedCatalogIds.length === 0} onClick={addSelectedFromCatalog}>Adicionar selecionados ao orçamento ({selectedCatalogIds.length})</button>{selectedCatalogIds.length > 0 && <button type="button" className="wf-secondary" onClick={() => setSelectedCatalogIds([])}>Limpar seleção</button>}</div><p className="wf-muted">Após adicionar, ajuste a quantidade de cada item e escolha a embalagem individual para este pedido.</p></details>}
            {items.length === 0 ? <div className="wf-empty"><h3>Uma peça nova também pode entrar aqui.</h3><p>Use “Novo produto” para informar nome, preço e dados físicos sem sair do orçamento.</p></div> : items.map(p => <article id={`wf-item-${p.id}`} tabIndex={-1} className={`wf-item${recentlyAddedId === p.id ? ' wf-item-recent' : ''}`} key={p.id}><div className="wf-row"><h3>{p.name}</h3>{recentlyAddedId === p.id && <span className="wf-tag">Adicionado ao orçamento</span>}<span className="wf-tag">{p.private ? 'Privado' : 'Divulgação autorizada'}</span></div><p>{p.description || 'Sem descrição'}<br />{quantityNumber(p.quantity) === null ? 'Quantidade pendente' : `${p.quantity} ${quantityNumber(p.quantity) === 1 ? 'unidade' : 'unidades'}`} × {cents(p.price) === null ? 'preço pendente' : money(cents(p.price)!)}<br />{p.length && p.width && p.height ? `${p.length} × ${p.width} × ${p.height} cm` : 'Dimensões pendentes'} · {p.weight ? `${p.weight} g/unidade` : 'Peso pendente'}</p><div className="wf-inline-quantity"><div><label htmlFor={`wf-quantity-${p.id}`}>Quantidade neste item</label><input id={`wf-quantity-${p.id}`} inputMode="numeric" value={p.quantity} onChange={e => updateQuantity(p.id, e.target.value)} /></div><p>Produtos: {lineAmount(cents(p.price), p.quantity) === null ? 'valor pendente' : money(lineAmount(cents(p.price), p.quantity)!)}</p></div>{quantityNumber(p.quantity) === null && <p className="wf-error" role="alert">Informe uma quantidade inteira maior que zero. Os valores deste item ficam pendentes.</p>}<p>{packagingLabel(p)}</p><p className="wf-muted">{originLabel(p.origin)} · {p.catalog ? 'Também salvo no catálogo simulado' : 'Somente neste orçamento'} · {p.private ? 'Bloqueado para futura carga no site' : 'Elegível para divulgação futura; ainda não publicado'}</p>{packagingControls(p)}<div className="wf-actions"><button className="wf-secondary" onClick={() => open(p)} aria-label={`Editar ${p.name}`}>Editar dados do produto</button><button className="wf-quiet" onClick={() => remove(p)} aria-label={`Remover ${p.name}`}>Remover do orçamento</button></div></article>)}
          </section>
          <section className="wf-card"><h2><span className="wf-step">3</span>Pacote de envio</h2><p>A embalagem individual é escolhida em cada produto. Aqui serão definidas a caixa externa e as proteções para transportar o conjunto de itens.</p><div className="wf-pending">Embalagem de transporte obrigatória para preparar o frete. Caixa, proteções, peso e medidas finais ainda não definidos. Frete não consultado.</div></section>
        </div><aside><section className="wf-card wf-summary"><small>RESUMO DO RASCUNHO</small><h2>Subtotal do pedido</h2><strong className="wf-total">{money(subtotal + packagingSubtotal)}</strong><p>Produtos: {money(subtotal)}</p><p>Embalagens individuais: {money(packagingSubtotal)}</p><p>{totalsPending ? 'Há valores ou quantidades pendentes; esta soma é parcial.' : 'Produtos e embalagens informados, sem transporte.'}</p><hr /><p>Embalagens individuais: {packagingSummary}</p><p>Caixa de transporte: a definir</p><p>Frete: pendente</p><p>Documento para envio: {taxDocument.trim() ? 'informado, ainda não validado' : 'pendente; não bloqueia cotação'}</p><p>Prazo de fabricação: a definir</p>{!postal && <p className="wf-pending">CEP de entrega pendente.</p>}{physicalPending && <p className="wf-pending">Há dados físicos incompletos para preparar o envio.</p>}<p className="wf-muted">Este subtotal não é o total final do orçamento. Nenhuma cotação, prazo ou publicação foi realizada.</p></section></aside></div>
      </>}
      <p className="wf-status" role="status">{status}</p>
    </main>
    <dialog ref={dialog} className="wf-dialog" aria-labelledby="wf-dialog-title" onCancel={e => { e.preventDefault(); close(); }} onClick={e => { if (e.target === e.currentTarget) close(); }}>
      <ValidatedForm noValidate onSubmit={save}>
        <div className="wf-modal-header"><div><small>CADASTRO DIRETO NO ORÇAMENTO</small><h2 id="wf-dialog-title">{editing === null ? 'Novo produto' : 'Editar produto'}</h2></div><ModalClose onClose={()=>close()}/></div>
        <div className="wf-modal-body"><p>Use o preço de venda final. Os dados do orçamento continuam guardados enquanto você preenche.</p><button type="button" className="wf-secondary" onClick={example}>Preencher exemplo histórico</button><p className="wf-muted">O exemplo é uma referência antiga; não consulta frete nem define preços atuais.</p>
          {error && <div className="wf-error" role="alert">{error}</div>}
          <label htmlFor="wf-product-name">Nome do produto <span aria-hidden="true">*</span></label><input autoFocus id="wf-product-name" value={draft.name} onChange={e => update('name', e.target.value)} aria-required="true" />
          <label htmlFor="wf-description">Descrição (opcional)</label><textarea id="wf-description" value={draft.description} onChange={e => update('description', e.target.value)} />
          <div className="wf-form-grid"><div><label htmlFor="wf-price">Preço de venda por unidade (R$)</label><input id="wf-price" inputMode="decimal" value={draft.price} onChange={e => update('price', e.target.value)} placeholder="Pode ficar pendente no rascunho" /></div></div>
          <label htmlFor="wf-included">O que já está incluído nesse preço?</label><textarea id="wf-included" value={draft.included} onChange={e => update('included', e.target.value)} placeholder="Ex.: custos, trabalho e margem; embalagem, se já incluída." />
          <fieldset><legend>Dados físicos da peça, por unidade</legend><p className="wf-muted">Estas são as medidas da peça, sem a embalagem individual ou a caixa de transporte. Dados ausentes deixam o envio pendente.</p><div className="wf-form-grid">{([
            ['length', 'Comprimento (cm)'], ['width', 'Largura (cm)'], ['height', 'Altura / espessura (cm)'], ['weight', 'Peso (g)']
          ] as const).map(([key, label]) => <div key={key}><label htmlFor={`wf-${key}`}>{label}</label><input id={`wf-${key}`} inputMode="decimal" value={draft[key]} onChange={e => update(key, e.target.value)} placeholder="A informar" /></div>)}</div></fieldset>

          <label htmlFor="wf-origin">Origem do produto <span aria-hidden="true">*</span></label><select id="wf-origin" required aria-required="true" value={draft.origin} onChange={e => update('origin', e.target.value as ProductForm['origin'])}><option value="" disabled>Selecione a origem</option><option value="own">Próprio</option><option value="client">De cliente</option></select><p className="wf-muted">A origem organiza os produtos. Um produto próprio também pode permanecer privado.</p>
          {draft.origin === 'own' ? <fieldset><legend>Privacidade e divulgação</legend><label className="wf-choice"><input type="radio" name="wf-visibility" checked={draft.private} onChange={() => update('private', true)} />Privado — não incluir em futura carga no site</label><label className="wf-choice"><input type="radio" name="wf-visibility" checked={!draft.private} onChange={() => update('private', false)} />Autorizo a elegibilidade para divulgação futura</label><p className="wf-muted">Todo produto novo começa privado. Autorizar não publica o produto. A integração com o site ainda não existe.</p></fieldset> : <p className="wf-pending">{draft.origin === 'client' ? 'Produto de cliente: sempre privado e bloqueado para divulgação no site.' : 'Selecione a origem para continuar. Produtos novos começam privados.'}</p>}
          <fieldset><legend>Onde usar este produto?</legend><label className="wf-choice"><input type="checkbox" checked={draft.catalog} onChange={e => update('catalog', e.target.checked)} />Salvar também no catálogo (simulação)</label><p className="wf-muted">Desmarcado: usar só neste orçamento. Produtos privados também podem ficar no catálogo e continuam bloqueados para divulgação.</p></fieldset>
        </div><div className="wf-modal-footer"><button type="button" className="wf-secondary" onClick={() => close()}>Cancelar</button><button type="submit">{editing === null ? 'Adicionar ao orçamento' : 'Salvar alterações no item'}</button></div>
      </ValidatedForm>
    </dialog>
  </div>;
}
