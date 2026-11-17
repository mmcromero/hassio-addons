import test from 'node:test';
import assert from 'node:assert/strict';
import Fastify from 'fastify';
import Database from 'better-sqlite3';
import { randomBytes, randomUUID, generateKeyPairSync, sign, createHash } from 'node:crypto';
import { buildPairV1LabRoutes } from '../src/pairing/backend/routes-lab.js';
import { canonicalProofMessage } from '../src/pairing/backend/protocol-v2.js';

const ORIGIN='https://pager.example';
const policy={approvalMs:300000,challengeMs:60000,recoveryMs:3600000};
function fixture() {
  const db=new Database(':memory:');
  db.pragma('foreign_keys=ON');
  db.exec(`CREATE TABLE restaurantes(id TEXT PRIMARY KEY);
    CREATE TABLE usuarios(id TEXT PRIMARY KEY);
    CREATE TABLE integracao_impressao_chaves(
      id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,
      criado_em INTEGER NOT NULL,revogado_em INTEGER,
      FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id)
    );
    INSERT INTO restaurantes(id) VALUES('rest-a'),('rest-b');
    INSERT INTO usuarios(id) VALUES('manager-a'),('manager-b');`);
  let clock=1800000000000;
  const app=Fastify({logger:false});
  app.register(buildPairV1LabRoutes({
    db,publicOrigin:ORIGIN,policy,now:()=>clock,
    managerFromRequest:req=>req.headers['x-test-user']==='a'
      ? {id:'manager-a',papel:'gerente',restaurante_id:'rest-a'}
      : req.headers['x-test-user']==='b'
      ? {id:'manager-b',papel:'gerente',restaurante_id:'rest-b'} : null
  }));
  const inject=(method,url,payload,headers={})=>app.inject({
    method,url,headers: { ...(payload?{'content-type':'application/json'}:{}),...headers },
    ...(payload?{payload:JSON.stringify(payload)}:{})
  });
  const mgr=(user='a')=>({'origin':ORIGIN,'x-test-user':user});
  const keys=()=>{
    const ed=generateKeyPairSync('ed25519'), x=generateKeyPairSync('x25519');
    return {ed,x,signing_public_key:ed.publicKey.export({format:'pem',type:'spki'}),
      delivery_public_key:x.publicKey.export({format:'pem',type:'spki'})};
  };
  const create=async (key=keys(),id=randomUUID())=>{
    const res=await inject('POST','/api/agentes/pareamentos',{
      protocol:'pair-v1',client_request_id:id,
      signing_public_key:key.signing_public_key,delivery_public_key:key.delivery_public_key
    });
    return {res,body:res.json(),key,clientId:id};
  };
  const challenge=async(pair,purpose,operationId=randomUUID())=>{
    const res=await inject('POST','/api/agentes/pareamentos/'+pair.id+'/desafios',{
      protocol:'pair-v1',purpose,operation_id:operationId
    });
    assert.equal(res.statusCode,201,JSON.stringify(res.json()));
    const c=res.json();
    const proof=sign(null,canonicalProofMessage({
      purpose,pairingId:pair.id,operationId,challengeId:c.challenge_id,challenge:c.challenge
    }),pair.key.ed.privateKey).toString('base64url');
    return {operationId,challenge:c,signature:proof};
  };
  const approve=async(pair,user='a')=>inject('POST','/api/agentes/pareamentos/'+pair.id+'/autorizar',{
    decisao:'aprovar',codigo:pair.code,caixa_nome:'Caixa de teste'
  },mgr(user));
  const redeem=async(pair,proof)=>inject('POST','/api/agentes/pareamentos/'+pair.id+'/resgatar',{
    protocol:'pair-v1',operation_id:proof.operationId,
    challenge_id:proof.challenge.challenge_id,signature:proof.signature
  });
  const ack=async(pair,redeemId,proof)=>inject('POST','/api/agentes/pareamentos/'+pair.id+'/confirmar',{
    protocol:'pair-v1',operation_id:redeemId,ack_operation_id:proof.operationId,
    challenge_id:proof.challenge.challenge_id,signature:proof.signature
  });
  return {db,app,inject,mgr,keys,create,challenge,approve,redeem,ack,advance:ms=>{clock+=ms},close:async()=>{await app.close();db.close()}};
}

