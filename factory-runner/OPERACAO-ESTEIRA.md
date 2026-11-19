# Factory Runner — Worker controlado e pré-verificação multi-projeto

**Estado:** candidata RC3 (`0.1.0-rc.3`) para homologação no Home Assistant; o isolamento do Bubblewrap segue bloqueado no HA até evidência em contrário. **Produto independente** dos projetos atendidos.

## O que já existe

- `GET /api/status` — autenticado, informa preflight somente leitura.
- `GET /api/projects` — autenticado, mostra apenas perfis JSON previamente configurados.
- `POST /api/preflight` — autenticado, aceita exatamente `{"project":"avisaqui","expected_source_sha":"<SHA-40>"}`. Verifica referências e política dos checkouts locais, sem escrever.
- `POST /api/worker/run` — autenticado, executa SOMENTE tarefas de leitura pré-definidas: `{"task":"diagnose"}`, `{"task":"profile","project":"avisaqui"}` ou `{"task":"preflight","project":"avisaqui","expected_source_sha":"<SHA-40>"}`. Rejeita campos extras e não aceita shell, exportadores, npm, scripts ou caminhos arbitrários. O processo filho recebe ambiente sem token e limites por processo; não é sandbox de código não confiável.
- `POST /api/prepare` — autenticado, aceita a mesma estrutura. Primeiro executa o preflight; se elegível, cria um checkout isolado, usa o exportador aprovado e verifica o pacote. **Não publica, não faz push e não permite ao cliente escolher caminhos de destino.** Uma única tarefa ativa por vez.
- `POST /api/fechar-pacote` e `POST /api/corrigir-issue` continuam bloqueados (403). Token não autoriza publicação.
- CLI `python3 /app/rc_fastlane.py --profile /app/projects/avisaqui.json ...` permite preparar exportação em checkout isolado, somente quando a política permitir; não publica.

## Pré-requisito de uso

O Runner não contém credenciais Git nem clona repositórios privados automaticamente. Para a API funcionar, um operador deve providenciar checkouts de leitura **confiáveis e atualizados** em:

```
/data/factory-runner/workspaces/avisaqui/source
/data/factory-runner/workspaces/avisaqui/distribution
```

Esses caminhos pertencem ao volume privado do add-on; não montar /config, Docker socket ou diretórios de produção. Para outro projeto, cadastrar perfil separado e criar `<id>/source` e `<id>/distribution` após aprovação de escopo. Checkouts precisam conter as refs `refs/remotes/origin/*`. O preflight exige o SHA exato que foi verificado no GitHub. O Avisaqui é somente um exemplo real.

**Atenção:** os caminhos acima são pré-requisitos; não são criados pela API. Sem eles, o endpoint devolve `503 workspace_or_export_unavailable`. Sem isolamento, prepare também falha com 503 e auditoria; nunca há fallback para Python não isolado. Não comunicar fechamento automático enquanto os portões não forem comprovados.

## Segurança

- API somente em `127.0.0.1` dentro do contêiner; nenhuma porta mapeada ao host.
- Token forte de pelo menos 32 caracteres, somente em `/data/options.json`.
- O diagnóstico de startup é executado com ambiente mínimo; não herda o token do serviço. O log expõe `[ISOLATION]` para Bubblewrap, `[WORKER]` para os atributos AppArmor/capabilities do próprio worker, e `[API] READY` após o bind local.
- No HA real, `bwrap: Failed to make / slave: Permission denied` foi observado na RC2. O diagnóstico da RC3 NÃO libera `SYS_ADMIN`, AppArmor, Docker socket ou o isolamento para exportadores.
- Nada de URL pública, upload de arquivo executável, rota de comandos arbitrários, GitHub Actions, `git push` ou auto-merge.
- Logs de auditoria sanitizados e gravados sob `/data/factory-runner/audit.jsonl`.
- Perfil JSON versionado e validado; cliente não escolhe paths arbitrários.
- Não encaminhar credenciais para subprocessos de testes/exportação.

## Verificações complementares (não são gate genérico de publicação)

A norma P0 vigente é `hassio-addons:main/CONTRIBUTING.md`. Conferir diff, sintaxe, testes dirigidos, configuração, segurança e escopo. Como este add-on utiliza Dockerfile sem imagem pré-compilada, o Supervisor executa o build ARM64 durante a instalação/atualização no HA. Buildx/QEMU externo abaixo é diagnóstico opcional quando houver risco técnico comprovado, não requisito obrigatório de publicação da RC de teste.

```sh
python3 -m unittest discover -s factory-runner/tests -p 'test_factory_runner_*.py' -v
python3 -m py_compile factory-runner/*.py
docker buildx build --platform linux/arm64 --load -t factory-runner:rc3-arm64 -f factory-runner/Dockerfile factory-runner/
python3 factory-runner/tests/smoke_container.py --image factory-runner:rc3-arm64 --platform linux/arm64 --sandbox-probe --security-report /tmp/factory-sandbox-arm64.json
```

O PR #43 registra a execução desta tarefa com SHA, contagens e imagens reais.
Há testes HTTP e Git reais com fixtures temporárias, distintos dos mocks de
unidade. ARM64 pode ser compilado pelo Supervisor no Home Assistant. Não declarar PASS
por compilação de sintaxe ou inspeção de Dockerfile.

## Critérios para uma versão instalável com publicação

Antes de publicar apenas `factory-runner/` em `hassio-addons:main`, cumprir os testes proporcionais, validações de configuração, distribuição e autorização da norma P0. No HA, registrar o resultado real de build ARM64, isolamento e inicialização; somente liberar a execução de preparação quando os limites de CPU/RAM e acesso aos checkouts estiverem comprovados. A próxima versão do Factory Runner é independente da `0.1.20-rc.8` do Avisaqui. Essa fase oferece **worker de leitura e preflight**, com preparação local apenas quando o isolamento realmente estiver disponível; **não fecha nem publica pacotes**.

