import test, { after } from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { randomUUID } from 'node:crypto';
const temp=mkdtempSync(path.join(tmpdir(),'avisaqui-impressao-'));
process.env.DATA_PATH=temp;
const {default:db}=await import('../src/db.js');
const {passwordHash,authRoutes}=await import('../src/auth.js');
const {pedidosRoutes}=await import('../src/routes/pedidos.js');
const {integracaoImpressaoRoutes}=await import('../src/routes/integracao-impressao.js');
const {default:Fastify}=await import('fastify');
const app=Fastify();
await app.register(authRoutes);
await app.register(pedidosRoutes);
await app.register(integracaoImpressaoRoutes);
await app.ready();
after(async()=>{await app.close();db.close();rmSync(temp,{recursive:true,force:true})});
const h={host:'localhost',origin:'http://localhost'};
const post=(url,payload,headers={})=>app.inject({method:'POST',url,headers:{...h,...headers},payload});
const get=(url,headers={})=>app.inject({method:'GET',url,headers:{...h,...headers}});
const rest=(name)=>{const id=randomUUID();db.prepare('INSERT INTO restaurantes(id,nome,slug,created_at) VALUES(?,?,?,?)').run(id,name,name.toLowerCase(),Date.now());return id};
const ra=rest('LabA'),rb=rest('LabB');
for (const [name,id] of [['gerentea',ra],['gerenteb',rb]]) {
  const now=Date.now();
  db.prepare('INSERT INTO usuarios(id,restaurante_id,nome,login,senha_hash,papel,criado_em,atualizado_em) VALUES(?,?,?,?,?,?,?,?)')
   .run(randomUUID(),id,name,name,await passwordHash('senha-super-forte-123!'),'gerente',now,now);
}
async function session(name){
 const res=await post('/api/auth/login',{login:name,senha:'senha-super-forte-123!'});
 assert.equal(res.statusCode,200,res.body);
 return res.headers['set-cookie'].split(';')[0];
}
const ca=await session('gerentea'),cb=await session('gerenteb');
const credential=await post('/api/integracoes/impressao/chave',{}, {cookie:ca});
assert.equal(credential.statusCode,201,credential.body);
const token=credential.json().token;
const ah={'x-avisaqui-agent-key':token};
test('agente sem chave é bloqueado e não cria pedido',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-sem-chave-001',numero:501});
 assert.equal(res.statusCode,401);
});
test('recebimento cria pedido visível no KDS',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-501',numero:501,itens:['X-BURGER']},ah);
 assert.equal(res.statusCode,201,res.body);
 const list=await get('/api/pedidos',{cookie:ca});
 assert.ok(list.json().some(p=>p.numero===501 && p.itens[0]==='X-BURGER'));
});
test('retry do mesmo evento não cria duplicata',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-501',numero:501,itens:['X-BURGER']},ah);
 assert.equal(res.statusCode,200,res.body);
 assert.equal(res.json().repetido,true);
 assert.equal(db.prepare('SELECT COUNT(*) total FROM pedidos WHERE restaurante_id=? AND numero=501').get(ra).total,1);
});
test('novo evento com número já ativo é pendência e não duplica',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-501-b',numero:501},ah);
 assert.equal(res.statusCode,409,res.body);
 assert.equal(db.prepare("SELECT COUNT(*) total FROM integracao_impressao_eventos WHERE situacao='PENDENTE_DUPLICADO'").get().total,1);
});
test('retry após resposta incerta preserva pendência de duplicado',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-501-b',numero:501},ah);
 assert.equal(res.statusCode,409,res.body);
 assert.equal(res.json().situacao,'PENDENTE_DUPLICADO');
 assert.equal(res.json().repetido,true);
 assert.equal(db.prepare("SELECT COUNT(*) total FROM integracao_impressao_eventos WHERE situacao='PENDENTE_DUPLICADO'").get().total,1);
});
test('restaurante B não acessa pedidos, chaves ou eventos de A',async()=>{
 assert.ok(!(await get('/api/pedidos',{cookie:cb})).json().some(p=>p.numero===501));
 assert.equal((await get('/api/integracoes/impressao/eventos',{cookie:cb})).json().length,0);
 assert.equal((await get('/api/integracoes/impressao/chaves',{cookie:cb})).json().length,0);
});
test('revogação da chave impede novos eventos',async()=>{
 const id=credential.json().id;
 const revoked=await app.inject({method:'DELETE',url:'/api/integracoes/impressao/chaves/'+id,headers:{...h,cookie:ca}});
 assert.equal(revoked.statusCode,200,revoked.body);
 const next=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-502',numero:502},ah);
 assert.equal(next.statusCode,401,next.body);
});
