// Biblioteca opcional. Somente a página principal controla o Pong e o estado do pedido.
import { obterCatalogo } from './catalogo.js';
import { newInstanceId, createEnvelope, validateEnvelope, createRateLimiter } from './protocolo-v1.js';

export function criarBibliotecaJogos({ container, iniciarPong, onExit = () => {} } = {}) {
  if (!(container instanceof HTMLElement)) throw new TypeError('Container inválido');
  let ativa = true, geracao = 0, sairPong = null;
  let pararIsolado = null;
  const raiz = document.createElement('section');
  raiz.setAttribute('aria-label', 'Biblioteca de jogos');
  const titulo = document.createElement('h2'); titulo.textContent = '🎮 Biblioteca de jogos';
  const aviso = document.createElement('p'); aviso.setAttribute('role', 'status'); aviso.textContent = 'Carregando biblioteca...';
  const lista = document.createElement('div');
  lista.style.cssText = 'display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin:14px 0';
  const palco = document.createElement('div');
  const voltar = document.createElement('button'); voltar.type = 'button'; voltar.textContent = 'Voltar à biblioteca'; voltar.hidden = true;
  voltar.dataset.gamesBack = 'true';
  voltar.style.cssText = 'margin:12px 0;padding:10px';
  function parar() {
    geracao++;
    const pararFrame = pararIsolado; pararIsolado = null;
    try { pararFrame?.(); } catch { /* remoção do iframe continua abaixo */ }
    const sair = sairPong; sairPong = null;
    try { sair?.(); } catch { /* limpeza da interface deve continuar */ }
    palco.replaceChildren();
    lista.hidden = false; voltar.hidden = true;
  }
  voltar.addEventListener('click', () => { parar(); aviso.textContent = 'Escolha um jogo.'; });
  raiz.append(titulo, aviso, lista, voltar, palco);
  container.append(raiz);
  async function jogar(jogo, modo) {
    if (!ativa) return;
    parar();
    const atual = ++geracao;
    lista.hidden = true; voltar.hidden = false; aviso.textContent = 'Carregando jogo...';
    try {
      if (jogo.id === 'pong') {
        if (typeof iniciarPong !== 'function') throw new Error('Pong indisponível');
        const encerrar = await iniciarPong(palco, modo);
        if (!ativa || atual !== geracao) { encerrar?.(); return; }
        sairPong = encerrar;
      } else {
        if (jogo.id !== 'jogo-da-velha' || !['solo', 'dupla-local'].includes(modo)) throw new Error('Jogo indisponível');
        const frame = document.createElement('iframe');
        frame.title = 'Jogo da Velha';
        frame.setAttribute('sandbox', 'allow-scripts');
        frame.setAttribute('referrerpolicy', 'no-referrer');
        frame.style.cssText = 'width:100%;height:440px;border:0;border-radius:12px';
        frame.src = new URL('./jogo-da-velha-isolado.html', import.meta.url).href;
        const canal = new MessageChannel();
        const instanceId = newInstanceId();
        const allowMessage = createRateLimiter();
        let parado = false, iniciado = false, lastSequence = -1, nextSequence = 0;
        const timeout = setTimeout(() => {
          if (parado || !ativa || atual !== geracao || iniciado) return;
          parar();
          aviso.textContent = 'O jogo não respondeu. Tente novamente.';
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
        palco.append(frame);
      }
      aviso.textContent = '';
    } catch {
      if (ativa && atual === geracao) { parar(); aviso.textContent = 'Não foi possível abrir o jogo.'; }
    }
  }
  const pronto = (async () => {
    try {
      const jogos = await obterCatalogo();
      if (!ativa) return;
      for (const jogo of jogos) {
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
          const modos = jogo.id === 'pong'
            ? [['solo', 'Contra o computador'], ['dupla', 'Duas pessoas']]
            : [['solo', 'Contra o computador'], ['dupla-local', 'Duas pessoas no aparelho']];
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
    raiz.remove();
    onExit();
  }
  return Object.freeze({ encerrar, pronto });
}
