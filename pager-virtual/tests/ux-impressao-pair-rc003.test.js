import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const page=readFileSync(new URL('../src/public/impressao.html',import.meta.url),'utf8');
const routes=readFileSync(new URL('../src/pairing/backend/routes-lab.js',import.meta.url),'utf8');

test('impressão mostra painel de computadores vinculado à API real',()=>{
 assert.match(page,/id="devices"/);
 assert.match(page,/id="refresh-devices"/);
 assert.match(page,/api\('api\/agentes\/dispositivos'\)/);
 assert.match(routes,/app\.get\('\/api\/agentes\/dispositivos'/);
});

test('ações nome e revogação usam contratos reais e confirmação explícita',()=>{
 assert.match(page,/method:'PATCH',body:JSON\.stringify\(\{caixa_nome:trimmed\}\)/);
 assert.match(page,/method:'DELETE',body:JSON\.stringify\(\{confirmar:true\}\)/);
 assert.match(page,/Esta ação não pode ser desfeita/);
 assert.match(routes,/app\.patch\('\/api\/agentes\/dispositivos\/:id'/);
 assert.match(routes,/app\.delete\('\/api\/agentes\/dispositivos\/:id'/);
 assert.match(routes,/req\.body\?\.confirmar !== true/);
});

test('UI não inventa online e não expõe credenciais de pareamento',()=>{
 assert.match(page,/Sem comunicação registrada/);
 assert.match(page,/O pareamento QR ainda não está disponível neste servidor/);
 assert.doesNotMatch(page,/status_online|device\.token|device\.credential/);
});

test('script JavaScript da página compila',()=>{
 const scripts=[...page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)];
 assert.equal(scripts.length,1);
 assert.doesNotThrow(()=>new Function(scripts[0][1]));
});

test('recebimentos ficam ocultos e sem polling antes do ACK do primeiro computador',()=>{
 assert.match(page,/<section[^>]*id="receipts" hidden>/);
 assert.match(page,/let receiptsEnabled=false;/);
 assert.match(page,/if\(!receiptsEnabled\)return;/);
 assert.match(page,/setReceiptsEnabled\(linkedCount>0\)/);
 assert.match(page,/device\.confirmado_em/);
 assert.match(page,/setInterval\(\(\)=>\{if\(receiptsEnabled\)void load\(\);\},10000\)/);
 assert.doesNotMatch(page,/\);load\(\);loadDevices\(\);setInterval\(load,10000\)/);
});
