import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
export type PilotConfig={distribution?:'home-assistant'|'debian';publicUrl:URL;prefix:string;dataDir:string;staticDir:string;clientId:string;clientSecret:string;sessionHours:number;idleMinutes:number;maxUsers:number|null;smtp?:{host:string;port:465|587;user:string;password:string;from:string};adminEmails?:string[];mercadopagoToken?:string;};
export function pilotConfig(env:NodeJS.ProcessEnv=process.env):PilotConfig{
 const distribution=env.ARTESAO_DISTRIBUTION??'home-assistant';
 if(!['home-assistant','debian'].includes(distribution))throw Error('Distribuição inválida.');
 let options:Record<string,unknown>={};
 if(env.PILOT_OPTIONS_FILE)options=JSON.parse(readFileSync(env.PILOT_OPTIONS_FILE,'utf8'));
 const value=(key:string,option:string)=>String(env[key]??options[option]??'');
 const raw=value('PILOT_PUBLIC_URL','public_url');
 if(!raw)throw Error('Configure public_url HTTPS antes de iniciar o piloto.');
 const publicUrl=new URL(raw);
 if(publicUrl.protocol!=='https:'||publicUrl.username||publicUrl.password||publicUrl.search||publicUrl.hash||publicUrl.pathname!=='/artesaos-piloto/')throw Error('public_url deve usar HTTPS e terminar em /artesaos-piloto/, sem credenciais ou parâmetros.');
 const clientId=value('GOOGLE_CLIENT_ID','google_client_id'),clientSecret=value('GOOGLE_CLIENT_SECRET','google_client_secret');
 if(!clientId||!clientSecret)throw Error('Configure o cliente OAuth Google antes de iniciar o piloto.');
 const admins:unknown=env.PILOT_ADMIN_EMAILS!==undefined?env.PILOT_ADMIN_EMAILS.split(',').map(s=>s.trim()).filter(Boolean):(options.admin_emails??[]);
 if(!Array.isArray(admins)||admins.length>20||admins.some(v=>typeof v!=='string'||v.length>254||!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(v)))throw Error('Confira os e-mails administrativos.');
 const adminEmails=[...new Set((admins as string[]).map(s=>s.trim().toLowerCase()))];
 const mercadopagoToken=value('MERCADOPAGO_ACCESS_TOKEN','mercadopago_access_token').trim();
 if(mercadopagoToken&&!/^[A-Za-z0-9_-]{20,300}$/.test(mercadopagoToken))throw Error('Confira o token do Mercado Pago na configuração.');
 const smtpValues={host:value('PILOT_SMTP_HOST','smtp_host'),port:value('PILOT_SMTP_PORT','smtp_port'),user:value('PILOT_SMTP_USER','smtp_user'),password:value('PILOT_SMTP_PASSWORD','smtp_password'),from:value('PILOT_SMTP_FROM','smtp_from')};
 let smtp:PilotConfig['smtp'];
 if(Object.values(smtpValues).some(Boolean)){
  if(!/^[a-zA-Z0-9.-]+$/.test(smtpValues.host)||![465,587].includes(Number(smtpValues.port))||!smtpValues.user.trim()||!smtpValues.password||smtpValues.from.length>254||!/^[^\s@<>;,]+@[^\s@<>;,]+\.[^\s@<>;,]+$/.test(smtpValues.from))throw Error('Confira a configuração SMTP completa (porta 465 ou 587 com TLS).');
  smtp={...smtpValues,port:Number(smtpValues.port) as 465|587};
 }
 return {distribution:distribution as 'home-assistant'|'debian',smtp,adminEmails,...(mercadopagoToken?{mercadopagoToken}:{}),publicUrl,prefix:publicUrl.pathname,dataDir:resolve(env.DATA_DIR??'/data'),staticDir:resolve(env.PILOT_STATIC_DIR??new URL('../../dist/',import.meta.url).pathname),clientId,clientSecret,sessionHours:8,idleMinutes:30,maxUsers:null};
}
