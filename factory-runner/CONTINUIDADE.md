# CONTINUIDADE — Factory Runner (19/11/2026)

### Lote grande — executor externo do Artesão Digital

O mesmo ramo agora inclui `artesao_isolated_executor.py` e `ARTESAO-BUILDER-002.md`. A execução real só pode ocorrer em VM descartável devidamente segregada, com cache npm/BuildKit offline e Docker local; a política de build está vinculada a fonte SHA + versão. `--execute` **não foi acionado** e a VM ainda não foi provisionada/validada. Os recibos oficiais, arquiteturas arm64/amd64 e hashes estão definidos e a verificação está implementada. Há **15 testes offline novos**, ainda não executados nesta sessão; não confundir criação de testes com PASS. Nenhuma mudança na RC9 publicada ou no Avisaqui, Forja 01, HA e catálogo.

**Próxima obrigação do executor técnico**: executar suítes offline, corrigir falhas, comprovar isolamento da VM e caches, e então ensaiar com uma futura versão nova autorizada. A fonte dev.28 atual colide com o pacote HA dev.28 de outra origem, portanto o teste real desta versão fica corretamente bloqueado antes do build. Não alterar a versão do produto por conveniência.


## Desenvolvimento: adaptador HA + Debian do Artesão Digital

**Branch isolada:** `feat/factory-runner-artesao-package-adapter` (base `feat/factory-runner-esteira-001`, RC9 de origem). Novo `artesao_adapter.py`; perfil com receitas oficiais pinadas; integração com preflight e sincronismo; preparação bloqueada até recibos, imagens e aprovação; novos testes Git locais. **Não há pacote, publicação, merge, Actions nem alteração de servidor.** A RC9 instalada no Raspberry não é afetada.

**Próximo responsável:** revisar/rodar os testes e estabelecer executor confiável para os scripts oficiais do Artesão (HA ARM64 e Debian AMD64), sem conceder Docker/socket ou permissões extras ao add-on HA. Conferir `ARTESAO-ADAPTER-001.md` e registrar na Issue #2.


**Situação atual: RC3 0.1.0-rc.3 INSTALADA E INICIADA NO HOME ASSISTANT (logs do proprietário). Nova RC4 0.1.0-rc.4 com lote técnico e testes dirigidos CONCLUÍDOS NA FONTE PRIVADA; candidata de diagnóstico pronta para decisão de publicação. RC4 NÃO PUBLICADA/NÃO INSTALADA. Exportação segue BLOQUEADA.**

