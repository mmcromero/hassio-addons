> **ESTADO VIGENTE — 25/11/2026 / M084**
>
> - **Roadmap:** seis etapas; isolamento de código não confiável permanece obrigatório na Etapa 5, antes de executar código de projetos.
> - **Fonte ativa:** `mmcromero/factory-runner:release-candidate`; RC45 (`0.1.0-rc.45`) publicada no catálogo; RC44 (`0.1.0-rc.44`) permanece instalada e homologada; atualização RC45 e testes Etapa 4 pendentes. Fonte de desenvolvimento preservada.
> - **Catálogo:** RC44 publicada em `mmcromero/hassio-addons:main/factory-runner/`; 114 arquivos comparados, zero divergências; somente seis caminhos da pasta Factory Runner alterados no pacote/proveniência.
> - **Supervisor:** RC44 instalada e `started` em ARM64; build concluído; sem atualização pendente. Backup pré-update RC41: `4e6ea0d9`.
> - **Etapa 1:** API/segurança, persistência/idempotência e configuração/bootstrap concluídas para o modo restrito.
> - **Etapa 2:** FR-EXEC-001 validada em RC41; planos read-only persistidos para os dois workspaces.
> - **Etapa 3:** homologação RC44 PASS: Dockerfile, sintaxe, compilação Python, suíte automatizada e probe real autenticado da API de jobs. Dois jobs terminaram PARCIAL como esperado; 68/54 testes selecionados, nenhum executado; digest/recibo, polling, idempotência, filtros e auditoria conferidos.
> - **Publisher:** DORMANT; publicação de produtos desativada. Nenhum código de Avisaqui/Artesão executado.
> - **Isolamento:** Bubblewrap ainda bloqueado no mount namespace e Landlock indisponível; execução arbitrária permanece fail-closed e reservada à Etapa 5.
> - **Continuidade:** [docs/CONTINUIDADE-ATIVA.md](../docs/CONTINUIDADE-ATIVA.md), seção M082; [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2).
>
> O histórico abaixo foi preservado. Referências antigas a RCs anteriores são registros históricos, não o estado operacional atual.


---

# Factory Runner — fonte, operação e continuidade

**Executor externo em estudo (não publicado):** `artesao_isolated_executor.py` implementa os passos oficiais de build HA ARM64 e Debian AMD64, recibos de testes reais, hashes e bloqueios por SHA/versão/arquitetura, somente em VM isolada. **Não é copiado para a imagem final HA.** O script só executa tarefas no builder com `--execute` e uma política externa exata; nenhuma VM/compilação/instalação foi usada neste lote. Ver `ARTESAO-BUILDER-002.md`.


**Em desenvolvimento — adaptador de pacotes Artesão Digital:** perfil de origem, políticas e versões HA/Forja auditáveis via Git, com receitas fixadas por blob SHA. Consulta `/api/preflight` poderá retornar o plano para os dois destinos; **não habilita compilação, preparação nem publicação**. Os recibos oficiais e builds de arquiteturas diferentes continuam obrigatórios. A versão pública instalada do Runner não muda por esta branch. Ver `ARTESAO-ADAPTER-001.md`.


**RC9 — Artesão Digital integrado em modo somente leitura (candidata):** o segundo perfil `artesao_digital` aponta para `fabricacao_e_orcamentos:main` e `fabricacao-e-orcamentos-ha:main`. Sua política de versões é diferente da do Avisaqui, por isso a sincronização verifica o blob `apps/umdoislab/artesao-release.json` e **recusa preflight, preparação e publicação**. O Avisaqui permanece com seu exportador e sua política anteriores. Com `workspace_sync_enabled=true`, o Runner passará a processar **dois projetos** quando a RC9 for publicada e instalada. Cinco testes de regressão foram acrescentados, mas **ainda não executados nesta revisão**. Ver `RC9-VALIDACAO.md` e Issue #2. A RC8 continua como última publicação comprovada.

