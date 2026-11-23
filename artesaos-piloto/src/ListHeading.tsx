const columns={products:['Foto','Produto e preços','Categoria','Origem','No catálogo','Ações'],clients:['Cliente','Dados cadastrais','Ações'],quotes:['Orçamento','Situação','Itens','Atualizado em','Ações']};
export default function ListHeading({kind,selection}:{kind:keyof typeof columns;selection:boolean}){
 return <div className={`data-list-heading ${kind}-list-heading${selection?' has-selection':''}`} aria-hidden="true">{selection&&<span/>}{columns[kind].map(label=><span key={label}>{label}</span>)}</div>;
}
