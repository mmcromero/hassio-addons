import {DatabaseSync} from 'node:sqlite';
import {existsSync} from 'node:fs';
import {join} from 'node:path';
import type {PilotStore} from './store.js';
export function registeredUserDetails(store:PilotStore,dataDir:string,id:string){
 const user=store.db.prepare('SELECT id,email,disabled,tenant_id FROM pilot_users WHERE id=?').get(id);
 if(!user)return null;
 const result={id:String(user.id),email:String(user.email),disabled:Boolean(user.disabled),company:null as Record<string,string>|null};
 const tenant=String(user.tenant_id);if(!/^[0-9a-f-]{36}$/.test(tenant))throw Error('Identificador interno de conta inválido.');
 const path=join(dataDir,'tenants',tenant,'validation.sqlite');if(!existsSync(path))return result;
 const db=new DatabaseSync(path,{readOnly:true});
 try{
  if(!db.prepare("SELECT 1 FROM sqlite_master WHERE type='table' AND name='company_profile'").get())return result;
  const row=db.prepare('SELECT data FROM company_profile WHERE id=1').get();if(!row)return result;
  const data=JSON.parse(String(row.data));result.company=Object.fromEntries(['name','responsible','phone','email'].map(key=>[key,typeof data[key]==='string'?data[key]:'']));return result;
 }finally{db.close();}
}
