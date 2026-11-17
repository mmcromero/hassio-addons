// Biblioteca opcional. Somente a página principal controla o Pong e o estado do pedido.
import { obterCatalogo } from './catalogo.js';
import { newInstanceId, createEnvelope, validateEnvelope, createRateLimiter } from './protocolo-v1.js';

export function criarBibliotecaJogos({ container, iniciarPong, onExit = () => {}, etiquetaPedido = 'Pedido em preparo' } = {}) {
  if (!(container instanceof HTMLElement)) throw new TypeError('Container inválido');
  let ativa = true, geracao = 0, sairPong = null;
  const scrollAnterior = window.scrollY;
  const estilos = document.createElement('style');
  estilos.textContent = "#game-screen{position:fixed;inset:0;z-index:1000;background:#071320;display:flex;flex-direction:column;width:100vw;height:100vh;height:100dvh;overflow:hidden}\n#game-screen .game-top{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:calc(6px + env(safe-area-inset-top,0px)) 12px 7px;background:#111d2d;border-bottom:1px solid #334155;font-size:.85rem}\n#game-screen .game-top strong{font-size:.9rem}#game-screen .game-top .secondary{padding:7px 12px;font-size:.85rem}\n#game-screen .game-body{flex:1 1 auto;min-height:0;min-width:0;display:flex;align-items:center;justify-content:center;padding:6px;overflow:auto}\n#game-screen #stage{width:100%;height:100%;min-height:0;display:flex;align-items:center;justify-content:center}\n#game-screen #stage>section{width:100%;max-width:100%;max-height:100%;overflow:auto}\n#game-screen #stage>section>div:not([hidden]){max-width:100%}\n#game-screen #stage canvas{width:100%;height:auto;max-height:calc(100dvh - 115px);object-fit:contain}\n#game-screen .game-foot{display:flex;justify-content:center;gap:8px;align-items:center;flex:0 0 auto;padding:5px 10px calc(5px + env(safe-area-inset-bottom,0px));font-size:.75rem;color:#94a3b8}\n#rotate-hint{display:none;text-align:center;padding:12px;background:#182b3d;color:#fff}\n@media(orientation:portrait){#game-screen.landscape #rotate-hint{display:block}#game-screen.landscape .game-body{display:none}}\nbody.game-active{overflow:hidden}\n#game-screen #stage canvas{max-width:none!important}#game-screen #stage>section h3{margin:3px 0;font-size:1rem}#game-screen #stage>section p{margin:5px 0;font-size:.85rem}#game-screen #stage>section button{padding:8px 12px}#game-screen #stage>section>div{max-width:100%}\n#game-screen .game-body{overflow:hidden;padding:4px}\n#game-screen #stage{overflow:hidden;align-items:stretch;justify-content:stretch}\n#game-screen #stage>.pong-root{height:100%;width:100%;max-height:100%;overflow:hidden;display:flex;flex-direction:column}\n#game-screen #stage>.pong-root>.pong-partida:not([hidden]){flex:1 1 auto;min-height:0;min-width:0;display:flex;flex-direction:column;overflow:hidden}\n#game-screen #stage .pong-arena{flex:1 1 auto;max-width:none!important;min-height:0;height:100%}\n#game-screen #stage .pong-arena canvas{width:100%!important;height:100%!important;max-height:none!important;max-width:none!important;object-fit:fill}\n#game-screen #stage>.pong-root>div:first-child:not([hidden]){margin:auto;width:min(420px,100%);padding:12px}\n#game-screen .game-foot{display:none}\n#game-screen .game-top{padding:calc(4px + env(safe-area-inset-top,0px)) 10px 4px}\n#game-screen .game-top .secondary{padding:5px 10px}\n@media(orientation:portrait){#game-screen.landscape .game-body{display:none}}\n/* Pong: a arena e o painel ocupam a mesma faixa horizontal, sem barras acima/abaixo. */\n#game-screen.landscape{flex-direction:row;align-items:stretch}\n#game-screen.landscape .game-top{order:2;flex:0 0 clamp(132px,18vw,205px);width:clamp(132px,18vw,205px);min-width:0;display:flex;flex-direction:column;align-items:stretch;justify-content:flex-start;gap:10px;padding:10px 8px;background:#152237;border:0;border-left:1px solid #334155;overflow-y:auto}\n#game-screen.landscape .game-top>div{display:flex;flex-direction:column;gap:6px;overflow-wrap:anywhere}\n#game-screen.landscape .game-top .secondary{width:100%;min-height:40px}\n#game-screen.landscape .game-body{order:1;flex:1 1 auto;min-width:0;min-height:0;padding:3px;overflow:hidden}\n#game-screen.landscape #stage,#game-screen.landscape .pong-root,#game-screen.landscape .pong-partida{height:100%;min-height:0}\n#game-screen.landscape .pong-arena{height:100%;min-height:0}\n#game-screen.landscape .pong-arena canvas{height:100%!important;max-height:none!important}\n#game-screen.landscape .game-sim{display:block}\n.game-sim{display:none}\n#game-screen .game-sim{margin-top:auto;font-size:.75rem;color:#94a3b8}\n#game-screen .game-sim button{font-size:.75rem;line-height:1.15;padding:8px 5px;white-space:normal}\n#rotate-hint{position:absolute;inset:0;z-index:5;align-items:center;justify-content:center;flex-direction:column;gap:18px;padding:24px;text-align:center;background:#091626;color:white}\n#rotate-hint .rotate-icon{font-size:clamp(65px,17vw,110px);line-height:1}\n#rotate-hint strong{font-size:clamp(1.6rem,7vw,2.5rem)}\n#rotate-hint p{font-size:1.05rem;max-width:330px;line-height:1.5;margin:0}\n#rotate-hint button{font-size:1rem;padding:12px 22px}\n@media(orientation:portrait){#game-screen.landscape #rotate-hint{display:flex}#game-screen.landscape .game-body{display:none}#game-screen.landscape .game-top{position:static;flex:0 0 auto;width:auto;order:1;display:none}}\n@media(orientation:landscape){#game-screen.landscape #rotate-hint{display:none}}\n/* Isolamento de rolagem somente durante a partida. */\nhtml:has(body.game-active),body.game-active{overflow:hidden!important;overscroll-behavior:none!important}\nbody.game-active{position:fixed;inset:0;width:100%;height:var(--game-viewport-height,100dvh);touch-action:none}\n#game-screen{top:0;left:0;right:auto;bottom:auto;width:var(--game-viewport-width,100vw);height:var(--game-viewport-height,100dvh);max-width:100%;max-height:100%;overflow:hidden!important;overscroll-behavior:none;touch-action:none}\n#game-screen .game-body,#game-screen #stage,#game-screen .pong-root,#game-screen .pong-partida,#game-screen .pong-arena{overscroll-behavior:none;touch-action:none}\n#game-screen.landscape .game-top{overflow:hidden;min-height:0;gap:clamp(3px,1.4vh,10px);padding:clamp(3px,1.4vh,10px) 6px}\n#game-screen.landscape .game-top .secondary{min-height:0;padding:clamp(4px,1vh,9px) 5px}\n#game-screen.landscape .game-sim{margin-top:auto}\n#game-screen .hub{height:100%;width:100%;display:flex;flex-direction:column;min-height:0;gap:8px;padding:8px;overflow:hidden}\n#game-screen .hub h2{font-size:clamp(1.1rem,3vw,1.6rem);margin:0}\n#game-screen .hub .hub-list{flex:1;min-height:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:center}\n#game-screen .hub .hub-card{display:flex;flex-direction:column;justify-content:space-between;gap:6px;min-width:0;min-height:0;padding:clamp(8px,2vw,16px);border:1px solid #52677e;border-radius:14px;background:#20334b}\n#game-screen .hub .hub-card h3{margin:0;font-size:clamp(1rem,2.5vw,1.4rem)}\n#game-screen .hub .hub-card p{margin:0;font-size:clamp(.75rem,1.6vw,.95rem);color:#cbd5e1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}\n#game-screen .hub .hub-card button{width:100%;padding:9px}\n#game-screen .hub .hub-status{font-size:.8rem;color:#cbd5e1;min-height:1em}\n#game-screen.landscape #stage>.hub{max-height:100%;overflow:hidden}\n#game-screen.landscape .game-top{touch-action:manipulation}\n#game-screen.landscape .game-body{touch-action:manipulation}\n#game-screen.landscape .pong-arena{touch-action:none}\n@media(max-width:550px) and (orientation:landscape){#game-screen .hub .hub-card p{display:none}}\n[hidden]{display:none!important}\n#game-screen #stage>.velha-root{height:100%;width:100%;min-height:0;max-height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center}\n#game-screen #stage .velha-root>div:not([hidden]){max-height:100%;min-height:0;box-sizing:border-box}\n#game-screen #stage .velha-root button{touch-action:manipulation}\n\n\n#game-screen .games-scene{width:100%;height:100%;min-height:0;display:flex;flex-direction:column;padding:8px;overflow:hidden}\n#game-screen .games-scene h2{margin:0 0 8px;font-size:clamp(1.1rem,3vw,1.5rem)}\n#game-screen .games-scene .games-list{flex:1;min-height:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:center;overflow:auto}\n#game-screen .games-scene .games-list article{border:1px solid #52677e!important;border-radius:14px!important;background:#20334b;min-width:0;padding:clamp(8px,2vw,16px)!important;color:#f8fafc}\n#game-screen .games-scene .games-list button{background:#2563eb;color:#fff;border:0;border-radius:10px;min-height:40px;font-weight:700}\n#game-screen .games-scene .games-stage{flex:1;min-height:0;min-width:0;width:100%;display:flex;align-items:stretch;justify-content:center;overflow:hidden}\n#game-screen .games-scene .games-stage iframe{height:100%!important;min-height:0!important;background:#102b39}\n#game-screen .games-scene .games-back{align-self:flex-start;background:#24344e;border:1px solid #64748b;border-radius:10px;color:white;padding:8px 14px}\n#game-screen .games-scene [role=status]{font-size:.85rem;color:#cbd5e1}\n#game-screen .game-top .games-close{background:#24344e;border:1px solid #64748b;border-radius:10px;color:white;padding:8px}\n";
  const tela = document.createElement('section');
  tela.id = 'game-screen';
  tela.className = 'landscape';
  tela.setAttribute('aria-label', 'Jogos em tela cheia');
  const topo = document.createElement('div');
  topo.className = 'game-top';
  const tituloTopo = document.createElement('strong'); tituloTopo.textContent = '🔔 ' + etiquetaPedido;
  const sairTodos = document.createElement('button'); sairTodos.type = 'button';
  sairTodos.className = 'games-close'; sairTodos.textContent = '✕ Sair';
  sairTodos.addEventListener('click', () => encerrar());
  topo.append(tituloTopo, sairTodos);
  const avisoRotacao = document.createElement('div');
  avisoRotacao.id = 'rotate-hint';
  const iconeRotacao = document.createElement('span'); iconeRotacao.className = 'rotate-icon'; iconeRotacao.textContent = '📱↻';
  const tituloRotacao = document.createElement('strong'); tituloRotacao.textContent = 'Gire o celular';
  const textoRotacao = document.createElement('p'); textoRotacao.textContent = 'Vire o aparelho para escolher um jogo e começar a diversão.';
  const sairRotacao = document.createElement('button'); sairRotacao.type = 'button';
  sairRotacao.textContent = '✕ Sair do jogo'; sairRotacao.addEventListener('click', () => encerrar());
  avisoRotacao.append(iconeRotacao, tituloRotacao, textoRotacao, sairRotacao);
  const corpo = document.createElement('div'); corpo.className = 'game-body';
  const cenario = document.createElement('div'); cenario.id = 'stage';
  corpo.append(cenario);
  tela.append(estilos, topo, avisoRotacao, corpo);
  function ajustarViewport() {
    if (!ativa) return;
    const vp = window.visualViewport;
    tela.style.setProperty('--game-viewport-width', Math.max(1, Math.floor(vp?.width || window.innerWidth)) + 'px');
    tela.style.setProperty('--game-viewport-height', Math.max(1, Math.floor(vp?.height || window.innerHeight)) + 'px');
    tela.style.transform = vp ? 'translate(' + Math.round(vp.offsetLeft) + 'px,' + Math.round(vp.offsetTop) + 'px)' : 'none';
  }
  window.addEventListener('resize', ajustarViewport, { passive: true });
  window.addEventListener('orientationchange', ajustarViewport, { passive: true });
  window.visualViewport?.addEventListener('resize', ajustarViewport, { passive: true });
  window.visualViewport?.addEventListener('scroll', ajustarViewport, { passive: true });
  document.body.classList.add('game-active');
  ajustarViewport();
  let pararIsolado = null;
  const raiz = document.createElement('section'); raiz.className = 'games-scene';
  raiz.setAttribute('aria-label', 'Biblioteca de jogos');
  const titulo = document.createElement('h2'); titulo.textContent = '🎮 Biblioteca de jogos';
  const aviso = document.createElement('p'); aviso.setAttribute('role', 'status'); aviso.textContent = 'Carregando biblioteca...';
  const lista = document.createElement('div'); lista.className = 'games-list';
  lista.style.cssText = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0';
  const palco = document.createElement('div'); palco.className = 'games-stage'; palco.hidden = true;
  const voltar = document.createElement('button'); voltar.type = 'button'; voltar.textContent = 'Voltar à biblioteca'; voltar.hidden = true; voltar.className = 'games-back';
  voltar.dataset.gamesBack = 'true';
  voltar.style.cssText = 'margin:12px 0;padding:10px';
  function parar() {
    geracao++;
    const pararFrame = pararIsolado; pararIsolado = null;
    try { pararFrame?.(); } catch { /* remoção do iframe continua abaixo */ }
    const sair = sairPong; sairPong = null;
    try { sair?.(); } catch { /* limpeza da interface deve continuar */ }
    palco.replaceChildren();
    palco.hidden = true;
    lista.hidden = false; voltar.hidden = true;
  }
  voltar.addEventListener('click', () => { parar(); aviso.textContent = 'Escolha um jogo.'; });
  raiz.append(titulo, aviso, lista, voltar, palco);
  cenario.append(raiz);
  document.body.append(tela);
  async function jogar(jogo, modo) {
    if (!ativa) return;
    parar();
    const atual = ++geracao;
    lista.hidden = true; palco.hidden = false; voltar.hidden = false; aviso.textContent = 'Carregando jogo...';
    try {
      if (jogo.id === 'pong' && modo === 'dupla') {
        // Apenas o controlador privilegiado inicia a partida online.
        if (typeof iniciarPong !== 'function') throw new Error('Pong indisponível');
        const encerrar = await iniciarPong(palco, modo);
        if (!ativa || atual !== geracao) { encerrar?.(); return; }
        sairPong = encerrar;
      } else {
        const local = jogo.id === 'pong' || jogo.id === 'jogo-da-velha';
        if (!local || !['solo', 'dupla-local'].includes(modo)) throw new Error('Jogo indisponível');
        const frame = document.createElement('iframe');
        frame.title = jogo.id === 'pong' ? 'Pong' : 'Jogo da Velha';
        frame.setAttribute('sandbox', 'allow-scripts');
        frame.setAttribute('referrerpolicy', 'no-referrer');
        frame.style.cssText = 'display:block;width:100%;height:min(64dvh,520px);min-height:320px;border:0;border-radius:12px';
        frame.src = new URL(jogo.id === 'pong'
          ? './pong-local-isolado.html' : './jogo-da-velha-isolado.html', import.meta.url).href;
        const canal = new MessageChannel();
        const instanceId = newInstanceId();
        const allowMessage = createRateLimiter();
        let parado = false, iniciado = false, lastSequence = -1, nextSequence = 0;
        const timeout = setTimeout(() => {
          if (parado || !ativa || atual !== geracao || iniciado) return;
          parar();
          aviso.textContent = 'O jogo não respondeu. Verifique o carregamento e tente novamente.';
        }, 8000);
        const limpar = () => {
          if (parado) return;
          parado = true;
          clearTimeout(timeout);
          canal.port1.close();
          canal.port2.close();
          frame.remove();
        };
        pararIsolado = limpar;
        canal.port1.onmessage = event => {
          if (parado || !ativa || atual !== geracao) return;
          const d = event.data;
          if (!allowMessage() || !validateEnvelope(d, {
            role: 'frame', state: iniciado ? 'RUNNING' : 'WAIT_READY', instanceId, lastSequence
          })) {
            parar();
            aviso.textContent = 'Comunicação do jogo encerrada.';
            return;
          }
          lastSequence = d.sequence;
          if (d.type === 'GAME_READY') {
            iniciado = true;
            clearTimeout(timeout);
            aviso.textContent = '';
            canal.port1.postMessage(createEnvelope({ type: 'GAME_START', instanceId, sequence: nextSequence++, payload: { mode: modo } }));
          } else if (d.type === 'GAME_EXIT' || d.type === 'GAME_ERROR') {
            parar();
            aviso.textContent = d.type === 'GAME_ERROR' ? 'O jogo apresentou um erro.' : 'Escolha um jogo.';
          }
        };
        frame.addEventListener('load', () => {
          if (parado || !ativa || atual !== geracao) return;
          // Origem opaca do sandbox: '*' é necessário somente no envio inicial da porta.
          // Não há credenciais, tokens ou dados de pedido no payload.
          try { frame.contentWindow.postMessage({ type: 'AVISAQUI_GAME_INIT', instanceId }, '*', [canal.port2]); }
          catch { if (ativa && atual === geracao) { parar(); aviso.textContent = 'Não foi possível iniciar o jogo.'; } }
        }, { once: true });
        frame.addEventListener('error', () => {
          if (!parado && ativa && atual === geracao) {
            parar();
            aviso.textContent = 'Falha ao carregar o arquivo do jogo.';
          }
        }, { once: true });
        palco.append(frame);
      }
      if (jogo.id === 'pong') aviso.textContent = '';
    } catch (erro) {
      if (ativa && atual === geracao) {
        parar();
        // Não vazar URL, token, sessão nem resposta HTTP de terceiros.
        const mensagem = erro instanceof Error && /^Pong indisponível/.test(erro.message)
          ? erro.message : 'Não foi possível abrir o jogo. Tente novamente.';
        aviso.textContent = mensagem;
      }
    }
  }
  const pronto = (async () => {
    try {
      const jogos = await obterCatalogo();
      if (!ativa) return;
      // O hub aprovado exibe apenas jogos que podem ser abertos.
      // Jogos em desenvolvimento continuam no manifesto para futuras versões.
      for (const jogo of jogos.filter(item => item.status !== 'construction')) {
        const card = document.createElement('article');
        card.style.cssText = 'border:1px solid #64748b;border-radius:12px;padding:10px;min-width:0';
        const nome = document.createElement('h3'); nome.textContent = jogo.title; nome.style.cssText = 'font-size:1rem;margin:4px 0';
        const descricao = document.createElement('p'); descricao.textContent = jogo.description || '';
        descricao.style.cssText = 'font-size:.85rem;margin:6px 0';
        card.append(nome, descricao);
        if (jogo.status === 'construction') {
          const etiqueta = document.createElement('p'); etiqueta.textContent = '🚧 Em construção';
          etiqueta.style.cssText = 'font-size:.85rem;font-weight:700';
          card.append(etiqueta);
        } else {
          // A escolha de 1 ou 2 jogadores locais ocorre dentro do jogo,
          // conforme o protótipo navegável aprovado.
          const modos = jogo.id === 'pong'
            ? [['solo', 'Jogar'], ['dupla', 'Duelo online']]
            : [['solo', 'Jogar']];
          for (const [modo, legenda] of modos) {
            const botao = document.createElement('button');
            botao.type = 'button'; botao.textContent = legenda;
            botao.style.cssText = 'width:100%;padding:9px;margin:3px 0;white-space:normal';
            botao.addEventListener('click', () => void jogar(jogo, modo));
            card.append(botao);
          }
        }
        lista.append(card);
      }
      aviso.textContent = 'Escolha um jogo.';
    } catch {
      if (ativa) aviso.textContent = 'Não foi possível carregar a biblioteca. O pedido continua disponível.';
    }
  })();
  function encerrar() {
    if (!ativa) return;
    ativa = false;
    parar();
    window.removeEventListener('resize', ajustarViewport);
    window.removeEventListener('orientationchange', ajustarViewport);
    window.visualViewport?.removeEventListener('resize', ajustarViewport);
    window.visualViewport?.removeEventListener('scroll', ajustarViewport);
    tela.remove();
    document.body.classList.remove('game-active');
    window.scrollTo(0, scrollAnterior);
    onExit();
  }
  return Object.freeze({ encerrar, pronto });
}
