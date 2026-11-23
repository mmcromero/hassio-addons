import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

export type AppMode = 'local' | 'home-assistant';
const projectRoot = fileURLToPath(new URL('../', import.meta.url));

export function loadConfig(env: NodeJS.ProcessEnv = process.env) {
  // Retain the former HA flag while keeping local execution safe by default.
  if (env.INGRESS_ONLY !== undefined && !['true', 'false'].includes(env.INGRESS_ONLY)) {
    throw new Error('INGRESS_ONLY deve ser true ou false.');
  }
  const mode = env.APP_MODE ?? (env.INGRESS_ONLY === 'true' ? 'home-assistant' : 'local');
  if (mode !== 'local' && mode !== 'home-assistant') {
    throw new Error('APP_MODE deve ser local ou home-assistant.');
  }
  const host = env.HOST ?? (mode === 'home-assistant' ? '0.0.0.0' : '127.0.0.1');
  if (mode === 'local' && !['127.0.0.1', '::1'].includes(host)) {
    throw new Error('Modo local sem autenticação permite apenas HOST de loopback.');
  }
  const portText = env.PORT ?? '8099';
  const port = Number(portText);
  if (!/^\d+$/.test(portText) || !Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('PORT deve ser um inteiro entre 1 e 65535.');
  }
  if (env.DATA_DIR !== undefined && !env.DATA_DIR.trim()) {
    throw new Error('DATA_DIR não pode ser vazio.');
  }
  return {
    mode: mode as AppMode,
    host,
    port,
    dataDir: resolve(env.DATA_DIR ?? (mode === 'home-assistant' ? '/data' : resolve(projectRoot, '.local-data'))),
    staticDir: resolve(projectRoot, 'dist'),
  };
}
