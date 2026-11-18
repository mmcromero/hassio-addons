import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const dir=mkdtempSync(path.join(tmpdir(),'avisaqui-f13-f15-security-'));
process.env.DATA_PATH=dir;
const { default:db }=await import('../src/db.js');
const { authRoutes,passwordHash }=await import('../src/auth.js');
const { adminRoutes }=await import('../src/admin.js');
const { default:Fastify }=await import('fastify');
const app=Fastify({logger:false});
await app.register(authRoutes);
await app.register(adminRoutes);
await app.ready();
after(async()=>{await app.close();db.close();rmSync(dir,{recursive:true,force:true});});

const masterPass='master-senha-sintetica-123!';
const managerPass='gerente-senha-sintetica-123!';
const host={host:'localhost',origin:'http://localhost'};
const send=(method,url,payload,cookie)=>app.inject({
  method,url,headers:{...host,...(cookie?{cookie}:{})},
  ...(payload===undefined?{}:{payload})
});
async function addUser(login,papel,restaurante,senha){
  const id=randomUUID(), now=Date.now();
  db.prepare(`INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em)
    VALUES(?,?,?,?,?,?,?,?)`).run(id,restaurante,login,login,await passwordHash(senha),papel,now,now);
  return id;
}
function addRest(name){
  const id=randomUUID();
  db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)')
    .run(id,name,name.toLowerCase(),Date.now());
  return id;
}
async function cookie(login,pass){
  const r=await send('POST','/api/auth/login',{login,senha:pass});
  assert.equal(r.statusCode,200,r.body);
  return r.headers['set-cookie'].split(';')[0];
}
const A=addRest('SegurancaA34'),B=addRest('SegurancaB34');
const managerA=await addUser('gerente-seg-a34','gerente',A,managerPass);
await addUser('gerente-seg-b34','gerente',B,managerPass);

test('F13/F15: sem contexto e contexto cruzado negam lista e reset',async()=>{
  await addUser('master-ctx-a34','master',null,masterPass);
  const session=await cookie('master-ctx-a34',masterPass);
  const url='/api/admin/restaurantes/'+A+'/gerentes';
  assert.equal((await send('GET',url,undefined,session)).statusCode,403);
  assert.equal((await send('PATCH',url+'/'+managerA+'/senha',{
    senha:'senha-nova-nao-aplicada-123!',senha_master_atual:masterPass
  },session)).statusCode,403);
  assert.equal((await send('POST','/api/admin/contexto/'+B,{},session)).statusCode,200);
  assert.equal((await send('GET',url,undefined,session)).statusCode,403);
  assert.equal((await send('POST','/api/auth/logout',{},session)).statusCode,200);
  assert.equal((await send('GET',url,undefined,session)).statusCode,401);
});

test('F15: cinco senhas Master inválidas bloqueiam nova tentativa, sem trocar o gerente',async()=>{
  await addUser('master-limite-a34','master',null,masterPass);
  const session=await cookie('master-limite-a34',masterPass);
  const url='/api/admin/restaurantes/'+A+'/gerentes/'+managerA+'/senha';
  assert.equal((await send('POST','/api/admin/contexto/'+A,{},session)).statusCode,200);
  const before=db.prepare('SELECT senha_hash FROM usuarios WHERE id=?').get(managerA).senha_hash;
  for(let i=0;i<5;i++){
    const r=await send('PATCH',url,{senha:'nova-senha-nunca-aplicada-123!',senha_master_atual:'incorreta'},session);
    assert.equal(r.statusCode,403,r.body);
  }
  const blocked=await send('PATCH',url,{senha:'nova-senha-nunca-aplicada-123!',senha_master_atual:masterPass},session);
  assert.equal(blocked.statusCode,429,blocked.body);
  assert.equal(db.prepare('SELECT senha_hash FROM usuarios WHERE id=?').get(managerA).senha_hash,before);
  assert.equal(db.prepare('SELECT count(*) total FROM auditoria_reset_gerente WHERE gerente_id=?').get(managerA).total,0);
});

test('F15: Origin/Fetch Metadata protegem mutação; gerente não pode usar endpoint Master',async()=>{
  await addUser('master-origem-a34','master',null,masterPass);
  const session=await cookie('master-origem-a34',masterPass);
  const manager=await cookie('gerente-seg-b34',managerPass);
  const url='/api/admin/restaurantes/'+A+'/gerentes/'+managerA+'/senha';
  const payload={senha:'nova-senha-nao-aplicada-123!',senha_master_atual:masterPass};
  assert.equal((await send('POST','/api/admin/contexto/'+A,{},session)).statusCode,200);
  const missing=await app.inject({method:'PATCH',url,headers:{host:'localhost',cookie:session},payload});
  assert.equal(missing.statusCode,403,missing.body);
  const cross=await app.inject({method:'PATCH',url,
    headers:{...host,'sec-fetch-site':'cross-site',cookie:session},payload});
  assert.equal(cross.statusCode,403,cross.body);
  assert.equal((await send('PATCH',url,payload,manager)).statusCode,403);
});


test('F15: cota SQLite conta resets bem-sucedidos e mantém o limite entre consultas',async()=>{
  await addUser('master-cota-ok-a34','master',null,masterPass);
  const session=await cookie('master-cota-ok-a34',masterPass);
  assert.equal((await send('POST','/api/admin/contexto/'+A,{},session)).statusCode,200);
  const url='/api/admin/restaurantes/'+A+'/gerentes/'+managerA+'/senha';
  for(let i=0;i<5;i++){
    const res=await send('PATCH',url,{
      senha:'senha-sintetica-rotativa-'+i+'-123!',senha_master_atual:masterPass
    },session);
    assert.equal(res.statusCode,200,res.body);
  }
  const blocked=await send('PATCH',url,{
    senha:'senha-sintetica-rotativa-6-123!',senha_master_atual:masterPass
  },session);
  assert.equal(blocked.statusCode,429,blocked.body);
  const actor=db.prepare('SELECT id FROM usuarios WHERE login=?').get('master-cota-ok-a34').id;
  const quota=db.prepare('SELECT quantidade,janela_ate FROM admin_reset_limites WHERE chave=?')
    .get('actor:'+actor);
  assert.equal(quota.quantidade,5);
  assert.ok(quota.janela_ate>Date.now());
  const fresh=await cookie('master-cota-ok-a34',masterPass);
  assert.equal((await send('POST','/api/admin/contexto/'+A,{},fresh)).statusCode,200);
  const again=await send('PATCH',url,{
    senha:'senha-sintetica-rotativa-7-123!',senha_master_atual:masterPass
  },fresh);
  assert.equal(again.statusCode,429,again.body);
});
