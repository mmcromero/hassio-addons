import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { validarCatalogo, criarSessaoJogos } from '../src/public/games/catalogo.js';

test('manifesto da biblioteca contém 16 jogos e somente dois disponíveis', async () => {
  const data = JSON.parse(await readFile(new URL('../src/public/games/manifest.json', import.meta.url), 'utf8'));
  const games = validarCatalogo(data);
  assert.equal(games.length, 16);
  assert.equal(games.filter(g => g.status === 'construction').length, 14);
  assert.deepEqual(games.filter(g => g.status !== 'construction').map(g => g.id).sort(), ['jogo-da-velha', 'pong']);
  assert.equal(games.find(g => g.id === 'pong').module, undefined);
});

test('jogos em construção e Pong externo não podem ser importados como módulo', async () => {
  const data = JSON.parse(await readFile(new URL('../src/public/games/manifest.json', import.meta.url), 'utf8'));
  let imports = 0;
  const session = criarSessaoJogos({ importar: async () => { imports++; return { iniciarJogo: () => () => {} }; } });
  for (const game of validarCatalogo(data).filter(g => g.status !== 'experimental')) {
    await assert.rejects(session.abrir(game, {}));
  }
  assert.equal(imports, 0);
});

test('HTML do cliente mantém prioridade de pedidos e biblioteca sob demanda', async () => {
  const html = await readFile(new URL('../src/public/cliente.html', import.meta.url), 'utf8');
  assert.match(html, /if \(!pongAllowed\) fecharJogos\(\)/);
  assert.match(html, /await import\('\.\/games\/biblioteca\.js'\)/);
  assert.match(html, /startAlarmLoop\(\)/);
  assert.match(html, /new EventSource\(sseUrl\)/);
  assert.doesNotMatch(html, /id="pong-start"/);
});

test('jogo da velha isolado não possui acesso à rede nem ao pedido', async () => {
  const frame = await readFile(new URL('../src/public/games/jogo-da-velha-isolado.html', import.meta.url), 'utf8');
  const biblioteca = await readFile(new URL('../src/public/games/biblioteca.js', import.meta.url), 'utf8');
  assert.match(biblioteca, /setAttribute\('sandbox', 'allow-scripts'\)/);
  assert.match(biblioteca, /new MessageChannel\(\)/);
  assert.match(biblioteca, /frame\.remove\(\)/);
  assert.match(frame, /connect-src 'none'/);
  assert.match(frame, /default-src 'none'/);
  assert.doesNotMatch(frame, /(?:fetch\(|EventSource\(|localStorage|sessionStorage|document\.cookie)/);
  assert.doesNotMatch(frame, /(?:token|pedido|credencial)/i);
});

test('handshake só inicia uma vez e falha não mantém iframe ativo', async () => {
  const biblioteca = await readFile(new URL('../src/public/games/biblioteca.js', import.meta.url), 'utf8');
  assert.match(biblioteca, /validateEnvelope\(d, \{/);
  assert.match(biblioteca, /instanceId, lastSequence/);
  assert.match(biblioteca, /createRateLimiter\(\)/);
  assert.match(biblioteca, /iniciado = true/);
  assert.match(biblioteca, /catch \{ if \(ativa && atual === geracao\) \{ parar\(\)/);
  assert.match(biblioteca, /canal\.port1\.close\(\)/);
  assert.match(biblioteca, /canal\.port2\.close\(\)/);
});

test('saída interna do Pong retorna à biblioteca e mantém módulo original', async () => {
  const html = await readFile(new URL('../src/public/cliente.html', import.meta.url), 'utf8');
  const biblioteca = await readFile(new URL('../src/public/games/biblioteca.js', import.meta.url), 'utf8');
  assert.match(html, /onExit: \(\) => \{/);
  assert.match(html, /querySelector\('button\[data-games-back\]'\)/);
  assert.match(biblioteca, /voltar\.dataset\.gamesBack = 'true'/);
  assert.match(html, /await import\('\.\/pong\.js'\)/);
});


test('contrato v1 é aplicado em ambos os lados do iframe', async () => {
  const frame = await readFile(new URL('../src/public/games/jogo-da-velha-isolado.html', import.meta.url), 'utf8');
  const biblioteca = await readFile(new URL('../src/public/games/biblioteca.js', import.meta.url), 'utf8');
  assert.match(biblioteca, /newInstanceId\(\)/);
  assert.match(biblioteca, /createEnvelope\(\{ type: 'GAME_START'/);
  assert.match(frame, /d\.instanceId !== instanceId/);
  assert.match(frame, /d\.sequence <= ultimo/);
  assert.match(frame, /JSON\.stringify\(d\)\.length > 4096/);
  assert.match(frame, /contadorTaxa > 20/);
  assert.match(frame, /enviar\('GAME_READY'\)/);
});
