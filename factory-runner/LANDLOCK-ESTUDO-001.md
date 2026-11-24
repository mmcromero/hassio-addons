# FACTORY-RUNNER-LANDLOCK-001 — Viabilidade e próximo experimento

**Data:** 19/11/2026. **Estado:** estudo + probe não destrutivo implementado na branch de desenvolvimento; **NÃO PUBLICADO / NÃO INSTALADO / NÃO HOMOLOGADO**. Controle: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2). Produto: Factory Runner independente dos projetos atendidos.

## Evidências confirmadas

1. **RC3 real no Home Assistant:** [WORKER] diagnóstico OK (UID 100, CapEff=0, AppArmor `docker-default (enforce)`, Seccomp=0), [API] READY; [ISOLATION] BLOCKED: `bwrap: Failed to make / slave: Permission denied`. São observações do processo real, não prova de operação de uma API cliente nem de origem exata do EPERM.
2. **Documentação do kernel (consultada):** o Landlock pode acrescentar restrições de arquivos desde ABI 1, TCP por porta desde ABI 4, escopo IPC desde ABI 6 e UDP por porta desde ABI 10. O suporte precisa ser verificado no ambiente de execução. Não oferece por si só quotas agregadas de CPU/RAM/PIDs, nem prova isolamento de processos, nem garante que toda forma de acesso externo seja negada.
3. **Docker AppArmor:** `docker-default` impõe restrições de `mount`, consistentes com a falha do Bubblewrap; o log de auditoria específico do kernel não foi coletado. A conclusão **AppArmor é a causa exata** continua NÃO COMPROVADA.
4. **Probe preparado:** `landlock_probe.py` invoca somente `landlock_create_ruleset(NULL, 0, LANDLOCK_CREATE_RULESET_VERSION)` com syscall 444 (Linux x86_64 e aarch64). Consulta ABI, sem criar ou aplicar ruleset, sem alterar `no_new_privs`, política do host ou dados. `controlled_worker.py --task diagnose` passará a incluir o campo `landlock` quando uma futura versão autorizada contiver o código.
5. **Resultados locais reais:** 11 testes de ABI, sucesso/erro/falha fechada PASS em Python local; execução direta como processo não-root no laboratório retornou `status=syscall_unavailable` (`ENOSYS`). O ambiente laboratorial pode interceptar syscall: **não prova que o kernel do Raspberry não suporta Landlock**. O hash Git do módulo testado foi comparado com o da fonte privada após revisão.
6. **Interpretação segura:** `status=supported` significa somente que a chamada de versão respondeu com ABI; `enforcement_verified=false` e `safe_for_untrusted_code=false` permanecem sempre. Mesmo ABI alta exige prova de regras efetivamente aplicadas e testes negativos no contêiner exato.

## Diagnóstico esperado

`landlock.status` é um destes: `supported`, `syscall_unavailable`, `disabled`, `permission_denied`, `unsupported_arch_or_os`, `query_failed`, `unknown`. `landlock.abi` é número ou nulo. `filesystem_rules`, `tcp_port_rules`, `udp_port_rules`, `ipc_scoping` são apenas capacidades da ABI, NÃO comprovantes de confinamento.

## Decisão técnica recomendada

**Não substituir Bubblewrap por Landlock isoladamente.** Mesmo quando disponível, ele é uma camada de defesa complementar e não garante por si a separação de PID/rede, limites agregados e bloqueio de todas as interfaces de comunicação.

Avançar em duas trilhas, sem modificar o Home Assistant agora:

- **Tarefas determinísticas de baixo risco:** investigar uma preparação de pacotes implementada inteiramente no código confiável do Runner, com esquema declarativo/allowlist de arquivos Git e hashes fixados, em vez de executar scripts dos projetos. Isso exige revisão de diferenças com o exportador aprovado e testes com fixtures reais; não habilitar diretamente `/api/prepare` até comprovar equivalência e limites.
- **Código não confiável e exportadores gerais:** manter FAIL-CLOSED. Estudar executor externo/dedicado com namespaces reais, sem rede, segredos ou acesso ao HA, e cgroups/quota por árvore de processos. Perfil AppArmor exclusivo do add-on somente como alternativa após avaliação da regra específica; não liberar `SYS_ADMIN` nem substituir perfil por permissivo.

