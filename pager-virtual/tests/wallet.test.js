import test from 'node:test';
import assert from 'node:assert/strict';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';
import { generateKeyPairSync, verify } from 'node:crypto';

test('Google Wallet: generateSaveUrl cria link assinado válido para o pedido', async (t) => {
  // Credencial efêmera só em memória. Nunca ler/sobrescrever a chave real,
  // acessar Google ou trocar o assinador do produto por um mock.
  const { privateKey, publicKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const credentialPath = fileURLToPath(new URL('../credentials/google-wallet-key.json', import.meta.url));
  const syntheticCredentials = JSON.stringify({
    client_email: 'wallet-laboratorio@example.invalid',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' })
  });
  const existsSync = fs.existsSync, readFileSync = fs.readFileSync;
  t.mock.method(fs, 'existsSync', (file) => file === credentialPath || existsSync(file));
  t.mock.method(fs, 'readFileSync', (file, ...args) =>
    file === credentialPath ? syntheticCredentials : readFileSync(file, ...args));
  const { generateSaveUrl } = await import('../src/wallet.js');
  const pedido = {
    token: 'token-teste-123',
    numero: 42,
    restaurante_nome: 'Hamburgueria do Bairro',
    status: 'preparo'
  };

  const url = generateSaveUrl(pedido);
  assert.ok(url.startsWith('https://pay.google.com/gp/v/save/'));
  
  const token = url.replace('https://pay.google.com/gp/v/save/', '');
  const parts = token.split('.');
  assert.equal(parts.length, 3, 'JWT deve conter 3 partes separadas por ponto');
  const header = JSON.parse(Buffer.from(parts[0], 'base64url').toString('utf8'));
  assert.deepEqual(header, { alg: 'RS256', typ: 'JWT' });
  assert.equal(verify('RSA-SHA256', Buffer.from(parts[0] + '.' + parts[1]), publicKey,
    Buffer.from(parts[2], 'base64url')), true, 'Assinatura real deve ser válida');

  const payload = JSON.parse(Buffer.from(parts[1], 'base64url').toString('utf8'));
  assert.equal(payload.aud, 'google');
  assert.equal(payload.iss, 'wallet-laboratorio@example.invalid');
  assert.equal(payload.typ, 'savetowallet');
  assert.ok(payload.payload.genericObjects[0].id.includes('token-teste-123'));
  assert.equal(payload.payload.genericObjects[0].header.defaultValue.value, 'Senha #42');
});


test('Google Wallet: credencial JSON via ambiente sem arquivo privado', async (t) => {
  const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const originalJson = process.env.GOOGLE_WALLET_CREDENTIALS;
  const originalFile = process.env.GOOGLE_WALLET_KEY_FILE;
  t.after(() => {
    if (originalJson === undefined) delete process.env.GOOGLE_WALLET_CREDENTIALS;
    else process.env.GOOGLE_WALLET_CREDENTIALS = originalJson;
    if (originalFile === undefined) delete process.env.GOOGLE_WALLET_KEY_FILE;
    else process.env.GOOGLE_WALLET_KEY_FILE = originalFile;
  });
  delete process.env.GOOGLE_WALLET_KEY_FILE;
  process.env.GOOGLE_WALLET_CREDENTIALS = JSON.stringify({
    client_email: 'wallet-env@example.invalid',
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' })
  });
  const { generateSaveUrl } = await import('../src/wallet.js?test=wallet-env');
  const url = generateSaveUrl({ token: 'pedido-env', numero: 12 });
  const claims = JSON.parse(Buffer.from(url.split('/').pop().split('.')[1], 'base64url').toString('utf8'));
  assert.equal(claims.iss, 'wallet-env@example.invalid');
});

test('Google Wallet: sem credencial, falha fechada e não gera link', async (t) => {
  const originalJson = process.env.GOOGLE_WALLET_CREDENTIALS;
  const originalFile = process.env.GOOGLE_WALLET_KEY_FILE;
  t.after(() => {
    if (originalJson === undefined) delete process.env.GOOGLE_WALLET_CREDENTIALS;
    else process.env.GOOGLE_WALLET_CREDENTIALS = originalJson;
    if (originalFile === undefined) delete process.env.GOOGLE_WALLET_KEY_FILE;
    else process.env.GOOGLE_WALLET_KEY_FILE = originalFile;
  });
  delete process.env.GOOGLE_WALLET_CREDENTIALS;
  process.env.GOOGLE_WALLET_KEY_FILE = '/data/credentials/google-wallet-key.json';
  t.mock.method(fs, 'existsSync', () => false);
  const { generateSaveUrl } = await import('../src/wallet.js?test=wallet-missing');
  assert.throws(
    () => generateSaveUrl({ token: 'pedido-sem-chave', numero: 14 }),
    /Chave de serviço da Carteira do Google não configurada/
  );
});

test('Google Wallet: chave inválida no ambiente não recua para arquivo local', async (t) => {
  const originalJson = process.env.GOOGLE_WALLET_CREDENTIALS;
  const originalFile = process.env.GOOGLE_WALLET_KEY_FILE;
  t.after(() => {
    if (originalJson === undefined) delete process.env.GOOGLE_WALLET_CREDENTIALS;
    else process.env.GOOGLE_WALLET_CREDENTIALS = originalJson;
    if (originalFile === undefined) delete process.env.GOOGLE_WALLET_KEY_FILE;
    else process.env.GOOGLE_WALLET_KEY_FILE = originalFile;
  });
  process.env.GOOGLE_WALLET_CREDENTIALS = '{invalid-json';
  delete process.env.GOOGLE_WALLET_KEY_FILE;
  const { generateSaveUrl } = await import('../src/wallet.js?test=wallet-invalid');
  assert.throws(
    () => generateSaveUrl({ token: 'pedido-invalido', numero: 15 }),
    /Chave de serviço da Carteira do Google não configurada/
  );
});
