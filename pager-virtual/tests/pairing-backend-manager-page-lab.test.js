// Verificacao dirigida da pagina REAL da autorizacao gerencial (laboratorio).
// Nao ativa src/server.js e nao exercita credenciais ou dados comerciais.
import test from 'node:test';
import assert from 'node:assert/strict';
import Fastify from 'fastify';
import { createHash } from 'node:crypto';
import { buildPairV1ManagerPageLab } from '../src/pairing/backend/manager-page-lab.js';

test('rota de autorizacao opt-in entrega HTML real, sem cache e sem embutir segredo', async () => {
  const app=Fastify({logger:false});
  try {
    await app.register(buildPairV1ManagerPageLab({managerFromRequest:()=>({id:'u-ensaio',papel:'gerente',restaurante_id:'r-ensaio'})}),{prefix:'/avisaqui'});
    const r=await app.inject({method:'GET',url:'/avisaqui/autorizar?solicitacao=00000000-0000-4000-8000-000000000001'});
    assert.equal(r.statusCode,200);
    assert.match(r.headers['content-type'],/^text\/html/);
    assert.equal(r.headers['cache-control'],'no-store');
    assert.equal(r.headers['referrer-policy'],'no-referrer');
    assert.equal(r.headers['x-frame-options'],'DENY');
    assert.match(r.headers['content-security-policy'],/connect-src 'self'/);
    const script = r.body.match(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/i);
    assert.ok(script, 'script de autorizacao deve estar no HTML entregue');
    const digest = createHash('sha256').update(script[1], 'utf8').digest('base64');
    assert.ok(r.headers['content-security-policy'].includes("script-src 'sha256-" + digest + "'"),
      'CSP deve autorizar apenas o script exato entregue');
    assert.doesNotMatch(r.headers['content-security-policy'],/script-src 'unsafe-inline'/,
      'nao permitir JavaScript inline arbitrario');
    assert.match(r.headers['content-security-policy'],/script-src-attr 'none'/);
    assert.match(r.body,/id="form"/);
    assert.match(r.body,/id="aprovar"/);
    assert.match(r.body,/id="recusar"/);
    assert.match(r.body,/credentials:'same-origin'/);
    assert.match(r.body,/Aprovação não é conexão online/);
    assert.doesNotMatch(r.body,/X-Avisaqui-Agent-Key|BEGIN PRIVATE KEY|Bearer [a-z0-9]/i);
    const unrelated=await app.inject({method:'GET',url:'/avisaqui/api/agentes/pareamentos'});
    assert.equal(unrelated.statusCode,404,'pagina isolada nao registra API comercial');
  } finally {await app.close();}
});

test('pagina falha fechada caso o HTML de laboratorio esteja indisponivel',async()=>{
  const app=Fastify({logger:false});
  try{
    await app.register(buildPairV1ManagerPageLab({readHtml:async()=>'',managerFromRequest:()=>({id:'u-ensaio',papel:'gerente',restaurante_id:'r-ensaio'})}));
    const r=await app.inject('/autorizar');
    assert.equal(r.statusCode,503);
  }finally{await app.close();}
});

test('pagina de laboratorio rejeita HTML sem script de aprovacao unico', async()=> {
  const app=Fastify({logger:false});
  try {
    await app.register(buildPairV1ManagerPageLab({
      readHtml:async()=>'<html><form id="form"></form></html>',
      managerFromRequest:()=>({id:'u',papel:'gerente',restaurante_id:'r'})
    }));
    const r=await app.inject('/autorizar');
    assert.equal(r.statusCode,503,'falha fechada ao faltar script autorizado pela CSP');
  }finally{await app.close();}
});

test('pagina nao pode ser registrada sem autenticador e falha fechado para operador',async()=>{
 assert.throws(()=>buildPairV1ManagerPageLab(),/Autenticador de gerente obrigat/);
 const app=Fastify({logger:false});
 try{
  await app.register(buildPairV1ManagerPageLab({
   managerFromRequest:()=>({id:'u',papel:'operador',restaurante_id:'r'})
  }),{prefix:'/avisaqui'});
  const result=await app.inject('/avisaqui/autorizar?solicitacao=00000000-0000-4000-8000-000000000001');
  assert.equal(result.statusCode,403);
 }finally{await app.close()}
});
