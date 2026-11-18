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
// Simula no SQLite uma identidade criada pelo resgate e confirmada por ACK.
// Este teste verifica a API de pedidos; a criptografia QR tem suíte própria.
const {preparePairingSchema}=await import('../src/pairing/backend/schema.js');
preparePairingSchema(db);
const token='b'.repeat(64),manualToken='c'.repeat(64);
const hash=value=>(awaitCrypto.createHash('sha256').update(value).digest('hex'));
const awaitCrypto=await import('node:crypto');
const keyId=randomUUID(),deviceId=randomUUID(),pairId=randomUUID(),operationId=randomUUID();
const stamp=Date.now();
db.prepare(`INSERT INTO integracao_pareamento_solicitacoes
 (id,client_request_id,protocol,estado,signing_public_key,delivery_public_key,codigo,criado_em,expira_aprovacao_em,restaurante_id)
 VALUES(?,?,'pair-v1','CONFIRMADO','fixture-ed25519','fixture-x25519','12345678',?,?,?)`).run(pairId,randomUUID(),stamp,stamp+300000,ra);
db.prepare('INSERT INTO integracao_impressao_dispositivos(id,restaurante_id,caixa_nome,criado_em) VALUES(?,?,?,?)')
 .run(deviceId,ra,'Caixa sintético',stamp);
db.prepare(`INSERT INTO integracao_pareamento_resgates
 (pairing_id,operation_id,dispositivo_id,envelope_json,emitido_em,recuperacao_expira_em,ack_em)
 VALUES(?,?,?,'{}',?,?,?)`).run(pairId,operationId,deviceId,stamp,stamp+3600000,stamp);
db.prepare('INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em,dispositivo_id) VALUES(?,?,?,?,?)')
 .run(keyId,ra,hash(token),stamp,deviceId);
db.prepare('INSERT INTO integracao_impressao_chaves(id,restaurante_id,hash,criado_em) VALUES(?,?,?,?)')
 .run(randomUUID(),ra,hash(manualToken),stamp);
const ah={'x-avisaqui-agent-key':token};
test('agente sem chave é bloqueado e não cria pedido',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-sem-chave-001',numero:501});
 assert.equal(res.statusCode,401);
});
test('token manual antigo não autoriza pedido',async()=>{
 const res=await post('/api/integracoes/impressao/pedidos',
  {evento_id:'legado-bloqueado-001',numero:503},
  {'x-avisaqui-agent-key':manualToken});
 assert.equal(res.statusCode,401);
});
test('dispositivo sem ACK não autoriza envio',async()=>{
 db.prepare('UPDATE integracao_pareamento_resgates SET ack_em=NULL WHERE pairing_id=?').run(pairId);
 try{
  const res=await post('/api/integracoes/impressao/pedidos',
   {evento_id:'sem-ack-0001',numero:504},ah);
  assert.equal(res.statusCode,401);
 }finally{
  db.prepare('UPDATE integracao_pareamento_resgates SET ack_em=? WHERE pairing_id=?').run(stamp,pairId);
 }
});
test('dispositivo QR revogado nao recebe novos pedidos',async()=>{
 db.prepare('UPDATE integracao_impressao_dispositivos SET revogado_em=? WHERE id=?').run(stamp,deviceId);
 try{
  const res=await post('/api/integracoes/impressao/pedidos',
   {evento_id:'revogado-qr-0001',numero:505},ah);
  assert.equal(res.statusCode,401);
 }finally{
  db.prepare('UPDATE integracao_impressao_dispositivos SET revogado_em=NULL WHERE id=?').run(deviceId);
 }
});
test('credencial QR de restaurante divergente nao autoriza envio',async()=>{
 db.prepare('UPDATE integracao_impressao_chaves SET restaurante_id=? WHERE id=?').run(rb,keyId);
 try{
  const res=await post('/api/integracoes/impressao/pedidos',
   {evento_id:'tenant-qr-0001',numero:506},ah);
  assert.equal(res.statusCode,401);
 }finally{
  db.prepare('UPDATE integracao_impressao_chaves SET restaurante_id=? WHERE id=?').run(ra,keyId);
 }
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
 assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_impressao_chaves WHERE restaurante_id=?').get(rb).n,0);
});
test('revogação da chave impede novos eventos',async()=>{
 // A revogação de um computador pair-v1 invalida a chave associada.
 db.prepare('UPDATE integracao_impressao_chaves SET revogado_em=? WHERE id=?').run(Date.now(),keyId);
 const next=await post('/api/integracoes/impressao/pedidos',{evento_id:'lab-evento-502',numero:502},ah);
 assert.equal(next.statusCode,401,next.body);
});

test('cadastro manual de chaves foi retirado; o pareamento é o emissor',async()=>{
 const response=await post('/api/integracoes/impressao/chave',{}, {cookie:ca});
 assert.equal(response.statusCode,404);
});
