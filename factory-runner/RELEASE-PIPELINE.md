# Esteira oficial — Factory Runner

**Estado vigente — M160 / 26/11/2026:** RC68 (0.1.0-rc.68) permanece instalada/started no HA; RC69 (0.1.0-rc.69) está somente em desenvolvimento. Nenhuma RC69 foi publicada/instalada nesta retomada; nenhum perfil AppArmor foi carregado/ativado.

**Validação M122 preservada:** compilação cruzada estática AMD64 e ARM64 com Zig 0.13.0: PASS; ELF sem PT_INTERP/PT_DYNAMIC; 14/19 testes de lógica pura PASS, 5 BLOCKED no Windows. Isso não substitui build Docker nativo, suíte Linux nem runtime.

**Correções de fonte/documentação M117–M160:** campo security_cap_sys_admin_in_userns presente; helper estático; transição Cx; peer literal exato `45c28620_fabrica_software` (sem wildcard); child sem sinais internos; pai envia somente SIGKILL; rprivate/tmpfs fora do bloco efetivo, apenas fragmentos candidatos; AppArmor 3.1 não restringe MNT_DETACH, que fica fixo no helper confiável. Matriz positiva/negativa cobre sinais, capabilities, proc, scratch, mount, tmpfs, unmount e cleanup. O parser HA 3.1.7 e o comportamento sob enforce ainda não foram executados.

**Quotas/runtime:** consulta somente leitura no HA confirmou cgroup v2 presente, mount RO, delegation_candidate=false, sem teto finito observado de CPU/memória, PIDs herdado 8781 e Bubblewrap bloqueado por `Failed to make / slave: Permission denied`. O probe de cgroup foi endurecido em M128–M150 para exigir cgroup domain, presença/W_OK/R_OK dos controles e read-back; testes novos M128–M153 ainda NÃO EXECUTADOS. Nenhuma quota agregada por job foi comprovada.

**Gates:** build Dockerfile completo, suíte Linux e execução nativa do helper; parser/execução AppArmor 3.1.7 sob enforce com controles positivos/negativos; delegação cgroup gravável e quotas agregadas CPU/RAM/swap/PIDs; integração seccomp no executor genérico. M006/P0 mantém a validação restrita ao Raspberry Pi como add-on HA, sem host/VM/nuvem externa. Nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed. Publicação RC segue autorização contínua M055; atualização/instalação e ativação AppArmor são estados separados.

---

## Regra do proprietário — sem backup da RC anterior no HA (25/11/2026)

Durante o ciclo experimental do Factory Runner, **não criar snapshot/backup da instalação RC anterior no Home Assistant antes de instalar/atualizar a próxima RC**. As RCs anteriores são testes incompletos e não são destino de rollback útil. A rastreabilidade e a recuperação do código são asseguradas por commits/branches Git, pacote publicado, manifesto de proveniência, hashes e registros da instalação/homologação.

Escopo restrito ao add-on Factory Runner e às atualizações normais de RC previamente autorizadas. Não apagar backups existentes; não alterar a política de backups gerais do HA ou de outros serviços; preservar opções e dados persistentes do add-on. Se uma mudança passar a envolver migração destrutiva de dados, exclusão ou impacto fora do ciclo normal de RC, tratar esse risco específico separadamente. A atualização de RC normal segue sem snapshot da versão anterior.


## M055 — autorização contínua de publicação de RC do Factory Runner (24/11/2026)

O proprietário autorizou expressamente publicações repetidas de candidatas do próprio Factory Runner, sem nova solicitação a cada RC, enquanto este desenvolvimento permanecer em andamento, para fins de validação, testes e homologação. Escopo: somente `mmcromero/hassio-addons:main/factory-runner/`, pelo procedimento oficial e com preservação integral dos demais add-ons e arquivos compartilhados.

A autorização não abrange publicação de pacotes Avisaqui/Artesão/outros produtos, ativação do Publisher, alteração de políticas de produto, credenciais, segredos, outros diretórios do catálogo ou ações destrutivas no host. Publicação, atualização/instalação e homologação são estados distintos. A atualização da instalação Factory Runner RC30 para RC31 está autorizada expressamente no pedido de 24/11/2026. Preservar opções e dados do add-on.

A passagem de bastão integral M055 está em `docs/CONTINUIDADE-ATIVA.md` e na Issue #2 do Orquestrador. A próxima ação daquela passagem foi concluída e seu resultado está registrado em M056: RC31 publicada, instalada/iniciada e probe declarativo real PASS. Não pedir novamente autorização de publicação de RC do Factory Runner durante este desenvolvimento.

Avisaqui e Artesão mantêm políticas, versões e receitas independentes.

## Auditoria M050 — RC30 e reconciliação do estado (24/11/2026)

