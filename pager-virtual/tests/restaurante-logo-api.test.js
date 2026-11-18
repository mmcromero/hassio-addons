// Regressão funcional de identidade: isolamento multi-restaurante e cliente SSE.
// Opera somente em SQLite temporário, sem conectar HA, Windows ou rede pública.
import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { randomBytes, randomUUID, createHash } from 'node:crypto';
import Fastify from 'fastify';

const dir=mkdtempSync(join(tmpdir(),'avisaqui-logo-api-'));
process.env.DATA_PATH=dir;
const {default:db}=await import('../src/db.js');
const {authRoutes}=await import('../src/auth.js');
const {adminRoutes}=await import('../src/admin.js');
const {pedidosRoutes}=await import('../src/routes/pedidos.js');
const app=Fastify({logger:false});
await app.register(authRoutes);
await app.register(adminRoutes);
await app.register(pedidosRoutes);
await app.ready();
after(async()=>{await app.close();db.close();rmSync(dir,{recursive:true,force:true});});

const now=Date.now();
const restA=randomUUID(),restB=randomUUID();
const logoA='https://assets.test/logo-a.png',logoB='https://assets.test/logo-b.png';
for(const [id,name,slug,logo] of [
  [restA,'Restaurante Alfa','restaurante-alfa',logoA],
  [restB,'Restaurante Beta','restaurante-beta',logoB]
])db.prepare('INSERT INTO restaurantes(id,nome,slug,logo_url,created_at) VALUES(?,?,?,?,?)')
 .run(id,name,slug,logo,now);
function makeSession(role,restaurantId){
 const userId=randomUUID(),sessionId=randomUUID(),token=randomBytes(32).toString('hex');
 db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?)')
  .run(userId,restaurantId,role,role+'-'+userId,'sem-login-real',role,now,now);
 db.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
  .run(sessionId,userId,createHash('sha256').update(token).digest('hex'),now,now+600000);
 return 'bipou_session='+token;
}
const master=makeSession('master',null),managerA=makeSession('gerente',restA);
const call=(method,url,cookie,payload)=>app.inject({method,url,
 headers:{host:'localhost',origin:'http://localhost',cookie},
 ...(payload===undefined?{}:{payload})});

test('Master lista logos reais; gerente não acessa ou modifica logo',async()=>{
 const denied=await call('GET','/api/admin/restaurantes',managerA);
 assert.equal(denied.statusCode,403);
 const list=await call('GET','/api/admin/restaurantes',master);
 assert.equal(list.statusCode,200,list.body);
 assert.equal(list.json().find(r=>r.id===restA).logo_url,logoA);
 assert.equal(list.json().find(r=>r.id===restB).logo_url,logoB);
 const deniedEdit=await call('PATCH','/api/admin/restaurantes/'+restA+'/logo',managerA,{logo_url:'https://assets.test/indevido.png'});
 assert.equal(deniedEdit.statusCode,403);
 assert.equal(db.prepare('SELECT logo_url FROM restaurantes WHERE id=?').get(restA).logo_url,logoA);
});

test('edição Master valida HTTPS e não altera outro restaurante',async()=>{
 const path='/api/admin/restaurantes/'+restA+'/logo';
 assert.equal((await call('PATCH',path,master,{logo_url:'http://assets.test/inseguro.png'})).statusCode,400);
 assert.equal((await call('PATCH',path,master,{logo_url:'javascript:alert(1)'})).statusCode,400);
 const updated=await call('PATCH',path,master,{logo_url:'https://assets.test/novo-a.png'});
 assert.equal(updated.statusCode,200,updated.body);
 assert.equal(db.prepare('SELECT logo_url FROM restaurantes WHERE id=?').get(restA).logo_url,'https://assets.test/novo-a.png');
 assert.equal(db.prepare('SELECT logo_url FROM restaurantes WHERE id=?').get(restB).logo_url,logoB);
});

test('sessão gerente e seleção Master retornam nome, logo e slug do restaurante correto',async()=>{
 const manager=await call('GET','/api/auth/me',managerA);
 assert.equal(manager.statusCode,200,manager.body);
 assert.equal(manager.json().restaurante_logo_url,'https://assets.test/novo-a.png');
 assert.equal(manager.json().restaurante_slug,'restaurante-alfa');
 assert.equal((await call('POST','/api/admin/contexto/'+restB,master,{})).statusCode,200);
 const selected=await call('GET','/api/auth/me',master);
 assert.equal(selected.json().restaurante_id,restB);
 assert.equal(selected.json().restaurante_logo_url,logoB);
 assert.equal(selected.json().restaurante_slug,'restaurante-beta');
 assert.equal((await call('POST','/api/admin/contexto/'+restA,master,{})).statusCode,200);
 const switched=await call('GET','/api/auth/me',master);
 assert.equal(switched.json().restaurante_id,restA);
 assert.equal(switched.json().restaurante_logo_url,'https://assets.test/novo-a.png');
});

test('SSE do cliente usa restaurante real do pedido, não valor fornecido na URL',{timeout:12000},async()=>{
 const orderToken=randomBytes(18).toString('hex');
 db.prepare('INSERT INTO pedidos(id,restaurante_id,numero,token,status,created_at) VALUES(?,?,?,?,?,?)')
  .run(randomUUID(),restB,123,orderToken,'preparo',now);
 const address=await app.listen({host:'127.0.0.1',port:0});
 const controller=new AbortController();const timer=setTimeout(()=>controller.abort(),5000);
 try{
  const response=await fetch(address+'/api/pedidos/stream/'+encodeURIComponent(orderToken),{signal:controller.signal});
  assert.equal(response.status,200);
  let text='';const reader=response.body.getReader();
  while(!text.includes('\n\n')){
   const part=await reader.read();if(part.done)throw Error('SSE encerrado antes do status inicial');
   text+=new TextDecoder().decode(part.value);
  }
  const line=text.split('\n').find(v=>v.startsWith('data: '));
  assert.ok(line,text);
  const event=JSON.parse(line.slice(6));
  assert.equal(event.status,'preparo');
  assert.equal(event.restaurante_nome,'Restaurante Beta');
  assert.equal(event.restaurante_logo_url,logoB);
 }finally{controller.abort();clearTimeout(timer);}
});
