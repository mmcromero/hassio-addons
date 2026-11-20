# Central Instagram — Umdoislab (laboratório)

**Primeira candidata:** 0.1.0 · arquitetura aarch64 · Home Assistant Ingress.

Este complemento é **independente da Central WhatsApp**. Recepção de webhooks Meta e armazenamento de rascunhos vêm **desativados**. Nenhuma rota do servidor envia Direct, consulta Gemini ou faz chamadas a WooCommerce/n8n.

## Primeiro teste no Home Assistant

Após uma **instalação autorizada**, o Supervisor fará o build do Dockerfile, incluindo quatro testes locais (assinatura e autenticação, SQLite/deduplicação, reserva+ACK e handoff). O build não exige GitHub Actions, QEMU ou imagem ARM64 pré-compilada.

Iniciar o add-on manualmente. O painel Ingress solicita usuário `admin` e a senha configurada em `panel_password` (mínimo 16 caracteres). Sem senha, a entrada fica bloqueada. Testar somente inicialização, logs, painel e persistência com dados sintéticos.

**Não ativar `ingress_enabled` ou `drafts_enabled` nesta candidata.** Ainda não há integração real Meta; nenhum token deve ser configurado sem a etapa própria.

Banco de dados persistente: `/data/instagram.sqlite3`. Não apagar, copiar para o Git nem compartilhar conteúdo real. Não expor a porta 8099 diretamente.

## Segurança e limites

- Painel HTML com autenticação independente e proteção CSRF, sem envio.
- Bridge por `X-Instagram-Bridge-Secret` (mínimo 32 caracteres), mas sem n8n conectado.
- Entrada Meta com assinatura HMAC-SHA256, desligada por padrão.
- Não há credenciais, logins, dados reais de clientes ou serviços externos no pacote.
- Publicação no catálogo não equivale a instalação ou homologação no Raspberry.

Fonte de desenvolvimento: `mmcromero/instagram-automacoes`, branch `feat/central-instagram-fase1`, PR #2. Evidências e acompanhamento: Issue #1.
