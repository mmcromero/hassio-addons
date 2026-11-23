import { createApp } from './app.js';
import { loadConfig } from './config.js';
const config = loadConfig();
const app = await createApp(config);
if (config.mode === 'local') app.log.warn('Modo local sem autenticação: somente testes no próprio computador.');
for (const signal of ['SIGTERM', 'SIGINT'] as const) {
  process.once(signal, () => { void app.close().catch(() => { process.exitCode = 1; }); });
}
try {
  await app.listen({ host: config.host, port: config.port });
} catch (error) {
  app.log.error(error);
  await app.close();
  process.exitCode = 1;
}
