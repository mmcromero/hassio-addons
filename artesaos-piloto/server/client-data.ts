const text=(maxLength:number)=>({type:'string',maxLength});
export const clientSchema={type:'object',additionalProperties:false,required:['name','contact','phone','email','taxDocument','postal'],anyOf:[{properties:{name:{type:'string',pattern:'\\S'}}},{properties:{contact:{type:'string',pattern:'\\S'}}}],properties:{
 commercialType:{enum:['wholesale','retail','undefined']},registrationOrigin:{enum:['quote','sale','direct','undefined']},captureSessionId:{anyOf:[{type:'string',maxLength:100},{type:'null'}]},name:text(200),contact:text(200),phone:text(50),email:{anyOf:[{type:'string',maxLength:254,format:'email'},{const:''}]},taxDocument:text(40),postal:text(20),
 street:text(200),number:text(30),complement:text(200),district:text(100),city:text(100),state:text(2)
}};
export type ClientDraft={commercialType?:'wholesale'|'retail'|'undefined';registrationOrigin?:'quote'|'sale'|'direct'|'undefined';captureSessionId?:string|null;name:string;contact:string;phone:string;email:string;taxDocument:string;postal:string;street?:string;number?:string;complement?:string;district?:string;city?:string;state?:string};
export function normalizeClient(data:ClientDraft){return {...data,name:data.name.trim(),contact:data.contact.trim(),street:data.street??'',number:data.number??'',complement:data.complement??'',district:data.district??'',city:data.city??'',state:data.state??''};}
