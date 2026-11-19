# Factory Runner RC4 — validação técnica (19/11/2026)

Estado: **RC4 VERSIONADA / PR #45 / PUBLICAÇÃO NO CATÁLOGO AUTORIZADA PELO PROPRIETÁRIO EM 19/11/2026; INSTALAÇÃO NÃO AUTORIZADA**.

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

## Correção de procedimento — P0 consultada em 19/11/2026
- Fontes obrigatórias lidas: `AGENTS.md`, `CONTRIBUTING.md`, `docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md`, `factory-runner/OPERACAO-ESTEIRA.md` e GOV-STD-001 v0.9 / GOV-BLK-002 v0.3.
- **Retirada a alegação de impedimento automático por falta de Docker ARM64/QEMU/Actions externos.** O add-on tem `Dockerfile`, sem `image` pré-compilada, e pode ser construído pelo Supervisor no Raspberry na fase de instalação autorizada. Esse teste não deve ser simulado como PASS antes da instalação.
- A falha Bubblewrap é **bloqueio específico de `/api/prepare` no HA**, não impedimento automático da candidata de leitura/diagnóstico nem de uma futura publicação autorizada da RC restrita. A correção exige diagnóstico real da política, sem afrouxar segurança. A rota permanece fail-closed.
- Os testes dirigidos Python para o código RC4 ainda precisam de execução real (não substituir por simples inspeção). A ausência de acesso a Docker ARM64 externo não deve bloquear os demais testes nem o encaminhamento da candidata.
- Estado adequado antes da ordem atual: RC4 em draft; após ordem do proprietário, publicação no catálogo autorizada, instalação continua não autorizada. Não declarar NO-GO da publicação exclusivamente por hardware/CI.

## Critérios de liberação da candidata
1. Diagnóstico de política do HA com causa exata do bloqueio e solução segura comprovada, ou manutenção explícita do modo somente leitura sem promessa de preparar pacotes.
2. Testes offline dirigidos reais, integração HTTP e negativas de acesso com evidências; build ARM64 pelo Supervisor na instalação autorizada, exceto risco técnico específico devidamente comprovado.
3. Conferência de SHA, manifesto, versão e alterações somente em `factory-runner/`.
4. Publicação desta RC restrita autorizada expressamente pelo proprietário; instalação e eventual liberação de funções adicionais exigem autorização e testes próprios.

Próximo responsável: desenvolvimento/infraestrutura para solução do isolamento e testes em ambiente compatível; Segurança para gate; proprietário exclusivamente para autorização final. Não foram executados deploy, instalação, merge, Actions ou testes Docker/HA nesta sessão.

## Verificação complementar do lote (19/11/2026)
- GitHub API: árvore da branch e diferença contra `main` conferidas; versões e arquivos do candidato recuperados da branch exata.
- **10/10 verificações estáticas dirigidas PASS**: versão RC4, teste offline obrigatório no Dockerfile, presença da nova regressão, recusa de tipo inválido, de backslash e de refs ambíguas, HTTP 403 para operações privilegiadas, recusa de root, recusa de ausência de Bubblewrap e ausência de imagem pré-compilada. Verificação estática **não equivale à execução dos testes Python**.
- Execução local tentada com `git ls-remote https://github.com/mmcromero/hassio-addons.git HEAD`: **FAIL por DNS** (`Could not resolve host: github.com`). O conector GitHub permite leitura/escrita de código, mas não fornece execução shell ou Docker, e o shell disponível não alcança o GitHub para baixar a árvore privada. A infraestrutura real não foi alterada.
- Alternativa já existente e proporcional: o `Dockerfile` possui `python3 -m unittest discover ...` como etapa obrigatória de build. Na instalação autorizada, o Supervisor pode realizar o build e o teste na arquitetura real, sem Actions ou emulador externo. **Essa instalação NÃO está autorizada nesta tarefa; não executá-la para obter PASS.**
- Este registro não considera a falta de ARM64 externo um NO-GO; a pendência efetiva de execução Python existe por limitação do ambiente acessível, não do projeto. O bloqueio Bubblewrap é independente e restrito a `/api/prepare`.
