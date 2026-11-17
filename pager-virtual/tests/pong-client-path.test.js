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
  const biblioteca = readFileSync(new URL('../src/public/games/biblioteca.js', import.meta.url), 'utf8');
  assert.match(biblioteca, /\['solo', 'Contra o computador'\]/);
  assert.match(biblioteca, /\['dupla', 'Duas pessoas'\]/);
  assert.match(html, /iniciarPong: async \(container, mode\) =>/);
  assert.match(html, /await iniciarPong\(\{ token, mode, container/);
  assert.match(js, /response\.status === 404/);
  assert.match(js, /response\.json\(\)\.catch/);
});


test('SSE do Pong não contém token de pedido e comandos usam sessão', () => {
  const client = readFileSync(new URL('../src/public/pong.js', import.meta.url), 'utf8');
  const backend = readFileSync(new URL('../src/pong.js', import.meta.url), 'utf8');
  const pedidos = readFileSync(new URL('../src/routes/pedidos.js', import.meta.url), 'utf8');
  assert.match(client, /new EventSource\(endpoint \+ '\/eventos\/' \+ encodeURIComponent\(player\)\)/);
  assert.doesNotMatch(client, /encodeURIComponent\(token\).*encodeURIComponent\(player\)/);
  assert.match(backend, /HttpOnly; SameSite=Strict/);
  assert.match(backend, /randomBytes\(32\)/);
  assert.match(backend, /sessions\.set\(hash\(secret\)/);
  assert.match(backend, /const auth = authorize\(req, req\.params\.player\)/);
  assert.match(backend, /if \(!validPost\(req\)\)/);
  assert.match(pedidos, /if \(status !== 'preparo'\) stopPongForOrder\(pedido\.id\)/);
});