**Responsável atual:** DEV/Tech Lead + Segurança pela investigação do isolamento; operador HA só será acionado após candidata validada para novo teste, sem repetir a RC3. **Issue única:** [Orquestrador #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2).

## Evidência da entrega

- **Fonte privada:** `mmcromero/orquestrador-projetos-base:feat/factory-runner-esteira-001/factory-runner-add-on/`, corte técnico do candidato `a7c089d3312222017afaced1741a105bbc721cc3`; documentação atualizada depois do corte para refletir a publicação.
- **Distribuição real:** `mmcromero/hassio-addons:main/factory-runner/`, commit **`db77d23fcfef78535240577388b2a654a0cb2d8a`**. Verificada a resposta remota de `main`, `config.yaml` versão `0.1.0-rc.3` e cópia do worker na imagem final.
- **Escopo do commit público:** **9 arquivos**, todos dentro de `factory-runner/`. Total de blobs no catálogo: 208 antes / 210 depois (dois arquivos novos). Nenhum outro add-on, workflow ou repositório afetado.
- **GitHub Actions:** nenhum acionamento manual; commit contém `[skip ci]`; consulta de execuções associadas ao commit retornou zero.
- **Instalação no Raspberry:** RC3 foi instalada pelo proprietário e seus logs de startup enviados. DEV não executou instalação; isso confirma worker diagnóstico e abertura da API, não homologação de chamadas HTTP cliente ou exportadores.

## O que a RC3 faz

- `controlled_worker.py` é processo filho **sem root** que permite somente tarefas controladas e de leitura: `diagnose`, `profile`, `preflight`. Nova rota `POST /api/worker/run` exige Bearer e recusa ações/parâmetros fora da allowlist.
- `run.sh` observa o perfil AppArmor e flags no contexto real do add-on, executando os diagnósticos com `env -i`, sem herdar o token do serviço; saída prefixada `[WORKER]`.
- `server.py` registra `[API] READY` somente depois do bind em loopback; `[ISOLATION] PASS/BLOCKED` continua se referindo a Bubblewrap.
- Segurança preservada: porta externa sem mapeamento, nenhum `SYS_ADMIN`, AppArmor relaxado, Docker socket ou `full_access`. `/api/prepare` segue condicionado a Bubblewrap operacional; `/api/fechar-pacote` e `/api/corrigir-issue` continuam HTTP 403.
- **Não é executor seguro para scripts externos.** RLIMIT por processo não substitui cgroup/quota agregada. Esta RC3 é candidata de homologação da camada read-only, não de fechamento automático de pacotes.

## Lote em desenvolvimento na fonte privada: consulta ABI Landlock

- **Versão reservada somente na branch:** `0.1.0-rc.4`. A loja `hassio-addons:main` continua na RC3 instalada. Nenhuma atualização HA neste lote.
- `landlock_probe.py` consulta `landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)` (syscall 444 em Linux aarch64/x86_64). Sem aplicar ruleset, mudar `no_new_privs`, montar, gravar, executar código de projeto ou alterar host.
- `controlled_worker.py` inclui `landlock` no resultado de `diagnose`. Mesmo que ABI esteja disponível, `enforcement_verified=false` e `safe_for_untrusted_code=false`.
- Dockerfile inclui o módulo na validação, compilação e imagem final; suite `tests/test_factory_runner_landlock_probe.py` cobre 11 cenários.
- **Testes reais no laboratório:** 11/11 PASS no Python local, hash Git do `landlock_probe.py` testado idêntico ao blob da fonte. A consulta como usuário não-root local retornou `syscall_unavailable` (`ENOSYS`), o que não informa disponibilidade no contêiner HA.
- **Limites:** Landlock controla arquivos (ABI 1+), TCP (ABI 4+), escopo IPC (ABI 6+) e UDP (ABI 10+), mas não substitui quotas de recursos nem namespaces. Não usar como sandbox de código não confiável apenas por ABI disponível.
- **Decisão de estudo:** priorizar alternativa de exportação determinística declarativa em código confiável para tarefas mecânicas; manter execução de scripts externos bloqueada até executor realmente isolado. Fonte: [LANDLOCK-ESTUDO-001.md](LANDLOCK-ESTUDO-001.md).

## Alternativa de preparação sem executar código do projeto — prova de conceito

- **Fonte exata examinada:** `mmcromero/pager-virtual:desenvolvimento/scripts/export-distribution.py`, blob `e67c816405707545b21b0e6863814ada7b26d0f1` fixado no perfil `avisaqui.json`. A maior parte é cópia determinística de arquivos de commit Git, mapeamento, hashes e proveniência; há exceções para workflow e patch de CI que exigem portão próprio.
- **Experimento privado:** `trusted_export_plan.py` calcula somente um plano de arquivos a partir de metadados sintéticos e regras genéricas, com 13/13 testes locais PASS, sem ler Git, copiar, executar script ou publicar. `Dockerfile` inclui no estágio de **validação somente**, nunca runtime. Não é equivalente ao exportador original nem habilita `/api/prepare`.
- **Decisão técnica:** estudar um exportador determinístico confiável por perfil como saída de baixo risco para tarefas mecânicas; reservar executor isolado para scripts de código não confiável. O planejador é uma etapa de POC, ainda faltam leitura real por SHA, tipos de blob, comparação com exportador oficial, validação de tamanhos/bytes e gates de workflow/pacote. Detalhes: [LANDLOCK-ESTUDO-001.md](LANDLOCK-ESTUDO-001.md).

## Verificação final do lote RC4 (consulta read-only, sem execução externa)

- Fonte oficial exata conferida no Avisaqui: commit `a4b97c1d353e6111dc48933806f13c77d0dec6f9`, exportador blob `e67c816405707545b21b0e6863814ada7b26d0f1`, política de pacote FECHADA `closed_release_candidate_published_pending_homologation` (`0.1.20-rc.11`). Não existe autorização operacional para preparar esse pacote.
- Snapshot de metadados com **295 blobs**, mapeamento de **135 arquivos padrão** e **1 workflow compartilhado** separado: `tests/fixtures/avisaqui_git_tree_20261119.json`. Nenhum conteúdo de código do Avisaqui foi copiado.
- Testes locais nesta rodada: **38/38 PASS** (7 núcleo worker, 11 Landlock, 13 planejador, 7 comparação de mapeamento). Executados em Python local; para o último grupo foi usada fixture local com 136 arquivos selecionados e tamanhos reais correspondentes. Metadados de todos os 295 caminhos da fixture versionada foram conferidos estaticamente.
- `controlled_worker.py`, `landlock_probe.py` e `trusted_export_plan.py` testados com blobs idênticos à branch; worker em subprocesso UID 65534 retornou `diagnose ok=true` e `safe_for_untrusted_code=false`. **Não foram executados Dockerfile inteiro, suíte completa da árvore privada, build ARM64/HA, verificação de bytes de exportação ou operações de patch CI**.
- RC4 é **candidata de diagnóstico**, não habilita `/api/prepare`, exportador ou publicação de pacotes. A ausência de Docker local não é gate de bloqueio genérico da distribuição, conforme `hassio-addons:main/CONTRIBUTING.md`. Publicação da RC4 exigirá autorização específica, não implícita na autorização RC3.

## Evidência nova: logs reais RC3 enviados pelo proprietário

```text
[STARTUP] Factory Runner — modo restrito
[ISOLATION] BLOCKED: bubblewrap probe exit 1 (bwrap: Failed to make / slave: Permission denied)
[STARTUP] Factory Runner — modo restrito
[ISOLATION] BLOCKED: bubblewrap probe exit 1 (bwrap: Failed to make / slave: Permission denied)
[WORKER] {"worker":"factory-runner-controlled","task":"diagnose","ok":true,"result":{"mode":"diagnostic_only","uid":100,"apparmor":"docker-default (enforce)","security_flags":{"CapEff":"0000000000000000","CapBnd":"00000000a80425fb","NoNewPrivs":"0","Seccomp":"0"},"bubblewrap_available":"not_tested","sandbox_ready":false}}
[API] READY: loopback-only; authenticated; worker read-only; publication disabled
```

**Comprovado:** RC3 iniciou worker diagnóstico (UID 100, sem capacidades efetivas) e a API abriu bind loopback; não há filtro seccomp no processo (`Seccomp=0`). **NÃO comprovado:** chamada HTTP real do cliente à nova rota `/api/worker/run`, preparação de pacote ou isolamento do exportador. Dois `[STARTUP]` apenas indicam pelo menos duas inicializações no trecho fornecido, não comprovam ciclo de crash. `NoNewPrivs=0` significa que este recurso não está ativo; não inferir que o processo tenha privilégios efetivos.

**Causa provável do bloqueio:** o perfil `docker-default (enforce)` inclui `deny mount,` na política padrão publicada pelo Docker, compatível com o `MS_SLAVE` negado pelo Bubblewrap. Falta auditoria da operação específica; é hipótese forte, não diagnóstico definitivo de syscall. Documento: https://docs.docker.com/engine/security/apparmor/. O HA aceita `apparmor.txt` por app, mas instalar perfil de concessão de `mount` pode enfraquecer o isolamento e requer design/revisão, sem permissão automática de `SYS_ADMIN`. Fonte: https://contributors.home-assistant.io/apps/guides/security/.

**Alternativa promissora para estudo:** Landlock (LSM do kernel sem montagens; direitos de arquivo e TCP em ABI v4+) pode confinar subprocessos mesmo com `docker-default`. **Suporte no kernel HA 6.18 ainda NÃO testado**; Landlock não equivale, por si, a namespaces de rede/PID nem limita CPU/RAM/PIDs agregados. Exige uma prova positiva de isolamento, que falhe fechada em ausência de ABI/direitos. Fonte: https://www.kernel.org/doc/html/latest/userspace-api/landlock.html.

**Próximo responsável:** DEV/Segurança investigar viabilidade de `apparmor.txt` restrito versus Landlock+limites, em ambiente de desenvolvimento, sem mudar o host e sem publicar novo pacote antes dos controles. O worker read-only RC3 não deve ser usado para código arbitrário.

## Testes e limites verificados

- Reexecutados localmente no laboratório Python 3.13: **7/7** do núcleo, **3/3** do lançador, **12/12** da rota HTTP (trechos de fonte conferidos por hashes FNV32 com o código da branch). Testes com usuário não-root realizados no laboratório, fora do HA.
- Revisão estática sobre 13 arquivos da candidata passou: versão, token, permissões, testes versionados, cópia do worker para estágios de validação/runtime, base de sandbox fail-closed, hash dos trechos testados. Teste novo versionado: 10 cenários.
- **Não foram executados:** Docker build completo, `unittest` da árvore Git integral, build ARM64 e teste físico no HA. Não marcar esses itens PASS; o Dockerfile contém validação obrigatória durante o build no Supervisor.
- **Bloqueio anterior conhecido:** `bwrap: Failed to make / slave: Permission denied`, no contêiner HA RC2. Investigação AppArmor não autorizou alterar a política. O 504 visto no stream de logs não comprova falha da API.

## Próxima ação exata (após implementação do probe Landlock)

1. **DEV/Segurança:** revisar a prova de conceito do plano declarativo e completar comparação do mapeamento/proveniência com o exportador oficial do Avisaqui; não habilitar escrita até comprovação e limites. Estudo: [LANDLOCK-ESTUDO-001.md](LANDLOCK-ESTUDO-001.md).
2. **DEV:** validar integração real da árvore privada no build; `landlock_probe.py` e suite dedicada estão no Dockerfile; 11 testes locais de ABI foram executados, mas a suíte integral da branch/ARM64 e runtime HA para RC4 ainda **NÃO** foram executados.
3. **Tech Lead/Segurança:** Landlock ABI positiva **não é isolamento aprovado**. Exigir provas de filesystem/rede/IPC/PIDs e limites de recursos agregados antes de permitir qualquer código externo. `/api/prepare` continua fail-closed e operações privilegiadas 403.
4. **Proprietário:** nenhum comando nem reinstalação neste ponto. Futuras alterações do catálogo/HA exigem controles e autorização específicos.

**Situação dos testes físicos da RC3:** STARTUP, worker de diagnóstico e bind local confirmados; API end-to-end não testada, exportador ainda bloqueado por Bubblewrap. RC4 contém apenas diagnóstico adicional em desenvolvimento, sem publicação.

**Políticas canônicas:** `fabricacao_e_orcamentos:main/docs/operacao/GOV_STD_001.md` v0.9, `GOV_BLK_002.md` v0.3, `hassio-addons:main/CONTRIBUTING.md` P0. Históricos e incidentes: [HISTORICO.md](HISTORICO.md), [CONTROLLED-WORKER.md](CONTROLLED-WORKER.md), Issue #2.
