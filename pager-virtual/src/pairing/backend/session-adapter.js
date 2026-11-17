// Adaptador opt-in da autenticação existente. NÃO importar no src/server.js.
// A autenticação obtém sessão e restaurante diretamente do banco, nunca de headers de teste.
import { requireRestaurant } from '../../auth.js';

export function managerFromAvisaquiSession(request, reply) {
  // requireRestaurant já valida sessão, restaurante selecionado e Origin/Host
  // para chamadas de escrita. Mantemos o contrato da mesma base autenticada.
  return requireRestaurant(request, reply);
}
