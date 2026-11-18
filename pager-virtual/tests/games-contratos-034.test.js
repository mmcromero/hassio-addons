import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { validarCatalogo } from '../src/public/games/catalogo.js';
import {
  PROTOCOL, VERSION, createEnvelope, validateEnvelope, createRateLimiter
} from '../src/public/games/protocolo-v1.js';

const manifesto = () => JSON.parse(readFileSync(new URL('../src/public/games/manifest.json', import.meta.url), 'utf8'));
const copia = value => JSON.parse(JSON.stringify(value));

test('GAMES-034: manifesto tem IDs únicos e 16 entradas com 14 em construção', () => {
  const dados = manifesto();
  const jogos = validarCatalogo(dados);
  assert.equal(jogos.length, 16);
  assert.equal(new Set(jogos.map(j => j.id)).size, 16);
  assert.equal(jogos.filter(j => j.status === 'construction').length, 14);
  assert.equal(jogos.find(j => j.id === 'pong')?.orientation, 'paisagem');
  assert.equal(jogos.find(j => j.id === 'jogo-da-velha')?.orientation, 'retrato');
});

test('GAMES-034: rejeita ID duplicado, módulo inseguro e modos inválidos', () => {
  for (const alterar of [
    d => { d.games[1].id = d.games[0].id; },
    d => { d.games[1].module = '../fora.js'; },
    d => { d.games[1].modes = ['modo-invalido']; },
    d => { d.games[1].minPlayers = 0; },
    d => { d.catalogVersion = 'sem-versao'; }
  ]) {
    const dados = copia(manifesto());
    alterar(dados);
    assert.throws(() => validarCatalogo(dados));
  }
});

test('GAMES-034: protocolo aceita GAME_READY válido e rejeita replay, instância e tipo falsos', () => {
  const instanceId = 'instancia-sintetica';
  const message = createEnvelope({ type: 'GAME_READY', instanceId, sequence: 0 });
  assert.equal(message.protocol, PROTOCOL);
  assert.equal(message.version, VERSION);
  const ctx = { role: 'frame', state: 'WAIT_READY', instanceId };
  assert.equal(validateEnvelope(message, ctx), true);
  assert.equal(validateEnvelope(message, { ...ctx, lastSequence: 0 }), false);
  assert.equal(validateEnvelope(message, { ...ctx, instanceId: 'outra-instancia' }), false);
  assert.equal(validateEnvelope({ ...message, type: 'GAME_START' }, ctx), false);
  assert.equal(validateEnvelope({ ...message, payload: { token: 'segredo' } }, ctx), false);
});

test('GAMES-034: protocolo limita taxas excessivas', () => {
  let tempo = 1000;
  const allowed = createRateLimiter({ limit: 2, windowMs: 1000, now: () => tempo });
  assert.equal(allowed(), true);
  assert.equal(allowed(), true);
  assert.equal(allowed(), false);
  tempo += 1000;
  assert.equal(allowed(), true);
});
