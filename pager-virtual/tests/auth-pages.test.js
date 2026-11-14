import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { Script } from 'node:vm';

for (const page of ['setup', 'login', 'admin', 'kds', 'cliente']) {
  test(page + ' possui script JavaScript válido', () => {
    const html = readFileSync(new URL('../src/public/' + page + '.html', import.meta.url), 'utf8');
    const inline = html.split('<script>').slice(1).map(x => x.split('</script>')[0]);
    assert.ok(inline.length, 'Página precisa conter JavaScript');
    for (const code of inline) assert.doesNotThrow(() => new Script(code, { filename: page + '.html' }));
  });
}
test('login envia credenciais somente ao endpoint de sessão', () => {
  const html = readFileSync(new URL('../src/public/login.html', import.meta.url), 'utf8');
  assert.match(html, /\/api\/auth\/login/);
  assert.doesNotMatch(html, /localStorage|sessionStorage/);
});
test('KDS mantém correção do carregamento inicial 0.1.4', () => {
  const html = readFileSync(new URL('../src/public/kds.html', import.meta.url), 'utf8');
  assert.doesNotMatch(html, /\borderCounter\b/);
  assert.match(html, /function carregarPedidos\(\)/);
});
