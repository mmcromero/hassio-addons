import fs from 'node:fs';
import path from 'node:path';

// A imagem inicia Node diretamente; validar antes de importar auth/SQLite.
export function configureRuntime(env = process.env) {
  const file = path.join(env.DATA_PATH || '/data', 'options.json');
  let options = {};
  if (fs.existsSync(file)) {
    try { options = JSON.parse(fs.readFileSync(file, 'utf8')); }
    catch { throw new Error('Não foi possível ler as opções do add-on'); }
    if (!options || typeof options !== 'object' || Array.isArray(options))
      throw new Error('Opções do add-on inválidas');
  }
  const enabled = env.AVISAQUI_PAIR_V1_ENABLED ?? options.pair_v1_enabled ?? false;
  if (![true, false, 'true', 'false'].includes(enabled))
    throw new Error('pair_v1_enabled deve ser booleano');
  env.AVISAQUI_PAIR_V1_ENABLED = String(enabled);
  if (env.PUBLIC_URL === undefined && typeof options.public_url === 'string')
    env.PUBLIC_URL = options.public_url;
  if (env.LOG_LEVEL === undefined && typeof options.log_level === 'string')
    env.LOG_LEVEL = options.log_level;
  if (env.AVISAQUI_PAIR_V1_ENABLED !== 'true') return;
  const origin = env.AVISAQUI_PAIR_V1_PUBLIC_ORIGIN ?? env.PUBLIC_URL;
  let url;
  try { url = new URL(origin); } catch { throw new Error('Pair-v1 requer origem HTTPS explícita'); }
  if (url.protocol !== 'https:' || url.username || url.password || url.search || url.hash ||
      !['/avisaqui', '/avisaqui/'].includes(url.pathname) ||
      !env.PUBLIC_URL || origin.replace(/\/$/, '') !== env.PUBLIC_URL.replace(/\/$/, ''))
    throw new Error('Pair-v1 requer public_url HTTPS /avisaqui compatível');
  env.AVISAQUI_PAIR_V1_PUBLIC_ORIGIN = origin;
  const prefix = env.AVISAQUI_PAIR_V1_MOUNT_PREFIX ?? options.pair_v1_mount_prefix;
  if (!['', '/', '/avisaqui'].includes(prefix))
    throw new Error('Pair-v1 requer prefixo interno explícito: / ou /avisaqui');
  env.AVISAQUI_PAIR_V1_MOUNT_PREFIX = prefix === '/' ? '' : prefix;
  for (const key of ['APPROVAL', 'CHALLENGE', 'RECOVERY']) {
    const name = 'AVISAQUI_PAIR_V1_' + key + '_MS';
    const raw = env[name] ?? options['pair_v1_' + key.toLowerCase() + '_ms'];
    if (typeof raw !== 'string' || !/^[1-9][0-9]*$/.test(raw) ||
        !Number.isSafeInteger(Number(raw)) || Number(raw) <= 1000 || Number(raw) > 7 * 86400000)
      throw new Error('Política temporal pair-v1 inválida ou incompleta: ' + key);
    env[name] = raw;
  }
}
