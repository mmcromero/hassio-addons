import { defineConfig } from 'vite';
import { readFileSync } from 'node:fs';
const { version } = JSON.parse(readFileSync(new URL('./package.json', import.meta.url), 'utf8'));
const release=JSON.parse(readFileSync(new URL('./artesao-release.json', import.meta.url),'utf8'));
export default defineConfig({ base: './', define: { __APP_VERSION__: JSON.stringify(version), __ARTESAO_RELEASE__:JSON.stringify(release.version) } });