test('criação idempotente e recusas de chave alterada/versão antiga',async()=>{
  const f=fixture();try{
    const created=await f.create();assert.equal(created.res.statusCode,201);
    assert.equal(created.body.protocol,'pair-v1');assert.match(created.body.code,/^[0-9]{8}$/);
    assert.match(created.body.qr_url,/^https:\/\/pager\.example\/autorizar\?solicitacao=/);
    const key=created.key;
    const retry=await f.create(key,created.clientId);
    assert.equal(retry.res.statusCode,200);assert.deepEqual(retry.body,created.body);
    const changed=await f.create(f.keys(),created.clientId);
    assert.equal(changed.res.statusCode,409);
    const old=await f.inject('POST','/api/agentes/pareamentos',{protocol:'pair-v0',client_request_id:randomUUID()});
    assert.equal(old.statusCode,400);
  }finally{await f.close()}
});

test('aprovador autenticado e isolado de restaurante; prova/ACK e retry mantêm identidade',async()=>{
  const f=fixture();try{
    const pair=await f.create();pair.id=pair.body.id;pair.code=pair.body.code;
    let response=await f.approve(pair,'b');assert.equal(response.statusCode,200);
    assert.equal(f.db.prepare('SELECT restaurante_id FROM integracao_pareamento_solicitacoes WHERE id=?').get(pair.id).restaurante_id,'rest-b');
    // O fluxo usa o restaurante escolhido pela sessão do gerente, nunca pelo agente.
    const prior=await f.db.prepare('SELECT * FROM integracao_impressao_chaves').all();
    assert.equal(prior.length,0);
    const rid=randomUUID(), proof=await f.challenge(pair,'redeem',rid);
    response=await f.redeem(pair,proof);assert.equal(response.statusCode,201,JSON.stringify(response.json()));
    const envelope=response.json();assert.equal(envelope.protocol,'pair-v1');
    const snapshot=JSON.stringify(envelope);
    assert.equal(snapshot.includes('Caixa de teste'),false);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_dispositivos').get().n,1);
    const repeat=await f.challenge(pair,'redeem',rid);
    const same=await f.redeem(pair,repeat);
    assert.equal(same.statusCode,200);assert.equal(JSON.stringify(same.json()),snapshot);
    const replay=await f.redeem(pair,repeat);assert.notEqual(replay.statusCode,200);
    const conflict=await f.inject('POST','/api/agentes/pareamentos/'+pair.id+'/desafios',{
      protocol:'pair-v1',purpose:'redeem',operation_id:randomUUID()});
    assert.equal(conflict.statusCode,410);
    const ackId=randomUUID(),ackProof=await f.challenge(pair,'ack',ackId);
    const result=await f.ack(pair,rid,ackProof);
    assert.equal(result.statusCode,200);assert.equal(result.json().state,'CONFIRMADO');
    const retryProof=await f.challenge(pair,'ack',ackId);
    const retryAck=await f.ack(pair,rid,retryProof);
    assert.equal(retryAck.statusCode,200);
    assert.deepEqual(retryAck.json(),result.json());
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves').get().n,1);
  }finally{await f.close()}
});

