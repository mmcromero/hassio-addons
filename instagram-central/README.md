# Central Instagram Umdoislab — versão 0.1.12 (diagnóstico OAuth)

**Estado:** versão 0.1.12 publicada no catálogo público `mmcromero/hassio-addons:main/instagram-central/` em 20/11/2026. Instalação/atualização e homologação no Home Assistant permanecem pendentes. O log real da versão 0.1.11 indicou falha em `parse_callback`; a conta ainda não foi verificada. Não declarar OAuth, mensagens, stories ou posts homologados. Mensagens e Editorial permanecem no mesmo add-on, painel e sessão.

- Repositório privado de origem: `mmcromero/instagram-automacoes`.
- Candidata de origem: [PR #8](https://github.com/mmcromero/instagram-automacoes/pull/8), branch `fix/instagram-oauth-state-diagnostics-001`, HEAD `c5953fd8e9da556179ac54c7df6dd329a0403f05`.
- Branch base: `feat/instagram-editorial-ux-patch-001`; branch atual da candidata: `fix/instagram-oauth-state-diagnostics-001`.
- Base imutável de código: PR #7, commit `f6ad64bc55bb3d8299c1e3cd71d40f5e63897082`, árvore original `instagram-central/` = `cf92e4dc5da1f75db389024499e8b7d951a6a24c`.
- Controle e evidências: [Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1), [PR #7](https://github.com/mmcromero/instagram-automacoes/pull/7), [relatório do gate](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md).
- Identidade de distribuição preservada: nome **Fábrica de Softwares - Central Instagram**, slug `umdoislab_instagram`, arquitetura declarada `aarch64`, Ingress `true` com porta interna `8099`, `backup: cold` e marca oficial. O catálogo público já contém `icon.png` e `logo.png` oficiais. **Não copiar nem recriar imagens na publicação**: manter os blobs existentes na pasta pública do Instagram.


## Versão 0.1.12 — diagnóstico de cookie, origem e proxy

- Reúne as alterações funcionais de 0.1.11 já publicadas: `redirect_uri` idêntico na troca de código e gravação de credenciais no diretório correto por negócio.
- Separa falhas de cookie ausente, duplicado e divergente. O log não imprime cookie, `state`, código OAuth ou segredo.
- Botão **Testar navegador e proxy (sem Meta)** verifica, em nova aba, se o navegador aceita e devolve um cookie temporário pelo HTTPS público; testa o mesmo caminho de callback e não contata a Meta. Reutiliza as rotas existentes `/oauth/meta/start` e `/oauth/meta/callback`; não altera o OAuth real.
- Acrescenta indicadores booleanos de correspondência entre Host público e autoridade do callback configurado, e de `X-Forwarded-Proto=https`.
- Mantém o cookie restrito a `Path=/oauth/meta/callback`; esse caminho corresponde ao callback. Não amplia para `/`.
- Não altera NGINX ativo, Ingress, Meta, credenciais, banco, mídias ou opções do HA.
- **Distribuição:** publicada na `main` do catálogo, somente na pasta `instagram-central/`. O build e a suíte integral do Dockerfile ainda dependem da instalação/atualização autorizada no Supervisor. Esta publicação não altera o Raspberry, NGINX ativo, opções, credenciais ou painel Meta.

## Versão 0.1.11 — correção de redirect_uri e isolamento de credenciais

- Inclui `redirect_uri` na troca do código OAuth.
- Usa `account_registry.credential_root(...)` ao armazenar token no callback e na assinatura.
- Adiciona testes de regressão unitário e HTTP.
- Publicação no catálogo público: PR #64, commit `fe90bd3ee77e03a15a40d9320d034616a3c72656`. O erro de `parse_callback` persistiu após a atualização relatada pelo proprietário.

## Candidata 0.1.10 — retorno OAuth e nova aba

- Link externo da Meta usa nova aba e `rel="noopener noreferrer"` para não abrir login dentro do iframe do Home Assistant.
- Logs locais do callback identificam a **etapa** da falha sem exibir URL com `code`, `state`, cookies, credenciais ou dados retornados pela Meta.
- Inclui teste de regressão dirigido; a suíte integral é verificada pelo Dockerfile no build do Supervisor. Nenhum PASS do Supervisor é declarado antes da atualização real.
- Sem alterações nos bancos, rascunhos, credenciais existentes ou nas rotas de publicação; não habilita envio ou publicação Meta.

## Funcionalidades incluídas no código 0.1.7

**Mensagens:** interface administrativa com formulário HTML e sessão única, visão de mensagens, indicador de estado de conexão, handoff e auditoria, deduplicação e filas locais com claim/ACK, políticas offline e OAuth Meta preparado mas desligado. O painel usa a senha própria `panel_password` e não envia Direct.

**Editorial:** a navegação abre `/editorial/` no mesmo servidor e sessão de Mensagens. Biblioteca de mídia, upload JPG/PNG/MP4 com validação de tipos/limites, rascunhos, edição, aprovação, agenda no fuso `America/Sao_Paulo`, cancelamento e recarga persistente via HTTP+SQLite. Edição invalida aprovação/agenda anterior; operações obsoletas recebem conflito de versão. **A agenda é local, não realiza postagem.** Não há segundo login nem serviço Editorial separado.

**Estrutura multicontas:** cadastro interno de negócios, separação entre `business_id` e ID da conta oficial Meta e isolamento de tokens/mídias. Nesta candidata, **somente Umdoislab** tem rotas administrativas operacionais. Outras contas são apenas sintéticas em testes; nenhuma ativação real.

## Patch 0.1.8 — interface Editorial (não publicado)

- **Feed automático:** a opção Publicação no feed aceita 1–20 imagens; uma imagem mantém `feed`, várias imagens são gravadas como `carousel`. Story e Reel continuam separados. Rascunhos anteriores mantêm o tipo.
- **Legendas locais por imagem:** quando o carrossel tem 2 ou mais imagens, escolher *Uma legenda para todas as imagens* ou *Legenda individual por imagem*. O SQLite mantém `caption_mode` na publicação e `slide_caption` em cada anexo, com migração **aditiva**. A API aceita `captionMode` e `slideCaptions` opcionais, mantendo chamadas antigas válidas. **A API Meta não está habilitada para publicar essas legendas**; não há conversão ou descarte silencioso.
- **Prévia no Editor e em Aprovações:** setas para percorrer carrossel, contador posição/total; miniatura de capa e bloco de texto clicáveis no cartão de Aprovações. O modal grande abre **somente leitura**, sem formulário/edição/aprovação. Editar, Aprovar, Agendar e Cancelar mantêm as ações anteriores.
- **Título do cartão:** sem novo campo obrigatório. A interface utiliza o início da legenda geral (ou primeira legenda individual) como título curto, seguido de resumo visual; depois mostra tipo e status. Preserva os rascunhos existentes.
- **Mídia indisponível em aba antiga (H11):** se foto/vídeo apresentar erro de carregamento, Biblioteca e prévia mostram aviso junto à própria mídia orientando atualizar a página. Falhas de upload/salvar exibem alerta persistente perto do componente afetado, com tratamento de sessão inválida e resposta não JSON. O app não reinicia a sessão automaticamente, não repete gravações sem confirmação e não assume que a falha é expiração de login. A sessão do painel já existente expira em 12 horas; tokens CSRF de ação são obtidos no momento da ação. A causa do H11 ainda depende de evidência de status HTTP/log para ser identificada.
- **Agendar com contexto (H10):** o modal mostra miniatura da primeira mídia (ou frame de vídeo), título derivado da legenda e trecho da legenda para confirmar a publicação correta. Erros de data passada são mostrados dentro da janela, junto ao botão **Confirmar agenda**, sem fechar o modal nem apagar a entrada. Horário civil é comparado em `America/Sao_Paulo`, **além** da validação obrigatória no servidor. Respostas inesperadas do servidor deixam de expor mensagens técnicas `JSON.parse` ao operador; um retorno não JSON não será tratado como gravação confirmada. Nenhuma mudança no backend de publicação Meta.
- **Edições simultâneas (H09):** o backend mantém bloqueio por versão (HTTP 409). Em caso de conflito, o formulário mostra alerta de erro persistente **“Não foi salvo”**, preserva a digitação local e não trata a ação como sucesso. A mensagem explica que outra aba alterou a publicação e orienta recuperar a versão atual. Não é feito merge automático das duas edições nem sobrescrita da versão mais recente.
- **Padrão visual e logout único:** painel Mensagens passa a usar o mesmo tema escuro, hierarquia, menu lateral e cabeçalho do Editorial; os formulários `Assumir`, `Aguardar`, `Concluir`, `Voltar ao bot` e os controles Meta são preservados. O cabeçalho de ambos mostra conta e botão **Sair**. No Editorial, usa `action="../auth/logout"`, no painel Mensagens `action="auth/logout"`; ambas resolvem para **a rota administrativa existente** `POST /auth/logout`. Não há nova senha, cookie, rota de logout ou envio externo.
- **Calendário com reserva e revisão:** ao editar uma publicação já agendada, a data e a hora continuam registradas em `pending_schedule_at` e a execução fica bloqueada até nova aprovação. A publicação aparece no calendário com destaque visual e botão **Aprovar** diretamente na lista. Ao aprovar, o horário original volta se futuro; se vencido, permanece visível como expirado e solicita reagendamento. O botão **Cancelar agenda** segue limpando a reserva ativa.
- **Teste de F5 do Ingress:** retorno ocasional à página Mensagens relatado; sem causa confirmada, o patch não altera o roteamento do Home Assistant.
- **Evidência:** novos testes Python de migração, validação e persistência e roteiro de Chromium incorporados aos testes de desenvolvimento. **Não estão executados nesta conversa**; não confundir revisão de fonte com PASS de homologação.

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

No corte base do PR #7, anterior às alterações OAuth 0.1.11 e 0.1.12:
- `python3 scripts/validate_offline.py`: **152/152 PASS**.
- `node instagram-central/tests/editorial_browser.cjs`: **PASS** em navegador Chromium com dados sintéticos.
- Build complementar no Linux/amd64, montando CA temporária do executor como segredo BuildKit: **149/149 testes do add-on PASS**. O Dockerfile original falhou por confiança TLS ao buscar índices Alpine naquele ambiente (exit 1); a execução não ocorreu em novo ambiente Codex independente.

Essas evidências **não comprovam** build `aarch64` ou execução no Home Assistant, e não devem ser repetidas por rotina quando só versão/documentação mudou. O Supervisor poderá construir no hardware alvo **apenas durante uma instalação autorizada**. Norma: [P0 do catálogo Home Assistant](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md).

## Distribuição Home Assistant — hotfix 0.1.9 para corrigir build ARM64

A versão 0.1.8 foi publicada no catálogo, mas **não passou na compilação dos testes dentro do Dockerfile no HA**, conforme o log do proprietário. O erro ocorreu antes da execução dos testes e da inicialização da nova versão. A 0.1.9 corrige a expressão Python inválida, usando `.encode("utf-8")` na asserção do `aria-label`. Nenhum módulo de execução, dado `/data`, token, opção de autenticação, ícone ou slug é alterado. A fonte do pacote novo está nesta branch; a publicação é feita pela P0 do catálogo apenas após conferência do diff e dos testes dirigidos. O Supervisor validará `py_compile` e a suíte no próximo build de atualização autorizada. O estado instalado atual deve ser confirmado no HA, não inferido do GitHub.

Documentação técnica: [contrato Mensagens + Editorial](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001.md), [relatório Codex](https://github.com/mmcromero/instagram-automacoes/blob/f6ad64bc55bb3d8299c1e3cd71d40f5e63897082/docs/IG-MULTICONTAS-001-RELATORIO-CODEX.md), [plano de homologação](https://github.com/mmcromero/instagram-automacoes/blob/6a6b4766c013d856b40856c06b47f53bef4a2d69/docs/IG-PR7-HOM-001-PLANO-CANDIDATA-HOMOLOGACAO.md). Consulte `CHANGELOG.md` para o histórico de versões anteriores.
