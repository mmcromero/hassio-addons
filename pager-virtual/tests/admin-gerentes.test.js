import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const temp = mkdtempSync(path.join(tmpdir(), 'avisaqui-gerentes-034-'));
process.env.DATA_PATH = temp;
const { default: db } = await import('../src/db.js');
const { authRoutes, passwordHash } = await import('../src/auth.js');
const { adminRoutes } = await import('../src/admin.js');
const { default: Fastify } = await import('fastify');
const app = Fastify({ logger: false });
await app.register(authRoutes);
await app.register(adminRoutes);
await app.ready();
after(async () => { await app.close(); db.close(); rmSync(temp, { recursive: true, force: true }); });

const masterPassword = 'master-senha-segura-123!';
const previous = 'gerente-senha-antiga-123!';
const next = 'gerente-senha-nova-456!';
const headers = { host: 'localhost', origin: 'http://localhost' };
const send = (method, url, payload, cookie) => app.inject({
  method, url, headers: { ...headers, ...(cookie ? { cookie } : {}) },
  ...(payload === undefined ? {} : { payload })
});
function restaurant(name) {
  const id = randomUUID();
  db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)')
    .run(id,name,name.toLowerCase(),Date.now());
  return id;
}
async function user(login,papel,restaurante_id,senha) {
  const id=randomUUID(), now=Date.now();
  db.prepare(`INSERT INTO usuarios (id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em)
     VALUES(?,?,?,?,?,?,?,?)`).run(id,restaurante_id,login,login,await passwordHash(senha),papel,now,now);
  return id;
}
async function login(login,senha) {
  const res=await send('POST','/api/auth/login',{ login, senha });
  assert.equal(res.statusCode,200,res.body);
  return res.headers['set-cookie'].split(';')[0];
}
const a=restaurant('RestA34'), b=restaurant('RestB34');
const masterId=await user('master-034','master',null,masterPassword);
const managerId=await user('gerente-a-034','gerente',a,previous);
await user('gerente-b-034','gerente',b,previous);
await user('operador-a-034','operador',a,previous);
const base='/api/admin/restaurantes/'+a+'/gerentes';

test('F13: exige sessão Master e contexto da sessão, não confia só na URL', async()=>{
  assert.equal((await send('GET',base)).statusCode,401);
  const manager=await login('gerente-a-034',previous);
  assert.equal((await send('GET',base,undefined,manager)).statusCode,403);
  const master=await login('master-034',masterPassword);
  assert.equal((await send('GET',base,undefined,master)).statusCode,403);
  assert.equal((await send('POST','/api/admin/contexto/'+a,{},master)).statusCode,200);
  const ok=await send('GET',base,undefined,master);
  assert.equal(ok.statusCode,200,ok.body);
  assert.equal(ok.headers['cache-control'],'no-store');
  assert.deepEqual(ok.json().map(x=>x.login),['gerente-a-034']);
  assert.deepEqual(Object.keys(ok.json()[0]).sort(),['ativo','id','login','nome']);
  assert.equal((await send('GET','/api/admin/restaurantes/'+b+'/gerentes',undefined,master)).statusCode,403);
  assert.equal((await send('POST','/api/admin/contexto/sair',{},master)).statusCode,200);
  assert.equal((await send('GET',base,undefined,master)).statusCode,403);
});
test('F15: reautenticação, escopo, revogação e auditoria persistente',async()=>{
  const master=await login('master-034',masterPassword);
  const gerente=await login('gerente-a-034',previous);
  assert.equal((await send('PATCH',base+'/'+managerId+'/senha',{senha:next,senha_master_atual:masterPassword},master)).statusCode,403);
  assert.equal((await send('POST','/api/admin/contexto/'+a,{},master)).statusCode,200);
  const wrong=await send('PATCH',base+'/'+managerId+'/senha',{senha:next,senha_master_atual:'senha-incorreta'},master);
  assert.equal(wrong.statusCode,403,wrong.body);
  const invalid=await send('PATCH',base+'/'+managerId+'/senha',{senha:'curta',senha_master_atual:masterPassword},master);
  assert.equal(invalid.statusCode,400);
  const other=await send('PATCH',base+'/'+randomUUID()+'/senha',{senha:next,senha_master_atual:masterPassword},master);
  assert.equal(other.statusCode,404);
  const ok=await send('PATCH',base+'/'+managerId+'/senha',{senha:next,senha_master_atual:masterPassword},master);
  assert.equal(ok.statusCode,200,ok.body);
  assert.equal(ok.json().sessoes_revogadas,true);
  assert.equal((await send('GET','/api/auth/me',undefined,gerente)).statusCode,401);
  assert.equal((await send('POST','/api/auth/login',{login:'gerente-a-034',senha:previous})).statusCode,401);
  assert.equal((await send('POST','/api/auth/login',{login:'gerente-a-034',senha:next})).statusCode,200);
  const audit=db.prepare('SELECT * FROM auditoria_reset_gerente WHERE gerente_id=?').all(managerId);
  assert.equal(audit.length,1);
  assert.equal(audit[0].ator_id,masterId);
  assert.equal(audit[0].restaurante_id,a);
  assert.equal(audit[0].resultado,'sucesso');
  assert.ok(!JSON.stringify(audit).includes(masterPassword));
  assert.ok(!JSON.stringify(audit).includes(next));
});
test('F15: erro na auditoria reverte hash e revogação na transação',async()=>{
  const master=await login('master-034',masterPassword);
  const session=await login('gerente-a-034',next);
  assert.equal((await send('POST','/api/admin/contexto/'+a,{},master)).statusCode,200);
  const before=db.prepare('SELECT senha_hash FROM usuarios WHERE id=?').get(managerId).senha_hash;
  db.exec(`CREATE TRIGGER bloquear_auditoria_034 BEFORE INSERT ON auditoria_reset_gerente
    BEGIN SELECT RAISE(ABORT,'auditoria indisponivel'); END`);
  try {
    const response=await send('PATCH',base+'/'+managerId+'/senha',{
      senha:'nova-senha-nao-aplicada-789!',senha_master_atual:masterPassword
    },master);
    assert.equal(response.statusCode,500,response.body);
    assert.equal(db.prepare('SELECT senha_hash FROM usuarios WHERE id=?').get(managerId).senha_hash,before);
    assert.equal((await send('GET','/api/auth/me',undefined,session)).statusCode,200);
  } finally { db.exec('DROP TRIGGER bloquear_auditoria_034'); }
});
