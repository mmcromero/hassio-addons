# 0.1.0-rc.60 — M103: comprovar CPU e overflow do canal stdout

- Adiciona ensaio sintético de RLIMIT_CPU em processo filho descartável, com limite soft=1 s/hard=2 s, deadline externo de 4 s e limpeza em caso de timeout.
- Mantém RC59 bounded-stream probe e acrescenta execução real do cenário `overflow 128` no startup: o processo confiável deve ler exatamente 129 bytes, encerrar o filho e registrar `blocked_output_limit`.
- O cenário seguro continua executado separadamente e deve registrar `status=pass`; no cenário seguro `output_limit_enforced=false` é esperado.
- Resultado real RC60 no Supervisor ARM64: build e suíte Dockerfile concluídos; `rlimit_cpu_primitive_enforced=true`, status `ok`, 1 s; overflow live `status=blocked_output_limit`, 129 bytes, filho encerrado por SIGKILL e tmpfs restaurado.
- Nenhum código de projeto é executado; nenhuma capability, AppArmor, mount, opção do Supervisor, rede, Docker ou credencial é alterada.
- Isso prova primitivas sintéticas por processo/canal, não orçamento agregado de job nem sandbox homologado. `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.

# 0.1.0-rc.59 — M102: prova de saída limitada sem filesystem gravável

- Adiciona bounded_stream_probe: payload sintético em chroot read-only, sem diretório gravável, com FDs auditados e stdout conectado a pipe.
- Seccomp em modo stream nega abertura de arquivos com flags de escrita, syscalls de mutação, criação de processos e sockets; o payload escreve apenas no pipe de saída.
- Processo confiável lê o pipe com limite de bytes e mata o filho ao exceder o teto; teste de overflow confirma corte em max_output_bytes+1.
- Protótipo não executa código de projeto; sandbox_export continua fail-closed.
- Supervisor atual só aceita tmpfs boolean e monta /tmp e /dev/shm sem opção de tamanho; não há quota dedicada configurável por add-on sem alterar Supervisor ou elevar privilégios.

# 0.1.0-rc.58 — M101: rootfs de job em tmpfs limitado

- A fixture de isolamento passa a ser criada dentro de /dev/shm, que o probe identificou como tmpfs com teto rígido de capacidade no contêiner.
- O rootfs sintético fica root-owned e read-only; /workspace e /tmp são privados e pertencem ao UID executor; /readonly é root-owned 0555.
- Após o drop de UID/GID, o probe comprova escrita permitida somente em /workspace e negação em /readonly e na raiz do rootfs.
- Relatório separa hard container tmpfs ceiling de per-job quota: o primeiro pode ser demonstrado; quota dedicada por job continua false.
- Validação Supervisor ARM64: build Dockerfile concluído; RC58 instalada/started; fd_audit.status=ok; rootfs owner UID 0/mode 0555; /workspace UID 104/mode 0700 gravável; /readonly e / negam escrita; /proc e /data/options.json ausentes no chroot.
- /dev/shm tmpfs: teto rígido do contêiner 4091707392 bytes; per_job_quota_proven=false. /data ext4 sem opções de quota identificadas.
- Nenhum código de projeto executado; sandbox_export continua fail-closed; safe_for_untrusted_code=false; Publisher DORMANT.

# 0.1.0-rc.57 — M100: validar metadados do rootfs antes do chroot

- O UID root registra owner UID e modo de /workspace na fixture sintética antes do chroot/drop de UID, sem depender de stat dentro do ambiente seccomp restrito.
- Após drop de UID/GID, continua a tentativa real de escrita em /workspace; o resultado deve ser denied.
- RC56 build ARM64 concluído e instalado/started; suíte do Dockerfile passou. Probe real: fd_audit.status=ok, sem descritores inesperados. A leitura de metadados de /workspace pós-drop retornou PermissionError; a tentativa de escrita ficou não testada. RC57 move somente a leitura de metadados para antes do chroot.
- Inventário real /data: ext4, 471816998912 bytes total, 360597803008 disponíveis; nenhuma opção de quota reconhecida; hard_quota_proven=false.
- Nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

# 0.1.0-rc.56 — M099: snapshot de FDs somente com descritores vivos

- Corrige o snapshot: após enumerar /proc/self/fd, valida cada número com fstat e descarta EBADF, removendo o FD transitório já fechado pela própria listagem.
- Mantém fechamento de todos os FDs não autorizados e preserva somente pipe de relatório e scratch FD.
- Nova regressão verifica que o snapshot retorna exclusivamente descritores que permanecem abertos; teste de auditoria imprime contagens em caso de falha.
- RC54 e RC55 falharam no teste de auditoria FD por falsos positivos de descritores transitórios; o teste de rootfs passou. RC53 segue instalada/started.
- Nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

# 0.1.0-rc.55 — M098: corrigir snapshot de descritores /proc/self/fd

- Corrige auditoria FD: a enumeração usa um descritor explícito para /proc/self/fd e exclui esse próprio descritor temporário da fotografia, evitando falso positivo.
- Mantém somente pipe de relatório e scratch FD autorizados; fecha todos os demais descritores antes do chroot.
- Regressão agora inclui o relatório completo de contagens/status em caso de falha.
- RC54 build ARM64 executou a suíte integral até encontrar uma única falha: test_fd_audit_closes_unapproved_descriptors_in_child (status='failed', esperado 'ok'). O teste de rootfs passou; os demais testes registrados passaram ou foram skips esperados.
- Nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

# 0.1.0-rc.54 — M097: auditoria de rootfs, FDs e sinais de quota

- Fixture de rootfs separa scratch gravável da área de trabalho root-owned 0555.
- Filho executor tenta escrita sintética na área de trabalho após drop de UID/GID.
- Auditoria de FDs fecha descritores herdados não autorizados e mantém apenas pipe de relatório e scratch FD explicitamente permitido; destinos não são registrados.
- Inventário passivo de mountinfo/statvfs inclui /data e sinaliza opções de quota sem declarar enforcement.
- Testes sintéticos novos para imutabilidade da área, fechamento de descritores e negação de escrita.
- Nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

# 0.1.0-rc.53 — M096: leitura dos limites cgroup herdados

- Probe read-only percorre a hierarquia cgroup v2 visível e calcula os menores limites finitos herdados de CPU, memória e PIDs.
- Não cria, escreve ou move processos entre cgroups; mount read-only continua sem delegação e não é tratado como sandbox.
- Testes sintéticos cobrem limites finitos em ancestrais, hierarquia ilimitada, metadados inválidos e ausência de controles.
- O diagnóstico não altera `safe_for_untrusted_code=false`; quota de armazenamento, rootfs/FDs e equivalência do backend continuam pendentes.

# 0.1.0-rc.52 — M095: build ARM64 e probe real parcial

- Build ARM64 concluído em 193,826 s; instalação RC52 `started`; backup pré-update RC51 `52be48a6`.
- Dockerfile validation chain passou; contagem individual de testes não capturada.
- Probe confirma CapEff zero, chroot, UID/GID drop, no_new_privs, seccomp/herança e RLIMIT_NPROC/AS/FSIZE.
- /proc, /data/options.json e sentinel externo retornam `permission_denied`, não `absent`.
- Sem quota agregada rígida de CPU/memória/armazenamento; `safe_for_untrusted_code=false`; Publisher DORMANT; nenhum código de projeto executado.

# 0.1.0-rc.52 — Etapa 5B: acesso explícito, capget e RLIMIT_FSIZE por FD (M094)

- O probe diferencia absent, permission_denied, readable e outros erros para /proc, PID 1, /data/options.json e sentinel externo; não registra conteúdo.
- Verifica CapEff após drop via capget, sem depender de /proc.
- Testa RLIMIT_FSIZE com descritor scratch pré-aberto antes do chroot, limitando o teste a 1.024 bytes.
- Mantém execução exclusivamente sintética e SAFE_FOR_UNTRUSTED_CODE=false; build/diagnóstico ARM64 pendentes.

## M093 — homologação real parcial RC51 (25/11/2026)

- Build ARM64 e instalação RC51 concluídos; bootstrap e API/E2E read-only PASS.
- Probe real confirmou primitives parciais; isolamento não homologado. Ver `docs/CONTINUIDADE-ATIVA.md` M093 para evidências e próximos testes.

# 0.1.0-rc.51 — Etapa 5B: diagnóstico completo da corrida de criação M092

- Unifica a verificação de metadados para diretórios persistentes preexistentes e para a janela de concorrência `mkdir`/`FileExistsError`.
- Se a criação concorrente encontrar tipo, UID, GID ou modo divergente, informa somente o nome relativo e os metadados esperados/encontrados; nunca repara, faz chown/chmod ou imprime caminhos absolutos/conteúdo.
- Adiciona regressão sintética que força a corrida e verifica diagnóstico exato e preservação do modo divergente.
- RC50 está instalada no Supervisor, mas o app permanece ERROR; os logs disponíveis ainda mostram a mensagem genérica, sem identificar o diretório. RC51 visa fechar essa lacuna de diagnóstico.
- Probe de isolamento permanece não homologado; Publisher DORMANT; nenhum código de projeto executado.

# 0.1.0-rc.50 — Etapa 5B: diagnóstico exato do bootstrap (M091)

- Bootstrap continua fail-closed, sem reparar diretórios persistentes; erro agora identifica somente o nome relativo e os metadados divergentes (tipo, UID, GID e modo), sem conteúdo/segredos/caminhos absolutos.
- Adiciona regressão para assegurar diagnóstico de modo e preservar o diretório sem alteração.
- RC49 build ARM64 PASS, mas o bootstrap ainda bloqueou `unsafe_existing_service_directory`; a hipótese de deslocamento de UID/GID não foi confirmada. RC50 permitirá identificar a divergência real antes de qualquer correção.
- Nenhuma execução de projeto; Publisher DORMANT e `SAFE_FOR_UNTRUSTED_CODE=false`. Build e homologação ARM64 pendentes.

# 0.1.0-rc.49 — Etapa 5B: preserva identidades e corrige prova chroot (M090)

- Move a criação do usuário/grupo executor para depois das contas/grupos persistentes já existentes, preservando UID/GID de approval, publisher, owner_ui e grupos IPC no volume do HA.
- Executa o diagnóstico sintético somente depois de o bootstrap validar os diretórios persistentes; falha de bootstrap não dispara sondas repetidas no watchdog.
- Corrige o rootfs efêmero: /tmp passa a 01777 e o sentinel externo 0644, evitando falsos positivos por permissão.
- Distingue ENOENT/ENOTDIR de EACCES, verifica CapEff após drop, e registra estágio/errno por primitive. Falhas RLIMIT são independentes e não impedem a tentativa seccomp.
- Continua diagnóstico-only; SAFE_FOR_UNTRUSTED_CODE permanece false, Publisher DORMANT e nenhum código de projeto é executado.
- RC48 build ARM64 PASS, mas startup bloqueou no bootstrap por divergência de diretório de serviço; a sonda também não comprovou seccomp/RLIMIT. RC49 aguarda build e homologação real.

# 0.1.0-rc.48 — Etapa 5B: corrige sintaxe e preload libseccomp (M089)

- Corrige literal de quebra de linha que causou a falha de py_compile da RC47.
- Importa o módulo confiável e carrega libseccomp antes do chroot vazio; o filho herda a biblioteca mapeada e aplica o filtro sem depender de /app ou /lib dentro da raiz.
- Mantém o protótipo fora do executor de produção; nenhum código de projeto é executado.
- RC47 publicada, mas não instalada: build falhou em py_compile na etapa final de validação. RC46 continua ativa.

# 0.1.0-rc.47 — Etapa 5B: diagnóstico chroot/seccomp/RLIMIT (M088)

- Adiciona UID executor sem shell/home/login, ainda sem uso por serviços.
- Inclui libseccomp e política deny de rede, IPC, introspecção e operações de escape; usada somente no processo filho sintético do probe.
- Probe root efêmero mede CAP_SYS_CHROOT/KILL, chroot seguido de drop de UID, no_new_privs, seccomp e RLIMITs; inventaria /tmp e /dev/shm.
- Não integra nem habilita execução de projetos; Publisher permanece DORMANT. Build e diagnóstico ARM64 pendentes.

# 0.1.0-rc.46 — Etapa 5A: gate de isolamento agregado e diagnóstico cgroup (M086)

- Bloqueia execução de exportador mesmo se o smoke test Bubblewrap passar, até homologação de isolamento agregado.
- Consulta cgroup v2 no processo não-root, sem alterar controles, host ou credenciais.
- Adiciona regressões sintéticas. Build e prova operacional pendentes. Publisher DORMANT.

# 0.1.0-rc.45 — integração do Publisher e revogação (M084)

- Conecta a revogação de grants ao Approval IPC e à interface do proprietário no HA Ingress.
- A revogação exige sessão HA verificada, CSRF de uso único, Origin validada, senha do proprietário e confirmação `REVOGAR`.
- A autoridade rejeita nonce inválido, grant inexistente, revogação duplicada e revogação após reserva; eventos ficam associados à proposta.
- Acrescenta regressões de interface/Ingress, IPC/ACL, estado do grant, revogação/reserva e roteamento HTTP Runner→Publisher.
- **Validação pendente:** testes novos ainda não executados; Publisher permanece DORMANT/desativado; sem publicação ou execução de código de projetos.
# 0.1.0-rc.44 — corrige sintaxe e falha fechada do worker

- Corrige o bloco try externo de `_worker_loop`, que estava sem except/finally e impedia o build ARM64 durante `py_compile`.
- Falhas ao reivindicar o próximo job agora interrompem o worker em estado fail-closed.
- Adiciona regressão para confirmar a parada segura quando o claim da fila falha.
- Supervisor/Home Assistant ARM64: build RC44 PASS; etapa Dockerfile concluiu `bash -n`, `py_compile`, suíte `test_factory_runner_*.py`, testes não-root de workspace sync e E2E probe. App RC44 instalada e `started`.
- Probe autenticado real da API de jobs PASS para Avisaqui e Artesão: POST/idempotência, polling até estado terminal, GET do job/plano, digest do recibo, filtros e auditoria. Jobs PARCIAL conforme esperado (68 e 54 testes selecionados, nenhum executado; `tests_execution_performed=false`; `authorization_verified=false`). Publisher DORMANT; nenhum código de projeto executado.

# 0.1.0-rc.43 — correção de estado visível após retry

- Ao aceitar retry de um job impedido, limpa o resultado anterior e reinicia as etapas com somente a validação do contrato; não exibe PASSs da tentativa anterior como progresso atual.
- Regressão cobre o reset de steps/result.
- Alteração ainda sem execução de testes/build; validação ARM64 depende de homologação autorizada no Supervisor.

# 0.1.0-rc.42 — Etapa 3: orquestração persistente (candidata publicada; build pendente)

- Adiciona fila persistente de trabalhos, worker único, estados explícitos, idempotência, timeout, retry limitado, cancelamento e recuperação após reinício.
- Endurece a persistência inicial com gravação atômica do pedido e limpeza de staging incompleto.
- Garante precedência do cancelamento diante de finalização, bloqueio ou reagendamento concorrente.
- Vincula o plano persistido ao contrato, projeto e SHA do trabalho; compara os digests e contagens do plano com a resposta do worker.
- Diferencia etapas de teste não executadas, evidência reutilizada e testes não requeridos.
- Adiciona regressões de persistência atômica, cancelamento concorrente, auditoria e integridade do plano.
- O worker executa somente o planejador FR-EXEC-001 read-only. Nenhum código/teste de Avisaqui ou Artesão é executado. Publisher permanece DORMANT.
- Publicação no catálogo confirmada; workflow de validação do catálogo PASS apenas em sintaxe/manifests/registro/scripts/arquivos sensíveis. Build-factory-runner-arm64 foi SKIPPED por exigir acionamento manual; testes Dockerfile, build ARM64 e probe real ainda NÃO executados. RC41 continua instalada até autorização específica para atualizar para RC42.

# 0.1.0-rc.41 — correção do delimitador JSONL

- Grava LF real após cada registro de evidência, em vez de uma sequência literal de escape.
- Nova regressão verifica os bytes e a leitura do registro.
- Sete testes dirigidos do ledger passaram em laboratório com blobs conferidos; validação ARM64 completa pendente.

# 0.1.0-rc.40 — diagnóstico do ledger e fixture de evidência

- Acrescenta diagnóstico não sensível do campo que invalida um registro de evidência, sem incluir valores no log.
- Corrige import explícito de os na fixture que define modo 0600 do ledger corrompido.
- Acrescenta teste isolado do schema interno do registro antes de testar append/reuso.
- RC39 executou 409 testes e terminou com 2 erros e 2 falhas; erros remanescentes estavam concentrados na validação do ledger e na fixture de permissões. RC40 aguarda novo build ARM64.

# 0.1.0-rc.39 — corrige regressões do ledger e do probe

- Permite versões numéricas de teste no binding de evidência, mantendo validação estrita do identificador.
- Corrige a fixture de ledger corrompido para usar o modo privado 0600 exigido pelo armazenamento.
- Ajusta a regressão do probe para a contagem real de três operações read-only por projeto (preflight, release-plan e execution-plan).
- RC38 build ARM64 executou 409 testes, mas terminou com 5 erros e 1 falha; RC39 incorpora as correções identificadas. Nova validação completa no Supervisor pendente.

# 0.1.0-rc.38 — FR-EXEC-001: contrato, impacto e plano de testes

- Adiciona contrato FR-EXEC-001/v1 com validação estrita, binding a perfil/repositório/ref/SHA, escopo, operações declaradas, autorização não verificada e limites.
- Persiste contratos e planos imutáveis no volume privado; mesmo execution_id + digest é idempotente; conflito de conteúdo é recusado; recuperação de gravação parcial é segura.
- Analisa diff Git sem checkout/hooks, mapeia módulos/dependências e seleciona testes proporcionalmente pelos catálogos confiáveis de Avisaqui (68 testes) e Artesão (54 testes).
- Reutiliza evidência somente com binding exato de teste/versão, digest da unidade/dependências, ambiente e artefato; ledger privado, serializado e idempotente. Nenhum endpoint aceita PASS externo.
- Emite recibo verificável com selecionados, reutilizados, omitidos, justificativas, bloqueios e digest.
- API autenticada: POST /api/execution-plan e GET /api/executions/{execution_id}. O probe de inicialização exercita o endpoint real para os workspaces existentes.
- Planejamento é somente leitura: não executa teste, script, comando ou código de projeto. Testes permanecem não executados até sandbox da Etapa 5. Publicação/deploy exigem grants independentes; Publisher permanece DORMANT.
- Build ARM64, suíte completa e probe real no Supervisor ainda pendentes.

# 0.1.0-rc.37 — append de auditoria com fsync

- Cada evento de auditoria agora faz flush e `fsync()` do arquivo antes de a operação ser considerada registrada.
- Na criação inicial do arquivo, também sincroniza o diretório pai para persistir a entrada.
- Falha de sincronização mantém o comportamento fail-closed: a operação não prossegue como se a auditoria estivesse íntegra.
- Dois testes regressivos cobrem fsync do arquivo/diretório na criação e fsync em append subsequente.
- Não altera APIs, autenticação, rede, opções, Publisher, políticas de produto ou execução de código não confiável.
- Supervisor build ARM64, Dockerfile tests, instalação e probe vivo PASS em 24/11/2026; 19 eventos de auditoria anteriores ao boot foram recuperados. Fsync foi exercitado pelos testes de regressão. Não equivale a ensaio de queda abrupta ou falha física de mídia.

# 0.1.0-rc.36 — conecta timestamp de boot ao probe de persistência

- O processo principal do probe agora lê `RUNNER_API_PROBE_BOOT_STARTED_AT` e repassa o instante a `run_probe()`.
- A contagem de eventos anteriores ao boot deixa de permanecer desconectada do caminho real de inicialização.
- Inclui regressão de integração que chama `main()` com ambiente sintético e exige que o timestamp chegue a `run_probe()`.
- Mantém probe somente leitura, sem preparação/publicação, sem mudança de rede, credenciais, opções ou políticas.
- Build/teste pelo Dockerfile e validação real no Supervisor ainda pendentes; esta RC não está publicada nem instalada.

# 0.1.0-rc.35 — verificação de auditoria persistida entre boots

- O probe captura o instante de início do contêiner e consulta a auditoria antes/depois do preflight.
- Conta somente eventos de auditoria anteriores ao início do boot atual, permitindo evidenciar a persistência do volume após atualização/reinício normal.
- Não grava marcador adicional, não altera o volume fora dos eventos read-only já existentes e não executa operações de preparação/publicação.
- Inclui teste sintético para reconhecer evento anterior ao boot.

# 0.1.0-rc.34 — importar sys no probe live API

- Corrige a falha de importação da RC33: o probe usa `sys.path` em modo Python isolado e agora importa explicitamente `sys`.
- Mantém o caminho confiável fixo `/app`, marcador de início e testes de regressão.
- Nenhuma mudança de endpoint, autorização, rede ou efeito operacional.

# 0.1.0-rc.33 — correção do probe sob Python isolado

- Corrige o caminho de importação do probe interno quando executado com `python -I`, adicionando somente o diretório fixo `/app` ao `sys.path`.
- Emite marcador de início para distinguir processo iniciado de probe concluído.
- Mantém o processo em background, sem abrir portas, sem expor Bearer e sem chamar preparação/publicação.
- Inclui teste de regressão do caminho de importação isolado.

# 0.1.0-rc.32 — probe autenticado da API viva

- Adiciona smoke probe interno no contêiner para exercitar a API loopback real com o Bearer já provisionado, sem expor ou imprimir o segredo.
- Verifica rejeição sem autenticação, status, projetos aprovados, status do Publisher, auditoria sanitizada e preflight/release-plan dos workspaces sincronizados.
- O probe não chama prepare, publication-preview/propose, publish, reconcile, nem executa código dos projetos; apenas preflight/release-plan read-only, com eventos de auditoria.
- Executa em processo separado, não bloqueia a inicialização do serviço e não altera portas/rede do add-on.
- Inclui testes sintéticos do contrato do probe e o integra à validação do Dockerfile e à imagem runtime.

# 0.1.0-rc.31 — probe declarativo em workspace Git real

- Exercita a exportação declarativa confiável contra os blobs reais do workspace sincronizado, usando SHA de origem e distribuição fixados.
- Gera pacote e proveniência somente em diretório temporário, verifica hashes e remove a saída ao terminar.
- Não executa scripts do projeto, não altera o workspace, não cria recibo de release e não publica.
- Mantém os gates normais de política: a preparação durável pela API continua recusada quando o pacote não está elegível.
- Adiciona testes de regressão para blobs reais em repositório Git temporário, pin do exportador, execução não-root e ausência de mutação dos checkouts.

# 0.1.0-rc.30 — cadastro inicial por Configurações

- Move o cadastro inicial único do proprietário para as opções do add-on no Home Assistant; o formulário de cadastro pelo Ingress deixa de existir.
- Processa a senha temporária no startup por IPC local com a autoridade isolada e limpa os dois campos via Supervisor API somente após confirmar o estado durável.
- Inclui o helper no estágio de validação e na imagem runtime; RC29 o referenciava no Dockerfile sem copiá-lo.
- Remove a redigitação de senha no consentimento de cada publicação: sessão HA verificada, CSRF de uso único e confirmação explícita `PUBLICAR` permanecem.
- Mantém publicação bloqueada, token de escrita vazio e nenhuma alteração no add-on instalado.

# 0.1.0-rc.28 — diagnóstico granular da sessão de cadastro

- Distingue sessão ausente, expirada, identidade/origem/Ingress divergentes, formato e CSRF sem registrar valores sensíveis.
- Registra PID e contagem de sessões ativas para confirmar perda de estado entre a emissão e o POST.
- Mantém mensagem externa genérica e validações de segurança; nenhuma senha, nonce, cookie, origem ou caminho Ingress é registrado.
- Adiciona teste integrado GET → POST pelo contrato do Supervisor Ingress e regressões para origem/caminho.
- Nenhuma alteração em credenciais, identidade, permissões, token de escrita ou gate de publicação.

# 0.1.0-rc.27 — correções do build ARM64 e diagnóstico do cadastro

- Envia diagnósticos sanitizados para stderr, preservando stdout para respostas JSON dos testes integrados.
- Trata erros de validação de formulário como recusa de entrada (403), sem confundi-los com falhas internas (503).
- Atualiza a regressão IPC para esperar o código seguro específico `ipc_action_denied`.
- Mantém propagação limitada de códigos, sem registrar credenciais ou conteúdo do formulário.
- Mantém nonce CSRF de 120 segundos, Origin HTTPS exata, identidade HA, permissões IPC e publicação de produtos bloqueada.

# 0.1.0-rc.26 — diagnóstico seguro da recusa no cadastro

- Registra códigos de erro constantes do cadastro sem registrar senha, corpo do formulário, cookies, cabeçalhos ou caminhos privados.
- Propaga pela IPC apenas códigos de erro previamente limitados; exceções inesperadas viram `internal_error`.
- A tela informa quando o nonce CSRF de 120 segundos expira e apresenta instrução específica para erros de sessão ou validação.
- Mantém Origin HTTPS exata, identidade HA, nonce de uso único, CSRF, IPC por UID, permissões e gate de publicação fechado.
- Nenhuma credencial ou grant é criada por diagnóstico; publicação de produtos continua bloqueada.

# 0.1.0-rc.25 — validação final da candidata de cadastro

- Corrige fixture unitária para fornecer o caminho Ingress autenticado exigido pelo cadastro.
- Mantém nonce CSRF de uso único, identidade HA vinculada, Origin HTTPS exata e vínculo ao caminho Ingress.
- Mantém consentimento de publicação separado por cookie HttpOnly, CSRF e reautenticação.
- Build ARM64 e suíte completa obrigatórios no Supervisor; homologação real do cadastro após instalação.
- Publicação de produtos continua bloqueada.

# 0.1.0-rc.24 — cadastro inicial sem dependência de cookie próprio

- Evidência real RC23: owner_session_cookie_missing_or_invalid.
- Cadastro usa nonce CSRF de 256 bits, uso único, validade de 120 s, vinculado à identidade HA e caminho Ingress verificados; exige Origin HTTPS exato.
- Consentimento de publicação mantém cookie HttpOnly, CSRF e reautenticação independentes.
- Validação integrada do cadastro sem cookie; publicação de produtos continua bloqueada.

# 0.1.0-rc.23 — cadastro via HA Ingress

- Aceita campos Cookie separados, mas recusa duplicação do cookie do proprietário.
- Usa política de referência same-origin nos formulários, preservando validação exata de Origin e CSRF.
- Diagnóstico sanitizado e retorno ao cadastro quando falta sessão ou origem.
- Corrige comparação de confirmação de senha UTF-8 em ambas as camadas; inclui regressões.
- Publicação de produtos permanece bloqueada; candidata pendente de validação no Supervisor.

# Changelog

## 0.1.0-rc.22 — compatibilidade IPC da autoridade (24/11/2026)

- Corrige a divergência entre o bootstrap (02750, setgid) e a validação dos diretórios IPC de Approval/Publisher (antes 0750). Mantém verificação de UID, GID, modo exato e SO_PEERCRED.
- Nova homologação integrada em laboratório: pacote sintético elegível, cadastro por UI simulada de HA, IPC Unix com UIDs/GIDs reais distintos, consentimento com CSRF/origin/senha, grant Ed25519, recusa de terceiro e de binding adulterado, gate real de publicação fechado sem token de escrita. Nenhum destino real é alterado.
- RC21 permanece no histórico; nenhuma configuração, identidade ou credencial real é habilitada. Validação da candidata pelo Supervisor ARM64.

## 0.1.0-rc.21 — retenção não destrutiva e homologação (24/11/2026)

- Substitui o teto fixo de quatro snapshots por orçamento global de 8 GiB de arquivos históricos; exige 2 GiB livres após o clone (2,5 GiB antes). Mantém todos os snapshots e recibos nos caminhos originais. Não elimina arquivos automaticamente.
- Recusa arquivos históricos não gerenciados, links, objetos especiais e orçamento excedido; mantém o workspace anterior. Registra contagem e bytes sem expor caminhos ou segredos.
- Teste integrado como runner: seis rotações, preservação do recibo anterior, preparo de pacote sintético, verificação de recibo e idempotência, sem publicação.
- Nenhuma ativação de Publisher, Approval ou sandbox; a validação ARM64 ocorre no Supervisor.

## 0.1.0-rc.20 — candidata única para homologação final (24/11/2026)

- Correção de segurança M020: arquivos runtime de autoridade movidos para diretórios root-managed separados (owner root, grupo do serviço, modo 0750); contas de serviço não podem substituir arquivos 0440 por manipulação do diretório pai.
- Testes de bootstrap cobrem os novos diretórios e os caminhos dos três serviços foram atualizados. Suíte completa ainda pendente do build de validação no Supervisor.
- M021: teste de permissões com UIDs/GIDs fixos e prova de leitura/escrita cruzada; teste de regressão confirma que Approval, Publisher e Owner UI iniciam com ambiente limpo.
- SEC-M020: `run.sh` não transmite `RUNNER_AUTH_TOKEN` nem `RUNNER_GITHUB_READ_TOKEN` aos três serviços de autoridade. Execução da suíte e nova revisão independente ainda pendentes.
- M027: regressões corrigidas para cache de workflow por vínculo, contrato de socket Publisher, endpoint de publicação protegido e resposta UTF-8 da página de status. Probe E2E passa a registrar status HTTP e erro sanitizado em falha.
- M028: Supervisor executou 354 testes; o probe E2E agora diagnostica a preparação em diretório temporário separado. Ajustados os fixtures de IPC para owner/group/mode exatos, o payload incompleto da rota Publisher e a cópia de `config.yaml` no estágio validation.

- Declara HA Ingress na configuração do add-on. O serviço apresenta uma página estática de status por padrão; cadastro e consentimento permanecem desligados (owner_ingress_enabled=false).
- A página de status aceita somente conexões do Supervisor (172.30.32.2) e não oferece POST, sessão, IPC, credenciais ou ação de publicação.
- O fluxo completo de owner ingress exige opt-in explícito, ID exato do usuário HA e origem HTTPS. O cadastro é único; após concluir, a interface solicita reinício para o bootstrap fixar a chave pública do proprietário e iniciar o publicador em modo somente leitura.
- Integra bootstrap persistente, Approval, Owner UI e Publisher em UIDs separados, com IPC Unix e verificações de identidade. O token de escrita GitHub é separado do token de leitura.
- As rotas de publicação continuam bloqueadas sem ativação root-managed e grant assinado do proprietário. Bearer operacional não autoriza publicação.
- O Dockerfile executa sintaxe, py_compile e a suíte unittest na etapa de validação. A execução desta candidata e o build ARM64 real permanecem pendentes da homologação pelo Supervisor no Home Assistant.

## 0.1.0-rc.19 — publicada no catálogo em 20/11/2026

- Distribuição no catálogo público pelo commit 64c9f134553ac9516de484330ee162ad2852bbb8.
- A leitura do Supervisor em 24/11/2026 confirmou a versão 0.1.0-rc.19 instalada e iniciada no add-on 45c28620_fabrica_software.
- A RC19 é o baseline preservado; ela não contém os incrementos M013–M019 desenvolvidos depois da publicação.
- A instalação confirmada não equivale à homologação integral ARM64, persistência após reinício ou ativação do publicador.

## Histórico — lote M006 anterior à integração M018/M019 (RC18)

- Contrato de publicação reproduz receita declarativa desde blobs pinados, confere política vigente e revalida arquivos/modos/hashes; não executa scripts de produto.
- Consentimento Ed25519 por ato com reautenticação independente, scrypt/throttle, preview e receipt persistidos, TTL/revogação/nonce e IPC por identidade do kernel; emissor, publisher, UI e preparador com contas distintas.
- Transporte GitHub somente bytes: prévia, árvore canônica, blobs SHA-256/OID, commit determinístico, CAS GraphQL beforeOid/force:false e ledger/reconciliação somente leitura após interrupção.
- Componentes dormentes na imagem e status autenticado somente leitura; run.sh e versão RC18 intactos. Sem listeners de aprovação, rota publish, enrollment, segredos reais ou ativação.
- Lote offline com API GitHub simulada/Git descartável, provas de quatro UIDs e revisão técnica; detalhes em M006-RPI-PIPELINE.md e relatório M006 da Issue #2. Nenhuma RC ou pacote de produto publicado.

## 0.1.0-rc.18 — Lote consolidado de integridade e autorização

- Preparação declarativa com recibo SHA-256, escopo exato e preservação de executáveis; repetição idempotente, trava entre processos e diretório final atômico.
- Console local de projetos/status/preparo/operações, sem porta adicional; auditoria recusa symlink, hardlink e FIFO.
- Componente separado de publicação SOMENTE em Git local sintético: autorização independente vinculada ao artefato, expiração/revogação/replay, prévia, CAS e recuperação de interrupção. Excluído da imagem final do HA.
- Verificador offline dos artefatos distintos HA ARM64 e Debian AMD64 do builder Artesão, excluído da imagem final; evidência sintética não equivale a build real.
- Publicação de pacotes pela API permanece desabilitada. Recibos de preparo permanecem com testes PENDING até execução e aprovação legítimas.
- Suíte offline integral e revisão técnica registradas no relatório do lote; build/instalação HA e fluxos reais de produtos são homologações separadas.

## Histórico de desenvolvimento anterior ao lote consolidado

Os registros seguintes preservam o estado declarado nos lotes anteriores; evidências novas estão na RC18 e no relatório do lote.

## Em desenvolvimento — executor isolado HA + Debian

- Adicionado `artesao_isolated_executor.py`, executável **exclusivamente fora do Home Assistant**, com pipeline oficial `release-evidence.py` → `prepare-distributions.py` → HA ARM64 e Debian AMD64 → verificação de `SHA256SUMS`/metadados → recibo local.
- Pré-requisitos de execução: VM descartável independente, prova externa de isolamento de rede, política local vinculada a SHA/versão, cache npm e imagens Docker já disponíveis offline; nenhuma credencial de servidores. O código recusa ambiente de HA, Docker remoto, root, checkout sujo ou HEAD diferente.
- Interface `--execute` é *opt-in* somente na VM aprovada; sem flag, apenas planeja. Falha não gera recibo de sucesso; saída marcada `INCOMPLETE-NOT-FOR-PUBLICATION`. ZIP da Forja Windows exige descriptor oficial existente, nunca sintetizado.
- 15 testes adicionais de executor/recibo/hash/política criados; **execução ainda pendente**. Script incluído somente no estágio de validação Docker, excluído da imagem final do add-on. `ARTESAO-BUILDER-002.md` descreve contrato.
- **Sem nova versão do Factory Runner no catálogo, sem merge, Actions, publicação, instalação ou alteração de servidores.**


## Em desenvolvimento — adaptador de pacotes Artesão Digital

- `artesao_adapter.py` analisa a mesma origem Git fixada para dois destinos independentes: HA ARM64 (contingência) e Debian AMD64 (Forja 01 principal).
- Perfil `artesao_digital.json` usa `mode: artesao_package`, com caminhos e cinco receitas oficiais fixadas por SHA Git; Avisaqui mantém seu perfil e suas regras.
- Versão e schema são verificados na origem e no catálogo, com gate para reuso de versão, ancestralidade da base, proveniência e migração.
- **Somente plano/pré-verificação**: não executa scripts, não gera pacote, não compila imagem, não publica. `/api/prepare` continua bloqueado até recibo de validação e builds reais; `/api/prepare-declarative` não reaproveita as regras do Avisaqui.
- Nove testes de regressão criados com repositórios Git sintéticos; **execução não comprovada** neste lote. Consultar `ARTESAO-ADAPTER-001.md`. Sem alteração de versão de add-on, Actions, merge, catálogo ou servidor.


## 0.1.0-rc.17 — Autodiagnóstico do plano de publicação

- Valida a função somente leitura release_plan após a sincronização, com os workspaces reais já aprovados.
- Registra apenas [RELEASE-PLAN] PASS (plano seguro, publicação desabilitada) ou BLOCKED (pré-verificação indisponível), sem caminho, token ou código arbitrário.
- Três testes HTTP/unitários adicionais preparados para pacote bloqueado, resultado inseguro e sigilo em erro.
- Não confirma autenticação HTTP nem publica pacotes; exige posteriormente teste dirigido autenticado do endpoint.
- Suíte integral de testes continua obrigatória na etapa de validação Docker do build no Home Assistant.


## 0.1.0-rc.16 — Plano de publicação por projeto (somente leitura)

- Nova rota autenticada POST /api/release-plan com project e expected_source_sha; utiliza o preflight real do perfil aprovado.
- Relatório limitado a projeto, SHA, elegibilidade de preparação, códigos de bloqueio e requisitos de publicação.
- Publicação continua desabilitada até existir autorização independente por artefato e executor seguro. Autenticação Bearer não aprova publicação.
- Quatro testes HTTP de autenticação, bloqueio, elegibilidade, sanitização e rejeição de aprovação fornecida pelo cliente.
- Suíte integral continua no estágio de validação Docker do add-on; não foi executada nesta sessão.
- Nenhuma alteração em outros add-ons, Actions, servidor ou projetos atendidos.


## 0.1.0-rc.15 — Sincronização por escopo sem arquivamento desnecessário

- Corrigido `workspace_archive_limit` causado por commits em outros add-ons no catálogo público.
- Se a origem do projeto não mudou e o pacote já está bloqueado por sua própria política, o Runner verifica no GitHub se o novo commit do catálogo alterou somente caminhos fora da pasta e dos arquivos compartilhados autorizados do projeto.
- Quando o comparativo é confiável e não há alterações relevantes, mantém o snapshot validado e registra `UNCHANGED_SCOPE` com `remote_public=<SHA>`, sem clonar, arquivar nem apagar arquivos.
- Falha de API, histórico não ancestral, comparação truncada, alteração na pasta/CI autorizada ou pacote elegível: **não** usa esse atalho; mantém os bloqueios originais e exige snapshot atual antes de preparar.
- Quatro testes de regressão adicionais, sem liberar publicação automática ou alterar dados de outros projetos.
- Não apaga as quatro cópias existentes; limpeza de arquivos permanece fora do escopo e depende de autorização própria. A suíte completa permanece obrigatória no build do Home Assistant.


## 0.1.0-rc.14 — Diagnóstico do histórico de sincronização

- Após o lote de sincronização, o Factory Runner verifica a leitura sanitizada do próprio histórico; registra `[OPERATIONS] PASS: sanitized_workspace_audit projects=N` quando encontra evidência dos projetos configurados.
- Falha de leitura ou ausência de evidência gera `[OPERATIONS] BLOCKED`, sem expor IDs de operação, caminhos, SHA ou tokens; o diagnóstico não libera publicações.
- Três testes de regressão incluídos: histórico válido, ausência de um projeto e log inseguro. A função de auditoria segue autenticada na API.
- O resultado do build e da suíte completa será verificado na instalação autorizada no HA. Nenhuma execução de Actions, compilação externa obrigatória nem mudança em outros add-ons.


## 0.1.0-rc.13 — Histórico de sincronização multiprojeto

- Corrigido o filtro autenticado de `GET /api/operations` para reconhecer as ações reais `workspace_sync:<projeto>`.
- Agora o histórico mostra `completed_workspace_sync`, `blocked_workspace_sync` e o estado final de bloqueio da política, sem incluir dados de credenciais ou caminhos.
- O identificador de projeto é validado; valores com traversal e entradas inválidas não aparecem no retorno.
- Dois testes HTTP adicionados para sincronização e rejeição de identificadores inválidos.
- Oito testes locais dirigidos da função de leitura: PASS. A suíte completa e o build do add-on continuam sujeitos à validação no Home Assistant.
- Nenhuma publicação de pacote de projetos foi habilitada, nenhum add-on alheio foi alterado. A RC é experimental e a instalação é responsabilidade separada.


## 0.1.0-rc.12 — Histórico autenticado de operações (RC experimental)

- Novo endpoint somente leitura `GET /api/operations` com Bearer, até 20 operações recentes; dados sanitizados (`operation_id`, `action`, `status`, `time`).
- Leitura limitada a 128 KiB; linhas inválidas ignoradas e log inseguro/indisponível bloqueado sem expor segredos.
- Quatro testes HTTP adicionais de autenticação, estados, sigilo, symlink e dados inválidos.
- Dois testes extras do executor externo exigem recusa de tokens de produção e Docker remoto; executor continua FORA da imagem final e sem permissão Docker no HA.
- Verificação local reproduzida da função de leitura de operações: 5 cenários PASS. A suíte completa do repositório ainda deverá rodar no estágio Docker validation do HA; sem alegar PASS antecipado.
- Nenhum outro add-on alterado; sem Actions, instalação no Raspberry, merge privado ou publicação de pacotes dos projetos. Issue #2.


## 0.1.0-rc.11 — Correção dos testes do build HA

- Corrigida chamada de `isolated_builder_preflight` no teste: agora passa SHA e versão exigidos.
- Corrigida fixture HTTP de pacote fechado para fornecer workspace sintético antes de verificar resposta 409, sem liberar operações bloqueadas.
- Dois erros da RC10 comprovados nos logs do Supervisor, que registrou 188 testes (169 ok, 1 FAIL, 1 ERROR, 17 SKIP).
- Testes continuam obrigatórios durante o build do Home Assistant. RC11 ainda não foi instalada nem homologada; nenhum PASS antecipado.
- GitHub Actions e instalação no Raspberry não executados nesta publicação. Issue #2.


## 0.1.0-rc.10 — Adaptador Artesão Digital (RC experimental)

- Pré-verificação para HA ARM64 e Debian AMD64 sem gerar pacotes ou publicar automaticamente.
- 24 casos de testes novos no estágio de validação Docker; execução no build do HA, sem declarar PASS antes dos logs.
- Executor externo permanece fora da imagem final; RC para homologação separada da execução Docker isolada.
- Fonte privada mantida em branch, GitHub Actions não executado, Raspberry não instalado. Issue #2.

## Histórico de desenvolvimento — executor isolado HA + Debian

- Adicionado `artesao_isolated_executor.py`, executável **exclusivamente fora do Home Assistant**, com pipeline oficial `release-evidence.py` → `prepare-distributions.py` → HA ARM64 e Debian AMD64 → verificação de `SHA256SUMS`/metadados → recibo local.
- Pré-requisitos de execução: VM descartável independente, prova externa de isolamento de rede, política local vinculada a SHA/versão, cache npm e imagens Docker já disponíveis offline; nenhuma credencial de servidores. O código recusa ambiente de HA, Docker remoto, root, checkout sujo ou HEAD diferente.
- Interface `--execute` é *opt-in* somente na VM aprovada; sem flag, apenas planeja. Falha não gera recibo de sucesso; saída marcada `INCOMPLETE-NOT-FOR-PUBLICATION`. ZIP da Forja Windows exige descriptor oficial existente, nunca sintetizado.
- 15 testes adicionais de executor/recibo/hash/política criados; **execução ainda pendente**. Script incluído somente no estágio de validação Docker, excluído da imagem final do add-on. `ARTESAO-BUILDER-002.md` descreve contrato.
- **Sem nova versão do Factory Runner no catálogo, sem merge, Actions, publicação, instalação ou alteração de servidores.**


## Histórico de desenvolvimento — adaptador de pacotes Artesão Digital

- `artesao_adapter.py` analisa a mesma origem Git fixada para dois destinos independentes: HA ARM64 (contingência) e Debian AMD64 (Forja 01 principal).
- Perfil `artesao_digital.json` usa `mode: artesao_package`, com caminhos e cinco receitas oficiais fixadas por SHA Git; Avisaqui mantém seu perfil e suas regras.
- Versão e schema são verificados na origem e no catálogo, com gate para reuso de versão, ancestralidade da base, proveniência e migração.
- **Somente plano/pré-verificação**: não executa scripts, não gera pacote, não compila imagem, não publica. `/api/prepare` continua bloqueado até recibo de validação e builds reais; `/api/prepare-declarative` não reaproveita as regras do Avisaqui.
- Nove testes de regressão criados com repositórios Git sintéticos; **execução não comprovada** neste lote. Consultar `ARTESAO-ADAPTER-001.md`. Sem alteração de versão de add-on, Actions, merge, catálogo ou servidor.


## 0.1.0-rc.9 — Cadastro seguro do Artesão Digital

- Novo perfil `projects/artesao_digital.json` como segundo projeto, em **modo exclusivo de sincronização**, com origem `fabricacao_e_orcamentos:main` e distribuição `fabricacao-e-orcamentos-ha:main`.
- `rc_fastlane.py` e `workspace_sync.py` recebem validação explícita de perfil sem fluxo de RC e leitura do blob de versão Git fixado. O Avisaqui permanece com política de pacote própria e inalterada.
- API expõe o perfil, porém **nega qualquer preflight/prepare** do Artesão Digital até existir adaptador de pacotes seguro. Mesmo se a auto-preparação estiver ligada, `PREPARE_BLOCKED_BY_PROFILE`.
- Cinco testes novos **adicionados, ainda sem execução comprovada** neste lote. GitHub Actions, publicação, build ARM64 e instalações não executados. Consultar `RC9-VALIDACAO.md`.
- Com `workspace_sync_enabled=true`, a RC9 deverá sincronizar dois projetos aprovados; novos projetos continuam exigindo cadastro próprio.


## 0.1.0-rc.8 — Sincronização multiprojeto por perfis aprovados (candidata)

- **Corrige seleção fixa:** remove `workspace_sync_project` do schema e aceita `workspace_sync_enabled` como chave geral (padrão desligada). Sem habilitação, não há busca GitHub.
- Com a chave ligada, sincroniza **todos os perfis versionados aprovados** em `projects/*.json`, até 32 por rodada. Uma falha não interrompe os demais. Execução sequencial compartilha a trava da API, liberada entre projetos.
- Preparação continua **desligada por padrão** (`workspace_auto_prepare=false`) e bloqueada para pacote fechado. Nunca executa scripts não confiáveis, Git push, merge nem publicação.
- **Laboratório:** 50/50 testes Python PASS em Linux sem root, incluindo novos testes multiprojeto e Git local real; sintaxe de Shell/Python e YAML PASS. **Pendente:** build/instalação da RC8 no HA e clone com credencial privada real.
- O catálogo atualmente contém apenas `avisaqui.json`; Artesão Digital e projetos futuros entram por perfil separado após validação, sem mudar o motor multiprojeto.
- **Candidata não instalada** neste estágio; rastreabilidade: `RC8-VALIDACAO.md` e Issue #2.


## 0.1.0-rc.7 — Sincronização privada GitHub somente leitura (CANDIDATA EM BRANCH)

- Sincroniza os repositórios **pré-aprovados no perfil** em volume privado do Factory Runner, usando HTTPS GitHub, token fine-grained de leitura configurado **apenas no Home Assistant** e verificação SHA de branches Git contra API remota.
- É **opt-in**: `workspace_sync_project` vazio preserva comportamento atual; `github_read_token` é segredo mascarado; `workspace_auto_prepare` inicia em `false`. Sem habilitação, não faz rede nem clonagem extra no startup.
- Git usa `--no-checkout` e não executa scripts/hook/submódulo nem envia token na URL, processo Git ou logs. Credencial existe somente em arquivo temporário `0600`, apagado ao concluir clone.
- Bloqueia diretórios desconhecidos, SHA divergente, URLs fora do perfil, volumes simbólicos e política fechada; atualizações preservam snapshots anteriores e usam troca recuperável. Trabalho isolado pela trava global da API, sem publicar ou alterar outros serviços.
- **Laboratório:** 18 testes novos PASS com Git local real e usuário sem root; conjunto local disponível 45 PASS; sintaxe shell/Python e YAML verificados. **Não executados:** clone GitHub privado real com token, build Docker da RC7 nem HA físico.
- **Avisaqui na data da verificação:** pacote `AVISAQUI-PACOTE-009` fechado e aguardando homologação; deve sincronizar somente leitura e **recusar preparação de nova RC**, sem reabrir política.
- Publicação na loja e instalação exigem autorização própria. RC6 da loja e teste E2E no HA permanecem inalterados.


## 0.1.0-rc.6 — Teste E2E interno sem portas expostas (PUBLICADA; E2E HA PASS)

- `factory_e2e_probe.py`: durante a inicialização, cria **apenas repositórios sintéticos temporários** e executa a API real por loopback efêmero `127.0.0.1:0`, com token de teste gerado no processo isolado. O token real do add-on não é transmitido ao teste.
- Confere autenticação, preflight com política aberta, preparação declarativa pela rota padrão, blobs e SHA-256, proveniência, não alteração dos repositórios, bloqueio de publicação, SHA inválido e pacote fechado. Apaga automaticamente os arquivos sintéticos.
- `run.sh` chama o teste com usuário sem root e ambiente limpo antes da API principal. O log apresenta `[E2E] PASS` ou `[E2E] BLOCKED`; falha do teste não libera operações nem altera as políticas de segurança.
- Dockerfile copia o probe para a **imagem final**, compila-o e executa os testes de regressão no estágio de validação. Sem GitHub Actions nem dependência de download de projeto.
- **Laboratório real:** execução direta sob `nobody`: `[E2E] PASS`; 4/4 testes novos PASS; conjunto local de 56/56 testes PASS. Código verificado pelos hashes Git, sem Docker/ARM64 neste laboratório.
- **HOMOLOGAÇÃO PARCIAL REAL:** o último bloco de logs fornecido pelo operador confirmou `[E2E] PASS` e `[API] READY` no HA. Esse PASS cobre apenas pacote sintético e política interna, não provisionamento de projetos privados.
- **PUBLICADA:** RC6 no catálogo por PR #48 (commit `55363aecb421cc4cd7c4c2976325f087f622e5b9`), sem alteração de outros add-ons; instalação inferida pelo log E2E e versão exata a conferir pelo Supervisor.


## 0.1.0-rc.5 — Preparação declarativa sem execução de scripts (CANDIDATA EM BRANCH)

- A rota autenticada `POST /api/prepare` utiliza exportação declarativa quando o perfil confiável possui receita aprovada; scripts externos **não** são executados nessa operação. A rota alternativa `/api/prepare-declarative` permanece disponível para diagnóstico dirigido.
- Sem receita aprovada, o caminho legado continua fail-closed com Bubblewrap obrigatório. `/api/corrigir-issue` e publicação/commit/push remoto permanecem bloqueados; nenhuma permissão do Home Assistant foi ampliada.
- Núcleo com leitura Git por SHA fixado, mapeamento/condições validados, rejeição de symlinks, controle de tamanho/quantidade/tempo, hashes SHA-256, manifesto e proveniência. Workflow compartilhado somente quando o commit público fixado comprova compatibilidade.
- **Execução local real:** 18/18 testes do núcleo (blobs idênticos aos da branch), 19/19 testes de preflight (após correção das fixtures), 8/8 testes HTTP dirigidos e 3/3 testes HTTP com preflight real, Git sintético e preparação por `/api/prepare`. O exportador canônico pinado e o novo método geraram 29 arquivos de pacote + 1 workflow compartilhado com bytes e proveniência idênticos em fixture sintética, e `--verify` passou.
- **Verificações da fonte:** 135/135 caminhos de distribuição equivalentes à receita original no snapshot real e 1 workflow compartilhado separado; blobs Git de código/testes conferidos; os programas dependentes de Landlock e planejador pré-existentes permanecem.
- **Não concluído:** execução da suíte completa em Docker, build ARM64 e homologação do funcionamento no Home Assistant físico. Nenhuma execução de GitHub Actions, merge, publicação na `main`, instalação no Raspberry ou liberação de execução de código não confiável foi realizada.
- **Status:** CANDIDATA DE DESENVOLVIMENTO, não instalada nem homologada; publicar somente após revisão do diff, gates da norma de catálogo e autorização aplicável.


## 0.1.0-rc.4 — Candidata privada de diagnóstico Landlock (NÃO PUBLICADA)

- `landlock_probe.py`: consulta somente a versão ABI da interface Linux, syscall 444, sem aplicar regras de segurança nem alterar o host.
- O diagnóstico `controlled_worker --task diagnose` inclui `landlock.status`, `abi`, capacidade filesystem/TCP/UDP/IPC e campos fixos `enforcement_verified=false` e `safe_for_untrusted_code=false`.
- Tratamento explícito de interface inexistente/bloqueada/indisponível; retorno `ENOSYS` é `syscall_unavailable`, não prova ausência no kernel do Raspberry.
- Dockerfile preparado para instalar `landlock_probe.py` nos estágios de validação e execução, compilá-lo e incluir 11 testes novos.
- Laboratório local: 11/11 cenários PASS, módulo `landlock_probe.py` testado com SHA de blob Git conferido. Consulta não-root no laboratório retornou `syscall_unavailable` — **não** representa o Home Assistant.
- **Planejador declarativo experimental:** `trusted_export_plan.py` gera apenas mapa em memória, sem executar script/ler Git/copiar/publicar; 13 testes locais PASS. Incluído só no estágio de validação do Dockerfile, **não no runtime**. Mapeamento comum de 135 arquivos comparado com o exportador oficial no snapshot Git `a4b97c1...` (995.337 bytes de metadados de tamanho); workflow compartilhado permanece com autorização própria. Sete regressões adicionais PASS no laboratório com metadados reais selecionados. **Equivalência integral de bytes/proveniência e patch de CI ainda não validada**.
- **NÃO PUBLICADO/INSTALADO:** `hassio-addons:main` continua na RC3. A RC4 não substitui o Bubblewrap, não libera `/api/prepare`, não altera a política AppArmor e não executa código não confiável.

## 0.1.0-rc.3 — Candidata de teste do worker controlado (19/11/2026; homologação HA pendente)

- Worker de somente leitura incorporado à fonte privada; 3 tarefas: diagnosticar segurança do próprio processo, conferir perfil instalado e pré-verificar projeto confiável.
- Rota autenticada `POST /api/worker/run`; recusa outras operações, parâmetros extras, projetos/SHAs inválidos, erros do worker e falhas de auditoria.
- Subprocesso sem root, ambiente mínimo sem credenciais, `python -I`, tempo máximo e limites de recursos por processo; não há isolamento comprovado para executar código não confiável.
- Diagnóstico no log do perfil AppArmor e flags do processo, sem token herdado; verificação de inclusão do worker na imagem final. Não altera a política de segurança do Home Assistant.
- Laboratório local: 7 testes do núcleo, 12 testes de rota HTTP com trecho idêntico ao versionado, 3 testes do lançador com trecho idêntico ao versionado, execução não-root real de diagnóstico e recusa de operação proibida, todos PASS. A suíte integrada da imagem e Docker/ARM64/HA ainda estão pendentes.
- `/api/prepare` continua a exigir Bubblewrap, atualmente BLOCKED no Raspberry. Fechamento e correção de Issues continuam HTTP 403. Porta externa não mapeada.
- `config.yaml` identifica a candidata `0.1.0-rc.3`. A publicação exige conferência do commit em `hassio-addons:main/factory-runner/`; a instalação e a homologação no Home Assistant são etapas separadas.

## 0.1.0-rc.2 — Candidata de pré-verificação multi-projeto (19/11/2026)

- Factory Runner permanece add-on independente do Avisaqui.
- Perfis JSON por projeto; Avisaqui é somente o primeiro perfil registrado.
- API autenticada somente leitura: lista de projetos e preflight por SHA fixado.
- Dockerfile incorpora Git, CLI de preflight e perfis versionados.
- Operações de publicação, push/merge e alteração autônoma permanecem bloqueadas.
- Porta externa 9876 continua não mapeada e bind localhost; nenhum deploy.

- Correção da fixture de árvore Git congelada e de refs RC com subdiretórios.
- Git sem credenciais herdadas; exportador com HOME temporário e Python isolado.
- Testes reais de HTTP/Git, preparação sem push, pin e hashes verificados.
- CA opcional por secret de build, sem desativar TLS ou incorporar CA à imagem.
- Smoke autenticado/reinício com emulação opcional em userspace.

- Sandbox obrigatório: user/PID/network/IPC/UTS namespaces, capabilities zeradas,
  origem e .git somente leitura, ambiente limpo, UID não-root e controles RLIMIT.
- Helper de limites em processo novo, monitor de saída que falha fechado,
  encerramento de grupo e tratamento explícito de indisponibilidade na CLI/API.
- Inicialização protege contra symlinks e permite travessia mínima do volume
  ao UID runner, preservando options.json; código/imagem legíveis pelo serviço.
- Provas reais de isolamento/consumo separadas dos testes com mocks e da
  integração Git funcional; negativa de namespace não recebe PASS artificial.
- Corrigida ordem de NPROC: bootstrap confiável cria o namespace antes de
  aplicar o teto de 32 processos ao exportador. Prova positiva de isolamento
  e controles executada no Codex, sem desativar Bubblewrap ou limites.

**Evidências e impedimentos no PR #43; HA não homologado.** O sandbox só é
considerado disponível após prova real. Cgroup agregado e quota rígida ainda
exigem ambiente/política operacionais; não fecha pacote nem publica.


## 0.1.0-rc.1 — Candidato restrito (18/11/2026)

- Integração estrutural ao catálogo central Home Assistant.
- Registro próprio no cadastro da loja e na seleção de build ARM64 manual.
- API com autenticação obrigatória e operações privilegiadas bloqueadas.
- Remoção de credenciais fixas e redução de dependências e volumes.
- Testes de regressão de segurança incluídos para execução isolada.

**Não homologado no hardware. Não equivale à versão funcional do worker.**

- M029: diagnóstico do probe E2E inclui mensagem de exceção sanitizada para identificar a causa do `ValueError` no preparo declarativo sintético. Não expõe caminhos reais, tokens ou dados de workspace.

- M030: testes E2E de preparação agora rodam como usuário real `runner` no estágio validation; a suíte root os pula e o Dockerfile executa o probe em seguida com UID/GID e permissões reais. Corrige o falso `publisher_snapshot_owner_mismatch` causado por simular `geteuid()` sem trocar o owner dos diretórios.

- M031: fixtures locais de workspace usam `git clone --no-hardlinks`, igualando o comportamento esperado do clone remoto e evitando que a ACL rejeite objetos Git compartilhados por hardlink. A validação agora alcança a suíte E2E não-root.

- M032: fixture Git usa `--no-local --no-hardlinks` para impedir otimização de clone local e garantir que nenhum objeto do snapshot compartilhe inode com o repositório de origem.
