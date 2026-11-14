// Uso explícito pelo administrador do servidor, sem senha ou conta predefinida.
// BIPOU_INITIAL_LOGIN=... BIPOU_INITIAL_PASSWORD=... node scripts/bootstrap-admin.js
import { randomUUID } from 'node:crypto';
import db from '../src/db.js';
import { passwordHash } from '../src/auth.js';

const existing = db.prepare("SELECT COUNT(*) AS count FROM usuarios WHERE papel = 'master'").get().count;
if (existing > 0) {
  console.error('Master Admin já existe. Inicialização recusada.');
  process.exitCode = 1;
} else {
  const login = (process.env.BIPOU_INITIAL_LOGIN || '').trim().toLowerCase();
  const senha = process.env.BIPOU_INITIAL_PASSWORD || '';
  if (!/^[a-z0-9._@-]{3,120}$/.test(login)) {
    console.error('Informe BIPOU_INITIAL_LOGIN válido (3-120 caracteres).');
    process.exitCode = 1;
  } else {
    try {
      const hash = await passwordHash(senha);
      const now = Date.now();
      db.prepare(`
        INSERT INTO usuarios (id, restaurante_id, nome, login, senha_hash, papel, criado_em, atualizado_em)
        VALUES (?, NULL, ?, ?, ?, 'master', ?, ?)
      `).run(randomUUID(), 'Administração da plataforma', login, hash, now, now);
      console.log('Master Admin inicializado. Senha não exibida.');
    } catch (err) {
      console.error('Não foi possível inicializar Master Admin:', err.message);
      process.exitCode = 1;
    }
  }
}
delete process.env.BIPOU_INITIAL_PASSWORD;
db.close();
