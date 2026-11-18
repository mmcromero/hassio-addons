// Biblioteca opcional. Somente a página principal controla o Pong e o estado do pedido.
import { obterCatalogo } from './catalogo.js';
import { ilustracao, etiquetas } from './catalogo-visual.js';
import { newInstanceId, createEnvelope, validateEnvelope, createRateLimiter } from './protocolo-v1.js';

export function criarBibliotecaJogos({ container, iniciarPong, onExit = () => {}, etiquetaPedido = 'Pedido em preparo' } = {}) {
  if (!(container instanceof HTMLElement)) throw new TypeError('Container inválido');
  let ativa = true, geracao = 0, sairPong = null;
  const scrollAnterior = window.scrollY;
  const estilos = document.createElement('style');
  estilos.textContent = "#game-screen{position:fixed;inset:0;z-index:1000;background:#071320;display:flex;flex-direction:column;width:100vw;height:100vh;height:100dvh;overflow:hidden}\n#game-screen .game-top{flex:0 0 auto;display:flex;align-items:center;justify-content:space-between;gap:8px;padding:calc(6px + env(safe-area-inset-top,0px)) 12px 7px;background:#111d2d;border-bottom:1px solid #334155;font-size:.85rem}\n#game-screen .game-top strong{font-size:.9rem}#game-screen .game-top .secondary{padding:7px 12px;font-size:.85rem}\n#game-screen .game-body{flex:1 1 auto;min-height:0;min-width:0;display:flex;align-items:center;justify-content:center;padding:6px;overflow:auto}\n#game-screen #stage{width:100%;height:100%;min-height:0;display:flex;align-items:center;justify-content:center}\n#game-screen #stage>section{width:100%;max-width:100%;max-height:100%;overflow:auto}\n#game-screen #stage>section>div:not([hidden]){max-width:100%}\n#game-screen #stage canvas{width:100%;height:auto;max-height:calc(100dvh - 115px);object-fit:contain}\n#game-screen .game-foot{display:flex;justify-content:center;gap:8px;align-items:center;flex:0 0 auto;padding:5px 10px calc(5px + env(safe-area-inset-bottom,0px));font-size:.75rem;color:#94a3b8}\n#rotate-hint{display:none;text-align:center;padding:12px;background:#182b3d;color:#fff}\n@media(orientation:portrait){#game-screen.landscape #rotate-hint{display:block}#game-screen.landscape .game-body{display:none}}\nbody.game-active{overflow:hidden}\n#game-screen #stage canvas{max-width:none!important}#game-screen #stage>section h3{margin:3px 0;font-size:1rem}#game-screen #stage>section p{margin:5px 0;font-size:.85rem}#game-screen #stage>section button{padding:8px 12px}#game-screen #stage>section>div{max-width:100%}\n#game-screen .game-body{overflow:hidden;padding:4px}\n#game-screen #stage{overflow:hidden;align-items:stretch;justify-content:stretch}\n#game-screen #stage>.pong-root{height:100%;width:100%;max-height:100%;overflow:hidden;display:flex;flex-direction:column}\n#game-screen #stage>.pong-root>.pong-partida:not([hidden]){flex:1 1 auto;min-height:0;min-width:0;display:flex;flex-direction:column;overflow:hidden}\n#game-screen #stage .pong-arena{flex:1 1 auto;max-width:none!important;min-height:0;height:100%}\n#game-screen #stage .pong-arena canvas{width:100%!important;height:100%!important;max-height:none!important;max-width:none!important;object-fit:fill}\n#game-screen #stage>.pong-root>div:first-child:not([hidden]){margin:auto;width:min(420px,100%);padding:12px}\n#game-screen .game-foot{display:none}\n#game-screen .game-top{padding:calc(4px + env(safe-area-inset-top,0px)) 10px 4px}\n#game-screen .game-top .secondary{padding:5px 10px}\n@media(orientation:portrait){#game-screen.landscape .game-body{display:none}}\n/* Pong: a arena e o painel ocupam a mesma faixa horizontal, sem barras acima/abaixo. */\n#game-screen.landscape{flex-direction:row;align-items:stretch}\n#game-screen.landscape .game-top{order:2;flex:0 0 clamp(132px,18vw,205px);width:clamp(132px,18vw,205px);min-width:0;display:flex;flex-direction:column;align-items:stretch;justify-content:flex-start;gap:10px;padding:10px 8px;background:#152237;border:0;border-left:1px solid #334155;overflow-y:auto}\n#game-screen.landscape .game-top>div{display:flex;flex-direction:column;gap:6px;overflow-wrap:anywhere}\n#game-screen.landscape .game-top .secondary{width:100%;min-height:40px}\n#game-screen.landscape .game-body{order:1;flex:1 1 auto;min-width:0;min-height:0;padding:3px;overflow:hidden}\n#game-screen.landscape #stage,#game-screen.landscape .pong-root,#game-screen.landscape .pong-partida{height:100%;min-height:0}\n#game-screen.landscape .pong-arena{height:100%;min-height:0}\n#game-screen.landscape .pong-arena canvas{height:100%!important;max-height:none!important}\n#game-screen.landscape .game-sim{display:block}\n.game-sim{display:none}\n#game-screen .game-sim{margin-top:auto;font-size:.75rem;color:#94a3b8}\n#game-screen .game-sim button{font-size:.75rem;line-height:1.15;padding:8px 5px;white-space:normal}\n#rotate-hint{position:absolute;inset:0;z-index:5;align-items:center;justify-content:center;flex-direction:column;gap:18px;padding:24px;text-align:center;background:#091626;color:white}\n#rotate-hint .rotate-icon{font-size:clamp(65px,17vw,110px);line-height:1}\n#rotate-hint strong{font-size:clamp(1.6rem,7vw,2.5rem)}\n#rotate-hint p{font-size:1.05rem;max-width:330px;line-height:1.5;margin:0}\n#rotate-hint button{font-size:1rem;padding:12px 22px}\n@media(orientation:portrait){#game-screen.landscape #rotate-hint{display:flex}#game-screen.landscape .game-body{display:none}#game-screen.landscape .game-top{position:static;flex:0 0 auto;width:auto;order:1;display:none}}\n@media(orientation:landscape){#game-screen.landscape #rotate-hint{display:none}}\n/* Isolamento de rolagem somente durante a partida. */\nhtml:has(body.game-active),body.game-active{overflow:hidden!important;overscroll-behavior:none!important}\nbody.game-active{position:fixed;inset:0;width:100%;height:var(--game-viewport-height,100dvh);touch-action:none}\n#game-screen{top:0;left:0;right:auto;bottom:auto;width:var(--game-viewport-width,100vw);height:var(--game-viewport-height,100dvh);max-width:100%;max-height:100%;overflow:hidden!important;overscroll-behavior:none;touch-action:none}\n#game-screen .game-body,#game-screen #stage,#game-screen .pong-root,#game-screen .pong-partida,#game-screen .pong-arena{overscroll-behavior:none;touch-action:none}\n#game-screen.landscape .game-top{overflow:hidden;min-height:0;gap:clamp(3px,1.4vh,10px);padding:clamp(3px,1.4vh,10px) 6px}\n#game-screen.landscape .game-top .secondary{min-height:0;padding:clamp(4px,1vh,9px) 5px}\n#game-screen.landscape .game-sim{margin-top:auto}\n#game-screen .hub{height:100%;width:100%;display:flex;flex-direction:column;min-height:0;gap:8px;padding:8px;overflow:hidden}\n#game-screen .hub h2{font-size:clamp(1.1rem,3vw,1.6rem);margin:0}\n#game-screen .hub .hub-list{flex:1;min-height:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:center}\n#game-screen .hub .hub-card{display:flex;flex-direction:column;justify-content:space-between;gap:6px;min-width:0;min-height:0;padding:clamp(8px,2vw,16px);border:1px solid #52677e;border-radius:14px;background:#20334b}\n#game-screen .hub .hub-card h3{margin:0;font-size:clamp(1rem,2.5vw,1.4rem)}\n#game-screen .hub .hub-card p{margin:0;font-size:clamp(.75rem,1.6vw,.95rem);color:#cbd5e1;overflow:hidden;display:-webkit-box;-webkit-line-clamp:3;-webkit-box-orient:vertical}\n#game-screen .hub .hub-card button{width:100%;padding:9px}\n#game-screen .hub .hub-status{font-size:.8rem;color:#cbd5e1;min-height:1em}\n#game-screen.landscape #stage>.hub{max-height:100%;overflow:hidden}\n#game-screen.landscape .game-top{touch-action:manipulation}\n#game-screen.landscape .game-body{touch-action:manipulation}\n#game-screen.landscape .pong-arena{touch-action:none}\n@media(max-width:550px) and (orientation:landscape){#game-screen .hub .hub-card p{display:none}}\n[hidden]{display:none!important}\n#game-screen #stage>.velha-root{height:100%;width:100%;min-height:0;max-height:100%;overflow:hidden;display:flex;align-items:center;justify-content:center}\n#game-screen #stage .velha-root>div:not([hidden]){max-height:100%;min-height:0;box-sizing:border-box}\n#game-screen #stage .velha-root button{touch-action:manipulation}\n\n\n#game-screen .games-scene{width:100%;height:100%;min-height:0;display:flex;flex-direction:column;padding:8px;overflow:hidden}\n#game-screen .games-scene h2{margin:0 0 8px;font-size:clamp(1.1rem,3vw,1.5rem)}\n#game-screen .games-scene .games-list{flex:1;min-height:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-content:center;overflow:auto}\n#game-screen .games-scene .games-list article{border:1px solid #52677e!important;border-radius:14px!important;background:#20334b;min-width:0;padding:clamp(8px,2vw,16px)!important;color:#f8fafc}\n#game-screen .games-scene .games-list button{background:#2563eb;color:#fff;border:0;border-radius:10px;min-height:40px;font-weight:700}\n#game-screen .games-scene .games-stage{flex:1;min-height:0;min-width:0;width:100%;display:flex;align-items:stretch;justify-content:center;overflow:hidden}\n#game-screen .games-scene .games-stage iframe{height:100%!important;min-height:0!important;background:#102b39}\n#game-screen .hub .games-stage{flex:1 1 auto;min-height:0;min-width:0;display:flex;align-items:stretch;justify-content:center;overflow:hidden}\n#game-screen .hub .games-stage iframe{height:100%!important;min-height:0!important;background:#102b39}\n#game-screen .hub .games-back{align-self:flex-start;background:#24344e;border:1px solid #64748b;border-radius:10px;color:white;padding:8px 14px}\n#game-screen .games-scene .games-back{align-self:flex-start;background:#24344e;border:1px solid #64748b;border-radius:10px;color:white;padding:8px 14px}\n#game-screen .games-scene [role=status]{font-size:.85rem;color:#cbd5e1}\n#game-screen .game-top .games-close{background:#24344e;border:1px solid #64748b;border-radius:10px;color:white;padding:8px}\n#game-screen .game-top .game-actions{display:flex;flex-direction:column;align-items:stretch;gap:8px;width:100%}\n#game-screen .game-top .game-actions button{width:100%;min-height:40px;touch-action:manipulation;white-space:normal}\n#game-screen .hub .games-stage{flex:1 1 0;min-height:0;min-width:0;width:100%;overflow:hidden}\n#game-screen .hub .games-stage iframe{height:100%!important;min-height:0!important}\n";
  estilos.textContent += "\n/* Fluxo compartilhado: catálogo e escolha sempre em retrato, sem forçar rotação. */\n#game-screen.game-portrait{flex-direction:column}\n#game-screen.game-portrait .game-top{order:0;flex:0 0 auto;width:100%;display:flex;flex-direction:row;align-items:center;justify-content:space-between;padding:8px 12px;overflow:hidden}\n#game-screen.game-portrait .game-top .game-sim{display:none}\n#game-screen.game-portrait .game-body{order:1;flex:1;min-height:0;padding:12px;overflow:hidden}\n#game-screen.game-portrait #stage{align-items:center;justify-content:center}\n#game-screen .games-choose{width:min(560px,100%);max-height:100%;overflow:auto;padding:12px;touch-action:pan-y}\n#game-screen .games-choose h2{font-size:1.35rem;margin:0 0 14px}\n#game-screen .games-list{display:grid;grid-template-columns:1fr;gap:12px}\n#game-screen .games-option{padding:14px;background:#20334b;border:1px solid #52677e;border-radius:14px}\n#game-screen .games-option h3{margin:0 0 8px}\n#game-screen .games-option p{color:#cbd5e1;font-size:.9rem;line-height:1.35}\n#game-screen .games-option .primary{margin-top:10px}\n#game-screen .games-list button[aria-pressed=true]{background:#1459b8;color:white;border:2px solid #67d4ff;font-weight:700}\n#game-screen .games-list button[aria-pressed=false]{background:#263a55;color:white;border:2px solid #64748b}\n#game-screen .games-actions{display:flex;gap:8px;margin-top:18px;flex-wrap:wrap}\n#game-screen .games-actions button{flex:1;min-width:130px}\n#rotate-hint[hidden]{display:none!important}\n#game-screen.game-portrait #rotate-hint{display:none}\n#game-screen.landscape #rotate-hint:not([hidden]){display:flex}\n#game-screen.landscape #rotate-hint:not([hidden])~.game-body{display:none}\n@media(orientation:portrait){#game-screen.landscape .game-top{display:flex;position:relative;width:100%;flex:0 0 auto}}\n\n/* Catálogo em retrato pode rolar internamente; a página do pedido permanece fixa. */\nbody.game-active:has(#game-screen.game-portrait),#game-screen.game-portrait,#game-screen.game-portrait .game-body,#game-screen.game-portrait #stage{touch-action:pan-y}\n#game-screen.game-portrait .games-choose{overscroll-behavior:contain}\n\n/* O aviso de orientação é exibido em qualquer etapa e para ambos os sentidos. */\n#game-screen #rotate-hint:not([hidden]){display:flex!important;position:absolute;inset:0;z-index:10;flex-direction:column;align-items:center;justify-content:center;gap:16px;text-align:center;background:#091626;padding:24px}\n#game-screen #rotate-hint:not([hidden])~.game-body{display:none!important}\n#game-screen #rotate-hint .rotate-icon{font-size:clamp(64px,15vw,110px)}\n#game-screen #rotate-hint strong{font-size:clamp(1.5rem,5vw,2.4rem)}\n#game-screen #rotate-hint p{font-size:1.1rem}\n\n/* Catálogo: duas colunas no celular, novas linhas para mais jogos. */\n#game-screen.game-portrait .games-choose .games-list:has(.games-option){display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;align-items:stretch}\n#game-screen.game-portrait .games-option{min-width:0;display:flex;flex-direction:column;gap:8px;padding:12px}\n#game-screen.game-portrait .games-option h3{font-size:1rem;line-height:1.2;overflow-wrap:anywhere}\n#game-screen.game-portrait .games-option p{font-size:.8rem;line-height:1.35;overflow-wrap:anywhere;flex:1}\n#game-screen.game-portrait .games-option .primary{margin-top:auto;width:100%;min-height:42px}\n#game-screen.game-portrait .games-choose{width:100%;max-width:640px;min-height:0;overflow-y:auto;overscroll-behavior:contain}\n\n/* Ilustrações vetoriais compactas, sem downloads de imagens. */\n#game-screen .games-option .games-art{display:block;width:100%;height:auto;aspect-ratio:5/3;border-radius:10px;flex:0 0 auto;overflow:hidden}\n#game-screen.game-portrait .games-option{gap:7px}\n#game-screen.game-portrait .games-option h3{margin:0}\n\n/* Cards em construção: mesma estrutura, botão sem interação. */\n#game-screen .games-option.games-unavailable .primary:disabled{background:#34465e;color:#cbd5e1;border:1px solid #64748b;cursor:not-allowed;opacity:1}\n#game-screen .games-option.games-unavailable .games-art{opacity:.85}\n#game-screen .games-option.games-unavailable h3{color:#e2e8f0}\n\n/* Etiquetas compactas de capacidade, sem prometer modos futuros. */\n#game-screen .games-tags{display:flex;flex-wrap:wrap;gap:5px;align-content:flex-start}\n#game-screen .games-tag{display:inline-flex;align-items:center;max-width:100%;padding:4px 7px;border:1px solid #57708b;border-radius:999px;background:#263b53;color:#e1efff;font-size:.68rem;font-weight:650;line-height:1.2;overflow-wrap:anywhere}\n#game-screen .games-unavailable .games-tag{background:#2d3747;color:#cbd5e1}\n\n/* Retorno ao catálogo: mensagem própria, horizontal, sem rolagem. */\n#game-screen #return-portrait[hidden]{display:none!important}\n#game-screen #return-portrait:not([hidden]){\n position:absolute;inset:0;z-index:11;display:flex;flex-direction:row;\n align-items:center;justify-content:center;gap:clamp(14px,4vw,48px);\n padding:clamp(16px,5vh,40px);box-sizing:border-box;\n background:radial-gradient(ellipse at 20% 50%,#193c58 0%,#091626 75%);\n color:#f8fafc;text-align:left;overflow:hidden;\n}\n#game-screen #return-portrait .return-portrait-art{\n flex:0 0 auto;display:grid;place-items:center;width:clamp(80px,20vw,160px);\n height:clamp(80px,20vw,160px);font-size:clamp(62px,14vw,112px);\n transform:rotate(-15deg);background:#203e59;border-radius:24px;\n}\n#game-screen #return-portrait .return-portrait-copy{max-width:440px;min-width:0}\n#game-screen #return-portrait strong{display:block;font-size:clamp(1.1rem,3.8vw,2rem);line-height:1.2}\n#game-screen #return-portrait p{font-size:clamp(.85rem,2.2vw,1.1rem);margin:12px 0}\n#game-screen #return-portrait span{font-size:clamp(.75rem,1.8vw,.95rem);color:#a9d5ee}\n@media(orientation:portrait){\n #game-screen #return-portrait:not([hidden]){flex-direction:column;text-align:center}\n}\n";
  estilos.textContent += "\n#game-screen #stage > .games-playing{display:flex;flex-direction:column;width:100%;height:100%;min-height:0;min-width:0;max-height:100%;overflow:hidden;padding:0;flex:1 1 auto}\n#game-screen .games-playing > .games-stage{display:flex;flex:1 1 0;width:100%;height:100%;min-height:0;min-width:0;overflow:hidden}\n#game-screen .games-playing > .games-stage iframe{width:100%;height:100%!important;min-height:0!important}";
  estilos.textContent += "\n/* Cabeçalho retrato: reservar espaço aos botões sem cortar o pedido. */\n#game-screen.game-portrait .game-top{gap:6px;min-width:0}\n#game-screen.game-portrait .game-top>strong{flex:1 1 auto;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:clamp(.72rem,2.9vw,.86rem)}\n#game-screen.game-portrait .game-top .game-actions{flex:0 0 auto;width:auto;max-width:65%;flex-direction:row;align-items:center;gap:5px}\n#game-screen.game-portrait .game-top .game-actions button{width:auto;min-height:40px;padding:5px 9px;font-size:.78rem}\n@media(max-width:360px){#game-screen.game-portrait .game-top .game-actions button{font-size:.7rem;padding:5px 6px}}\n";
  // O catálogo aprovado usa retrato; paisagem é exclusiva da partida.
  const tela = document.createElement('section');
  tela.id = 'game-screen';
  tela.className = 'game-portrait';
  tela.setAttribute('aria-label', 'Jogos em tela cheia');
  const topo = document.createElement('div');
  topo.className = 'game-top';
  const tituloTopo = document.createElement('strong'); tituloTopo.textContent = '🔔 ' + etiquetaPedido;
  const sairTodos = document.createElement('button'); sairTodos.type = 'button';
  sairTodos.className = 'games-close'; sairTodos.textContent = '✕ Sair';
  // A ação de sair depende da etapa. O evento é registrado abaixo.
  const acoesTopo = document.createElement('div');
  acoesTopo.className = 'game-actions';
  topo.append(tituloTopo, acoesTopo);
  acoesTopo.append(sairTodos);
  const avisoRotacao = document.createElement('div');
  avisoRotacao.id = 'rotate-hint';
  const iconeRotacao = document.createElement('span'); iconeRotacao.className = 'rotate-icon'; iconeRotacao.textContent = '📱↻';
  const tituloRotacao = document.createElement('strong'); tituloRotacao.textContent = 'Gire o celular';
  const textoRotacao = document.createElement('p'); textoRotacao.textContent = 'Gire o celular para a horizontal antes de jogar.';
  const sairRotacao = document.createElement('button'); sairRotacao.type = 'button';
  sairRotacao.textContent = '← Voltar aos jogos'; sairRotacao.addEventListener('click', () => mostrarCatalogo());
  avisoRotacao.append(iconeRotacao, tituloRotacao, textoRotacao, sairRotacao);
  const corpo = document.createElement('div'); corpo.className = 'game-body';
  const cenario = document.createElement('div'); cenario.id = 'stage';
  corpo.append(cenario);
  const voltarRetrato = document.createElement('div');
  voltarRetrato.id = 'return-portrait'; voltarRetrato.hidden = true;
  voltarRetrato.setAttribute('role', 'status'); voltarRetrato.setAttribute('aria-live', 'polite');
  const arteRetrato = document.createElement('div'); arteRetrato.className = 'return-portrait-art'; arteRetrato.textContent = '📱';
  const textoRetrato = document.createElement('div'); textoRetrato.className = 'return-portrait-copy';
  const tituloRetrato = document.createElement('strong'); tituloRetrato.textContent = 'Volte o celular para a posição vertical';
  const instrucaoRetrato = document.createElement('p'); instrucaoRetrato.textContent = 'O catálogo de jogos fica melhor com o celular em pé.';
  const detalheRetrato = document.createElement('span'); detalheRetrato.textContent = 'Assim que você girar, os jogos aparecem automaticamente.';
  textoRetrato.append(tituloRetrato, instrucaoRetrato, detalheRetrato);
  voltarRetrato.append(arteRetrato, textoRetrato);
  tela.append(estilos, topo, avisoRotacao, voltarRetrato, corpo);
  function ajustarViewport() {
    if (!ativa) return;
    const vp = window.visualViewport;
    tela.style.setProperty('--game-viewport-width', Math.max(1, Math.floor(vp?.width || window.innerWidth)) + 'px');
    tela.style.setProperty('--game-viewport-height', Math.max(1, Math.floor(vp?.height || window.innerHeight)) + 'px');
    tela.style.transform = vp ? 'translate(' + Math.round(vp.offsetLeft) + 'px,' + Math.round(vp.offsetTop) + 'px)' : 'none';
  }
  const atualizarTela = () => { ajustarViewport(); if (ativa) layout(); };
  window.addEventListener('resize', atualizarTela, { passive: true });
  window.addEventListener('orientationchange', atualizarTela, { passive: true });
  window.visualViewport?.addEventListener('resize', atualizarTela, { passive: true });
  window.visualViewport?.addEventListener('scroll', atualizarTela, { passive: true });
  document.body.classList.add('game-active');
  ajustarViewport();
  let pararIsolado = null;
  let etapa = 'catalogo', jogoAtual = null, modoAtual = 'solo', sequenciaPartida = 0;
  const raiz = document.createElement('section');
  raiz.className = 'games-choose';
  raiz.setAttribute('aria-label', 'Biblioteca de jogos');
  const palco = document.createElement('div');
  palco.className = 'games-stage';
  palco.style.cssText = 'flex:1 1 auto;min-height:0;min-width:0;width:100%;height:100%;display:flex;align-items:stretch;justify-content:center;overflow:hidden';
  const voltar = document.createElement('button');
  voltar.type = 'button'; voltar.textContent = '← Voltar aos jogos';
  voltar.dataset.gamesBack = 'true'; voltar.className = 'games-back secondary'; voltar.hidden = true;
  acoesTopo.prepend(voltar);
  cenario.append(raiz);
  document.body.append(tela);
  function parar() {
    geracao++;
    const fim = pararIsolado; pararIsolado = null;
    try { fim?.(); } catch { /* a tela continua podendo ser encerrada */ }
    const pararPong = sairPong; sairPong = null;
    try { pararPong?.(); } catch { /* limpar interface */ }
    palco.replaceChildren();
  }
  function layout() {
    if (!ativa) return;
    const partida = etapa === 'partida' || etapa === 'rotacao';
    const desejaPaisagem = partida && jogoAtual?.orientation === 'paisagem';
    const retrato = window.matchMedia('(orientation: portrait)').matches;
    const incompatibilidade = desejaPaisagem ? retrato : !retrato;
    tela.classList.toggle('landscape', desejaPaisagem);
    tela.classList.toggle('game-portrait', !desejaPaisagem);
    tituloRotacao.textContent = desejaPaisagem ? 'Gire o celular' : 'Volte o celular para a posição vertical';
    textoRotacao.textContent = desejaPaisagem
      ? 'Gire o celular para a horizontal antes de jogar.'
      : 'Coloque o celular em pé para continuar a partida.';
    avisoRotacao.hidden = !incompatibilidade || !partida;
    voltarRetrato.hidden = !incompatibilidade || partida;
    corpo.hidden = incompatibilidade;
    if (etapa === 'rotacao' && !incompatibilidade) {
      void jogar(jogoAtual, modoAtual);
    }
  }
  function botao(texto, acao, classe = 'secondary') {
    const b = document.createElement('button');
    b.type = 'button'; b.className = classe; b.textContent = texto;
    b.addEventListener('click', acao);
    return b;
  }
  function mostrarCatalogo(mensagem = '') {
    if (!ativa) return;
    parar(); etapa = 'catalogo'; jogoAtual = null;
    voltar.hidden = true;
    sairTodos.textContent = '✕ Sair';
    raiz.className = 'games-choose';
    raiz.replaceChildren();
    const titulo = document.createElement('h2'); titulo.textContent = '🎮 Escolha um jogo';
    const lista = document.createElement('div'); lista.className = 'games-list';
    const aviso = document.createElement('p'); aviso.setAttribute('role','status');
    aviso.textContent = mensagem || 'Carregando jogos…';
    raiz.append(titulo, lista, aviso);
    layout();
    const ticket = geracao;
    return obterCatalogo().then(jogos => {
      if (!ativa || ticket !== geracao || etapa !== 'catalogo') return;
      aviso.textContent = mensagem || jogos.length + ' jogos disponíveis';
      for (const item of jogos) {
        const card = document.createElement('article'); card.className = 'games-option';
        const h = document.createElement('h3'); h.textContent = item.title;
        const p = document.createElement('p'); p.textContent = item.description || '';
        const bloqueado = item.status === 'construction';
        const btn = botao(bloqueado ? 'Em construção' : 'Escolher',
          () => mostrarJogadores(item), 'primary');
        btn.disabled = bloqueado;
        if (bloqueado) {
          btn.setAttribute('aria-label', item.title + ' em construção');
          card.classList.add('games-unavailable');
        }
        card.append(ilustracao(item), h, p, etiquetas(item), btn);
        lista.append(card);
      }
    }).catch(() => {
      if (ativa && ticket === geracao) aviso.textContent = 'Não foi possível carregar o catálogo. Tente novamente.';
    });
  }
  function mostrarJogadores(item) {
    if (!ativa || item.status === 'construction') return;
    parar(); etapa = 'jogadores'; jogoAtual = item; modoAtual = 'solo';
    voltar.hidden = false; sairTodos.textContent = '✕ Sair';
    raiz.replaceChildren();
    const titulo = document.createElement('h2'); titulo.textContent = item.title + ' · Jogadores';
    const opcoes = document.createElement('div'); opcoes.className = 'games-list';
    const descricao = document.createElement('p'); descricao.setAttribute('role','status');
    const numeros = item.playerCounts || [1,2];
    const botoes = [];
    function selecionar(n) {
      modoAtual = n === 1 ? 'solo' : 'dupla-local';
      for (const [quantidade,b] of botoes) {
        const marcado = quantidade === n;
        b.setAttribute('aria-pressed', String(marcado));
        b.textContent = (marcado ? '✓ ' : '') + quantidade + (quantidade === 1 ? ' jogador' : ' jogadores');
      }
      descricao.textContent = n === 1 ? 'Contra o computador.' : 'Jogadores no mesmo aparelho.';
    }
    for (const n of numeros) {
      const b = botao('', () => selecionar(n));
      botoes.push([n,b]); opcoes.append(b);
    }
    const acoes = document.createElement('div'); acoes.className = 'games-actions';
    acoes.append(botao('← Voltar aos jogos', () => mostrarCatalogo()),
      botao('Começar partida', confirmarPartida, 'primary'));
    // Modalidade existente do núcleo: oferecer sem alterar os modos locais aprovados.
    if (item.modes.includes('multiplayer-online')) {
      acoes.append(botao('Cada um no seu celular (online)', () => {
        modoAtual = 'dupla';
        confirmarPartida();
      }));
    }
    raiz.append(titulo, opcoes, descricao, acoes);
    selecionar(numeros[0]);
    layout();
  }
  function confirmarPartida() {
    if (!ativa || !jogoAtual) return;
    parar(); etapa = 'rotacao'; raiz.replaceChildren();
    voltar.hidden = false;
    sairTodos.textContent = '✕ Sair';
    layout();
  }
  voltar.addEventListener('click', () => mostrarCatalogo());
  sairTodos.addEventListener('click', () => {
    if (etapa === 'catalogo') encerrar();
    else mostrarCatalogo();
  });
  async function jogar(jogo, modo) {
    if (!ativa || etapa !== 'rotacao') return;
    parar();
    etapa = 'partida';
    // A partida precisa ocupar toda a área: o contêiner do catálogo tem altura automática.
    raiz.className = 'games-playing';
    raiz.replaceChildren(palco);
    palco.hidden = false;
    const atual = ++geracao;
    layout();
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
        frame.style.cssText = 'display:block;flex:1 1 auto;min-width:0;min-height:0;width:100%;height:100%;border:0;border-radius:8px';
        frame.src = new URL(jogo.id === 'pong'
          ? './pong-local-isolado.html' : './jogo-da-velha-isolado.html', import.meta.url).href;
        const canal = new MessageChannel();
        const instanceId = newInstanceId();
        const allowMessage = createRateLimiter();
        let parado = false, iniciado = false, lastSequence = -1, nextSequence = 0;
        const timeout = setTimeout(() => {
          if (parado || !ativa || atual !== geracao || iniciado) return;
          mostrarCatalogo('O jogo não respondeu. Tente novamente.');
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
            mostrarCatalogo('A comunicação do jogo foi encerrada.');
            return;
          }
          lastSequence = d.sequence;
          if (d.type === 'GAME_READY') {
            iniciado = true;
            clearTimeout(timeout);
            canal.port1.postMessage(createEnvelope({ type: 'GAME_START', instanceId, sequence: nextSequence++, payload: { mode: modo } }));
          } else if (d.type === 'GAME_EXIT' || d.type === 'GAME_ERROR') {
            mostrarCatalogo(d.type === 'GAME_ERROR' ? 'O jogo apresentou um erro.' : 'Escolha um jogo.');
          }
        };
        frame.addEventListener('load', () => {
          if (parado || !ativa || atual !== geracao) return;
          // Origem opaca do sandbox: '*' é necessário somente no envio inicial da porta.
          // Não há credenciais, tokens ou dados de pedido no payload.
          try { frame.contentWindow.postMessage({ type: 'AVISAQUI_GAME_INIT', instanceId }, '*', [canal.port2]); }
          catch { if (ativa && atual === geracao) mostrarCatalogo('Não foi possível iniciar o jogo.'); }
        }, { once: true });
        frame.addEventListener('error', () => {
          if (!parado && ativa && atual === geracao) {
            mostrarCatalogo('Falha ao carregar o arquivo do jogo.');
          }
        }, { once: true });
        palco.append(frame);
      }

    } catch (erro) {
      if (ativa && atual === geracao) {
        const mensagem = erro instanceof Error && /^Pong indisponível/.test(erro.message)
          ? erro.message : 'Não foi possível abrir o jogo. Tente novamente.';
        mostrarCatalogo(mensagem);
      }
    }
  }
  const pronto = mostrarCatalogo();
  function encerrar() {
    if (!ativa) return;
    ativa = false;
    parar();
    window.removeEventListener('resize', atualizarTela);
    window.removeEventListener('orientationchange', atualizarTela);
    window.visualViewport?.removeEventListener('resize', atualizarTela);
    window.visualViewport?.removeEventListener('scroll', atualizarTela);
    tela.remove();
    document.body.classList.remove('game-active');
    window.scrollTo(0, scrollAnterior);
    onExit();
  }
  return Object.freeze({ encerrar, pronto });
}
