import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const publicFile = name => readFileSync(new URL('../src/public/' + name, import.meta.url), 'utf8');
const manifest = JSON.parse(publicFile('manifest.webmanifest'));
const cliente = publicFile('cliente.html');
const pushWorker = publicFile('push-sw.js');
const pushServer = readFileSync(new URL('../src/push.js', import.meta.url), 'utf8');
const setupServer = readFileSync(new URL('../src/setup.js', import.meta.url), 'utf8');
const setupPage = publicFile('setup.html');

test('PWA usa nome Avisaqui e mantém a identidade técnica instalada', () => {
  assert.equal(manifest.name, 'Avisaqui — Acompanhamento de pedido');
  assert.equal(manifest.short_name, 'Avisaqui');
  assert.equal(manifest.id, './cliente.html');
  assert.equal(manifest.start_url, './cliente.html');
  assert.equal(manifest.scope, './');
  assert.equal(manifest.display, 'standalone');
  assert.match(cliente, /<link\s+rel="manifest"\s+href="\.\/manifest\.webmanifest">/);
});

test('orientações e notificações do cliente não mostram marca antiga', () => {
  for (const [name, text] of [
    ['manifest.webmanifest', publicFile('manifest.webmanifest')],
    ['cliente.html', cliente],
    ['push-sw.js (sem tag técnica persistente)', pushWorker.replaceAll('bipou-pedido', '')]
  ]) {
    assert.doesNotMatch(text, /\b(?:bipou|bipol)\b/i, name);
  }
  assert.match(cliente, /adicionar o Avisaqui à Tela de Início/);
  assert.match(cliente, /notificações do Avisaqui/);
  assert.match(pushWorker, /data\.title \|\| 'Avisaqui'/);
  assert.match(pushServer, /title: 'Avisaqui — pedido pronto!'/);
  assert.match(setupPage, /AVISAQUI PRIMEIRO ACESSO/);
  assert.match(setupServer, /AVISAQUI PRIMEIRO ACESSO/);
  assert.doesNotMatch(pushServer.replaceAll('bipou-', ''), /\b(?:Bipou|Bipol)\b/i);
  assert.doesNotMatch(setupPage, /\b(?:Bipou|Bipol)\b/i);
});

test('notificação mantém tag técnica existente para não mudar a deduplicação', () => {
  assert.match(pushWorker, /tag: data\.tag \|\| 'bipou-pedido'/);
});
