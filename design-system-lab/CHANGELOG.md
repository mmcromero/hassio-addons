# Changelog — Design System Lab

## 0.1.0-test.5 — 25/11/2026
- Corrige expansões de parâmetros shell no askpass e runner para que o Git receba o usuário/token somente durante o clone privado.


## 0.1.0-test.4 — 25/11/2026
- Substitui a base Home Assistant com S6 pela imagem oficial Node.js 22 Bookworm slim; o servidor inicia diretamente como PID 1, eliminando o conflito s6-overlay-suexec.
- Mantém a instalação de Chromium/Playwright e o campo protegido github_read_token.


## 0.1.0-test.3 — 25/11/2026
- Padroniza o nome exibido na loja e no painel com o prefixo oficial “Fábrica de Softwares”.


## 0.1.0-test.2 — 25/11/2026
- Remove o token GitHub do ambiente antes de executar npm ci, builds e testes do código baixado.


## 0.1.0-test.1 — 25/11/2026
- Primeira versão experimental para validação do Design System no Home Assistant ARM64.
- Clone privado com Fine-grained PAT somente leitura.
- npm ci, build, Vitest, Playwright/Chromium e Demo estática via Ingress.
- Sem acesso à API HA/Supervisor, Docker socket, host mounts ou portas públicas.
