import test from 'node:test';
import assert from 'node:assert/strict';
import { vencedor, jogar, escolhaComputador } from '../src/public/games/jogo-da-velha.js';
test('linhas, colunas e diagonais',()=>{
  assert.equal(vencedor(['X','X','X',null,null,null,null,null,null]),'X');
  assert.equal(vencedor(['O',null,null,'O',null,null,'O',null,null]),'O');
  assert.equal(vencedor(['X',null,null,null,'X',null,null,null,'X']),'X');
});
test('empate e partida aberta',()=>{
  assert.equal(vencedor(['X','O','X','X','O','O','O','X','X']),'empate');
  assert.equal(vencedor(Array(9).fill(null)),null);
});
test('jogadas inválidas não alteram estado',()=>{
  const inicio=Array(9).fill(null); const proximo=jogar(inicio,0,'X');
  assert.equal(inicio[0],null); assert.equal(proximo[0],'X');
  assert.equal(jogar(proximo,0,'O'),null);assert.equal(jogar(inicio,9,'X'),null);
});
test('computador bloqueia vitória imediata',()=>{
  assert.equal(escolhaComputador(['X','X',null,null,'O',null,null,null,null]),2);
});
