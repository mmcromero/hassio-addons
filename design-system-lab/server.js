'use strict';

const http = require('node:http');
const fs = require('node:fs');
const path = require('node:path');
const { spawn } = require('node:child_process');

const HOST = '0.0.0.0';
const PORT = Number(process.env.PORT || 8099);
const PUBLIC = '/app/public';
const MAX_LOG = 60000;
let child = null;
let demoRoot = null;
let githubToken = '';

const state = {
  status: 'idle',
  message: 'Aguardando execução.',
  sourceSha: null,
  evidenceDir: null,
  startedAt: null,
  finishedAt: null,
  log: ''
};

function readOptions() {
  try {
    const data = JSON.parse(fs.readFileSync('/data/options.json', 'utf8'));
    return data && typeof data === 'object' ? data : {};
  } catch {
    return {};
  }
}

function send(res, status, body, type = 'application/json; charset=utf-8') {
  res.writeHead(status, {
    'Content-Type': type,
    'Cache-Control': 'no-store',
    'X-Content-Type-Options': 'nosniff',
    'Referrer-Policy': 'no-referrer'
  });
  res.end(body);
}

function json(res, status, value) {
  send(res, status, JSON.stringify(value));
}

function appendLog(chunk) {
  let value = String(chunk);
  if (githubToken) value = value.split(githubToken).join('[REDACTED]');
  state.log = (state.log + value).slice(-MAX_LOG);
  for (const line of value.split(/\r?\n/)) {
    let match = line.match(/^SOURCE_SHA=([a-f0-9]{40})$/);
    if (match) state.sourceSha = match[1];
    match = line.match(/^EVIDENCE_DIR=(\/tmp\/ds-lote-e-[A-Za-z0-9._-]+)$/);
    if (match) state.evidenceDir = match[1];
    match = line.match(/^DEMO_DIR=(\/tmp\/ds-lote-e-[A-Za-z0-9._-]+\/checkout\/apps\/demo\/dist)$/);
    if (match) demoRoot = match[1];
  }
}

function publicStatus() {
  const options = readOptions();
  return {
    ...state,
    tokenConfigured: typeof options.github_read_token === 'string' && options.github_read_token.length > 0,
    demoAvailable: state.status === 'success' && !!demoRoot
  };
}

function startRun(res) {
  if (child) return json(res, 409, { error: 'Já existe uma validação em andamento.' });
  const options = readOptions();
  const token = typeof options.github_read_token === 'string' ? options.github_read_token.trim() : '';
  if (!token) {
    return json(res, 400, {
      error: 'Configure um Fine-grained PAT de somente leitura na aba Configuração do app.'
    });
  }

  githubToken = token;
  demoRoot = null;
  state.status = 'running';
  state.message = 'Executando validação no Raspberry Pi ARM64.';
  state.sourceSha = null;
  state.evidenceDir = null;
  state.startedAt = new Date().toISOString();
  state.finishedAt = null;
  state.log = '';

  child = spawn('/bin/bash', ['/app/run-validation.sh'], {
    cwd: '/app',
    env: {
      ...process.env,
      GITHUB_TOKEN: token,
      DS_BROWSER_TOOLS: '/opt/browser-tools',
      DS_PLAYWRIGHT_BROWSERS_PATH: '/opt/pw-cache',
      DS_PLAYWRIGHT_READY: '1'
    },
    stdio: ['ignore', 'pipe', 'pipe']
  });

  child.stdout.on('data', appendLog);
  child.stderr.on('data', appendLog);
  child.on('error', error => {
    appendLog('\nERRO AO INICIAR: ' + error.message + '\n');
    state.status = 'error';
    state.message = 'Não foi possível iniciar o executor.';
    state.finishedAt = new Date().toISOString();
    child = null;
    githubToken = '';
  });
  child.on('close', code => {
    state.finishedAt = new Date().toISOString();
    if (code === 0 && demoRoot) {
      state.status = 'success';
      state.message = 'Build, testes e Chromium concluídos. Demo disponível para homologação manual.';
    } else {
      state.status = 'error';
      state.message = 'Validação não concluída. Consulte o log para identificar a etapa.';
    }
    child = null;
    githubToken = '';
  });

  return json(res, 202, { accepted: true, message: 'Validação iniciada.' });
}

function contentType(file) {
  const ext = path.extname(file).toLowerCase();
  return ({
    '.html': 'text/html; charset=utf-8',
    '.js': 'text/javascript; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.svg': 'image/svg+xml',
    '.png': 'image/png',
    '.jpg': 'image/jpeg',
    '.jpeg': 'image/jpeg',
    '.webp': 'image/webp',
    '.woff': 'font/woff',
    '.woff2': 'font/woff2',
    '.json': 'application/json; charset=utf-8'
  })[ext] || 'application/octet-stream';
}

function serveFile(res, root, relative) {
  const safeRoot = path.resolve(root);
  const file = path.resolve(safeRoot, '.' + (relative || '/index.html'));
  if (file !== safeRoot && !file.startsWith(safeRoot + path.sep)) {
    return send(res, 403, 'Forbidden', 'text/plain; charset=utf-8');
  }
  let target = file;
  try {
    if (fs.statSync(target).isDirectory()) target = path.join(target, 'index.html');
    const data = fs.readFileSync(target);
    res.writeHead(200, {
      'Content-Type': contentType(target),
      'Cache-Control': 'no-store',
      'X-Content-Type-Options': 'nosniff',
      'Referrer-Policy': 'no-referrer'
    });
    return res.end(data);
  } catch {
    return send(res, 404, 'Not found', 'text/plain; charset=utf-8');
  }
}

const server = http.createServer((req, res) => {
  let url;
  try {
    url = new URL(req.url, 'http://localhost');
  } catch {
    return send(res, 400, 'Bad request', 'text/plain; charset=utf-8');
  }

  if (url.pathname === '/api/status' && req.method === 'GET') return json(res, 200, publicStatus());
  if (url.pathname === '/api/run' && req.method === 'POST') return startRun(res);
  if (url.pathname === '/api/log' && req.method === 'GET') {
    res.setHeader('Content-Disposition', 'attachment; filename="design-system-validation.log"');
    return send(res, 200, state.log, 'text/plain; charset=utf-8');
  }
  if (url.pathname === '/demo' || url.pathname === '/demo/') {
    if (!demoRoot || state.status !== 'success') {
      return send(res, 404, 'A Demo estará disponível após a validação PASS.', 'text/plain; charset=utf-8');
    }
    return serveFile(res, demoRoot, '/index.html');
  }
  if (url.pathname.startsWith('/demo/')) {
    if (!demoRoot || state.status !== 'success') return send(res, 404, 'Demo não disponível.', 'text/plain; charset=utf-8');
    let relative;
    try { relative = decodeURIComponent(url.pathname.slice('/demo'.length)); }
    catch { return send(res, 400, 'Bad path', 'text/plain; charset=utf-8'); }
    return serveFile(res, demoRoot, relative);
  }
  if (req.method === 'GET' && (url.pathname === '/' || url.pathname === '/index.html')) return serveFile(res, PUBLIC, '/index.html');
  if (req.method === 'GET' && url.pathname === '/app.js') return serveFile(res, PUBLIC, '/app.js');
  if (req.method === 'GET' && url.pathname === '/style.css') return serveFile(res, PUBLIC, '/style.css');
  return send(res, 404, 'Not found', 'text/plain; charset=utf-8');
});

server.listen(PORT, HOST, () => {
  console.log('Design System Lab disponível em Ingress na porta ' + PORT);
});