### Baseline e escopo revisados

- Base indicada por M047: `15e6625bbc22f293677062fe299015d65c62fd04`.
- HEAD RC30 indicado por M047: `4daf3fe633f067f8d32c532eae5e5c2a3f7d98d1`.
- Comparação GitHub da base ao HEAD RC30: **17 commits à frente, 0 atrás**.
- Arquivos de código/configuração/documentação do lote: 12 caminhos. As mudanças de runtime concentram-se em `owner_settings_enroll.py`, `owner_approval.py`, `owner_bootstrap.py`, `owner_consent_ui.py`, `ha_ingress_server.py`, `owner_ingress_service.py`, `run.sh`, Dockerfile/config e duas suítes de teste.
- RC30 declara `0.1.0-rc.30` em `config.yaml` e no cabeçalho do changelog.
- M049 acrescentou apenas documentação; não alterou o código da RC30. O HEAD documental atual não deve ser confundido com o HEAD de código RC30.

### Conclusões da revisão estática

1. Cadastro inicial único movido para as Configurações do add-on. O Ingress não expõe mais rotas de cadastro; apresenta orientação para usar Configurações e mantém o consentimento por proposta.
2. `owner_settings_enroll.py` executa como root no startup, valida arquivo/opções, confirmação e identidade HA/Ingress, comunica-se com a autoridade Approval somente pelo socket Unix local e só solicita a limpeza dos campos temporários depois de receber estado de cadastro durável.
3. A autoridade valida a confirmação `CADASTRAR`, compara a senha em tempo constante, cria a chave Ed25519 e o registro em staging privado, faz fsync e confirma o estado antes de devolver sucesso.
4. Se a limpeza das opções pelo Supervisor falhar, o helper retorna falha e o startup fecha; em nova tentativa, o estado já cadastrado evita recriar credenciais e permite repetir a limpeza. Isso é comportamento previsto pelo código, ainda sem ensaio integrado desta candidata.
5. Consentimento de publicação não pede a senha novamente. A jornada mantém identidade/sessão HA, CSRF de uso único e confirmação explícita `PUBLICAR`; o grant e os gates independentes do Publisher permanecem.
6. Dockerfile inclui o helper tanto na etapa de validação quanto na imagem runtime; `run.sh` aguarda Approval IPC antes de processar as opções temporárias e falha fechado se a submissão não puder ser processada.
7. A leitura estática não identificou no diff revisado uma rota de cadastro Ingress remanescente nem um caminho de consentimento que exija redigitação da senha. Isso não equivale a aprovação de segurança nem a execução dos testes.

### Cobertura adicionada/alterada identificada

- `test_factory_runner_owner_settings_enroll.py`: 7 testes novos (cadastro via IPC local, idempotência após cadastro, rejeição de senha inválida, identidade incompleta, campos vazios, limpeza seletiva e falha de limpeza).
- `test_factory_runner_owner_ui_enrollment.py`: 4 testes no estado RC30 (orientação para Configurações, consentimento sem senha, POST HTTP sem senha e rotas antigas de cadastro indisponíveis).
- `test_factory_runner_owner_bootstrap.py`: 10 testes existentes/atualizados na área de provisionamento e identidade.
- `test_factory_runner_owner_ingress_service.py`: 2 testes de serviço Ingress.
- O Dockerfile declara validação com `bash -n`, `py_compile`, `unittest discover` da suíte `test_factory_runner_*.py`, mais rodadas não-root de workspace sync e E2E probe. `validate_offline.py` é a entrada offline que gera logs, exit codes e hashes.

**Contagem acima é inspeção estática dos métodos de teste, não resultado de execução.**

### Limite objetivo de validação nesta etapa

- A árvore atual não contém arquivos em `.github/workflows/`; não existe workflow local de CI a consultar/disparar para esta candidata.
- Check-runs e status associados ao HEAD documental M049 retornaram vazios (`check_runs=[]`, status sem contextos). Isso não representa PASS.
- O conector GitHub disponível nesta sessão permite inspecionar e alterar conteúdo Git, mas não disponibiliza checkout/terminal para executar `validate_offline.py` ou Docker build.
- A instalação comprovada no HA permanece RC28; RC30 não está instalada. A atualização do add-on não foi autorizada nesta etapa e não deve ser usada como atalho para executar testes.
- Portanto, **a suíte RC30, a validação offline completa e o build Docker/ARM64 não foram executados nesta etapa**. Não declarar PASS, GO técnico final ou candidata pronta para publicação.

### Reconciliação documental concluída