## Revisão do exportador real do Avisaqui — evidência de alternativa sem executar scripts

**Fonte exata inspecionada:** `mmcromero/pager-virtual:desenvolvimento/scripts/export-distribution.py`, blob Git `e67c816405707545b21b0e6863814ada7b26d0f1`. O mesmo blob está fixado no perfil privado `factory-runner-add-on/projects/avisaqui.json` e aparece em `release-candidate`. Nenhum arquivo do Avisaqui foi alterado.

**Operações verificadas no código original:**
- `git ls-tree` lista os objetos do commit; `git show <sha>:<path>` extrai cada arquivo do commit. Há mapeamento de prefixos como `src/`, `tests/fixtures/` e arquivos `tests/*.test.js` e alguns arquivos declarados explicitamente.
- Os bytes são copiados ao diretório `pager-virtual/` da distribuição, e os SHA-256 são registrados em `SOURCE_PROVENANCE.json`; `--verify` compara os bytes gerados com objetos do commit.
- O script também possui modos históricos de hotfix, exportação opcional de arquivos de governança para `.github/workflows/` e aplicação/verificação de um patch de CI Node 22. **Essas operações alteram caminhos compartilhados e exigem portões independentes; não são uma simples cópia de arquivos.**

**Viabilidade:** uma nova função de **planejamento e cópia declarativa confiável** no Runner pode reproduzir a parte estritamente determinística sem importar/executar o `export-distribution.py`. O Runner leria apenas objetos Git de SHA fixado; um perfil versionado definiria entradas, destinos e limites. O resultado iria para checkout temporário; sem push, sem merge, sem publicar. Isso é alternativa arquitetural, **não implementação já validada**.

**Controles mínimos:** validar tipos de objeto Git (rejeitar symlinks/submódulos), normalizar caminhos, prefixos de destino e allowlist, tamanho total de arquivos, quantidade de objetos, diretórios do workspace, redirecionamento por links, ausência de tokens no subprocesso e comparação byte a byte de proveniência. A reprodução integral do exportador (incluindo CI, hotfix e workflows) exige fixture comparativa e aprovação específica da mudança; **não afirmar equivalência antes dos testes**.

**Recomendação:** priorizar esse modelo para tarefas mecânicas de empacotamento. Reservar Landlock, AppArmor específico e executor externo para situações que realmente demandem executar código desconhecido. Mantém o produto multi-projeto, porque regras de cópia ficam em perfis de projeto, não no núcleo genérico.

## Protótipo de planejamento declarativo — implementado, mas NÃO integrado ao serviço

- Código privado `trusted_export_plan.py`: recebe metadados de uma árvore Git e regras declarativas; **retorna apenas um plano**, sem chamar `git`, executar Python do projeto, ler ou escrever arquivos, criar checkout, alterar workflows, autenticar API ou publicar.
- Testes `tests/test_factory_runner_trusted_export_plan.py`: **13/13 PASS** no laboratório local, cobrindo mapeamento normal, bloqueio de caminhos absolutos/relativos perigosos, prefixo reservado `.github/`, symlink, submódulo, duplicatas, fontes obrigatórias ausentes e limites por arquivo/total. O módulo e o teste versionados possuem blob Git igual ao testado localmente.
- O Dockerfile inclui o planejador **apenas na etapa de validação**, não na imagem final e sem endpoint ou tarefa operacional. Isso evita apresentar uma prova de conceito como função habilitada.
- O exemplo de mapeamento testado é **parcial**. Não reproduz ainda o manifesto completo do Avisaqui, suas regras condicionais, hotfixes nem patches de CI. Antes de substituir o exportador oficial, exigir comparação byte a byte e de proveniência em checkouts sintéticos/realistas, suporte a todos os caminhos legítimos e testes de bloqueio, sem alterar `hassio-addons:main`.
- Os limites do protótipo usam metadados de tamanhos recebidos como entrada; não equivalem a quota real de disco ou validação de blob. Um futuro executor deve conferir bytes reais, tamanhos, SHA-256, links, limites de IO e integridade novamente durante a cópia e só então permitir preparo autorizado.

