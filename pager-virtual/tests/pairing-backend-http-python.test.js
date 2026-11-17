import test from 'node:test';
import assert from 'node:assert/strict';
import { spawn } from 'node:child_process';
import { mkdtempSync, rmSync } from 'node:fs';
import { join, resolve, dirname } from 'node:path';
import { tmpdir } from 'node:os';
import { fileURLToPath } from 'node:url';
import Database from 'better-sqlite3';
import Fastify from 'fastify';
import { buildPairV1LabRoutes } from '../src/pairing/backend/routes-lab.js';

const ROOT=resolve(dirname(fileURLToPath(import.meta.url)),'..');
// Transporte HTTP de loopback substitui HTTPS só no ensaio isolado.
// Chamadas usam o cliente real PairV1Client, com chaves e provas reais Python.
const PY=String.raw`
import json, sys, uuid, os
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlparse
sys.path.insert(0,str(Path.cwd()/'scripts'/'impressao_windows'))
from cliente_pair_v1 import PairV1Client
from pair_v1 import new_keys
port=os.environ['PAIR_PORT']
def transport(url,method,data,headers=None):
    parsed=urlparse(url)
    if parsed.scheme!='https' or parsed.hostname!='pager.example':
        raise ValueError('Origem inesperada')
    target='http://127.0.0.1:'+port+parsed.path
    if parsed.query: target+='?'+parsed.query
    body=json.dumps(data).encode() if data is not None else None
    req=Request(target,data=body,method=method,
       headers={'Content-Type':'application/json',**(headers or {})})
    with urlopen(req,timeout=8) as response:
        return json.load(response)
client=PairV1Client('https://pager.example',transport=transport)
signer,receiver=new_keys()
pair=client.create(str(uuid.uuid4()),signer,receiver)
# Emulação explícita do clique do gerente só neste laboratório de transporte;
# autorização real/CSRF por sessão é testada separadamente.
approved=transport('https://pager.example/api/agentes/pareamentos/'+pair['id']+'/autorizar',
  'POST',{'decisao':'aprovar','codigo':pair['code'],'caixa_nome':'Caixa HTTP'}, {'Origin':'https://pager.example'})
if approved['state']!='APROVADO': raise AssertionError('Aprovação não persistida')
status=client.status(signer,pair['id'],str(uuid.uuid4()))
if status['state']!='APROVADO': raise AssertionError('Status inválido')
redeem_id=str(uuid.uuid4())
payload=client.redeem(signer,receiver,pair['id'],redeem_id)
if payload['caixa_nome']!='Caixa HTTP' or payload['restaurante_id']!='rest-1':
    raise AssertionError('Tenant/nome divergente')
result=client.ack(signer,pair['id'],redeem_id,str(uuid.uuid4()))
if result['dispositivo_id']!=payload['dispositivo_id']:
    raise AssertionError('ACK com dispositivo divergente')
print(json.dumps({'pairing_state':status['state'],'ack_state':result['state'],
  'device_matches':True},separators=(',',':')))
`;

function runPython(port) {
  return new Promise((resolve,reject)=>{
    const child=spawn('python3',['-c',PY],{
      cwd:ROOT,env:{...process.env,PAIR_PORT:String(port)},stdio:['ignore','pipe','pipe']
    });
    let out='',err='';
    const timer=setTimeout(()=>{child.kill();reject(Error('Timeout de teste Python HTTP'))},20000);
    child.stdout.on('data',d=>out+=d.toString());
    child.stderr.on('data',d=>err+=d.toString());
    child.on('error',e=>{clearTimeout(timer);reject(e)});
    child.on('close',code=>{
      clearTimeout(timer);
      if(code!==0)return reject(Error('Falha HTTP Python: '+err.slice(0,1000)));
      try{resolve(JSON.parse(out.trim()))}catch(e){reject(Error('Resposta do teste inválida: '+out.slice(0,200)))}
    });
  });
}
test('cliente Python Windows percorre HTTP real de loopback: criar, aprovar, status, resgatar e ACK',async()=>{
  const dir=mkdtempSync(join(tmpdir(),'avisaqui-pair-http-'));
  const db=new Database(join(dir,'pairing.db'));
  let app;
  try{
    db.pragma('foreign_keys=ON');
    db.exec(`CREATE TABLE restaurantes(id TEXT PRIMARY KEY);
      CREATE TABLE usuarios(id TEXT PRIMARY KEY);
      CREATE TABLE integracao_impressao_chaves (
        id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,
        criado_em INTEGER NOT NULL,revogado_em INTEGER,
        FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id));
      INSERT INTO restaurantes(id) VALUES('rest-1');
      INSERT INTO usuarios(id) VALUES('mgr-1');`);
    app=Fastify({logger:false});
    app.register(buildPairV1LabRoutes({
      db,publicOrigin:'https://pager.example',
      policy:{approvalMs:300000,challengeMs:60000,recoveryMs:3600000},
      managerFromRequest:()=>({id:'mgr-1',papel:'gerente',restaurante_id:'rest-1'})
    }));
    await app.listen({host:'127.0.0.1',port:0});
    const port=app.server.address().port;
    const result=await runPython(port);
    assert.deepEqual(result,{pairing_state:'APROVADO',ack_state:'CONFIRMADO',device_matches:true});
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves').get().n,1);
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_dispositivos').get().n,1);
    assert.equal(db.prepare('SELECT estado FROM integracao_pareamento_solicitacoes').get().estado,'CONFIRMADO');
  }finally{
    if(app)await app.close();
    db.close();
    rmSync(dir,{recursive:true,force:true});
  }
});
