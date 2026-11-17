import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, existsSync } from 'node:fs';

const root = new URL('../', import.meta.url);
const source = path => readFileSync(new URL(path, root), 'utf8');

test('tela de autorizacao fica empacotada sob src e fora dos arquivos estaticos', () => {
  const relative = 'src/pairing/backend/assets/autorizar-pair-lab.html';
  assert.ok(existsSync(new URL(relative, root)), 'arquivo da tela deve entrar no Docker COPY src/');
  assert.ok(!existsSync(new URL('src/public/autorizar-pair-lab.html', root)), 'evitar GET publico sem autenticar');
  const page = source(relative);
  assert.match(page, /id="form"/);
  assert.match(page, /id="aprovar"/);
  assert.match(page, /id="recusar"/);
  assert.match(page, /api\/agentes\/pareamentos/);
  const handler = source('src/pairing/backend/manager-page-lab.js');
  assert.match(handler, /assets\/autorizar-pair-lab\.html/);
  assert.match(handler, /managerFromRequest/);
  assert.match(handler, /'no-store'/);
});

test('host de laboratorio integra pagina e API com origem e politica explicitas', () => {
  const host = source('src/pairing/backend/integrated-host-lab.js');
  assert.match(host, /parsed\.protocol!=='https:'/);
  assert.match(host, /mountPrefix/);
  assert.match(host, /prefix:mountPrefix/);
  assert.match(host, /Prefixo interno de pareamento nao autorizado/);
  assert.match(host, /buildPairV1ManagerPageLab/);
  assert.match(host, /buildPairV1LabRoutes/);
  const server = source('src/server.js');
  assert.match(server, /AVISAQUI_PAIR_V1_ENABLED === 'true'/,
    'montagem somente em modo opt-in explícito');
  assert.match(server, /await import\('\.\/pairing\/backend\/integrated-host-lab\.js'\)/,
    'importação dinâmica somente após verificar opt-in');
  assert.match(server, /AVISAQUI_PAIR_V1_PUBLIC_ORIGIN/);
  assert.match(server, /AVISAQUI_PAIR_V1_MOUNT_PREFIX/);
  assert.match(server, /approvalMs: durations\[0\]/);
  assert.match(server, /challengeMs: durations\[1\]/);
  assert.match(server, /recoveryMs: durations\[2\]/);
  assert.doesNotMatch(server, /registerPairV1IntegratedLab\(fastify,\s*\{\s*db\s*\}\s*\)/,
    'nao montar pareamento sem política, origem e prefixo explícitos');
});

test('pareamento registra depois do esquema de credenciais legadas', () => {
  const server = source('src/server.js');
  const legacy = source('src/routes/integracao-impressao.js');
  assert.match(legacy, /CREATE TABLE IF NOT EXISTS integracao_impressao_chaves/);
  const registration = server.indexOf('await fastify.register(integracaoImpressaoRoutes)');
  const pairing = server.indexOf("if (process.env.AVISAQUI_PAIR_V1_ENABLED === 'true')");
  assert.ok(registration >= 0 && pairing > registration,
    'a tabela de chaves deve existir antes da migração aditiva pair-v1');
  const migration = source('src/pairing/backend/schema.js');
  assert.match(migration, /ALTER TABLE integracao_impressao_chaves ADD COLUMN dispositivo_id/);
  assert.match(migration, /idx_pair_chaves_dispositivo/);
});

test('schema contempla nome aprovado, limites persistentes e migracao aditiva', () => {
  const schema = source('src/pairing/backend/schema.js');
  assert.match(schema, /caixa_nome_aprovado/);
  assert.match(schema, /integracao_pareamento_limites/);
  assert.match(schema, /ALTER TABLE integracao_pareamento_solicitacoes ADD COLUMN caixa_nome_aprovado/);
});
