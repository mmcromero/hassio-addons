export const supportKinds={question:'Dúvida de uso',bug:'Relatar erro'} as const;
export const supportStatuses={open:'Em aberto',analysis:'Em análise',answered:'Respondido',waiting_customer:'Aguardando resposta do cliente',closed:'Finalizado'} as const;
export type SupportKind=keyof typeof supportKinds;
export type SupportStatus=keyof typeof supportStatuses;
export type SupportSummary={id:number;email:string;kind:SupportKind;subject:string;status:SupportStatus;revision:number;createdAt:string;updatedAt:string};
export type SupportEvent={id:number;role:'user'|'admin';body:string;status:SupportStatus;createdAt:string};
export type SupportDetail=SupportSummary&{events:SupportEvent[]};
export type SupportList={items:SupportSummary[];page:number;pages:number;total:number};