test('estado e desafio exigem prova exata; expiração de aprovação',async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={...created,key:created.key,id:created.body.id};
    const c=await f.challenge(pair,'status');
    const path='/api/agentes/pareamentos/'+pair.id+'/estado';
    const headers={'x-avisaqui-pair-version':'pair-v1',
      'x-avisaqui-pair-operation-id':c.operationId,
      'x-avisaqui-pair-challenge-id':c.challenge.challenge_id,
      'x-avisaqui-pair-proof':c.signature};
    const status=await f.inject('GET',path,null,headers);
    assert.equal(status.statusCode,200);assert.equal(status.json().state,'PENDENTE');
    const reused=await f.inject('GET',path,null,headers);
    assert.equal(reused.statusCode,403);
    f.advance(policy.approvalMs+1);
    const d=await f.challenge(pair,'status');
    const expired=await f.inject('GET',path,null,{
      'x-avisaqui-pair-version':'pair-v1',
      'x-avisaqui-pair-operation-id':d.operationId,
      'x-avisaqui-pair-challenge-id':d.challenge.challenge_id,
      'x-avisaqui-pair-proof':d.signature});
    assert.equal(expired.statusCode,200);assert.equal(expired.json().state,'EXPIRADO');
  }finally{await f.close()}
});


test('aprovação errada não conclui vínculo, registra tentativas e respeita limite no banco',async()=>{
  const f=fixture();try{
    const {body,key}=await f.create(),pair={id:body.id,code:body.code,key};
    const path='/api/agentes/pareamentos/'+pair.id+'/autorizar';
    const payload={decisao:'aprovar',codigo:body.code,caixa_nome:'Caixa de teste'};
    const denied=await f.inject('POST',path,payload);
    assert.equal(denied.statusCode,403);
    const bad='00000000'===body.code?'99999999':'00000000';
    for(let i=0;i<8;i++){
      const r=await f.inject('POST',path,{...payload,codigo:bad},f.mgr());
      assert.equal(r.statusCode,403);
    }
    assert.equal(f.db.prepare('SELECT tentativas_codigo AS n FROM integracao_pareamento_solicitacoes WHERE id=?').get(pair.id).n,8);
    const blocked=await f.inject('POST',path,payload,f.mgr());
    assert.equal(blocked.statusCode,429);
    assert.equal(f.db.prepare('SELECT estado FROM integracao_pareamento_solicitacoes WHERE id=?').get(pair.id).estado,'PENDENTE');
  }finally{await f.close()}
});

test('resgate inicial depois do prazo não emite credencial nem dispositivo',async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={id:created.body.id,code:created.body.code,key:created.key};
    const authorized=await f.approve(pair);
    assert.equal(authorized.statusCode,200);
    f.advance(policy.approvalMs-10000);
    const redeemId=randomUUID(),proof=await f.challenge(pair,'redeem',redeemId);
    f.advance(10001);
    const rejected=await f.redeem(pair,proof);
    assert.equal(rejected.statusCode,410);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves').get().n,0);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_dispositivos').get().n,0);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_pareamento_resgates').get().n,0);
  }finally{await f.close()}
});

test('credencial legada anterior permanece intacta após migração explícita',async()=>{
  const f=fixture();try{
    f.db.prepare('INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em) VALUES(?,?,?,?)')
      .run('legacy','rest-a',createHash('sha256').update('fixture').digest('hex'),100);
    const created=await f.create();assert.equal(created.res.statusCode,201);
    const saved=f.db.prepare('SELECT * FROM integracao_impressao_chaves WHERE id=?').get('legacy');
    assert.equal(saved.revogado_em,null);assert.equal(saved.dispositivo_id,null);
  }finally{await f.close()}
});

