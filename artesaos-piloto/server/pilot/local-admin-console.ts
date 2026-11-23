import {constants,openSync,writeFileSync,closeSync,fsyncSync,statSync,unlinkSync,existsSync} from 'node:fs';
import {resolve,dirname,isAbsolute,join} from 'node:path';
import {PilotStore} from './store.js';
import {LocalAdmin,bindDistribution} from './local-admin.js';
process.umask(0o077);
const [action,dataDir,output,...extra]=process.argv.slice(2);
let store:PilotStore|undefined,created=false;
try{
 if(process.env.ARTESAO_DISTRIBUTION!=='debian'||!['setup-code','recovery-code'].includes(action)||!dataDir||!output||extra.length||!isAbsolute(dataDir)||!isAbsolute(output))throw Error('Uso: ARTESAO_DISTRIBUTION=debian node dist-server/pilot/local-admin-console.js setup-code|recovery-code /diretorio/absoluto/dados /diretorio/privado/novo-arquivo');
 const parent=statSync(dirname(output));
 if(!parent.isDirectory()||(parent.mode&0o077)!==0||(process.getuid&&parent.uid!==process.getuid()))throw Error('O diretório de saída deve pertencer ao operador e ter permissão 0700.');
 if(existsSync(output))throw Error('Use um novo arquivo de saída; arquivos existentes não serão substituídos.');
 if(action==='recovery-code'&&!existsSync(join(resolve(dataDir),'pilot-control.sqlite')))throw Error('Instalação existente não encontrada.');
 store=new PilotStore(resolve(dataDir));bindDistribution(store,'debian');
 const expires=new LocalAdmin(store).issueCode(action==='setup-code'?'setup':'recovery',code=>{
  const fd=openSync(output,constants.O_WRONLY|constants.O_CREAT|constants.O_EXCL|constants.O_NOFOLLOW,0o600);created=true;
  try{writeFileSync(fd,code+'\n');fsyncSync(fd);}finally{closeSync(fd);}
 });
 process.stdout.write(`Código gravado em arquivo restrito. Válido até ${new Date(expires).toISOString()}. Leia o arquivo localmente e remova-o após o uso.\n`);
}catch(error){if(created){try{unlinkSync(output);}catch{}}process.stderr.write(error instanceof Error&&error.message.startsWith('Uso:')?error.message+'\n':'Não foi possível emitir o código. Confira modo Debian, diretório de dados, permissões e estado da instalação. Nenhum código será exibido no log.\n');process.exitCode=1;}
finally{store?.close();}
