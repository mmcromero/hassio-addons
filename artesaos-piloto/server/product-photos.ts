import type {FastifyInstance} from 'fastify';
import type {DatabaseSync} from 'node:sqlite';
import {createHash,randomBytes} from 'node:crypto';
import {mkdirSync,lstatSync,openSync,closeSync,readFileSync,writeFileSync,constants,fstatSync,fsyncSync,linkSync,unlinkSync} from 'node:fs';
import {join} from 'node:path';
import {PNG} from 'pngjs';

export const PHOTO_LIMIT=500*1024;
const reference=/^api\/product-photos\/([a-f0-9]{32})\/([a-f0-9]{64})\.png$/;
const stores=new WeakMap<DatabaseSync,ProductPhotos>();
export const PHOTO_REFERENCE_ERROR='Envie a foto pelo aplicativo. Novas URLs externas não são permitidas.';
/** Bounded decoding, CRC verification and re-encoding remove metadata and extra payloads. */
export function optimizedPng(base64:string){
 if(!base64||base64.length>683000||!/^(?:[A-Za-z0-9+/]{4})*(?:[A-Za-z0-9+/]{2}==|[A-Za-z0-9+/]{3}=)?$/.test(base64))throw Error('invalid image');
 const input=Buffer.from(base64,'base64');
 if(input.length>PHOTO_LIMIT||input.length<33||!input.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10]))||input.readUInt32BE(8)!==13||input.toString('ascii',12,16)!=='IHDR'||input[28]!==0)throw Error('invalid PNG');
 let at=8,headers=0,ended=false;
 while(at+12<=input.length){const length=input.readUInt32BE(at),kind=input.toString('ascii',at+4,at+8);if(length>input.length-at-12)throw Error('invalid PNG');if(kind==='IHDR'&&++headers!==1)throw Error('duplicate header');at+=12+length;if(kind==='IEND'){ended=true;break;}}
 if(!ended||at!==input.length||headers!==1)throw Error('invalid PNG');
 const w=input.readUInt32BE(16),h=input.readUInt32BE(20);if(!w||!h||w>1024||h>1024)throw Error('invalid dimensions');
 const png=PNG.sync.write(PNG.sync.read(input,{checkCRC:true}));if(png.length>PHOTO_LIMIT)throw Error('image too large');
 return {png,width:w,height:h};
}
export class ProductPhotos{
 readonly directory:string;readonly owner:string;
 constructor(dataDir:string){
  this.directory=join(dataDir,'product-photos');mkdirSync(this.directory,{recursive:true,mode:0o700});if(!lstatSync(this.directory).isDirectory()||lstatSync(this.directory).isSymbolicLink())throw Error('Unsafe media directory');
  const ownerPath=join(this.directory,'.owner');
  try{writeFileSync(ownerPath,randomBytes(16).toString('hex'),{flag:'wx',mode:0o600});}catch(e){if((e as NodeJS.ErrnoException).code!=='EEXIST')throw e;}
  const fd=openSync(ownerPath,constants.O_RDONLY|constants.O_NOFOLLOW);try{if(!fstatSync(fd).isFile()||fstatSync(fd).size!==32)throw Error('Invalid media owner');this.owner=readFileSync(fd,'utf8');}finally{closeSync(fd);}if(!/^[a-f0-9]{32}$/.test(this.owner))throw Error('Invalid media owner');
 }
 read(url:string):Buffer|null{
  const match=reference.exec(url);if(!match||match[1]!==this.owner)return null;
  let fd:number|undefined;try{fd=openSync(join(this.directory,match[2]+'.png'),constants.O_RDONLY|constants.O_NOFOLLOW);const stat=fstatSync(fd);if(!stat.isFile()||stat.size>PHOTO_LIMIT)return null;const data=readFileSync(fd);return createHash('sha256').update(data).digest('hex')===match[2]?data:null;}catch{return null;}finally{if(fd!==undefined)closeSync(fd);}
 }
 put(base64:string){let decoded:ReturnType<typeof optimizedPng>;try{decoded=optimizedPng(base64);}catch{throw Error('Invalid image');}const {png,width,height}=decoded,hash=createHash('sha256').update(png).digest('hex'),url=`api/product-photos/${this.owner}/${hash}.png`;
  const temporary=join(this.directory,'.upload-'+randomBytes(16).toString('hex'));
  const fd=openSync(temporary,'wx',0o600);try{writeFileSync(fd,png);fsyncSync(fd);}finally{closeSync(fd);}
  try{try{linkSync(temporary,join(this.directory,hash+'.png'));}catch(e){if((e as NodeJS.ErrnoException).code!=='EEXIST'||!this.read(url))throw e;}}finally{unlinkSync(temporary);}
  return {url,sha256:hash,bytes:png.length,width,height};
 }
}
/** Only exact legacy values on their own record are grandfathered. */
export function photoReferenceAllowed(db:DatabaseSync,value:string|undefined,previous?:string){
 if(!value)return true;
 if(value===previous&&/^https:\/\/[^\s]+$/.test(value))return true;
 return Boolean(stores.get(db)?.read(value));
}
export function registerProductPhotos(app:FastifyInstance,db:DatabaseSync,dataDir:string){
 const store=new ProductPhotos(dataDir);stores.set(db,store);
 app.post<{Body:{png:string}}>('/api/product-photos',{bodyLimit:700000,schema:{body:{type:'object',additionalProperties:false,required:['png'],properties:{png:{type:'string',maxLength:683000}}}}},(req,reply)=>{
  try{return store.put(req.body.png);}catch(e){if((e as NodeJS.ErrnoException).code)return reply.code(503).send({message:'Não foi possível guardar a foto. Preserve o formulário e tente novamente.'});return reply.code(400).send({message:'Use uma foto PNG válida de até 1024 × 1024 pixels e 500 KB após otimização.'});}
 });
 app.get<{Params:{owner:string;file:string}}>('/api/product-photos/:owner/:file',(req,reply)=>{const url=`api/product-photos/${req.params.owner}/${req.params.file}`,data=store.read(url);return data?reply.type('image/png').header('Content-Disposition','inline').header('X-Content-Type-Options','nosniff').send(data):reply.code(404).send({message:'Foto não encontrada.'});});
 app.addHook('onClose',async()=>{stores.delete(db);});
}
