import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';

const page = fs.readFileSync(new URL('../src/public/cliente.html', import.meta.url), 'utf8');
const scripts = [...page.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/g)]
  .map(match => match[1]).filter(Boolean);

// Verifica a sintaxe JS embutida, sem executar a UI no Node.
test('cliente: scripts inline compilam', () => {
  assert.ok(scripts.length > 0, 'script inline esperado');
  for (const source of scripts) assert.doesNotThrow(() => new Function(source));
});

test('cliente: preferência de som persiste após recarregar e não simula gesto', () => {
  assert.match(page, /const soundPreferenceKey = 'avisaqui:cliente:alerta-sonoro:v1'/);
  assert.match(page, /localStorage\.getItem\(soundPreferenceKey\)/);
  assert.match(page, /localStorage\.setItem\(soundPreferenceKey, enabled \? 'on' : 'off'\)/);
  assert.match(page, /let isSoundEnabled = readSoundPreference\(\)/);
  assert.match(page, /saveSoundPreference\(isSoundEnabled\)/);
  assert.match(page, /renderSoundPreference\(\);/);
  assert.match(page, /btnSoundTest\.setAttribute\('aria-pressed', String\(isSoundEnabled\)\)/);
  assert.doesNotMatch(page, /let isSoundEnabled = false/);
});

test('cliente: Wallet distingue falta de chave de indisponibilidade e não duplica aviso', () => {
  assert.match(page, /code === 'WALLET_NOT_CONFIGURED'/);
  assert.match(page, /wallet_not_configured/);
  assert.match(page, /unavailable\.hidden = true; \/\/ Não apresentar duas mensagens contraditórias/);
  assert.match(page, /cache: 'no-store'/);
  assert.match(page, /walletLink\.href = data\.url/);
});
