import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const client = readFileSync(new URL('../src/public/cliente.html', import.meta.url), 'utf8');
const pong = readFileSync(new URL('../src/public/pong.js', import.meta.url), 'utf8');

test('cliente carrega Pong somente enquanto pedido está em preparo', () => {
  assert.match(client, /pongAllowed\s*=\s*status\s*===\s*'preparo'/);
  assert.match(client, /if\s*\(!pongAllowed\)\s*fecharJogos\(\)/);
  assert.match(client, /if\s*\(!pongAllowed\s*\|\|\s*atual\s*!==\s*gamesGeneration\)/);
});

test('Pong preserva prefixo HTTPS e não coloca token do pedido na URL do SSE', () => {
  assert.match(pong, /location\.pathname\.endsWith\('\/cliente\.html'\)/);
  assert.match(pong, /const endpoint = apiBase \+ '\/api\/jogos\/pong'/);
  assert.match(pong, /new EventSource\(endpoint \+ '\/eventos\/' \+ encodeURIComponent\(player\)\)/);
  assert.doesNotMatch(pong, /new EventSource\([^\n]*token/);
});

test('Pong usa credenciais da mesma origem e encerra SSE ao sair', () => {
  assert.match(pong, /credentials:\s*'same-origin'/);
  assert.match(pong, /stream\?\.close\(\)/);
  assert.match(pong, /stream\.addEventListener\('encerrado', exit\)/);
  assert.match(pong, /container\.replaceChildren\(\)/);
});

test('cliente não insere Pong em iframe nem usa mensagens entre origens', () => {
  assert.doesNotMatch(pong, /document\.createElement\(['"]iframe['"]\)/);
  assert.doesNotMatch(pong, /postMessage\s*\(|new MessageChannel\s*\(/);
  assert.match(pong, /document\.createElement\('canvas'\)/);
});
