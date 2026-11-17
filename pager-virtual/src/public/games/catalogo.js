// Biblioteca independente: manifesto descritivo e carregamento somente sob demanda.
const ID_VALIDO = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
const ARQUIVO_VALIDO = /^\.\/[a-z0-9-]+\.js$/;
const VERSAO_VALIDA = /^\d+\.\d+\.\d+(?:-[a-z0-9.-]+)?$/;
const MODOS = new Set(['solo','dupla-local','multiplayer-simulado','multiplayer-online']);
const ORIENTACOES = new Set(['retrato','paisagem','livre']);

export function validarCatalogo(dados) {
  if (!dados || dados.schemaVersion !== 1 || !VERSAO_VALIDA.test(dados.catalogVersion || '') ||
      !Array.isArray(dados.games)) throw new Error('Catálogo incompatível');
  const ids = new Set();
  return dados.games.map(jogo => {
    if (!jogo || typeof jogo.id !== 'string' || !ID_VALIDO.test(jogo.id) ||
        typeof jogo.title !== 'string' || !jogo.title.trim() ||
        typeof jogo.version !== 'string' || !VERSAO_VALIDA.test(jogo.version) ||
        (['construction','external'].includes(jogo.status) ? jogo.module !== undefined : (typeof jogo.module !== 'string' || !ARQUIVO_VALIDO.test(jogo.module))) ||
        !Array.isArray(jogo.modes) || (jogo.status === 'experimental' && !jogo.modes.length) ||
        jogo.modes.some(m => !MODOS.has(m)) || new Set(jogo.modes).size !== jogo.modes.length ||
        !Number.isSafeInteger(jogo.minPlayers) || jogo.minPlayers < 1 ||
        !Number.isSafeInteger(jogo.maxPlayers) || jogo.maxPlayers < jogo.minPlayers ||
        typeof jogo.requiresServer !== 'boolean' || !ORIENTACOES.has(jogo.orientation) ||
        ids.has(jogo.id)) throw new Error('Entrada de jogo inválida');
    ids.add(jogo.id);
    return Object.freeze({ ...jogo, modes: Object.freeze([...jogo.modes]) });
  });
}

export async function obterCatalogo({ fetcher = fetch, url = new URL('./manifest.json', import.meta.url) } = {}) {
  const resposta = await fetcher(url, { cache: 'no-cache', credentials: 'omit' });
  if (!resposta.ok) throw new Error('Catálogo indisponível');
  return validarCatalogo(await resposta.json());
}

export function criarSessaoJogos({ importar = caminho => import(caminho) } = {}) {
  let geracao = 0, destruirAtual = null;
  return {
    async abrir(jogo, container, opcoes = {}) {
      const atual = ++geracao;
      if (destruirAtual) { const anterior = destruirAtual; destruirAtual = null; anterior(); }
      if (!jogo || jogo.status !== 'experimental' || !ARQUIVO_VALIDO.test(jogo.module)) throw new Error('Jogo indisponível');
      const modulo = await importar(new URL(jogo.module, import.meta.url).href);
      if (atual !== geracao) return false;
      const iniciar = modulo.iniciarJogo;
      if (typeof iniciar !== 'function') throw new Error('Módulo incompatível');
      const encerrar = iniciar({ ...opcoes, container });
      if (typeof encerrar !== 'function') throw new Error('Jogo sem encerramento');
      if (atual !== geracao) { encerrar(); return false; }
      destruirAtual = encerrar;
      return true;
    },
    pausar() { destruirAtual?.pausar?.(); },
    retomar() { destruirAtual?.retomar?.(); },
    encerrar() {
      geracao++;
      if (destruirAtual) { const destruir = destruirAtual; destruirAtual = null; destruir(); }
    }
  };
}
