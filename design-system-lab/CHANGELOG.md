# Changelog — Design System Lab

## 0.1.0-test.3 — 25/11/2026
- Padroniza o nome exibido na loja e no painel com o prefixo oficial “Fábrica de Softwares”.


## 0.1.0-test.2 — 25/11/2026
- Remove o token GitHub do ambiente antes de executar npm ci, builds e testes do código baixado.


## 0.1.0-test.1 — 25/11/2026
- Primeira versão experimental para validação do Design System no Home Assistant ARM64.
- Clone privado com Fine-grained PAT somente leitura.
- npm ci, build, Vitest, Playwright/Chromium e Demo estática via Ingress.
- Sem acesso à API HA/Supervisor, Docker socket, host mounts ou portas públicas.
