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
