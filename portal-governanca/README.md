# Portal de Governança — add-on Home Assistant

**Candidata:** 0.1.0-dev.36.

Add-on independente para Home Assistant OS, acessado exclusivamente pelo Ingress. Esta pasta é o pacote de distribuição gerado a partir do repositório-fonte mmcromero/portal-governanca; não é uma segunda fonte de código.

## Segurança

- Arquitetura aarch64, alvo Raspberry Pi 4.
- Ingress obrigatório, painel restrito a administradores e sem portas publicadas.
- O servidor aceita somente conexões do proxy Supervisor em 172.30.32.2 e exige X-Ingress-Path válido.
- Sem login Basic duplicado no Ingress.
- GitHub é opcional; token Fine-grained somente leitura permanece no servidor.
- Cadastro controlado de projetos usa credencial Fine-grained separada, opcional, para criar somente o marcador .portal-governanca.json.
- A integração Supervisor usa exclusivamente hassio_api com hassio_role default e um bridge isolado que consulta slugs allowlisted por GET. Não usa manager/admin, homeassistant_api, Docker API, host network ou portas públicas.
- O token Supervisor permanece isolado no processo bridge; o processo Node principal não recebe SUPERVISOR_TOKEN, HASSIO_TOKEN ou SUPERVISOR_API.
- Integração n8n é somente leitura e não executa nem ativa workflows.
- O health check local /healthz não retorna configuração nem credenciais.

## Histórico dos projetos

- Coleta GitHub incremental de commits, Issues, Pull Requests e releases.
- Evidências são persistidas no ledger append-only, com hash encadeado, deduplicação, fonte, link e confiança.
- Dias ativos são dias distintos com commits observados no fuso America/Sao_Paulo; não representam horas trabalhadas.
- O início não é inferido da data de criação do repositório.
- Encerramento depende de registro explícito do proprietário; o contador congela nessa data.
- A coleta e o build/testes são executados no ambiente de destino pelo Supervisor durante a instalação/atualização.

## Instalação e homologação

O build multi-stage ocorre no próprio Home Assistant aarch64: npm ci, build do Design System vendorizado, suíte Vitest e build TypeScript/Vite. A homologação funcional deve ocorrer pelo botão Abrir interface, com inspeção de assets, APIs, navegação, Ingress e logs do app/Supervisor. Publicação no catálogo não equivale a instalação nem homologação.
