import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';

const dir=mkdtempSync(path.join(tmpdir(),'avisaqui-gerentes-041-'));
process.env.DATA_PATH=dir;
const {default:db}=await import('../src/db.js');
const {authRoutes,passwordHash}=await import('../src/auth.js');
const {adminRoutes}=await import('../src/admin.js');
const {default:Fastify}=await import('fastify');
const app=Fastify({logger:false});
await app.register(authRoutes);
await app.register(adminRoutes);
await app.ready();
after(async()=>{await app.close();db.close();rmSync(dir,{recursive:true,force:true});});
const pwd='Senha-de-Teste-Master-123!';
const old='Senha-Gerente-Antiga-123!';
const next='Senha-Gerente-Nova-456!';
const headers={host:'localhost',origin:'http://localhost'};
const send=(method,url,payload,cookie)=>app.inject({
  method,url,headers:{...headers,...(cookie?{cookie}:{})},
  ...(payload===undefined?{}:{payload})
});
function rest(slug){
  const id=randomUUID();
  db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)').run(id,slug,slug,Date.now());
  return id;
}
async function addUser(login,papel,restaurant,pass){
  const id=randomUUID(),now=Date.now();
  db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?)')
    .run(id,restaurant,login,login,await passwordHash(pass),papel,now,now);
  return id;
}
async function login(name,pass){
  const r=await send('POST','/api/auth/login',{login:name,senha:pass});
  assert.equal(r.statusCode,200,r.body);
  return r.headers['set-cookie'].split(';')[0];
}
const a=rest('teste-gerentes-41-a'),b=rest('teste-gerentes-41-b');
const mid=await addUser('master-41','master',null,pwd);
const uid=await addUser('gerente-legado-41','gerente',a,old);
const other=await addUser('gerente-outra-41','gerente',b,old);
const operator=await addUser('operador-41','operador',a,old);
const base='/api/admin/restaurantes/'+a+'/gerentes';
let master,manager;
test('Issue 41: contas individuais, contexto e conflito 409',async()=>{
  master=await login('master-41',pwd);
  manager=await login('gerente-legado-41',old);
  assert.equal((await send('POST',base,{nome:'Gerente Novo',login:'novo-41',senha:next},master)).statusCode,403);
  assert.equal((await send('POST','/api/admin/contexto/'+a,{},master)).statusCode,200);
  assert.equal((await send('POST',base,{nome:'Gerente Novo',login:'novo-41',senha:next},manager)).statusCode,403);
  const created=await send('POST',base,{nome:'Gerente Novo',login:' NOVO-41 ',senha:next},master);
  assert.equal(created.statusCode,201,created.body);
  assert.equal(created.json().login,'novo-41');
  const duplicate=await send('POST',base,{nome:'Outro Nome',login:'novo-41',senha:next},master);
  assert.equal(duplicate.statusCode,409,duplicate.body);
  const list=await send('GET',base,undefined,master);
  assert.equal(list.statusCode,200,list.body);
  assert.equal(list.json().length,2);
  assert.equal((await send('GET','/api/admin/restaurantes/'+b+'/gerentes',undefined,master)).statusCode,403);
  assert.equal((await send('PATCH',base+'/'+other,{nome:'Errado',login:'errado-41',senha_master_atual:pwd},master)).statusCode,404);
  assert.equal((await send('PATCH',base+'/'+operator,{nome:'Errado',login:'errado-41',senha_master_atual:pwd},master)).statusCode,404);
  const cross='/api/admin/restaurantes/'+b+'/gerentes/'+other;
  assert.equal((await send('PATCH',cross,{nome:'Errado',login:'errado-41',senha_master_atual:pwd},master)).statusCode,403);
  assert.equal((await send('PATCH',base+'/'+uid+'/ativo',{ativo:false,senha_master_atual:pwd},manager)).statusCode,403);
  assert.equal((await send('PATCH',base+'/'+uid,{nome:'Errado',login:'errado-41',senha_master_atual:pwd},manager)).statusCode,403);
  const noOrigin=await app.inject({method:'PATCH',url:base+'/'+uid+'/ativo',
    headers:{host:'localhost',cookie:master},payload:{ativo:false,senha_master_atual:pwd}});
  assert.equal(noOrigin.statusCode,403);
});
test('Issue 41: editar mantém ID, login único e encerra sessão se login mudou',async()=>{
  db.prepare('DELETE FROM admin_reset_limites').run();
  const conflict=await send('PATCH',base+'/'+uid,{nome:'Alterado',login:'NOVO-41',senha_master_atual:pwd},master);
  assert.equal(conflict.statusCode,409,conflict.body);
  assert.equal(db.prepare('SELECT nome FROM usuarios WHERE id=?').get(uid).nome,'gerente-legado-41');
  const r=await send('PATCH',base+'/'+uid,{nome:'Nome Corrigido',login:'corrigido-41',senha_master_atual:pwd},master);
  assert.equal(r.statusCode,200,r.body);
  const row=db.prepare('SELECT id,nome,login FROM usuarios WHERE id=?').get(uid);
  assert.equal(row.id,uid);assert.equal(row.nome,'Nome Corrigido');assert.equal(row.login,'corrigido-41');
  assert.equal((await send('GET','/api/auth/me',undefined,manager)).statusCode,401);
  manager=await login('corrigido-41',old);
  assert.equal((await send('PATCH',base+'/'+uid,{nome:'x',login:'errado-41',senha_master_atual:pwd},master)).statusCode,400);
});
test('Issue 41: desativar revoga, bloqueia login e é idempotente',async()=>{
  db.prepare('DELETE FROM admin_reset_limites').run();
  const r=await send('PATCH',base+'/'+uid+'/ativo',{ativo:false,senha_master_atual:pwd},master);
  assert.equal(r.statusCode,200,r.body);
  assert.equal((await send('GET','/api/auth/me',undefined,manager)).statusCode,401);
  assert.equal((await send('POST','/api/auth/login',{login:'corrigido-41',senha:old})).statusCode,401);
  assert.equal((await send('PATCH',base+'/'+uid+'/ativo',{ativo:false,senha_master_atual:pwd},master)).statusCode,200);
  assert.equal(db.prepare('SELECT ativo FROM usuarios WHERE id=?').get(uid).ativo,0);
  assert.equal((await send('PATCH',base+'/'+uid+'/ativo',{ativo:true,senha_master_atual:pwd},master)).statusCode,400);
});
test('Issue 41: reativar exige senha nova sem ressuscitar sessão antiga',async()=>{
  db.prepare('DELETE FROM admin_reset_limites').run();
  const reused=await send('PATCH',base+'/'+uid+'/ativo',{ativo:true,senha:old,senha_master_atual:pwd},master);
  assert.equal(reused.statusCode,400,reused.body);
  assert.equal(db.prepare('SELECT ativo FROM usuarios WHERE id=?').get(uid).ativo,0);
  const r=await send('PATCH',base+'/'+uid+'/ativo',{ativo:true,senha:next,senha_master_atual:pwd},master);
  assert.equal(r.statusCode,200,r.body);
  assert.equal((await send('POST','/api/auth/login',{login:'corrigido-41',senha:old})).statusCode,401);
  assert.equal((await send('GET','/api/auth/me',undefined,manager)).statusCode,401);
  const newCookie=await login('corrigido-41',next);
  assert.equal((await send('GET','/api/auth/me',undefined,newCookie)).statusCode,200);
  const audit=db.prepare('SELECT * FROM auditoria_reset_gerente WHERE gerente_id=? ORDER BY criado_em').all(uid);
  assert.ok(audit.some(x=>x.acao==='editar_gerente'));
  assert.ok(audit.some(x=>x.acao==='desativar_gerente'));
  assert.ok(audit.some(x=>x.acao==='reativar_gerente'));
  assert.ok(audit.every(x=>x.ator_id===mid&&x.restaurante_id===a));
  assert.ok(!JSON.stringify(audit).includes(pwd));
  assert.ok(!JSON.stringify(audit).includes(next));
  assert.ok(!JSON.stringify(audit).includes(old));
  assert.equal(db.prepare('SELECT COUNT(*) n FROM sessoes WHERE usuario_id=? AND revogado_em IS NULL').get(uid).n,1);
});
test('Issue 41: erros de auditoria revertem desativação e sessões',async()=>{
  db.prepare('DELETE FROM admin_reset_limites').run();
  const live=await login('corrigido-41',next);
  db.exec(`CREATE TRIGGER audit_fail_41 BEFORE INSERT ON auditoria_reset_gerente
    BEGIN SELECT RAISE(ABORT,'auditoria indisponivel'); END`);
  try{
    const r=await send('PATCH',base+'/'+uid+'/ativo',{ativo:false,senha_master_atual:pwd},master);
    assert.equal(r.statusCode,500,r.body);
    assert.equal(db.prepare('SELECT ativo FROM usuarios WHERE id=?').get(uid).ativo,1);
    assert.equal((await send('GET','/api/auth/me',undefined,live)).statusCode,200);
  }finally{db.exec('DROP TRIGGER audit_fail_41');}
});
test('Issue 41: interface contextual oferece ações e mensagens',()=>{
  const html=readFileSync(new URL('../src/public/admin.html',import.meta.url),'utf8');
  for(const action of ['Criar gerente','Editar nome/login','Desativar','Reativar','Redefinir senha']){
    assert.ok(html.includes(action),'Ação ausente: '+action);
  }
  assert.match(html,/aria-live/);
  assert.match(html,/dialog\.showModal\(\)/);
  assert.match(html,/refreshManagers\(\)/);
});