## Verificação com árvore Git real do Avisaqui — realizada no lote de validação RC4

- **Origem conferida via conector GitHub:** `mmcromero/pager-virtual:desenvolvimento` SHA `a4b97c1d353e6111dc48933806f13c77d0dec6f9` (não é autorização de pacote). O exportador `scripts/export-distribution.py` mantém blob `e67c816405707545b21b0e6863814ada7b26d0f1`. A política do pacote no snapshot está **`closed_release_candidate_published_pending_homologation`**, versão `0.1.20-rc.11`, por isso **nenhuma preparação real foi autorizada ou feita**.
- **Árvore revisada:** 320 entradas Git, sendo 295 blobs. O mapeamento não-hotfix do script aponta para **135 arquivos padrão** (soma de tamanhos de blobs **995.337 bytes**), todos presentes e com modos regulares `100644`/`100755`; nenhum selecionado é symlink ou submódulo. Há ainda **um workflow compartilhado** `distribution/governance/avisaqui-governance.yml` → `.github/workflows/avisaqui-governance.yml`, que requer portão de autorização próprio. A aplicação do patch de CI continua operação separada **não coberta por esse planejamento**.
- **Fixture imutável na origem privada:** `tests/fixtures/avisaqui_git_tree_20261119.json` contém somente nomes, tamanhos e modos do commit fixado, mais a lista esperada de destinos do script; **nenhum conteúdo dos arquivos**. Testes `tests/test_factory_runner_real_export_mapping.py` usam regras de mapeamento explícitas independentes da lista esperada, verificam os 135 destinos, as permissões, os 995.337 bytes, o gate de workflow e casos negativos de symlink/tamanho.
- **Execução local comprovada:** reproduzida a seleção com metadados da árvore real; **7/7 testes do mapeamento PASS** com fixture local contendo os 136 arquivos selecionados, com tamanhos conferidos ao snapshot e hash Git do arquivo de teste igual ao versionado (`0f2dcd27efaa7956a506e25c8cd21b1eaeaed48c`). A fixture completa da branch (295 blobs) ainda não foi executada localmente; inspeção estrutural de seus 295 caminhos e modos foi PASS. Uma execução integral no build do Supervisor validará a fixture completa.
- **Demais verificações deste lote:** teste local Python com módulos de fonte conferidos por blob Git: 7 testes de worker, 11 Landlock, 13 do planejador, 7 do mapeamento = **38/38 PASS**. `controlled_worker.py` carregado localmente possui blob `5560726b5ce800da538e5793c6a326813ff79f99` idêntico ao da branch e executou `diagnose` como UID 65534 com `ok=true`, sem executar código externo. `landlock_probe.py` e `trusted_export_plan.py` também foram executados com blobs idênticos aos da origem. Não confundir esses testes locais com teste de API no HA.
- **Escopo:** o planejador não entra na imagem de execução; só é compilado/testado no estágio `validation` do Dockerfile. A consulta Landlock entra no diagnóstico do worker, mas sempre sinaliza que não comprova isolamento. Nenhum arquivo do Avisaqui foi modificado.

## Critérios antes de qualquer RC futura

1. Comprovar que Dockerfile incluiu `landlock_probe.py` nos estágios `validation` e `runtime`, e que a suíte dedicada de ABI está incluída no build.
2. Verificar autenticação, ausência de tokens no subprocesso e que `landlock.enforcement_verified` e `safe_for_untrusted_code` continuam `false`.
3. Executar testes dirigidos e validar docs/versão/escopo.
4. **Solicitar autorização específica de publicação** para a próxima versão e atualizar somente `hassio-addons:main/factory-runner/`. O operador instala e reporta logs; não repetir os testes já realizados na RC3 sem mudança.
5. Só habilitar exportação se existir prova real de confinamento, limite de recursos, permissões por operação e autorização por pacote/SHA.

**Fontes:** [Kernel Landlock](https://www.kernel.org/doc/html/latest/userspace-api/landlock.html), [Linux syscall numbers](https://github.com/torvalds/linux/blob/master/include/uapi/asm-generic/unistd.h), [Docker AppArmor](https://docs.docker.com/engine/security/apparmor/), [Home Assistant app security](https://contributors.home-assistant.io/apps/guides/security/).
