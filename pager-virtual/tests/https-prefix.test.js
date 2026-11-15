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
  assert.match(html, /api\('api\/integracoes\/impressao\/chaves'\)/);
  assert.doesNotMatch(html, /'\.\/api\/integracoes\/impressao\//);
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
