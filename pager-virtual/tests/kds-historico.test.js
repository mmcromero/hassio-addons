import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

test('KDS interface possui abas clicaveis Ativos e Finalizados com persistencia', () => {
  const html = readFileSync(new URL('../src/public/kds.html', import.meta.url), 'utf8');
  assert.match(html, /id="btn-tab-active"/, 'Deve conter o botão de aba Ativos');
  assert.match(html, /id="btn-tab-finished"/, 'Deve conter o botão de aba Finalizados');
  assert.match(html, /async function carregarResumo\(\)/, 'Deve conter a função para buscar resumo persistido');
  assert.match(html, /function renderFinishedOrders\(\)/, 'Deve conter a função para renderizar os finalizados');
  assert.match(html, /carregarResumo\(\)/, 'Deve chamar carregarResumo na inicialização');
});

test('Rotas de pedidos possui endpoint /api/pedidos/historico com privacidade e resumo', () => {
  const js = readFileSync(new URL('../src/routes/pedidos.js', import.meta.url), 'utf8');
  assert.match(js, /\/api\/pedidos\/historico/, 'Deve registrar endpoint de histórico');
  assert.match(js, /status = 'entregue'/, 'Deve filtrar pedidos entregues');
  assert.match(js, /total_hoje:/, 'Deve retornar contagem persistente de finalizados hoje');
  // Valida que cliente_nome e cliente_telefone NÃO são selecionados na rota de histórico (privacidade)
  const historicoBlock = js.slice(js.indexOf('/api/pedidos/historico'), js.indexOf('fastify.post(\'/api/pedidos\''));
  assert.doesNotMatch(historicoBlock, /p\.cliente_nome/, 'Histórico não deve expor dados pessoais');
  assert.doesNotMatch(historicoBlock, /p\.cliente_telefone/, 'Histórico não deve expor telefone');
});
