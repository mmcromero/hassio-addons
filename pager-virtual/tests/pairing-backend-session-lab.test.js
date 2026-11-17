import test from 'node:test';
import assert from 'node:assert/strict';
import Fastify from 'fastify';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

test('adaptador de sessão real: gerente/master, operador, sessão inválida, CSRF e tenant', async()=>{
  // O módulo de autenticação real importa seu banco na inicialização.
  // Este arquivo roda em worker Node independente; DATA_PATH aponta somente a pasta efêmera.
  const dataPath=mkdtempSync(join(tmpdir(),'avisaqui-pair-auth-lab-'));
  const previousData=process.env.DATA_PATH, previousPublic=process.env.PUBLIC_URL;
  process.env.DATA_PATH=dataPath;
  process.env.PUBLIC_URL='https://pager.example';
  let app, db;
  try{
    ({default:db}=await import('../src/db.js'));
    const {managerFromAvisaquiSession}=await import('../src/pairing/backend/session-adapter.js');
    const {requireRestaurant}=await import('../src/auth.js');
    const {buildPairV1LabRoutes}=await import('../src/pairing/backend/routes-lab.js');
    const time=Date.now();
    db.prepare('INSERT INTO restaurantes(id,nome,slug,ativo,created_at) VALUES(?,?,?,?,?)')
      .run('rest-a','Restaurante A','rest-a',1,time);
    db.prepare('INSERT INTO restaurantes(id,nome,slug,ativo,created_at) VALUES(?,?,?,?,?)')
      .run('rest-b','Restaurante B','rest-b',1,time);
    const users=[
      ['gerente-a','rest-a','gerente'],
      ['gerente-b','rest-b','gerente'],
      ['operador-a','rest-a','operador'],
      ['master-1',null,'master']
    ];
    const cookies={};
    for(const [id,restaurant,role] of users){
      db.prepare(`INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,ativo,criado_em,atualizado_em)
        VALUES(?,?,?,?,?,?,1,?,?)`).run(id,restaurant,id,id,'synthetic-not-authenticatable',role,time,time);
      const token=randomBytes(32).toString('hex'),sessionId=randomUUID();
      db.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
        .run(sessionId,id,createHash('sha256').update(token).digest('hex'),time,time+3600000);
      cookies[id]='bipou_session='+token;
      if(role==='master') db.prepare('INSERT INTO master_contextos(sessao_id,restaurante_id,selecionado_em) VALUES(?,?,?)')
        .run(sessionId,'rest-a',time);
    }
    db.exec(`CREATE TABLE integracao_impressao_chaves (
      id TEXT PRIMARY KEY, restaurante_id TEXT NOT NULL,hash TEXT UNIQUE NOT NULL,
      criado_em INTEGER NOT NULL,revogado_em INTEGER,
      FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id));`);
    app=Fastify({logger:false});
    // Rota de diagnóstico SOMENTE neste servidor efêmero, para observar diretamente
    // o formato e a resposta do requireRestaurant sem presumir contrato pelo import.
    app.get('/lab/diagnostico-sessao',async(req,reply)=>{
      const user=requireRestaurant(req,reply);
      if(!user)return;
      return {id:user.id,papel:user.papel,restaurante_id:user.restaurante_id};
    });
    app.register(buildPairV1LabRoutes({
      db,publicOrigin:'https://pager.example',
      policy:{approvalMs:300000,challengeMs:60000,recoveryMs:3600000},
      managerFromRequest:managerFromAvisaquiSession
    }));
    const call=async(token,origin='https://pager.example',headers={})=>app.inject({
      method:'GET',url:'/api/agentes/dispositivos',
      headers:{host:'pager.example',origin,cookie:token,...headers}
    });
    const probe=async(token,origin,extra={})=>app.inject({
      method:'GET',url:'/lab/diagnostico-sessao',
      headers:{host:'pager.example',cookie:token,...(origin?{origin}:{}),...extra}
    });
    const direct=await probe(cookies['gerente-a']);
    assert.equal(direct.statusCode,200);
    assert.deepEqual(direct.json(),{id:'gerente-a',papel:'gerente',restaurante_id:'rest-a'});
    const master=await probe(cookies['master-1']);
    assert.equal(master.statusCode,200);
    assert.deepEqual(master.json(),{id:'master-1',papel:'master',restaurante_id:'rest-a'});
    const operator=await probe(cookies['operador-a']);
    assert.equal(operator.statusCode,200);
    assert.deepEqual(operator.json(),{id:'operador-a',papel:'operador',restaurante_id:'rest-a'});
    const invalid=await probe('bipou_session='+randomBytes(32).toString('hex'));
    assert.equal(invalid.statusCode,401);
    assert.deepEqual(invalid.json(),{error:'Sessão inválida ou expirada'});
    // GET sem Origin é legítimo, mas a rota comercial ainda verifica a sessão.
    const getWithoutOrigin=await app.inject({
      method:'GET',url:'/api/agentes/dispositivos',
      headers:{host:'pager.example',cookie:cookies['gerente-a']}
    });
    assert.equal(getWithoutOrigin.statusCode,200);
    // Escrita sem Origin não pode avançar nem com sessão válida.
    const unsafe=await app.inject({
      method:'PATCH',url:'/api/agentes/dispositivos/'+randomUUID(),
      headers:{host:'pager.example',cookie:cookies['gerente-a']},
      payload:{caixa_nome:'Nome não autorizado'}
    });
    assert.equal(unsafe.statusCode,403);
    assert.equal((await call(cookies['gerente-a'])).statusCode,200);
    assert.equal((await call(cookies['gerente-b'])).statusCode,200);
    assert.equal((await call(cookies['master-1'])).statusCode,200);
    assert.equal((await call(cookies['operador-a'])).statusCode,403);
    assert.equal((await call('bipou_session='+randomBytes(32).toString('hex'))).statusCode,401);
    assert.equal((await call(cookies['gerente-a'],'https://evil.example')).statusCode,403);
    assert.equal((await call(cookies['gerente-a'],undefined,{'sec-fetch-site':'cross-site'})).statusCode,403);
    // Cookie válido do restaurante B jamais lista dispositivo do restaurante A.
    db.prepare(`INSERT INTO integracao_impressao_dispositivos
      (id,restaurante_id,caixa_nome,criado_em) VALUES(?,?,?,?)`)
      .run(randomUUID(),'rest-a','Caixa A',time);
    const listA=(await call(cookies['gerente-a'])).json();
    const listB=(await call(cookies['gerente-b'])).json();
    assert.equal(listA.length,1);
    assert.equal(listB.length,0);
    assert.equal(JSON.stringify(listA).includes('credential'),false);
  }finally{
    if(app) await app.close();
    if(db) db.close();
    if(previousData===undefined) delete process.env.DATA_PATH; else process.env.DATA_PATH=previousData;
    if(previousPublic===undefined) delete process.env.PUBLIC_URL; else process.env.PUBLIC_URL=previousPublic;
    rmSync(dataPath,{recursive:true,force:true});
  }
});
