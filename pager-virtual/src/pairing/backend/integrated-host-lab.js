// AVISAQUI-PAIR-001 — montagem completa somente em laboratorio isolado.
// Montado por src/server.js somente com opt-in explícito em banco de laboratório.
import { buildPairV1LabRoutes } from './routes-lab.js';
import { buildPairV1ManagerPageLab } from './manager-page-lab.js';
import { managerFromAvisaquiSession } from './session-adapter.js';
import { currentUser } from '../../auth.js';

export async function registerPairV1IntegratedLab(app, {db, publicOrigin, policy, mountPrefix='/avisaqui', managerFromRequest=managerFromAvisaquiSession} = {}) {
  if (!db || typeof db.prepare !== 'function') throw new TypeError('SQLite do laboratorio obrigatorio');
  const parsed=new URL(publicOrigin);
  if(parsed.protocol!=='https:' || parsed.username || parsed.password || parsed.search || parsed.hash ||
    parsed.pathname!=='/avisaqui' && parsed.pathname!=='/avisaqui/') throw new TypeError('Origem /avisaqui HTTPS obrigatoria');
  if(typeof managerFromRequest!=='function') throw new TypeError('Autenticador de sessao obrigatorio');
  // Proxies podem remover /avisaqui antes de enviar ao servidor interno.
  // O prefixo deve ser explícito; nunca derivado de headers do cliente.
  if(!['/avisaqui',''].includes(mountPrefix))
    throw new TypeError('Prefixo interno de pareamento nao autorizado');
  // Plugin registrado somente com opt-in e configuracao explicita do host de testes.
  await app.register(buildPairV1LabRoutes({db,publicOrigin,policy,managerFromRequest}),{prefix:mountPrefix || '/'});
  // Navegador sem sessão: encaminhar ao login do próprio Avisaqui, preservando somente
  // a solicitação UUID; API/JSON continuam falhando fechado pela autenticação real.
  const pageManager = (request, reply) => {
    if (managerFromRequest===managerFromAvisaquiSession &&
        /text\/html/i.test(request.headers.accept || '') &&
        !currentUser(request)) {
      const id=request.query?.solicitacao;
      const uuid=/^[0-9a-f]{8}-[0-9a-f]{4}-[1-8][0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/i;
      if(typeof id!=='string' || !uuid.test(id)) {
        reply.code(400).send({error:'Solicitação inválida'});return null;
      }
      const target='/avisaqui/autorizar?solicitacao='+encodeURIComponent(id);
      reply.code(303).header('Location','/avisaqui/login.html?return_to='+encodeURIComponent(target)).send();
      return null;
    }
    return managerFromRequest(request,reply);
  };
  await app.register(buildPairV1ManagerPageLab({managerFromRequest:pageManager}),{prefix:mountPrefix || '/'});
}
