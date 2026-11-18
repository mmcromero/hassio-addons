import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const html=readFileSync(new URL('../src/public/impressao.html',import.meta.url),'utf8');
const route=readFileSync(new URL('../src/windows-download.js',import.meta.url),'utf8');
const server=readFileSync(new URL('../src/server.js',import.meta.url),'utf8');
const options=readFileSync(new URL('../config.yaml',import.meta.url),'utf8');
const bootstrap=readFileSync(new URL('../src/runtime-config.js',import.meta.url),'utf8');

test('botão Windows usa rota interna e não URL pública/hardcoded',()=>{
 const download=html.match(/<a\b[^>]*\bid="windows-download-button"[^>]*>/i)?.[0];
 assert.ok(download,'elemento de download obrigatório');
 assert.doesNotMatch(download,/github\.com|api\.github|token|Bearer|releases\/latest|raw\/refs/i);
 assert.match(html,/windowsDownload\.href=basePath\+'\/api\/windows\/download'/);
 assert.match(html,/\/api\/windows\/download\/status/);
 assert.match(html,/data\.available === true/);
});

test('API exige sessão autorizada e não expõe diretório share',()=>{
 assert.match(route,/currentUser\(request\)/);
 assert.match(route,/\['gerente', 'master'\]/);
 assert.match(route,/!!user\.restaurante_id/);
 assert.match(route,/\/api\/windows\/download'/);
 assert.match(route,/Content-Disposition/);
 assert.match(route,/Cache-Control/);
 assert.doesNotMatch(html,/\/share\//);
 assert.match(server,/fastify\.register\(windowsDownloadRoutes\)/);
});

test('caminho ZIP configurável no HA e via variável no servidor final',()=>{
 assert.match(options,/windows_zip_path: "\/share\/avisaqui\/windows\/Avisaqui-Windows\.zip"/);
 assert.match(options,/windows_zip_path: str\?/);
 assert.match(bootstrap,/options\.windows_zip_path/);
 assert.match(bootstrap,/env\.WINDOWS_ZIP_PATH/);
});

test('metadata Windows traz versão configurável e horário real do ZIP',()=>{
 assert.match(options,/windows_zip_version: ""/);
 assert.match(options,/windows_zip_version: str\?/);
 assert.match(bootstrap,/options\.windows_zip_version/);
 assert.match(route,/file_updated_at: zip \? zip\.metadata\.mtime\.toISOString\(\) : null/);
 assert.match(route,/version: zip/);
 assert.match(html,/id="windows-release-metadata"/);
 assert.match(html,/data\.file_updated_at/);
 assert.match(html,/data\.version/);
});

test('ZIP Windows inválido nunca bloqueia inicialização web',async()=>{
 const {configureRuntime}=await import('../src/runtime-config.js');
 for(const value of ['arquivo.zip','/tmp/arquivo.txt','',null]){
  const env={DATA_PATH:'/tmp/avisaqui-inexistente-windows-zip-gate',WINDOWS_ZIP_PATH:value,
   AVISAQUI_PAIR_V1_ENABLED:'false'};
  assert.doesNotThrow(()=>configureRuntime(env));
  assert.equal(env.WINDOWS_ZIP_PATH,'');
 }
 const env={DATA_PATH:'/tmp/avisaqui-inexistente-windows-zip-gate',
  WINDOWS_ZIP_PATH:'/share/avisaqui/windows/Avisaqui-Windows.zip',
  AVISAQUI_PAIR_V1_ENABLED:'false'};
 assert.doesNotThrow(()=>configureRuntime(env));
 assert.equal(env.WINDOWS_ZIP_PATH,'/share/avisaqui/windows/Avisaqui-Windows.zip');
});

test('caminho ZIP explicitamente desabilitado não volta ao ZIP padrão',()=>{
 assert.match(route,/if \(env\.WINDOWS_ZIP_PATH === undefined\) return DEFAULT_ZIP_PATH/);
 assert.match(route,/typeof env\.WINDOWS_ZIP_PATH === 'string'/);
 assert.doesNotMatch(route,/env\.WINDOWS_ZIP_PATH \|\| DEFAULT_ZIP_PATH/);
});
