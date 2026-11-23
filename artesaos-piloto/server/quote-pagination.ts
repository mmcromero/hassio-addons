import type {DatabaseSync} from 'node:sqlite';
export const quoteSearchText=(data:unknown)=>{const value=data as {title?:unknown;client?:{name?:unknown;contact?:unknown}|null};return `${value.title??''} ${value.client?.name??''} ${value.client?.contact??''}`.normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase();};
export const quoteListQuerySchema={type:'object',additionalProperties:false,properties:{page:{type:'integer',minimum:1,maximum:1000000000},pageSize:{enum:['10','15','20','30','40','50','all']},search:{type:'string',maxLength:200}}};
export type QuoteListQuery={page?:number;pageSize?:'10'|'15'|'20'|'30'|'40'|'50'|'all';search?:string};
export function pagedQuotes(db:DatabaseSync,query:QuoteListQuery,pilot=false){
 const term=(query.search??'').normalize('NFD').replace(/\p{Diacritic}/gu,'').toLocaleLowerCase().replace(/[\\%_]/g,'\\$&');
 const pattern=`%${term}%`;
 const where="archived=0 AND (search_text LIKE ? ESCAPE '\\' OR CAST(id AS TEXT) LIKE ? ESCAPE '\\')";
 const total=Number(db.prepare(`SELECT COUNT(*) AS total FROM quotes WHERE ${where}`).get(pattern,pattern)!.total);
 const size=query.pageSize==='all'?Math.max(1,total):Number(query.pageSize??10);const pages=Math.max(1,Math.ceil(total/size)),page=Math.min(query.page??1,pages);
 const rows=db.prepare(`SELECT id,revision,updated_at,json_extract(data,'$.title') AS title,COALESCE(NULLIF(TRIM(json_extract(data,'$.client.name')),''),NULLIF(TRIM(json_extract(data,'$.client.contact')),''),'Cliente a definir') AS client_name,COALESCE(json_extract(data,'$.status'),'draft') AS status,json_array_length(data,'$.items') AS item_count FROM quotes WHERE ${where} ORDER BY id DESC LIMIT ? OFFSET ?`).all(pattern,pattern,size,(page-1)*size);
 return {items:rows.map(row=>({...(pilot?(()=>{const order=db.prepare('SELECT id,status FROM orders WHERE quote_id=?').get(row.id);return {orderId:order?.id??null,orderStatus:order?.status??null};})():{}),id:Number(row.id),revision:Number(row.revision),title:row.title??'',clientName:row.client_name,status:row.status,itemCount:Number(row.item_count),updatedAt:row.updated_at})),total,page,pages,pageSize:query.pageSize??'10'};
}
