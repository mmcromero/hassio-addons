import test from 'node:test';
import assert from 'node:assert/strict';
import { validarCatalogo, obterCatalogo, criarSessaoJogos } from '../src/public/games/catalogo.js';

const valido = { schemaVersion: 1, catalogVersion: '0.2.0', games: [{ id: 'jogo-da-velha', title: 'Jogo da Velha', version: '0.2.0', module: './jogo-da-velha.js', status: 'experimental', modes: ['solo','dupla-local'], minPlayers: 1, maxPlayers: 2, requiresServer: false, orientation: 'retrato' }] };

test('catálogo valida esquema e módulos locais', () => {
  assert.equal(validarCatalogo(valido).length, 1);
  assert.throws(() => validarCatalogo({ schemaVersion: 2, games: [] }));
  assert.throws(() => validarCatalogo({ ...valido, games: [{ ...valido.games[0], module: 'https://externo/jogo.js' }] }));
  assert.throws(() => validarCatalogo({ ...valido, games: [valido.games[0], valido.games[0]] }));
  assert.throws(() => validarCatalogo({ ...valido, games: [{ ...valido.games[0], maxPlayers: 0 }] }));
  assert.throws(() => validarCatalogo({ ...valido, games: [{ ...valido.games[0], orientation: 'diagonal' }] }));
});

test('consulta revalida o catálogo sob demanda', async () => {
  let opcoes;
  const jogos = await obterCatalogo({ fetcher: async (_url, config) => { opcoes = config; return { ok: true, json: async () => valido }; } });
  assert.equal(jogos[0].id, 'jogo-da-velha');
  assert.equal(opcoes.cache, 'no-cache');
});

test('encerramento durante carregamento impede início tardio', async () => {
  let resolver;
  let iniciados = 0;
  const sessao = criarSessaoJogos({ importar: () => new Promise(resolve => { resolver = resolve; }) });
  const abertura = sessao.abrir(valido.games[0], {});
  sessao.encerrar();
  resolver({ iniciarJogo: () => { iniciados++; return () => {}; } });
  assert.equal(await abertura, false);
  assert.equal(iniciados, 0);
});

test('troca de jogo encerra o anterior e encerramento é idempotente', async () => {
  let encerrados = 0;
  const sessao = criarSessaoJogos({ importar: async () => ({ iniciarJogo: () => () => { encerrados++; } }) });
  await sessao.abrir(valido.games[0], {});
  await sessao.abrir(valido.games[0], {});
  sessao.encerrar();
  sessao.encerrar();
  assert.equal(encerrados, 2);
});

test('pausa e retomada encaminhadas somente ao jogo ativo', async () => {
  let pausas = 0, retomadas = 0;
  const sessao = criarSessaoJogos({ importar: async () => ({ iniciarJogo: () => {
    const encerrar = () => {};
    encerrar.pausar = () => { pausas++; };
    encerrar.retomar = () => { retomadas++; };
    return encerrar;
  } }) });
  await sessao.abrir(valido.games[0], {});
  sessao.pausar(); sessao.retomar(); sessao.encerrar(); sessao.pausar();
  assert.equal(pausas, 1); assert.equal(retomadas, 1);
});