**Produto:** Fábrica de Software / Factory Runner (add-on Home Assistant).
**Status deste arquivo:** registro de continuidade, não prova de instalação ou homologação.
**Atualizado:** 2026-11-19.
**Regra de leitura:** este diretório é a origem de desenvolvimento da esteira, mas a distribuição atualmente instalada vem de outro repositório. Antes de qualquer alteração, conferir os HEADs e comparar a origem com o pacote publicado.

## Comece aqui (novo agente)

1. Leia a continuidade ativa em ../docs/CONTINUIDADE-ATIVA.md.
2. Leia GOV-STD-001, GOV-BLK-002 e CONTRIBUTING do catálogo HA.
3. Acompanhe a Issue canônica #2 do Orquestrador. A Issue #1 deste repositório trata somente da preservação do histórico Git adiada pelo proprietário.
4. Use exclusivamente mmcromero/factory-runner:desenvolvimento como fonte ativa e compare a pasta factory-runner/ do catálogo antes de publicar.
5. Retome a última pendência validada; não repita etapas aprovadas nem crie branches/Issues sem necessidade.

## Repositórios e responsabilidade

| Papel | Localização |
| --- | --- |
| Fonte ativa | mmcromero/factory-runner:desenvolvimento/factory-runner-add-on/ |
| Distribuição | mmcromero/hassio-addons:main/factory-runner/ |
| Baseline publicada/instalada | Factory Runner 0.1.0-rc.19, conforme registro HA de 24/11/2026 |
| Candidata em desenvolvimento | 0.1.0-rc.20, para homologação final no HA |
| Acompanhamento oficial | Issue #2 do Orquestrador; Issue #1 deste repositório mantém somente a pendência histórica de importação Git adiada |

**Atualização em 19/11/2026:** a base RC2 foi sincronizada na origem privada e o worker controlado foi desenvolvido; a **RC3 foi publicada somente na pasta `factory-runner/` de `hassio-addons:main`**, commit `db77d23fcfef78535240577388b2a654a0cb2d8a`. O worker está **PUBLICADO NO GITHUB**, mas **não instalado ou homologado no Home Assistant**. A divergência histórica da fonte consta em `HISTORICO.md`. A divergência histórica está registrada em `HISTORICO.md`. Não fazer exportação cega nem sobrescrever a distribuição.

## Regras permanentes

- O catálogo existente do HA usa `hassio-addons:main` sem `#branch`. Uma branch alternativa não atualiza o add-on já instalado.
- A publicação autorizada modifica exclusivamente `hassio-addons:main/factory-runner/`, preservando outros add-ons, `repository.yaml`, workflows e credenciais. Não fazer merge geral de branch se ela contiver arquivos não autorizados.
- Com `Dockerfile` e sem campo `image` no `config.yaml`, o Supervisor pode compilar no próprio Raspberry durante a atualização. Não exigir QEMU, Actions ou Codespaces como etapa fixa. Segurança e erros reais podem exigir testes complementares.
- PUBLICADO, INSTALADO, INICIADO, TESTADO e HOMOLOGADO são estados distintos.
- Nunca introduzir execução arbitrária, bypass de Bubblewrap, tokens embutidos, Docker socket, portas públicas, privilégios extras, sysctl ou mutações no host para contornar diagnóstico. A falha do sandbox deve permanecer fechada.
- Não usar Forja 01 para builds/testes do Factory Runner; não interferir em Evolution, Avisaqui ou outros serviços HA.
- Ao concluir cada lote: registrar data, branch, SHA, arquivos alterados, validações realizadas e **não** realizadas, resultados, autorização e próximo passo em HISTORICO.md e Issue #2; atualizar CONTINUIDADE.md. Não copiar segredos nem dados privados em logs/documentos.

**Próxima leitura obrigatória:** [CONTINUIDADE.md](CONTINUIDADE.md), [CONTROLLED-WORKER.md](CONTROLLED-WORKER.md) e [LANDLOCK-ESTUDO-001.md](LANDLOCK-ESTUDO-001.md). A consulta ABI está apenas na RC4 privada; a RC3 instalada não a contém.
