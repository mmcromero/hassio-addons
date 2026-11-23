import {initializeDatabase} from '../foundation/migrations.js';
import {DatabaseSync} from 'node:sqlite';
import {randomBytes,randomUUID,createHash,timingSafeEqual} from 'node:crypto';
import {mkdirSync} from 'node:fs';
import {join} from 'node:path';
export const token=()=>randomBytes(32).toString('base64url');
export const digest=(value:string)=>createHash('sha256').update(value).digest('hex');
export const equal=(a:string,b:string)=>{const x=Buffer.from(a),y=Buffer.from(b);return x.length===y.length&&timingSafeEqual(x,y);};
export type Identity={issuer:string;subject:string;email:string;verified:boolean};
export type Session={userId:string;tenantId:string;email:string;csrfHash:string};
export class PilotStore{
 readonly db:DatabaseSync;
 constructor(dir:string){mkdirSync(dir,{recursive:true,mode:0o700});this.db=new DatabaseSync(join(dir,'pilot-control.sqlite'));initializeDatabase(this.db,'control');
 }
 listUsers(page=1,search=''){
  const pattern='%'+search.trim().toLowerCase().replace(/[!%_]/g,'!$&')+'%',total=Number(this.db.prepare("SELECT COUNT(*) n FROM pilot_users WHERE email LIKE ? ESCAPE '!'").get(pattern)!.n),pages=Math.max(1,Math.ceil(total/25)),current=Math.min(page,pages);
  const records=this.db.prepare("SELECT id,email,disabled FROM pilot_users WHERE email LIKE ? ESCAPE '!' ORDER BY email,id LIMIT 25 OFFSET ?").all(pattern,(current-1)*25).map(row=>({id:String(row.id),email:String(row.email),disabled:Boolean(row.disabled)}));return {records,total,page:current,pages};
 }
 invite(email:string,hours=24){email=email.trim().toLowerCase();if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)||hours<1||hours>168)throw Error('E-mail ou validade inválidos.');const code=token();this.db.prepare('INSERT INTO pilot_invites(hash,email,expires_at) VALUES (?,?,?)').run(digest(code),email,Date.now()+hours*3600000);return code;}
 flow(state:string,browser:string,verifier:string,nonce:string,invite:string,purpose:'user'|'admin'='user'){const now=Date.now();this.db.prepare('DELETE FROM pilot_flows WHERE expires_at<?').run(now);this.db.prepare('INSERT INTO pilot_flows(hash,browser_hash,verifier,nonce,invite_hash,expires_at,purpose) VALUES (?,?,?,?,?,?,?)').run(digest(state),digest(browser),verifier,nonce,invite?digest(invite):'',now+600000,purpose);}
 takeFlow(state:string,browser:string){const hash=digest(state);const row=this.db.prepare('SELECT * FROM pilot_flows WHERE hash=?').get(hash);if(!row||Number(row.expires_at)<Date.now()||!equal(String(row.browser_hash),digest(browser)))return null;this.db.prepare('DELETE FROM pilot_flows WHERE hash=?').run(hash);return {verifier:String(row.verifier),nonce:String(row.nonce),inviteHash:String(row.invite_hash),purpose:String(row.purpose)};}
 activate(identity:Identity,inviteHash:string,maxUsers:number|null){
  if(identity.issuer!=='https://accounts.google.com'||!identity.subject||!identity.verified||!identity.email)throw Error('Identidade Google não confirmada.');
  const email=identity.email.toLowerCase();const old=this.db.prepare('SELECT * FROM pilot_users WHERE issuer=? AND subject=?').get(identity.issuer,identity.subject);
  if(old){
   if(old.disabled)throw Error('Acesso revogado.');
   // A returning account may explicitly consume a fresh invitation without
   // creating a duplicate account. Empty/old codes do not affect normal login.
   if(inviteHash){const now=Date.now();this.db.prepare("UPDATE pilot_invites SET used_at=?,accepted_user_id=? WHERE hash=? AND used_at IS NULL AND revoked=0 AND (no_expiry=1 OR expires_at>?) AND (binding_mode='first_google' OR email=?)").run(now,String(old.id),inviteHash,now,email);}
   return String(old.id);
  }
  this.db.exec('BEGIN IMMEDIATE');try{
   const invite=this.db.prepare('SELECT * FROM pilot_invites WHERE hash=?').get(inviteHash);
   if(!invite||(invite.binding_mode!=='first_google'&&invite.email!==email)||invite.used_at||invite.revoked||!invite.no_expiry&&Number(invite.expires_at)<Date.now())throw Error('Convite inválido, expirado ou não autorizado para esta conta.');
   if(maxUsers!==null&&Number(this.db.prepare('SELECT COUNT(*) n FROM pilot_users').get()!.n)>=maxUsers)throw Error('Limite de participantes atingido.');
   const id=randomUUID();this.db.prepare('INSERT INTO pilot_users(id,issuer,subject,email,tenant_id) VALUES (?,?,?,?,?)').run(id,identity.issuer,identity.subject,email,randomUUID());this.db.prepare('INSERT INTO pilot_account_registrations VALUES(?,?)').run(id,Date.now());this.db.prepare('UPDATE pilot_invites SET used_at=?,accepted_user_id=? WHERE hash=?').run(Date.now(),id,inviteHash);this.db.exec('COMMIT');return id;
  }catch(e){this.db.exec('ROLLBACK');throw e;}
 }
 bootstrap(email:string,code:string){if(!email&&!code)return;if(code.length<32||code.length>100||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))throw Error('Convite inicial inválido.');this.db.prepare('INSERT OR IGNORE INTO pilot_invites(hash,email,expires_at) VALUES (?,?,?)').run(digest(code),email.trim().toLowerCase(),Date.now()+86400000);}
 session(userId:string,hours:number){const value=token(),csrf=token(),now=Date.now();this.db.prepare('DELETE FROM pilot_sessions WHERE expires_at<?').run(now);this.db.prepare('INSERT INTO pilot_sessions VALUES (?,?,?,?,?)').run(digest(value),userId,digest(csrf),now+hours*3600000,now);return {value,csrf};}
 getSession(value:string,idleMinutes:number):Session|null{if(!value||value.length>100)return null;const hash=digest(value),now=Date.now();const row=this.db.prepare('SELECT s.*,u.tenant_id,u.email,u.disabled FROM pilot_sessions s JOIN pilot_users u ON s.user_id=u.id WHERE s.hash=?').get(hash);if(!row)return null;if(row.disabled||Number(row.expires_at)<now||now-Number(row.last_seen)>idleMinutes*60000){this.db.prepare('DELETE FROM pilot_sessions WHERE hash=?').run(hash);return null;}if(now-Number(row.last_seen)>60000)this.db.prepare('UPDATE pilot_sessions SET last_seen=? WHERE hash=?').run(now,hash);return {userId:String(row.user_id),tenantId:String(row.tenant_id),email:String(row.email),csrfHash:String(row.csrf_hash)};}
 adminSession(identity:Identity){if(identity.issuer!=='https://accounts.google.com'||!identity.verified||!identity.subject||!identity.email)throw Error('Identidade inválida.');const value=token(),csrf=token(),now=Date.now();this.db.prepare('DELETE FROM pilot_admin_sessions WHERE expires_at<?').run(now);this.db.prepare('INSERT INTO pilot_admin_sessions VALUES (?,?,?,?,?,?)').run(digest(value),identity.email.toLowerCase(),identity.subject,digest(csrf),now+3600000,now);return {value,csrf};}
 getAdmin(value:string,allowed:string[]){if(!value||value.length>100)return null;const hash=digest(value),now=Date.now();const row=this.db.prepare('SELECT * FROM pilot_admin_sessions WHERE hash=?').get(hash);if(!row)return null;if(!allowed.includes(String(row.email))||Number(row.expires_at)<now||now-Number(row.last_seen)>900000){this.adminLogout(value);return null;}if(now-Number(row.last_seen)>60000)this.db.prepare('UPDATE pilot_admin_sessions SET last_seen=? WHERE hash=?').run(now,hash);return {email:String(row.email),csrfHash:String(row.csrf_hash),context:digest(String(row.subject)+':'+String(row.email))};}
 adminLogout(value:string){this.db.prepare('DELETE FROM pilot_admin_sessions WHERE hash=?').run(digest(value));}
 logout(value:string){this.db.prepare('DELETE FROM pilot_sessions WHERE hash=?').run(digest(value));}
 revoke(email:string){this.db.exec('BEGIN IMMEDIATE');try{this.db.prepare('UPDATE pilot_users SET disabled=1 WHERE email=?').run(email.trim().toLowerCase());this.db.prepare('UPDATE pilot_invites SET revoked=1 WHERE email=? OR accepted_user_id IN (SELECT id FROM pilot_users WHERE disabled=1)').run(email.trim().toLowerCase());this.db.prepare('DELETE FROM pilot_sessions WHERE user_id IN (SELECT id FROM pilot_users WHERE disabled=1)').run();this.db.exec('COMMIT');}catch(e){this.db.exec('ROLLBACK');throw e;}}
 limited(key:string,maximum:number,windowMs=600000){const now=Date.now();this.db.prepare('DELETE FROM pilot_limits WHERE window_start<?').run(now-windowMs);const row=this.db.prepare('SELECT count FROM pilot_limits WHERE key=?').get(key);this.db.prepare('INSERT INTO pilot_limits VALUES (?,?,1) ON CONFLICT(key) DO UPDATE SET count=count+1').run(key,now);return Number(row?.count??0)>=maximum;}
 close(){this.db.close();}
}
