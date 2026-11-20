# Factory Runner — RC5 validação de laboratório (19/11/2026)

**Controle único:** [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2). **Estado:** CANDIDATA NA BRANCH; **NÃO PUBLICADA / NÃO INSTALADA / NÃO HOMOLOGADA**. A RC4 permanece na `main` pública. Não houve GitHub Actions, Docker build, QEMU, merge, instalação ou alteração no host HA.

## Mudança funcional

- `POST /api/prepare` usa **exportação declarativa confiável** quando o perfil versionado fornece receita aprovada. Não executa o exportador Python do projeto e, nessa função mecânica, não depende de Bubblewrap.
- O método é multi-projeto por perfis; o primeiro exemplo validado é Avisaqui. SHA de origem, política do pacote, referências Git, versão, CI compartilhado e hashes são verificados. O destino é somente bundle local, sem publicação ou gravação remota.
- Sem receita confiável, a execução legada mantém Bubblewrap e falha fechada. `/api/corrigir-issue` e `/api/fechar-pacote` permanecem HTTP 403; código não confiável continua **PROIBIDO**.
- Na inicialização, `declarative_runtime_probe.py` usa dados sintéticos em `/tmp`, usuário sem root e ambiente limpo; grava `[DECLARATIVE] PASS/BLOCKED`. O diagnóstico não libera automaticamente tarefas, não acessa checkouts privados e não comprova limites de cgroup ou isolamento de código desconhecido.

## Evidência de execução real — laboratório isolado

| Verificação | Resultado | Alcance |
|---|---|---|
| Módulo `declarative_export.py` | **18/18 PASS** | Git temporário real, SHA, mapeamentos, versões, symlinks, limites, manifesto |
| `rc_fastlane.py` | **19/19 PASS** | Validação de perfil e política, SHA, cenários negativos; corrigidas fixtures que misturavam dois modos de mapeamento |
| HTTP dirigido com `server.py` exato | **8/8 PASS** | Autenticação, bloqueio, auditoria, CI fixado, `/api/prepare` declarativo e fallback proibido |
| HTTP com preflight Git **real** | **3/3 PASS** | `/api/preflight` → `/api/prepare` com repositórios sintéticos; pacote aberto, fechado e SHA inválido |
| Startup probe | **4/4 PASS** | Recusa root, Git indisponível, ambiente sem token e verificação sintética |
| Startup probe via `runuser -u nobody`, ambiente limpo, Python `-I` | **PASS**, exit 0 | Execução realmente não-root no laboratório Linux; **não** no Home Assistant |
| Exportador canônico original vs método declarativo | **PASS** | **29 arquivos + 1 workflow compartilhado**, bytes idênticos, proveniência JSON idêntica, `--verify` oficial PASS; dados sintéticos |
| `run.sh` | **PASS** em `bash -n` | Blob exato `59df004d5523805151a52ee1f13aef73a63f6099`; invocação do probe com `env -i` |
| Paridade fonte ↔ distribuição | **26 arquivos funcionais/de teste + config compatíveis** | SHA de Git blob igual nas branches privadas/de preparação; sem alterações em outros add-ons |

**Total de testes Python executados e aprovados:** **52/52** (18 + 19 + 8 + 3 + 4). A comparação canônica é cenário adicional, fora da contagem. Os arquivos-base do módulo, do preflight e do servidor executados no laboratório foram reproduzidos com hashes Git iguais aos blobs nas branches; as suítes HTTP auxiliares foram criadas para o laboratório e não substituem a suíte integral do checkout.

**Fonte exata e snapshot:** exportador oficial `scripts/export-distribution.py`, Git blob `e67c816405707545b21b0e6863814ada7b26d0f1` (perfil aprovado); árvore real do commit `a4b97c1d353e6111dc48933806f13c77d0dec6f9` usada para comparação de seleção: **135/135 caminhos padrão equivalentes, sem diferença**, mais um workflow compartilhado. Isso não é comparação byte a byte do snapshot real; a equivalência integral de bytes foi executada somente em fixture sintética.

## Arquitetura e segurança preservadas

- Nenhum `privileged`, `SYS_ADMIN`, `docker_api`, Docker socket, porta pública, AppArmor permissivo ou fallback para execução de scripts fora do sandbox.
- A preparação não confirma autorização de publicação. Os tokens não são incluídos nos subprocessos Git sintéticos. Falhas de permissão, SHA, política e CI resultam em bloqueio.
- O código-fonte privado permanece em `orquestrador-projetos-base:feat/factory-runner-esteira-001` e a distribuição de teste em `hassio-addons:feat/factory-runner-declarative-preparation`. `main` pública continua RC4.

## Gates restantes — não declarar PASS antes do evento

1. **Suíte completa do checkout no Dockerfile**: `python3 -m unittest discover -s /app/tests -p 'test_factory_runner_*.py' -v` no estágio `validation`. Nenhum Docker disponível neste ambiente para executar o build completo.
2. **Build ARM64 real e startup no HA/Raspberry**: instalação de candidata autorizada no Supervisor. Confirmar `[DECLARATIVE] PASS` como UID runner, API ativa, sem negação de acesso e sem enfraquecer segurança.
3. **Workspaces privados do projeto atendido**: checkouts confiáveis pré-provisionados e refs/SHAs corretos. A falta desses volumes mantém o endpoint 503, mesmo com o exportador corrigido. Não montar `/config`, Docker socket ou diretórios de produção.
4. **Gate de Segurança/Homologação**: validar pacote funcional no hardware alvo, comportamento negativo, cgroups/quotas conforme necessidade e autorização independente de publicação. O código gerado por IA ainda exige isolamento separado.

**Próxima ação:** revisão final de segurança do lote; preparar o corte de distribuição somente no `factory-runner/` para publicação de teste, seguida de homologação física. Nenhuma nova Issue.
