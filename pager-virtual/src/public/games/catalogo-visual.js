// Fonte visual aprovada: games-preview v59. SVG local, sem imagem externa.
function ilustracao(item){
 const ns='http://www.w3.org/2000/svg';
 const svg=document.createElementNS(ns,'svg');
 svg.setAttribute('viewBox','0 0 240 144');
 svg.setAttribute('role','img');
 svg.setAttribute('aria-label','Ilustração do jogo '+item.title);
 svg.classList.add('games-art');
 const criar=(tag,atributos)=>{const el=document.createElementNS(ns,tag);for(const [k,v] of Object.entries(atributos))el.setAttribute(k,String(v));svg.append(el);return el;};
 criar('rect',{x:0,y:0,width:240,height:144,rx:16,fill:'#12263c'});
 if(item.id==='pong'){
  criar('path',{d:'M120 10 V134',stroke:'#54748a','stroke-width':3,'stroke-dasharray':'8 9'});
  criar('rect',{x:28,y:34,width:12,height:65,rx:6,fill:'#67d4ff'});
  criar('rect',{x:200,y:49,width:12,height:65,rx:6,fill:'#ffb66d'});
  criar('circle',{cx:133,cy:68,r:10,fill:'#fff'});
  criar('path',{d:'M91 82 L117 71',stroke:'#fff','stroke-width':3,'stroke-linecap':'round',opacity:'.5'});
 }else if(item.id==='jogo-da-velha'){
  for(const x of [95,145])criar('path',{d:`M${x} 18 V126`,stroke:'#6b89a2','stroke-width':5,'stroke-linecap':'round'});
  for(const y of [48,96])criar('path',{d:`M47 ${y} H193`,stroke:'#6b89a2','stroke-width':5,'stroke-linecap':'round'});
  for(const [x,y] of [[70,32],[170,112],[120,72]])criar('path',{d:`M${x-11} ${y-11} L${x+11} ${y+11} M${x+11} ${y-11} L${x-11} ${y+11}`,stroke:'#67d4ff','stroke-width':6,'stroke-linecap':'round'});
  for(const [x,y] of [[170,32],[70,72]])criar('circle',{cx:x,cy:y,r:15,fill:'none',stroke:'#ffb66d','stroke-width':6});
 }else{
  const simbolos={
   'jogo-da-memoria':'🃏','cobrinha':'🐍','quebra-cabeca':'🧩','forca':'🔤',
   'campo-minado':'💣','ligue-os-pontos':'🔷','batalha-naval':'🚢',
   'quiz-relampago':'⚡','sudoku':'🔢','blocos':'🧱',
   'corrida-de-carros':'🏎️','air-hockey':'🏒','labirinto':'🌀',
   'jogo-das-diferencas':'🔍'
  };
  criar('circle',{cx:120,cy:70,r:51,fill:'#203f57',stroke:'#3e7089','stroke-width':3});
  const t=criar('text',{x:120,y:91,'text-anchor':'middle','font-size':62,'font-family':'system-ui,sans-serif'});
  t.textContent=simbolos[item.id]||'🎮';
 }
 return svg;
}
function etiquetas(item){
 const grupo=document.createElement('div');grupo.className='games-tags';
 const adicionar=(texto)=>{const tag=document.createElement('span');tag.className='games-tag';tag.textContent=texto;grupo.append(tag);};
 const numeros=Array.isArray(item.playerCounts)?item.playerCounts:[];
 if(numeros.length)adicionar((item.status==='construction'?'Previsto: ':'')+(numeros.length===1?String(numeros[0]):Math.min(...numeros)+'–'+Math.max(...numeros))+' jogador'+(numeros.length===1&&numeros[0]===1?'':'es'));
 if(item.status==='construction'){adicionar('Modo a definir');return grupo;}
 const modos=Array.isArray(item.modes)?item.modes:[];
 if(modos.includes('solo'))adicionar('Solo / CPU');
 if(modos.includes('dupla-local'))adicionar('Multiplayer local');
 if(modos.includes('multiplayer-online'))adicionar('Cada um no seu celular');
 return grupo;
}

export { ilustracao, etiquetas };
