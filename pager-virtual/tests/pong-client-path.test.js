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
  // O catálogo atual escolhe 1/2 jogadores antes de abrir o iframe;
  // o duelo em aparelhos diferentes continua no controlador privilegiado.
  assert.match(biblioteca, /const numeros = item\.playerCounts \|\| \[1,2\]/);
  assert.match(biblioteca, /modoAtual = n === 1 \? 'solo' : 'dupla-local'/);
  assert.match(biblioteca, /botao\('Cada um no seu celular \(online\)'/);
  assert.match(biblioteca, /modoAtual = 'dupla';\s*confirmarPartida\(\)/);
  const frame = readFileSync(new URL('../src/public/games/jogo-da-velha-isolado.html', import.meta.url), 'utf8');
  assert.match(frame, /modo==='dupla-local'/);
  assert.match(frame, /'1 jogador'/);
  assert.match(frame, /'2 jogadores'/);
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
