# Factory Runner — Worker controlado e investigação AppArmor

**Estado:** RC3 **PUBLICADA E INSTALADA (startup diagnosticado)** em `mmcromero/hassio-addons:main/factory-runner/`, commit `db77d23fcfef78535240577388b2a654a0cb2d8a`; exportador não homologado. A branch privada `feat/factory-runner-esteira-001` prepara RC4 somente para consulta da ABI Landlock, **NÃO PUBLICADA**. Acompanhamento: Issue #2 do Orquestrador.

## Contrato do worker (primeiro lote da arquitetura híbrida)

O `controlled_worker.py` é um processo-filho limitado e de **somente leitura**, iniciado como usuário `runner`. Não é sandbox para código não confiável.

A API autenticada `POST /api/worker/run` aceita exclusivamente:

| Tarefa | Corpo JSON | Efeito |
| --- | --- | --- |
| `diagnose` | `{"task":"diagnose"}` | Lê perfil de `/proc/self/attr/current` e apenas `NoNewPrivs`, `Seccomp`, `CapEff`, `CapBnd` em `/proc/self/status` do próprio processo |
| `profile` | `{"task":"profile","project":"avisaqui"}` | Verifica integridade e metadados do perfil versionado na imagem (SHA-256). Não executa projeto |
| `preflight` | `{"task":"preflight","project":"avisaqui","expected_source_sha":"<SHA-40>"}` | Reutiliza o pré-flight Git existente, somente leitura; exige checkouts provisionados e confiáveis |

A rota exige Bearer. Retorna 401 sem autenticação, 400 para tarefas/parâmetros proibidos, 409 se ocupado e 503 se o worker falhar. A trilha de auditoria registra estado/ID, nunca credenciais ou corpo da chamada.

**Proteções:** lista fechada de tarefas, argumentos fixos (sem shell), Python `-I`, ambiente filho sem `RUNNER_AUTH_TOKEN` ou `GITHUB_TOKEN`, diretórios predefinidos, sem acesso a Docker/host e sem porta TCP pública. O processo-filho recusa root e impõe RLIMIT_CPU (12s), RLIMIT_AS (512 MiB), RLIMIT_FSIZE (1 MiB), RLIMIT_NOFILE (96) e RLIMIT_CORE (0), com timeout externo 50s e término do grupo. **São limites por processo; não são cgroups/quota agregada nem comprovam contenção de filhos maliciosos.**

**Continuam bloqueados:** `/api/fechar-pacote` e `/api/corrigir-issue` (403); exportadores e `/api/prepare` dependem de Bubblewrap funcional e falham fechados. Este worker não executa exportadores, npm, pytest, comandos arbitrários ou mutações Git. O antigo worker Avisaqui não foi modificado.

## Diagnóstico Landlock (fonte privada / RC4 NÃO publicada)

- `landlock_probe.py` consulta apenas a versão ABI via syscall 444 com `LANDLOCK_CREATE_RULESET_VERSION`; nenhum ruleset é criado ou aplicado.
- `controlled_worker.py --task diagnose` inclui `landlock.status`, `abi`, indicadores de capacidade de regras e os campos `enforcement_verified=false`, `safe_for_untrusted_code=false`.
- Mesmo em ABI suportada, isso **não libera** preparação ou execução de código externo. UDP só é controlável a partir de ABI 10, TCP a partir de ABI 4, IPC scoped a partir de ABI 6; Landlock não substitui limites de recursos agregados, nem isolamento de PID/rede completo.
- A consulta local no laboratório retornou `syscall_unavailable`; isso **não identifica** o status do Raspberry. Testes negativos e positivos da ABI: 11/11 PASS. [Estudo de viabilidade](LANDLOCK-ESTUDO-001.md).

## Investigação AppArmor — delimitada e sem mudança de política

- **Evidência no equipamento:** `bwrap: Failed to make / slave: Permission denied`; nas duas consultas `ha host logs` enviadas pelo proprietário não houve registro de `apparmor="DENIED"`. Ausência de log não significa permissão concedida.
- **Fonte oficial do Supervisor:** `supervisor/docker/interface.py` retorna `["seccomp=unconfined"]` como opção de contêiner. `docker/app.py` adiciona perfil AppArmor padrão/customizado. Isso fortalece a hipótese AppArmor ou limites de capabilities/mount, mas **não comprova a causa exclusiva no contêiner real**.
- No futuro log da RC3, o diagnóstico aparecerá com prefixo **`[WORKER]`**, e o servidor só registrará **`[API] READY`** depois de abrir a escuta local. Assim, um 504 do proxy da tela de logs não será confundido com prova de falha na API. O diagnóstico só registra os atributos efetivos **após eventual instalação autorizada**, sem alterar sysctl, AppArmor global ou Docker.
- A documentação oficial permite `apparmor.txt` do add-on. Um perfil permissivo ou com `complain` muda a proteção e **não será publicado por hipótese**. Não adicionar SYS_ADMIN, `apparmor: false`, `privileged`, `full_access`, `host_pid` ou acesso ao socket Docker para forçar o probe.

Referências oficiais: [Segurança de apps](https://contributors.home-assistant.io/apps/guides/security/), [Arquivos de apps](https://contributors.home-assistant.io/apps/reference/files/), [Supervisor interface](https://github.com/home-assistant/supervisor/blob/main/supervisor/docker/interface.py), [Supervisor app](https://github.com/home-assistant/supervisor/blob/main/supervisor/docker/app.py).

## Critérios para a próxima fase

1. Executar regressões completas e validar build final sem efeitos em outros projetos (testes Python dirigidos realizados parcialmente antes da integração, não equivalem a homologação HA).
2. Revisar segurança da API, proteções de processo e sanitização antes de oferecer uma candidata para publicação.
3. Só depois de autorização de publicação e escopo, atualizar **exclusivamente `hassio-addons:main/factory-runner/`** conforme `CONTRIBUTING.md`, com versão nova e teste real pelo Supervisor.
4. Separadamente, projetar um executor com isolamento e orçamento agregados para **código não confiável**. Ele não se confunde com o worker atual de leitura e não pode ser criado por simples replicação do processo.
