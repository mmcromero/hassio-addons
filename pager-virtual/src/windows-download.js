import fs from 'node:fs';
import path from 'node:path';
import { currentUser } from './auth.js';

const DEFAULT_ZIP_PATH = '/share/avisaqui/windows/Avisaqui-Windows.zip';
const MAX_ZIP_BYTES = 200 * 1024 * 1024;

export function configuredWindowsZipPath(env = process.env) {
  // Valor ausente usa o padrão. Valor vazio/inválido foi desabilitado pelo
  // bootstrap e NÃO deve voltar silenciosamente para outro ZIP.
  if (env.WINDOWS_ZIP_PATH === undefined) return DEFAULT_ZIP_PATH;
  return typeof env.WINDOWS_ZIP_PATH === 'string' ? env.WINDOWS_ZIP_PATH : '';
}

function allowedUser(request) {
  const user = currentUser(request);
  return user && ['gerente', 'master'].includes(user.papel) && !!user.restaurante_id;
}

function zipMetadata() {
  const candidate = configuredWindowsZipPath();
  if (!path.isAbsolute(candidate) || !candidate.toLowerCase().endsWith('.zip')) return null;
  try {
    const metadata = fs.statSync(candidate);
    if (!metadata.isFile() || metadata.size < 4 || metadata.size > MAX_ZIP_BYTES) return null;
    const fd = fs.openSync(candidate, 'r');
    try {
      const signature = Buffer.alloc(4);
      if (fs.readSync(fd, signature, 0, 4, 0) !== 4 ||
          !(signature[0] === 0x50 && signature[1] === 0x4b &&
            [0x03, 0x05, 0x07].includes(signature[2]) &&
            [0x04, 0x06, 0x08].includes(signature[3]))) return null;
    } finally { fs.closeSync(fd); }
    return { candidate, metadata };
  } catch { return null; }
}

export async function windowsDownloadRoutes(fastify) {
  fastify.get('/api/windows/download/status', async (request, reply) => {
    if (!allowedUser(request)) return reply.code(403).send({ error: 'Acesso não autorizado' });
    reply.header('Cache-Control', 'no-store');
    const zip = zipMetadata();
    const version=process.env.WINDOWS_ZIP_VERSION;
    return {
      available: !!zip,
      version: zip && typeof version==='string' && /^[a-zA-Z0-9._+-]{1,64}$/.test(version) ? version : null,
      file_updated_at: zip ? zip.metadata.mtime.toISOString() : null,
      size_bytes: zip ? zip.metadata.size : null
    };
  });

  fastify.get('/api/windows/download', async (request, reply) => {
    if (!allowedUser(request)) return reply.code(403).send({ error: 'Acesso não autorizado' });
    const zip = zipMetadata();
    if (!zip) return reply.code(404).send({ error: 'ZIP Windows não disponível' });
    reply.header('Content-Type', 'application/zip');
    reply.header('Content-Length', String(zip.metadata.size));
    reply.header('Content-Disposition', 'attachment; filename="Avisaqui-Windows.zip"');
    reply.header('Cache-Control', 'private, no-store');
    reply.header('X-Content-Type-Options', 'nosniff');
    return reply.send(fs.createReadStream(zip.candidate));
  });
}
