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
  // Caminho de administrador, lido das opções do Home Assistant ou do ambiente final.
  // Apenas o servidor acessa este caminho; o navegador usa a rota protegida.
  if (env.WINDOWS_ZIP_PATH === undefined && typeof options.windows_zip_path === 'string')
    env.WINDOWS_ZIP_PATH = options.windows_zip_path;
  if (env.WINDOWS_ZIP_PATH === undefined) env.WINDOWS_ZIP_PATH = '/share/avisaqui/windows/Avisaqui-Windows.zip';
  if (env.WINDOWS_ZIP_VERSION === undefined && typeof options.windows_zip_version === 'string')
    env.WINDOWS_ZIP_VERSION = options.windows_zip_version;
  // O ZIP Windows é uma distribuição independente: nenhuma configuração
  // inválida ou arquivo ausente pode impedir inicialização do WEB/HA.
  // A rota /api/windows/download/status deve retornar available:false.
  // Nunca usar o caminho inválido para acessar o sistema de arquivos.
  if (typeof env.WINDOWS_ZIP_PATH !== 'string' || !path.isAbsolute(env.WINDOWS_ZIP_PATH) ||
      env.WINDOWS_ZIP_PATH.includes(String.fromCharCode(0)) ||
      !env.WINDOWS_ZIP_PATH.toLowerCase().endsWith('.zip'))
    env.WINDOWS_ZIP_PATH = '';
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
