// AVISAQUI-PAIR-001: servico de pagina SOMENTE opt-in para laboratorio.
// Nenhum import por src/server.js; o chamador deve montar o prefixo explicitamente.
// Acoes de gerente continuam protegidas pelo plugin routes-lab + auth de sessao.
import { readFile } from 'node:fs/promises';
import { createHash } from 'node:crypto';

const PAGE = new URL('./assets/autorizar-pair-lab.html', import.meta.url);
// A página usa script inline próprio. O hash CSP vincula a execução exatamente ao
// conteúdo servido e dispensa 'unsafe-inline' para JavaScript.
function cspForHtml(html) {
  const scripts = [...html.matchAll(/<script(?:\s[^>]*)?>([\s\S]*?)<\/script>/gi)];
  if (scripts.length !== 1 || !scripts[0][1].trim()) throw new TypeError('Script da pagina do laboratorio invalido');
  const digest = createHash('sha256').update(scripts[0][1], 'utf8').digest('base64');
  return [
    "default-src 'none'",
    `script-src 'sha256-${digest}'`,
    "script-src-attr 'none'",
    "style-src 'unsafe-inline'", // CSS inline da pagina de laboratorio; nao autoriza scripts.
    "img-src 'self'", // Logo oficial servido pela mesma origem; nenhum host externo.
    "connect-src 'self'",
    "form-action 'self'",
    "base-uri 'none'",
    "frame-ancestors 'none'"
  ].join('; ');
}

export function buildPairV1ManagerPageLab({ readHtml = () => readFile(PAGE, 'utf8'), managerFromRequest } = {}) {
  if (typeof managerFromRequest !== 'function') throw new TypeError('Autenticador de gerente obrigatório');
  if (typeof readHtml !== 'function') throw new TypeError('Leitor HTML obrigatório');
  return async function registerPairV1ManagerPageLab(app) {
    app.get('/autorizar', async (request, reply) => {
      const actor=managerFromRequest(request,reply);
      if (reply.sent) return;
      if (!actor || !['gerente','master'].includes(actor.papel) || !actor.id || !actor.restaurante_id)
        return reply.code(403).send({error:'Acesso de gerente necessario'});
      const html = await readHtml();
      if (typeof html !== 'string' || !html.includes('id="form"'))
        return reply.code(503).send('Página do laboratório indisponível');
      let csp;
      try { csp = cspForHtml(html); }
      catch { return reply.code(503).send('Página do laboratório indisponível'); }
      return reply
        .header('Cache-Control', 'no-store')
        .header('Referrer-Policy', 'no-referrer')
        .header('X-Content-Type-Options', 'nosniff')
        .header('X-Frame-Options', 'DENY')
        .header('Content-Security-Policy', csp)
        .type('text/html; charset=utf-8')
        .send(html);
    });
  };
}
