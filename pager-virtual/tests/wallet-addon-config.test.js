import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { generateKeyPairSync } from 'node:crypto';

const appConfigPath = '/config/google-wallet-key.json';
const persistentPath = '/data/credentials/google-wallet-key.json';

function withIsolatedWalletEnv(t) {
  const before = Object.fromEntries(['GOOGLE_WALLET_CREDENTIALS', 'GOOGLE_WALLET_KEY_FILE', 'DATA_PATH'].map(k => [k, process.env[k]]));
  delete process.env.GOOGLE_WALLET_CREDENTIALS;
  delete process.env.GOOGLE_WALLET_KEY_FILE;
  process.env.DATA_PATH = '/data';
  t.after(() => {
    for (const [key, value] of Object.entries(before)) {
      if (value === undefined) delete process.env[key];
      else process.env[key] = value;
    }
  });
}

function syntheticCredential() {
  const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  return JSON.stringify({
    client_email: 'wallet-addon-config@example.invalid',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' })
  });
}

test('Wallet lê credencial de app_config no caminho /config sem expor segredo', async t => {
  withIsolatedWalletEnv(t);
  const key = syntheticCredential();
  const inspected = [];
  t.mock.method(fs, 'existsSync', file => file === appConfigPath || file === persistentPath);
  t.mock.method(fs, 'readFileSync', file => {
    inspected.push(file);
    if (file === appConfigPath) return key;
    throw new Error('Não deve tentar ler a credencial persistente se app_config estiver válido');
  });
  const { generateSaveUrl } = await import('../src/wallet.js?test=addon-config');
  const url = generateSaveUrl({ token: 'token-sem-segredo', numero: 22 });
  const payload = JSON.parse(Buffer.from(url.split('/').at(-1).split('.')[1], 'base64url').toString('utf8'));
  assert.equal(payload.iss, 'wallet-addon-config@example.invalid');
  assert.deepEqual(inspected, [appConfigPath]);
});

test('Wallet mantém fallback /data se app_config estiver ausente', async t => {
  withIsolatedWalletEnv(t);
  const key = syntheticCredential();
  t.mock.method(fs, 'existsSync', file => file === persistentPath);
  t.mock.method(fs, 'readFileSync', file => {
    if (file === persistentPath) return key;
    throw new Error('Leitura inesperada');
  });
  const { generateSaveUrl } = await import('../src/wallet.js?test=addon-config-fallback');
  assert.match(generateSaveUrl({ token: 'fallback', numero: 23 }), /^https:\/\/pay\.google\.com\/gp\/v\/save\//);
});

test('Wallet rejeita JSON inválido em app_config sem trocar silenciosamente de chave', async t => {
  withIsolatedWalletEnv(t);
  t.mock.method(fs, 'existsSync', file => file === appConfigPath || file === persistentPath);
  t.mock.method(fs, 'readFileSync', file => {
    if (file === appConfigPath) return '{invalid';
    throw new Error('A credencial em /data não pode substituir arquivo inválido');
  });
  const { generateSaveUrl } = await import('../src/wallet.js?test=addon-config-invalid');
  assert.throws(() => generateSaveUrl({ token: 'invalid', numero: 24 }), /não configurada/);
});
