# Central Instagram — Umdoislab (laboratório)

**Candidata de publicação:** 0.1.2 · arquitetura aarch64 · Home Assistant Ingress.

O nome de distribuição segue a norma do catálogo: **Fábrica de Softwares - Central Instagram**. O ícone e o logotipo públicos devem ser os arquivos oficiais padronizados, com blobs Git `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` e `7e500016222b0a5bf395be8ed17447edeb3e2af9`, respectivamente.

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


## OAuth Meta — desenvolvimento isolado (ainda não instalado)

A branch `feat/instagram-meta-unified-oauth` acrescenta o fluxo **Meta Unified Login** com `config_id`, retorno `GET /oauth/meta/callback`, `state` único com cookie seguro, troca do código no Graph e credencial criptografada em `/data`. Continua **desativado por padrão** (`meta_oauth_enabled:false`). Essa função ainda não está presente na versão 0.1.1 instalada antes da atualização autorizada.

Rotas de laboratório: `/oauth/meta/start` e `/oauth/meta/status` requerem Basic do administrador. `/oauth/meta/callback` é público somente após futura configuração de proxy HTTPS específico e OAuth ativado. O token **não é mostrado em resposta, log ou painel**. A existência do token não comprova acesso validado à conta Instagram. Nenhuma chamada de envio de mensagens foi adicionada.

**Não cadastre URL de redirecionamento na Meta agora**: é necessário antes definir e homologar uma rota pública HTTPS que encaminhe somente os caminhos OAuth, sem expor os endpoints de bridge, o painel ou outros serviços. Consulte `docs/META-OAUTH-UNIFIED-001.md`.

## Versão 0.1.2 — ativação não automática

Atualização experimental com OAuth Meta desativado por padrão. O callback só funcionará após configuração específica e homologada do HTTPS em `https://romeropi.duckdns.org:8443/oauth/meta/callback` e opção `meta_oauth_enabled: true`. **Não preencha nem ative as credenciais OAuth neste primeiro teste.** O formulário Meta só deve receber a URL depois que a rota pública estiver verificada. Não há envio de mensagens ou acesso ao WhatsApp.
