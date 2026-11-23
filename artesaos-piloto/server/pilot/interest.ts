import {initializeDatabase} from '../foundation/migrations.js';
import {DatabaseSync} from 'node:sqlite';
import {randomBytes,randomUUID,createCipheriv,createDecipheriv,createHmac} from 'node:crypto';
import {mkdirSync,existsSync,readFileSync,writeFileSync,chmodSync,lstatSync} from 'node:fs';
import {join} from 'node:path';
export type Interest={name:string;email:string;whatsapp:string};
export function parseInterest(value:unknown):Interest{
 if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Confira os campos do formulário.');
 const v=value as Record<string,unknown>;
 if(Object.keys(v).some(k=>!['name','email','whatsapp','consent','website','token'].includes(k)))throw Error('Confira os campos do formulário.');
 const field=(key:string,max:number)=>{const x=v[key]??'';if(typeof x!=='string'||x.length>max||/[\x00-\x1f\x7f<>]/.test(x))throw Error('Confira os campos do formulário.');return x.trim();};
 const name=field('name',100),email=field('email',254).toLowerCase(),phone=field('whatsapp',40);
 if(!name)throw Error('Informe seu nome.');
 if(!email)throw Error('Informe seu e-mail.');
 if(email&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw Error('Confira o e-mail informado.');
 if(phone&&(!/^\+?[\d ()\-.]+$/.test(phone)||!/^\d{8,15}$/.test(phone.replace(/\D/g,''))))throw Error('Confira o WhatsApp com DDD e, se necessário, código do país.');
 if(v.consent!==true)throw Error('Confirme que deseja receber contato sobre convites.');
 return {name,email,whatsapp:phone?phone.replace(/\D/g,''):''};
}
export class InterestStore{
 readonly db:DatabaseSync;private key:Buffer;private macKey:Buffer;
 constructor(dir:string){
  mkdirSync(dir,{recursive:true,mode:0o700});
  const dbPath=join(dir,'pilot-interest.sqlite'),keyPath=join(dir,'pilot-interest.key');
  this.db=new DatabaseSync(dbPath);initializeDatabase(this.db,'interest');this.db.exec('PRAGMA secure_delete=ON;');
  try{
   chmodSync(dbPath,0o600);
   if(!existsSync(keyPath)){
    if(this.db.prepare('SELECT id FROM metadata LIMIT 1').get()||this.db.prepare('SELECT id FROM interests LIMIT 1').get())throw Error('Chave de contatos ausente.');
    try{writeFileSync(keyPath,randomBytes(32),{flag:'wx',mode:0o600});}catch(e){if(!existsSync(keyPath))throw e;}
   }
   if(!lstatSync(keyPath).isFile()||lstatSync(keyPath).isSymbolicLink())throw Error('Chave de contatos inválida.');
   chmodSync(keyPath,0o600);this.key=readFileSync(keyPath);if(this.key.length!==32)throw Error('Chave de contatos inválida.');this.macKey=createHmac('sha256',this.key).update('artesao-interest-mac-v1').digest();
   const meta=this.db.prepare('SELECT * FROM metadata WHERE id=1').get();
   if(meta){if(this.decrypt(meta,'metadata')!=='artesao-interest-v1')throw Error('Chave de contatos inválida.');}
   else{const c=this.encrypt('artesao-interest-v1','metadata');this.db.prepare('INSERT INTO metadata VALUES (1,?,?,?)').run(c.iv,c.tag,c.payload);}
   this.prune();
  }catch(e){this.db.close();throw e;}
 }
 private hash(value:string){return createHmac('sha256',this.macKey).update(value).digest('hex');}
 private encrypt(value:string,aad:string){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',this.key,iv);c.setAAD(Buffer.from(aad));const payload=Buffer.concat([c.update(value,'utf8'),c.final()]);return {iv,payload,tag:c.getAuthTag()};}
 private decrypt(row:Record<string,unknown>,aad:string){const d=createDecipheriv('aes-256-gcm',this.key,row.iv as Uint8Array);d.setAAD(Buffer.from(aad));d.setAuthTag(row.tag as Uint8Array);return Buffer.concat([d.update(row.payload as Uint8Array),d.final()]).toString('utf8');}
 prune(){this.db.prepare('DELETE FROM interests WHERE created_at<?').run(Date.now()-90*86400000);this.db.prepare('DELETE FROM form_tokens WHERE expires_at<?').run(Date.now());}
 issue(browser:string,token:string){this.prune();this.db.prepare('INSERT INTO form_tokens VALUES (?,?,?)').run(this.hash(token),this.hash(browser),Date.now()+900000);}
 consume(browser:string,token:string){const r=this.db.prepare('DELETE FROM form_tokens WHERE hash=? AND browser_hash=? AND expires_at>? RETURNING hash').get(this.hash(token),this.hash(browser),Date.now());return !!r;}
 add(data:Interest){
  this.prune();if(Number(this.db.prepare('SELECT COUNT(*) n FROM interests').get()!.n)>=5000)throw Error('Lista temporariamente indisponível.');
  const id=randomUUID(),createdAt=Date.now(),c=this.encrypt(JSON.stringify(data),id+':'+createdAt);
  this.db.prepare('INSERT OR IGNORE INTO interests VALUES (?,?,?,?,?,?,?)').run(id,createdAt,data.email?this.hash('email:'+data.email):null,data.whatsapp?this.hash('phone:'+data.whatsapp):null,c.iv,c.tag,c.payload);
 }
 get(id:string){const row=this.db.prepare('SELECT * FROM interests WHERE id=? AND created_at>=?').get(id,Date.now()-90*86400000);return row?{id:String(row.id),createdAt:Number(row.created_at),...JSON.parse(this.decrypt(row,String(row.id)+':'+row.created_at)) as Interest}:null;}
 list(page:number){this.prune();const total=Number(this.db.prepare('SELECT COUNT(*) n FROM interests').get()!.n),pages=Math.max(1,Math.ceil(total/25)),current=Math.min(page,pages);const records=this.db.prepare('SELECT * FROM interests ORDER BY created_at DESC,id DESC LIMIT 25 OFFSET ?').all((current-1)*25).map(row=>({id:String(row.id),createdAt:Number(row.created_at),...JSON.parse(this.decrypt(row,String(row.id)+':'+row.created_at)) as Interest}));return {records,total,page:current,pages};}
 close(){this.db.close();this.key.fill(0);this.macKey.fill(0);}
}
