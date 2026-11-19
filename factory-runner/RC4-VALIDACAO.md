# Factory Runner RC4 — validação técnica (19/11/2026)

Estado: **RC4 VERSIONADA EM BRANCH ISOLADA / PR #45 DRAFT / NÃO PUBLICAR / NÃO INSTALAR**.

## Proveniência
- Branch isolada: `release/factory-runner-rc4-validation`, criada a partir de `main` em 19/11/2026.
- Base observada no catálogo: `factory-runner/config.yaml` com `0.1.0-rc.3`.
- Não se identificou branch RC4 anterior no catálogo nem no Orquestrador nas buscas realizadas.
- Após a revisão inicial foi preparada a candidata `0.1.0-rc.4` na própria branch; PR em rascunho: https://github.com/mmcromero/hassio-addons/pull/45. **Sem build, instalação, homologação ou aprovação.**

## Evidências verificadas em leitura
1. Código `runtime_probe.py`: o resultado de falha não inicia isolamento; a sonda retorna 0 por desenho para permitir API de diagnóstico, mantendo `/api/prepare` fail-closed.
2. Log de execução informado: `bubblewrap probe exit 1 (bwrap: Failed to make / slave: Permission denied)`. O erro revela incompatibilidade entre a operação de namespace/mount e a política efetiva do container HA, mas não identifica isoladamente a causa configuracional exata.
3. `controlled_worker.py`: apenas `diagnose`, `profile` e `preflight` são permitidos; recusa root e tarefas não autorizadas; resultado diagnóstico declara `sandbox_ready: false`.
4. `server.py`: `/api/fechar-pacote` e `/api/corrigir-issue` devolvem 403 após autenticação; `/api/prepare` depende de sandbox. A fonte exige autenticação e mantém publicação desativada.
5. `Dockerfile`: testes Python durante build; não é prova de execução ARM64 real.

## Problema confirmado e tratamento
- **BLOQUEIO AMBIENTAL**: a sonda Bubblewrap retornou permission denied no HA/Raspberry (evidência operacional reportada). Não remover `--unshare-*`, não habilitar execução sem sandbox, não afrouxar AppArmor/seccomp/capacidades para obter PASS artificial.
- **LACUNA DE EVIDÊNCIA**: testes completos, build ARM64, cgroup/quota e integração HA da candidata RC4 ainda não executados/verificados nesta validação.
- **IDENTIDADE DA CANDIDATA**: `factory-runner/config.yaml` agora marca `0.1.0-rc.4` somente nesta branch. A `main` continua RC3; candidata não homologada.

## Correções aplicadas (não qualificadas por execução)
- `rc_fastlane.py`: validação fail-closed para tipos incorretos de campos de perfil, prefixos de distribuição ambíguos, referências Git com segmentos `.`/`..`/vazios e barras invertidas em caminhos compartilhados.
- `tests/test_factory_runner_fastlane.py`: regressão para nove casos inválidos de perfis, ainda sem execução da suíte integrada neste ambiente.
- `config.yaml` e `CHANGELOG.md`: versão e histórico RC4.
- Comparação `main...release/factory-runner-rc4-validation`: cinco arquivos modificados/adicionados, todos sob `factory-runner/`; nenhuma mudança em outros add-ons.
- Leitura da página de apps instalados no HA confirmou que o Factory Runner **atual** aparece em execução; isso não prova RC4 instalada, nem sua versão.

## Critérios de liberação da candidata
1. Diagnóstico de política do HA com causa exata do bloqueio e solução segura comprovada, ou manutenção explícita do modo somente leitura sem promessa de preparar pacotes.
2. Testes offline reais, integração HTTP, testes de negativa de acesso e build ARM64 com evidências anexadas.
3. Conferência de SHA, manifesto, versão e alterações somente em `factory-runner/`.
4. Revisão de Segurança e autorização específica do proprietário antes de qualquer publicação ou instalação.

Próximo responsável: desenvolvimento/infraestrutura para solução do isolamento e testes em ambiente compatível; Segurança para gate; proprietário exclusivamente para autorização final. Não foram executados deploy, instalação, merge, Actions ou testes Docker/HA nesta sessão.