O cabeçalho anterior deste manual (M019/RC20/RC19 baseline), o cabeçalho de `CONTINUIDADE.md` e o de `OPERACAO-ESTEIRA.md` estavam obsoletos em relação a M047/M049. Foram atualizados para declarar RC30 como estado de desenvolvimento e RC28 como última instalação comprovada. O histórico anterior foi preservado; as afirmações antigas não são mais apresentadas como estado vigente.

### Resultado M050

**AUDITORIA ESTÁTICA E RECONCILIAÇÃO DOCUMENTAL CONCLUÍDAS. VALIDAÇÃO EXECUTÁVEL PENDENTE.**

Próxima ação para encerrar a Entrega 1: executar `python3 validate_offline.py --output <diretório-novo>` em checkout confiável da fonte e, conforme os resultados, o build Docker da etapa de validação que exercita `bash -n`, `py_compile`, suíte completa e probes não-root. Corrigir falhas, repetir apenas os testes afetados e registrar logs/exit codes/hashes vinculados ao HEAD exato. Até essa evidência, não iniciar a Entrega 2 nem publicar/instalar RC30.

## Operação disponível

A API operacional permanece autenticada e em loopback. `/api/prepare` e
`/api/prepare-declarative` usam somente o perfil confiável da imagem, SHA completo,
política aberta, versão coerente e blob aprovado do exportador. Não executam o
exportador no caminho declarativo. `/api/release-plan` continua somente leitura;
`/api/fechar-pacote` continua 403 mesmo com Bearer válido.

O incremento M018/M019 integrou o Publisher isolado e as rotas autenticadas
`/api/publication-preview`, `/api/publication-propose`, `/api/publish` e
`/api/publication-reconcile`. Elas encaminham somente payloads fechados ao
Publisher por IPC Unix. O Publisher valida perfil, recibo, política vigente,
artefato reproduzido, token de escrita separado, ativação root-managed e grant
Ed25519 do proprietário. Sem qualquer gate, a escrita retorna bloqueio; Bearer
operacional não é consentimento. O estado atual permanece sem token de escrita
e sem ativação root-managed.

Console local, sob a conta confiável do Runner e com os diretórios configurados:

```sh
python3 -I /app/release_console.py projects
python3 -I /app/release_console.py status --project avisaqui --source-sha SHA_COMPLETO
python3 -I /app/release_console.py prepare --project avisaqui --source-sha SHA_COMPLETO
python3 -I /app/release_console.py operations
```

O console recusa seleção de comando, URL, caminho e publicação pelo cliente.
Não tem comando publish nem abre porta. Não altera opções/segredos do HA.
Receitas que exigem execução de código externo não são habilitadas pelo console.

## Integridade e repetição

O preparo usa identidade derivada de perfil, SHA de origem e SHA do catálogo,
trava interprocesso e staging exclusivo. Somente um diretório completo e selado
é renomeado para o nome final. Falhas preservam staging `.incomplete-*` para
inspeção; nenhum arquivo/snapshot existente é removido automaticamente.

`RELEASE_RECEIPT.json` registra projeto, pacote, versão, origem/ref/SHA,
destino/ref/SHA esperado, hash do perfil, escopo, arquivos exatos, modos, tamanhos,
SHA-256, momento e resultados de testes. A resposta inclui o digest canônico do
recibo. O mesmo pedido revalida todos os bytes e devolve o mesmo digest sem
criar outra candidata. Symlinks, hardlinks, traversal, `.git`, nomes sensíveis,
manifesto/artefato adulterado e budgets excedidos são recusados.

**Preparo não executa testes do produto.** O recibo nasce `tests=PENDING`; isso
impede publicação no componente de teste. Um resultado PASS externo só tem valor
se o executor legítimo e a autoridade verificarem sua origem e o digest exato.
Diretórios e perfis precisam ser exclusivos da conta confiável: hashes não
substituem isolamento, identidade ou autorização. Não edite recibos reais para
simular PASS. Fixtures modificam somente evidência sintética em diretórios temporários.

## Publisher runtime — integração M018/M019

- O serviço Publisher roda sob UID próprio e recebe requisições do Runner por socket Unix com SO_PEERCRED e ACL.
- Approval, Publisher e Owner UI são iniciados por `env -i` com PATH mínimo antes de `su-exec`; não recebem os tokens do Runner nem variáveis de workspace. O processo Runner/API mantém apenas os tokens necessários; o token de escrita do Publisher continua em arquivo privado separado. Regressão em `tests/test_factory_runner_security.py`.
- O token GitHub de escrita fica em arquivo privado separado do token de leitura dos workspaces; sem ele, o transporte é somente leitura.
- A ativação root-managed é uma trava independente. O consentimento do proprietário é por proposta, com sessão HA verificada, CSRF/nonce de uso único, confirmação explícita `PUBLICAR`, grant Ed25519, TTL e revogação. Não exige redigitação da senha do cadastro.
- A rota `/api/publish` existe, mas o gate de ativação permanece fechado no último estado documentado. A publicação do próprio add-on Factory Runner no catálogo não ativa a publicação de pacotes dos produtos.

