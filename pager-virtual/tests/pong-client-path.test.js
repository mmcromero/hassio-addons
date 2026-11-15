import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('Pong usa prefixo da página cliente, inclusive atrás de /avisaqui/', () => {
  const js = readFileSync(new URL('../src/public/pong.js', import.meta.url), 'utf8');
  assert.match(js, /location\.pathname\.endsWith\('\/cliente\.html'\)/);
  assert.match(js, /const endpoint = apiBase \+ '\/api\/jogos\/pong'/);
  for (const pathname of ['/cliente.html', '/avisaqui/cliente.html']) {
    const base = pathname.endsWith('/cliente.html') ? pathname.slice(0, -'/cliente.html'.length) : pathname.replace(/\/$/, '');
    assert.equal(base + '/api/jogos/pong/entrar', pathname.startsWith('/avisaqui/') ? '/avisaqui/api/jogos/pong/entrar' : '/api/jogos/pong/entrar');
  }
});

test('interface contém os modos solo e dupla, com tratamento explícito de 404', () => {
  const html = readFileSync(new URL('../src/public/cliente.html', import.meta.url), 'utf8');
  const js = readFileSync(new URL('../src/public/pong.js', import.meta.url), 'utf8');
  assert.match(html, /abrirPong\('solo'\)/);
  assert.match(html, /abrirPong\('dupla'\)/);
  assert.match(js, /response\.status === 404/);
  assert.match(js, /response\.json\(\)\.catch/);
});
