import {PDFDocument} from 'pdf-lib';
import type {FastifyInstance} from 'fastify';
import type {LegalStore,ResourceKind} from './legal.js';
import {resourceAdminHtml,resourceAdminScript} from './resource-ui.js';
import {adminNavigation} from './admin-navigation.js';
export function registerResourceAdmin(app:FastifyInstance,base:string,legal:LegalStore,auth:(req:any,reply:any,write:boolean)=>any,page:(title:string,body:string,extra?:string)=>string){
 const run=(fn:(req:any,admin:any)=>any)=>async(req:any,reply:any)=>{const a=auth(req,reply,req.method!=='GET');if(!a)return;try{return await fn(req,a);}catch{return reply.code(400).send({message:'Não foi possível salvar. Confira tipo, versão única, conteúdo e limites do arquivo.'});}};
 app.get(base+'resources',(req,reply)=>{const a=auth(req,reply,false);if(!a)return;return reply.type('text/html').send(page('Documentos, manual e contribuição',adminNavigation(base,'resources')+resourceAdminHtml(),`<meta name="pilot-admin-context" content="${a.context}"><script defer src="${base}session.js"></script><script defer src="${base}resources.js"></script>`));});
 app.get(base+'resources.js',(_req,reply)=>reply.type('application/javascript').send(resourceAdminScript(base)));
 app.get(base+'api/resources',run(()=>({versions:legal.list(),legacyVersions:legal.db.prepare('SELECT kind,version,data FROM documents ORDER BY kind,version').all(),legacyAcceptances:legal.db.prepare("SELECT a.* FROM acceptances a WHERE NOT EXISTS(SELECT 1 FROM resource_events e JOIN resource_versions v ON v.id=e.document_id WHERE e.account=a.account AND e.action='accept' AND v.kind='terms' AND v.version=a.version) ORDER BY a.accepted_at DESC").all(),pix:legal.db.prepare('SELECT * FROM contribution_config WHERE id=1').get()})));
 app.post(base+'api/resources',{bodyLimit:8*1024*1024},run(async(req,a)=>{if(req.body?.kind==='manual'){if(typeof req.body.pdf!=='string'||req.body.pdf.length>7*1024*1024)throw Error('PDF inválido');const pdf=await PDFDocument.load(Buffer.from(req.body.pdf,'base64'),{ignoreEncryption:false,updateMetadata:false});if(pdf.getPageCount()<1)throw Error('Manual sem páginas');}return {id:legal.create(req.body?.kind as ResourceKind,req.body,a.email)};}));
 app.post(base+'api/resources/:id/publish',run((req,a)=>legal.publish(req.params.id,a.email)));
 app.put(base+'api/contribution',{bodyLimit:4096},(req,reply)=>{if(!auth(req,reply,true))return;try{return legal.configurePix(req.body);}catch(error){return reply.code(400).send({message:error instanceof Error?error.message:'Não foi possível salvar o Pix.'});}});
 app.get(base+'api/legal-audit',run(req=>legal.audit(typeof req.query?.account==='string'?req.query.account:undefined,Number(req.query?.page??1))));
 app.get(base+'resources/:id/pdf',(req:any,reply)=>{if(!auth(req,reply,false))return;const row:any=legal.db.prepare("SELECT payload FROM resource_versions WHERE id=? AND kind='manual'").get(req.params.id);return row?reply.type('application/pdf').header('Content-Disposition','attachment; filename="manual-artesao-digital.pdf"').send(Buffer.from(row.payload)):reply.code(404).send({message:'Manual não encontrado.'});});
}
