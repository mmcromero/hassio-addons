// Contratos de implementação do protótipo ux-master-v2 e MATRIZ-UX-AVISAQUI.md.
// Não substitui teste em navegador nem homologa a apresentação visual.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = path => readFileSync(new URL('../'+path, import.meta.url), 'utf8');
const admin=source('src/public/admin.html');
const kds=source('src/public/kds.html');
const client=source('src/public/cliente.html');
const printing=source('src/public/impressao.html');
const pairing=source('src/pairing/backend/assets/autorizar-pair-lab.html');
const pedidos=source('src/routes/pedidos.js');
const auth=source('src/auth.js');
const download=source('src/windows-download.js');
const windows=source('scripts/impressao_windows/janela_pair_v1.py');

test('telas de sessão: marca Avisaqui e Sair na primeira faixa',()=>{
 assert.match(admin, /class="admin-session-top"[\s\S]*?id="logout"/);
 assert.match(kds, /class="kds-brand-bar"[\s\S]*?id="btn-logout"/);
 assert.match(printing, /class="brand-header"[\s\S]*?id="logout"/);
 assert.match(pairing, /class="brand-top"[\s\S]*?id="logout"/);
});
test('restaurante: nome, logo, papel e identificador por sessão real',()=>{
 assert.match(auth,/AS restaurante_logo_url/);
 assert.match(auth,/AS restaurante_slug/);
 assert.match(admin,/restaurantLogo\(user\.restaurante_logo_url,restaurantName\)/);
 assert.match(admin,/user\.restaurante_slug/);
 assert.match(kds,/img\.src=user\.restaurante_logo_url/);
 assert.match(kds,/user\.restaurante_slug/);
 assert.match(printing,/user\.restaurante_slug/);
 assert.match(pairing,/user\.restaurante_slug/);
 assert.match(pairing,/user\.restaurante_logo_url/);
});
test('Master: lista mostra logo e possui modal para editar URL real',()=>{
 assert.match(admin,/restaurantLogo\(rest\.logo_url,rest\.nome\)/);
 assert.match(admin,/logoButton\.textContent='Editar logo'/);
 assert.match(admin,/setAttribute\('role','dialog'\)/);
 assert.doesNotMatch(admin,/prompt\('URL HTTPS do logo/);
});
test('Master e gerente: formulários em modais com fechar e cancelar',()=>{
 assert.match(admin,/createAdminDialog\(cards\[0\],newButton/);
 assert.match(admin,/createAdminDialog\(cards\[1\],managerButton/);
 assert.match(admin,/window\.terminalDialog/);
 assert.match(admin,/cancel\.addEventListener\('click',dismiss\)/);
 assert.match(admin,/dialog\.addEventListener\('cancel'/);
});
test('KDS: modais de pedido, numeração e QR mantêm X e Cancelar',()=>{
 for(const id of ['manual-x','sequence-x','qr-x'])assert.ok(kds.includes('id="'+id+'"'));
 assert.match(kds,/event\.key==='Escape'/);
 assert.match(kds,/snapshotSequence=sequenceOriginal\(\)/);
 assert.match(kds,/id="btn-print-qr"/);
});
test('cliente: identidade real do restaurante vem do token, sem Burger House',()=>{
 assert.doesNotMatch(client,/Burger House/);
 assert.match(client,/showRestaurantIdentity\(data\.restaurante_nome,data\.restaurante_logo_url\)/);
 assert.match(client,/id="client-restaurant-context"/);
 assert.match(pedidos,/r\.nome AS restaurante_nome/);
 assert.match(pedidos,/r\.logo_url AS restaurante_logo_url/);
 assert.match(client,/id="games-open"/);
 assert.match(client,/id="btn-sound-test"/);
});
test('Impressão: QR Windows e gestão por API sem cadastro manual de chaves',()=>{
 assert.match(printing,/id="pairing-guide"/);
 assert.match(printing,/pairingGuide\.hidden=false/);
 assert.match(printing,/api\('api\/agentes\/dispositivos'\)/);
 assert.match(printing,/function askComputerName\(current,trigger\)/);
 assert.match(printing,/function confirmRemoval\(title,message,trigger\)/);
 assert.doesNotMatch(printing,/prompt\('Nome deste computador/);
 assert.match(printing,/api\/windows\/download\/status/);
 assert.match(printing,/id="windows-release-metadata"/);
 assert.match(download,/file_updated_at:/);
 assert.doesNotMatch(printing,/api\/integracoes\/impressao\/chave(?:s)?/);
 assert.doesNotMatch(printing,/id="generate"|id="token"|id="copy"|Credenciais anteriores/);
});
test('Windows: QR, código, autorização e confirmação ficam no PC/gerente',()=>{
 assert.match(windows,/import qrcode/);
 assert.match(windows,/self\.code/);
 assert.match(windows,/self\.manager_url/);
 assert.match(windows,/Iniciar ou retomar pareamento/);
 assert.match(windows,/PairV1Controller/);
});
test('scripts inline de todas as telas realmente compilam',()=>{
 for(const path of [
  'src/public/admin.html','src/public/kds.html','src/public/cliente.html',
  'src/public/impressao.html','src/public/login.html','src/public/setup.html',
  'src/public/landing.html','src/pairing/backend/assets/autorizar-pair-lab.html'
 ]){
  const html=source(path);
  const scripts=[...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  assert.ok(scripts.length>0,path);
  for(const [,code] of scripts)assert.doesNotThrow(()=>new Function(code),path);
  const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(x=>x[1]);
  assert.equal(new Set(ids).size,ids.length,'IDs duplicados em '+path);
 }
});
