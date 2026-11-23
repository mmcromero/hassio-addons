// The query string is the source for browser navigation. Old area and hash
// links remain valid; no operational state or account data is stored here.
export const settingsGroups=['geral','preferencias','custos','vendas','frete','produtos','clientes','materiais','suporte'] as const;
export type SettingsGroup=typeof settingsGroups[number];
const areaGroups:Record<string,SettingsGroup>={fabricacao:'custos',produtos:'produtos',clientes:'clientes',orcamentos:'frete',suporte:'suporte'};
const hashGroups:Record<string,SettingsGroup>={'config-geral':'geral','config-custos':'custos','config-vendas':'vendas','config-frete':'frete','config-cadastros':'produtos','config-products':'produtos','config-clients':'clientes','config-support':'suporte'};
export function resolveSettingsGroup(url:URL,available:readonly SettingsGroup[]):SettingsGroup|null{
 const explicit=url.searchParams.get('settings');
 const target=explicit!==null?explicit:hashGroups[url.hash.slice(1)]??areaGroups[url.searchParams.get('area')??'']??null;
 return available.find(group=>group===target)??null;
}
export function settingsUrl(current:URL,group:SettingsGroup|null):URL{
 const next=new URL(current.href);
 next.searchParams.set('view','configuracoes');
 next.searchParams.delete('area');
 next.searchParams.delete('settings');
 if(group)next.searchParams.set('settings',group);
 next.hash='';
 return next;
}