## Publicador de referência em laboratório Git local — histórico RC18

`local_publisher.py` é componente de referência para testes, sem rota HTTP e sem
cópia na imagem final HA. Só escreve em Git **bare dentro do seu diretório de
estado privado**, sem remotes, URL, rede ou push. Não publica GitHub. Recusa
checkouts/targets externos. Seu caminho não é um atalho para publicar produtos.

A autoridade é injetada pelo executor confiável, com chaves HMAC independentes
do Bearer; não há emissor de aprovação na API, console ou perfis. Não foi criada
ou instalada chave de produção neste lote. `grant_payload` descreve o contrato,
não assina nem concede autoridade. Provisionamento real de aprovador, chaves,
revogação e executor isolado é dependência externa específica.

O grant assinado vincula autoridade, nonce, Issue, ação, projeto, pacote,
repositórios/refs, origem SHA completo, versão, SHA esperado da distribuição,
perfil, escopo/paths compartilhados e digest do recibo. Expiração máxima de 24h,
revogação e nonce persistente são verificados. Strings owner_approved, WhatsApp,
n8n ou Bearer não substituem assinatura. A mesma operação concluída é idempotente;
nonce com outro binding é replay. Banco SQLite serializa escritores.

`preview` mostra adições/modificações/exclusões contra o SHA fixado e não escreve
objetos/refs. Publicar exige testes PASS vinculados ao SHA e grant independente,
revalida bytes e expiração antes do CAS, cria commit filho do SHA esperado e usa
`git update-ref REF NOVO ANTIGO`. Não há force-push. Somente o prefixo aprovado é
substituído, com preservação de arquivos externos e modos executáveis. Paths
compartilhados precisam constar no perfil e no grant. A publicação GitHub do
próprio Runner neste lote é a exportação revisada pela equipe, não esse simulador.

Intent durável antecede CAS; um retry reconcilia o commit exato se houver queda
entre Git e SQLite. Ref divergente bloqueia; cancelamento/deadline impedem nova
escrita inclusive no retry. Falhas geram eventos sanitizados persistentes, sem
rollback automático da ref: outro escritor pode ter avançado. Revogação/expiração
impedem retry privilegiado; reconciliar manualmente a evidência preservada nesse
caso, sem renovar aprovação por inferência. SQLite/FS precisam fornecer a
durabilidade esperada; não é prometida tolerância a perda física de armazenamento.

## Receitas de produtos

- Avisaqui: política vigente encerrada não é aberta por este código. Declaração
  de exportação aprovada e pin do script continuam obrigatórios. Fixtures Git
  completas cobrem preparo, recibo, autorização e CAS local sem pacote real.
- Artesão: `/api/prepare` continua bloqueado até executor externo autorizado.
  `artesao_isolated_executor.py` mantém a receita oficial e não entra no runtime.
  `artesao_artifacts.py` revalida sua saída com recibo oficial do mesmo SHA,
  checksums completos dos pacotes, hashes dos archives/imagem, proveniência,
  schemas e evidências distintas HA `linux/arm64` e Debian `linux/amd64`.
  O builder chama esse verificador antes de concluir. Ele também pode ser usado
  offline para receber saída do builder. Não extrai archives nem executa comandos.
  Testes com metadados sintéticos não provam build real ou autoridade. Não há
  transporte GitHub para o pacote dual nem liberação automática por grant genérico.

## Validação e próxima homologação

`validate_offline.py --output DIRETORIO_NOVO` executa suítes offline com ambiente
sem credenciais herdadas e preserva logs, exit codes e hashes de código/config.
Na fonte privada inclui a suíte do repositório; no catálogo executa a do add-on.
O Dockerfile executa a suíte completa na etapa de validação e uma segunda rodada
workspace_sync como usuário não root. O runtime não recebe publicador, builder,
verificador dual ou testes. A CA do proxy do laboratório pode ser fornecida por
BuildKit secret `build_ca`; TLS não é desligado e a CA não vai à imagem final.

Publicação de uma RC do Runner no catálogo não habilita pacotes dos produtos.
Autoridade e isolamento reais de publish continuam NO-GO específico; o produto
permanece parcialmente concluído para esse uso. Build/atualização e homologação
no HA dependem do proprietário. Não há Actions, mudanças em servidores, Docker
de produção, reabertura de pacote, instalação ou rotação de segredos neste fluxo.


## M054 — prova declarativa em workspace Git real (24/11/2026)

