import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const pkgRoot = path.resolve(__dirname, '..');
const srcDir = path.join(pkgRoot, 'src');
const distDir = path.join(pkgRoot, 'dist');

if (!fs.existsSync(distDir)) {
  fs.mkdirSync(distDir, { recursive: true });
}

// 1. Read sources
const refRaw = JSON.parse(fs.readFileSync(path.join(srcDir, 'ref.json'), 'utf8'));
const sysRaw = JSON.parse(fs.readFileSync(path.join(srcDir, 'sys.json'), 'utf8'));
const darkRaw = JSON.parse(fs.readFileSync(path.join(srcDir, 'theme-dark.json'), 'utf8'));
const govRaw = JSON.parse(fs.readFileSync(path.join(srcDir, 'theme-governance.json'), 'utf8'));

// Helper to flatten token object to path -> value
function flattenTokens(obj, prefix = '') {
  let result = {};
  for (const [key, val] of Object.entries(obj)) {
    if (key.startsWith('$')) continue;
    const currentPath = prefix ? `${prefix}.${key}` : key;
    if (val && typeof val === 'object' && '$value' in val) {
      result[currentPath] = {
        value: val.$value,
        type: val.$type || 'string'
      };
    } else if (val && typeof val === 'object') {
      Object.assign(result, flattenTokens(val, currentPath));
    }
  }
  return result;
}

const refFlat = flattenTokens(refRaw);
const sysFlat = flattenTokens(sysRaw);
const darkFlat = flattenTokens(darkRaw.sys, 'sys');
const govFlat = flattenTokens(govRaw.sys, 'sys');

// Alias resolver
function resolveValue(val, lookup) {
  if (typeof val !== 'string') return val;
  const match = val.match(/^{(.+?)}$/);
  if (!match) return val;
  const targetKey = match[1];
  if (lookup[targetKey]) {
    return resolveValue(lookup[targetKey].value, lookup);
  }
  throw new Error(`Token alias não resolvido: "${val}" referenciado mas não encontrado no dicionário.`);
}

const allRefLookup = { ...refFlat };
const resolvedRef = {};
for (const [k, v] of Object.entries(refFlat)) {
  resolvedRef[k] = { ...v, value: resolveValue(v.value, allRefLookup) };
}

const allLookup = { ...resolvedRef, ...sysFlat };
const resolvedSys = {};
for (const [k, v] of Object.entries(sysFlat)) {
  resolvedSys[k] = { ...v, value: resolveValue(v.value, allLookup) };
}

const resolvedDark = {};
for (const [k, v] of Object.entries(darkFlat)) {
  resolvedDark[k] = { ...v, value: resolveValue(v.value, allLookup) };
}

const resolvedGov = {};
for (const [k, v] of Object.entries(govFlat)) {
  resolvedGov[k] = { ...v, value: resolveValue(v.value, allLookup) };
}

// Convert path to CSS custom property name: ref.color.neutral.50 -> --ds-ref-color-neutral-50
function toCssVarName(path) {
  return '--ds-' + path.replace(/\./g, '-');
}

// Generate CSS
let css = `/**\n * Design System mmcromero — Tokens Semânticos\n * Este arquivo é gerado automaticamente. Não editar manualmente.\n * Fonte: packages/tokens/src/\n */\n\n:root {\n`;

// Ref tokens
css += `  /* Fundamentos / Referência */\n`;
for (const [pathKey, item] of Object.entries(resolvedRef)) {
  css += `  ${toCssVarName(pathKey)}: ${item.value};\n`;
}

// Default Sys tokens
css += `\n  /* Semântica do Sistema */\n`;
for (const [pathKey, item] of Object.entries(resolvedSys)) {
  css += `  ${toCssVarName(pathKey)}: ${item.value};\n`;
}
css += `}\n\n`;

// Dark theme
css += `/* Tema Escuro: [data-theme="dark"] e prefers-color-scheme */\n`;
css += `@media (prefers-color-scheme: dark) {\n  :root:not([data-theme="light"]) {\n`;
for (const [pathKey, item] of Object.entries(resolvedDark)) {
  css += `    ${toCssVarName(pathKey)}: ${item.value};\n`;
}
css += `  }\n}\n\n`;

css += `[data-theme="dark"] {\n`;
for (const [pathKey, item] of Object.entries(resolvedDark)) {
  css += `  ${toCssVarName(pathKey)}: ${item.value};\n`;
}
css += `}\n\n`;

// Governance theme (brand override)
css += `/* Tema da Marca: Portal de Governança */\n`;
css += `[data-theme="governance"] {\n`;
for (const [pathKey, item] of Object.entries(resolvedGov)) {
  css += `  ${toCssVarName(pathKey)}: ${item.value};\n`;
}
css += `}\n\n`;

// Reduced motion override
css += `/* Acessibilidade: Movimento Reduzido (WCAG 2.2 / prefers-reduced-motion) */\n`;
css += `@media (prefers-reduced-motion: reduce) {\n  :root {\n`;
css += `    --ds-ref-motion-duration-fast: 0ms;\n`;
css += `    --ds-ref-motion-duration-normal: 0ms;\n`;
css += `    --ds-ref-motion-duration-slow: 0ms;\n`;
css += `  }\n}\n`;

fs.writeFileSync(path.join(distDir, 'tokens.css'), css, 'utf8');

// Export JSON
const fullJson = {
  ref: resolvedRef,
  sys: resolvedSys,
  themes: {
    dark: resolvedDark,
    governance: resolvedGov
  }
};
fs.writeFileSync(path.join(distDir, 'tokens.json'), JSON.stringify(fullJson, null, 2), 'utf8');

// Export JS / TS
const jsContent = `export const tokens = ${JSON.stringify(fullJson, null, 2)};\nexport default tokens;\n`;
fs.writeFileSync(path.join(distDir, 'index.js'), jsContent, 'utf8');

const dtsContent = `export interface TokenItem {\n  value: string;\n  type: string;\n}\n\nexport declare const tokens: {\n  ref: Record<string, TokenItem>;\n  sys: Record<string, TokenItem>;\n  themes: {\n    dark: Record<string, TokenItem>;\n    governance: Record<string, TokenItem>;\n  };\n};\n\nexport default tokens;\n`;
fs.writeFileSync(path.join(distDir, 'index.d.ts'), dtsContent, 'utf8');

console.log('✅ Tokens compilados com sucesso em packages/tokens/dist/');
