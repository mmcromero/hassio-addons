# Changelog

## 0.1.0-rc.7 — Sincronização privada GitHub somente leitura (CANDIDATA EM BRANCH)

- Sincroniza os repositórios **pré-aprovados no perfil** em volume privado do Factory Runner, usando HTTPS GitHub, token fine-grained de leitura configurado **apenas no Home Assistant** e verificação SHA de branches Git contra API remota.
- É **opt-in**: `workspace_sync_project` vazio preserva comportamento atual; `github_read_token` é segredo mascarado; `workspace_auto_prepare` inicia em `false`. Sem habilitação, não faz rede nem clonagem extra no startup.
- Git usa `--no-checkout` e não executa scripts/hook/submódulo nem envia token na URL, processo Git ou logs. Credencial existe somente em arquivo temporário `0600`, apagado ao concluir clone.
- Bloqueia diretórios desconhecidos, SHA divergente, URLs fora do perfil, volumes simbólicos e política fechada; atualizações preservam snapshots anteriores e usam troca recuperável. Trabalho isolado pela trava global da API, sem publicar ou alterar outros serviços.
- **Laboratório:** 18 testes novos PASS com Git local real e usuário sem root; conjunto local disponível 45 PASS; sintaxe shell/Python e YAML verificados. **Não executados:** clone GitHub privado real com token, build Docker da RC7 nem HA físico.
- **Avisaqui na data da verificação:** pacote `AVISAQUI-PACOTE-009` fechado e aguardando homologação; deve sincronizar somente leitura e **recusar preparação de nova RC**, sem reabrir política.
- Publicação na loja e instalação exigem autorização própria. RC6 da loja e teste E2E no HA permanecem inalterados.


## 0.1.0-rc.6 — Teste E2E interno sem portas expostas (PUBLICADA; E2E HA PASS)

- `factory_e2e_probe.py`: durante a inicialização, cria **apenas repositórios sintéticos temporários** e executa a API real por loopback efêmero `127.0.0.1:0`, com token de teste gerado no processo isolado. O token real do add-on não é transmitido ao teste.
- Confere autenticação, preflight com política aberta, preparação declarativa pela rota padrão, blobs e SHA-256, proveniência, não alteração dos repositórios, bloqueio de publicação, SHA inválido e pacote fechado. Apaga automaticamente os arquivos sintéticos.
- `run.sh` chama o teste com usuário sem root e ambiente limpo antes da API principal. O log apresenta `[E2E] PASS` ou `[E2E] BLOCKED`; falha do teste não libera operações nem altera as políticas de segurança.
- Dockerfile copia o probe para a **imagem final**, compila-o e executa os testes de regressão no estágio de validação. Sem GitHub Actions nem dependência de download de projeto.
- **Laboratório real:** execução direta sob `nobody`: `[E2E] PASS`; 4/4 testes novos PASS; conjunto local de 56/56 testes PASS. Código verificado pelos hashes Git, sem Docker/ARM64 neste laboratório.
- **HOMOLOGAÇÃO PARCIAL REAL:** o último bloco de logs fornecido pelo operador confirmou `[E2E] PASS` e `[API] READY` no HA. Esse PASS cobre apenas pacote sintético e política interna, não provisionamento de projetos privados.
- **PUBLICADA:** RC6 no catálogo por PR #48 (commit `55363aecb421cc4cd7c4c2976325f087f622e5b9`), sem alteração de outros add-ons; instalação inferida pelo log E2E e versão exata a conferir pelo Supervisor.


## 0.1.0-rc.5 — Preparação declarativa sem execução de scripts (CANDIDATA EM BRANCH)

- A rota autenticada `POST /api/prepare` utiliza exportação declarativa quando o perfil confiável possui receita aprovada; scripts externos **não** são executados nessa operação. A rota alternativa `/api/prepare-declarative` permanece disponível para diagnóstico dirigido.
- Sem receita aprovada, o caminho legado continua fail-closed com Bubblewrap obrigatório. `/api/corrigir-issue` e publicação/commit/push remoto permanecem bloqueados; nenhuma permissão do Home Assistant foi ampliada.
- Núcleo com leitura Git por SHA fixado, mapeamento/condições validados, rejeição de symlinks, controle de tamanho/quantidade/tempo, hashes SHA-256, manifesto e proveniência. Workflow compartilhado somente quando o commit público fixado comprova compatibilidade.
- **Execução local real:** 18/18 testes do núcleo (blobs idênticos aos da branch), 19/19 testes de preflight (após correção das fixtures), 8/8 testes HTTP dirigidos e 3/3 testes HTTP com preflight real, Git sintético e preparação por `/api/prepare`. O exportador canônico pinado e o novo método geraram 29 arquivos de pacote + 1 workflow compartilhado com bytes e proveniência idênticos em fixture sintética, e `--verify` passou.
- **Verificações da fonte:** 135/135 caminhos de distribuição equivalentes à receita original no snapshot real e 1 workflow compartilhado separado; blobs Git de código/testes conferidos; os programas dependentes de Landlock e planejador pré-existentes permanecem.
- **Não concluído:** execução da suíte completa em Docker, build ARM64 e homologação do funcionamento no Home Assistant físico. Nenhuma execução de GitHub Actions, merge, publicação na `main`, instalação no Raspberry ou liberação de execução de código não confiável foi realizada.
- **Status:** CANDIDATA DE DESENVOLVIMENTO, não instalada nem homologada; publicar somente após revisão do diff, gates da norma de catálogo e autorização aplicável.


