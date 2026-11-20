# Changelog

## 0.1.0-rc.19 — Candidata privada M008 (não publicada)

M006 consolidado para homologação dirigida no RPi4; consentimento, transporte e contas permanecem dormentes. Publicação, instalação e ativação dependem de autorização posterior.


## Em desenvolvimento — M006 Raspberry exclusivo (sem nova RC)

- Contrato de publicação reproduz receita declarativa desde blobs pinados, confere política vigente e revalida arquivos/modos/hashes; não executa scripts de produto.
- Consentimento Ed25519 por ato com reautenticação independente, scrypt/throttle, preview e receipt persistidos, TTL/revogação/nonce e IPC por identidade do kernel; emissor, publisher, UI e preparador com contas distintas.
- Transporte GitHub somente bytes: prévia, árvore canônica, blobs SHA-256/OID, commit determinístico, CAS GraphQL beforeOid/force:false e ledger/reconciliação somente leitura após interrupção.
- Componentes dormentes na imagem e status autenticado somente leitura; run.sh e versão RC18 intactos. Sem listeners de aprovação, rota publish, enrollment, segredos reais ou ativação.
- Lote offline com API GitHub simulada/Git descartável, provas de quatro UIDs e revisão técnica; detalhes em M006-RPI-PIPELINE.md e relatório M006 da Issue #2. Nenhuma RC ou pacote de produto publicado.

## 0.1.0-rc.18 — Lote consolidado de integridade e autorização

- Preparação declarativa com recibo SHA-256, escopo exato e preservação de executáveis; repetição idempotente, trava entre processos e diretório final atômico.
- Console local de projetos/status/preparo/operações, sem porta adicional; auditoria recusa symlink, hardlink e FIFO.
- Componente separado de publicação SOMENTE em Git local sintético: autorização independente vinculada ao artefato, expiração/revogação/replay, prévia, CAS e recuperação de interrupção. Excluído da imagem final do HA.
- Verificador offline dos artefatos distintos HA ARM64 e Debian AMD64 do builder Artesão, excluído da imagem final; evidência sintética não equivale a build real.
- Publicação de pacotes pela API permanece desabilitada. Recibos de preparo permanecem com testes PENDING até execução e aprovação legítimas.
- Suíte offline integral e revisão técnica registradas no relatório do lote; build/instalação HA e fluxos reais de produtos são homologações separadas.

## Histórico de desenvolvimento anterior ao lote consolidado

Os registros seguintes preservam o estado declarado nos lotes anteriores; evidências novas estão na RC18 e no relatório do lote.

## Em desenvolvimento — executor isolado HA + Debian

- Adicionado `artesao_isolated_executor.py`, executável **exclusivamente fora do Home Assistant**, com pipeline oficial `release-evidence.py` → `prepare-distributions.py` → HA ARM64 e Debian AMD64 → verificação de `SHA256SUMS`/metadados → recibo local.
- Pré-requisitos de execução: VM descartável independente, prova externa de isolamento de rede, política local vinculada a SHA/versão, cache npm e imagens Docker já disponíveis offline; nenhuma credencial de servidores. O código recusa ambiente de HA, Docker remoto, root, checkout sujo ou HEAD diferente.
- Interface `--execute` é *opt-in* somente na VM aprovada; sem flag, apenas planeja. Falha não gera recibo de sucesso; saída marcada `INCOMPLETE-NOT-FOR-PUBLICATION`. ZIP da Forja Windows exige descriptor oficial existente, nunca sintetizado.
- 15 testes adicionais de executor/recibo/hash/política criados; **execução ainda pendente**. Script incluído somente no estágio de validação Docker, excluído da imagem final do add-on. `ARTESAO-BUILDER-002.md` descreve contrato.
- **Sem nova versão do Factory Runner no catálogo, sem merge, Actions, publicação, instalação ou alteração de servidores.**


## Em desenvolvimento — adaptador de pacotes Artesão Digital

- `artesao_adapter.py` analisa a mesma origem Git fixada para dois destinos independentes: HA ARM64 (contingência) e Debian AMD64 (Forja 01 principal).
- Perfil `artesao_digital.json` usa `mode: artesao_package`, com caminhos e cinco receitas oficiais fixadas por SHA Git; Avisaqui mantém seu perfil e suas regras.
- Versão e schema são verificados na origem e no catálogo, com gate para reuso de versão, ancestralidade da base, proveniência e migração.
- **Somente plano/pré-verificação**: não executa scripts, não gera pacote, não compila imagem, não publica. `/api/prepare` continua bloqueado até recibo de validação e builds reais; `/api/prepare-declarative` não reaproveita as regras do Avisaqui.
- Nove testes de regressão criados com repositórios Git sintéticos; **execução não comprovada** neste lote. Consultar `ARTESAO-ADAPTER-001.md`. Sem alteração de versão de add-on, Actions, merge, catálogo ou servidor.


