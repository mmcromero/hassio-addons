import type {ClientDraft} from './client-model';
export default function ClientDetails({client}:{client:ClientDraft&{id:number}}){
 const field=(label:string,value:string,wide=false)=><div key={label} className={wide?'client-detail-wide':undefined}><dt>{label}</dt><dd>{value||'Não informado'}</dd></div>;
 return <div className="client-details-panel" id={`client-details-${client.id}`} role="region" aria-label={`Dados cadastrais de ${client.name.trim()||client.contact.trim()}`}>
  <div><h4>Classificação e origem</h4><dl>{field('Tipo comercial',({wholesale:'Atacado',retail:'Varejo',undefined:'Não definido'} as Record<string,string>)[client.commercialType]??'Não definido')}{field('Origem original',({quote:'Orçamento',sale:'Venda',direct:'Cadastro direto'} as Record<string,string>)[client.registrationOrigin??'']??'Não definido')}{field('Sessão de captação',client.captureSessionId??'Não definida')}{field('Cadastrado em',client.createdAt?new Date(client.createdAt).toLocaleString('pt-BR'):'Não definido')}</dl></div><div><h4>Contato e documento</h4><dl>{field('Telefone',client.phone)}{field('CPF ou CNPJ',client.taxDocument)}{field('E-mail',client.email,true)}</dl></div>
  <div><h4>Endereço de entrega</h4><dl>{field('CEP',client.postal)}{field('Número',client.number)}{field('Rua / logradouro',client.street,true)}{field('Complemento',client.complement)}{field('Bairro',client.district)}{field('Cidade',client.city)}{field('Estado (UF)',client.state)}</dl></div>
 </div>;
}
