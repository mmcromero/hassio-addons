import test from 'node:test';
import assert from 'node:assert/strict';
import Fastify from 'fastify';
import { spawn, spawnSync } from 'node:child_process';
import { createHash, randomBytes, randomUUID } from 'node:crypto';
import { mkdtempSync, mkdirSync, readFileSync, existsSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { createServer } from 'node:net';
import https from 'node:https';

// Ensaio de proxy real NGINX com TLS assinado pela CA *exclusiva deste teste*.
// O módulo pair-v1 permanece opt-in e fora de src/server.js.
async function freePort() {
  return new Promise((resolve,reject)=>{
    const srv=createServer();
    srv.once('error',reject);
    srv.listen(0,'127.0.0.1',()=>{const {port}=srv.address();srv.close(()=>resolve(port))});
  });
}
async function requestTls({port,ca,servername='pager.test',method='GET',path='/api/agentes/dispositivos',headers={},body}) {
  const data=body===undefined?null:JSON.stringify(body);
  return new Promise((resolve,reject)=>{
    const req=https.request({
      hostname:'127.0.0.1',port,servername,method,path,
      ca,rejectUnauthorized:true,timeout:8000,
      headers:{Host:'pager.test:'+port,...(data?{'Content-Type':'application/json','Content-Length':Buffer.byteLength(data)}:{}),...headers}
    },res=>{
      let text='';
      res.setEncoding('utf8');
      res.on('data',x=>text+=x);
      res.on('end',()=>{let body=text;try{body=text?JSON.parse(text):null}catch{}resolve({status:res.statusCode,body,headers:res.headers})});
    });
    req.on('error',reject);
    req.on('timeout',()=>req.destroy(Error('HTTPS timeout')));
    req.end(data);
  });
}
async function waitNginx(port,ca,child) {
  const deadline=Date.now()+9000;
  while(Date.now()<deadline){
    if(child.exitCode!==null) throw Error('nginx exited before readiness: '+child.exitCode);
    try{
      const response=await requestTls({port,ca,headers:{Origin:'https://pager.test:'+port}});
      if(response.status===401)return;
    }catch{}
    await new Promise(r=>setTimeout(r,80));
  }
  throw Error('NGINX HTTPS not ready');
}
test('NGINX HTTPS observa cookie REAL, CSP ausente e prefixo /avisaqui', {timeout:45000}, async()=>{
  const dir=mkdtempSync(join(tmpdir(),'avisaqui-pair-nginx-'));
  mkdirSync(join(dir,'logs'));
  // NGINX sem root no Codespaces: diretórios temporários pertencem ao ensaio.
  for (const name of ['client-body','proxy-temp','fastcgi-temp','uwsgi-temp','scgi-temp'])
    mkdirSync(join(dir,name));
  let db,app,proxy;
  const prevData=process.env.DATA_PATH, prevPublic=process.env.PUBLIC_URL;
  try{
    const openssl=spawnSync('openssl',['req','-x509','-newkey','rsa:2048','-sha256','-nodes',
      '-keyout',join(dir,'key.pem'),'-out',join(dir,'cert.pem'),'-days','1',
      '-subj','/CN=pager.test','-addext','subjectAltName=DNS:pager.test'],{
      encoding:'utf8',timeout:10000
    });
    assert.equal(openssl.status,0,'openssl unavailable: '+(openssl.stderr||''));
    const ca=readFileSync(join(dir,'cert.pem'));
    const port=await freePort();
    const origin='https://pager.test:'+port;
    process.env.DATA_PATH=join(dir,'db');
    process.env.PUBLIC_URL=origin;
    // Import dinâmico: auth.js lê PUBLIC_URL na primeira importação deste worker.
    const {default:database}=await import('../src/db.js'); db=database;
    const {buildPairV1LabRoutes}=await import('../src/pairing/backend/routes-lab.js');
    const {managerFromAvisaquiSession}=await import('../src/pairing/backend/session-adapter.js');
    const {authRoutes,passwordHash}=await import('../src/auth.js');
    const now=Date.now(),user='gerente-lab',restaurant='rest-lab';
    db.prepare('INSERT INTO restaurantes(id,nome,slug,ativo,created_at) VALUES(?,?,?,?,?)')
      .run(restaurant,'Restaurante teste','rest-lab',1,now);
    db.prepare(`INSERT INTO usuarios
      (id,restaurante_id,nome,login,senha_hash,papel,ativo,criado_em,atualizado_em)
      VALUES(?,?,?,?,?,?,1,?,?)`).run(user,restaurant,'Gerente','gerente-lab',await passwordHash('senha-de-lab-123456'),'gerente',now,now);
    const token=randomBytes(32).toString('hex');
    db.prepare('INSERT INTO sessoes(id,usuario_id,token_hash,criado_em,expira_em) VALUES(?,?,?,?,?)')
      .run(randomUUID(),user,createHash('sha256').update(token).digest('hex'),now,now+3600000);
    db.exec(`CREATE TABLE integracao_impressao_chaves
      (id TEXT PRIMARY KEY,restaurante_id TEXT NOT NULL,hash TEXT NOT NULL UNIQUE,
      criado_em INTEGER NOT NULL,revogado_em INTEGER,
      FOREIGN KEY(restaurante_id) REFERENCES restaurantes(id))`);
    app=Fastify({logger:false});
    app.register(authRoutes);
    app.register(buildPairV1LabRoutes({
      db,publicOrigin:origin,managerFromRequest:managerFromAvisaquiSession,
      policy:{approvalMs:300000,challengeMs:60000,recoveryMs:3600000}
    }));
    await app.listen({host:'127.0.0.1',port:0});
    const backendPort=app.server.address().port;
    // Proxy não confia em Host arbitrário. Não lê X-Forwarded de clientes como autoridade.
    const conf=`worker_processes 1;
error_log ${join(dir,'logs','error.log')};
pid ${join(dir,'nginx.pid')};
events { worker_connections 64; }
http {
  access_log off;
  client_body_temp_path ${join(dir,'client-body')};
  proxy_temp_path ${join(dir,'proxy-temp')};
  fastcgi_temp_path ${join(dir,'fastcgi-temp')};
  uwsgi_temp_path ${join(dir,'uwsgi-temp')};
  scgi_temp_path ${join(dir,'scgi-temp')};
  server {
    listen 127.0.0.1:${port} ssl;
    server_name pager.test;
    ssl_certificate ${join(dir,'cert.pem')};
    ssl_certificate_key ${join(dir,'key.pem')};
    if ($host != pager.test) { return 421; }
    location /avisaqui/ {
      proxy_pass http://127.0.0.1:${backendPort}/;
      proxy_set_header X-Forwarded-Prefix /avisaqui;
      proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Connection close;
    }
    location / {
      proxy_pass http://127.0.0.1:${backendPort};
      proxy_set_header Host $http_host;
      proxy_set_header X-Forwarded-Host $host;
      proxy_set_header X-Forwarded-Proto https;
      proxy_set_header Connection close;
      proxy_read_timeout 5s;
    }
  }
}`;
    const config=join(dir,'nginx.conf');
    writeFileSync(config,conf);
    // Validar sintaxe do NGINX antes do start e preservar diagnóstico real.
    const check=spawnSync('nginx',['-p',dir+'/','-c',config,'-t'],{
      encoding:'utf8',timeout:10000
    });
    assert.equal(check.status,0,
      'NGINX configuração inválida: '+(check.stderr||check.stdout||'sem diagnóstico').slice(0,1800));
    proxy=spawn('nginx',['-p',dir+'/','-c',config,'-g','daemon off;'],{stdio:['ignore','ignore','pipe']});
    let nginxStderr='';
    proxy.stderr.on('data',chunk=>{nginxStderr+=chunk.toString().slice(0,1400)});
    try { await waitNginx(port,ca,proxy); }
    catch (error) {
      const errorPath=join(dir,'logs','error.log');
      const log=existsSync(errorPath)?readFileSync(errorPath,'utf8'):'arquivo de erro não criado';
      throw new Error('Falha ao iniciar NGINX de laboratório: '+error.message+
        '\\nSTDERR: '+nginxStderr.slice(0,1400)+'\\nERROR_LOG: '+log.slice(-1800));
    }
    const cookie='bipou_session='+token;
    const good={port,ca,headers:{Cookie:cookie}};
    assert.equal((await requestTls(good)).status,200,'GET sem Origin permitido');
    const result=await requestTls(good);
    assert.deepEqual(result.body,[]);
    assert.equal((await requestTls({port,ca})).status,401,'GET sem sessão recusado');
    assert.equal((await requestTls({port,ca,headers:{Cookie:cookie,Origin:'https://malicioso.test'}})).status,403);
    assert.equal((await requestTls({port,ca,headers:{Cookie:cookie,'Sec-Fetch-Site':'cross-site'}})).status,403);
    assert.equal((await requestTls({port,ca,headers:{Cookie:cookie,Host:'evil.test'}})).status,421);
    assert.equal((await requestTls({port,ca,headers:{Cookie:cookie,'X-Forwarded-Host':'evil.test','X-Forwarded-Proto':'http'}})).status,200);
    const target='/api/agentes/dispositivos/'+randomUUID();
    assert.equal((await requestTls({...good,path:target,method:'PATCH',body:{caixa_nome:'novo'}})).status,403,'escrita sem Origin bloqueada');
    assert.equal((await requestTls({...good,path:target,method:'PATCH',body:{caixa_nome:'novo'},headers:{Cookie:cookie,Origin:origin}})).status,404,'escrita autorizada passa ACL');
    assert.equal((await requestTls({...good,path:target,method:'PATCH',body:{caixa_nome:'novo'},headers:{Cookie:cookie,Origin:'https://evil.test'}})).status,403);
    assert.equal((await requestTls({...good,path:target,method:'PATCH',body:{caixa_nome:'novo'},headers:{Cookie:cookie,Origin:origin,'Sec-Fetch-Site':'cross-site'}})).status,403);
    // Duas CAs PEM válidas distintas: confiança errada deve falhar na cadeia,
    // não por falha de parse de chave privada.
    const wrongCaResult=spawnSync('openssl',['req','-x509','-newkey','rsa:2048',
      '-sha256','-nodes','-keyout',join(dir,'untrusted-key.pem'),
      '-out',join(dir,'untrusted-ca.pem'),'-days','1',
      '-subj','/CN=untrusted.test','-addext','subjectAltName=DNS:untrusted.test'],{
      encoding:'utf8',timeout:10000
    });
    assert.equal(wrongCaResult.status,0,'CA de teste independente inválida');
    const otherCa=readFileSync(join(dir,'untrusted-ca.pem'));
    assert.match(otherCa.toString(),/BEGIN CERTIFICATE/);
    await assert.rejects(
      requestTls({port,ca:otherCa}),
      err=>['DEPTH_ZERO_SELF_SIGNED_CERT','UNABLE_TO_VERIFY_LEAF_SIGNATURE',
        'SELF_SIGNED_CERT_IN_CHAIN','UNABLE_TO_GET_ISSUER_CERT_LOCALLY'].includes(err?.code),
      'Certificado válido de outra CA deve ser recusado pela cadeia'
    );
    // Uma CA correta não autoriza nome DNS divergente.
    await assert.rejects(
      requestTls({port,ca,servername:'impostor.test'}),
      err=>err?.code==='ERR_TLS_CERT_ALTNAME_INVALID',
      'SNI/hostname divergente deve ser recusado'
    );
    // Regressão de Segurança: Origin correto não pode anular Fetch Metadata hostil,
    // inclusive no endpoint real de login, por trás do NGINX HTTPS.
    for (const metadata of [
      {'Sec-Fetch-Site':'cross-site'},
      {'Sec-Fetch-Mode':'no-cors'}
    ]) {
      const deniedLogin=await requestTls({
        port,ca,method:'POST',path:'/avisaqui/api/auth/login',
        headers:{Origin:origin,...metadata},
        body:{login:'gerente-lab',senha:'senha-de-lab-123456'}
      });
      assert.equal(deniedLogin.status,403,'login com Fetch Metadata hostil recusado');
      assert.equal(deniedLogin.headers['set-cookie'],undefined,
        'login recusado não emite cookie de sessão');
    }
    // Diagnóstico de cabeçalhos EFETIVOS, nunca inferidos do proxy.
    const login=await requestTls({port,ca,method:'POST',path:'/avisaqui/api/auth/login',
      headers:{Origin:origin},body:{login:'gerente-lab',senha:'senha-de-lab-123456'}});
    assert.equal(login.status,200,'login real via proxy e prefixo');
    const issued=login.headers['set-cookie'];
    assert.equal(Array.isArray(issued),true,'servidor emite cookie de sessão');
    const cookieValue=issued[0];
    assert.match(cookieValue,/^bipou_session=[a-f0-9]{64};/);
    assert.match(cookieValue,/; Secure(?:;|$)/);
    assert.match(cookieValue,/; HttpOnly(?:;|$)/);
    assert.match(cookieValue,/; SameSite=Strict(?:;|$)/);
    // OBSERVAÇÃO CONTRATUAL: a implementação atual em auth.js usa Path=/,
    // não /avisaqui; registrar lacuna sem mascarar como cumprimento.
    assert.match(cookieValue,/; Path=\/(?:;|$)/);
    assert.equal(cookieValue.includes('Path=/avisaqui'),false);
    const issuedCookie=cookieValue.split(';')[0];
    const current=await requestTls({port,ca,path:'/avisaqui/api/agentes/dispositivos',
      headers:{Cookie:issuedCookie}});
    assert.equal(current.status,200,'cookie realmente emitido autentica pelo prefixo');
    const redirect=await requestTls({port,ca,path:'/avisaqui/api/auth/me',
      headers:{Cookie:issuedCookie}});
    assert.equal(redirect.status,200);
    // CSP não é inventada: ausência em fixture deve ser registrada como lacuna.
    assert.equal(login.headers['content-security-policy'],undefined,
      'CSP não observada nesta fixture de Fastify');
    assert.equal(current.headers['content-security-policy'],undefined);
    assert.equal(current.headers['x-content-type-options'],undefined);
    assert.equal(current.headers['strict-transport-security'],undefined);
    // Apenas metadados não sensíveis: não imprimir cookie/token no CI.
    console.log('PAIR_LAB_HEADERS '+JSON.stringify({
      cookie_emitted:true,cookie_path:'/',
      cookie_secure:true,cookie_httponly:true,cookie_samesite:'Strict',
      csp:login.headers['content-security-policy']??null,
      hsts:login.headers['strict-transport-security']??null,
      x_content_type_options:login.headers['x-content-type-options']??null,
      prefix_api_auth_status:current.status
    }));
    const missing=await requestTls({port,ca,path:'/avisaqui/nao-existe'});
    assert.equal(missing.status,404);
    const badHost=await requestTls({port,ca,path:'/avisaqui/api/auth/me',
      headers:{Host:'invalid.test'}});
    assert.equal(badHost.status,421);
    // Sem endpoint público: apenas loopback e certificado de laboratório.
    assert.equal(db.prepare('SELECT COUNT(*) AS n FROM integracao_pareamento_solicitacoes').get().n,0);
  }finally{
    if(proxy){proxy.kill('SIGTERM');}
    if(app)await app.close();
    if(db)db.close();
    if(prevData===undefined)delete process.env.DATA_PATH;else process.env.DATA_PATH=prevData;
    if(prevPublic===undefined)delete process.env.PUBLIC_URL;else process.env.PUBLIC_URL=prevPublic;
    rmSync(dir,{recursive:true,force:true});
  }
});