## 0.1.0-rc.17 — Autodiagnóstico do plano de publicação

- Valida a função somente leitura release_plan após a sincronização, com os workspaces reais já aprovados.
- Registra apenas [RELEASE-PLAN] PASS (plano seguro, publicação desabilitada) ou BLOCKED (pré-verificação indisponível), sem caminho, token ou código arbitrário.
- Três testes HTTP/unitários adicionais preparados para pacote bloqueado, resultado inseguro e sigilo em erro.
- Não confirma autenticação HTTP nem publica pacotes; exige posteriormente teste dirigido autenticado do endpoint.
- Suíte integral de testes continua obrigatória na etapa de validação Docker do build no Home Assistant.


## 0.1.0-rc.16 — Plano de publicação por projeto (somente leitura)

- Nova rota autenticada POST /api/release-plan com project e expected_source_sha; utiliza o preflight real do perfil aprovado.
- Relatório limitado a projeto, SHA, elegibilidade de preparação, códigos de bloqueio e requisitos de publicação.
- Publicação continua desabilitada até existir autorização independente por artefato e executor seguro. Autenticação Bearer não aprova publicação.
- Quatro testes HTTP de autenticação, bloqueio, elegibilidade, sanitização e rejeição de aprovação fornecida pelo cliente.
- Suíte integral continua no estágio de validação Docker do add-on; não foi executada nesta sessão.
- Nenhuma alteração em outros add-ons, Actions, servidor ou projetos atendidos.


## 0.1.0-rc.15 — Sincronização por escopo sem arquivamento desnecessário

- Corrigido `workspace_archive_limit` causado por commits em outros add-ons no catálogo público.
- Se a origem do projeto não mudou e o pacote já está bloqueado por sua própria política, o Runner verifica no GitHub se o novo commit do catálogo alterou somente caminhos fora da pasta e dos arquivos compartilhados autorizados do projeto.
- Quando o comparativo é confiável e não há alterações relevantes, mantém o snapshot validado e registra `UNCHANGED_SCOPE` com `remote_public=<SHA>`, sem clonar, arquivar nem apagar arquivos.
- Falha de API, histórico não ancestral, comparação truncada, alteração na pasta/CI autorizada ou pacote elegível: **não** usa esse atalho; mantém os bloqueios originais e exige snapshot atual antes de preparar.
- Quatro testes de regressão adicionais, sem liberar publicação automática ou alterar dados de outros projetos.
- Não apaga as quatro cópias existentes; limpeza de arquivos permanece fora do escopo e depende de autorização própria. A suíte completa permanece obrigatória no build do Home Assistant.


## 0.1.0-rc.14 — Diagnóstico do histórico de sincronização

- Após o lote de sincronização, o Factory Runner verifica a leitura sanitizada do próprio histórico; registra `[OPERATIONS] PASS: sanitized_workspace_audit projects=N` quando encontra evidência dos projetos configurados.
- Falha de leitura ou ausência de evidência gera `[OPERATIONS] BLOCKED`, sem expor IDs de operação, caminhos, SHA ou tokens; o diagnóstico não libera publicações.
- Três testes de regressão incluídos: histórico válido, ausência de um projeto e log inseguro. A função de auditoria segue autenticada na API.
- O resultado do build e da suíte completa será verificado na instalação autorizada no HA. Nenhuma execução de Actions, compilação externa obrigatória nem mudança em outros add-ons.


## 0.1.0-rc.13 — Histórico de sincronização multiprojeto

- Corrigido o filtro autenticado de `GET /api/operations` para reconhecer as ações reais `workspace_sync:<projeto>`.
- Agora o histórico mostra `completed_workspace_sync`, `blocked_workspace_sync` e o estado final de bloqueio da política, sem incluir dados de credenciais ou caminhos.
- O identificador de projeto é validado; valores com traversal e entradas inválidas não aparecem no retorno.
- Dois testes HTTP adicionados para sincronização e rejeição de identificadores inválidos.
- Oito testes locais dirigidos da função de leitura: PASS. A suíte completa e o build do add-on continuam sujeitos à validação no Home Assistant.
- Nenhuma publicação de pacote de projetos foi habilitada, nenhum add-on alheio foi alterado. A RC é experimental e a instalação é responsabilidade separada.


