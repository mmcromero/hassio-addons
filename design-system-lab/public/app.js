'use strict';
const $ = id => document.getElementById(id);
const runButton = $('run');
let lastLog = '';
function formatDate(value) {
  if (!value) return '—';
  try { return new Date(value).toLocaleString('pt-BR'); } catch { return value; }
}
async function refresh() {
  try {
    const response = await fetch('api/status', { cache: 'no-store' });
    const data = await response.json();
    $('token-state').textContent = data.tokenConfigured
      ? 'Token GitHub configurado. O acesso é somente leitura.'
      : 'Token GitHub ainda não configurado. Siga as instruções abaixo.';
    runButton.disabled = data.status === 'running' || !data.tokenConfigured;
    $('status').textContent = data.message;
    $('sha').textContent = data.sourceSha || 'Ainda não executado';
    $('started').textContent = formatDate(data.startedAt);
    $('finished').textContent = formatDate(data.finishedAt);
    $('log-state').textContent = data.status === 'running' ? 'Executando…' : data.status.toUpperCase();
    if (data.log !== lastLog) {
      $('log').textContent = data.log || 'Os resultados aparecerão aqui.';
      lastLog = data.log;
    }
    $('demo').hidden = !data.demoAvailable;
  } catch {
    $('status').textContent = 'Não foi possível consultar o estado do executor.';
  }
}
runButton.addEventListener('click', async () => {
  runButton.disabled = true;
  $('status').textContent = 'Solicitando execução…';
  try {
    const response = await fetch('api/run', { method: 'POST' });
    const data = await response.json();
    if (!response.ok) $('status').textContent = data.error || 'Falha ao iniciar.';
  } catch {
    $('status').textContent = 'Falha de comunicação com o executor.';
  }
  await refresh();
});
refresh();
setInterval(refresh, 2000);