## Ambiente de laboratório e limites de segurança

- Em proxy gerenciado, o Dockerfile aceita CA confiável opcional com
  `--secret id=build_ca,src=/caminho/ca.pem`. TLS e assinaturas APK continuam
  verificados; o secret não fica na imagem. Não usar `--no-check-certificate`.
- BuildKit oficial inclui `buildkit-qemu-aarch64` para emulação em userspace.
  O Codex pode usar builder `docker-container` isolado e o comando Buildx acima;
  o smoke aceita `--emulator /caminho/buildkit-qemu-aarch64`, montado só no
  contêiner de teste. Não instala binfmt no kernel/host. Exigir saída aarch64 real.
- Sem capacidade local, consultar a alternativa Codespaces documentada no
  Avisaqui; verificar cota/autorização antes de iniciar qualquer recurso.
- O smoke usa dados sintéticos, rede `none`, rootfs somente leitura, sem portas
  publicadas; confere autenticação, rotas bloqueadas, workspace ausente,
  auditoria e reinício. Solicita 1 CPU/256 MiB/128 PIDs quando cgroups existem;
  indisponibilidade fica explícita no resultado e não equivale a limites aprovados.
- `RUNNER_PREPARATIONS_DIR` é configuração do operador, nunca do cliente HTTP.
  Symlinks na raiz de preparação são recusados. Git recebe ambiente mínimo;
  o exportador usa Python isolado e ambiente limpo, sem credenciais herdadas.
- Blob aprovado e Bubblewrap são obrigatórios. O serviço perde root após ler
  as opções; o volume privado dá ao grupo runner somente travessia no diretório
  /data, preservando bytes, proprietário e modo de options.json. Inicialização
  recusa symlinks nos caminhos que administra antes de chown/install.
- O sandbox exige user/PID/network/IPC/UTS namespaces explícitos e remove todas
  as capabilities. Monta /source e bibliotecas/binários somente leitura, /target
  com escrita e /target/.git somente leitura (sem injeção de hooks/fsmonitor
  no Git posterior). Não monta /data, home, sockets ou credenciais do serviço.
- Limites iniciais por processo: CPU 120 s, AS 512 MiB, NPROC 32, NOFILE 128,
  CORE 0 e arquivo individual 256 MiB. Helper Python novo aplica RLIMIT antes
  de exec, sem preexec_fn no servidor multithread. Timeout 240 s e encerramento
  do grupo em violação/saída, inclusive após término do processo principal.
  NPROC é aplicado dentro do namespace por helper confiável somente leitura,
  antes de qualquer código do exportador. Aplicá-lo antes do Bubblewrap contava
  processos do UID do serviço no host e podia impedir a criação do namespace
  com EAGAIN. O teto permanece 32; os demais limites já valem no bootstrap.
- /tmp é tmpfs de 32 MiB. Saída é monitorada a cada 150 ms e ao final (256 MiB
  agregados), rejeitando symlinks, arquivos especiais e diretórios ilegíveis.
  **Monitoramento não é quota de filesystem**: pode haver pico entre amostras.
  RLIMIT por processo não é limite agregado de CPU/RAM/PIDs da árvore inteira.
- O teste funcional Git/HTTP usa exportador sintético explicitamente separado
  da prova de segurança. `probe_sandbox.py` testa o sandbox real como UID
  não-root. Namespace indisponível retorna IMPEDIDO/exit 2, nunca PASS/skipped;
  nenhuma falha do exportador é ignorada para aprovar a candidata.
- Em namespace disponível, a prova mede UID/capabilities, separação user/PID/net,
  bloqueio de credenciais/rede e escrita em /source/.git, RLIMIT, consumo de RAM,
  CPU, processos, FSIZE, tmpfs, timeout e monitor agregado, só com dados sintéticos.
  O smoke distingue 503 de workspace de 503 de falha da auditoria.
- Cgroups agregados, quota rígida e compatibilidade no destino continuam gates.
  O PR #43 registra o erro real de cada ambiente. Não inferir que o HA permite
  userns por existir Bubblewrap, nem que a negação do Codex prova falha no HA.
  Não habilitar sysctl, privilégios ou seccomp/AppArmor irrestrito para conseguir
  PASS. Infra deve fornecer execução isolada compatível e política restrita,
  ou avaliar executor externo sem Docker socket no HA. Sem isso prepare fica 503.

## Prova positiva no próprio Codex — correção NPROC

No atendimento posterior do proprietário, o probe foi executado também fora
do sandbox adicional do terminal (com autorização do executor), mantendo
Bubblewrap, todos os namespaces, capabilities zeradas e limites do exportador.
Não houve troca de máquina nem alteração de kernel/Docker/HA.

Após corrigir a ordem de NPROC, passaram de verdade: isolamento user/PID/net,
UID não-root, credenciais/rede do host inacessíveis, origem e .git RO, consumo
de memória/FSIZE/tmpfs/processos, CPU, timeout e monitor agregado. A preparação
HTTP com Git temporário e sandbox real também passou, sem substituir a função
por mock e sem escrita remota. Resultados vinculados ao SHA ficam no PR #43.
Essa prova não afirma disponibilidade sob a política padrão do contêiner HA
e não transforma monitor de disco em quota rígida/cgroup.

Rastreabilidade: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2), [PR #3](https://github.com/mmcromero/orquestrador-projetos-base/pull/3), `docs/governanca/FACTORY-RUNNER-ARQUITETURA-002.md`.