## 0.1.0-rc.12 — Histórico autenticado de operações (RC experimental)

- Novo endpoint somente leitura `GET /api/operations` com Bearer, até 20 operações recentes; dados sanitizados (`operation_id`, `action`, `status`, `time`).
- Leitura limitada a 128 KiB; linhas inválidas ignoradas e log inseguro/indisponível bloqueado sem expor segredos.
- Quatro testes HTTP adicionais de autenticação, estados, sigilo, symlink e dados inválidos.
- Dois testes extras do executor externo exigem recusa de tokens de produção e Docker remoto; executor continua FORA da imagem final e sem permissão Docker no HA.
- Verificação local reproduzida da função de leitura de operações: 5 cenários PASS. A suíte completa do repositório ainda deverá rodar no estágio Docker validation do HA; sem alegar PASS antecipado.
- Nenhum outro add-on alterado; sem Actions, instalação no Raspberry, merge privado ou publicação de pacotes dos projetos. Issue #2.


## 0.1.0-rc.11 — Correção dos testes do build HA

- Corrigida chamada de `isolated_builder_preflight` no teste: agora passa SHA e versão exigidos.
- Corrigida fixture HTTP de pacote fechado para fornecer workspace sintético antes de verificar resposta 409, sem liberar operações bloqueadas.
- Dois erros da RC10 comprovados nos logs do Supervisor, que registrou 188 testes (169 ok, 1 FAIL, 1 ERROR, 17 SKIP).
- Testes continuam obrigatórios durante o build do Home Assistant. RC11 ainda não foi instalada nem homologada; nenhum PASS antecipado.
- GitHub Actions e instalação no Raspberry não executados nesta publicação. Issue #2.


## 0.1.0-rc.10 — Adaptador Artesão Digital (RC experimental)

- Pré-verificação para HA ARM64 e Debian AMD64 sem gerar pacotes ou publicar automaticamente.
- 24 casos de testes novos no estágio de validação Docker; execução no build do HA, sem declarar PASS antes dos logs.
- Executor externo permanece fora da imagem final; RC para homologação separada da execução Docker isolada.
- Fonte privada mantida em branch, GitHub Actions não executado, Raspberry não instalado. Issue #2.

## Histórico de desenvolvimento — executor isolado HA + Debian

- Adicionado `artesao_isolated_executor.py`, executável **exclusivamente fora do Home Assistant**, com pipeline oficial `release-evidence.py` → `prepare-distributions.py` → HA ARM64 e Debian AMD64 → verificação de `SHA256SUMS`/metadados → recibo local.
- Pré-requisitos de execução: VM descartável independente, prova externa de isolamento de rede, política local vinculada a SHA/versão, cache npm e imagens Docker já disponíveis offline; nenhuma credencial de servidores. O código recusa ambiente de HA, Docker remoto, root, checkout sujo ou HEAD diferente.
- Interface `--execute` é *opt-in* somente na VM aprovada; sem flag, apenas planeja. Falha não gera recibo de sucesso; saída marcada `INCOMPLETE-NOT-FOR-PUBLICATION`. ZIP da Forja Windows exige descriptor oficial existente, nunca sintetizado.
- 15 testes adicionais de executor/recibo/hash/política criados; **execução ainda pendente**. Script incluído somente no estágio de validação Docker, excluído da imagem final do add-on. `ARTESAO-BUILDER-002.md` descreve contrato.
- **Sem nova versão do Factory Runner no catálogo, sem merge, Actions, publicação, instalação ou alteração de servidores.**


## Histórico de desenvolvimento — adaptador de pacotes Artesão Digital

- `artesao_adapter.py` analisa a mesma origem Git fixada para dois destinos independentes: HA ARM64 (contingência) e Debian AMD64 (Forja 01 principal).
- Perfil `artesao_digital.json` usa `mode: artesao_package`, com caminhos e cinco receitas oficiais fixadas por SHA Git; Avisaqui mantém seu perfil e suas regras.
- Versão e schema são verificados na origem e no catálogo, com gate para reuso de versão, ancestralidade da base, proveniência e migração.
- **Somente plano/pré-verificação**: não executa scripts, não gera pacote, não compila imagem, não publica. `/api/prepare` continua bloqueado até recibo de validação e builds reais; `/api/prepare-declarative` não reaproveita as regras do Avisaqui.
- Nove testes de regressão criados com repositórios Git sintéticos; **execução não comprovada** neste lote. Consultar `ARTESAO-ADAPTER-001.md`. Sem alteração de versão de add-on, Actions, merge, catálogo ou servidor.


