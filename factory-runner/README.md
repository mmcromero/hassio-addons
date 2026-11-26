> **ESTADO VIGENTE — 25/11/2026 / M116**
>
> - **HA:** RC68 (0.1.0-rc.68) continua instalada/started; RC69 (0.1.0-rc.69) está somente em desenvolvimento.
> - **Implementação:** helper ELF dedicado compilado no Dockerfile; userns_probe.py executa somente o binário fixo, com ambiente limpo, FDs fechados e timeout por grupo.
> - **Validação local:** compilação C estrita; 16/16 testes dirigidos (camada Python com shim local de `isolation_backend_probe`); probe real de namespaces/tmpfs PASS no laboratório, com NNP=1. O perfil observado foi `kernel`, sem AppArmor ativo.
> - **AppArmor:** estrutura parent/child passou sintaxe no parser 4.1.0 com skip-kernel-load. Parser HA 3.1.7 é inferido; transição cx e permissões ainda não foram exercitadas no HA.
> - **Próximo:** build Dockerfile/ARM64 e homologação controlada no HA; ativação do perfil customizado depende de autorização específica.
> - **Segurança:** nenhum apparmor.txt criado/aplicado; nenhum código de projeto executado; safe_for_untrusted_code=false; Publisher DORMANT; sandbox_export fail-closed.
>

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
