/** Verificação interna de prontidão: preserva validação de Host, sem expor segredos. */
import {get} from 'node:http';
import {pilotConfig} from './config.js';
try{
 const config=pilotConfig();
 const request=get({hostname:'127.0.0.1',port:Number(process.env.PORT??8099),path:config.prefix+'login',headers:{Host:config.publicUrl.host},timeout:4000},response=>{response.resume();process.exitCode=response.statusCode===200?0:1;});
 request.on('timeout',()=>request.destroy());request.on('error',()=>{process.exitCode=1;});
}catch{process.exitCode=1;}
