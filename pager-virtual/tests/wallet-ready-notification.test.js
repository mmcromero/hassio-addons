import test from 'node:test';
import assert from 'node:assert/strict';
import { generateKeyPairSync } from 'node:crypto';

async function withSyntheticWallet(t, id) {
  const { privateKey } = generateKeyPairSync('rsa', { modulusLength: 2048 });
  const previousCredentials = process.env.GOOGLE_WALLET_CREDENTIALS;
  const previousFile = process.env.GOOGLE_WALLET_KEY_FILE;
  const previousFetch = globalThis.fetch;

  process.env.GOOGLE_WALLET_CREDENTIALS = JSON.stringify({
    private_key: privateKey.export({ type: 'pkcs8', format: 'pem' }),
    client_email: 'wallet-teste@example.invalid'
  });
  delete process.env.GOOGLE_WALLET_KEY_FILE;
  t.after(() => {
    if (previousCredentials === undefined) delete process.env.GOOGLE_WALLET_CREDENTIALS;
    else process.env.GOOGLE_WALLET_CREDENTIALS = previousCredentials;
    if (previousFile === undefined) delete process.env.GOOGLE_WALLET_KEY_FILE;
    else process.env.GOOGLE_WALLET_KEY_FILE = previousFile;
    globalThis.fetch = previousFetch;
  });
  const module = await import('../src/wallet.js?test=' + id);
  return module.notifyGoogleWalletReady;
}

const order = { id: 'pedido-10', token: 'token-teste-10', numero: 10, status: 'preparo' };
const ok = (status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => ({ access_token: 'token-ficticio' }) });

test('Wallet atualiza o passe e envia TEXT_AND_NOTIFY uma vez quando pedido fica pronto', async t => {
  const notify = await withSyntheticWallet(t, 'ready-success');
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options });
    return ok();
  };
  const result = await notify(order);
  assert.deepEqual(result, { updated: true, notified: true });
  assert.equal(calls.length, 3);
  assert.equal(calls[0].url, 'https://oauth2.googleapis.com/token');
  assert.equal(calls[1].method, 'PATCH');
  assert.match(calls[1].url, /genericObject\/3388000000023241721\.token-teste-10$/);
  assert.equal(JSON.parse(calls[1].body).textModulesData[0].id, 'status_pedido');
  assert.equal(calls[2].method, 'POST');
  assert.match(calls[2].url, /\/addMessage$/);
  assert.deepEqual(JSON.parse(calls[2].body), {
    message: {
      id: 'avisaqui_pedido_pronto',
      header: 'Seu pedido está pronto!',
      body: 'Senha #10: retire seu pedido no balcão do restaurante.',
      messageType: 'TEXT_AND_NOTIFY'
    }
  });
});

test('Wallet não envia aviso se passe não existe', async t => {
  const notify = await withSyntheticWallet(t, 'ready-not-found');
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, ...options });
    return url.includes('/genericObject/') ? ok(404) : ok();
  };
  const result = await notify(order);
  assert.equal(result.reason, 'pass_not_found');
  assert.equal(result.notified, false);
  assert.equal(calls.length, 2);
});

test('Wallet conserva atualização quando push falha ou atinge limite', async t => {
  const notify = await withSyntheticWallet(t, 'ready-quota');
  globalThis.fetch = async (url) => url.endsWith('/addMessage') ? ok(429) : ok();
  assert.deepEqual(await notify(order), {
    updated: true, notified: false, reason: 'notification_quota', status: 429
  });
});

test('Wallet não envia push se atualização do passe falhar', async t => {
  const notify = await withSyntheticWallet(t, 'ready-patch-fails');
  const calls = [];
  globalThis.fetch = async (url) => {
    calls.push(url);
    return url.includes('/genericObject/') ? ok(403) : ok();
  };
  const result = await notify(order);
  assert.equal(result.updated, false);
  assert.equal(result.reason, 'update_failed');
  assert.equal(calls.length, 2);
});

test('Wallet não notifica pedido sem transição ou sem identificação', async t => {
  const notify = await withSyntheticWallet(t, 'ready-invalid');
  globalThis.fetch = async () => { throw new Error('Não deveria usar rede'); };
  assert.equal((await notify({ ...order, status: 'pronto' })).reason, 'invalid_order_transition');
  assert.equal((await notify({ numero: 10, status: 'preparo' })).reason, 'invalid_order_transition');
});

test('Wallet distingue rejeição do addMessage sem desfazer atualização do cartão', async t => {
  const notify = await withSyntheticWallet(t, 'ready-notification-denied');
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method });
    return url.endsWith('/addMessage') ? ok(403) : ok();
  };
  assert.deepEqual(await notify(order), {
    updated: true, notified: false, reason: 'notification_failed', status: 403
  });
  assert.equal(calls.length, 3);
  assert.equal(calls[1].method, 'PATCH');
  assert.equal(calls[2].method, 'POST');
});

test('Wallet aceita resposta 204 do addMessage como aceitação da API, não entrega Android', async t => {
  const notify = await withSyntheticWallet(t, 'ready-notification-204');
  const calls = [];
  globalThis.fetch = async (url, options) => {
    calls.push({ url, method: options.method });
    return url.endsWith('/addMessage') ? ok(204) : ok();
  };
  assert.deepEqual(await notify(order), { updated: true, notified: true });
  assert.equal(calls.filter(c => c.url.endsWith('/addMessage')).length, 1);
});
