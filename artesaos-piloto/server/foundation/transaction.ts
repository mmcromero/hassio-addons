import type {DatabaseSync} from 'node:sqlite';
import {isAsyncFunction} from 'node:util/types';
let sequence=0;
/** Apenas trabalho síncrono; efeitos externos devem ocorrer depois do commit. */
export function transaction<T>(db:DatabaseSync,work:()=>T):T{
 if(isAsyncFunction(work))throw Error('Transações exigem função síncrona.');
 const nested=db.isTransaction,savepoint=`foundation_${++sequence}`;
 db.exec(nested?`SAVEPOINT ${savepoint}`:'BEGIN IMMEDIATE');
 try{
  const result=work();
  if(result&&typeof (result as any).then==='function')throw Error('Transações não aceitam Promises.');
  db.exec(nested?`RELEASE ${savepoint}`:'COMMIT');return result;
 }catch(error){db.exec(nested?`ROLLBACK TO ${savepoint}`:'ROLLBACK');if(nested)db.exec(`RELEASE ${savepoint}`);throw error;}
}