A RC30 instalada contém o exportador declarativo e o servidor que o integra; os blobs de `server.py`, `declarative_export.py` e `projects/avisaqui.json` da distribuição coincidem com a fonte RC30 consultada. Os logs da RC30 comprovam somente o probe sintético: cinco blobs Git de fixture; nenhum workspace real foi exercitado.

A RC31 acrescenta `declarative_workspace_probe.py`, chamado depois de uma sincronização de workspace concluída. Ele:
- valida o SHA de origem e o SHA da distribuição já sincronizados;
- aplica somente as regras declarativas confiáveis do perfil do Runner;
- confere o blob pinado do exportador e o contrato CI, quando aplicável;
- copia blobs Git reais para uma pasta temporária, verifica SHA-256 e gera proveniência temporária;
- remove a pasta temporária ao terminar, sem tocar nos checkouts ou na área persistente de preparações.

**Limite importante:** o probe não é uma preparação de release nem substitui a elegibilidade do pacote. Ele não cria recibo, não marca testes do produto como PASS, não abre pacote, não publica e não contorna os gates de versão/branch/proveniência. A API `/api/prepare-declarative` continua exigindo preflight elegível.

**Evidência de política observada no workspace Avisaqui:** o perfil está configurado com regras declarativas, mas a política do pacote atual está em `release_candidate_preparing`, enquanto o validador e o preflight exigem `active_package.status == "open"`; além disso, a proveniência pública já declara a versão candidata `0.1.20-rc.12` com origem `0da93dba4a6fff67eb2944f5c760346d8f3619d5`, enquanto o HEAD de desenvolvimento consultado é `10b21c4ddaeb778daab78d8a64c9f4b35290465c`. Isso explica por que a preparação real durável permanece bloqueada por política; não é falha do Bubblewrap nem da exportação declarativa. Nenhuma política de produto foi alterada.

**Fonte RC31:** commit `31177332f9c5d3c3e34be77839f3171a7e1643f5` (branch `desenvolvimento`). **Validação:** sintaxe do novo helper e da nova suíte conferida por análise AST; testes unitários completos, build Docker/ARM64 e execução do probe no Home Assistant ainda NÃO executados. Dependem de publicar e atualizar a RC31 pela esteira oficial. Não declarar PASS antes desses logs.


## M056 — resultado da homologação técnica inicial da RC31 (24/11/2026)

- PR #10 promoveu `desenvolvimento` para `release-candidate`; merge commit `1cd8db2134d4ddae7ab8cb5ee5d483b97df4a9da`.
- Publicação no catálogo: commit `e501c858f7ed9f91746e1418aa40d139fa455dd2`; somente nove paths em `factory-runner/`. Proveniência integral de 99 arquivos; commit de atualização da evidência `a2a6fa8ae4d1f0cc74f7b59404b525234489567a`.
- Supervisor confirmou `App successfully updated`; versão instalada `0.1.0-rc.31`, estado `started`, sem atualização pendente.
- Dockerfile executa bash -n, py_compile, suíte unittest completa `test_factory_runner_*.py` e rodadas não-root de workspace sync/E2E. O build/validação foi concluído para a instalação RC31.
- Log real: `[DECLARATIVE-REAL-PROBE] PASS: project=avisaqui files=136 bytes=1000106 provenance_files=135 method=real_git_blobs_no_script`.
- E2E sintético PASS continua explicitamente sem workspaces reais; não confundir com o probe acima.
- Opções do add-on preservadas. Publisher permanece bloqueado; publicação de produtos desativada.
- Bubblewrap continua bloqueado no ambiente, sem bypass. A prova declarativa usa Git blobs e não depende dele.
- A política de pacote Avisaqui permanece fechada; não alterar status ou contornar preflight.
- Estado: **RC31 PUBLICADA, INSTALADA, INICIADA; BUILD/TESTES DO DOCKERFILE E PROBE DECLARATIVO REAL PASS; HOMOLOGAÇÃO FUNCIONAL AMPLA PENDENTE.**


## M057 — roadmap de conclusão e início da Etapa 1 (24/11/2026)

Roadmap aprovado pelo proprietário: `docs/ROADMAP-CONCLUSAO-001.md`. Sequência: (1) fechar funcionalmente RC31; (2) implementar FR-EXEC-001 e inteligência de testes; (3) concluir orquestração; (4) integrar Publisher e controles; (5) implementar isolamento de código não confiável por Bubblewrap ou alternativa comprovada; (6) homologação integral multiprojeto. O isolamento é a última etapa de construção, mas seu contrato de integração é respeitado desde o início. Código não confiável permanece bloqueado até a etapa 5.

