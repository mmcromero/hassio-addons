/** Cross-build copies production JS only. Reject native binaries instead of
 * silently copying an AMD64 dependency into an ARM64 runtime (or vice versa). */
import {readdirSync,openSync,readSync,closeSync,realpathSync} from 'node:fs';
import {resolve,relative,isAbsolute} from 'node:path';
import {pathToFileURL} from 'node:url';
export function verifyPortableRuntime(directory){
 const root=realpathSync(directory);let count=0;
 const visit=dir=>{for(const entry of readdirSync(dir,{withFileTypes:true})){
  const file=resolve(dir,entry.name);
  if(entry.isSymbolicLink()){const target=realpathSync(file),rel=relative(root,target);if(rel.startsWith('..')||isAbsolute(rel))throw Error('Dependência aponta fora do runtime.');continue;}
  if(entry.isDirectory()){visit(file);continue;}
  if(!entry.isFile())throw Error('Tipo de dependência inesperado.');
  const header=Buffer.alloc(4),fd=openSync(file,'r');try{readSync(fd,header,0,4,0);}finally{closeSync(fd);}
  if(file.endsWith('.node')||header.equals(Buffer.from([127,69,76,70]))||header.subarray(0,2).toString()==='MZ'||['feedface','feedfacf','cefaedfe','cffaedfe','cafebabe'].includes(header.toString('hex')))throw Error('Binário nativo de dependência: exige instalação para a arquitetura alvo, não cópia cruzada.');
  count++;
 }};
 visit(root);return count;
}
if(import.meta.url===pathToFileURL(resolve(process.argv[1]??'')).href)console.log('Runtime portável verificado: '+verifyPortableRuntime(resolve('node_modules'))+' arquivos sem binários nativos.');
