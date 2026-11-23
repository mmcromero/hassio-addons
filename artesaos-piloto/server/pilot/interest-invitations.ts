import {transaction} from '../foundation/transaction.js';
import type {InterestStore} from './interest.js';
import type {PilotStore} from './store.js';
import {Invitations,InvitationError} from './invitations.js';
export class InterestInvitations{
 constructor(private interests:InterestStore,private store:PilotStore,private invitations:Invitations){}
 private current(id:string){let d=this.invitations.detail(id),seen=new Set([id]);while(d.replacementId){if(seen.has(d.replacementId))throw new InvitationError(409,'Encadeamento inválido; consulte o convite.');seen.add(d.replacementId);d=this.invitations.detail(d.replacementId);}return d;}
 private phone(value:string){const digits=value.replace(/\D/g,'');return digits.length===10||digits.length===11?'55'+digits:digits.length>=12&&digits.length<=15?digits:'';}
 private stateFor(record:{id:string;email:string;whatsapp:string}){
  const linked=this.store.db.prepare('SELECT invitation_hash FROM pilot_interest_invitation_links WHERE interest_id=? ORDER BY rowid DESC LIMIT 1').get(record.id);
  let d=linked?this.current(String(linked.invitation_hash)):null;const contact=this.invitations.findContact(record.email,this.phone(record.whatsapp));if(!d||(d.status==='revoked'||d.status==='expired')&&(contact?.status==='pending'||contact?.status==='accepted'))d=contact;
  const user=this.store.db.prepare('SELECT u.id,r.registered_at FROM pilot_users u LEFT JOIN pilot_account_registrations r ON r.user_id=u.id WHERE lower(u.email)=?').get(record.email.toLowerCase());
  if(d?.status==='accepted')return {state:'registered',eligible:false,invitationId:d.id,userId:this.invitations.acceptedUserId(d.id),acceptedAt:d.acceptedAt,accountCreatedAt:this.invitations.accountCreatedAt(d.id),invitationStatus:d.status,createdAt:d.createdAt,channel:d.channel};
  if(user)return {state:'registered',eligible:false,userId:String(user.id),accountCreatedAt:user.registered_at===null?null:Number(user.registered_at),invitationId:d?.id??null};
  if(d)return {state:d.status==='pending'?'invited':d.status,eligible:false,invitationId:d.id,invitationStatus:d.status,createdAt:d.createdAt,acceptedAt:d.acceptedAt,channel:d.channel,deliveries:this.invitations.deliveries(d.id)};
  return {state:'eligible',eligible:true,invitationId:null};
 }
 status(record:{id:string;email:string;whatsapp:string}){return this.stateFor(record);}
 convert(id:string,actor:string,maxUsers:number|null){const record=this.interests.get(id);if(!record)throw new InvitationError(404,'Interessado não encontrado ou fora do período de retenção.');
  return transaction(this.store.db,()=>{
   let state=this.stateFor(record);if(state.state==='registered')return {...state,generated:false};
   let invitationId=state.invitationId,generated=false;
   if(!invitationId){const d=this.invitations.issue(record.name,record.email,actor,record.id,maxUsers,'email',this.phone(record.whatsapp));invitationId=d.id;generated=true;}
   const d=this.current(invitationId!);this.store.db.prepare('INSERT OR IGNORE INTO pilot_interest_invitation_links(interest_id,invitation_hash,registered_at,linked_at,actor,channel) VALUES(?,?,?,?,?,?)').run(record.id,d.id,record.createdAt,Date.now(),actor,d.channel);
   state=this.stateFor(record);return {...state,generated};
  });
 }
}
