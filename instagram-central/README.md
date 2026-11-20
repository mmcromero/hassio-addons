# Central Instagram — Umdoislab (laboratório)

**Candidata experimental:** 0.1.6 · arquitetura aarch64 · Home Assistant Ingress. O login HTML já foi publicado na versão 0.1.5; conexão Meta real requer configuração e homologação próprias.

O nome de distribuição segue a norma do catálogo: **Fábrica de Softwares - Central Instagram**. O ícone e o logotipo públicos devem ser os arquivos oficiais padronizados, com blobs Git `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` e `7e500016222b0a5bf395be8ed17447edeb3e2af9`, respectivamente.

Este complemento é **independente da Central WhatsApp**. Recepção de webhooks Meta e armazenamento de rascunhos vêm **desativados**. Nenhuma rota do servidor envia Direct, consulta Gemini ou faz chamadas a WooCommerce/n8n.

## Primeiro teste no Home Assistant

Após uma **instalação autorizada**, o Supervisor fará o build do Dockerfile, incluindo quatro testes locais (assinatura e autenticação, SQLite/deduplicação, reserva+ACK e handoff). O build não exige GitHub Actions, QEMU ou imagem ARM64 pré-compilada.

Nesta branch, o painel Ingress exibe uma **tela HTML própria** para autenticação, com usuário `admin` e a senha existente em `panel_password` (mínimo 16 caracteres). Os campos `autocomplete=username` e `autocomplete=current-password` permitem que o Chrome ofereça armazenamento e preenchimento. Login cria sessão revogável no SQLite, expira após 12 horas, com botão **Sair**. Sem senha configurada, a entrada continua bloqueada. **Essa mudança não está publicada/instalada na versão 0.1.4.**

Preferir o Home Assistant via HTTPS já existente; em `http://192.168.0.6:8123`, o navegador sinaliza **conexão não privada** e credenciais trafegam sem TLS. A tela HTML não corrige esse risco de transporte. Testar inicialização, logs, login, logout e persistência somente após instalação autorizada.

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

## Lote 1 — Conectar Instagram e receber uma mensagem real

A versão 0.1.6 apresenta no painel:
- Checklist de campos Meta preenchidos (sem revelar segredos).
- **Autorização pela Meta:** depois do callback OAuth, o servidor verifica `/me/assigned_instagram_accounts` e exige a identidade exata de `@umdoislab` antes de guardar o token cifrado.
- **Verificar acesso Meta:** testa a credencial na Graph API com uma ação administrativa explícita.
- **Assinar mensagens na Meta:** solicita somente eventos `messages` para a conta Instagram identificada. Não envia mensagens e não habilita robôs.
- Contador de mensagens recebidas pelo webhook com HMAC válido e última data registrada; carregamento do painel não dispara chamadas Meta.

**Identificadores públicos confirmados no painel Meta:**
- Meta App ID: `1783613199623321`
- Login config ID: `990074610355962`
- Instagram Account ID: `17841454345931235`
- Callback OAuth candidato: `https://romeropi.duckdns.org:8443/oauth/meta/callback`
- Webhook candidato: `https://romeropi.duckdns.org:8443/webhook/instagram`

**Importante:** os caminhos HTTPS precisam ser validados no NGINX real. O arquivo de proxy foi preparado somente no repositório privado; não foi instalado no Raspberry. A Meta ainda não foi autorizada, não houve assinatura do webhook e nenhum recebimento real foi homologado. A versão 0.1.6 **não liga OAuth, webhook ou rascunhos automaticamente**. Nenhuma integração WhatsApp/n8n/Gemini é alterada.

Requisitos Meta: `instagram_basic` e `instagram_manage_messages`, token de usuário do sistema da configuração *Unified Login*, Graph API em `graph.facebook.com`. Token e segredo do app nunca entram no GitHub ou em conversas.

**Roteiro e critérios de aceite:** `docs/IG-LOT1-REAL-001.md` no repositório privado `mmcromero/instagram-automacoes` e Issue #1.
