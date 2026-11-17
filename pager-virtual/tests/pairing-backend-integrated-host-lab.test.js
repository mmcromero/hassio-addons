// AVISAQUI-PAIR-001: unico ensaio integrado, sem servicos externos ou Windows real.
// Fastify TLS em loopback; cookies de sessoes REAIS (tabela sessoes) com identidade sintetica.
import test from 'node:test';
import assert from 'node:assert/strict';
import Fastify from 'fastify';
import { spawnSync } from 'node:child_process';
import { createHash, generateKeyPairSync, randomBytes, randomUUID, sign } from 'node:crypto';
import { mkdtempSync, readFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import https from 'node:https';
import net from 'node:net';

async function portAvailable(){
 return new Promise((resolve,reject)=>{
  const s=net.createServer();s.once('error',reject);
  s.listen(0,'127.0.0.1',()=>{const p=s.address().port;s.close(()=>resolve(p))});
 });
}
async function tlsCall({port,ca,path,method='GET',cookie,origin,body,headers={}}){
 const data=body===undefined?null:JSON.stringify(body);
 return new Promise((resolve,reject)=>{
  const q=https.request({hostname:'127.0.0.1',servername:'pager.test',port,path,method,ca,rejectUnauthorized:true,
   headers:{Host:'pager.test:'+port,...(cookie?{Cookie:cookie}:{}),...(origin?{Origin:origin}:{}),
    ...(data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}),...headers},
   timeout:6000},res=>{let raw='';res.setEncoding('utf8');res.on('data',x=>raw+=x);
    res.on('end',()=>{let json;try{json=JSON.parse(raw)}catch{}resolve({status:res.statusCode,raw,json,headers:res.headers})})});
  q.on('error',reject);q.on('timeout',()=>q.destroy(Error('HTTPS timeout')));q.end(data);
 });
}
test('HTTPS integrado: sessao real, QR, tenant, aprovar, resgatar, ACK, idempotencia e reinicio', {timeout:45000}, async()=>{
 const dir=mkdtempSync(join(tmpdir(),'avisaqui-pair-integration-'));
 const envData=process.env.DATA_PATH,envPublic=process.env.PUBLIC_URL;
 let app,db;
 try {
  const cert=join(dir,'cert.pem'),key=join(dir,'key.pem');
  const openssl=spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-nodes','-sha256',
   '-keyout',key,'-out',cert,'-days','1','-subj','/CN=pager.test',
   '-addext','subjectAltName=DNS:pager.test'],{encoding:'utf8',timeout:10000});
  assert.equal(openssl.status,0,'certificado de laboratorio nao criado');
  const ca=readFileSync(cert),port=await portAvailable();
  const origin='https://pager.test:'+port;
  process.env.DATA_PATH=join(dir,'data');
  process.env.PUBLIC_URL=origin;
  ({default:db}=await import('../src/db.js'));
  const { registerPairV1IntegratedLab }=await import('../src/pairing/backend/integrated-host-lab.js');
  const { canonicalProofMessage }=await import('../src/pairing/backend/protocol-v2.js');
  const now=Date.now();
  for(const id of ['rest-a','rest-b']){
   db.prepare('INSERT INTO restaurantes(id,nome,slug,ativo,created_at) VALUES(?,?,?,?,?)')
    .run(id,id,id,1,now);
  }
  const cookieByRest={};
  for(const id of ['rest-a','rest-b']){
   const user='manager-'+id,token=randomBytes(32).toString('hex');
   db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,ativo,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,1,?,?)')
    .run(user,id,user,user,'synthetic-not-authenticatable','gerente',now,now);
   db.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
    .run(randomUUID(),user,createHash('sha256').update(token).digest('hex'),now,now+3600000);
   cookieByRest[id]='bipou_session='+token;
  }
  db.exec('CREATE TABLE integracao_impressao_chaves(id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL, hash TEXT UNIQUE NOT NULL, criado_em INTEGER NOT NULL, revogado_em INTEGER, FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id))');
  const setup=async()=>{
   const instance=Fastify({logger:false,https:{key:readFileSync(key),cert:readFileSync(cert)}});
   await registerPairV1IntegratedLab(instance,{db,publicOrigin:origin+'/avisaqui',
    policy:{approvalMs:300000,challengeMs:60000,recoveryMs:3600000}});
   await instance.listen({host:'127.0.0.1',port});
   return instance;
  };
  app=await setup();
  const call=(path,options={})=>tlsCall({port,ca,path,...options});
  const managerCookie=cookieByRest['rest-a'];
  const managerOrigin={cookie:managerCookie,origin};
  const pagePath='/avisaqui/autorizar?solicitacao='+randomUUID();
  assert.equal((await call(pagePath)).status,401,'cliente API sem sessao continua 401');
  const browser=await call(pagePath,{headers:{Accept:'text/html,application/xhtml+xml'}});
  assert.equal(browser.status,303,'navegador sem sessao deve ir ao login antes de aprovar');
  assert.match(browser.headers.location,/^\/avisaqui\/login\.html\?return_to=/);
  const params=new URL(browser.headers.location,'https://pager.test').searchParams;
  assert.equal(params.get('return_to'),pagePath,'login retoma a mesma solicitacao UUID');
  const invalid=await call('/avisaqui/autorizar?solicitacao=../fora',{headers:{Accept:'text/html'}});
  assert.equal(invalid.status,400,'nao redirecionar solicitacao invalida');
  const page=await call(pagePath,{cookie:managerCookie});
  assert.equal(page.status,200);
  assert.match(page.raw,/id="aprovar"/);
  assert.match(page.headers['content-security-policy'],/connect-src 'self'/);
  assert.equal(page.headers['cache-control'],'no-store');
  assert.equal((await call('/avisaqui/api/agentes/dispositivos')).status,401);
  assert.equal((await call('/avisaqui/api/agentes/dispositivos',{cookie:managerCookie})).status,200);
  const keys={ed:generateKeyPairSync('ed25519'),x:generateKeyPairSync('x25519')};
  const created=await call('/avisaqui/api/agentes/pareamentos',{method:'POST',body:{
   protocol:'pair-v1',client_request_id:randomUUID(),
   signing_public_key:keys.ed.publicKey.export({format:'pem',type:'spki'}),
   delivery_public_key:keys.x.publicKey.export({format:'pem',type:'spki'})
  }});
  assert.equal(created.status,201,created.raw);
  const pairingId=created.json.id;
  assert.equal(created.json.qr_url,origin+'/avisaqui/autorizar?solicitacao='+pairingId);
  const target='/avisaqui/api/agentes/pareamentos/'+pairingId;
  assert.equal((await call(target+'/autorizar',{method:'POST',cookie:managerCookie,body:{
    decisao:'aprovar',codigo:created.json.code,caixa_nome:'Caixa seguro'
  }})).status,403,'sem Origin nao pode aprovar');
  assert.equal((await call(target+'/autorizar',{method:'POST',...managerOrigin,
   headers:{'Sec-Fetch-Site':'cross-site'},body:{decisao:'aprovar',codigo:created.json.code,caixa_nome:'Caixa seguro'}})).status,403);
  const approve=await call(target+'/autorizar',{method:'POST',...managerOrigin,body:{
   decisao:'aprovar',codigo:created.json.code,caixa_nome:'Caixa seguro',restaurante_id:'rest-b'
  }});
  assert.equal(approve.status,200,approve.raw);
  assert.equal(approve.json.state,'APROVADO');
  const stored=db.prepare('SELECT restaurante_id,caixa_nome_aprovado FROM integracao_pareamento_solicitacoes WHERE id=?').get(pairingId);
  assert.equal(stored.restaurante_id,'rest-a','restaurante deriva da sessao, nao do body');
  assert.equal(stored.caixa_nome_aprovado,'Caixa seguro');
  const challenge=async(purpose,operationId)=>{
   const result=await call(target+'/desafios',{method:'POST',body:{protocol:'pair-v1',purpose,operation_id:operationId}});
   assert.equal(result.status,201,result.raw);
   const c=result.json;
   return {protocol:'pair-v1',operation_id:operationId,challenge_id:c.challenge_id,
    signature:sign(null,canonicalProofMessage({purpose,pairingId,operationId,challengeId:c.challenge_id,challenge:c.challenge}),keys.ed.privateKey).toString('base64url')};
  };
  const redeemId=randomUUID(),proof=await challenge('redeem',redeemId);
  const redeem=await call(target+'/resgatar',{method:'POST',body:proof});
  assert.equal(redeem.status,201,redeem.raw);
  assert.equal(redeem.json.protocol,'pair-v1');
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves').get().n,1);
  const again=await challenge('redeem',redeemId);
  const recovered=await call(target+'/resgatar',{method:'POST',body:again});
  assert.equal(recovered.status,200);
  assert.deepEqual(recovered.json,redeem.json);
  const ackOperationId=randomUUID(),ackProof=await challenge('ack',ackOperationId);
  const ack=await call(target+'/confirmar',{method:'POST',body:{...ackProof,operation_id:redeemId,ack_operation_id:ackOperationId}});
  assert.equal(ack.status,200,ack.raw);
  assert.equal(ack.json.state,'CONFIRMADO');
  assert.equal(db.prepare('SELECT last_seen_em FROM integracao_impressao_dispositivos').get().last_seen_em,null,'ACK nao e heartbeat');
  await app.close();app=null;
  // O banco sintetico persiste enquanto a API de laboratorio reinicia.
  app=await setup();
  const ackRetry=await challenge('ack',ackOperationId);
  const confirmed=await call(target+'/confirmar',{method:'POST',body:{...ackRetry,operation_id:redeemId,ack_operation_id:ackOperationId}});
  assert.equal(confirmed.status,200,confirmed.raw);
  assert.deepEqual(confirmed.json,ack.json);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_dispositivos').get().n,1);
  assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves').get().n,1);
  assert.equal((await call('/avisaqui/api/agentes/dispositivos',{cookie:cookieByRest['rest-b']})).json.length,0);
  // Proxy de distribuicao remove /avisaqui antes de encaminhar ao backend.
  // Com opt-in explicito de laboratorio, a montagem na raiz INTERNA deve
  // preservar a URL EXTERNA do QR (/avisaqui/autorizar).
  await app.close(); app=null;
  app=Fastify({logger:false,https:{key:readFileSync(key),cert:readFileSync(cert)}});
  await registerPairV1IntegratedLab(app,{db,publicOrigin:origin+'/avisaqui',
    mountPrefix:'',policy:{approvalMs:300000,challengeMs:60000,recoveryMs:3600000}});
  await app.listen({host:'127.0.0.1',port});
  const stripped=await call('/autorizar?solicitacao='+pairingId,{cookie:managerCookie});
  assert.equal(stripped.status,200,'rota interna sem prefixo serve pagina autorizada');
  assert.equal((await call('/api/agentes/dispositivos',{cookie:managerCookie})).status,200);
  assert.equal((await call('/avisaqui/autorizar?solicitacao='+pairingId,{cookie:managerCookie})).status,404,
    'nao duplicar prefixo interno quando proxy remove /avisaqui');

 }finally{
  if(app)await app.close();
  if(db)db.close();
  if(envData===undefined)delete process.env.DATA_PATH;else process.env.DATA_PATH=envData;
  if(envPublic===undefined)delete process.env.PUBLIC_URL;else process.env.PUBLIC_URL=envPublic;
  rmSync(dir,{recursive:true,force:true});
 }
});
