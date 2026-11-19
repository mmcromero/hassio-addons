# Changelog

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
