export async function iniciarPong({ token, container, onExit, mode = 'dupla' }) {
  container.innerHTML = '';
  const label = document.createElement('p');
  label.textContent = 'Conectando ao Pong...';
  const canvas = document.createElement('canvas');
  canvas.width = 600; canvas.height = 360;
  canvas.style.cssText = 'width:100%;max-width:600px;touch-action:none;background:#102b39;border-radius:12px';
  const close = document.createElement('button');
  close.textContent = 'Sair do jogo';
  close.type = 'button';
  container.append(label, canvas, close);
  const base = new URL('.', import.meta.url).pathname.replace(/\/$/, '');
  // API usa o mesmo prefixo público da página; evita divergência de caminhos no proxy.
  const apiBase = base.endsWith('/public') ? base.slice(0, -7) : base;
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
  function exit() {
    active = false;
    stream?.close();
    if (player) void fetch(endpoint + '/sair', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ token, player }), keepalive: true }).catch(() => {});
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
        body: JSON.stringify({ token, player, y })
      });
      if (response.status === 409) exit();
    } catch { label.textContent = 'Conexão instável. Tentando novamente...'; }
  }
  canvas.addEventListener('pointerdown', move);
  canvas.addEventListener('pointermove', event => { if (event.buttons || event.pointerType === 'touch') move(event); });
  try {
    const response = await fetch(endpoint + '/entrar', {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ token, mode })
    });
    const data = await response.json();
    if (!response.ok) throw new Error(response.status === 404 ? 'Rota do jogo não encontrada (HTTP 404). Verificar versão do servidor e encaminhamento HTTPS.' : (data.error || 'Não foi possível entrar'));
    player = data.player; side = data.side;
    if (!active) return exit();
    render(data);
    stream = new EventSource(endpoint + '/eventos/' + encodeURIComponent(token) + '/' + encodeURIComponent(player));
    stream.onmessage = event => render(JSON.parse(event.data));
    stream.addEventListener('encerrado', exit);
    stream.onerror = () => { if (active) label.textContent = 'Reconectando à partida...'; };
  } catch (error) {
    if (active) label.textContent = error.message;
  }
  return exit;
}
