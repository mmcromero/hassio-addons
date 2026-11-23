import {PilotStore} from './store.js';
import {resolve} from 'node:path';
process.umask(0o077);
const [action,email]=process.argv.slice(2);
if(action==='invite'){
 process.stderr.write('Crie e gerencie os convites na administração do Artesão Digital. O comando invite foi desativado.\n');process.exitCode=1;
}else if(action!=='revoke'||!email){process.stderr.write('Uso emergencial de conta: pilot:admin -- revoke email. Convites são gerenciados pela administração Web.\n');process.exitCode=1;}
else{
 const store=new PilotStore(resolve(process.env.DATA_DIR??'/data'));
 try{store.revoke(email);process.stdout.write('Acesso da conta e convites associados revogados.\n');}catch{process.stderr.write('Não foi possível executar a ação. Confira os dados.\n');process.exitCode=1;}finally{store.close();}
}
