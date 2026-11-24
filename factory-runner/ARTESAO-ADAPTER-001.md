# ARTESÃO-ADAPTER-001 — Primeira etapa: plano auditável de pacotes HA e Debian

**Situação atual (20/11/2026):** o adaptador foi publicado na RC10 e a correção de dois testes foi publicada na **RC11**, versão instalada no Home Assistant e confirmada por captura. Logs da RC11 demonstram sincronização e avaliação real de políticas do Artesão. O executor externo segue NÃO homologado e permanece fora da imagem de produção. O resultado integral da suíte da RC11 não foi disponibilizado; registros abaixo são o histórico original de desenvolvimento, não o estado atual da instalação.

## Correção do histórico da RC12 — fonte para próxima RC

A leitura da RC12 não reconhece a família de auditoria real
`workspace_sync:<project_id>` nem os estados `completed_workspace_sync`
e `blocked_workspace_sync`. Por isso poderia retornar lista vazia mesmo
quando o startup registrava sincronização de projetos. Corrigido **na branch
de desenvolvimento**: aceitar apenas identificadores de projeto dentro da
gramática validada, exibir o último estado da operação, preservar a seleção
dos quatro campos seguros e rejeitar nomes de projetos inválidos. Dois
testes HTTP novos cobrem sincronização realista com estado final e tentativa
de incluir path em nome de projeto. **Sem teste no HA até uma RC posterior.**

## Operações observáveis — desenvolvimento posterior à RC11

A branch privada agora implementa `GET /api/operations`, autenticado e
somente leitura. Ele mostra até 20 operações recentes extraídas de uma janela
limitada do histórico local, com apenas `operation_id`, ação, estado e hora.
Não devolve parâmetros de requisição, SHA, credenciais, paths, `actor` ou
linhas brutas. Ausência do histórico devolve lista vazia; histórico inacessível
ou link simbólico devolve `503 audit_unavailable`. São previstos testes
HTTP para autenticação, resultado da pré-verificação, sanitização e symlink,
sem execução de ações de publicação.

Esse endpoint **não é um sistema completo de filas nem altera a situação da
RC11 instalada**; é avanço incremental da observabilidade na branch.
**Testes novos não executados nesta sessão**, e nenhuma RC pública foi criada.

## Continuação — executor externo de builds (ARTESAO-BUILDER-002)

Na mesma branch isolada, foi acrescentado `artesao_isolated_executor.py`. Ele separa **plano somente leitura** e **execução expressa numa VM descartável dedicada**, exigindo política fixada em SHA e versão, checkout Git íntegro/limpo, cache npm offline e Docker local na VM. Usa scripts oficiais pinados para recibo real, origem HA/Debian, imagens distintas arm64/amd64 e checksums. Não cria versão nova, não modifica source/HA/Forja, não publica nem instala. O arquivo da política é declaração do operador e **não prova isolamento físico**; validação real da VM/firewall permanece obrigatória antes de usar `--execute`.

O executor tem `tests/test_factory_runner_artesao_isolated_executor.py` com **15 testes novos**. Na receita do Dockerfile do Factory Runner, o script é copiado **só para o estágio de testes**, e não para a imagem final HA. **Ainda não houve execução da suíte nem build real em VM** nesta entrega. Mais detalhes em `ARTESAO-BUILDER-002.md`. O bloqueio da fonte 0.2.0-dev.28 com origem diferente permanece ativo.


**Estado:** desenvolvido em branch isolada; **nenhum pacote criado, compilado ou publicado**. O adaptador atual é de **pré-verificação**, não um executor da esteira completa. Rastreabilidade: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2).

## Documentos e scripts reais consultados

- Fonte: `mmcromero/fabricacao_e_orcamentos:main`; commit consultado `673cc37aa41339f5c3bd91435e717c48948060db`.
- Destino HA/arquivos públicos Debian: `mmcromero/fabricacao-e-orcamentos-ha:main`; commit consultado `a8a78322170de2692ba9c59c94b5069b6425f602`.
- `scripts/release-evidence.py`: gera recibo externo ao Git **somente após** `npm run build`, `npm test`, validação de ferramentas, testes operacionais e checksums de schemas, para SHA exato e checkout limpo.
- `scripts/prepare-pilot-release.py`: verifica versão/base e ancestralidade de `pilot/core-base.json`; exporta o piloto, não o legado.
- `scripts/prepare-distributions.py`: **exige recibo real** com `sourceCommit`, `checks` aprovados e `schemaChecksums`; produz fontes/manifestos dos dois destinos. Debian usa `app/`, `compose.yaml`, `manage.py`, `operation-policy.json`, e pode exigir imagem AMD64 auditada; sem imagem, somente `compose-source`.
- `scripts/prepare-ha-aarch64.py`: **exige** imagem real `linux/arm64`, labels corretos, runtime, manifesto e checksum; gera pacote HA em `apps/artesaos-piloto/` com runtime.tar.gz e `arch: aarch64`; sem build real, este pacote **não existe**.
- `scripts/prepare-forja-windows.py`: prepara ZIP de atualização da Forja somente com descriptor aprovado, arquivos e hashes já validados; não atualiza a máquina.
- `apps/umdoislab/pilot/POLITICA-DE-VERSOES.md`, `apps/umdoislab/distribution/docs/HOME-ASSISTANT.md`, `.../DEBIAN.md`, `docs/operacao/POLITICA_SEGURANCA.json` (Nível 1, autorização expressa) e documentação de arquitetura do Runner.

