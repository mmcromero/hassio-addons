import {validPixKey,normalizePixKey} from './pix.js';
import {initializeDatabase} from '../foundation/migrations.js';
import {DatabaseSync} from 'node:sqlite';
import {existsSync,readFileSync,chmodSync} from 'node:fs';
import {join} from 'node:path';
import {createHash,randomUUID} from 'node:crypto';
import {digest} from './store.js';
import {transaction} from '../foundation/transaction.js';
export const resourceKinds=['terms','privacy','cookies','manual'] as const;
export type ResourceKind=typeof resourceKinds[number];
const escape=(s:string)=>s.replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]!));
const initial={
 terms:'Artesão Digital — Termos de Uso iniciais (beta)\nResponsabilidade do projeto: Tudoe3d. Documento inicial sujeito a revisão jurídica. O aplicativo auxilia cadastros, custos, estoque, orçamentos, vendas e controles financeiros; não substitui orientação contábil, fiscal ou profissional. Confira informações e resultados antes de utilizá-los. O beta pode apresentar erros e indisponibilidade. Mantenha cópias de segurança. Você deve ter autorização para cadastrar dados de terceiros e proteger seu acesso. O acesso comum utiliza uma conta Google e convite; a administração depende da distribuição instalada. A contribuição voluntária não compra licença, assinatura ou prioridade. A recusa dos termos permite sair, mas impede utilizar as áreas protegidas. Atualizações que exigem novo aceite serão apresentadas antes da continuidade do uso. Não são prometidas certificações, disponibilidade ou conformidade jurídica não verificadas.',
 privacy:'Artesão Digital — Política de Privacidade inicial (beta)\nResponsabilidade do projeto: Tudoe3d. Texto sujeito a revisão jurídica. O aplicativo trata a identificação da conta, dados de empresa, clientes, contatos, documentos comerciais, registros de uso necessários às operações, suporte e eventos de aceite. Os dados são utilizados para autenticação, prestação das funções e rastreabilidade. O Google participa do login; consultas opcionais de CEP enviam o CEP ao ViaCEP. O responsável pela instalação mantém os bancos, arquivos e backups; instalações Home Assistant e Debian são independentes. Não presumimos anonimização, certificação ou tratamento exclusivamente nacional. Evite registrar informações pessoais desnecessárias ou segredos no suporte. Retenção, exportação, exclusão e bases legais precisam de avaliação específica; solicitações devem ser encaminhadas ao administrador da instalação pelos meios já conhecidos. Não há contato, CNPJ ou endereço adicional verificado neste documento.',
 cookies:'Artesão Digital — Política de Cookies inicial (beta)\nResponsabilidade do projeto: Tudoe3d. Texto sujeito a revisão jurídica. Cookies de sessão, proteção de formulários e fluxos de autenticação são necessários. O navegador também utiliza mecanismos técnicos de preparação da aplicação e preferências de interface. Não foram identificados mecanismos próprios opcionais de publicidade ou análise de visitantes nesta versão. O contador de visitantes é manual e agregado por sessão de venda, sem identificação da pessoa contada. Não há opção decorativa para aceitar cookies opcionais que não existem. Caso mecanismos opcionais sejam introduzidos, deverão permanecer desativados até escolha específica, com possibilidade de recusa e alteração. O login Google segue também as políticas desse serviço.'
};
export class LegalStore{
 readonly db:DatabaseSync;
 constructor(dir:string){
  this.db=new DatabaseSync(join(dir,'pilot-legal.sqlite'));initializeDatabase(this.db,'legal');chmodSync(join(dir,'pilot-legal.sqlite'),0o600);
  try{transaction(this.db,()=>{
   const path=join(dir,'legal-config.json');const config=existsSync(path)?JSON.parse(readFileSync(path,'utf8')):null;
   if(config?.enabled){if(config.reviewed!==true)throw Error('Documentos legais não revisados.');
    for(const kind of ['terms','privacy','cookies'] as const){const d=config[kind];if(!d||!d.version?.trim()||d.version.length>100||!d.text?.trim()||d.text.length>100000||!Number.isFinite(Date.parse(d.effectiveAt))||Date.parse(d.effectiveAt)>Date.now())throw Error('Documento legal inválido.');
     const old=this.db.prepare('SELECT data FROM documents WHERE kind=? AND version=?').get(kind,d.version),data=JSON.stringify({version:d.version,effectiveAt:d.effectiveAt,text:d.text});if(old&&old.data!==data)throw Error('Versão jurídica imutável: crie uma nova versão.');
     this.db.prepare('INSERT OR IGNORE INTO documents VALUES(?,?,?)').run(kind,d.version,data);
     if(!this.db.prepare('SELECT 1 FROM resource_versions WHERE kind=? AND version=?').get(kind,d.version)){
      const id=this.create(kind,{version:d.version,content:d.text,requiresAcceptance:true},'legacy-config');this.publish(id,'legacy-config');
     }
    }
   }
   for(const kind of ['terms','privacy','cookies'] as const)if(!this.active(kind)){const id=this.create(kind,{version:'beta-1',content:initial[kind],requiresAcceptance:true},'Tudoe3d — texto inicial sujeito a revisão jurídica');this.publish(id,'Tudoe3d');}
  });}catch(e){this.db.close();throw e;}
 }
 active(kind:ResourceKind):any{return this.db.prepare('SELECT v.* FROM resource_active a JOIN resource_versions v ON v.id=a.resource_id WHERE a.kind=?').get(kind);}
 list(){return this.db.prepare('SELECT id,kind,version,content,hash,created_at,author,published_at,requires_acceptance,length(payload) bytes FROM resource_versions ORDER BY rowid DESC').all();}
 create(kind:ResourceKind,input:any,author:string){
  if(!resourceKinds.includes(kind)||typeof input.version!=='string'||!input.version.trim()||input.version.length>100||typeof input.requiresAcceptance!=='boolean')throw Error('Informe tipo, versão e regra de aceite.');
  let payload:Buffer|null=null;const content=kind==='manual'?'Manual PDF':input.content;
  if(typeof content!=='string'||!content.trim()||content.length>100000)throw Error('Conteúdo inválido (limite 100 mil caracteres).');
  if(kind==='manual'){if(typeof input.pdf!=='string'||input.pdf.length>7*1024*1024||!/^[A-Za-z0-9+/]*={0,2}$/.test(input.pdf))throw Error('PDF inválido.');payload=Buffer.from(input.pdf,'base64');if(payload.length>5*1024*1024||payload.subarray(0,5).toString()!=='%PDF-'||!payload.subarray(-2048).includes(Buffer.from('%%EOF'))||/\/(JavaScript|JS|Launch|EmbeddedFile|OpenAction)\b/i.test(payload.toString('latin1')))throw Error('Envie PDF válido de até 5 MiB.');}
  const id=randomUUID();this.db.prepare('INSERT INTO resource_versions(id,kind,version,content,payload,hash,created_at,author,requires_acceptance) VALUES(?,?,?,?,?,?,?,?,?)').run(id,kind,input.version.trim(),content,payload,createHash('sha256').update(payload??content).digest('hex'),new Date().toISOString(),author,input.requiresAcceptance?1:0);return id;
 }
 publish(id:string,author:string){return transaction(this.db,()=>{const d:any=this.db.prepare('SELECT * FROM resource_versions WHERE id=?').get(id);if(!d||d.published_at)throw Error('Rascunho não encontrado ou já publicado.');const now=new Date().toISOString(),order=Number(this.db.prepare('SELECT COALESCE(MAX(published_order),0)+1 n FROM resource_versions').get()!.n);this.db.prepare('UPDATE resource_versions SET published_at=?,published_order=?,author=? WHERE id=?').run(now,order,author,id);this.db.prepare('INSERT INTO resource_active VALUES(?,?) ON CONFLICT(kind) DO UPDATE SET resource_id=excluded.resource_id').run(d.kind,id);return {id};});}
 status(account:string){const d=this.active('terms');const baseline:any=this.db.prepare("SELECT id,published_order FROM resource_versions WHERE kind='terms' AND published_at IS NOT NULL AND requires_acceptance=1 ORDER BY published_order DESC LIMIT 1").get();
  const valid=this.db.prepare("SELECT 1 FROM resource_events e JOIN resource_versions v ON v.id=e.document_id WHERE e.account=? AND e.action='accept' AND v.kind='terms' AND v.published_order>=? LIMIT 1").get(account,baseline?.published_order??0);
  return {enabled:true,version:d.version,documentId:d.id,termsHash:d.hash,required:!valid,optionalCookies:false};
 }
 accept(account:string,version:unknown,hash:unknown,accepted:unknown,tenant=account,context=''){
  const current=this.status(account);if(accepted!==true||version!==current.version||hash!==current.termsHash)return false;
  transaction(this.db,()=>{this.event(account,tenant,current.documentId,'accept',context);this.db.prepare('INSERT OR IGNORE INTO acceptances VALUES(?,?,?)').run(account,current.version,new Date().toISOString());});return true;
 }
 event(account:string,tenant:string,id:string,action:string,context:string){
  const d:any=this.db.prepare('SELECT * FROM resource_versions WHERE id=? AND published_at IS NOT NULL').get(id);if(!d||d.kind==='manual'||!['accept','acknowledge','refuse','preference'].includes(action)||action==='accept'&&d.kind!=='terms'||action==='preference'&&d.kind!=='cookies')throw Error('Evento inválido.');
  this.db.prepare('INSERT INTO resource_events(account,tenant,document_id,action,created_at,session_context,manual_id) VALUES(?,?,?,?,?,?,?)').run(account,tenant,id,action,new Date().toISOString(),digest(context),this.active('manual')?.id??null);
 }
 audit(account?:string,page=1){if(!Number.isSafeInteger(page)||page<1||page>100000)throw Error('Página inválida.');return this.db.prepare('SELECT e.*,v.kind,v.version,v.hash FROM resource_events e JOIN resource_versions v ON v.id=e.document_id'+(account?' WHERE e.account=?':'')+' ORDER BY e.id DESC LIMIT 500 OFFSET ?').all(...(account?[account]:[]),(page-1)*500);}
 contribution(){const c:any=this.db.prepare('SELECT * FROM contribution_config WHERE id=1').get();return c.enabled&&validPixKey(c.pix_key)&&c.beneficiary.trim()?{enabled:true,key:c.pix_key,beneficiary:c.beneficiary,message:c.message}:{enabled:false};}
 configurePix(input:any){
  if(!input||typeof input.enabled!=='boolean'||!['key','beneficiary','message'].every(k=>typeof input[k]==='string')||input.key.length>254||input.beneficiary.length>200||input.message.length>1000)throw Error('Confira chave Pix, beneficiário e mensagem (limites: 254, 200 e 1000 caracteres).');
  const key=normalizePixKey(input.key);if(input.enabled&&(!validPixKey(key)||!input.beneficiary.trim()))throw Error('Informe uma chave Pix válida e o nome do beneficiário. Para telefone brasileiro, use DDD e número; CPF/CNPJ devem ter dígitos válidos.');
  if(/[\x00-\x1f\x7f]/.test(key))throw Error('A chave Pix contém caracteres inválidos.');
  const saved:any=this.db.prepare('INSERT INTO contribution_config(id,enabled,pix_key,beneficiary,message) VALUES(1,?,?,?,?) ON CONFLICT(id) DO UPDATE SET enabled=excluded.enabled,pix_key=excluded.pix_key,beneficiary=excluded.beneficiary,message=excluded.message RETURNING *').get(input.enabled?1:0,key,input.beneficiary.trim(),input.message.trim());if(!saved)throw Error('Salvamento não confirmado pelo armazenamento.');return {ok:true,config:{enabled:!!saved.enabled,key:saved.pix_key,beneficiary:saved.beneficiary,message:saved.message}};
 }

 publicPage(prefix:string,returnTo=''){return `<!doctype html><html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Documentos — Artesão Digital</title><link rel="stylesheet" href="${prefix}pilot.css"></head><body><main class="pilot-auth"><h1>Artesão Digital — Tudoe3d</h1><p>Documentos iniciais sujeitos a revisão jurídica.</p>${(['terms','privacy','cookies'] as const).map((kind,i)=>{const d=this.active(kind);return `<section id="${kind}"><h2>${['Termos de Uso','Política de Privacidade','Política de Cookies'][i]}</h2><p>Versão ${escape(d.version)} · ${escape(d.published_at)}</p><div style="white-space:pre-wrap;overflow-wrap:anywhere">${escape(d.content)}</div></section>`;}).join('')}<h2>Histórico publicado</h2>${this.list().filter((d:any)=>d.published_at&&d.kind!=='manual').map((d:any)=>`<details><summary>${escape(d.kind)} — ${escape(d.version)}</summary><p style="white-space:pre-wrap">${escape(d.content)}</p></details>`).join('')}<form method="get" action="${prefix}legal/back"><input type="hidden" name="returnTo" value="${escape(returnTo)}"><button type="submit">Voltar</button></form></main></body></html>`;}
 close(){this.db.close();}
}
