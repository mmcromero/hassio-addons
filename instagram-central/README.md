# Central Instagram Umdoislab — distribuição 0.1.7

**Estado:** versão **0.1.7 publicada no catálogo GitHub**; atualização e homologação no Home Assistant **ainda não executadas**. A versão 0.1.6 é a distribuição anterior e foi informada pelo proprietário como instalada. Esta 0.1.7 reúne Mensagens + Editorial no **mesmo aplicativo, sessão, login e Ingress**, sem criar outra integração.

- Repositório privado: `mmcromero/instagram-automacoes`.
- Branch da candidata: `release/instagram-0.1.7-rc.1`.
- Base imutável de código: PR #7, commit `f6ad64bc55bb3d8299c1e3cd71d40f5e63897082`, árvore original `instagram-central/` = `cf92e4dc5da1f75db389024499e8b7d951a6a24c`.
- Controle e evidências: [Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1), [PR #7](https://github.com/mmcromero/instagram-automacoes/pull/7), [relatório do gate](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md).
- Identidade de distribuição preservada: nome **Fábrica de Softwares - Central Instagram**, slug `umdoislab_instagram`, arquitetura declarada `aarch64`, Ingress `true` com porta interna `8099`, `backup: cold` e marca oficial. O catálogo público já contém `icon.png` e `logo.png` oficiais. **Não copiar nem recriar imagens na publicação**: manter os blobs existentes na pasta pública do Instagram.

## Funcionalidades incluídas no código 0.1.7

**Mensagens:** interface administrativa com formulário HTML e sessão única, visão de mensagens, indicador de estado de conexão, handoff e auditoria, deduplicação e filas locais com claim/ACK, políticas offline e OAuth Meta preparado mas desligado. O painel usa a senha própria `panel_password` e não envia Direct.

**Editorial:** a navegação abre `/editorial/` no mesmo servidor e sessão de Mensagens. Biblioteca de mídia, upload JPG/PNG/MP4 com validação de tipos/limites, rascunhos, edição, aprovação, agenda no fuso `America/Sao_Paulo`, cancelamento e recarga persistente via HTTP+SQLite. Edição invalida aprovação/agenda anterior; operações obsoletas recebem conflito de versão. **A agenda é local, não realiza postagem.** Não há segundo login nem serviço Editorial separado.

**Estrutura multicontas:** cadastro interno de negócios, separação entre `business_id` e ID da conta oficial Meta e isolamento de tokens/mídias. Nesta candidata, **somente Umdoislab** tem rotas administrativas operacionais. Outras contas são apenas sintéticas em testes; nenhuma ativação real.

## Dados e compatibilidade

- Mensagens, fila, estados, sessões e registro de contas: `/data/instagram.sqlite3` (SQLite WAL).
- Editorial da Umdoislab: `/data/editorial/editorial.sqlite3` e `/data/editorial/media/`.
- Chaves e token cifrado Meta, **se existirem**: permanecem na raiz `/data`, sem migração destrutiva; `/data/options.json` contém opções operacionais privadas no ambiente do add-on. Nunca copiar dados, tokens, opções ou chaves reais para o pacote ou para o Git.
- Migrações são aditivas; preservar diretórios, credenciais, mídias, chaves e os dois bancos durante qualquer atualização futura autorizada. Histórico `IndexedDB` do protótipo não é apagado nem importado automaticamente. Um backup consistente, inclusive WAL e mídia, deve ser avaliado no portão da instalação; não bloqueia a preparação privada deste pacote.

## Estado seguro por padrão

`ingress_enabled: false`, `drafts_enabled: false`, `meta_oauth_enabled: false`. São opções de integração específicas, **não** o campo `ingress: true` que apresenta o painel pelo Home Assistant. Senhas/segredos começam vazios no manifesto e nunca devem aparecer no Git.

A Central **não** publica posts, não envia Direct, não liga robô Gemini, não chama WooCommerce/n8n ou WhatsApp, não configura NGINX e não expõe a porta 8099 diretamente. Meta real, webhooks e primeira DM pertencem a homologação futura com autorização específica. `publishingEnabled:false` nas APIs editoriais.

Acesso administrativo deve ser por HA Ingress e HTTPS confiável quando usado com credenciais reais. A sessão do painel e as rotas Editorial exigem autenticação; mutações exigem CSRF por ação, e a mídia é privada. MP4 passa por verificação **estrutural**; não há transcodificação nem antivírus. Limites atuais: 25 MiB por upload, 20 MP para imagens, biblioteca até 500 arquivos/1 GiB e até 1000 publicações locais. Não há rotina automática de limpeza.

## Testes de desenvolvimento — evidências já aceitas com ressalvas

No código base do PR #7, sem alterações de lógica nesta candidata:
- `python3 scripts/validate_offline.py`: **152/152 PASS**.
- `node instagram-central/tests/editorial_browser.cjs`: **PASS** em navegador Chromium com dados sintéticos.
- Build complementar no Linux/amd64, montando CA temporária do executor como segredo BuildKit: **149/149 testes do add-on PASS**. O Dockerfile original falhou por confiança TLS ao buscar índices Alpine naquele ambiente (exit 1); a execução não ocorreu em novo ambiente Codex independente.

Essas evidências **não comprovam** build `aarch64` ou execução no Home Assistant, e não devem ser repetidas por rotina quando só versão/documentação mudou. O Supervisor poderá construir no hardware alvo **apenas durante uma instalação autorizada**. Norma: [P0 do catálogo Home Assistant](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md).

## Distribuição Home Assistant — catálogo publicado, instalação pendente

A fonte privada 0.1.7 permanece em `release/instagram-0.1.7-rc.1`. A distribuição correspondente está em `mmcromero/hassio-addons:main/instagram-central/`, preservando os dois arquivos de marca oficiais, `icon.png` e `logo.png`.

**Próximo passo, mediante autorização específica:** atualizar apenas o add-on Central Instagram no Home Assistant, preservando opções e dados. Após a instalação, conferir o build do Supervisor, login, Mensagens e Editorial. Registrar a evidência na Issue #1.

O método oficial é publicar **os arquivos da pasta no GitHub**, não gerar TAR, ZIP ou imagem Docker separada. Na atualização autorizada do Home Assistant, o Supervisor poderá construir o add-on pelo Dockerfile na arquitetura alvo. **Publicação no catálogo não equivale a instalação ou homologação**. Não iniciar Actions, fazer merge automático do PR #7 nem ativar Meta.

Documentação técnica: [contrato Mensagens + Editorial](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001.md), [relatório Codex](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001-RELATORIO-CODEX.md), [plano de homologação](https://github.com/mmcromero/instagram-automacoes/blob/6a6b4766c013d856b40856c06b47f53bef4a2d69/docs/IG-PR7-HOM-001-PLANO-CANDIDATA-HOMOLOGACAO.md). Consulte `CHANGELOG.md` para o histórico de versões anteriores.
