# Factory Runner RC9 — Artesão Digital como segundo projeto

**Situação:** implementação em branch isolada, ainda **não publicada** no catálogo nem instalada no Home Assistant. Registro principal: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2).

## Fontes verificadas antes da integração

- **Origem privada:** `mmcromero/fabricacao_e_orcamentos`, branch `main` (SHA observado `673cc37aa41339f5c3bd91435e717c48948060db`). A antiga branch `codex/artesao-digital-evolucao` estava 282 commits atrás da `main`, sem commits novos em relação a ela, portanto não foi usada.
- **Distribuição própria do Home Assistant:** `mmcromero/fabricacao-e-orcamentos-ha`, branch `main` (SHA observado `a8a78322170de2692ba9c59c94b5069b6425f602`). **Não** presumir que a pasta da distribuição esteja em `hassio-addons/`; esse catálogo publica o próprio Factory Runner e o Avisaqui.
- **Identidade do produto:** `apps/umdoislab/artesao-release.json` na fonte informa `0.2.0-dev.28`; a distribuição Home Assistant possui `apps/artesaos-piloto/config.yaml` também em `0.2.0-dev.28`. A instalação do Artesão Digital na Forja 01 é ambiente primário e o Home Assistant é contingência; a RC9 não modifica nenhum deles.
- **Processo do produto:** `scripts/prepare-distributions.py` exige recibo de validação e SHA da fonte, inclui Debian e Home Assistant, schema/versão própria e procedimentos de migração. `scripts/prepare-pilot-release.py` valida referência do núcleo. **Não é a política `active_package` e o fluxo de RC do Avisaqui.**

## Integração segura

1. Perfil novo e versionado `projects/artesao_digital.json`, com `mode: sync_only`, repositórios exatos, refs `main` e caminho `apps/umdoislab/artesao-release.json`. Não inclui shell, exportador, comandos, segredo nem campos de publicação.
2. `rc_fastlane.load_profile()` valida **conjunto exato de chaves**, ID, repositórios, branches e arquivo de versão, recusando escapes `../`, URLs escolhidas pelo cliente e opções de exportação injetadas. `evaluate()` recusa perfis sync-only, mesmo se chamado diretamente.
3. `workspace_sync.synchronize()` conserva validação GitHub REST SHA = SHA do Git clonado, TLS, token privado, `--no-checkout`, ausência de scripts e proteção dos snapshots. Para perfil sync-only, lê **somente um blob JSON do commit de origem confirmado**, valida o campo `version` e retorna `SYNC_ONLY_NO_PREPARATION`. Não depende do Avisaqui nem executa exportação.
4. API `/api/projects` identifica que a preparação do Artesão Digital está desativada. Rotas `/api/preflight` e `/api/prepare` recusam-no. Na inicialização, a sincronização registra `[WORKSPACE] SYNCED/UNCHANGED: project=artesao_digital ...` e `[WORKSPACE] SYNC_ONLY: project=artesao_digital package_preparation_disabled`. Mesmo com `workspace_auto_prepare=true` por erro, fica `PREPARE_BLOCKED_BY_PROFILE`.
5. O perfil do Avisaqui, os checks de política e preparação declarativa existentes permanecem inalterados. Na RC8, `workspace_sync_enabled` já percorria todos os perfis aprovados; com o novo perfil deverá informar `approved_projects=2`.

## Limites de segurança e testes

- **Cinco testes de regressão adicionados** à suíte Git local `tests/test_factory_runner_workspace_sync.py`: aceitação do perfil e do blob versionado, idempotência, rejeição de perfil/path/repo inválidos, ausência de versão, e bloqueio de preflight/preparação inclusive quando solicitada automaticamente.
- **A execução da suíte em Docker/ARM64 ou Python real nesta revisão ainda não ocorreu.** Não declarar testes novos PASS antes do build da RC9 no Supervisor ou de execução comprovada em runner de laboratório. A RC8 teve testes e sincronização reais previamente aprovados, mas isso não comprova o código novo da RC9.
- **Sem autorização de publicação nesta etapa:** manter candidata em PR; não fazer merge, Actions, instalação, publicação de projetos ou alterações de token.
- O perfil `sync_only` é deliberado: o Artesão Digital **sincroniza e fica visível**, mas ainda não prepara pacote. Converter para modo de preparação exige um adaptador próprio que respeite `scripts/prepare-distributions.py`, `artesao-release.json` e recibos reais, com testes e gate de autorização novos.

## Homologação futura

Após publicação e instalação autorizadas da RC9 no Raspberry, manter `workspace_sync_enabled=true`, `workspace_auto_prepare=false` e o token GitHub de leitura atual (se der acesso ao repositório privado do Artesão Digital). Esperar `[WORKSPACE] START: approved_projects=2`, um resultado individual para `avisaqui` e outro para `artesao_digital`, e `[WORKSPACE] FINISHED: approved_projects=2`. Falha de um perfil não pode afetar o outro. Não reiniciar outros add-ons.
