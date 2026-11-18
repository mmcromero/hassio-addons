import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';

const text=path=>readFileSync(new URL('../'+path,import.meta.url),'utf8');

test('tela da integração não oferece cadastro manual de credenciais',()=>{
 const html=text('src/public/impressao.html');
 assert.match(html,/id="start-pairing"/);
 assert.match(html,/id="windows-download-button"/);
 assert.match(html,/api\/windows\/download\/status/);
 assert.doesNotMatch(html,/id="generate"|id="token"|id="copy"|Credenciais anteriores e migração/);
 assert.doesNotMatch(html,/api\/integracoes\/impressao\/chave(?:s)?/);
});

test('agente inicia somente com identidade pair-v1 protegida após ACK',()=>{
 const loader=text('scripts/impressao_windows/credencial_agente.py');
 const agent=text('scripts/impressao_windows/agente.py');
 assert.match(loader,/dispositivo\.protected\.json/);
 assert.match(loader,/ack_pending/);
 assert.match(loader,/PairV1Flow\._valid_active/);
 assert.match(loader,/record\['credential'\]/);
 assert.doesNotMatch(loader,/config\.json|return.*legado|configuracao legada/);
 assert.doesNotMatch(agent,/--configurar|def configure\(/);
 assert.match(agent,/publish_pending\(db,cfg,tls_context\)/);
});

test('API não emite chave manual e conserva envio de pedidos por credencial do pareamento',()=>{
 const routes=text('src/routes/integracao-impressao.js');
 const pair=text('src/pairing/backend/routes-lab.js');
 assert.doesNotMatch(routes,/app\.post\('\/api\/integracoes\/impressao\/chave'/);
 assert.doesNotMatch(routes,/app\.get\('\/api\/integracoes\/impressao\/chaves'/);
 assert.match(routes,/app\.post\('\/api\/integracoes\/impressao\/pedidos'/);
 assert.match(routes,/x-avisaqui-agent-key/);
 assert.match(pair,/integracao_impressao_chaves/);
 assert.match(pair,/dispositivo_id/);
});

test('ZIP distribui scripts QR e agente sem instalador/legado',()=>{
 const builder=text('scripts/ci/build-windows-zip.py');
 const cmd=text('scripts/impressao_windows/INICIAR_PAREAMENTO.cmd');
 assert.match(cmd,/py -3 janela_pair_v1\.py/);
 for(const name of ['credencial_agente.py','janela_pair_v1.py','agente.py',
    'INICIAR_PAREAMENTO.cmd','INICIAR_AGENTE.cmd','requirements-windows.txt']){
   assert.ok(builder.includes(name), name);
 }
 assert.doesNotMatch(builder,/'CONFIGURAR_AGENTE\.cmd'|'pareamento\.py'|'janela_pareamento\.py'/);
 assert.doesNotMatch(builder,/\.exe'/i);
});