**Etapa 1 em andamento.** Baseline HA confirmada: RC31 instalada/iniciada, sem update pendente; dois workspaces sincronizados; auditoria sanitizada PASS; release-plan executado para Avisaqui e Artesão com bloqueios de política preservados; probe declarativo real PASS (136 arquivos); API loopback authenticated/worker read-only/publication disabled. Publisher continua DORMANT. Bubblewrap/Landlock seguem sem isolamento aprovado. Não foram alteradas opções, dados, workspaces ou políticas.

Limites: testes HTTP autenticados sintéticos e cadeia de testes Dockerfile concluídos no build RC31. A chamada autenticada direta aos endpoints do runtime não foi repetida nesta auditoria porque o Bearer está protegido e a porta 9876 não está publicada; não expor token nem abrir porta para contornar. Persistência após reinício ainda precisa de evidência dirigida. Estado da Etapa 1: **PARCIALMENTE VALIDADA / EM EXECUÇÃO**. Ver matriz e próxima ação em `docs/CONTINUIDADE-ATIVA.md`, seção M057.


## M058 — matriz de rotas e persistência (24/11/2026)

Revisão de código da Etapa 1 concluída. Todas as rotas API exigem Bearer e o listener é loopback `127.0.0.1:9876`, sem porta publicada. GET status/projects/operations/publication-status são leitura; POST preflight/release-plan são leitura de política com auditoria; worker aceita apenas diagnose/profile/preflight; prepare/declarative pode gravar bundle local/recibo somente se elegível; preview/propose são fases distintas; publish/reconcile exigem Publisher e grant independente; fechar-pacote/corrigir-issue permanecem bloqueados.

Persistência: auditoria append sanitizada com `O_NOFOLLOW`, arquivo regular, link-count 1 e modo 0600; preparação declarativa usa identidade determinística, staging, recibo, rename atômico e retry idempotente. Testes cobrem idempotência e segurança. **Não há fsync explícito em `record()` e a persistência do volume real após reinício ainda não foi demonstrada.**

Tentativa MCP de API direta falhou por isolamento de rede (9876 não publicada); Ingress 8099 negou o peer MCP como esperado. Não abrir porta nem expor token. Próxima implementação de Etapa 1: probe autenticado interno de loopback para o processo vivo, limitado a endpoints read-only/preflight, sem chamar prepare/publish. Estado: **PARCIAL / EM EXECUÇÃO**.


## M059 — probe autenticado do processo vivo (RC32)

RC32 adiciona `runtime_api_probe.py`, executado em processo separado dentro do contêiner após o start da API. Usa o Bearer já provisionado no ambiente, sem imprimi-lo e sem passar tokens GitHub/Supervisor ao processo. Exercita autenticação negativa, status, projetos, status de publicação, auditoria sanitizada e preflight/release-plan dos workspaces reais. Não chama prepare, preview, propose, publish ou reconcile; não executa código de projeto e não abre porta.

O probe aguarda workspace sync/lock, é não bloqueante para o serviço e falha sem derrubar a API. Dockerfile inclui py_compile, testes e cópia para runtime. Fonte: `desenvolvimento`, RC32, commits `8e06905d53436afecec0b2e41eac495fc4040727` e `863377a4baa5b0e843a302619abfe4b31e4e6dfc`.

**Ainda não validado no HA:** build ARM64, suíte Dockerfile e log `[API-PROBE]`. Próxima ação autorizada: promoção/publicação isolada RC32 e atualização da instalação existente pelo Supervisor, preservando opções/dados.


## M060 — RC32 e correção RC33 do probe live API

RC32 (`0.1.0-rc.32`) foi instalada/iniciada no Supervisor; build/validação do Dockerfile concluiu. O probe não passou: log `[API-PROBE] BLOCKED: workspace_sync_in_progress`. Diagnóstico: `python3 -I` não inclui `/app` no `sys.path`, então os imports confiáveis `server`/ `workspace_sync` falhavam dentro do retry.

RC33 (`0.1.0-rc.33`), commit `d09aff0a1fc6641ec1e0ad087200acc501d8ed5e`, adiciona somente o caminho fixo `/app` ao `sys.path`, marcador `[API-PROBE] START`, teste de regressão e README vigente. Ainda não publicada/instalada. Próximo passo: promover/publicar RC33 e validar build/testes/probe real no Supervisor. Não abrir porta, não expor Bearer e não ativar Publisher.


## M061 — falha de build RC33 e correção RC34

RC33 falhou no build ARM64 do Supervisor (exit code 1) durante a suíte unitária: `runtime_api_probe.py` consultava `sys.path` sem importar `sys`. `py_compile` passou, mas a suíte registrou `FAILED (errors=1, skipped=28)`. RC33 não foi instalada; RC32 permaneceu `started`.

RC34 (`0.1.0-rc.34`), commit `7e95296dd4c92aff36a1deb74d738e23716e845a`, adiciona `import sys`. O teste de regressão de import path permanece. Ainda pendentes promoção, publicação, build/testes no Supervisor e log real `[API-PROBE] PASS`.


