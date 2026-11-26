import {createHash,randomUUID} from "node:crypto";
import {mkdir,open,readFile,lstat} from "node:fs/promises";
import path from "node:path";
const GENESIS="0".repeat(64),TYPES=new Set(["homologation","evidence","decision"]),STATUSES=new Set(["PASS","FAIL","NAO_EXECUTADO","NAO_VERIFICADO","BLOQUEADO","INDISPONIVEL"]),MAX_FILE=5*1024*1024,MAX_RECORD=12000;
const text=(v,n)=>typeof v==="string"?v.trim().slice(0,n):"";
const digest=v=>createHash("sha256").update(JSON.stringify(v)).digest("hex");
function validate(v){
 if(!v||typeof v!=="object"||Array.isArray(v))throw Object.assign(new Error("Registro inválido."),{status:400,code:"INVALID_RECORD"});
 const type=text(v.type,32),status=text(v.status,32);
 if(!TYPES.has(type))throw Object.assign(new Error("Tipo inválido."),{status:400,code:"INVALID_TYPE"});
 if(type==="homologation"&&!STATUSES.has(status))throw Object.assign(new Error("Estado inválido."),{status:400,code:"INVALID_STATUS"});
 const title=text(v.title,160),summary=text(v.summary,2000);if(!title||!summary)throw Object.assign(new Error("Título e descrição são obrigatórios."),{status:400,code:"REQUIRED_FIELDS"});
 const row={type,title,summary,status:type==="homologation"?status:null,projectId:text(v.projectId,64)||null,repository:text(v.repository,160)||null,sha:text(v.sha,64)||null,version:text(v.version,64)||null,environment:text(v.environment,80)||null,responsible:text(v.responsible,80)||null,origin:text(v.origin,80)||"Portal",evidenceKind:type==="evidence"?(v.evidenceKind==="real"?"real":"synthetic"):null,sourceUrl:text(v.sourceUrl,500)||null};
 if(row.sha&&!/^[a-f0-9]{7,64}$/i.test(row.sha))throw Object.assign(new Error("SHA inválido."),{status:400,code:"INVALID_SHA"});if(row.sourceUrl){let u;try{u=new URL(row.sourceUrl);}catch{throw Object.assign(new Error("URL de origem inválida."),{status:400,code:"INVALID_SOURCE_URL"});}if(u.protocol!=="https:")throw Object.assign(new Error("A URL de origem deve usar HTTPS."),{status:400,code:"INVALID_SOURCE_URL"});row.sourceUrl=u.toString();}return row;
}
export function createLedger({filePath="/data/portal-ledger.ndjson",now=()=>new Date().toISOString(),id=randomUUID}={}){
 let queue=Promise.resolve();
 async function ensure(){await mkdir(path.dirname(filePath),{recursive:true,mode:0o700});try{const s=await lstat(filePath);if(!s.isFile()||s.isSymbolicLink())throw new Error("Arquivo de histórico não regular.");}catch(e){if(e.code!=="ENOENT")throw e;}}
 async function read(){await ensure();let raw;try{raw=await readFile(filePath,"utf8");}catch(e){if(e.code==="ENOENT")return [] ;throw e;}if(Buffer.byteLength(raw)>MAX_FILE)throw Object.assign(new Error("Histórico excede limite de leitura."),{status:503,code:"LEDGER_TOO_LARGE"});if(!raw)return [];if(!raw.endsWith("\n"))throw Object.assign(new Error("Último registro incompleto; gravação bloqueada."),{status:503,code:"LEDGER_TORN_WRITE"});let previous=GENESIS;const rows=raw.trimEnd().split("\n").map((line,i)=>{let row;try{row=JSON.parse(line);}catch{throw Object.assign(new Error("JSON inválido na linha "+(i+1)),{status:503,code:"LEDGER_CORRUPT"});}const {hash,...payload}=row;if(row.previousHash!==previous||digest(payload)!==hash)throw Object.assign(new Error("Integridade inválida na linha "+(i+1)),{status:503,code:"LEDGER_INTEGRITY_FAILED"});previous=hash;return row;});return rows;}
 async function list(){const rows=await read();return {records:rows.slice(-500).reverse(),total:rows.length,integrity:"valid",lastHash:rows.at(-1)?.hash||GENESIS};}
 async function append(input){const op=queue.then(async()=>{const record=validate(input),rows=await read(),previousHash=rows.at(-1)?.hash||GENESIS,payload={id:id(),createdAt:now(),...record,previousHash},row={...payload,hash:digest(payload)},line=JSON.stringify(row)+"\n";if(Buffer.byteLength(line)>MAX_RECORD)throw Object.assign(new Error("Registro excede limite."),{status:413,code:"RECORD_TOO_LARGE"});const h=await open(filePath,0o600|1|0x40|0x400|0x20000);try{const s=await h.stat();if(!s.isFile()||s.size+Buffer.byteLength(line)>MAX_FILE)throw Object.assign(new Error("Limite de armazenamento atingido."),{status:507,code:"LEDGER_STORAGE_LIMIT"});await h.writeFile(line,"utf8");await h.sync();}finally{await h.close();}return row;});queue=op.catch(()=>{});return op;}
 return {list,append};
}