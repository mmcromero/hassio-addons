import {randomBytes,createCipheriv,createDecipheriv,createHmac,randomUUID} from 'node:crypto';
import {existsSync,writeFileSync,readFileSync,lstatSync,chmodSync} from 'node:fs';
import {join} from 'node:path';
import {PilotStore,digest,token} from './store.js';
export class InvitationError extends Error{constructor(readonly status:number,message:string){super(message);}}
export class Invitations{
 private key:Buffer;private phoneKey:Buffer;
 constructor(private store:PilotStore,dir:string){

  const path=join(dir,'pilot-invitations.key');
  if(!existsSync(path)){if(store.db.prepare('SELECT 1 FROM pilot_invitation_keycheck').get()||store.db.prepare('SELECT 1 FROM pilot_invitation_details').get())throw Error('Chave dos convites ausente. Restaure a cópia completa do volume.');try{writeFileSync(path,randomBytes(32),{flag:'wx',mode:0o600});}catch(e){if(!existsSync(path))throw e;}}
  if(!lstatSync(path).isFile()||lstatSync(path).isSymbolicLink())throw Error('Chave dos convites inválida.');chmodSync(path,0o600);this.key=readFileSync(path);if(this.key.length!==32)throw Error('Chave dos convites inválida.');this.phoneKey=createHmac('sha256',this.key).update('pilot-invitation-phone-key-v1').digest();
  const check=store.db.prepare('SELECT * FROM pilot_invitation_keycheck WHERE id=1').get();if(check){if(this.decrypt(check,'keycheck')!=='pilot-invitations-v1')throw Error('Chave dos convites inválida.');}else{const c=this.encrypt('pilot-invitations-v1','keycheck');store.db.prepare('INSERT INTO pilot_invitation_keycheck VALUES(1,?,?,?)').run(c.iv,c.tag,c.payload);}
  this.transaction(()=>{
   if(store.db.prepare('SELECT 1 FROM legacy_data_jobs WHERE name=?').get('invitation-phone-hash-v1'))return;
   const update=store.db.prepare('UPDATE pilot_invitation_details SET phone_hash=? WHERE hash=?');for(const row of store.db.prepare('SELECT * FROM pilot_invitation_details WHERE phone_hash IS NULL').iterate()){const saved=JSON.parse(this.decrypt(row,String(row.hash)));update.run(this.phoneHash(saved.phone||''),String(row.hash));}

   store.db.prepare('INSERT INTO legacy_data_jobs VALUES(?,?)').run('invitation-phone-hash-v1',new Date().toISOString());
  });
  store.db.prepare("UPDATE pilot_invitation_deliveries SET status='unconfirmed',finished_at=? WHERE status='sending'").run(Date.now());
 }
 private transaction<T>(fn:()=>T):T{const db=this.store.db,nested=db.isTransaction;db.exec(nested?'SAVEPOINT invitation_action':'BEGIN IMMEDIATE');try{const result=fn();db.exec(nested?'RELEASE invitation_action':'COMMIT');return result;}catch(e){db.exec(nested?'ROLLBACK TO invitation_action':'ROLLBACK');if(nested)db.exec('RELEASE invitation_action');throw e;}}
 private encrypt(text:string,aad:string){const iv=randomBytes(12),c=createCipheriv('aes-256-gcm',this.key,iv);c.setAAD(Buffer.from(aad));return {iv,payload:Buffer.concat([c.update(text,'utf8'),c.final()]),tag:c.getAuthTag()};}
 private decrypt(row:Record<string,unknown>,aad:string){const c=createDecipheriv('aes-256-gcm',this.key,row.iv as Uint8Array);c.setAAD(Buffer.from(aad));c.setAuthTag(row.tag as Uint8Array);return Buffer.concat([c.update(row.payload as Uint8Array),c.final()]).toString('utf8');}
 private phoneHash(phone:string){return phone?createHmac('sha256',this.phoneKey).update(phone).digest('hex'):'';}
 private record(row:Record<string,unknown>,includeCode=false){
  const accepted=row.accepted_user_id?this.store.db.prepare('SELECT email FROM pilot_users WHERE id=?').get(String(row.accepted_user_id)):null;
  const saved=row.payload?JSON.parse(this.decrypt(row,String(row.hash))):null,legacy=!saved||saved.legacy===true;
  return {id:String(row.hash),bindingMode:row.binding_mode==='first_google'?'first_google':'email',acceptedGoogleEmail:accepted?String(accepted.email):null,name:saved?.name??null,channel:saved?.channel??'email',phone:saved?.phone||null,email:String(row.email),createdBy:row.created_by?String(row.created_by):null,createdAt:legacy?null:row.created_at?Number(row.created_at):null,expiresAt:row.no_expiry?null:Number(row.expires_at),acceptedAt:row.used_at?Number(row.used_at):null,status:row.used_at?'accepted':row.revoked?'revoked':!row.no_expiry&&Number(row.expires_at)<=Date.now()?'expired':'pending',legacy,codeAvailable:!!saved?.code,previousId:row.previous_hash?String(row.previous_hash):null,replacementId:row.replacement_hash?String(row.replacement_hash):null,...(includeCode?{code:saved?.code??null}:{})};
 }
 private row(id:string){return this.store.db.prepare('SELECT i.*,d.created_at,d.created_by,d.request_key,d.iv,d.tag,d.payload,d.previous_hash,d.replacement_hash FROM pilot_invites i LEFT JOIN pilot_invitation_details d ON d.hash=i.hash WHERE i.hash=?').get(id);}
 detail(id:string){const row=this.row(id);if(!row)throw new InvitationError(404,'Convite não encontrado.');return {...this.record(row,true),deliveries:this.deliveries(id),shareEvents:this.store.db.prepare('SELECT actor,event,created_at FROM pilot_invitation_share_events WHERE invitation_hash=? ORDER BY created_at DESC').all(id)};}
 deliveries(id:string){return this.store.db.prepare('SELECT id,method,status,started_at,finished_at FROM pilot_invitation_deliveries WHERE invite_hash=? ORDER BY started_at DESC').all(id);}
 recordShare(id:string,actor:string,event:string,key:string){if(!['copy_code','copy_link','copy_message','open_whatsapp','native_share'].includes(event))throw new InvitationError(400,'Ação inválida.');return this.transaction(()=>{this.detail(id);const old=this.store.db.prepare('SELECT * FROM pilot_invitation_share_events WHERE request_key=?').get(key);if(old&&(old.invitation_hash!==id||old.actor!==actor||old.event!==event))throw new InvitationError(409,'Solicitação divergente.');this.store.db.prepare('INSERT OR IGNORE INTO pilot_invitation_share_events VALUES(?,?,?,?,?)').run(key,id,actor,event,Date.now());return {ok:true};});}
 acceptedUserId(id:string){return this.store.db.prepare('SELECT accepted_user_id FROM pilot_invites WHERE hash=?').get(id)?.accepted_user_id??null;}
 accountCreatedAt(id:string){return this.store.db.prepare('SELECT r.registered_at FROM pilot_account_registrations r JOIN pilot_invites i ON i.accepted_user_id=r.user_id WHERE i.hash=?').get(id)?.registered_at??null;}
 findContact(email:string,phone:string){const phoneHash=this.phoneHash(phone);const row=this.store.db.prepare(`SELECT i.hash FROM pilot_invites i LEFT JOIN pilot_invitation_details d ON d.hash=i.hash WHERE (i.email=? OR (?<>'' AND d.phone_hash=?)) AND d.replacement_hash IS NULL ORDER BY CASE WHEN i.used_at IS NOT NULL THEN 0 WHEN i.revoked=0 AND (i.no_expiry=1 OR i.expires_at>?) THEN 1 ELSE 2 END,i.rowid DESC LIMIT 1`).get(email.toLowerCase(),phoneHash,phoneHash,Date.now());return row?this.detail(String(row.hash)):null;}
 contactForUser(userId:string){const row=this.store.db.prepare('SELECT i.*,d.created_at,d.iv,d.tag,d.payload FROM pilot_invites i JOIN pilot_invitation_details d ON d.hash=i.hash WHERE i.accepted_user_id=? AND i.used_at IS NOT NULL ORDER BY i.used_at LIMIT 1').get(userId);if(!row)return null;const item=this.record(row);return {name:item.name,email:item.email,phone:item.phone,channel:item.channel,registeredAt:item.createdAt};}
 list(page=1,status='unaccepted',search=''){
  const condition=status==='unaccepted'?'i.used_at IS NULL':status==='accepted'?'i.used_at IS NOT NULL':status==='revoked'?'i.used_at IS NULL AND i.revoked=1':status==='expired'?'i.used_at IS NULL AND i.revoked=0 AND i.no_expiry=0 AND i.expires_at<=?':status==='pending'?'i.used_at IS NULL AND i.revoked=0 AND (i.no_expiry=1 OR i.expires_at>?)':'1=1';
  const args:(string|number)[]=status==='expired'||status==='pending'?[Date.now()]:[];let where=condition+' AND d.replacement_hash IS NULL';
  if(search.trim()){const value=search.trim(),digits=value.replace(/\D/g,'');if(/^[+\d ()-]+$/.test(value)&&digits.length>=8){where+=' AND d.phone_hash=?';args.push(this.phoneHash(digits));}else{where+=" AND i.email LIKE ? ESCAPE '!'";args.push('%'+value.toLowerCase().replace(/[!%_]/g,'!$&')+'%');}}
  const total=Number(this.store.db.prepare('SELECT COUNT(*) n FROM pilot_invites i LEFT JOIN pilot_invitation_details d ON d.hash=i.hash WHERE '+where).get(...args)!.n),pages=Math.max(1,Math.ceil(total/25)),current=Math.min(page,pages);
  const records=this.store.db.prepare('SELECT i.*,d.created_at,d.iv,d.tag,d.payload,d.previous_hash,d.replacement_hash FROM pilot_invites i LEFT JOIN pilot_invitation_details d ON d.hash=i.hash WHERE '+where+' ORDER BY i.rowid DESC LIMIT 25 OFFSET ?').all(...args,(current-1)*25).map(row=>this.record(row));return {records,total,page:current,pages};
 }
 issue(name:string,email:string,actor:string,requestKey:string,maxUsers:number|null,channel:'email'|'whatsapp'='email',phone='',previousId:string|null=null){
  name=name.trim();email=email.trim().toLowerCase();if(!name||name.length>100||/[\x00-\x1f\x7f<>]/.test(name)||email.length>254||(email!==''&&!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email))||/[\x00-\x20\x7f<>;,]/.test(email)||channel==='email'&&!email)throw new InvitationError(400,'Confira nome e e-mail do destinatário.');
  if(phone){if(!/^[+\d ()-]+$/.test(phone))throw new InvitationError(400,'Informe o WhatsApp com DDI e DDD.');phone=phone.replace(/\D/g,'');if(!/^[1-9]\d{7,14}$/.test(phone))throw new InvitationError(400,'Informe o WhatsApp com DDI e DDD.');}else if(channel==='whatsapp')throw new InvitationError(400,'Informe o WhatsApp com DDI e DDD.');
  return this.transaction(()=>{
   const db=this.store.db,previous=db.prepare('SELECT hash,created_by FROM pilot_invitation_details WHERE request_key=?').get(requestKey);
   if(previous){const found=this.detail(String(previous.hash));if(found.name!==name||found.email!==email||previous.created_by!==actor||found.channel!==channel||found.phone!==(phone||null)||found.previousId!==previousId)throw new InvitationError(409,'Identificador de solicitação já utilizado.');return found;}
   const hashedPhone=this.phoneHash(phone);
   const duplicateEmail=email&&db.prepare('SELECT 1 FROM pilot_invites WHERE email=? AND used_at IS NULL AND revoked=0 AND (no_expiry=1 OR expires_at>?) LIMIT 1').get(email,Date.now());
   const duplicatePhone=hashedPhone&&db.prepare('SELECT 1 FROM pilot_invitation_details d JOIN pilot_invites i ON i.hash=d.hash WHERE d.phone_hash=? AND i.used_at IS NULL AND i.revoked=0 AND (i.no_expiry=1 OR i.expires_at>?) LIMIT 1').get(hashedPhone,Date.now());
   if(duplicateEmail||duplicatePhone)throw new InvitationError(409,'Já existe convite ativo para este contato. Consulte o registro antes de gerar outro.');
   if(maxUsers!==null){const accounts=Number(db.prepare('SELECT COUNT(*) n FROM pilot_users').get()!.n),reserved=Number(db.prepare("SELECT COUNT(DISTINCT CASE WHEN binding_mode='first_google' THEN 'code:'||hash ELSE 'email:'||email END) n FROM pilot_invites WHERE used_at IS NULL AND revoked=0 AND (no_expiry=1 OR expires_at>?) AND (binding_mode='first_google' OR email NOT IN (SELECT email FROM pilot_users))").get(Date.now())!.n);if(accounts+reserved>=maxUsers)throw new InvitationError(409,'O limite configurado de contas ou convites ativos foi atingido.');}
   const code=token(),hash=digest(code),createdAt=Date.now();db.prepare("INSERT INTO pilot_invites(hash,email,expires_at,binding_mode,no_expiry) VALUES(?,?,0,'first_google',1)").run(hash,email);
   const c=this.encrypt(JSON.stringify({name,code,channel,phone}),hash);db.prepare('INSERT INTO pilot_invitation_details(hash,created_at,created_by,request_key,iv,tag,payload,phone_hash,previous_hash) VALUES(?,?,?,?,?,?,?,?,?)').run(hash,createdAt,actor,requestKey,c.iv,c.tag,c.payload,hashedPhone,previousId);return this.detail(hash);
  });
 }
 revoke(id:string){return this.transaction(()=>{const record=this.detail(id);if(record.replacementId)throw new InvitationError(409,'Este código já foi substituído. Atualize a lista.');if(record.status==='accepted')throw new InvitationError(409,'Este convite já foi aceito. A conta está em Usuários cadastrados.');this.store.db.prepare('UPDATE pilot_invites SET revoked=1 WHERE hash=? AND used_at IS NULL').run(id);return this.detail(id);});}
 reactivate(id:string,name:string,email:string,actor:string,requestKey:string,maxUsers:number|null,channel:'email'|'whatsapp',phone:string){return this.transaction(()=>{
  const old=this.detail(id);if(old.status==='accepted'||old.status==='pending')throw new InvitationError(409,'Somente convites revogados ou antigos expirados podem ser ativados novamente.');
  if(old.replacementId){const saved=this.store.db.prepare('SELECT request_key,created_by FROM pilot_invitation_details WHERE hash=?').get(old.replacementId);if(saved?.request_key===requestKey&&saved.created_by===actor)return this.issue(name,email,actor,requestKey,maxUsers,channel,phone,id);throw new InvitationError(409,'Este convite já foi substituído. Abra o registro com o novo código.');}
  const created=this.issue(name,email,actor,requestKey,maxUsers,channel,phone,id);
  this.store.db.prepare('UPDATE pilot_invites SET revoked=1 WHERE hash=?').run(id);
  if(this.store.db.prepare('SELECT 1 FROM pilot_invitation_details WHERE hash=?').get(id))this.store.db.prepare('UPDATE pilot_invitation_details SET replacement_hash=? WHERE hash=?').run(created.id,id);
  else{const c=this.encrypt(JSON.stringify({legacy:true,name:null,code:null,channel:'email',phone:''}),id);this.store.db.prepare('INSERT INTO pilot_invitation_details(hash,created_at,created_by,request_key,iv,tag,payload,phone_hash,replacement_hash) VALUES(?,?,?,?,?,?,?,?,?)').run(id,Date.now(),actor,'legacy-replaced:'+randomUUID(),c.iv,c.tag,c.payload,'',created.id);}
  return created;
 });}
 beginDelivery(id:string,actor:string,requestKey:string,method:'smtp'='smtp'){return this.transaction(()=>{
  const db=this.store.db,old=db.prepare('SELECT * FROM pilot_invitation_deliveries WHERE request_key=?').get(requestKey);if(old){if(old.invite_hash!==id||old.actor!==actor||old.method!==method)throw new InvitationError(409,'Identificador de envio já utilizado.');return {id:String(old.id),fresh:false};}
  const record=this.detail(id);if(record.status!=='pending')throw new InvitationError(409,'Este convite já foi aceito ou está inativo.');if(record.channel!=='email')throw new InvitationError(400,'Este convite foi preparado para envio pelo WhatsApp.');if(!record.code)throw new InvitationError(409,'O código deste convite antigo não está disponível.');
  if(db.prepare("SELECT 1 FROM pilot_invitation_deliveries WHERE invite_hash=? AND status='sending'").get(id))throw new InvitationError(409,'Já existe uma tentativa em andamento para este convite.');
  if(db.prepare("SELECT 1 FROM pilot_invitation_deliveries WHERE invite_hash=? AND method='smtp' AND started_at>?").get(id,Date.now()-60000))throw new InvitationError(429,'Aguarde um minuto antes de tentar novamente.');
  if(Number(db.prepare('SELECT COUNT(*) n FROM pilot_invitation_deliveries WHERE invite_hash=?').get(id)!.n)>=100)throw new InvitationError(409,'O limite técnico de tentativas deste código foi atingido.');
  const attempt=randomUUID();db.prepare('INSERT INTO pilot_invitation_deliveries VALUES(?,?,?,?,?,?,?,?)').run(attempt,id,requestKey,actor,Date.now(),null,method,'sending');return {id:attempt,fresh:true};
 });}
 finishDelivery(id:string,confirmed:boolean){this.store.db.prepare("UPDATE pilot_invitation_deliveries SET status=?,finished_at=? WHERE id=? AND status='sending'").run(confirmed?'smtp_accepted':'unconfirmed',Date.now(),id);}
 close(){this.key.fill(0);this.phoneKey.fill(0);}
}
