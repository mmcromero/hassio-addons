import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';

const temporaryDir = mkdtempSync(path.join(tmpdir(), 'bipou-auth-schema-'));
process.env.DATA_PATH = temporaryDir;

const { default: db } = await import('../src/db.js');
db.prepare("INSERT INTO restaurantes (id, nome, slug, created_at) VALUES (?, ?, ?, ?)").run(
  'rest-auth-test', 'Restaurante de teste', 'rest-auth-test', Date.now()
);

try {
  test('esquema mantém pedidos e restaurantes existentes', () => {
    assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE name='pedidos'").get());
    assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE name='restaurantes'").get());
    assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE name='usuarios'").get());
    assert.ok(db.prepare("SELECT name FROM sqlite_master WHERE name='sessoes'").get());
  });

  test('não cria administrador ou senha padrão', () => {
    assert.equal(db.prepare('SELECT count(*) as n FROM usuarios').get().n, 0);
  });

  test('Master Admin deve ser global e gerente deve ter restaurante', () => {
    const now = Date.now();
    const insert = db.prepare(
      'INSERT INTO usuarios (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    );
    insert.run('master-test', null, 'Admin de teste', 'admin-teste', 'hash-sintetico', 'master', now, now);
    assert.throws(() => insert.run('master-invalido', 'rest-auth-test', 'Admin inválido', 'admin-invalido', 'hash-sintetico', 'master', now, now));
    assert.throws(() => insert.run('gerente-invalido', null, 'Gerente inválido', 'gerente-invalido', 'hash-sintetico', 'gerente', now, now));
    insert.run('gerente-test', 'rest-auth-test', 'Gerente de teste', 'gerente-teste', 'hash-sintetico', 'gerente', now, now);
    assert.equal(db.prepare("SELECT restaurante_id FROM usuarios WHERE id='gerente-test'").get().restaurante_id, 'rest-auth-test');
  });

  test('não aceita login duplicado nem papel desconhecido', () => {
    const now = Date.now();
    const insert = db.prepare(
      'INSERT INTO usuarios (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em) VALUES (?, ?, ?, ?, ?, ?, ?, ?)'
    );
    assert.throws(() => insert.run('outro-admin', null, 'Admin duplicado', 'admin-teste', 'hash-sintetico', 'master', now, now));
    assert.throws(() => insert.run('papel-invalido', null, 'Papel inválido', 'papel-invalido', 'hash-sintetico', 'superadmin', now, now));
  });

  test('sessão vinculada a usuário e token hash não duplicado', () => {
    const now = Date.now();
    const insert = db.prepare(
      'INSERT INTO sessoes (id, usuario_id, token_hash, criado_em, expira_em) VALUES (?, ?, ?, ?, ?)'
    );
    insert.run('sessao-1', 'master-test', 'hash-token-1', now, now + 1000);
    assert.throws(() => insert.run('sessao-2', 'master-test', 'hash-token-1', now, now + 1000));
    assert.throws(() => insert.run('sessao-3', 'usuario-inexistente', 'hash-token-3', now, now + 1000));
  });
} finally {
  // O runner executa os testes após a definição; limpeza fica em after().
}

import { after } from 'node:test';
after(() => {
  db.close();
  rmSync(temporaryDir, { recursive: true, force: true });
});
