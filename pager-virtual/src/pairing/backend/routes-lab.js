// AVISAQUI-PAIR-001 — rotas pair-v1 de laboratório. NÃO importar no servidor ativo.
// Requer banco isolado, políticas explícitas e autenticação injetada; não é release comercial.
import { randomBytes, randomUUID, createHash, randomInt } from 'node:crypto';
import { parsePublicKey, assertUuid, assertProtocol, verifyOperationProof,
  sealCredentialEnvelope, PAIR_PROTOCOL } from './protocol-v2.js';
import { preparePairingSchema } from './schema.js';

const hash = s => createHash('sha256').update(s).digest('hex');
const digits = () => String(randomInt(100000000)).padStart(8, '0');
const fail = (status, error) => ({ status, error });
const UUID_PATTERN = /^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/;
const asUuid = v => typeof v === 'string' && UUID_PATTERN.test(v);
const textName = value => typeof value === 'string' && value.trim().length > 0 &&
  value.length <= 120 && !/[\u0000-\u001f\u007f]/.test(value);
function parseInput(value, kind) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw fail(400, 'Dados inválidos');
  if (kind === 'new') {
    assertProtocol(value.protocol);
    assertUuid(value.client_request_id);
    parsePublicKey(value.signing_public_key, 'ed25519');
    parsePublicKey(value.delivery_public_key, 'x25519');
  }
  if (kind === 'challenge') {
    assertProtocol(value.protocol); assertUuid(value.operation_id);
    if (!['status', 'redeem', 'ack'].includes(value.purpose)) throw fail(400, 'Finalidade inválida');
  }
  if (kind === 'redeem' || kind === 'ack') {
    assertProtocol(value.protocol); assertUuid(value.operation_id); assertUuid(value.challenge_id);
    if (kind === 'ack') assertUuid(value.ack_operation_id);
    if (typeof value.signature !== 'string' || value.signature.length > 128) throw fail(400, 'Prova inválida');
  }
  return value;
}
function makeLimiter(db, now) {
  // Janela fixa persistida no SQLite: todos os processos usando o mesmo banco
  // compartilham o contador. O IP é convertido em digest e não é armazenado.
  // Este controle local não substitui WAF/limites em múltiplos servidores.
  const limit = db.transaction((key, max, windowMs) => {
    const stamp=now(), digest=hash('avisaqui-pair-v1-limit:'+key);
    const previous=db.prepare('SELECT contador,expira_em FROM integracao_pareamento_limites WHERE chave_hash=?').get(digest);
    if (!previous || previous.expira_em<=stamp) {
      db.prepare(`INSERT INTO integracao_pareamento_limites(chave_hash,contador,expira_em)
        VALUES(?,?,?) ON CONFLICT(chave_hash) DO UPDATE SET contador=excluded.contador,expira_em=excluded.expira_em`)
        .run(digest,1,stamp+windowMs);
      return true;
    }
    if (previous.contador>=max) return false;
    db.prepare('UPDATE integracao_pareamento_limites SET contador=contador+1 WHERE chave_hash=?').run(digest);
    return true;
  });
  return (key, max, windowMs) => {
    if (typeof key!=='string' || key.length>256 ||
        !Number.isSafeInteger(max) || max<1 ||
        !Number.isSafeInteger(windowMs) || windowMs<1000) return false;
    try { return limit.immediate(key,max,windowMs); }
    catch { return false; } // falha fechada se SQLite indisponível
  };
}
function requirePolicy(ms) {
  if (!Number.isSafeInteger(ms) || ms <= 1000 || ms > 7 * 86400000) throw new TypeError('Prazo de política não aprovado/fornecido');
}
export function buildPairV1LabRoutes({ db, publicOrigin, policy, managerFromRequest, now = Date.now }) {
  // A configuração pública não é inferida de Host/X-Forwarded-*, evitando QR adulterado.
  let url;
  try { url = new URL(publicOrigin); } catch { throw new TypeError('Origem pública HTTPS necessária'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search ||
      url.hash || !['/', '/avisaqui', '/avisaqui/'].includes(url.pathname)) {
    throw new TypeError('Origem HTTPS inválida');
  }
  if (typeof managerFromRequest !== 'function') throw new TypeError('Autorização de gerente obrigatória');
  for (const p of ['approvalMs','challengeMs','recoveryMs']) requirePolicy(policy?.[p]);
  const origin = url.origin, basePath = url.pathname.replace(/\/$/, '');
  const rate = makeLimiter(db,now);
  const select = id => db.prepare('SELECT * FROM integracao_pareamento_solicitacoes WHERE id=?').get(id);
  const manager = (req, reply) => {
    // Implementação da autenticação é fornecida por adaptador externo testado; não confie no corpo.
    // GET normalmente não envia Origin no navegador; escrita sempre exige Origin.
    if (((req.method !== 'GET' && req.method !== 'HEAD') || req.headers.origin) &&
        req.headers.origin !== origin ||
        (req.headers['sec-fetch-site'] && req.headers['sec-fetch-site'] !== 'same-origin') ||
        (req.headers['sec-fetch-mode'] === 'no-cors')) {
      reply.code(403).send({error:'Origem não autorizada'}); return null;
    }
    // Não confiar em X-Forwarded-Host/Proto ou X-Test-User: fronteira HTTPS
    // e host confiável devem ser definidos pelo proxy e auth.js.
    const actor = managerFromRequest(req, reply);
    if (reply.sent) return null; // requer sessão real pode ter retornado 401/403
    if (!actor || !['gerente','master'].includes(actor.papel) || !actor.restaurante_id || !actor.id) {
      reply.code(403).send({error:'Acesso não autorizado'}); return null;
    }
    return actor;
  };
  const tx = fn => db.transaction(fn).immediate();
  const audit = (actor, pair, action, result) => db.prepare(
    'INSERT INTO integracao_pareamento_auditoria(id,actor_id,restaurante_id,pairing_id,acao,resultado,criado_em) VALUES(?,?,?,?,?,?,?)'
  ).run(randomUUID(),actor.id,actor.restaurante_id,pair.id,action,result,now());
  function challengeProof(pair, purpose, operationId, challengeId, signature) {
    const c = db.prepare('SELECT * FROM integracao_pareamento_desafios WHERE id=? AND pairing_id=? AND purpose=? AND operation_id=?')
      .get(challengeId,pair.id,purpose,operationId);
    if (!c || c.consumido_em !== null || c.expira_em <= now()) throw fail(403, 'Prova inválida ou expirada');
    if (!verifyOperationProof({
      signingPublicKey:pair.signing_public_key,purpose,pairingId:pair.id,
      operationId,challengeId,challenge:Buffer.from(c.desafio).toString('base64url'),signature
    })) throw fail(403, 'Prova inválida ou expirada');
    const n = db.prepare('UPDATE integracao_pareamento_desafios SET consumido_em=? WHERE id=? AND consumido_em IS NULL')
      .run(now(),challengeId).changes;
    if (n !== 1) throw fail(409,'Desafio já usado');
  }
  return async function registerPairV1LabRoutes(app) {
    // Migração SOMENTE após chamada explícita de registro em laboratório.
    preparePairingSchema(db);
    app.addHook('onRequest', async (_req, reply) => { reply.header('Cache-Control', 'no-store'); });
    app.setErrorHandler((err, _req, reply) => {
      // Retorno público não divulga chaves, IDs internos, detalhes SQL ou payloads.
      if (Number.isInteger(err.status) && err.status >= 400 && err.status < 500)
        return reply.code(err.status).send({error:err.error || 'Requisição recusada'});
      if (err instanceof TypeError) return reply.code(400).send({error:'Dados inválidos'});
      return reply.code(503).send({error:'Operação indisponível'});
    });
    // Administração baseada exclusivamente no tenant autenticado.
    app.get('/api/agentes/dispositivos', async (req, reply) => {
      const actor=manager(req,reply); if (!actor) return;
      // GET exige sessão e tenant válidos; Origin pode estar ausente em navegadores legítimos.
      // Origin presente e Fetch Metadata cross-site continuam sujeitos ao bloqueio.
      const rows=db.prepare(`SELECT id,caixa_nome,criado_em,revogado_em,last_seen_em
        FROM integracao_impressao_dispositivos WHERE restaurante_id=?
        ORDER BY criado_em DESC LIMIT 100`).all(actor.restaurante_id);
      return reply.send(rows);
    });
    app.patch('/api/agentes/dispositivos/:id', async (req, reply) => {
      const actor=manager(req,reply); if (!actor) return;
      if (!asUuid(req.params.id) || !textName(req.body?.caixa_nome))
        return reply.code(400).send({error:'Dados inválidos'});
      const name=req.body.caixa_nome.trim();
      const changed=tx(()=>{
        const device=db.prepare('SELECT * FROM integracao_impressao_dispositivos WHERE id=? AND restaurante_id=?')
          .get(req.params.id,actor.restaurante_id);
        if (!device) throw fail(404,'Computador não encontrado');
        if (device.revogado_em!==null) throw fail(409,'Computador revogado');
        db.prepare('UPDATE integracao_impressao_dispositivos SET caixa_nome=? WHERE id=? AND restaurante_id=?')
          .run(name,device.id,actor.restaurante_id);
        db.prepare(`INSERT INTO integracao_pareamento_auditoria
          (id,actor_id,restaurante_id,dispositivo_id,acao,resultado,criado_em)
          VALUES(?,?,?,?,?,?,?)`).run(randomUUID(),actor.id,actor.restaurante_id,
          device.id,'renomear',JSON.stringify({antes:device.caixa_nome,depois:name}),now());
        return {id:device.id,caixa_nome:name};
      });
      return reply.send(changed);
    });
    app.delete('/api/agentes/dispositivos/:id', async (req, reply) => {
      const actor=manager(req,reply); if (!actor) return;
      if (!asUuid(req.params.id) || req.body?.confirmar !== true)
        return reply.code(400).send({error:'Confirmação obrigatória'});
      const changed=tx(()=>{
        const device=db.prepare('SELECT id,revogado_em FROM integracao_impressao_dispositivos WHERE id=? AND restaurante_id=?')
          .get(req.params.id,actor.restaurante_id);
        if (!device) throw fail(404,'Computador não encontrado');
        if (device.revogado_em!==null) return {id:device.id,revogado:true,repetido:true};
        const time=now();
        db.prepare('UPDATE integracao_impressao_dispositivos SET revogado_em=? WHERE id=? AND restaurante_id=?')
          .run(time,device.id,actor.restaurante_id);
        db.prepare('UPDATE integracao_impressao_chaves SET revogado_em=? WHERE dispositivo_id=? AND restaurante_id=? AND revogado_em IS NULL')
          .run(time,device.id,actor.restaurante_id);
        db.prepare(`INSERT INTO integracao_pareamento_auditoria
          (id,actor_id,restaurante_id,dispositivo_id,acao,resultado,criado_em)
          VALUES(?,?,?,?,?,?,?)`).run(randomUUID(),actor.id,actor.restaurante_id,
          device.id,'revogar','confirmado',time);
        return {id:device.id,revogado:true,repetido:false};
      });
      return reply.send(changed);
    });
    app.post('/api/agentes/pareamentos', async (req, reply) => {
      if (!rate('create:'+req.ip, 12, 60000)) return reply.code(429).send({error:'Limite excedido'});
      const input = parseInput(req.body,'new');
      const result = tx(() => {
        let previous = db.prepare('SELECT * FROM integracao_pareamento_solicitacoes WHERE client_request_id=?').get(input.client_request_id);
        if (previous) {
          if (previous.signing_public_key !== input.signing_public_key ||
              previous.delivery_public_key !== input.delivery_public_key) throw fail(409,'Operação conflitante');
          return {row:previous, repeated:true};
        }
        const time=now(), id=randomUUID(), code=digits();
        db.prepare(`INSERT INTO integracao_pareamento_solicitacoes
          (id,client_request_id,protocol,estado,signing_public_key,delivery_public_key,codigo,criado_em,expira_aprovacao_em)
          VALUES(?,?,?,?,?,?,?,?,?)`).run(id,input.client_request_id,PAIR_PROTOCOL,'PENDENTE',
          input.signing_public_key,input.delivery_public_key,code,time,time+policy.approvalMs);
        return {row:select(id),repeated:false};
      });
      const {row,repeated}=result;
      return reply.code(repeated?200:201).send({
        protocol:PAIR_PROTOCOL,id:row.id,code:row.codigo,
        qr_url:origin+basePath+'/autorizar?solicitacao='+encodeURIComponent(row.id),
        expires_at:row.expira_aprovacao_em,state:row.estado
      });
    });
    app.post('/api/agentes/pareamentos/:id/desafios', async (req, reply) => {
      if (!asUuid(req.params.id)) return reply.code(404).send({error:'Solicitação não encontrada'});
      if (!rate('challenge:'+req.ip,120,60000) ||
          !rate('pair:'+req.params.id,120,60000)) return reply.code(429).send({error:'Limite excedido'});
      const input=parseInput(req.body,'challenge'), time=now();
      const result=tx(() => {
        const pair=select(req.params.id);
        if (!pair || ['RECUSADO','CANCELADO','EXPIRADO'].includes(pair.estado))
          throw fail(404,'Solicitação não encontrada');
        if (pair.estado==='CONFIRMADO' && input.purpose!=='status' && input.purpose!=='ack')
          throw fail(404,'Solicitação não encontrada');
        if (pair.estado==='PENDENTE' && pair.expira_aprovacao_em<=time && input.purpose!=='status')
          throw fail(410,'Solicitação expirada');
        if (pair.estado==='CONFIRMADO' && input.purpose==='ack') {
          const ack=db.prepare('SELECT ack_operation_id FROM integracao_pareamento_resgates WHERE pairing_id=?').get(pair.id);
          if (!ack || ack.ack_operation_id!==input.operation_id) throw fail(409,'ACK divergente');
        }
        if (pair.estado==='RESGATADO' && input.purpose==='redeem') {
          const redemption=db.prepare('SELECT * FROM integracao_pareamento_resgates WHERE pairing_id=?').get(pair.id);
          if (!redemption || redemption.operation_id!==input.operation_id ||
              redemption.recuperacao_expira_em<=time) throw fail(410,'Recuperação indisponível');
        }
        const id=randomUUID(), bytes=randomBytes(32);
        db.prepare(`INSERT INTO integracao_pareamento_desafios
          (id,pairing_id,purpose,operation_id,desafio,criado_em,expira_em)
          VALUES(?,?,?,?,?,?,?)`).run(id,pair.id,input.purpose,input.operation_id,bytes,time,time+policy.challengeMs);
        return {challenge_id:id,challenge:bytes.toString('base64url'),expires_at:time+policy.challengeMs};
      });
      return reply.code(201).send(result);
    });
    app.get('/api/agentes/pareamentos/:id/estado', async (req, reply) => {
      if (!asUuid(req.params.id)) return reply.code(404).send({error:'Solicitação não encontrada'});
      const operationId=req.headers['x-avisaqui-pair-operation-id'];
      const challengeId=req.headers['x-avisaqui-pair-challenge-id'];
      const signature=req.headers['x-avisaqui-pair-proof'];
      if (req.headers['x-avisaqui-pair-version']!==PAIR_PROTOCOL ||
          !asUuid(operationId) || !asUuid(challengeId)) return reply.code(400).send({error:'Prova inválida'});
      const row=tx(()=>{
        const pair=select(req.params.id);
        if (!pair) throw fail(404,'Solicitação não encontrada');
        challengeProof(pair,'status',operationId,challengeId,signature);
        if (pair.estado==='PENDENTE' && pair.expira_aprovacao_em<=now()) {
          db.prepare("UPDATE integracao_pareamento_solicitacoes SET estado='EXPIRADO' WHERE id=?").run(pair.id);
          pair.estado='EXPIRADO';
        }
        return {protocol:PAIR_PROTOCOL,state:pair.estado,expires_at:pair.expira_aprovacao_em};
      });
      return reply.send(row);
    });
    app.post('/api/agentes/pareamentos/:id/autorizar', async (req, reply) => {
      const actor=manager(req,reply); if (!actor) return;
      if (!asUuid(req.params.id)) return reply.code(404).send({error:'Solicitação não encontrada'});
      if (!rate('approve:'+req.ip,20,60000) ||
          !rate('approval:'+req.params.id,8,600000)) return reply.code(429).send({error:'Limite excedido'});
      const input=req.body;
      if (!input || !['aprovar','recusar'].includes(input.decisao) ||
          typeof input.codigo !== 'string' || !/^[0-9]{8}$/.test(input.codigo) ||
          (input.decisao==='aprovar' && !textName(input.caixa_nome))) {
        return reply.code(400).send({error:'Dados inválidos'});
      }
      const updated=tx(()=>{
        const pair=select(req.params.id);
        if (!pair) throw fail(404,'Solicitação não encontrada');
        if (pair.estado!=='PENDENTE' || pair.expira_aprovacao_em<=now()) throw fail(409,'Solicitação não disponível');
        if (pair.tentativas_codigo>=8) return {status:429,error:'Limite excedido'};
        if (pair.codigo!==input.codigo) {
          db.prepare('UPDATE integracao_pareamento_solicitacoes SET tentativas_codigo=tentativas_codigo+1 WHERE id=?').run(pair.id);
          audit(actor,pair,'pareamento','recusado_codigo');
          return {status:403,error:'Solicitação não autorizada'};
        }
        const state=input.decisao==='aprovar'?'APROVADO':'RECUSADO';
        db.prepare(`UPDATE integracao_pareamento_solicitacoes SET estado=?,restaurante_id=?,
          aprovado_por=?,aprovado_em=?,recusado_em=?,caixa_nome_aprovado=? WHERE id=? AND estado='PENDENTE'`)
          .run(state,actor.restaurante_id,actor.id,state==='APROVADO'?now():null,
            state==='RECUSADO'?now():null,state==='APROVADO'?input.caixa_nome.trim():null,pair.id);
        audit(actor,pair,'pareamento',state);
        return {state};
      });
      if (updated.status) return reply.code(updated.status).send({error:updated.error});
      return reply.send(updated);
    });
    app.post('/api/agentes/pareamentos/:id/resgatar', async (req, reply) => {
      if (!asUuid(req.params.id)) return reply.code(404).send({error:'Solicitação não encontrada'});
      const input=parseInput(req.body,'redeem');
      const answer=tx(()=>{
        const pair=select(req.params.id);
        if (!pair) throw fail(404,'Solicitação não encontrada');
        challengeProof(pair,'redeem',input.operation_id,input.challenge_id,input.signature);
        const previous=db.prepare('SELECT * FROM integracao_pareamento_resgates WHERE pairing_id=?').get(pair.id);
        if (previous) {
          if (previous.operation_id!==input.operation_id) throw fail(409,'Operação conflitante');
          if (previous.recuperacao_expira_em<=now()) throw fail(410,'Recuperação indisponível');
          return {repeated:true,payload:JSON.parse(previous.envelope_json)};
        }
        if (pair.estado!=='APROVADO' || !pair.restaurante_id) throw fail(409,'Solicitação não aprovada');
        if (pair.expira_aprovacao_em<=now()) throw fail(410,'Solicitação expirada');
        const deviceId=randomUUID(),credential=randomBytes(32).toString('hex'),time=now();
        const envelope=sealCredentialEnvelope({
          pairingId:pair.id,operationId:input.operation_id,deliveryPublicKey:pair.delivery_public_key,
          deviceId,restaurantId:pair.restaurante_id,cashierName:pair.caixa_nome_aprovado,credential
        });
        db.prepare(`INSERT INTO integracao_impressao_dispositivos
          (id,restaurante_id,caixa_nome,criado_em,aprovado_por)
          VALUES(?,?,?,?,?)`).run(deviceId,pair.restaurante_id,pair.caixa_nome_aprovado,time,pair.aprovado_por);
        db.prepare(`INSERT INTO integracao_impressao_chaves
          (id,restaurante_id,hash,criado_em,dispositivo_id) VALUES(?,?,?,?,?)`)
          .run(randomUUID(),pair.restaurante_id,hash(credential),time,deviceId);
        db.prepare(`INSERT INTO integracao_pareamento_resgates
          (pairing_id,operation_id,dispositivo_id,envelope_json,emitido_em,recuperacao_expira_em)
          VALUES(?,?,?,?,?,?)`).run(pair.id,input.operation_id,deviceId,JSON.stringify(envelope),time,time+policy.recoveryMs);
        db.prepare("UPDATE integracao_pareamento_solicitacoes SET estado='RESGATADO' WHERE id=? AND estado='APROVADO'").run(pair.id);
        return {repeated:false,payload:envelope};
      });
      return reply.code(answer.repeated?200:201).send(answer.payload);
    });
    app.post('/api/agentes/pareamentos/:id/confirmar', async (req, reply) => {
      if (!asUuid(req.params.id)) return reply.code(404).send({error:'Solicitação não encontrada'});
      const input=parseInput(req.body,'ack');
      const output=tx(()=>{
        const pair=select(req.params.id);
        if (!pair) throw fail(404,'Solicitação não encontrada');
        challengeProof(pair,'ack',input.ack_operation_id,input.challenge_id,input.signature);
        const res=db.prepare('SELECT * FROM integracao_pareamento_resgates WHERE pairing_id=?').get(pair.id);
        if (!res || res.operation_id!==input.operation_id) throw fail(409,'Resgate divergente');
        if (res.ack_operation_id && res.ack_operation_id!==input.ack_operation_id) throw fail(409,'ACK divergente');
        if (!res.ack_operation_id) {
          db.prepare('UPDATE integracao_pareamento_resgates SET ack_operation_id=?,ack_em=? WHERE pairing_id=?')
            .run(input.ack_operation_id,now(),pair.id);
          db.prepare("UPDATE integracao_pareamento_solicitacoes SET estado='CONFIRMADO' WHERE id=? AND estado='RESGATADO'").run(pair.id);
        }
        return {state:'CONFIRMADO',dispositivo_id:res.dispositivo_id};
      });
      return reply.send(output);
    });
  };
}
