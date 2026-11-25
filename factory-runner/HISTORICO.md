# HISTÓRICO DE MANUTENÇÃO — Factory Runner

**Regra:** histórico aditivo, com data, repositório, branch, SHA, escopo, evidência e situação. Nunca inserir credenciais ou copiar logs privados. Para trabalhos futuros, acrescentar registros em ordem cronológica e atualizar `CONTINUIDADE.md` com **somente** o ponto atual.

## 19/11/2026 — Diagnóstico de namespace e desenvolvimento da RC2

- Teste real no terminal SSH do HA: `unshare --user --map-root-user --pid --fork --net /bin/true` terminou `RESULTADO=0`. **Não valida o contexto do add-on**.
- Diagnóstico `factory-runner/runtime_probe.py` criado na distribuição, integrado a `run.sh` e `Dockerfile`. Commits da branch de desenvolvimento pública: `92b08a16`, `6e2ce218`, `44fc973a`.
- O probe verifica namespaces Bubblewrap sem raiz, com `/bin/true`, sem porta pública ou mutação do host. Resultado no Raspberry ainda não coletado.
- Os testes Python e builds realizados anteriormente no ambiente do desenvolvedor pertenciam a SHAs anteriores; **não tratar como aprovação automática do SHA do diagnóstico novo**.

## 19/11/2026 — Incidente de publicação, causa e correção

