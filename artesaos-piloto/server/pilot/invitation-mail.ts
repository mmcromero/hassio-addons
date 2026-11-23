import nodemailer from 'nodemailer';
import type {PilotConfig} from './config.js';
export type InvitationMail={to:string;name:string;code:string;expiresAt:number|null;loginUrl:string};
export type InvitationMailer={send:(mail:InvitationMail)=>Promise<void>;close?:()=>void};
export function invitationText(mail:InvitationMail){return `Olá, ${mail.name}!\n\nVocê recebeu um convite para o piloto gratuito Artesão Digital.\n\nAcesse: ${mail.loginUrl}\nCódigo do convite: ${mail.code}\n\n${mail.expiresAt===null?'Este convite não possui vencimento.':'Validade: '+new Date(mail.expiresAt).toLocaleString('pt-BR',{timeZone:'America/Sao_Paulo'})+' (horário de Brasília).'} O convite é individual e de uso único. Entre com sua conta Google. A primeira conta Google que usar este código válido ficará vinculada ao convite; ele não poderá ativar outra conta.\n\nEquipe Artesão Digital`;}
export function smtpInvitationMailer(config:PilotConfig):InvitationMailer|null{
 if(!config.smtp)return null;const smtp=config.smtp;
 const transport=nodemailer.createTransport({host:smtp.host,port:smtp.port,secure:smtp.port===465,requireTLS:true,auth:{user:smtp.user,pass:smtp.password},connectionTimeout:10000,greetingTimeout:10000,socketTimeout:20000,logger:false,debug:false});
 return {async send(mail){const result=await transport.sendMail({from:{name:'Artesão Digital',address:smtp.from},to:mail.to,subject:'Seu convite para o Artesão Digital',text:invitationText(mail),disableFileAccess:true,disableUrlAccess:true});if(!result.accepted?.some(address=>String(address).toLowerCase()===mail.to.toLowerCase()))throw Error('Envio não confirmado pelo servidor.');},close:()=>transport.close()};
}
