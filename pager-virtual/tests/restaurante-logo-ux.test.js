import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
const source = path => readFileSync(new URL('../' + path, import.meta.url), 'utf8');
test('restaurante mantém logo opcional na migração aditiva', () => {
  const db=source('src/db.js');
  assert.match(db,/PRAGMA table_info\(restaurantes\)/);
  assert.match(db,/ALTER TABLE restaurantes ADD COLUMN logo_url TEXT/);
});
test('Master lista e edita logo sem alterar outros restaurantes', () => {
  const api=source('src/admin.js');
  assert.match(api,/SELECT id, nome, slug, ativo, logo_url FROM restaurantes/);
  assert.match(api,/UPDATE restaurantes SET logo_url = \? WHERE id = \?/);
  assert.match(api,/mustBe\(request, reply, \['master'\]\)/);
  const ui=source('src/public/admin.html');
  assert.match(ui,/restaurantLogo\(rest.logo_url,rest.nome\)/);
  assert.match(ui,/restaurante_logo_url/);
});
test('KDS e impressão exibem logo do restaurante autenticado', () => {
  const auth=source('src/auth.js');
  assert.match(auth,/AS restaurante_logo_url/);
  for (const page of ['src/public/kds.html','src/public/impressao.html']) {
    const html=source(page);
    assert.match(html,/restaurante_logo_url/);
    assert.match(html,/referrerPolicy='no-referrer'/);
  }
  assert.match(source('src/public/kds.html'),/avisaqui-marca-transparente\.svg/);
});

test('Master usa modal em vez de prompt para editar logo', () => {
  const html=source('src/public/admin.html');
  assert.match(html,/setAttribute\('role','dialog'\)/);
  assert.match(html,/close\.setAttribute\('aria-label','Fechar'\)/);
  assert.match(html,/cancel\.textContent='Cancelar'/);
  assert.match(html,/event\.key==='Escape'/);
  assert.doesNotMatch(html,/prompt\('URL HTTPS do logo/);
});
test('KDS mantém marca e um único botão Sair no cabeçalho', () => {
  const html=source('src/public/kds.html');
  const header=html.match(/<header class="kds-header">[\s\S]*?<\/header>/)?.[0] || '';
  assert.match(header,/avisaqui-marca-transparente\.svg/);
  assert.equal((header.match(/id="btn-logout"/g)||[]).length,1);
  assert.match(header,/id="restaurant-context"/);
});
