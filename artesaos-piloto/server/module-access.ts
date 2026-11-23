/** Pilot availability, independent of licenses and billing. */
export const moduleLabels={fabricacao:'Fabricação / Precificação',catalogo:'Catálogo',vendas:'PDV',clientes:'Clientes',orcamentos:'Orçamentos',pedidos:'Pedidos',estoque:'Estoque',financeiro:'Financeiro'} as const;
export type ModuleKey=keyof typeof moduleLabels;
export const moduleKeys=Object.keys(moduleLabels) as ModuleKey[];
export const essentialModules:ModuleKey[]=['fabricacao','catalogo','vendas'];
export type ModuleAccess={enabled:ModuleKey[];revision:number};
export function viewModule(view:string|null):ModuleKey|null{
 return ({consignados:'vendas',materiais:'fabricacao',pagamentos:'vendas',produtos:'catalogo',fabricacao:'fabricacao',vendas:'vendas',clientes:'clientes',orcamentos:'orcamentos',produto:'orcamentos',pedidos:'pedidos',estoque:'estoque',financeiro:'financeiro'} as Record<string,ModuleKey>)[view??'produtos']??(['ajuda','suporte','configuracoes','diagnostico'].includes(view??'')?null:'catalogo');
}
/** Explicit shared operations stay available; disabling a screen never disables internal services. */
export function apiModules(path:string,method:string):ModuleKey[]|null{
 const read=method==='GET'||method==='HEAD';
 const contextual=contextualApi(path,method);
 if(path.startsWith('/api/context/'))return contextual?[contextual.module]:[];
 if(/^\/api\/finance\/(accounts|methods)(\/|$)/.test(path))return ['financeiro','vendas'];
 if(path.startsWith('/api/finance'))return ['financeiro'];
 if(/^\/api\/(sales|sale-coupons|sales-sessions|sale-locations|sales-places)(\/|$)/.test(path))return ['vendas'];
 if(/^\/api\/inventory\/(manufacturing-preview|manufacture)$/.test(path))return ['fabricacao'];
 if(/^\/api\/inventory\/(materials|material-|lots|current-product-costs)/.test(path))return read?['fabricacao','estoque']:['estoque'];
 if(read&&/^\/api\/inventory\/(product-stock|consigned|stock-locations)(\/|$)/.test(path))return ['estoque','vendas','financeiro','pedidos'];
 if(path.startsWith('/api/inventory'))return ['estoque'];
 if(/^\/api\/(orders|shipping)(\/|$)/.test(path))return ['pedidos'];
 if(/^\/api\/(quotes|quote-documents)(\/|$)/.test(path))return ['orcamentos'];
 if(/^\/api\/clients(\/|$)/.test(path))return read?['clientes','vendas','pedidos','orcamentos','financeiro']:['clientes'];
 if(/^\/api\/manufacturing(\/|$)/.test(path)||/^\/api\/products\/[^/]+\/manufacturing$/.test(path))return ['fabricacao'];
 if(/^\/api\/materials(\/|$)/.test(path))return ['fabricacao','estoque'];
 if(/^\/api\/settings\/fabricacao$/.test(path))return read?['fabricacao','catalogo']:['fabricacao'];
 if(/^\/api\/settings\/orcamentos$/.test(path))return ['orcamentos'];
 if(/^\/api\/settings\/clientes$/.test(path))return ['clientes'];
 if(/^\/api\/products(\/|$)/.test(path)||/^\/api\/categories(\/|$)/.test(path)||path==='/api/settings/produtos')return ['catalogo','fabricacao',...(read?['vendas','pedidos','orcamentos','financeiro'] as ModuleKey[]:[])];
 if(path.startsWith('/api/records/')){const kind=path.split('/')[3];return kind==='products'?['catalogo']:kind==='clients'?['clientes']:kind==='quotes'?['orcamentos']:[];}
 if(/^\/api\/(company|onboarding|operational-preferences|attention|health|note)(\/|$)/.test(path))return null;
 if(/^\/api\/product-photos(\/|$)/.test(path))return read?['catalogo','fabricacao','vendas','pedidos','orcamentos','financeiro']:['catalogo','fabricacao','vendas'];
 return [];
}
/** These are separate, bounded capabilities, never a browser-supplied context flag. */
export function contextualApi(path:string,method:string):{target:string;module:ModuleKey}|null{
 const client=path.match(/^\/api\/context\/pdv\/clients(\/\d+)?$/);
 if(client&&((!client[1]&&['GET','HEAD','POST'].includes(method))||(client[1]&&method==='PUT')))return {target:'/api/clients'+(client[1]??''),module:'vendas'};
 const consigned=path.match(/^\/api\/context\/pdv\/consigned((?:\/[^/]+\/(?:receive|history))?)$/);
 if(consigned&&((!consigned[1]&&['GET','HEAD','POST'].includes(method))||(consigned[1].endsWith('/receive')&&method==='POST')||(consigned[1].endsWith('/history')&&['GET','HEAD'].includes(method))))return {target:'/api/inventory/consigned'+consigned[1],module:'vendas'};
 return null;
}
export function allowsApi(access:ModuleAccess,path:string,method:string){const required=apiModules(path,method);return required===null||required.some(key=>access.enabled.includes(key));}
