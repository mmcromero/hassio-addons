export const pageSizes=['10','20','30','40','50','all'];
export const searchText=(value:string)=>value.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase('pt-BR').trim();
export function searchProducts<T extends {name:string;sku?:string}>(products:T[],search:string){
 const term=searchText(search);if(!term)return products;
 return products.filter(p=>searchText(p.name).includes(term)||searchText(p.sku??'').includes(term))
 .map((product,index)=>({product,index,exact:searchText(product.sku??'')===term}))
 .sort((a,b)=>Number(b.exact)-Number(a.exact)||a.index-b.index).map(p=>p.product);
}
export default function ListPagination({page,pages,total,size,label,settingsArea,busy=false,readOnly=false,onPage}:{page:number;pages:number;total:number;size:string;label:string;settingsArea:'clientes'|'produtos';busy?:boolean;readOnly?:boolean;onPage:(page:number)=>void}){
 if(pages<=1||size==='all')return null;
 return <nav className="quote-pagination" aria-label={`Paginação de ${label}`}><button type="button" disabled={busy||page<=1} onClick={()=>onPage(page-1)}>Página anterior</button><span role="status">Página {page} de {pages} · {total} {label}</span><button type="button" disabled={busy||page>=pages} onClick={()=>onPage(page+1)}>Próxima página</button><small>{size==='all'?'Todos os resultados':`${size} registros por página`}. {!readOnly&&<>Altere nas <a href={`?view=configuracoes&area=${settingsArea}`}>Configurações</a>.</>}</small></nav>;
}
