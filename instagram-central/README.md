# Central Instagram Umdoislab — 0.1.17 (acesso HTTPS independente)

**Estado:** pacote para teste autorizado no Home Assistant, sem homologação declarada. O proprietário autorizou correção e publicação pela esteira rápida em 21/11/2026. A instalação/atualização será feita pelo operador no Supervisor, preservando opções e `/data`. A autorização não ativa Meta, webhook ou envio.

A 0.1.17 acrescenta HTTPS próprio em outra porta para tirar painel e OAuth da origem controlada pelo service worker do HA. O A/B/A do proprietário na 0.1.16 sustenta essa interferência; não identifica um defeito específico do Ingress. A nova configuração reutiliza login, senha, dados e o certificado existente, mantendo o Ingress como alternativa. A porta externa e o teste real ainda precisam ser conferidos pelo operador.

- Repositório privado de origem: `mmcromero/instagram-automacoes`.
- Fonte desta versão: branch privada `fix/instagram-oauth-safe-diagnostics-001`, baseada no PR #9 (`723b423069c18a19c1053aecaf3bcef399b0efbb`) e sincronizada com o diagnóstico público 0.1.14. SHAs de fonte e publicação são registrados na Issue #1.
- Base imutável de código: PR #7, commit `f6ad64bc55bb3d8299c1e3cd71d40f5e63897082`, árvore original `instagram-central/` = `cf92e4dc5da1f75db389024499e8b7d951a6a24c`.
- Controle e evidências: [Issue #1](https://github.com/mmcromero/instagram-automacoes/issues/1), [PR #7](https://github.com/mmcromero/instagram-automacoes/pull/7), [relatório do gate](https://github.com/mmcromero/instagram-automacoes/blob/d4a885460635d5930b8c8a1e4875e94918816dae/docs/evidence/IG-PR7-GATE-001-20261120/RELATORIO.md).
- Identidade de distribuição preservada: nome **Fábrica de Softwares - Central Instagram**, slug `umdoislab_instagram`, arquitetura declarada `aarch64`, Ingress `true` com porta interna `8099`, `backup: cold` e marca oficial. O catálogo público já contém `icon.png` e `logo.png` oficiais. **Não copiar nem recriar imagens na publicação**: manter os blobs existentes na pasta pública do Instagram.


## Acesso independente HTTPS — 0.1.17

O teste A/B/A do proprietário na 0.1.16 passou com **Ignorar da rede** e voltou a falhar sem essa opção. O controlador observado foi `sw-modern.js` na raiz da origem do HA. Abrir outra aba na mesma origem não isola esse controlador. A nova porta HTTPS cria outra origem para painel, início e retorno OAuth; não altera o service worker nem o NGINX do HA.

O aplicativo mantém o Ingress como alternativa, mas acrescenta links **Abrir Central em janela própria** no login e no painel. O manifesto também declara `webui` HTTPS e mapeia somente `9443/tcp`; a porta HTTP interna `8099` não é publicada. Dependendo da interface do HA, o botão do Supervisor ainda pode preferir o Ingress: use o link da Central ou a URL pública diretamente.

### Configuração pelo operador, após atualizar para 0.1.17

1. Preserve todas as opções existentes, a senha e `/data`. Acrescente/ajuste somente:
   ```yaml
   public_base_url: "https://romeropi.duckdns.org:9443"
   certfile: "fullchain.pem"
   keyfile: "privkey.pem"
   meta_oauth_redirect_uri: "https://romeropi.duckdns.org:9443/oauth/meta/callback"
   ```
   Não altere flags Meta, webhook ou rascunhos para executar esta atualização. O probe continua exigindo a configuração OAuth já preparada; ele não chama a Meta.
2. Confirme a disponibilidade da porta 9443 no host. Em **Rede** do aplicativo, mantenha `9443/tcp` → `9443`. Para acesso pela internet, o roteador precisa encaminhar **TCP 9443 externo → IP do HA:9443**. Esse encaminhamento não foi executado nem verificado pelo Codex. Se usar outra porta externa, ajuste `public_base_url` e o callback de forma idêntica; o listener interno continua 9443.
3. O Supervisor monta `/ssl` somente para leitura. O certificado deve ser válido para `romeropi.duckdns.org`; a Central lê os mesmos nomes de certificado documentados no inventário do HA. Nunca envie nem copie a chave por chat/Git. Não é necessário alterar o proxy, certificado, fragmentos ou porta 8443 dos outros aplicativos.
4. Salve/reinicie a Central pelo Supervisor. O log esperado é `Standalone HTTPS ready: port=9443 version=0.1.17`. Com URL vazia, o listener fica desligado. Sem senha adequada, certificado/chave válidos ou porta disponível, não abre HTTP no lugar de HTTPS; o Ingress interno é mantido e o log informa indisponibilidade. Certificados renovados são relidos nas novas conexões.
5. Abra **https://romeropi.duckdns.org:9443/panel** fora do HA. Use o mesmo usuário `admin` e a mesma senha da Central. O Chrome pode exigir login novamente; não se cria outra conta nem outro banco. Não use bypass de service worker nem ignore avisos de certificado neste teste real.
6. Execute **Testar navegador e proxy (sem Meta)**. O retorno deve permanecer em `:9443` e mostrar versão 0.1.17 e teste aprovado. Compartilhe somente a tela e as linhas de diagnóstico seguro, sem URL de retorno/cookie/state/código.
7. Antes de qualquer consentimento real futuro, o operador deverá cadastrar o **novo callback exato** na lista de redirecionamentos permitidos do mesmo app Meta. Isso não foi executado nesta entrega. Não tente consentimento até o probe passar e a configuração ser revisada. O webhook atual em 8443 permanece separado e não foi alterado.

Se o callback ainda apontar para a origem antiga, a Central esconde os links OAuth e recusa start/callback antes de criar/consumir state ou trocar código. URLs antigas em 8443 também são recusadas quando o modo independente está configurado. Nada é redirecionado silenciosamente de volta ao HA.

Esta versão não migra nem apaga dados, sessões, mídia ou tokens. Os dois acessos usam o mesmo servidor, login e armazenamento. **Origens isolam service workers; cookies do mesmo hostname não são isolados por porta.** A mudança não promete isolamento de cookies entre aplicativos no mesmo domínio. Para isso seria necessário hostname dedicado.

### Porta 9443 no roteador: passo a passo

1. No HA, abra **Configurações → Sistema → Rede** e anote o endereço IPv4 local da máquina do HA. Não use o endereço Docker do aplicativo. Confira também a porta 9443 na seção **Rede** da Central após a atualização.
2. Abra o painel do seu roteador e procure **Encaminhamento de portas**, **Port Forwarding**, **NAT** ou **Servidor virtual**. Confira se já há regra para TCP 9443. Os nomes variam conforme o modelo; não apague nem substitua a regra atual da 8443.
3. Se 9443 estiver livre, cadastre uma regra: nome **Central Instagram**, protocolo **TCP**, porta externa **9443**, IP de destino **IPv4 local do HA**, porta interna **9443**. Salve. Não crie encaminhamento da 8099.
4. Se a 9443 já estiver reservada, não substitua o serviço existente. Pode usar, por exemplo, externa **9444 → HA:9443**, mas então configure `public_base_url` com `:9444` e o callback com o mesmo `:9444`. Use a URL pública explícita para abrir a Central.
5. Depois de configurar/reiniciar a Central, teste `https://romeropi.duckdns.org:9443/health` e depois `/panel`, sem trocar o domínio por IP. A resposta de health deve indicar 0.1.17. Se o roteador não permitir acesso ao próprio IP público por dentro da rede, teste primeiro no celular com Wi-Fi desligado; isso diferencia alcance externo de NAT loopback.
6. Se o log não mostrar HTTPS pronto, confira a configuração/certificados/porta no Supervisor antes de mexer no roteador. Se o HTTPS estiver pronto mas a URL externa não responder, confira a regra, IP local e eventual bloqueio de entrada. Não desabilite a verificação do certificado nem altere o NGINX/8443 como tentativa genérica.

Publicação, instalação, acesso externo e homologação são etapas distintas. O pacote foi preparado para teste do operador; não declara a infraestrutura externa pronta nem OAuth real aprovado.

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