## 0.1.0-rc.4 — Publicação autorizada para teste (19/11/2026; instalação independente)

- Reforço fail-closed no carregamento de perfis: tipos incorretos, refs com segmentos vazios/dot segments, prefixos ambíguos e barras invertidas na allowlist são recusados.
- Cobertura de regressão adicionada para os casos acima. Execução da suíte completa ainda **não comprovada** nesta sessão.
- Bloqueio Bubblewrap/AppArmor no Raspberry **não resolvido**; nenhuma flexibilização de isolamento ou concessão de privilégios foi feita.
- Publicação na loja autorizada expressamente pelo proprietário em 19/11/2026. Testes Python integrados e build/ensaio no HA ainda sem PASS; a imagem executa a suíte Python obrigatoriamente no estágio de validação do Dockerfile durante o build do Supervisor. Instalação/atualização não autorizadas nesta tarefa.


## 0.1.0-rc.3 — Candidata de teste do worker controlado (19/11/2026; homologação HA pendente)

- Worker de somente leitura incorporado à fonte privada; 3 tarefas: diagnosticar segurança do próprio processo, conferir perfil instalado e pré-verificar projeto confiável.
- Rota autenticada `POST /api/worker/run`; recusa outras operações, parâmetros extras, projetos/SHAs inválidos, erros do worker e falhas de auditoria.
- Subprocesso sem root, ambiente mínimo sem credenciais, `python -I`, tempo máximo e limites de recursos por processo; não há isolamento comprovado para executar código não confiável.
- Diagnóstico no log do perfil AppArmor e flags do processo, sem token herdado; verificação de inclusão do worker na imagem final. Não altera a política de segurança do Home Assistant.
- Laboratório local: 7 testes do núcleo, 12 testes de rota HTTP com trecho idêntico ao versionado, 3 testes do lançador com trecho idêntico ao versionado, execução não-root real de diagnóstico e recusa de operação proibida, todos PASS. A suíte integrada da imagem e Docker/ARM64/HA ainda estão pendentes.
- `/api/prepare` continua a exigir Bubblewrap, atualmente BLOCKED no Raspberry. Fechamento e correção de Issues continuam HTTP 403. Porta externa não mapeada.
- `config.yaml` identifica a candidata `0.1.0-rc.3`. A publicação exige conferência do commit em `hassio-addons:main/factory-runner/`; a instalação e a homologação no Home Assistant são etapas separadas.

## 0.1.0-rc.2 — Candidata de pré-verificação multi-projeto (19/11/2026)

- Factory Runner permanece add-on independente do Avisaqui.
- Perfis JSON por projeto; Avisaqui é somente o primeiro perfil registrado.
- API autenticada somente leitura: lista de projetos e preflight por SHA fixado.
- Dockerfile incorpora Git, CLI de preflight e perfis versionados.
- Operações de publicação, push/merge e alteração autônoma permanecem bloqueadas.
- Porta externa 9876 continua não mapeada e bind localhost; nenhum deploy.

- Correção da fixture de árvore Git congelada e de refs RC com subdiretórios.
- Git sem credenciais herdadas; exportador com HOME temporário e Python isolado.
- Testes reais de HTTP/Git, preparação sem push, pin e hashes verificados.
- CA opcional por secret de build, sem desativar TLS ou incorporar CA à imagem.
- Smoke autenticado/reinício com emulação opcional em userspace.

- Sandbox obrigatório: user/PID/network/IPC/UTS namespaces, capabilities zeradas,
  origem e .git somente leitura, ambiente limpo, UID não-root e controles RLIMIT.
- Helper de limites em processo novo, monitor de saída que falha fechado,
  encerramento de grupo e tratamento explícito de indisponibilidade na CLI/API.
- Inicialização protege contra symlinks e permite travessia mínima do volume
  ao UID runner, preservando options.json; código/imagem legíveis pelo serviço.
- Provas reais de isolamento/consumo separadas dos testes com mocks e da
  integração Git funcional; negativa de namespace não recebe PASS artificial.
- Corrigida ordem de NPROC: bootstrap confiável cria o namespace antes de
  aplicar o teto de 32 processos ao exportador. Prova positiva de isolamento
  e controles executada no Codex, sem desativar Bubblewrap ou limites.

**Evidências e impedimentos no PR #43; HA não homologado.** O sandbox só é
considerado disponível após prova real. Cgroup agregado e quota rígida ainda
exigem ambiente/política operacionais; não fecha pacote nem publica.


## 0.1.0-rc.1 — Candidato restrito (18/11/2026)

- Integração estrutural ao catálogo central Home Assistant.
- Registro próprio no cadastro da loja e na seleção de build ARM64 manual.
- API com autenticação obrigatória e operações privilegiadas bloqueadas.
- Remoção de credenciais fixas e redução de dependências e volumes.
- Testes de regressão de segurança incluídos para execução isolada.

**Não homologado no hardware. Não equivale à versão funcional do worker.**