## M062 — RC34: API viva e preflight real PASS

Supervisor confirmou RC34 `started`, build ARM64 concluído e atualização bem-sucedida. Log: `[API-PROBE] PASS: authenticated live loopback API; projects=2 preflight_checks=2 audited_read_only_operations=4 publication=disabled`. Avisaqui bloqueado por 3 códigos de política e Artesão por 7; ambos retornaram `blocked_by_project_policy`, sem alterar gates. Nenhuma rota prepare/publish/reconcile foi chamada. API permanece loopback-only, worker read-only, Publisher DORMANT.

RC35 em desenvolvimento acrescenta medição de eventos de auditoria anteriores ao timestamp do boot atual para provar persistência após update/restart normal. Não comprova durabilidade contra queda abrupta; `record()` ainda não faz fsync explícito. Etapa 1 permanece aberta até RC35.


## M103 — prova de CPU por processo e overflow live (25/11/2026)

RC60 candidata mantém o protótipo stream-only da RC59 e acrescenta: (1) teste RLIMIT_CPU em filho sintético descartável, com soft=1 s/hard=2 s e timeout externo; (2) chamada de startup ao cenário `bounded_stream_probe.py overflow 128`, que deve registrar `status=blocked_output_limit`, `output_limit_enforced=true` e `stdout_bytes=129`, seguida de limpeza tmpfs. O cenário safe continua separado e `output_limit_enforced=false` é esperado nele. Não executa código de projeto. Esses ensaios não comprovam orçamento agregado de CPU/memória nem quota por job; cgroup v2 segue read-only/sem delegação, Publisher DORMANT e `sandbox_export` fail-closed.


### Resultado operacional M103 — RC60 (25/11/2026)

Supervisor registrou build ARM64 concluído às 15:37:32 e atualização bem-sucedida às 15:37:35. Instalada/started; `update_available=false`. O primeiro pedido MCP de update expirou em conflito com job group ocupado, mas o build iniciado concluiu; não houve repetição cega. Logs reais: RLIMIT_CPU `enforced=true`; overflow `stdout_bytes=129`, `child_signal=9`, `child_killed_for_output_limit=true`, `tmpfs_cleanup_restored=true`. Opções não foram enviadas para alteração; `protected=true`, `privileged=[]`, `full_access=false`, AppArmor default. Nenhum backup da RC59 foi criado. Nenhum código de projeto executado.


## M104 — validador de archive stream

RC61 adiciona `archive_stream.py` como componente confiável de validação/extração de tar stream. O contrato exige allowlist exata, paths obrigatórios, budgets de archive/file/total/count/depth/time, rejeição de links/special files/PAX/sparse/traversal e staging atômico. O módulo não executa conteúdo e ainda não está conectado ao `sandbox_export`; o executor permanece fail-closed. Build ARM64 e suíte Dockerfile pendentes.


## M104 — resultado do primeiro build ARM64 RC61 (25/11/2026)

- RC61 (0.1.0-rc.61) está publicada em mmcromero/hassio-addons:main/factory-runner/. Proveniência aponta para factory-runner:release-candidate SHA 1a61dff8669e3df1184d6791c27742960751d750; comparação remota confirmou 123/123 blobs da origem correspondentes no catálogo; RC4-VALIDACAO.md e SOURCE_PROVENANCE.json preservados; nenhum caminho fora de factory-runner/ foi alterado.
- Atualização no Supervisor foi tentada duas vezes (inícios de build às 16:05 e 16:10 BRT). Ambas terminaram com falha no estágio de validação do Dockerfile, comando composto de bash -n, py_compile e unittest discover, exit code 1. Supervisor reportou erro genérico ao construir a imagem; os logs disponíveis não expõem a saída do teste específico que falhou. Portanto, não classificar o validador nem a suíte como PASS ou FAIL individual até obter a saída detalhada.
- O journal do host registra moby.buildkit Solve com exit code 1 e healthcheck da sessão BuildKit 'only one connection allowed'. O mesmo healthcheck também aparece após o build RC60 que concluiu com sucesso; isoladamente, ele não prova a causa da falha RC61.
- Estado verificado após as tentativas: RC60 (0.1.0-rc.60) permanece started; version_latest=0.1.0-rc.61; update_available=true. protected=true, privileged=[], full_access=false, AppArmor default. Opções não foram alteradas. Nenhum backup da RC60 foi criado. Nenhum código de projeto foi executado.
- Próximo passo: obter diagnóstico do erro do estágio de validação antes de qualquer nova atualização. Separar a execução de py_compile, suíte test_factory_runner_*.py, workspace_sync e E2E em etapas de build identificáveis, preservando o mesmo conjunto de testes e a política fail-closed; então corrigir somente a causa comprovada e repetir o build ARM64 no Supervisor.
- Gate permanece: safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed; quota por job, cgroup delegado e runtime genérico completo não comprovados.


