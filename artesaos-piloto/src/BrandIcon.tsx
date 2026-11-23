export type BrandIconName='vendas'|'financeiro'|'pedidos'|'estoque'|'produtos'|'clientes'|'orcamentos'|'configuracoes'|'menu'|'close'|'plus'|'ajuda'|'back'|'cart'|'store'|'card'|'clock'|'layers'|'pix'|'cash'|'trash'|'print'|'share';
const paths:Record<Exclude<BrandIconName,'estoque'|'pedidos'|'financeiro'|'vendas'>,string>={
 back:'M20 12H4m7-7-7 7 7 7',
 cart:'M2 3h3l3 12h10l3-8H6m3 13h.01m8 0h.01',
 store:'M3 9 5 3h14l2 6M3 9v2a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0V9M5 14v7h14v-7m-9 7v-5h4v5',
 card:'M3 5h18v14H3zM3 9h18M6 15h5',
 clock:'M12 7v5l3 2M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z',
 layers:'m12 3 9 5-9 5-9-5 9-5Zm-9 9 9 5 9-5M3 16l9 5 9-5',
 pix:'m12 2 10 10-10 10L2 12 12 2ZM7 8l5 5 5-5m-10 8 5-5 5 5',
 cash:'M2 5h20v14H2zM6 12h.01M18 12h.01M12 9a3 3 0 1 0 0 6 3 3 0 0 0 0-6Z',
 trash:'M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7m4-7v7',
 print:'M6 8V3h12v5M6 17H3V9h18v8h-3M6 14h12v7H6zM17 11h.01',
 share:'M12 15V3m-4 4 4-4 4 4M5 11v9h14v-9',
 ajuda:'M9 9a3 3 0 1 1 5 2c-2 1-2 2-2 3M12 18h.01M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Z',
 produtos:'M12 3 3 7.5v9L12 21l9-4.5v-9L12 3ZM3 7.5l9 4.5 9-4.5M12 12v9M7.5 5.25l9 4.5',
 clientes:'M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
 orcamentos:'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8l-6-6ZM14 2v6h6M8 13h8M8 17h6',
 configuracoes:'m9 3-1 3-3 1-2 3 2 2-1 3 2 3 3-1 3 2 3-2 3 1 2-3-1-3 2-2-2-3-3-1-1-3H9ZM12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8Z',
 menu:'M3 6h18M3 12h18M3 18h18',close:'m6 6 12 12M18 6 6 18',plus:'M12 5v14M5 12h14'
};
export default function BrandIcon({name}:{name:BrandIconName}){return <svg className="pilot-icon" aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d={paths[name==='estoque'?'produtos':name==='pedidos'||name==='financeiro'||name==='vendas'?'orcamentos':name]}/></svg>;}
