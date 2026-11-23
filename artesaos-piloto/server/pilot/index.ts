import {pilotConfig} from './config.js';
import {createPilotApp} from './app.js';
process.umask(0o077);
try{
 const config=pilotConfig();const app=await createPilotApp(config);
 for(const sig of ['SIGTERM','SIGINT'] as const)process.once(sig,()=>{void app.close();});
 const port=Number(process.env.PORT??8099);if(!Number.isInteger(port)||port<1||port>65535)throw Error('Porta inválida.');
 await app.listen({host:process.env.HOST??'127.0.0.1',port});
}catch{process.stderr.write('Piloto não iniciado. Confira public_url HTTPS, opções Google, diretório de dados e porta.\n');process.exitCode=1;}