## Perfil e segurança

O perfil `projects/artesao_digital.json` usa o modo **`artesao_package`**. Declara:
- Repositórios e branch `main` exatos, sem seleção de URLs ou comandos pelo cliente.
- Arquivos versionados de origem (`artesao-release.json`, piloto, base) e arquivos públicos da distribuição HA + ponteiro da Forja.
- **Cinco receitas oficiais fixadas pelo SHA Git blob**, de modo que qualquer mudança de script gere `TRUSTED_RELEASE_RECIPE_CHANGED` até nova revisão.

`artesao_adapter.evaluate_artesao` **somente lê blobs Git de SHAs verificados**. Confere:
- Origem pinada continua sendo HEAD aprovado; versão comum coincide com `pilot/config.yaml` e slug `artesaos_piloto`/aarch64 preservados.
- `core-base.json` contém commit ancestral da origem; versão do núcleo corresponde ao `package.json` no commit-base.
- Metadados e proveniência públicos do HA compatíveis; ponteiro Debian/Forja válido; comparação separada de versões HA e Debian.
- Reuso de versão do HA com origem divergente é bloqueado; versões inferiores a qualquer destino são bloqueadas; mudança de schemas exige revisão de migração.
- Arquiteturas são **distintas**: HA `linux/arm64`, Debian `linux/amd64`; não reutilizar imagem nem chamar HA contingência de primária.

## Resultado confirmado apenas por inspeção dos arquivos públicos

Na consulta, a fonte `main` tinha **0.2.0-dev.28** e SHA `673cc37aa41339f5c3bd91435e717c48948060db`. O pacote público HA também era **0.2.0-dev.28**, mas seu `release.json` declarou origem **`e6b48ed1149a0e06fb74c268acfd20253306035c`**. Portanto, **preflight da fonte atual deve indicar `VERSION_ALREADY_PUBLISHED_WITH_DIFFERENT_SOURCE`**. O ponteiro Debian público consultado indicava **0.2.0-dev.26**, independentemente da versão HA. Não reutilizar dev.28 para outra árvore.

Esses valores são uma **fotografia do Git**, não confirmação da versão instalada na Forja 01 nem no Raspberry.

## Limites deliberados da entrega

`GET /api/projects` pode apresentar `verified_dual_distribution_plan`. `POST /api/preflight` devolve relatório de ambos os destinos, com `blocking_errors`, requisitos pendentes e **`state: PLAN_ONLY_NO_PACKAGE`**. O mesmo preflight também é aplicado na sincronização Git do perfil.

**`POST /api/prepare` é bloqueado:** retorna `eligible: false`, sem criar diretório/artefato de release e sem executar script, compilador, Docker, Git push, Actions ou merge. `POST /api/prepare-declarative` também recusa o uso do exportador do Avisaqui.

A liberação de **pacotes reais** requer uma etapa posterior de executor confiável/isolado que implemente: recibo real do mesmo SHA, compilação ARM64 e AMD64, checksums, proveniência, identificação de schema, escopo e autorização de publicação por versão/commit/destino. O HA atual nega sandbox de código não confiável (`bwrap` + Landlock indisponíveis); **não dar ao Runner privilégio de host/Docker** para contornar isso. Um executor confiável independente, autorizado e com resultados verificáveis é o caminho a estudar antes de abrir escrita.

## Testes incluídos

`tests/test_factory_runner_artesao_adapter.py`: nove testes com repositórios Git sintéticos locais para planos de duas distribuições, reutilização de versão, mudança de schema, alteração de script, SHA stale, perfil malicioso, API/preparação, sincronização e ausência de metadados. O estágio Docker de validação já usa `unittest discover`, e o novo módulo `artesao_adapter.py` foi incluído no `COPY` e no `py_compile`.

**Os testes ainda não foram executados neste atendimento:** GitHub Actions proibido e ambiente local disponível sem acesso de rede para obter a árvore privada. Não tratar simples presença dos testes como `PASS`; requer executar suite em executor autorizado, revisar resultados e corrigir antes de solicitar merge/publicação.

**Alterações restritas** a `factory-runner-add-on/` da fonte privada. Nenhuma modificação em `mmcromero/fabricacao_e_orcamentos`, `mmcromero/fabricacao-e-orcamentos-ha`, `mmcromero/hassio-addons`, servidores, Raspberry, Forja ou credenciais.
