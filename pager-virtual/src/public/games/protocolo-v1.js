// Contrato de mensagens avisaqui.games v1. Não transporta dados de pedidos.
export const PROTOCOL = 'avisaqui.games';
export const VERSION = 1;
export const MAX_MESSAGE_BYTES = 4096;
export const MAX_MESSAGES_PER_SECOND = 20;
export const STATES = Object.freeze(['CREATED','WAIT_READY','RUNNING','STOPPING','CLOSED']);
const TYPES = Object.freeze({
  frame: Object.freeze({ WAIT_READY: ['GAME_READY'], RUNNING: ['GAME_ERROR','GAME_EXIT'] }),
  controller: Object.freeze({ WAIT_READY: ['GAME_START','GAME_STOP'], RUNNING: ['GAME_STOP'] })
});
const MODES = new Set(['solo','dupla-local']);
const keys = ['protocol','version','type','instanceId','sequence','payload'];
const plain = value => value !== null && typeof value === 'object' && !Array.isArray(value) && Object.getPrototypeOf(value) === Object.prototype;
export function newInstanceId() {
  if (!globalThis.crypto?.randomUUID) throw new Error('Gerador criptográfico indisponível');
  return globalThis.crypto.randomUUID();
}
export function createEnvelope({ type, instanceId, sequence, payload = {} }) {
  return { protocol: PROTOCOL, version: VERSION, type, instanceId, sequence, payload };
}
export function validateEnvelope(value, { role, state, instanceId, lastSequence = -1 } = {}) {
  if (!plain(value) || Object.keys(value).sort().join(',') !== [...keys].sort().join(',')) return false;
  if (value.protocol !== PROTOCOL || value.version !== VERSION ||
      typeof value.instanceId !== 'string' || value.instanceId !== instanceId ||
      !Number.isSafeInteger(value.sequence) || value.sequence < 0 || value.sequence <= lastSequence ||
      !TYPES[role]?.[state]?.includes(value.type) || !plain(value.payload)) return false;
  if (JSON.stringify(value).length > MAX_MESSAGE_BYTES) return false;
  if (value.type === 'GAME_START') return Object.keys(value.payload).length === 1 && MODES.has(value.payload.mode);
  if (value.type === 'GAME_ERROR') return Object.keys(value.payload).length === 1 &&
    typeof value.payload.code === 'string' && /^[A-Z_]{1,32}$/.test(value.payload.code);
  return Object.keys(value.payload).length === 0;
}
export function createRateLimiter({ limit = MAX_MESSAGES_PER_SECOND, windowMs = 1000, now = () => Date.now() } = {}) {
  let start = now(), count = 0;
  return () => {
    const time = now();
    if (time - start >= windowMs) { start = time; count = 0; }
    return ++count <= limit;
  };
}
