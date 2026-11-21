# Central Instagram Umdoislab — 0.1.18 (HTTPS no proxy existente)

**Estado:** pacote para teste autorizado; sem instalação ou homologação presumida. A 0.1.18 substitui a proposta 0.1.17 de expor diretamente 9443. Não abrir nova porta no roteador. O HTTPS continua no NGINX existente, com hostname exclusivo para isolar o service worker do HA.

- Origem privada: `mmcromero/instagram-automacoes`, branch `fix/instagram-oauth-safe-diagnostics-001`, [PR #11](https://github.com/mmcromero/instagram-automacoes/pull/11). Commits, evidências e revisão independente na [Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1).
- Identidade preservada: nome **Fábrica de Softwares - Central Instagram**, slug `umdoislab_instagram`, `aarch64`, Ingress na porta interna 8099, `backup: cold`, ícones oficiais. O catálogo não publica portas nem monta `/ssl` na Central.
- Mesmos login/senha, banco, tokens e mídias em `/data`; nenhuma exclusão/migração de dados nesta mudança. `certfile`/`keyfile` antigos são aceitos mas ignorados para compatibilidade com opções já salvas.
- Base histórica: PR #7 `f6ad64bc55bb3d8299c1e3cd71d40f5e63897082`, PR #9 `723b423069c18a19c1053aecaf3bcef399b0efbb`. Fonte main privada e demais aplicativos preservados.

## Configuração atual

Acesso proposto: **https://instagram.romeropi.duckdns.org:8443/panel**. O hostname resolve em DNS, mas a ativação depende de certificado e proxy do operador. O certificado confirmado pelo proprietário cobre somente `romeropi.duckdns.org`; precisa incluir o novo hostname/wildcard antes de ativá-lo. Não ignorar aviso de certificado.

**[Siga o guia do operador: certificado, arquivo adicional, teste e rollback](proxy/GUIA-OPERADOR.md).** O arquivo revisável é [proxy/instagram.conf](proxy/instagram.conf), incluído por `customize.servers`, na mesma porta interna 443 já usada pelo proxy (externa 8443). Não substitui o servidor HA ou fragmentos dos outros aplicativos.

Após atualizar para 0.1.18, preserve todas as opções e ajuste somente:

```yaml
public_base_url: "https://instagram.romeropi.duckdns.org:8443"
meta_oauth_redirect_uri: "https://instagram.romeropi.duckdns.org:8443/oauth/meta/callback"
```

Os links **Abrir Central em janela própria** aparecem no login e painel do Ingress. Na URL nova, use o mesmo `admin`/senha da Central. O hostname separado isola o worker raiz do HA e os cookies host-only. A origem antiga é recusada no OAuth quando a nova origem está configurada; callback divergente é bloqueado antes de state/exchange.

## Controles e validação

O proxy contém lista explícita de rotas e métodos para login, painel, Editorial e OAuth. Rotas bridge, health, Supervisor, scripts do worker e caminhos desconhecidos não são publicados nesse host. Login limitado por IP no NGINX, corpo limitado por rota, upload máximo 25 MiB, Host/SNI conferidos, sem cache nem logs de URLs OAuth. Sessão, CSRF e cookies seguros continuam na aplicação. A Central não recebe a chave privada do certificado.

Teste primeiro **Testar navegador e proxy (sem Meta)**, sem bypass. Esse teste exige a configuração OAuth já preparada, mas não chama a Meta. Antes de qualquer consentimento real futuro, revisar o novo callback na lista permitida do mesmo app Meta. Webhook, Meta, Direct e postagens não são ativados por esta atualização.

Evidência local: **201 testes Python PASS**, Chromium com nove cenários de probe, concorrência/config drift e worker ativo na origem antiga versus hostname separado na mesma porta; **build Docker linux/amd64 com 198 testes PASS**; **NGINX real local: nginx -t, TLS verificado, autenticação/CSRF, probe, 404 de rotas privadas, limites 413/429 e preservação de vhost representativo PASS**. Sem Meta/HA real. ARM64/Supervisor, certificado wildcard, instalação do arquivo e aceite externo permanecem pendentes do operador.

O proxy reduz a exposição direta e aplica controles; isso não torna o painel público livre de risco nem substitui revisão independente. Publicado não significa instalado ou homologado. Se foi criada regra 9443 exclusivamente para 0.1.17, desabilite essa regra; a atualização não altera o roteador.

## Histórico das correções anteriores

## Correção 0.1.16 — leitura de todos os cabeçalhos Cookie

- Após o teste real da 0.1.15, chegaram logs com cabeçalho Cookie presente, mas nenhum cookie OAuth no trecho lido. Localmente foi comprovado que `HTTPMessage.get('Cookie')` retorna somente o primeiro campo; se um intermediário encaminha o cookie esperado em um segundo campo, a aplicação o ignora.
- A 0.1.16 reúne todos os campos Cookie em ordem antes de sessão/CSRF/OAuth/probe. Não descarta pares nem escolhe um dos duplicados: dois cookies com o nome de state esperado continuam sendo rejeitados.
- A tela de falha também mostra se algum cookie de estado chegou e se havia vários campos Cookie. O log registra a contagem limitada de campos recebidos, nunca seus nomes/valores.
- Evidência: **189 testes Python PASS** e **Chromium PASS** em nove cenários, incluindo proxy que fragmenta Cookie, mais abas concorrentes/config drift. Antes da correção, cookie esperado no segundo campo retornou 400; reunido num campo ou no primeiro, 200. Após a correção, o segundo campo passa; duplicação continua 400.
- A reprodução comprova uma falha de leitura do servidor, **não comprova que o HA encaminhou cabeçalhos separados**. Se o teste real ainda falhar, a tela/log 0.1.16 permitirá verificar essa condição sem expor dados.
- Sem nova migração, alteração de credenciais, esquema, banco, atributos de cookie, opções ou proxy. Instalação/Meta continuam fora da execução do Codex.

## Mudanças 0.1.15

- Logs de emissão indicam somente modo/versão e atributos fixos; logs de retorno usam flags e contagem limitada, nunca nomes/valores de cookies.
- Falhas de troca são classificadas como HTTP, TLS, DNS, timeout, rede ou JSON; status HTTP e códigos/subcódigos numéricos seguros podem aparecer no log, sem corpo, mensagem remota, URL ou cabeçalhos. A resposta pública permanece genérica.
- `meta_oauth_states.authorization_context` é uma coluna aditiva com fingerprint de campos públicos da configuração. Mudança de app/configuração/redirect/versão/conta entre start e callback é recusada antes da troca. Estados em voo emitidos antes desta atualização não são reutilizados; credenciais existentes não são alteradas.
- Mantém cookies individuais por tentativa, `Secure`, `HttpOnly`, `SameSite=Lax`, `Path=/oauth/meta/callback`, TTL e consumo único, contas/tokens isolados, mesma aplicação Meta, mesmo login, Mensagens e Editorial.
- Evidência local: **185 testes Python PASS**, **8 cenários Chromium de probe PASS**, duas abas com autorizações sintéticas independentes e rejeição de mudança de configuração antes do exchange. Rede de testes limitada a loopback/stubs; nenhuma chamada Meta ou operação HA real.
- Esteira rápida P0: teste do diff, inspeção de sintaxe/configuração/segredos, exportação auditada uma vez e publicação somente da pasta autorizada com `[skip ci]`. Sem Actions ou exigência genérica de build ARM64 externo. Build/instalação/homologação no HA são etapas distintas.

## Histórico anterior


## Candidata 0.1.14 — probe do mesmo cookie state usado pelo OAuth

- O teste anterior `probe=1` usava `ig_oauth_probe`, diferente do cookie `ig_oauth_state_<hash>` do fluxo real. O teste de transporte aprovado não cobria o cookie novo.
- A 0.1.14 passa a emitir um nonce sintético e um cookie com o mesmo nome derivado do state e o mesmo leitor de cookie usados pelo callback OAuth. A callback de probe valida o cookie sem criar state no SQLite nem chamar a Meta.
- `/health` informa a versão carregada; a página de probe também mostra a versão. Isso permite confirmar se o Supervisor está executando a versão publicada.
- Testes unitários e HTTP adicionados para validar nome e valor do cookie, cookie de outra tentativa, valor divergente e versão.
- Situação: código em branch privada; testes pendentes; sem merge/publicação/instalação. Nenhuma tentativa OAuth real necessária.

## Candidata 0.1.13 — isolamento do cookie de estado OAuth por tentativa

- Cada autorização usa um nome de cookie próprio, derivado do SHA-256 do `state`; o callback valida somente o cookie correspondente ao `state` recebido.
- Evita colisão/sobrescrita entre tentativas simultâneas no mesmo navegador. A evidência anterior confirma cookie presente e divergente, mas não prova que concorrência foi a causa original.
- Preserva `state` aleatório de 256 bits, expiração de 10 minutos, consumo único no SQLite e atributos `Secure`, `HttpOnly`, `SameSite=Lax` e `Path=/oauth/meta/callback`.
- Não altera NGINX, Ingress, rotas, banco, dados, credenciais, opções do HA, webhook, Direct ou publicação de posts/stories.
- Testes offline do módulo OAuth: 18/18 passaram em harness isolado com o arquivo `oauth_meta.py` e `test_oauth_meta.py` do SHA de origem. Isso não substitui o build do Supervisor nem a homologação no HA.
- Estado desta candidata: proposta em PR de distribuição; não instalada nem homologada. A única tentativa real anterior de OAuth foi consumida e não deve ser repetida sem autorização específica.

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
