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
});
test('primeiro acesso preserva API e marcador legado do log',()=>{
 const s=page('setup.html');
 assert.ok(s.includes('/api/setup/master') && s.includes('BIPOU PRIMEIRO ACESSO'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg') && s.includes('<h1>Primeiro acesso</h1>'));
});
test('KDS preserva impressão e controles da operação',()=>{
 const s=page('kds.html');
 assert.ok(s.includes('id="btn-add-manual-order"') && s.includes('id="printing-integration-link"'));
 assert.ok(s.includes('<h1>Pedidos em atendimento</h1>'));
});
test('gerência preserva permissões e navegação',()=>{
 const s=page('admin.html');
 assert.ok(s.includes('id="manager-area"') && s.includes('data-manager-tab="terminals"'));
 assert.ok(s.includes('avisaqui-marca-transparente.svg'));
});
test('clipboard tem fallback sem afirmar cópia quando API falha',()=>{
 const s=page('impressao.html');
 assert.ok(s.includes('navigator.clipboard.writeText(token)'));
 assert.ok(s.includes('selection.addRange(range)'));
 assert.ok(s.includes('Pressione Ctrl+C'));
});
