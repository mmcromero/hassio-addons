import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { join } from 'node:path';

const source = (name) => readFileSync(join(process.cwd(), 'src', name), 'utf8');

test('login e primeiro acesso fazem chamadas de API dentro do prefixo HTTPS', () => {
  for (const page of ['login.html', 'setup.html']) {
    const html = source('public/' + page);
    assert.match(html, /const basePath = location\.pathname\.startsWith\('\/avisaqui\/'\)/);
    assert.match(html, /fetch\(basePath \+ '\/api\//);
    assert.doesNotMatch(html, /fetch\('\/api\//);
  }
  assert.match(source('public/login.html'), /location\.replace\(basePath \+ \(data\.papel/);
});

test('administração e KDS não deixam a subrota nos redirecionamentos', () => {
  const admin = source('public/admin.html');
  const kds = source('public/kds.html');
  assert.doesNotMatch(admin, /location\.(?:replace|assign)\('\/(?:login|admin|kds)\.html/);
  assert.doesNotMatch(kds, /location\.(?:replace|assign)\('\/(?:login|admin|kds)\.html/);
  assert.match(kds, /apiPath\('\/api\/kds\/stream'\)/);
});

test('página de integração consulta API relativa ao prefixo, não à página HTML', () => {
  const html = source('public/impressao.html');
  // A tela aprovada usa pareamento, sem geração manual de chaves.
  assert.match(html, /api\('api\/integracoes\/impressao\/eventos'\)/);
  assert.match(html, /api\('api\/agentes\/dispositivos'\)/);
  assert.doesNotMatch(html, /'\.\/api\/integracoes\/impressao\//);
  assert.match(html, /fetch\(basePath\+'\/api\/auth\/me',\{credentials:'same-origin'/);
  const paths = [...html.matchAll(/\bapi\('([^']+)'/g)].map(match => match[1]);
  assert.ok(paths.length >= 3);
  for (const prefix of ['', '/avisaqui']) {
    const page = (prefix ? 'https://exemplo.invalid' : 'http://localhost:8090') + prefix + '/impressao.html';
    for (const endpoint of paths) {
      const url = new URL(endpoint, page);
      assert.equal(url.origin, new URL(page).origin);
      assert.equal(url.pathname, prefix + '/' + endpoint);
      assert.ok(endpoint.startsWith('api/'));
    }
  }
});

test('cliente mantém base de API e Worker no mesmo escopo', () => {
  const html = source('public/cliente.html');
  assert.match(html, /const appBasePath = window\.location\.pathname/);
  assert.match(html, /fetch\(appBasePath \+ '\/api\/push\/public-key'/);
  assert.match(html, /navigator\.serviceWorker\.register\(appBasePath \+ '\/push-sw\.js', \{ scope: appBasePath \+ '\/' \}\)/);
  const manifest = JSON.parse(source('public/manifest.webmanifest'));
  assert.equal(manifest.scope, './');
  assert.equal(manifest.start_url, './cliente.html');
  const sw = source('public/push-sw.js');
  assert.match(sw, /new URL\('cliente\.html', self\.registration\.scope\)/);
});

test('proxy usa prefixo apenas no HTTPS e mantém Fastify escutando na porta interna', () => {
  const server = source('server.js');
  assert.match(server, /x-forwarded-prefix/);
  assert.match(server, /pageUrl\(request, '\/login\.html'\)/);
  assert.match(server, /process\.env\.PORT \|\| '8095'/);
  const nginx = readFileSync(join(process.cwd(), 'docs/AVISAQUI-HTTPS-001-nginx.conf.example'), 'utf8');
  assert.match(nginx, /location \^~ \/avisaqui\//);
  assert.match(nginx, /proxy_pass http:\/\/45c28620-pager-virtual:8095\//);
  assert.match(nginx, /proxy_buffering off;/);
});

test('diagnóstico do aparelho preservado no cliente com a rota HTTPS', () => {
  const html = source('public/cliente.html');
  assert.match(html, /id="diagnosticos"/);
  for (const id of ['diag-check', 'diag-wake', 'diag-vibrate', 'diag-audio', 'diag-result']) {
    assert.match(html, new RegExp('id="' + id + '"'));
    if (id !== 'diag-result') assert.match(html, new RegExp("getElementById\\('" + id + "'\\)"));
  }
  assert.match(html, /const appBasePath = window\.location\.pathname/);
  assert.match(html, /navigator\.serviceWorker\.register\(appBasePath/);
});

test('landing preserva login e formulário do piloto no prefixo HTTPS e no HTTP local', () => {
  const html = source('public/landing.html');
  assert.match(html, /href="\.\/login\.html"/);
  assert.match(html, /fetch\('\.\/api\/piloto\/interesse'/);
  for (const [page, login, api] of [
    ['https://romeropi.duckdns.org:8443/avisaqui/landing.html',
      '/avisaqui/login.html', '/avisaqui/api/piloto/interesse'],
    ['http://192.168.0.6:8090/landing.html',
      '/login.html', '/api/piloto/interesse']
  ]) {
    assert.equal(new URL('./login.html', page).pathname, login);
    assert.equal(new URL('./api/piloto/interesse', page).pathname, api);
  }
});

test('Pong 0.1.14 é experimental e protegido por limites de recursos', () => {
  const yaml = readFileSync(join(process.cwd(), 'config.yaml'), 'utf8');
  const pong = source('pong.js');
  const client = source('public/cliente.html');
  assert.match(yaml, /pong_experimental: false/);
  assert.match(yaml, /pong_experimental: bool/);
  assert.match(pong, /const MAX_ROOMS = 64/);
  assert.match(pong, /const MAX_STREAMS_PER_ROOM = 4/);
  assert.match(pong, /order\.status !== 'preparo'/);
  assert.match(client, /await import\('\.\/pong\.js'\)/);
  assert.match(client, /if \(!pongAllowed\) fecharJogos\(\)/);
  assert.match(client, /try \{ sair\?\.\(\); \} catch/);
  assert.match(client, /gamesContent\.replaceChildren\(\)/);
});
