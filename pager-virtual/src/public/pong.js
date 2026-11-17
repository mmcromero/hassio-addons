export async function iniciarPong({ token, container, onExit, mode = 'dupla' }) {
  container.replaceChildren();
  const raiz = document.createElement('section'); raiz.className = 'pong-root';
  const label = document.createElement('p');
  label.setAttribute('role', 'status');
  label.textContent = 'Conectando ao Pong...';
  const canvas = document.createElement('canvas');
  canvas.width = 600; canvas.height = 360;
  canvas.style.cssText = 'display:block;width:100%;height:100%;min-width:0;touch-action:none;background:#102b39;border-radius:8px';
  const faixa = document.createElement('div');
  faixa.setAttribute('role', 'group');
  faixa.style.cssText = 'flex:0 0 clamp(40px,8%,62px);display:flex;align-items:center;justify-content:center;background:#263e55;border:2px solid #65d4f0;border-radius:12px;color:#e0f2fe;touch-action:none;user-select:none;writing-mode:vertical-rl;font-size:12px;letter-spacing:1px';
  faixa.textContent = 'AZUL';
  faixa.setAttribute('aria-label', 'Controle da raquete azul');
  const arena = document.createElement('div'); arena.className = 'pong-arena';
  arena.style.cssText = 'display:flex;align-items:stretch;gap:5px;min-height:0;min-width:0;width:100%;flex:1';
  arena.append(faixa, canvas);
  const partida = document.createElement('div'); partida.className = 'pong-partida';
  partida.append(arena);
  const close = document.createElement('button');
  close.textContent = 'Sair do jogo';
  close.type = 'button';
  raiz.append(label, partida, close);
  container.append(raiz);
  // Usa o prefixo da página do pedido, não um caminho absoluto que ignora /avisaqui/.
  const apiBase = location.pathname.endsWith('/cliente.html')
    ? location.pathname.slice(0, -'/cliente.html'.length)
    : location.pathname.replace(/\/$/, '');
  const endpoint = apiBase + '/api/jogos/pong';
  let player = '', side = -1, stream = null, active = true, lastMove = 0;
  const ctx = canvas.getContext('2d');
  function render(state) {
    if (!active) return;
    label.textContent = state.status === 'aguardando' ? 'Aguardando o segundo celular...' :
      (mode === 'solo' ? 'Você joga contra o computador.' : 'Você controla a raquete ' + (side === 0 ? 'esquerda' : 'direita') + '.');
    ctx.fillStyle = '#102b39'; ctx.fillRect(0, 0, 600, 360);
    ctx.strokeStyle = '#3c6977'; ctx.setLineDash([8, 8]);
    ctx.beginPath(); ctx.moveTo(300, 0); ctx.lineTo(300, 360); ctx.stroke(); ctx.setLineDash([]);
    ctx.fillStyle = '#fff'; ctx.font = '24px sans-serif';
    ctx.fillText(String(state.scores[0]), 255, 32); ctx.fillText(String(state.scores[1]), 330, 32);
    ctx.fillStyle = '#65d4f0';
    ctx.fillRect(18, state.paddles[0] - 35, 12, 70);
    ctx.fillStyle = '#ffb66d';
    ctx.fillRect(570, state.paddles[1] - 35, 12, 70);
    ctx.fillStyle = '#fff';
    ctx.beginPath(); ctx.arc(state.ball.x, state.ball.y, 8, 0, Math.PI * 2); ctx.fill();
  }
  function solicitarSaida(participante) {
    if (!participante) return;
    void fetch(endpoint + '/sair', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ player: participante }),
      credentials: 'same-origin',
      keepalive: true
    }).catch(() => {});
  }
  function exit() {
    if (!active) return;
    active = false;
    stream?.close();
    solicitarSaida(player);
    container.replaceChildren();
    onExit?.();
  }
  close.addEventListener('click', exit);
  async function move(event) {
    if (!active || !player || Date.now() - lastMove < 45) return;
    lastMove = Date.now();
    const rect = canvas.getBoundingClientRect();
    const y = (event.clientY - rect.top) / rect.height * 360;
    try {
      const response = await fetch(endpoint + '/mover', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ player, y }), credentials: 'same-origin'
      });
      if ([403, 409].includes(response.status)) exit();
    } catch { label.textContent = 'Conexão instável. Tentando novamente...'; }
  }
  for (const controle of [canvas, faixa]) {
    controle.addEventListener('pointerdown', move);
    controle.addEventListener('pointermove', event => {
      if (event.buttons || event.pointerType === 'touch') move(event);
    });
  }
  try {
    const response = await fetch(endpoint + '/entrar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, mode }), credentials: 'same-origin'
    });
    const data = await response.json().catch(() => ({}));
    if (!response.ok) throw new Error(response.status === 404 ? 'Rota do jogo não encontrada (HTTP 404). Verificar versão do servidor e encaminhamento HTTPS.' : (data.error || 'Falha ao entrar no jogo (HTTP ' + response.status + ')'));
    player = data.player; side = data.side;
    if (side === 1) {
      faixa.textContent = 'LARANJA';
      faixa.style.borderColor = '#ffb66d';
      faixa.setAttribute('aria-label', 'Controle da raquete laranja');
      arena.append(faixa);
    }
    // O pedido pode ficar pronto enquanto /entrar está em trânsito.
    // Mesmo com a tela encerrada, liberar o participante criado pela resposta tardia.
    if (!active) {
      solicitarSaida(player);
      return exit;
    }
    render(data);
    stream = new EventSource(endpoint + '/eventos/' + encodeURIComponent(player));
    stream.onmessage = event => render(JSON.parse(event.data));
    stream.addEventListener('encerrado', exit);
    stream.onerror = () => { if (active) label.textContent = 'Reconectando à partida...'; };
  } catch (error) {
    if (active) {
      label.textContent = error.message;
      close.textContent = 'Voltar';
    }
  }
  return exit;
}
