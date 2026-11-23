import type {DatabaseSync} from 'node:sqlite';
import type {FastifyInstance} from 'fastify';
import {renderQuotePdf} from './quote-pdf.js';
export type DocumentData={company:Record<string,string>;quote:{client:Record<string,unknown>;items:{name:string;quantity:string;priceKey:string;prices:Record<string,number>;packaging:string;packagingIncluded:boolean;packagingAmount:string;packagingType?:string}[];notes:string;delivery:{mode:string;carrier:string;notes:string}};totals:{productCents:number;packagingCents:number;deliveryCents:number;totalCents:number}};

export function captureDocument(db:DatabaseSync,id:number,revision:number,quote:unknown,totals:unknown){
 const company=db.prepare('SELECT data FROM company_profile WHERE id=1').get();
 if(!company)throw Error('Salve os dados da empresa antes de finalizar.');
 const edition=Number(db.prepare('SELECT COALESCE(MAX(edition),0)+1 AS n FROM quote_documents WHERE quote_id=?').get(id)!.n);
 db.prepare('INSERT INTO quote_documents VALUES(?,?,?,?,?)').run(id,edition,revision,new Date().toISOString(),JSON.stringify({company:JSON.parse(String(company.data)),quote,totals}));
}
let generating=0;
export function registerQuoteDocuments(app:FastifyInstance,db:DatabaseSync){

 app.get<{Params:{id:string}}>('/api/quotes/:id/documents',(req,reply)=>{
  if(!db.prepare('SELECT 1 FROM quotes WHERE id=? AND archived=0').get(req.params.id))return reply.code(404).send({message:'Orçamento não encontrado.'});
  return db.prepare('SELECT edition,source_revision AS sourceRevision,finalized_at AS finalizedAt FROM quote_documents WHERE quote_id=? ORDER BY edition DESC').all(req.params.id);
 });
 app.get<{Params:{id:string};Querystring:{edition?:number}}>('/api/quotes/:id/document',{schema:{querystring:{type:'object',additionalProperties:false,properties:{edition:{type:'integer',minimum:1}}}}},async(req,reply)=>{
  const row=db.prepare('SELECT d.* FROM quote_documents d JOIN quotes q ON q.id=d.quote_id WHERE q.archived=0 AND d.quote_id=? AND (? IS NULL OR d.edition=?) ORDER BY d.edition DESC LIMIT 1').get(req.params.id,req.query.edition??null,req.query.edition??null);
  if(!row)return reply.code(404).send({message:'Esta edição não tem documento final. Para orçamentos antigos, reabra como rascunho e finalize novamente para registrar os dados atuais da empresa.'});
  if(generating>=2)return reply.code(503).send({message:'Geração ocupada. Tente novamente em instantes.'});
  generating++;
  try{
   const logo=db.prepare('SELECT image FROM company_logo WHERE id=1').get()?.image;
   const pdf=await renderQuotePdf(Number(row.quote_id),Number(row.edition),String(row.finalized_at),JSON.parse(String(row.data)),logo?Buffer.from(logo as Uint8Array):undefined);
   return reply.type('application/pdf').header('Content-Disposition',`attachment; filename="orcamento-${row.quote_id}-edicao-${row.edition}.pdf"`).send(Buffer.from(pdf));
  }finally{generating--;}
 });
}
