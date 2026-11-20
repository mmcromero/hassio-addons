# Changelog — Pager Virtual (Add-on Home Assistant)

Todas as mudanças relevantes e marcos de versão deste complemento são registrados neste arquivo.
Padrão de versionamento: [SemVer](https://semver.org/).

---

## [0.1.20-rc.12] — 20/11/2026 — Avisaqui e alerta Google Wallet

- Nome apresentado na loja: **Fábrica de Softwares - Avisaqui**, sem modificar slug, pasta, ícones, logo ou dados.
- Integração da notificação individual Google Wallet `TEXT_AND_NOTIFY` no estado PRONTO, com atualização PATCH prévia e falha tolerada sem interromper o pedido.
- Inclusão do código e dos testes da fonte integral de desenvolvimento, mantendo ajustes de outros módulos do mesmo pacote; ensaios isolados V8 12/12 PASS, suíte oficial Node/Android real ainda sem confirmação.
- Publicação da candidata para instalação e teste autorizada pelo proprietário; publicação não comprova funcionamento ou instalação.


## [0.1.20-rc.11] — 19/11/2026 — UX Wallet e alto contraste

- Snapshot integral do desenvolvimento após RC10: Google Wallet em badge vetorial português (Brasil), layout aprovado centralizado e ajustes de alto contraste na vitrine do cliente.
- Mantidas correções anteriores de som, credenciais Wallet e fluxo do pedido.
- Publicação do pacote de teste no canal público Home Assistant; Google Wallet real e testes no Android seguem sem homologação concluída.
- Nenhuma modificação da main privada de código, outros add-ons ou dados do Raspberry.


## [0.1.20-rc.10] — 19/11/2026 — alerta sonoro persistente e diagnóstico Google Wallet

- Snapshot integral da branch desenvolvimento após RC9, sem seleção de arquivos.
- A preferência de alerta sonoro do cliente persiste entre atualizações e recargas, mantendo restrições do navegador para ativação efetiva do áudio por gesto.
- Google Wallet apresenta estado de credencial ausente sem mensagens duplicadas e mantém a rota de acompanhamento do pedido como prioridade.
- Teste de regressão de interface incluído. Teste no Android, integração Google Wallet real e homologação HA ainda pendentes.
- Distribuição pública RC para testes; `main` privada da fonte não alterada.


## [0.1.20-rc.9] — 19/11/2026 — Google Wallet no HA via app_config

- Pacote completo do HEAD de desenvolvimento, incluindo `config.yaml` com mapeamento `app_config` somente leitura para `/config`, leitura segura de `google-wallet-key.json`, fallback controlado e testes dirigidos.
- Sem segredos na distribuição. A configuração externa do Google Wallet e a homologação funcional no Android permanecem pendentes.
- Publicação de teste pela `main` pública do catálogo de add-ons; `main` privada de código preservada; sem GitHub Actions.


## [0.1.20-rc.8] — 18/11/2026 — preparacao pelo Factory Runner (pendente de publicacao)

- Pacote AVISAQUI-PACOTE-006 aberto em https://github.com/mmcromero/pager-virtual/issues/42.
- Snapshot integral de desenvolvimento incluindo atualizacoes de gerentes, telas, jogos e testes do codigo versionado.
- Versoes de package.json, package-lock.json e config.yaml alinhadas.
- RC privada e distribuicao exigem proveniencia por SHA, testes e verificacao de hashes.
- **Nao comprova teste Node, build ARM64 nem homologacao no Raspberry. Publicacao RC8 ainda pendente.**


## [0.1.20-rc.7] — 18/11/2026 — pacote completo com correção Google Wallet

- Fonte privada `desenvolvimento` congelada integralmente, incluindo mudanças posteriores à RC6, sem selecionar arquivos.
- Android: integração Google Wallet corrigida para credenciais por ambiente, caminho explícito ou volume persistente /data, resposta controlada da API e aviso visível se indisponível; testes focados adicionados.
- Preservadas alterações de telas, PWA e demais módulos presentes no SHA congelado; versão consistente em config, pacote e lock.
- A emissão real de passe depende de credencial externa válida, configurada de modo seguro; testes Google/Android e homologação no Raspberry não estão comprovados.
- Nenhum código-fonte não homologado promovido à main privada; distribuição de teste na main pública de add-ons conforme política atual.



## [0.1.20-rc.6] — 18/11/2026 — fechamento pela esteira oficial

- Fonte canônica: `desenvolvimento`; candidato privado preparado em `release-candidate`.
- Layout de login aprovado preservado integralmente: `src/public/login.html`, commit `2a525edce160562c2bf3ab31932897654776345c`, blob Git `70c68fde853f623884ca0df20a9ea1279a803870`.
- Inclusão das correções posteriores à RC5 externa em gerentes, confirmações ACK, tratamento de erros do login e histórico KDS, conforme código da branch de desenvolvimento.
- RC5 externa mantida apenas como histórico. A candidata RC6 deve ser derivada da fonte privada com manifesto `SOURCE_PROVENANCE.json` e hashes verificados.
- Nenhuma alteração do layout de login, nenhum trabalho novo exclusivo da Issue #17, nenhum ZIP Windows embutido no add-on WEB/HA.
- Publicação de código na branch pública de testes não equivale a instalação ou homologação no Raspberry.

## [0.1.20-rc.3] — 17/11/2026 — segurança do formulário de login

- Avisaqui: fallback nativo de formulário de login usa POST e não GET, mesmo sem JavaScript; regressão incluída.
- Mantida autenticação JSON por POST na mesma origem; sem alteração de credenciais, cookies, banco ou proxy.
- O alerta de reutilização de senha do Chrome não é considerado corrigido sem observação no navegador afetado após atualização.
- ZIP Windows permanece o único formato autorizado; nenhum executável foi criado ou exigido.
- Homologação Windows e HTTPS ativo será feita pelo proprietário após publicação do pacote; não registrar PASS fictício.

## [0.1.20-rc.2] — 17/11/2026 — publicação de teste autorizada (PR #30)

- Distribuição integral das correções de impressão, ACK e configuração HA do merge privado `9bc8802f6a734f143e3b11eb6ae54253b4bcaec3`.
- Versão avançada da rc.1 já pública para permitir ao Home Assistant detectar a atualização; runtime preservado byte a byte em relação ao merge.
- Pareamento segue OFF por padrão; ativação depende de origem/prefixo/prazos explícitos e operação separada. Nenhuma alteração do Raspberry ou banco real.
- Proprietário autorizou publicação excepcional dispensando gates pendentes; ARM64 deste lote, Windows físico e aceite Segurança não foram executados e não são PASS.

## [0.1.20-rc.1] — 17/11/2026 — RC003 EM PREPARAÇÃO, NÃO PUBLICADA

### PR30 — correção em preparação, sem publicação

- Tela de impressão alinhada à estrutura aprovada do PR71: cartões/métricas reais, ação de vincular, download Windows indisponível, histórico e credenciais antigas recolhidas. Confirmação de vínculo depende de ACK persistido, sem inventar online/fila.
- Opções HA carregadas pelo entrypoint Node real antes de SQLite; opt-in OFF padrão, política completa obrigatória, prefixo removido `/` normalizado. Wrapper sem dependência de bashio ausente na imagem.
- Validação ARM64 isolada vinculada ao SHA final; sem push, merge, Actions, instalação automática de QEMU ou reutilização de imagem antiga.


- Telas reais de autorização e computadores vinculados conectadas às APIs opt-in de laboratório; validação local do fluxo cliente Python → QR/referência → autorização gerencial → resgate → ACK → renomeação/revogação.
- Corrigida a resposta duplicada 403/401 causada pelo hook assíncrono de cabeçalhos; preservados headers, CSP específica, papéis e isolamento.
- Monitor Windows passa pelo leitor protegido de configuração existente: credencial pair-v1 incompleta/corrompida não pode ser ignorada em favor do legado; pair-v1 segue bloqueado no monitor até integração autorizada.
- Bancos e credenciais legados preservados; opt-in OFF por padrão, sem toggle de ativação no add-on. Não comprova Windows físico/DPAPI, impressão, proxy público ou build ARM64.

## [0.1.19-rc.1] — 17/11/2026 — PUBLICADA NO GITHUB (pacote AVISAQUI-PACOTE-002)

### Funcionalidades e experiência entregues na RC
- **Biblioteca opcional com 16 títulos:** Pong original e Jogo da Velha disponíveis; outros 14 jogos exibidos como **Em construção**. Jogos carregados sob demanda e encerrados quando o pedido deixa **Em preparo**, sem substituir o aviso de pedido pronto.
- **Jogo da Velha isolado** em iframe `sandbox="allow-scripts"` sem `allow-same-origin`, com CSP restritiva e comunicação controlada. O Pong legado mantém API/SSE próprios e requer os controles de segurança correspondentes.
- **Interfaces administrativas e do cliente:** ajustes mobile-first no Master Admin, identificação visual, navegação e compatibilidade dos fluxos do pedido/alerta; preservar autorização e contexto do restaurante.
- **Correções de jogos/Pong e SSE:** encerramento e fluxo de navegação revisados, inclusive retorno tardio e eventos de estado; a execução no navegador real Android/iOS permanece objeto de homologação.

### Evidências e limites
- **Aplicação:** 109/109 testes Node aprovados no SHA privado `80ff0c19cbdef877dffd54fa95b1e29787d6da79`. Alterações posteriores na fonte final são documentais, de exportação e política, conforme auditoria do Tech Lead; **não afirmar nova execução Node no HEAD final**.
- **Integridade da distribuição:** exportação e verificação de 85 arquivos com hashes SHA-256 e origem privada registrada; política de pacote verificada localmente e documentos/arquivos compartilhados preservados.
- **ARM64:** build de imagem e smoke de inicialização, API health, escrita SQLite sintética, reinício e persistência aprovados no Codespaces, conforme evidência registrada no PR #35; não equivale a execução de GitHub Actions ou teste no Home Assistant ativo.
- **Estado da publicação:** PR #22 privado integrado (`f3e93faa7cdd107d976d7f60c6250103b6e53a1a`), PR #35 da loja integrado (`5977b1b6522dbc7682e1ef8e672c14c52c9c4bd2`), por autorização do proprietário. A CI do catálogo foi corrigida em `d12135bd`; [run #44068193157](https://github.com/mmcromero/hassio-addons/actions/runs/44068193157) concluída com sucesso nos jobs executados. Builds ARM64 não rodaram nessa run; o smoke Codespaces anterior permanece a evidência técnica de build.
- **Limites:** não inclui implantação do pareamento Windows pair-v1, mudança de impressora/spooler ou alteração de dados reais. **A versão está publicada na `main` do GitHub, mas a instalação no Home Assistant Raspberry Pi e a homologação móvel/HTTPS/recuperação ainda não foram comprovadas.**

## [0.1.18-rc.1] — 15/11/2026 — integrada ao GitHub e instalada no Raspberry Pi (relato do proprietário)

- Recuperação da origem canônica privada: autenticação, administração, KDS, impressão experimental, Web Push, HTTPS e Pong solo/dupla.
- Pendência de impressão mantém HTTP 409 em retries; origem de login exige Host coerente.
- Migração SQLite com números ativos conflitantes interrompe com orientação explícita, sem exclusão de dados.
- Fastify 5.12.8, plugins compatíveis e runtime Node.js 22; lockfile para instalações reproduzíveis. Auditoria npm sem vulnerabilidades conhecidas no snapshot desta RC.
- Docker respeita arquitetura do build; ARM64 e AMD64 devem passar build e smoke isolados antes de aprovação.
- Rastreabilidade por commit privado e SHA-256; Pong desativado por padrão e agente Windows mantido em laboratório.
- Versão instalada 0.1.15 conforme proprietário; 0.1.16 não instalada/homologada. Nenhuma instalação ou publicação nesta missão.

## [0.1.17] — 15/11/2026 — botão WebUI direto na landing HTTPS

- Corrige o endereço montado pelo Home Assistant: `https://[HOST]:[PORT:8443]/avisaqui/landing.html`.
- A porta 8443 é a do proxy HTTPS já existente; não é mapeada para a porta 8090 do aplicativo. O Supervisor preserva esse valor quando não há mapeamento Docker correspondente.
- O botão abre diretamente a landing HTTPS, inclusive com sessão autenticada. Não depende de acessar HTTP :8090 nem executar redirecionamento no aplicativo.
- Regressão usa o getter original do Supervisor para reproduzir o endereço incorreto mostrado pelo proprietário e validar o endereço final correto.
- Somente manifesto, versão e testes/documentação; servidor, dados, dependências, impressão, proxy/DNS e portas expostas preservados.

## [0.1.16 — correção de catálogo e botão WebUI] — 15/11/2026

- Corrige `webui` para o formato `[HOST]`/`[PORT]` exigido pelo Supervisor. A URL absoluta anterior é rejeitada na validação do catálogo e pode impedir a oferta da atualização.
- O botão abre `/webui`, que redireciona para a landing usando `public_url` (HTTPS quando configurado), com fallback local e preservação de `/avisaqui/`.
- Acrescenta regressões de manifesto e abertura da WebUI, sem alterações de autenticação, SQLite, pedidos, impressão ou dependências.
- Correção da candidata 0.1.16 ainda não instalada/homologada pelo proprietário. Não inclui a RC de consolidação 0.1.17-rc.1 nem muda proxy/DNS/portas.

## [0.1.15 — candidata para testes] — correções do Pong após teste da 0.1.14
- A versão 0.1.14 já foi instalada e testada no Home Assistant pelo proprietário; o Pong apresentou erro "Not Found" na entrada da partida.
- Corrigida a construção de URL do Pong atrás do prefixo HTTPS /avisaqui/ e melhorado o tratamento de erro HTTP 404.
- Adicionado modo de um jogador contra o computador, preservando a opção de dois jogadores.
- Adicionados testes de rotas e prefixo público; resultados de CI e homologação real ainda precisam ser confirmados.
- A versão foi incrementada em config.yaml e package.json para permitir atualização distinta da 0.1.14.
- Sem migração de banco ou exclusão de pedidos; manter backup antes da atualização.

## [0.1.14 — instalada e testada no Home Assistant em 14/11/2026 (relato do proprietário)] — Pong experimental e correções HTTPS
- Incorporado o Pong experimental para dois celulares no mesmo pedido, via SSE e memória temporária (PR #29).
- Opção `pong_experimental` desativada por padrão; o jogo não altera o banco de dados.
- Corrigidos link Entrar da landing HTTPS e endpoint do formulário piloto sob `/avisaqui/` (correção do PR #30).
- Teste de regressão para URLs da landing com e sem o prefixo HTTPS.
- Homologação real do Pong e publicação no Home Assistant ainda pendentes.

## [0.1.13 — candidata, não publicada] — AVISAQUI-HTTPS-001
- Suporte planejado à publicação da aplicação em `/avisaqui/` pelo NGINX SSL Proxy existente.
- Corrigidos URLs de login, administração, KDS, painel de impressão, cliente, Web Push e manifest.
- Incorporado o painel opcional de diagnóstico do aparelho na página do cliente, originado do PR #18 (`mmcromero/pager-virtual`, merge `7a2612271d2342b29863cd82e5007a60e9da620f`). Apenas HTML/JS do cliente, sem alteração em pedidos ou banco.
- Validação de origem pública e cookies revista; preservado HTTP local.
- Modelo NGINX isolado em `docs/AVISAQUI-HTTPS-001-nginx.conf.example`, **não instalado**.
- Antes de ativar, configurar no add-on `public_url` para `https://romeirop.duckdns.org:8443/avisaqui/` e validar login externo, SSE, QR Code, Web Push e agente Windows.
- **Ainda não houve merge, publicação nem alteração no Home Assistant.** O suporte HTTPS só está preparado em branch de desenvolvimento.

## [0.1.12 — candidata, não publicada] — integração Windows → API → KDS (PR #16)

- Rotas de recepção de pedido com chave de agente por restaurante, revogação, idempotência e atualização SSE no KDS.
- Tela `impressao.html` de credenciais e últimos eventos; atalho no KDS para gerente/master.
- Testes de API e separação de restaurantes adicionados. Agente Windows continua no repositório fonte; não integrar ao contêiner ARM64.
- **Candidata 0.1.12:** manifestos da branch preparados; nenhum merge, publicação ou instalação no Home Assistant.
- Limites: OCR apenas número, captura legada por arquivo fixo, reimpressão não automática, duplicados pendentes de decisão visual. Não modifica impressão física nem o banco real.
- Evidência e plano de validação: `docs/AVISAQUI_PRINT_HA_001.md`.

## [0.1.11] — 14/11/2026 — interface administrativa Avisaqui

- Sincronizada a interface `src/public/admin.html` do PR #14 do repositório privado `mmcromero/pager-virtual`.
- Navegação administrativa para Master e gerente, diálogos de cadastro, estados de carregamento, validação acessível e feedback contextual.
- Corrigida a confirmação após fechar diálogos, preservada a seleção de restaurante durante atualização e incluído rótulo na redefinição de senha de terminal.
- Sem alterações previstas no banco, slug `pager_virtual`, porta 8095, rotas de API ou dados persistidos em `/data`.
- **Estado:** versão preparada em branch; CI, publicação e homologação no Home Assistant dependem de evidência.

## [0.1.10] — 14/11/2026 — entrada pela landing page

- Corrigido o botão **Abrir página web** do Home Assistant para acessar `/`, em vez de `/kds.html`.
- Visitantes sem sessão válida são direcionados à landing `/landing.html`; usuários autenticados continuam com o direcionamento por perfil.
- Sem alterações no banco de dados, slug, porta ou rotas de autenticação.


## [0.1.8] — 14/11/2026 — cadastro rápido e WhatsApp manual

- Cadastro manual com nome e WhatsApp opcionais.
- Numeração automática persistente, com próximo número configurável pelo gerente quando não houver pedidos ativos.
- Proteção SQLite contra número duplicado ativo no restaurante e transição de pedido entregue de volta para ativo.
- Compartilhamento manual de acompanhamento e aviso de retirada pelo WhatsApp; o funcionário confirma o envio.
- Dados opcionais de nome e telefone são apagados ao marcar pedido entregue.
- Testes de duplicidade, sequência, concorrência, migração aditiva e restauração.
- Instalação e atualização do add-on exigem backup e validação no Home Assistant real.

## [0.1.7] — 14/11/2026 — acesso contextual do Master Admin

- Botão **Entrar no restaurante** em cada estabelecimento ativo no painel do Master Admin.
- KDS usa a própria sessão Master com restaurante selecionado, permitindo consultar, criar, chamar e finalizar pedidos sem usuário adicional.
- **Voltar à administração** encerra o contexto. A seleção afeta apenas a sessão atual, não altera gerentes ou outros restaurantes.
- Registro de entrada e saída em `master_contexto_eventos`; seleção corrente em `master_contextos`.
- Teste integrado com dois restaurantes valida seleção, pedido manual, status, isolamento, bloqueio sem contexto e retorno ao painel.

---

## [0.1.6] — 14/11/2026 — notificações Web Push e orientação ao cliente

- Notificação do sistema para pedido pronto via Web Push, associada ao token e autorizada pelo cliente.
- Service worker, manifesto de aplicativo web, chave VAPID gerada e persistida no armazenamento do complemento.
- Orientação inicial contextual: Android/navegador compatível pode ativar notificações; sem suporte, iPhone fora do app de Tela de Início ou permissão bloqueada recebe aviso para manter a página aberta.
- Mantido o SSE e o alarme da página em primeiro plano. Removida a estratégia de áudio silencioso, que não garante execução em segundo plano.
- Registro de assinaturas e teste automatizado sem enviar mensagens de teste a serviços externos.
- **Limite:** a entrega e o som das notificações dependem da permissão, do HTTPS, do aparelho e das configurações do sistema. A publicação no GitHub não instala o add-on no Raspberry Pi.

---

## [0.1.5] — 14/11/2026 — KDS e autenticação de restaurantes
- Teste HTTP integrado de revogação de KDS aprovado: operador desativado perde a conexão SSE antes do próximo pedido; KDS do gerente continua recebendo notificações. Sem homologação no proxy externo real.
- Segurança SSE do KDS: a sessão é revalidada antes de cada evento; terminal desativado deixa de receber imediatamente o próximo aviso, mesmo antes do heartbeat de 25 segundos. Teste de isolamento e revogação aprovado na CI.
- Corrigido o ciclo de vida das conexões SSE para assumir explicitamente a resposta no Fastify e limpar heartbeat ao desconectar. Teste HTTP real aprovado: KDS recebe pedido novo e KDS/cliente recebem transição para pronto. CI aprovada; sem teste ainda no proxy do Raspberry Pi.

- Adicionada verificação de execução da imagem ARM64: inicialização HTTP, escrita SQLite em `/data`, reinício do contêiner e recuperação dos mesmos registros. Etapa `Smoke da imagem ARM64 com volume persistente e reinício` concluída com sucesso no job `build-pager-arm64` (execução 43590737190).

- Teste automatizado de segurança de dados aprovado: backup SQLite pela API nativa com conexão WAL aberta, verificação de integridade, restauração isolada, migração aditiva, preservação de 120 pedidos e simulação de retorno ao backup anterior. **Banco real do Home Assistant não testado.**

- Após a migração, gerente de restaurante preservado consegue entrar e consultar os pedidos antigos ainda ativos; pedido entregue permanece armazenado sem reaparecer no KDS. Teste integrado aprovado.
- Migração aditiva do SQLite 0.1.3 validada em CI: preservados integralmente restaurante, pedidos (em preparo/pronto/entregue), números, tokens, datas e status; novas tabelas de usuários e sessões criadas sem credenciais padrão. Sem execução sobre o banco real do Raspberry Pi.

- Teste de configuração `PUBLIC_URL=https://...` aprovado: login HTTP local sem `Secure`, login pela origem HTTPS declarada com cookie `Secure`, e rejeição de origem externa. Teste automatizado, sem validação do proxy real.

- Teste integrado com servidor real aprovado no GitHub Actions: dois restaurantes, Master Admin, gerentes, terminais, criação e alteração de pedidos, bloqueio cruzado e revogação de sessão. Sem homologação no Home Assistant.

- Teste automatizado de primeiro acesso concluído no add-on: cadastro único, bloqueio de domínio público, login e autorização do painel. **Homologação no Raspberry Pi/HTTPS real ainda pendente.**

- A próxima versão reunirá a correção 0.1.4 do KDS e a autenticação por Master Admin, gerente e terminal operacional.
- O primeiro acesso planejado usa um código temporário nos logs privados do Home Assistant para criar o Master Admin, sem senha padrão.
- Segurança adicional do primeiro acesso: verificação de origem, hostname local e IP privado para impedir que um proxy público seja confundido com acesso local.
- Smoke de primeiro acesso incluído no add-on: inicia o servidor, testa código temporário, bloqueia origem externa e segundo cadastro, valida login e acesso ao painel. Teste automatizado aprovado na esteira do PR #19; teste no Raspberry Pi e no proxy real continua pendente.
- O backend em desenvolvimento já contém sessões revogáveis e isolamento de pedidos/SSE por restaurante; a homologação final ainda está pendente.
- O gerente poderá administrar terminais e redefinir suas senhas; a troca da própria senha revoga sessões anteriores.
- Código e testes da branch `feat/auth-restaurantes-fundacao` foram sincronizados para `feat/pager-auth-staging` neste repositório. **Não estão integrados à main nem distribuídos no Home Assistant.**
- Pendências: testes integrados, fluxo de primeiro acesso no HA, validação HTTPS/proxy, verificação da sincronização final, compilação ARM64, homologação e atualização final de versão.

---

## [0.1.4] — 14/11/2026

### Corrigido
- **KDS sem pedidos ao abrir ou atualizar:** removida a referência ao contador de simulação `orderCounter` do carregamento inicial. A variável inexistente interrompia a renderização mesmo após a API devolver os pedidos salvos no SQLite.
- A criação de outro pedido fazia a lista reaparecer porque o evento SSE executava novamente a renderização.
- Acrescentado teste de regressão no repositório principal para impedir a volta do contador antigo.

### Preservação e validação
- Não apaga pedidos, tokens, banco SQLite nem configurações da instalação anterior.
- O teste visual no Home Assistant após atualização ainda precisa confirmar a correção no aparelho real.

---

## [0.1.3] — 14/11/2026

### Adicionado
- Cadastro manual de pedidos no KDS pelo número da senha, com criação real no SQLite.
- QR Code por pedido com token exclusivo e opção de impressão e reimpressão pelo navegador.
- Campo `public_url` nas configurações do add-on para gerar links de clientes com endereço configurado, aplicável ao reiniciar.

### Alterado
- Eliminados o botão de simulação e os dados fictícios da operação normal.
- Página de acompanhamento adaptada a pedidos sem lista de produtos.

### Limitações atuais
- O KDS ainda não possui login e isolamento por restaurante; não expor as rotas operacionais na internet.
- O endereço público configurado não substitui a configuração de proxy/DNS/HTTPS e exige testes de acesso no celular.

---

## [0.1.2] — 14/11/2026

### Adicionado
- Melhorias de alerta ao cliente: Screen Wake Lock, gerador de áudio de fundo, timbre de alarme e vibração aprimorada.
- A eficácia com o celular bloqueado depende do navegador e deve ser homologada em dispositivos reais.

---

## [0.1.1] — 14/11/2026

### Corrigido
- **Eliminação do conflito `s6-overlay-suexec: fatal: can only run as pid 1`:**
  - Ajustado `init: false` no `config.yaml` seguindo a arquitetura de produção homologada do Artesão Digital.
  - O container agora executa `node src/server.js` diretamente como PID 1 nativo, sem camadas intermediárias.
- **Simplificação e remoção de duplicidade de portas:**
  - Removido o campo redundante `port` da seção `options` no `config.yaml`.
  - O mapeamento de porta agora é gerenciado exclusivamente pela seção nativa `ports` ("Rede") do Home Assistant OS, permitindo ao usuário definir portas customizadas (ex: `8090`, `8095`, `8096`) sem conflitos internos.
- **Dockerfile otimizado:**
  - Imagem base migrada para `node:20-alpine` (ARM64) com build direto e limpo.

---

## [0.1.0] — 14/11/2026

### Adicionado
- **Lançamento inicial do complemento Pager Virtual para Home Assistant OS:**
  - Backend ultraleve em Node.js com Fastify (< 40 MB de RAM).
  - Persistência em banco de dados SQLite com modo WAL ativo, armazenando dados na partição persistente `/data`.
  - Gerenciador de eventos em tempo real via **Server-Sent Events (SSE)** nativo (`/api/pedidos/stream/:token` e `/api/kds/stream`).
  - Frontend integrado servido pelo próprio add-on:
    - `kds.html`: Painel de Cozinha/Balcão multi-pedidos com fila cronológica rigorosa FIFO e botões de chamada/finalização.
    - `cliente.html`: Arquitetura "Página Casca" (< 50 KB) com leitura de dados estáticos diretamente dos parâmetros da URL/QR Code e alertas multissensoriais (Web Audio API, vibração ritmada e Edge Lighting amarelo neon).
  - Manifesto `config.yaml`, script `run.sh` e `Dockerfile` com compilação de dependências nativas C++ para arquitetura `aarch64` (Raspberry Pi 4) e `amd64`.
