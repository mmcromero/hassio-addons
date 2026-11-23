import type {DatabaseSync} from 'node:sqlite';
import {createHash} from 'node:crypto';
import {isAsyncFunction} from 'node:util/types';
import {transaction} from './transaction.js';
export type Json=null|boolean|number|string|Json[]|{[key:string]:Json};
export class OperationConflict extends Error{}
function canonical(value:Json):string{
 if(value===null||typeof value==='string'||typeof value==='boolean')return JSON.stringify(value);
 if(typeof value==='number'){if(!Number.isFinite(value)||!Number.isSafeInteger(value))throw Error('Use inteiros seguros ou strings decimais no contrato.');return JSON.stringify(value);}
 if(Array.isArray(value))return '['+Array.from(value,v=>canonical(v)).join(',')+']';
 if(typeof value!=='object'||Object.getPrototypeOf(value)!==Object.prototype)throw Error('Contrato JSON inválido.');
 return '{'+Object.keys(value).sort().map(key=>JSON.stringify(key)+':'+canonical(value[key])).join(',')+'}';
}
export function executeOperation<T extends Json>(db:DatabaseSync,input:{scope:string;key:string;actor:string;action:string;sourceId:string;request:Json},work:()=>T):{replayed:boolean;result:T}{
 if(isAsyncFunction(work))throw Error('Operações exigem função síncrona.');
 for(const field of [input.scope,input.key,input.actor,input.action,input.sourceId])if(typeof field!=='string'||!field.trim()||field.length>250)throw Error('Identificação de operação inválida.');
 const payload=canonical({actor:input.actor,action:input.action,sourceId:input.sourceId,request:input.request});
 if(Buffer.byteLength(payload)>1024*1024)throw Error('Solicitação grande demais.');
 const hash=createHash('sha256').update(payload).digest('hex');
 return transaction(db,()=>{
  const old=db.prepare('SELECT request_hash,response_json FROM operation_records WHERE scope=? AND operation_key=?').get(input.scope,input.key);
  if(old){if(old.request_hash!==hash)throw new OperationConflict('Chave já utilizada com outros dados.');return {replayed:true,result:JSON.parse(String(old.response_json)) as T};}
  const result=work(),response=canonical(result),now=new Date().toISOString();
  if(Buffer.byteLength(response)>1024*1024)throw Error('Resultado grande demais.');
  db.prepare('INSERT INTO operation_records VALUES(?,?,?,?,?)').run(input.scope,input.key,hash,response,now);
  db.prepare('INSERT INTO operation_audit(scope,operation_key,actor,action,source_id,details_json,created_at) VALUES(?,?,?,?,?,?,?)').run(input.scope,input.key,input.actor,input.action,input.sourceId,JSON.stringify({requestHash:hash}),now);
  return {replayed:false,result:JSON.parse(response) as T};
 });
}
