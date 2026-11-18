import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { runInNewContext } from 'node:vm';

const html = readFileSync(new URL('../src/public/login.html', import.meta.url), 'utf8');
const script = html.match(/<script>([\s\S]*?)<\/script>/)?.[1];

async function submitLogin({ role = 'gerente', returnTo = '', status = 200 } = {}) {
  assert.ok(script, 'A tela de login precisa manter seu script funcional');
  const visits = [];
  const requests = [];
  const controls = {
    login: { value: 'operador' },
    senha: { value: 'SENHA-PRIVADA-DE-TESTE' },
    submit: { disabled: false, textContent: 'Entrar' },
    error: { textContent: '' }
  };
  let handler;
  const document = {
    getElementById(id) {
      if (id === 'login-form') {
        return { addEventListener(type, callback) {
          assert.equal(type, 'submit');
          handler = callback;
        } };
      }
      assert.ok(controls[id], `Elemento necessário ausente: ${id}`);
      return controls[id];
    }
  };
  const location = {
    pathname: '/avisaqui/login.html',
    search: returnTo ? `?return_to=${encodeURIComponent(returnTo)}` : '',
    replace(target) { visits.push(target); }
  };
  async function fetch(url, options) {
    requests.push({ url, options });
    if (url === '/avisaqui/api/setup/status') {
      return { json: async () => ({ needs_setup: false }) };
    }
    return {
      ok: status === 200,
      json: async () => status === 200
        ? ({ papel: role })
        : ({ error: 'Login ou senha inválidos' })
    };
  }
  runInNewContext(script, { document, location, fetch, URLSearchParams });
  assert.equal(typeof handler, 'function', 'Login precisa registrar evento submit');
  let prevented = false;
  await handler({ preventDefault() { prevented = true; } });
  assert.equal(prevented, true, 'Nunca usar envio nativo durante login via JavaScript');
  assert.match(html, /<form\b[^>]*\bid="login-form"[^>]*\bmethod="post"/i,
    'Fallback HTML nunca pode ser GET');
  const loginRequest = requests.filter(({ url }) => url.endsWith('/api/auth/login'));
  assert.equal(loginRequest.length, 1, 'Um único POST por envio');
  const [{ url, options }] = loginRequest;
  assert.equal(url, '/avisaqui/api/auth/login');
  assert.equal(options.method, 'POST');
  assert.equal(options.credentials, 'same-origin');
  assert.equal(options.headers['Content-Type'], 'application/json');
  assert.deepEqual(JSON.parse(options.body), {
    login: 'operador', senha: 'SENHA-PRIVADA-DE-TESTE'
  });
  assert.equal(controls.submit.disabled, false);
  assert.equal(controls.submit.textContent, 'Entrar');
  assert.equal(visits.every(value => !value.includes('SENHA-PRIVADA-DE-TESTE')), true);
  return { visits, error: controls.error.textContent };
}

test('login master segue para administração sem vazar senha na URL', async () => {
  const result = await submitLogin({ role: 'master' });
  assert.deepEqual(result.visits, ['/avisaqui/admin.html']);
});

test('login gerente segue para atendimento', async () => {
  const result = await submitLogin();
  assert.deepEqual(result.visits, ['/avisaqui/kds.html']);
});

test('retorno autorizado de pareamento é preservado', async () => {
  const returnTo = '/avisaqui/autorizar?solicitacao=12345678-1234-4234-8234-123456789abc';
  const result = await submitLogin({ returnTo });
  assert.deepEqual(result.visits, [returnTo]);
});

test('URL externa não recebe redirecionamento pós-login', async () => {
  const result = await submitLogin({ returnTo: 'https://site-externo.invalid/roubar' });
  assert.deepEqual(result.visits, ['/avisaqui/kds.html']);
});

test('senha incorreta mantém usuário no login com botão reabilitado', async () => {
  const result = await submitLogin({ status: 401 });
  assert.deepEqual(result.visits, []);
  assert.equal(result.error, 'Login ou senha inválidos');
});

test('limite de tentativas usa o mesmo login normalizado da consulta', () => {
  const authSource = readFileSync(new URL('../src/auth.js', import.meta.url), 'utf8');
  const declaration = authSource.match(/const loginKey = request =>[^;]+;/)?.[0];
  assert.ok(declaration, 'Chave de bloqueio por tentativas ausente');
  const code = declaration + '\n loginKey(request);';
  const key = login => runInNewContext(code, {
    request: { ip: '192.0.2.15', body: { login } }
  });
  assert.equal(key('operador'), key(' OPERADOR '));
  assert.equal(key('operador'), key('operador   '));
  assert.notEqual(key('operador'), key('outro'));
});
