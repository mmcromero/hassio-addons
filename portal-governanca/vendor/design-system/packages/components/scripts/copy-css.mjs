import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pkgRoot = path.resolve(__dirname, '..');

const srcCss = path.join(pkgRoot, 'src', 'styles', 'components.css');
const distCss = path.join(pkgRoot, 'dist', 'styles.css');

fs.mkdirSync(path.dirname(distCss), { recursive: true });
fs.copyFileSync(srcCss, distCss);
console.log('✅ Estilos de componentes copiados para packages/components/dist/styles.css');
