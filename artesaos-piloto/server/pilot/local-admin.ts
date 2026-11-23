import {scrypt,randomBytes} from 'node:crypto';
import {transaction} from '../foundation/transaction.js';
import {PilotStore,token,digest,equal} from './store.js';
const parameters={N:32768,r:8,p:1,maxmem:64*1024*1024};
let hashing=0;
export class LocalAdminError extends Error{constructor(readonly status:number,message:string){super(message);}}
function emailOf(value:string){if(typeof value!=='string'||value.length>254||/[\x00-\x1f\x7f<>]/.test(value)||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim()))throw new LocalAdminError(400,'Confira o e-mail.');return value.trim().toLowerCase();}
function passwordOf(value:string){if(typeof value!=='string'||value.length<12||value.length>128||/[\x00-\x1f\x7f]/.test(value))throw new LocalAdminError(400,'Use senha de 12 a 128 caracteres, sem caracteres de controle.');return value;}
async function key(password:string,salt:string){
 if(hashing>=2)throw new LocalAdminError(503,'Autenticação ocupada. Tente novamente em instantes.');
 hashing++;try{return await new Promise<Buffer>((resolve,reject)=>scrypt(password,Buffer.from(salt,'hex'),64,parameters,(error,result)=>error?reject(error):resolve(result)));}finally{hashing--;}
}
async function hashPassword(password:string){const salt=randomBytes(16).toString('hex');return `scrypt$32768$8$1$${salt}$${(await key(password,salt)).toString('hex')}`;}
async function verify(password:string,encoded:string){
 const match=/^scrypt\$32768\$8\$1\$([a-f0-9]{32})\$([a-f0-9]{128})$/.exec(encoded);
 const actual=await key(password,match?.[1]??'0'.repeat(32));return !!match&&equal(actual.toString('hex'),match[2]);
}
/** Exclusivo do adaptador Debian; tabelas compartilhadas existem também no HA. */
export class LocalAdmin{
 constructor(private store:PilotStore,private now=()=>Date.now()){}
 private record(){return this.store.db.prepare('SELECT * FROM local_admin WHERE id=1').get();}
 exists(){return !!this.record();}
 /** Publicação local restrita ocorre dentro da transação; nunca retornar código por HTTP. */
 issueCode(purpose:'setup'|'recovery',publish:(code:string)=>void){
  return transaction(this.store.db,()=>{
   if(this.exists()!==(purpose==='recovery'))throw new LocalAdminError(409,'Ação indisponível neste estado da instalação.');
   const code=token(),expires=this.now()+30*60000;
   this.store.db.prepare('INSERT INTO local_admin_activation(id,purpose,code_hash,expires_at) VALUES(1,?,?,?) ON CONFLICT(id) DO UPDATE SET purpose=excluded.purpose,code_hash=excluded.code_hash,expires_at=excluded.expires_at').run(purpose,digest(code),expires);
   publish(code);return expires;
  });
 }
 private validCode(purpose:string,code:string){
  if(typeof code!=='string'||code.length<32||code.length>100)return false;
  const row=this.store.db.prepare('SELECT * FROM local_admin_activation WHERE id=1').get();
  return !!row&&row.purpose===purpose&&Number(row.expires_at)>this.now()&&equal(String(row.code_hash),digest(code));
 }
 async setPassword(purpose:'setup'|'recovery',email:string,password:string,confirmation:string,code:string){
  email=emailOf(email);password=passwordOf(password);
  if(password!==confirmation)throw new LocalAdminError(400,'A confirmação da senha não confere.');
  const allowed=()=>{const admin=this.record();return purpose==='setup'?!admin:!!admin&&admin.email===email;};
  if(!allowed()||!this.validCode(purpose,code))throw new LocalAdminError(403,'Código inválido, expirado ou acesso indisponível.');
  const encoded=await hashPassword(password);
  transaction(this.store.db,()=>{
   if(!allowed()||!this.validCode(purpose,code))throw new LocalAdminError(403,'Código inválido, expirado ou acesso indisponível.');
   if(purpose==='setup')this.store.db.prepare('INSERT INTO local_admin VALUES(1,?,?,1,?)').run(email,encoded,new Date(this.now()).toISOString());
   else this.store.db.prepare('UPDATE local_admin SET password_hash=?,revision=revision+1,updated_at=? WHERE id=1').run(encoded,new Date(this.now()).toISOString());
   this.store.db.exec('DELETE FROM local_admin_activation; DELETE FROM pilot_admin_sessions;');
  });
 }
 async login(email:string,password:string){
  if(typeof password!=='string'||password.length>128||typeof email!=='string'||email.length>254)throw new LocalAdminError(403,'E-mail ou senha inválidos.');
  const admin=this.record();const correct=await verify(password,String(admin?.password_hash??''));
  if(!admin||admin.email!==email.trim().toLowerCase()||!correct)throw new LocalAdminError(403,'E-mail ou senha inválidos.');
  return transaction(this.store.db,()=>{
   const current=this.record();if(current?.revision!==admin.revision)throw new LocalAdminError(403,'Acesso alterado. Entre novamente.');
   const value=token(),csrf=token(),now=this.now();
   this.store.db.prepare('DELETE FROM pilot_admin_sessions WHERE expires_at<?').run(now);
   this.store.db.prepare('INSERT INTO pilot_admin_sessions VALUES(?,?,?,?,?,?)').run(digest(value),String(admin.email),'local-admin:'+admin.revision,digest(csrf),now+3600000,now);
   return {value,csrf};
  });
 }
 current(value:string){
  if(!value||value.length>100)return null;
  const admin=this.record();if(!admin)return null;
  const row=this.store.db.prepare('SELECT subject FROM pilot_admin_sessions WHERE hash=?').get(digest(value));
  if(row?.subject!=='local-admin:'+admin.revision)return null;
  return this.store.getAdmin(value,[String(admin.email)]);
 }
}

/** Impede compartilhar por engano o volume entre os adaptadores. */
export function bindDistribution(store:PilotStore,distribution:'home-assistant'|'debian'){
 transaction(store.db,()=>{
  const old=store.db.prepare('SELECT distribution FROM installation_distribution WHERE id=1').get();
  if(old&&old.distribution!==distribution)throw Error('Diretório pertence a outra distribuição. Use dados independentes.');
  if(!old){
   if(distribution==='debian'&&(store.db.prepare('SELECT 1 FROM pilot_users LIMIT 1').get()||store.db.prepare('SELECT 1 FROM pilot_invites LIMIT 1').get()))throw Error('Debian exige diretório novo, sem contas ou convites importados.');
   store.db.prepare('INSERT INTO installation_distribution VALUES(1,?)').run(distribution);
  }
 });
}