**Gate de promoção M116:** comparação de `release-candidate` (HEAD `f7deb5a7e321801de72cfb42f4c320c426071126`) com `desenvolvimento`: 237 commits exclusivos em desenvolvimento, 283 commits exclusivos na RC e merge-base `fec0fe9cf7951345cbefada12cc239c87b483a5b`; nenhum PR de promoção aberto. Não publicar RC69 enquanto a ancestralidade obrigatória não for reconciliada sem perda de histórico. Não usar merge geral às cegas, reset ou force-push.

**Atualização M141 — 26/11/2026:** o probe de cgroup também calcula o teto herdado de swap em cada ancestral visível; `hierarchy_complete` agora exige CPU/RAM/swap/PIDs parseáveis em todos eles e o gate `delegation_candidate` depende dessa completude. A matriz AppArmor M121 foi corrigida: `rprivate` e `tmpfs` são fragmentos não aprovados fora do child profile efetivo; unmount é apenas regra candidata. Testes M141 foram adicionados, mas não executados. Nenhuma mudança no HA ou ativação de perfil.

**Atualização M142 — 26/11/2026:** o cleanup do scratch no processo pai agora compara `lstat()` inicial/final (tipo, UID, modo 0700, device/inode), recusa caminho substituído ou mountpoint, usa `rmdir()` e confirma ausência. Testes de regressão adicionados, ainda NÃO EXECUTADOS por M006/P0. A matriz M121 agora documenta explicitamente controles positivos/negativos de cleanup e separa AppArmor de invariantes do helper/pai.

**Atualização M144 — 26/11/2026:** suíte de cleanup ganhou regressões negativas para mountpoint ainda ativo e diretório não vazio; ambos devem permanecer sem remoção e bloquear o status disponível. Commit de teste `81a85d6aecaf6660cc48f38f15dbbbb049c6009b`. Não executado por M006/P0.

**Atualização M145 — 26/11/2026:** o helper C agora usa `lstat()` após unmount para confirmar o diretório real restaurado por device/inode, sem seguir symlink. Build e teste C pendentes por M006/P0. Commit `ee8a2f51ab5e0617fb12c8cb9e4b3f15d7ec465b`.

**Atualização M146 — 26/11/2026:** cleanup verifica mountpoint antes da identidade do inode, para classificar corretamente `parent_mount_leaked=true` quando houver mount inesperado. Teste existente cobre o caso; não executado por M006/P0. Commit `c1b3b34019f1499e27404e5944c74f8fd3f2849c`.

**Atualização M148 — 26/11/2026:** helper C lê `statvfs().f_flag` após montar tmpfs e exige `ST_NOSUID|ST_NODEV|ST_NOEXEC`; o classificador Python exige `tmpfs_flags_verified` e os testes cobrem flag ausente. Build C e testes NÃO EXECUTADOS por M006/P0. Nenhuma ativação AppArmor.

**Atualização M150 — 26/11/2026:** corrigido falso negativo no preflight cgroup: `delegation_candidate` agora só é calculado depois de inventariar todos os ancestrais e preencher `hierarchy_complete`. Testes exigem hierarquia completa para candidato RW e bloqueiam ancestral sem `memory.swap.max`. Não executados por M006/P0.

**Atualização M155 — 26/11/2026:** investigação na tag exata Supervisor 2026.11.0 confirmou que a configuração de apps não oferece subtree cgroup delegation/cgroupfs RW nem quotas CPU/RAM/PIDs por job. `device_cgroup_rules` cobre somente dispositivos; `privileged` ampliaria capabilities. A alternativa cgroup está BLOCKED nesta instalação protegida. `sandbox_export.py` permanece fail-closed; não usar SYS_ADMIN/full_access/Docker socket/host changes.

**Atualização M157 — 26/11/2026:** revisão de quotas agregadas concluída: cgroup delegation bloqueada pela plataforma; RLIMIT+UID, seccomp sem processos, tmpfs e fila serial não são equivalentes para builds/testes genéricos. Não há executor equivalente suportado no escopo M006/P0. Execução genérica continua bloqueada por `_require_aggregate_isolation()`.

**Atualização M160 — 26/11/2026:** regra de recepção SIGKILL do child usa agora o peer literal exato `45c28620_fabrica_software`, confirmado pelo slug do app no Supervisor 2026.11.0 e pelo `adjust_profile()` que reescreve apenas o nome do perfil pai. Wildcard removido; correspondência exata sob parser 3.1.7/enforce ainda pendente.
