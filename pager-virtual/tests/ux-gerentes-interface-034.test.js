import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html=readFileSync(new URL('../src/public/admin.html',import.meta.url),'utf8');
const backend=readFileSync(new URL('../src/admin-gerentes.js',import.meta.url),'utf8');

test('F13: Master tem acesso contextual à lista de gerentes',()=>{
  assert.match(html,/manage\.textContent='Gerenciar gerentes'/);
  assert.match(html,/manageRestaurantManagers\(rest,manage\)/);
  assert.match(html,/const managers=await api\(managerUrl\)/);
  assert.match(backend,/app\.get\('\/api\/admin\/restaurantes\/:restauranteId\/gerentes'/);
  assert.match(html,/await post\(contextUrl\+encodeURIComponent\(rest\.id\),\{\}\)/);
});

test('F15: redefinição usa senha atual do Master, confirmação e bloqueio de repetição',()=>{
  assert.match(html,/senha_master_atual:masterPassword\.value/);
  assert.match(html,/if\(busy\|\|save\.disabled\)return/);
  assert.match(html,/confirm\('Redefinir a senha de '/);
  assert.match(html,/masterPassword\.value='';busy=false/);
  assert.match(backend,/passwordMatches\(body\.senha_master_atual/);
  assert.match(backend,/UPDATE sessoes SET revogado_em/);
});

test('F13/F15: modal dispõe de saída segura e contexto restaurado',()=>{
  assert.match(html,/dialog\.addEventListener\('cancel',event=>\{event\.preventDefault\(\);void dismiss\(\);\}\)/);
  assert.match(html,/await restoreContext\(\);dialog\.close\(\)/);
  assert.match(html,/if\(unsaved\(\)&&!confirm/);
  assert.match(html,/try\{await refreshManagers\(\);state\.textContent='Senha redefinida/);
  assert.match(backend,/INSERT INTO auditoria_reset_gerente/);
});

test('F13: atualização manual trata erro e libera controles',()=>{
  assert.match(html,/refresh\.textContent='Atualizar lista'/);
  assert.match(html,/if\(unsaved\(\)&&!confirm\('Descartar alterações não salvas e atualizar a lista\?'\)\)return/);
  assert.match(html,/state\.textContent='Não foi possível atualizar gerentes: '\+error\.message/);
  assert.match(html,/finally\{busy=false;refresh\.disabled=false;close\.disabled=false;done\.disabled=false;\}/);
  assert.match(html,/list\.replaceChildren\(\);unsaved=\(\)=>false/);
});

test('F13: consulta falha não apaga a lista nem campos antes de resposta válida',()=>{
  const start=html.indexOf('async function refreshManagers(){');
  const end=html.indexOf('for(const item of managers)',start);
  assert.ok(start>=0 && end>start);
  const body=html.slice(start,end);
  const call=body.indexOf('const managers=await api(managerUrl)');
  const guard=body.indexOf("if(!Array.isArray(managers))throw Error('Lista de gerentes inválida')");
  const clear=body.indexOf('list.replaceChildren();unsaved=()=>false');
  assert.ok(call>=0 && guard>call && clear>guard,
    'a lista só deve ser substituída depois que a API retornar dados válidos');
});
