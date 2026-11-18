import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const root=new URL('../src/public/',import.meta.url);
const page=(file)=>readFileSync(new URL(file,root),'utf8');
test('marca oficial transparente não desenha fundo',()=>{
 const svg=page('avisaqui-marca-transparente.svg');
 assert.ok(svg.includes('Avisaqui<tspan'));
 assert.ok(!svg.includes('id="background"'));
});
test('cliente preserva controles e integra identidade visual',()=>{
 const s=page('cliente.html');
 assert.ok(s.includes('id="order-num"') && s.includes('id="status-text"'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg') && s.includes('<h1>Seu pedido</h1>'));
 assert.ok(!s.includes('<h1>Pager Virtual</h1>'));
});
test('login preserva autenticação e marca',()=>{
 const s=page('login.html');
 assert.ok(s.includes('id="login-form"') && s.includes('/api/auth/login'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg') && s.includes('<h1>Entrar</h1>'));
 // Sem JavaScript, o browser não pode enviar campos de senha por GET na URL.
 assert.match(s, /<form\b[^>]*\bid="login-form"[^>]*\bmethod="post"/i);
 // O fluxo com JavaScript continua fazendo POST autenticado para a API local.
 assert.match(s, /fetch\(basePath \+ '\/api\/auth\/login', \{/);
 assert.ok(s.includes("method: 'POST', credentials: 'same-origin'"));
});
test('primeiro acesso preserva API e marcador legado do log',()=>{
 const s=page('setup.html');
 assert.ok(s.includes('/api/setup/master') && s.includes('BIPOU PRIMEIRO ACESSO'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg') && s.includes('<h1>Primeiro acesso</h1>'));
});
test('KDS preserva impressão e controles da operação',()=>{
 const s=page('kds.html');
 assert.ok(s.includes('id="btn-add-manual-order"') && s.includes('id="printing-integration-link"'));
 assert.match(s, /<h1\b[^>]*>\s*Pedidos em atendimento\s*<\/h1>/);
});
test('gerência preserva permissões e navegação',()=>{
 const s=page('admin.html');
 assert.ok(s.includes('id="manager-area"') && s.includes('data-manager-tab="terminals"'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg'));
});
test('impressão oferece QR e download sem copiar token manual',()=>{
 const s=page('impressao.html');
 assert.ok(s.includes('id="start-pairing"') && s.includes('id="windows-download-button"'));
 assert.ok(!s.includes('id="generate"') && !s.includes('id="token"'));
 assert.ok(!s.includes('navigator.clipboard.writeText(token)'));
});

test('gerente tem acesso visível à impressão e identidade do estabelecimento',()=>{
 const admin=page('admin.html'), kds=page('kds.html');
 assert.match(admin,/<a[^>]*href="\.\/impressao\.html"[^>]*id="manager-print-link"/);
 assert.ok(admin.includes('id="restaurant-identity"'));
 assert.ok(admin.includes("restaurantLogo(user.restaurante_logo_url,restaurantName)"));
 assert.ok(admin.includes('user.restaurante_slug'));
 assert.ok(admin.includes("restaurantIdentity.replaceChildren("));
 assert.ok(admin.includes("printLink.href='./impressao.html'"));
 assert.ok(kds.includes('id="restaurant-context"'));
 assert.ok(kds.includes("img.src=user.restaurante_logo_url"));
 assert.ok(kds.includes("meta.textContent="));
 assert.ok(kds.includes('user.restaurante_slug'));
 assert.ok(kds.includes('id="printing-integration-link"'));
});

test('contexto de sessão fornece nome seguro sem consulta livre a outro restaurante',()=>{
 const s=readFileSync(new URL('../src/auth.js',import.meta.url),'utf8');
 assert.ok(s.includes('ELSE r.nome END AS restaurante_nome'));
 assert.ok(s.includes('CASE WHEN mr.ativo = 1 THEN mr.nome ELSE NULL END'));
 assert.ok(s.includes('return user;'));
});