- Tentativas erradas: branches de distribuição `release/factory-runner-rc2-ha` e `factory-runner-rc2-ha` foram criadas para teste; o add-on existente permaneceu vinculado à loja original `hassio-addons:main`, que continuava na RC1.
- Norma revisada: GOV-STD-001 P0, GOV-BLK-002 v0.3, `hassio-addons/AGENTS.md` e `CONTRIBUTING.md`. Não impor build ARM64 externo/Actions como bloqueio genérico. Repositório de distribuição publica somente a pasta do add-on autorizado na `main`.
- Correção: publicação isolada de 19 arquivos em `hassio-addons:main/factory-runner/`, commit **`8677c7ee61f9020dbdbc509e97d2217faf36b73a`**. Diff remoto contra `d7abb0bc` conferido: todos os caminhos alterados dentro de `factory-runner/`; `config.yaml` mostra `0.1.0-rc.2`.
- Registro GitHub da publicação: [Issue #2, comentário 7016078579](https://github.com/mmcromero/orquestrador-projetos-base/issues/2#issuecomment-7016078579).
- Situação: PUBLICADO confirmado. INSTALADO relatado pelo proprietário posteriormente. Build, startup, isolamento e função **ainda não homologados**.

## 19/11/2026 — Documentação de continuidade (este lote)

- Repositório privado de origem: `mmcromero/orquestrador-projetos-base`, branch `feat/factory-runner-esteira-001`, diretório `factory-runner-add-on/`.
- Documentos criados na raiz do módulo: `README.md` (orientação), `CONTINUIDADE.md` (situação e próxima ação) e `HISTORICO.md` (registro cronológico).
- Situação relevante identificada: origem privada ainda não contém todos os módulos executados na distribuição RC2. É pendência de sincronização, **não autorização para sobrescrever a distribuição**.
- Nenhum teste adicional realizado no Home Assistant nesta etapa, por solicitação expressa do proprietário.

## Formulário de registro para próximos lotes

```text
Data/hora e responsável:
Demanda/Issue existente:
Fonte (repo, branch, SHA antes/depois):
Distribuição (repo, branch, SHA antes/depois), quando aplicável:
Objetivo e escopo autorizado:
Arquivos alterados:
Testes efetivamente executados (ambiente/comando/resultado):
Testes não executados e justificativa:
Publicação: NÃO / PUBLICADA (SHA)
Instalação HA: NÃO / RELATADA / CONFIRMADA
Homologação: NÃO / PARCIAL / CONFIRMADA COM EVIDÊNCIA
Riscos, impedimentos e alternativas:
Próxima ação objetiva e responsável:
```

## 19/11/2026 — Arquitetura hibrida: desenvolvimento do worker controlado

- **Autorizacao:** proprietario aprovou arquitetua hibrida em branch, worker de tarefas controladas e investigacao limitada do AppArmor; nao autorizou publicar/instalar nem alterar outros add-ons.
- **Fonte:** `mmcromero/orquestrador-projetos-base:feat/factory-runner-esteira-001/factory-runner-add-on/`. Base RC2 sincronizada por arquivos a partir de `hassio-addons:main/factory-runner/` antes das mudancas do worker; a configuracao antiga privada `1.0.0` foi substituida pelo manifesto real `0.1.0-rc.2` da distribuicao, apenas na fonte.
- **Implementacao:** `controlled_worker.py` (tarefas `diagnose`, `profile`, `preflight`, sem root, sem shell e com ambiente sem token), `server.py` (API autenticada de lista fechada, validacao e auditoria), `run.sh` (diagnostico no log) e `Dockerfile` (inclusao no build/teste). Testes especificos adicionados em `tests/test_factory_runner_controlled_worker.py`.
- **Teste executado:** suite local independente de regras do worker, Python 3.13, `python3 -m unittest discover -s /mnt/data/factoryrunner_lote/tests -p 'test_factory_runner_*.py' -q`, resultado 7/7 PASS; `python3 -m py_compile controlled_worker.py` local PASS. Esta suite foi executada contra prototipo de mesmo nucleo de worker; **nao equivale a teste da arvore integrada, Docker, ARM64 ou HA**.
- **Nao executado:** nova suite de integracao HTTP da fonte, validação Docker, probe e limitacao no Raspberry, cgroup/quota, revisão independente de seguranca, CI, homologacao. A proxima instalacao nao esta autorizada neste lote.
- **Investigacao AppArmor limitada:** codigo oficial do Supervisor confirma seccomp unconfined e o uso de AppArmor; negacao observada no bwrap continua nao atribuida a uma regra especifica por auditoria local. Diagnostico adicional usa apenas /proc da propria tarefa, sem mudar controles. Fonte: `CONTROLLED-WORKER.md`.
- **Estado:** DESENVOLVIDO NA BRANCH; NAO PUBLICADO/NAO INSTALADO. Publicacao e execucao de codigo nao confiavel bloqueadas. Proximo responsavel: Tech Lead/Seguranca por revisão; DEV por testes integrados e ajustes, sem repetir host SSH.

## 19/11/2026 — Validação dirigida e candidata RC3 privada (sem publicar)

- **Candidata preparada:** manifesto `factory-runner-add-on/config.yaml` passou de `0.1.0-rc.2` para `0.1.0-rc.3` SOMENTE na fonte privada. `hassio-addons:main/factory-runner/config.yaml` permanece RC2. Nenhum deploy/instalação.
- **Testes locais efetivamente executados:** 7 testes do núcleo `controlled_worker` (PASS); 12 ensaios HTTP de `do_POST` usando trecho copiado e conferido por comprimento/FNV32 com a branch (PASS); 3 cenários de falha do lançador com trecho copiado e conferido com a branch (PASS). Diagnóstico executado sob UID 65534 no laboratório e operação `publish` rejeitada. Os ensaios de trecho **não são testes integrados da árvore Git completa**.
- **Regressões versionadas:** suite `tests/test_factory_runner_controlled_worker.py` agora contém 10 testes, incluindo saída inválida/grande, timeout e sinal de término do grupo, e sanitização do ambiente filho. Execução da suite **integrada do commit Git** ainda pendente, não registrar como PASS.
- **Observabilidade:** `run.sh` prefixa diagnóstico com `[WORKER]`; `server.py` registra `[API] READY` somente depois de escuta local aberta. A falha Bubblewrap deve continuar sinalizada em `[ISOLATION] BLOCKED` caso a política do HA não tenha mudado.
- **Segurança:** nenhuma permissão, porta, imagem de execução ou política AppArmor foi afrouxada. Workspaces privados, exportação e publicação permanecem protegidos. Falta build real do Dockerfile em ARM64 e avaliação de segurança no Home Assistant antes de aceitar homologação.
- **Próximo passo:** congelar candidato para revisão do lote, conferir todos os paths alterados e controles P0. Publicação do RC3 só após autorização específica; instalação somente após publicação correta.

## 19/11/2026 — Correção final, publicação controlada e verificação da RC3

- **Autorização do proprietário:** concluir revisão técnica e testes proporcionais; publicar a RC3 **somente** na pasta `factory-runner/` da `main` do catálogo, sem Actions, sem alterar outros add-ons, sem instalar no Raspberry.
- **Defeitos reais corrigidos antes do corte:** (1) `Dockerfile` copiava `controlled_worker.py` para a fase de validação, mas omitia o arquivo da imagem final; corrigido o `COPY --from=validation` e adicionado `test -r` no runtime. (2) `run.sh` exportava o token do serviço e o herdava no diagnóstico; agora `runtime_probe.py` e `controlled_worker.py --task diagnose` iniciam via `env -i`. O servidor autenticado permanece com o token.
- **Testes realmente executados:** 7/7 testes locais do núcleo Python, 3/3 do lançador e 12/12 da rota HTTP reproduzida de trecho com hash idêntico à fonte. Revisão estática final de 13 arquivos e hashes dos trechos `do_POST` / lançador: PASS. O Dockerfile compila Python e roda `unittest discover` durante o build real; build/HA ainda **não executados** neste lote.
- **Publicação:** blobs das alterações gravados no catálogo, nova árvore construída sobre `8a568f634378f50aa997fe32c7509ece5a08166f` e diff comparado: **9 caminhos alterados**, todos em `factory-runner/`; árvore final `1373b1b8aad25e5ecdcfa7bbc1f5dd957ea32fc7`. Commit `db77d23fcfef78535240577388b2a654a0cb2d8a` aplicado na `main` por atualização condicional com HEAD anterior `45993490905eefe760278847f5b295aaac8cc1fc`; sem force.
- **Verificação remota:** `hassio-addons:main` passou a `db77d23fcfef78535240577388b2a654a0cb2d8a`; manifesto `0.1.0-rc.3`, arquivo `controlled_worker.py` presente, Dockerfile com cópia nos dois estágios, `run.sh` com `env -i`. Lista de arquivos do commit confirma apenas 9 caminhos `factory-runner/`. GitHub Actions não foi acionado manualmente; consulta de workflow runs associados ao commit retornou 0.
- **Estado final deste lote:** **PUBLICADA E VERIFICADA NO GITHUB**, **NÃO INSTALADA, NÃO HOMOLOGADA no Home Assistant**. Bubblewrap continua fail-closed sem mudança de política; release destinada a testar camada read-only e identificar perfil AppArmor efetivo pelos logs. Próxima ação: proprietário atualizar apenas Factory Runner no HA, enviar startup com `[ISOLATION]`, `[WORKER]`, `[API] READY`; DEV retoma a etapa afetada se falhar.

## 19/11/2026 — Recebimento de logs RC3 reais e causa provável do Bubblewrap

- **HA testado pelo operador:** startup da versão publicada RC3; worker `diagnose` retornou `ok: true` / UID 100 / `CapEff=0000000000000000` / `CapBnd=00000000a80425fb` / `NoNewPrivs=0` / `Seccomp=0` / `apparmor=docker-default (enforce)`. API reportou `[API] READY: loopback-only; authenticated; worker read-only; publication disabled`. **Não significa que rota HTTP foi exercida por cliente**.
- **Bloqueio permanece:** `bwrap: Failed to make / slave: Permission denied`; exportador não é executado sem sandbox. Nenhum `SYS_ADMIN`, `apparmor:false`, Docker socket ou política modificada.
- **Causa provável investigada:** regra `deny mount,` presente na documentação oficial do Docker no perfil padrão, compatível com erro; sem registro de audit específico, a origem exata da EPERM ainda não foi comprovada. Docs: https://docs.docker.com/engine/security/apparmor/
- **Alternativas:** perfil AppArmor específico para o add-on conforme documentação oficial do HA (não preparado/publicado sem revisão de segurança), ou estudo de Landlock LSM sem montagens — ABI e disponibilidade no Raspberry ainda não confirmadas. Requer isolamento de arquivos/rede e limites agregados antes de scripts de projetos. Fontes: https://contributors.home-assistant.io/apps/guides/security/ e https://www.kernel.org/doc/html/latest/userspace-api/landlock.html
- **Estado:** RC3 INICIADA / DIAGNÓSTICO CONFIRMADO; preparar pacote e execução não confiável BLOQUEADOS. Registro: Issue #2 comentário 7021054127. `CONTINUIDADE.md` atualizada com a próxima ação técnica. **Proprietário não precisa executar nova rotina de SSH nem atualizar novamente a RC3.**

## 19/11/2026 — Lote de investigação Landlock (branch privada RC4, sem publicação)

- **Autorização existente:** continuar arquitetura híbrida e investigação limitada, preservando segurança e outros add-ons; nenhuma autorização nova para publicação ou instalação da RC4.
- **Norma e fonte:** consultada documentação oficial do Linux Landlock e syscall `landlock_create_ruleset` 444 em x86_64/aarch64; ABI para filesystem 1+, TCP 4+, escopo IPC 6+, UDP 10+. Disponibilidade concreta em HA 6.18 NÃO foi comprovada.
- **Implementação:** criado `factory-runner-add-on/landlock_probe.py`, integrando consulta não destrutiva da ABI ao `controlled_worker.py --task diagnose`. Nenhum `landlock_restrict_self`, `prctl`, `unshare`, comando arbitrário, token, mount ou alteração host. Campos de aprovação permanecem sempre falsos.
- **Build:** `Dockerfile` inclui `landlock_probe.py` em validação, compilação e imagem final; regressões `tests/test_factory_runner_landlock_probe.py` (11 casos), além de asserções de segurança no teste de diagnóstico do worker.
- **Teste efetivamente executado:** módulo `landlock_probe.py` idêntico byte a byte à fonte remota (hash Git conferido: `fc66089552725137ee244d2d869b1331e2452c4e`) passou 11/11 casos de versão ABI, indisponibilidade, permissões e erros no laboratório. Execução direta como usuário `nobody` no laboratório retornou `syscall_unavailable` (ENOSYS), sem evidência sobre o HA; `py_compile` PASS local. `unittest` completo do checkout integrado, Docker, ARM64 e HA para RC4 não executados.
- **Arquitetura:** Landlock não é substituto único para Bubblewrap; sem prova de isolamento do código arbitrário e limites agregados, `/api/prepare` continua fail-closed. Recomendado estudar exportação determinística por metadados confiáveis no Runner como alternativa para tarefas mecânicas; execução de scripts externos permanece separada/bloqueada. Documento `LANDLOCK-ESTUDO-001.md`.
- **Versionamento:** `config.yaml` na origem privada foi marcado `0.1.0-rc.4`, sem tag nem publicação. `hassio-addons:main` permanece RC3, previamente instalada pelo proprietário. **NÃO PUBLICADA / NÃO INSTALADA** a RC4.

## 19/11/2026 — Prova de conceito de exportação determinística sem código do projeto

- **Fonte exata conferida:** `pager-virtual:desenvolvimento/scripts/export-distribution.py`, blob `e67c816405707545b21b0e6863814ada7b26d0f1`, coincide com o hash fixado no perfil do Runner. O exportador faz majoritariamente `git ls-tree` + `git show`, mapeamento/cópia de blobs Git, SHA-256 e proveniência; executa operações especiais em workflow/patch de CI que NÃO podem ser omitidas se houver requisito de equivalência.
- **Implementado SOMENTE na fonte privada:** `trusted_export_plan.py`, função pura de planejamento: aceita entradas Git sintéticas e esquema genérico de caminhos, valida destinos/tipos/metadados/limites e devolve mapa; não lê Git, não grava, não executa comandos/scripts nem publica. `tests/test_factory_runner_trusted_export_plan.py` contém **13 testes** de caminhos, links simbólicos, submódulos, duplicatas e orçamento.
- **Testes realmente executados:** 13/13 PASS no laboratório Python; hashes dos blobs de ambos arquivos coincidiram byte a byte com os de GitHub (`trusted_export_plan.py`: `4c95c8c241625b544438a7b4fe7cfe8c6ccb3a94`, testes: `a9afc0d26fed4ab413b09f4168ec227ea8b7c5bf`). Os 11 casos da ABI Landlock também passaram no mesmo laboratório. **Ainda não executado:** teste integral da árvore privada/CI Docker/ARM64/HA, leitura de repositórios Git reais, exportação, equivalência com o exportador do Avisaqui e validação de limites sobre bytes reais.
- **Integração restrita:** Dockerfile inclui o planejador no estágio de validação e compila o módulo; **não copia ao runtime**. Sem endpoint novo, sem alteração de worker HA instalado, sem publicação da RC4 nem acesso a outros projetos. `/api/prepare` continua bloqueado pelo Bubblewrap.
- **Próximo responsável:** DEV/Tech Lead/Segurança devem comparar a especificação de mapeamento e de proveniência com a fonte oficial e testar limites reais antes de propor uma função de preparo. Publicação da RC4 depende de autorização separada.

## 19/11/2026 — Revisão dirigida da RC4 e comparação com Git real

- Não houve espera por novo comando do proprietário: executados testes do código de fonte privada no laboratório, com checagem dos blobs de `controlled_worker.py`, `landlock_probe.py` e `trusted_export_plan.py` contra GitHub.
- **38 testes locais PASS**: 7 do núcleo worker, 11 de Landlock, 13 de planejador declarativo, 7 de mapeamento com metadados selecionados reais do Avisaqui. O subprocesso `controlled_worker.py --task diagnose` como UID 65534 retornou `ok=true`, sem operar sobre código de projeto.
- Snapshot Git `mmcromero/pager-virtual:desenvolvimento` commit `a4b97c1d353e6111dc48933806f13c77d0dec6f9`, exportador `e67c816405707545b21b0e6863814ada7b26d0f1`: 320 entradas Git, 295 blobs, 135 arquivos comuns selecionados = 995.337 bytes, todos presentes e regulares; um workflow compartilhado exige gate separado. Política do pacote vigente neste corte: `closed_release_candidate_published_pending_homologation`, versão `0.1.20-rc.11`, portanto **não elegível para preparo operacional**.
- Teste novo versionado `tests/test_factory_runner_real_export_mapping.py` (7 casos, blob `0f2dcd27efaa7956a506e25c8cd21b1eaeaed48c`) e fixture de 295 blobs de metadados `tests/fixtures/avisaqui_git_tree_20261119.json` (sem bytes de conteúdo). A fixture completa e todo o Dockerfile não foram executados neste ambiente; confere-se estática e logicamente o mapeamento mas não se presume equivalência byte a byte nem execução de CI.
- Estado: **RC4 preparada tecnicamente para eventual publicação controlada de diagnóstico**, sem instalar/publicar neste atendimento. `/api/prepare` continua fail-closed; `hassio-addons:main` permanece RC3. Responsável DEV/Tech Lead; aprovação da publicação separada pertence ao proprietário.


## 24/11/2026 — M044: publicação e instalação da RC28

- Publicada a candidata RC28 em `hassio-addons:main/factory-runner/`, commit `303b313d8e5dffe2f50f53648eab312fd65eb870`, derivada da fonte `factory-runner:desenvolvimento` @ `db7b3331c1d2154062ded70dda27b2b8f8753b11`.
- Workflow de validação do catálogo: PASS. Supervisor atualizou o app existente para RC28, executou o build ARM64 e iniciou a versão com sucesso. Proveniência atualizada no commit `617828b45410e55c58530f8194295789b22faaec`.
- Opções, identidade, origem, token de escrita vazio, porta sem mapeamento e gate de publicação foram preservados.
- Cadastro real não repetido ainda: falta o proprietário submeter formulário novo pelo Ingress; RC28 deverá identificar a condição de eventual recusa sem registrar valores sensíveis.


## M075 — Etapa 3 iniciada: primeira implementação do orquestrador persistente (24/11/2026)

### Baseline e estado
- RC41 (0.1.0-rc.41) permanece instalada e started no Home Assistant. Não foi iniciada atualização, publicação de candidata nova ou execução de código dos produtos.
- Branch de trabalho: desenvolvimento; baseline M074 preservada. O código desta etapa ainda não está homologado.

### Implementação inicial
- Novo execution_orchestrator.py: fila persistente com worker único, estados/transições explícitos, idempotência por execution_id + digest, retry limitado, cancelamento, timeout, recuperação após reinício, histórico append-only e armazenamento privado 0700/0600 com flock/fsync.
- Novo execution_plan_worker.py: subprocesso fixo para o planejador confiável FR-EXEC-001, com allowlist de ambiente, sem tokens/credenciais, sem shell e sem execução de código de projeto.
- API autenticada adicionada: POST/GET /api/jobs, GET /api/jobs/{id}, POST cancel e retry. Consulta de plano continua em /api/executions/{id}.
- Probe de inicialização ampliado para submeter e acompanhar jobs nos dois workspaces, validar plano/recibo, filtros, idempotência e auditoria. Testes unitários e de API foram adicionados ao Dockerfile.
- Especificação: [ETAPA-3-ORQUESTRACAO-001](ETAPA-3-ORQUESTRACAO-001.md).

### Fronteiras preservadas
- O worker executa somente análise/planejamento read-only. Testes de produto permanecem NOT_EXECUTED; Bubblewrap/Landlock e execução de código não confiável continuam reservados à Etapa 5.
- Publisher DORMANT; prepare/package/homologate/publish/deploy/update/promote permanecem bloqueados; políticas, opções, credenciais, outros add-ons e serviços preservados.
- Build ARM64, suíte de testes e probe real da nova API ainda não foram executados. Não declarar PASS nesta fase.

### Roteamento de branch
- Três atualizações foram temporariamente direcionadas a main por desvio do conector. Detectado antes de PR/merge/release; os três arquivos foram removidos de main por commits corretivos e aplicados a desenvolvimento por commit Git Data com SHA-base explícito. Estado final dos arquivos de main conferido; histórico preservado, sem force-push. Nenhum pacote, instalação ou outro add-on foi alterado.

### Próximo gate
1. concluir revisão estática e regressões;
2. preparar e publicar a próxima RC somente em hassio-addons:main/factory-runner/, conforme M055;
3. solicitar autorização específica antes de atualizar o HA e executar a homologação ARM64/operacional.


## M078 — RC42 publicada; build ARM64 pendente (25/11/2026)

- PR #22 promoveu a implementação M076 para release-candidate; PR #23 registrou a promoção. Fonte final publicada: 38e2a7567da41d52e2c34d70c580ef21e2670fc0.
- Versão 0.1.0-rc.42 publicada somente em hassio-addons:main/factory-runner/.
- Commit do pacote: b17a8f01eb3a57f3a7327d94c29a19ab187a1fd3. Commit da proveniência: df1be943fc9a5cd48e3cc85888e4d1abf0445d2d. Tree SHA do pacote antes da atualização da proveniência: 467295c67d1721a1ccff902f2ccd567c1e22f498.
- Proveniência: 114 arquivos; hashes do pacote conferidos contra a fonte release-candidate. Alterados somente caminhos dentro de factory-runner/.
- Workflow de catálogo 45544117692 concluiu SUCCESS: manifests, registry, shell syntax e detecção de arquivos sensíveis PASS. O job de build-factory-runner-arm64 foi SKIPPED porque exige acionamento manual; não foi disparado.
- Supervisor store refresh confirmou version_latest 0.1.0-rc.42 e update_available=true. Versão instalada continua RC41 (0.1.0-rc.41), state started.
- A atualização do store também atualizou apenas metadados disponíveis do add-on Home Assistant MCP Dev (9.3.0.dev3723 → 9.3.0.dev3725); nenhum add-on foi instalado ou atualizado por esse refresh.
- Testes do Dockerfile, build ARM64 da RC42 e probe real de jobs ainda não executados. Nenhum código de Avisaqui/Artesão executado; Publisher DORMANT; sandbox Etapa 5 preservado.
- Próximo gate: autorização específica do proprietário para atualizar Factory Runner RC41 → RC42 no Supervisor e executar build/testes ARM64 e homologação da API de jobs.

## 25/11/2026 — M085: RC45 instalada e homologação restrita no Supervisor ARM64

- Autorização do proprietário: backup add-on-only da RC44 e atualização para RC45.
- Backup pré-update concluído: ID `e00cf68f`, nome `Factory Runner RC44 pre-update RC45 2026-11-25`, somente add-on `45c28620_fabrica_software`, versão `0.1.0-rc.44`, 1.218.263.040 bytes, sem falhas; sem HA config/DB e sem outros add-ons.
- Fonte `release-candidate` SHA `b9644bd53972af1eba1a785c036e5c358fcb3a2f`; catálogo `hassio-addons:main` SHA `2fb8e5a5a4f454935af427098a3997df2c16a6f8` no momento da atualização; RC45 `0.1.0-rc.45`.
- Supervisor build real `linux/arm64` iniciado 03:00:17 e concluído 03:03:38 BRT. Atualização confirmada 03:03:41; app `started`, versão RC45, sem update pendente.
- Dockerfile validation stage concluído: `bash -n`, `py_compile`, `unittest discover -p 'test_factory_runner_*.py'` (241 testes em 35,535 s) e comandos adicionais não-root para workspace-sync e E2E probe; build concluído sem erro.
- Inicialização RC45: API autenticada PASS (2 projetos, 10 operações read-only auditadas); E2E PASS (5 blobs Git sintéticos, publicação negada, sem workspaces reais); declarative preparation não-root/SHA-256 PASS.
- Cobertura de revogação de grant, UI/Ingress, Approval IPC/ACL e reserva foi incluída na suíte de 241 testes. Revogação ao vivo não exercitada: Publisher permanece DORMANT por falta de enrollment/runtime config pinada; nenhum grant foi emitido.
- Opções preservadas: `workspace_auto_prepare=false`, `workspace_sync_enabled=true`, Owner Ingress habilitado, runner/read tokens configurados; senha de enrollment e GitHub write token vazios. Nenhuma opção/credencial alterada.
- Avisaqui e Artesão continuam bloqueados pelas políticas específicas; nenhum código/teste desses projetos foi executado. Bubblewrap segue falhando no mount namespace e Landlock indisponível; Etapa 5 permanece obrigatória.
- Supervisor registrou aviso no encerramento da imagem antiga RC44: não tratou SIGTERM e saiu com código 143. Não impediu a atualização; RC45 iniciou normalmente. Reavaliar shutdown gracioso em manutenção futura.
- Estado: RC45 instalada e homologada para o escopo restrito de orquestração read-only e regressões automatizadas da Etapa 4; não libera Publisher nem publicação/execução de produtos.


## 25/11/2026 — M107: diagnóstico RC63 e correção da fixture para RC64

- **Ambiente:** Home Assistant OS / Raspberry Pi 4, add-on Factory Runner slug `45c28620_fabrica_software`.
- **Baseline confirmada após falha:** RC60 (`0.1.0-rc.60`) permanece `started`; catálogo reconhece RC63 e `update_available=true`. A chamada de atualização RC63 retornou HTTP 500; leitura posterior do estado e logs do Supervisor confirmou que o build falhou e RC60 não foi substituída.
- **Evidência:** Dockerfile RUN `python3 /app/tests/run_archive_stream_diagnostics.py` terminou exit code 77. Índice 27: `test_valid_archive_extracts_allowlisted_files_and_hashes`. Traceback `AttributeError: 'tuple' object has no attribute 'tobuf'`, em `tests/test_factory_runner_archive_stream.py:19`, durante `tar.addfile`.
- **Causa:** `dir_member("pkg")` já retorna `(TarInfo, None)`; o teste envolvia esse par em `(dir_member("pkg"), None)`, produzindo tupla aninhada. O defeito é da fixture, não do módulo `archive_stream.py`.
- **Correção:** branch `promote/rc64-m107-fix-archive-fixture`, baseada no HEAD RC M106 `0e9bf85aceeeb4e8be34e233ee227f127f1ad27d`. A linha foi corrigida para `dir_member("pkg")`; versão `0.1.0-rc.64`; changelog, README, continuidade e manual de release atualizados.
- **Commits:** teste `b96e72170b307261b46a236dee7e6a92931cb64a`; versão `6fbbbf1f71fd41b3ab124380fdca5de260a6c34d`; changelog `f7313bb9a320d2830f7d25e7a8c87761b78ce589`; continuidade `bf644e7028bc4cb9b7e46a5514b158d5cb014914`; Etapa 5 `3e5854873092633782918858fdbadd6ce450db50`; pipeline `345dfa8ff7df8b8887c386e0a27da9e33eff755a`.
- **Diff:** 7 arquivos; 1 linha de fixture alterada; nenhum módulo de runtime, Dockerfile, configuração de permissões, mounts, capabilities, AppArmor, rede ou credenciais alterado.
- **Testes:** o teste individual RC63 falhou conforme evidência acima. A correção RC64 ainda NÃO foi executada; diagnóstico individual e suíte completa aguardam build ARM64 no Supervisor.
- **Publicação/instalação:** RC64 ainda não publicada no catálogo nem instalada. Nenhum backup da RC60 criado, conforme regra do proprietário; opções/dados persistentes preservados.
- **Segurança:** nenhum código de projeto executado; `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.
- **Próxima ação:** revisão final, PR da branch para `release-candidate`, publicação isolada em `hassio-addons:main/factory-runner/` com proveniência/hash, refresh do catálogo e atualização RC64 pela autorização vigente. Confirmar build/testes/startup no Supervisor; não repetir RC63.


## 25/11/2026 — M108: prova sintética integrada chroot → archive stream (RC65)

- Baseline anterior: RC64 `0.1.0-rc.64` instalada/started. PR #55 integrado em `release-candidate`, merge `311db52c41915bab5e1e47dfe94fbeb32872afd0`.
- RC65 `0.1.0-rc.65` publicada somente em `hassio-addons:main/factory-runner/`; pacote commit `402241eee350057dc1bc218e4bd57926b7dfe758`; proveniência commit `f54d0ce0af40b2b344fdfe988d78b7985d241cba`. 126/126 blobs da fonte conferidos; 2 arquivos exclusivos do catálogo preservados; nenhum caminho externo a `factory-runner/` alterado.
- Supervisor ARM64: build iniciado 17:34:59.863 e concluído 17:38:33.321 BRT; atualização concluída e app iniciado 17:38:36.398. Estado final RC65 `started`, `update_available=false`.
- Build Dockerfile concluiu toda a cadeia obrigatória: bash -n, py_compile, diagnóstico individual archive_stream, suíte integral `test_factory_runner_*.py`, workspace-sync não-root e E2E não-root. Contagem individual de testes não capturada.
- `[ARCHIVE-STREAM-PROBE]` **PASS** no startup: TAR sintético válido extraído/validado (1 arquivo, 38 bytes, conteúdo e hash coincidentes); child comprovou chroot, UID/GID drop, CapEff zero, ambiente vazio, FD audit ok, no_new_privs, seccomp e negação de escrita/rede/process creation.
- Traversal rejeitado como `unsafe_archive_path`, sem destino; overflow encerrou child por SIGKILL em 129 bytes; timeout externo encerrou child por SIGKILL; tmpfs cleanup restaurado em todos os cenários. `project_code_executed=false`.
- Opções preservadas: workspace_auto_prepare=false, workspace_sync_enabled=true, Owner Ingress habilitado; runner/read tokens presentes; GitHub write token e senha de enrollment vazios. Nenhum backup da RC64 criado, conforme decisão do proprietário.
- Nenhum código de projeto foi carregado/executado. O probe retorna `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.
- Pendências: quotas agregadas por job não comprovadas (cgroup v2 read-only/sem delegação; /dev/shm é compartilhado); Bubblewrap bloqueado por permissão de namespace/mount; Landlock indisponível; exportador Artesão atual (subprocessos e escrita em diretório) não compatível diretamente com stream. Nenhuma alteração no repositório consumidor.
- Resultado M108: **prova sintética integrada homologada no Raspberry Pi; Etapa 5B/Etapa 5 ainda NÃO concluídas e execução de código não confiável continua bloqueada.**


## M111 — RC66: probe sintético de user namespaces e tmpfs limitado (25/11/2026)

- RC66 candidata acrescenta `userns_probe.py`, um diagnóstico não mutante no próprio contêiner do add-on: tenta user namespace, mapeamento UID/GID, mount namespace com propagação privada, tmpfs de 1 MiB, quota por ENOSPC, network namespace e PID namespace com verificação de PID 1.
- O tmpfs é montado somente depois de confirmar `MS_REC|MS_PRIVATE` no mount namespace. O teste grava apenas arquivo sintético de até 2 MiB, desmonta e verifica ausência de mount vazado no namespace pai.
- A máscara de capabilities efetivas do processo pai é comparada antes/depois por capget. Timeout mata o filho; nenhum código de projeto é carregado/executado.
- Estados: blocked/partial/available/timeout/failed_cleanup_or_parent_state. `available` exige todos os namespaces, tmpfs com quota realmente aplicada, desmontagem e estado do pai preservado. User namespace sozinho não equivale a sandbox.
- Testes unitários cobrem a classificação fail-closed. A candidata ainda NÃO foi publicada, instalada ou executada no Raspberry; nenhum resultado real está declarado.
- Mesmo que user/mount/net/PID e quota tmpfs passem, isso prova apenas confinamento de namespaces e scratch limitado. Não prova quota agregada de CPU/memória nem autoriza execução de projeto.
- Gate permanece: `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.

### Próximo gate M111
Revisar código/testes/Dockerfile; promover RC66 para release-candidate; publicar somente factory-runner/ pela esteira oficial; atualizar o add-on existente uma vez, sem backup da RC anterior, e ler o marcador `[USERNS-PROBE]` no Supervisor. Se qualquer teste falhar, corrigir apenas a causa comprovada; não elevar privilégios nem alterar AppArmor, host, Docker API ou cgroups.


## M112 — RC67: correção de import do probe userns (25/11/2026)

- RC66 build ARM64 concluiu e o add-on iniciou, mas `[USERNS-PROBE] ERROR` ocorreu antes de qualquer syscall: `ModuleNotFoundError: No module named 'isolation_backend_probe'`.
- Causa confirmada: o script é iniciado com `python3 -I`; esse modo não adiciona automaticamente `/app` ao caminho de importação. O probe anterior já aplica `sys.path.insert(0, str(Path(__file__).resolve().parent))`.
- RC67 replica explicitamente esse padrão no novo probe. Nenhuma alteração em permissões, capabilities, AppArmor, seccomp, cgroups ou host.
- RC67 ainda não publicada/instalada; o resultado de namespaces continua desconhecido. Nenhum código de projeto executado.
- Gates mantidos: `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.


## M113 — RC67 instalada; resultado real do probe userns (25/11/2026)

- Fonte `release-candidate`: `f519fcd30dfbf89bae00b3f3b467fc367ef21b62`; pacote catálogo `fd13140c1ad656bf9a483127b3c8d62d9218fac9`; proveniência `6e2e165aa96b1d04216aa07b33d5901c71b07aa8`.
- Auditoria: 128/128 blobs da fonte correspondem ao catálogo; 2 arquivos exclusivos preservados; nenhum caminho fora de `factory-runner/` alterado.
- Supervisor: build ARM64 iniciado 19:49:27.752 BRT e concluído 19:52:54.466 BRT. RC67 instalada/started; update_available=false.
- Dockerfile completo concluído (bash -n, py_compile, suíte integral, workspace-sync não-root e E2E não-root). API-PROBE, E2E sintético e archive stream sintético PASS; contagem individual de testes não capturada.
- Manifesto HA: nome `Fábrica de Ideias - Factory Runner`; `ingress_entry` omitido para raiz. Ingress real termina em uma única barra. Opções persistentes preservadas; nenhum backup da RC66 criado conforme regra do proprietário.
- Probe real: user namespace, UID/GID maps, network namespace e PID namespace/PID 1 PASS. Mount namespace criado, mas `MS_REC|MS_PRIVATE` falhou com `EACCES`. Tmpfs não foi montado e quota por job não foi testada, pois o probe corretamente não tenta mount antes de garantir propagação privada. Parent capabilities inalteradas, SYS_ADMIN ausente antes/depois, nenhum mount vazou, sem timeout. Resultado `partial`.
- A causa exata de EACCES não está demonstrada; AppArmor/seccomp são hipóteses. Consultas de logs host/Supervisor não retornaram auditoria de negação. App permanece AppArmor default, privileged vazio, full_access=false; nenhuma proteção foi relaxada.
- Nenhum código de projeto executado. `safe_for_untrusted_code=false`; Publisher DORMANT; `sandbox_export` fail-closed.

### Próximo gate M114
Investigar a origem de EACCES apenas por evidências não mutantes (capabilities dentro do user namespace, perfil AppArmor efetivo e audit logs disponíveis). Não contornar com SYS_ADMIN, privileged, host mounts, Docker API/socket, alteração de AppArmor/seccomp ou capabilities. Se a política do host bloquear mount, registrar a limitação e avaliar alternativa sem mount; manter execução genérica bloqueada até comprovar quotas agregadas e contenção entre jobs.


## M114 — RC68: diagnóstico do contexto de segurança dentro do user namespace (25/11/2026)

- M113 confirmou user namespace, UID/GID maps, network namespace e PID namespace/PID 1. O mount namespace foi criado, mas `MS_REC|MS_PRIVATE` retornou `EACCES`; tmpfs e quota por job não foram testados.
- RC68 acrescenta leitura não mutante de `/proc/self/status` e `/proc/self/attr/current` dentro do processo filho após criar user namespace e mapear UID/GID. Registra CapEff, presença de CAP_SYS_ADMIN dentro do user namespace, NoNewPrivs, Seccomp e perfil AppArmor.
- A finalidade é distinguir falta de CAP_SYS_ADMIN dentro do user namespace de uma negação externa do syscall; o perfil/LSM só será apontado como causa se houver evidência correspondente. Não altera políticas nem tenta mount alternativo.
- Testes unitários cobrem o parser do contexto sintético; nenhum código de projeto é executado.
- RC68 candidata; build ARM64 e probe real pendentes. Gates mantidos: safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

### Próximo gate M114
Publicar RC68 pelo procedimento oficial, atualizar o app existente sem backup da RC anterior, verificar build ARM64, suíte completa e o novo campo child_security_context. Não ampliar permissões, não mudar AppArmor/seccomp/capabilities e não tentar montar tmpfs se a propagação privada falhar.

## M114 — RC68: diagnóstico real identifica a política AppArmor (25/11/2026)

- RC68 (0.1.0-rc.68) publicada, build ARM64 concluído às 20:08:33.024 BRT, app started; update_available=false.
- Contexto dentro do user namespace: CapEff=000001ffffffffff; CAP_SYS_ADMIN=true; NoNewPrivs=0; Seccomp=0; AppArmor=docker-default (enforce).
- mount(MS_REC|MS_PRIVATE) continua retornando EACCES. A ausência de CAP_SYS_ADMIN e o seccomp não são a causa neste probe. O template oficial Moby docker-default contém deny mount; Docker confirma que esse perfil é gerado a partir desse template. AppArmor é a causa de alta confiança, embora não haja audit record host para a negação específica.
- HA oferece caminho suportado: apparmor.txt na pasta do App substitui o perfil default sem desativar AppArmor. Fontes: https://contributors.home-assistant.io/apps/guides/security/ e https://contributors.home-assistant.io/apps/reference/configuration/.
- A política seccomp atual inclui deny mount/unshare, mas o módulo se declara protótipo não conectado ao executor genérico. Antes de executar projetos, o worker filho deve remover capabilities, ativar NNP e instalar seccomp antes do exec.
- Nenhum código de projeto executado; tmpfs continua não montado; quota por job não comprovada.
- Gates: safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.

### Próximo gate M115
Preparar proposta de perfil AppArmor mínimo em documento/branch isolada. Preservar as regras default e avaliar somente allow rules para rprivate na raiz do mount namespace e tmpfs no diretório scratch do probe. Não criar apparmor.txt, publicar ou instalar sem aprovação explícita do proprietário. Não usar apparmor: false, privileged, SYS_ADMIN no host, full_access ou Docker API/socket.