test('administração de dispositivo separa restaurantes, audita renomeação e revoga somente credencial do próprio caixa', async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={id:created.body.id,code:created.body.code,key:created.key};
    assert.equal((await f.approve(pair)).statusCode,200);
    const proof=await f.challenge(pair,'redeem');
    assert.equal((await f.redeem(pair,proof)).statusCode,201);
    const device=f.db.prepare('SELECT id,restaurante_id,caixa_nome FROM integracao_impressao_dispositivos').get();
    assert.equal(device.restaurante_id,'rest-a');
    const list='/api/agentes/dispositivos',id='/api/agentes/dispositivos/'+device.id;
    const a=await f.inject('GET',list,null,f.mgr('a'));
    const b=await f.inject('GET',list,null,f.mgr('b'));
    assert.equal(a.statusCode,200);assert.equal(a.json().length,1);
    assert.equal(b.statusCode,200);assert.equal(b.json().length,0);
    const otherRename=await f.inject('PATCH',id,{caixa_nome:'Caixa indevida'},f.mgr('b'));
    assert.equal(otherRename.statusCode,404);
    const otherRevoke=await f.inject('DELETE',id,{confirmar:true},f.mgr('b'));
    assert.equal(otherRevoke.statusCode,404);
    const missingConfirm=await f.inject('DELETE',id,{},f.mgr('a'));
    assert.equal(missingConfirm.statusCode,400);
    const renamed=await f.inject('PATCH',id,{caixa_nome:'Caixa Norte'},f.mgr('a'));
    assert.equal(renamed.statusCode,200);assert.equal(renamed.json().caixa_nome,'Caixa Norte');
    const revoked=await f.inject('DELETE',id,{confirmar:true},f.mgr('a'));
    assert.equal(revoked.statusCode,200);
    assert.equal(f.db.prepare('SELECT revogado_em FROM integracao_impressao_chaves WHERE dispositivo_id=?').get(device.id).revogado_em!==null,true);
    const retry=await f.inject('DELETE',id,{confirmar:true},f.mgr('a'));
    assert.equal(retry.statusCode,200);assert.equal(retry.json().repetido,true);
    const audit=f.db.prepare('SELECT acao,resultado FROM integracao_pareamento_auditoria WHERE dispositivo_id=? ORDER BY criado_em').all(device.id);
    assert.equal(audit.some(row=>row.acao==='renomear'),true);
    assert.equal(audit.some(row=>row.acao==='revogar'),true);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_dispositivos').get().n,1);
  }finally{await f.close()}
});

test('Origin, Fetch Metadata e papel são validados no gerenciamento', async()=>{
  const f=fixture();try{
    const path='/api/agentes/dispositivos';
    assert.equal((await f.inject('GET',path)).statusCode,403);
    // GET seguro pode omitir Origin como em navegadores comuns; sessão segue obrigatória.
    assert.equal((await f.inject('GET',path,null,{'x-test-user':'a'})).statusCode,200);
    assert.equal((await f.inject('GET',path,null,{...f.mgr(), 'sec-fetch-site':'cross-site'})).statusCode,403);
    assert.equal((await f.inject('GET',path,null,{...f.mgr(), 'sec-fetch-mode':'no-cors'})).statusCode,403);
    assert.equal((await f.inject('GET',path,null,{...f.mgr(), 'x-forwarded-host':'evil.example'})).statusCode,200);
  }finally{await f.close()}
});

test('resposta perdida após COMMIT: resgate/ACK repetidos não criam outra identidade', async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={id:created.body.id,code:created.body.code,key:created.key};
    assert.equal((await f.approve(pair)).statusCode,200);
    const redeemId=randomUUID(),challenge=await f.challenge(pair,'redeem',redeemId);
    // A primeira resposta é deliberadamente ignorada, como perda no transporte.
    assert.equal((await f.redeem(pair,challenge)).statusCode,201);
    const again=await f.challenge(pair,'redeem',redeemId);
    const recovered=await f.redeem(pair,again);
    assert.equal(recovered.statusCode,200);
    const stored=f.db.prepare('SELECT envelope_json FROM integracao_pareamento_resgates').get().envelope_json;
    assert.equal(JSON.stringify(recovered.json()),stored);
    const ackId=randomUUID(),a=await f.challenge(pair,'ack',ackId);
    assert.equal((await f.ack(pair,redeemId,a)).statusCode,200);
    const b=await f.challenge(pair,'ack',ackId);
    assert.equal((await f.ack(pair,redeemId,b)).statusCode,200);
    for(const table of ['integracao_impressao_dispositivos','integracao_impressao_chaves','integracao_pareamento_resgates']){
      assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM '+table).get().n,1);
    }
  }finally{await f.close()}
});