## 0.1.0-rc.9 — Cadastro seguro do Artesão Digital

- Novo perfil `projects/artesao_digital.json` como segundo projeto, em **modo exclusivo de sincronização**, com origem `fabricacao_e_orcamentos:main` e distribuição `fabricacao-e-orcamentos-ha:main`.
- `rc_fastlane.py` e `workspace_sync.py` recebem validação explícita de perfil sem fluxo de RC e leitura do blob de versão Git fixado. O Avisaqui permanece com política de pacote própria e inalterada.
- API expõe o perfil, porém **nega qualquer preflight/prepare** do Artesão Digital até existir adaptador de pacotes seguro. Mesmo se a auto-preparação estiver ligada, `PREPARE_BLOCKED_BY_PROFILE`.
- Cinco testes novos **adicionados, ainda sem execução comprovada** neste lote. GitHub Actions, publicação, build ARM64 e instalações não executados. Consultar `RC9-VALIDACAO.md`.
- Com `workspace_sync_enabled=true`, a RC9 deverá sincronizar dois projetos aprovados; novos projetos continuam exigindo cadastro próprio.


## 0.1.0-rc.8 — Sincronização multiprojeto por perfis aprovados (candidata)

- **Corrige seleção fixa:** remove `workspace_sync_project` do schema e aceita `workspace_sync_enabled` como chave geral (padrão desligada). Sem habilitação, não há busca GitHub.
- Com a chave ligada, sincroniza **todos os perfis versionados aprovados** em `projects/*.json`, até 32 por rodada. Uma falha não interrompe os demais. Execução sequencial compartilha a trava da API, liberada entre projetos.
- Preparação continua **desligada por padrão** (`workspace_auto_prepare=false`) e bloqueada para pacote fechado. Nunca executa scripts não confiáveis, Git push, merge nem publicação.
- **Laboratório:** 50/50 testes Python PASS em Linux sem root, incluindo novos testes multiprojeto e Git local real; sintaxe de Shell/Python e YAML PASS. **Pendente:** build/instalação da RC8 no HA e clone com credencial privada real.
- O catálogo atualmente contém apenas `avisaqui.json`; Artesão Digital e projetos futuros entram por perfil separado após validação, sem mudar o motor multiprojeto.
- **Candidata não instalada** neste estágio; rastreabilidade: `RC8-VALIDACAO.md` e Issue #2.


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


## 0.1.0-rc.4 — Candidata privada de diagnóstico Landlock (NÃO PUBLICADA)

- `landlock_probe.py`: consulta somente a versão ABI da interface Linux, syscall 444, sem aplicar regras de segurança nem alterar o host.
- O diagnóstico `controlled_worker --task diagnose` inclui `landlock.status`, `abi`, capacidade filesystem/TCP/UDP/IPC e campos fixos `enforcement_verified=false` e `safe_for_untrusted_code=false`.
- Tratamento explícito de interface inexistente/bloqueada/indisponível; retorno `ENOSYS` é `syscall_unavailable`, não prova ausência no kernel do Raspberry.
- Dockerfile preparado para instalar `landlock_probe.py` nos estágios de validação e execução, compilá-lo e incluir 11 testes novos.
- Laboratório local: 11/11 cenários PASS, módulo `landlock_probe.py` testado com SHA de blob Git conferido. Consulta não-root no laboratório retornou `syscall_unavailable` — **não** representa o Home Assistant.
- **Planejador declarativo experimental:** `trusted_export_plan.py` gera apenas mapa em memória, sem executar script/ler Git/copiar/publicar; 13 testes locais PASS. Incluído só no estágio de validação do Dockerfile, **não no runtime**. Mapeamento comum de 135 arquivos comparado com o exportador oficial no snapshot Git `a4b97c1...` (995.337 bytes de metadados de tamanho); workflow compartilhado permanece com autorização própria. Sete regressões adicionais PASS no laboratório com metadados reais selecionados. **Equivalência integral de bytes/proveniência e patch de CI ainda não validada**.
- **NÃO PUBLICADO/INSTALADO:** `hassio-addons:main` continua na RC3. A RC4 não substitui o Bubblewrap, não libera `/api/prepare`, não altera a política AppArmor e não executa código não confiável.

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
