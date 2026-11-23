export type ClientDraft={registrationOrigin?:string;captureSessionId?:string|null;createdAt?:string|null;commercialType:string;name:string;contact:string;phone:string;email:string;taxDocument:string;postal:string;street:string;number:string;complement:string;district:string;city:string;state:string};
export type Client=ClientDraft&{id:number};
export const emptyClient=():ClientDraft=>({commercialType:'retail',name:'',contact:'',phone:'',email:'',taxDocument:'',postal:'',street:'',number:'',complement:'',district:'',city:'',state:''});
export function clientDraft(data:Partial<ClientDraft>):ClientDraft{const result=emptyClient();for(const key of Object.keys(result) as (keyof ClientDraft)[])result[key]=data[key]??'';return result;}
export const clientLabel=(data:{name?:string;contact?:string})=>data.name?.trim()||data.contact?.trim()||'Cliente a definir';
export const addressFields=[['street','Rua / logradouro',200],['number','Número',30],['complement','Complemento',200],['district','Bairro',100],['city','Cidade',100],['state','Estado (UF)',2]] as const;