test('rollback de resgate: falha SQL não deixa chave, dispositivo ou resgate parcial', async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={id:created.body.id,code:created.body.code,key:created.key};
    assert.equal((await f.approve(pair)).statusCode,200);
    const challenge=await f.challenge(pair,'redeem');
    f.db.exec(`CREATE TRIGGER block_redemption BEFORE INSERT ON integracao_pareamento_resgates
      BEGIN SELECT RAISE(ABORT,'falha sintetica'); END`);
    const failed=await f.redeem(pair,challenge);
    assert.equal(failed.statusCode,503);
    assert.equal(f.db.prepare('SELECT estado FROM integracao_pareamento_solicitacoes WHERE id=?').get(pair.id).estado,'APROVADO');
    for(const table of ['integracao_impressao_dispositivos','integracao_impressao_chaves','integracao_pareamento_resgates']){
      assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM '+table).get().n,0);
    }
    const challengeDb=f.db.prepare('SELECT consumido_em FROM integracao_pareamento_desafios WHERE id=?').get(challenge.challenge.challenge_id);
    assert.equal(challengeDb.consumido_em,null);
    f.db.exec('DROP TRIGGER block_redemption');
    assert.equal((await f.redeem(pair,challenge)).statusCode,201);
  }finally{await f.close()}
});

test('challenge vencido falha fechado sem registrar resgate', async()=>{
  const f=fixture();try{
    const created=await f.create(),pair={id:created.body.id,code:created.body.code,key:created.key};
    assert.equal((await f.approve(pair)).statusCode,200);
    const challenge=await f.challenge(pair,'redeem');
    f.advance(policy.challengeMs+1);
    const result=await f.redeem(pair,challenge);
    assert.equal(result.statusCode,403);
    assert.equal(f.db.prepare('SELECT COUNT(*) AS n FROM integracao_pareamento_resgates').get().n,0);
  }finally{await f.close()}
});


test('Windows/UX: listagem não inventa heartbeat ou fila e exige ACK para confirmar vínculo',async()=>{
  const f=fixture();
  try{
    const created=await f.create();
    const pair={id:created.body.id,code:created.body.code,key:created.key};
    const list=()=>f.inject('GET','/api/agentes/dispositivos',null,f.mgr('a'));
    let response=await list();
    assert.equal(response.statusCode,200);
    assert.deepEqual(response.json(),[],'criação ainda não equivale a computador vinculado');
    assert.equal((await f.approve(pair)).statusCode,200);
    response=await list();
    assert.deepEqual(response.json(),[],'aprovação não equivale a computador instalado');
    const proof=await f.challenge(pair,'redeem');
    const redeemed=await f.redeem(pair,proof);
    assert.equal(redeemed.statusCode,201);
    response=await list();
    assert.equal(response.statusCode,200);
    const rows=response.json();
    assert.equal(rows.length,1);
    assert.equal(rows[0].last_seen_em,null,
      'resgate sem evento autenticado não representa comunicação observada');
    assert.equal(Object.hasOwn(rows[0],'eventos_pendentes'),false,
      'não expor zero ou estado de fila que ainda não tenha fonte confiável');
    assert.equal(Object.hasOwn(rows[0],'online'),false,
      'não inferir online a partir de resgate');
    const ackId=randomUUID(),ackProof=await f.challenge(pair,'ack',ackId);
    const confirmed=await f.ack(pair,proof.operationId,ackProof);
    assert.equal(confirmed.statusCode,200);
    assert.equal(confirmed.json().state,'CONFIRMADO');
    const after=await list();
    assert.equal(after.statusCode,200);
    assert.equal(after.json()[0].last_seen_em,null,
      'ACK confirma vínculo, não prova heartbeat recente');
    assert.equal(Object.hasOwn(after.json()[0],'eventos_pendentes'),false);
    const other=await f.inject('GET','/api/agentes/dispositivos',null,f.mgr('b'));
    assert.deepEqual(other.json(),[],'outro restaurante não pode ver o caixa');
  }finally{await f.close()}
});
