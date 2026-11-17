// AVISAQUI-GAMES-001 — jogo local sem acesso a pedidos ou rede.
export function vencedor(casas) {
  const linhas = [[0,1,2],[3,4,5],[6,7,8],[0,3,6],[1,4,7],[2,5,8],[0,4,8],[2,4,6]];
  for (const [a,b,c] of linhas) if (casas[a] && casas[a] === casas[b] && casas[b] === casas[c]) return casas[a];
  return casas.every(Boolean) ? 'empate' : null;
}
export function jogar(casas, indice, simbolo) {
  if (!Number.isInteger(indice) || indice < 0 || indice > 8 || casas.length !== 9 || casas[indice] || vencedor(casas) || !['X','O'].includes(simbolo)) return null;
  const novas = [...casas]; novas[indice] = simbolo; return novas;
}
export function escolhaComputador(casas) {
  const avaliar = (estado, turno, profundidade) => {
    const fim = vencedor(estado);
    if (fim) return fim === 'O' ? 10 - profundidade : fim === 'X' ? profundidade - 10 : 0;
    const valores = estado.map((v,i) => v ? null : avaliar(jogar(estado,i,turno),turno === 'O' ? 'X' : 'O',profundidade+1)).filter(v => v !== null);
    return turno === 'O' ? Math.max(...valores) : Math.min(...valores);
  };
  let melhor = -Infinity, indice = -1;
  casas.forEach((v,i) => {
    if (v) return;
    const nota = avaliar(jogar(casas,i,'O'),'X',1);
    if (nota > melhor) { melhor = nota; indice = i; }
  });
  return indice;
}
export function iniciarJogoDaVelha({ container, onExit = () => {}, modo = 'solo' }) {
  if (!(container instanceof HTMLElement)) throw new TypeError('Container inválido');
  let casas = Array(9).fill(null), turno = 'X', encerrado = false, pausado = false;
  const raiz = document.createElement('section');
  raiz.setAttribute('aria-label','Jogo da Velha');
  const titulo = document.createElement('h2'); titulo.textContent = 'Jogo da Velha';
  const status = document.createElement('p'); status.setAttribute('role','status');
  const grade = document.createElement('div');
  grade.style.cssText = 'display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;max-width:320px;margin:12px auto';
  const botoes = Array.from({length:9},(_,i) => {
    const botao = document.createElement('button');
    botao.type='button'; botao.style.cssText='min-height:76px;font-size:2rem;touch-action:manipulation';
    botao.addEventListener('click',() => {
      if (encerrado || pausado || vencedor(casas) || (modo === 'solo' && turno !== 'X')) return;
      const novas = jogar(casas,i,turno); if (!novas) return;
      casas = novas; turno = turno === 'X' ? 'O' : 'X'; atualizar();
      if (modo === 'solo' && !vencedor(casas)) {
        const cpu = escolhaComputador(casas); casas = jogar(casas,cpu,'O'); turno = 'X'; atualizar();
      }
    });
    grade.append(botao); return botao;
  });
  const reiniciar = document.createElement('button'); reiniciar.type='button'; reiniciar.textContent='Nova partida';
  reiniciar.addEventListener('click',()=>{ if(encerrado || pausado)return; casas=Array(9).fill(null); turno='X'; atualizar(); });
  const sair = document.createElement('button'); sair.type='button'; sair.textContent='Sair do jogo';
  const destruir = () => { if(encerrado)return; encerrado=true; raiz.remove(); onExit(); };
  sair.addEventListener('click',destruir);
  raiz.append(titulo,status,grade,reiniciar,sair); container.append(raiz);
  function atualizar() {
    const fim = vencedor(casas);
    status.textContent = pausado ? 'Jogo pausado' : fim === 'empate' ? 'Empate!' : fim ? 'Vitória de '+fim : 'Vez de '+turno;
    botoes.forEach((b,i)=>{b.textContent=casas[i]||'·';b.disabled=pausado||!!fim||!!casas[i]||(modo==='solo'&&turno!=='X');b.setAttribute('aria-label','Casa '+(i+1)+': '+(casas[i]||'vazia'));});
  }
  atualizar();
  destruir.pausar = () => { if (!encerrado) { pausado = true; atualizar(); } };
  destruir.retomar = () => { if (!encerrado) { pausado = false; atualizar(); } };
  return destruir;
}

// Contrato uniforme para o carregador independente.
export const iniciarJogo = iniciarJogoDaVelha;
