# Factory Runner RC7 — integração GitHub somente leitura

**Estado:** implementação em branch, NÃO PUBLICADA / NÃO INSTALADA / NÃO HOMOLOGADA no HA. Controle único: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2). A RC6 permanece publicada; o último log real confirmou `[E2E] PASS` em dados sintéticos.

## Entrega RC7

- `workspace_sync.py`: sincronização **opt-in** de fonte privada e distribuição pública usando exclusivamente `source_repo`, `distribution_repo` e refs aprovados no perfil versionado. Conexão fixa a `api.github.com` e `github.com` por HTTPS, com validação TLS, sem URLs fornecidas pelo cliente. Obtém SHAs de branches por API GitHub e compara aos refs de clones Git completos.
- `workspace_askpass.py`: autenticação de clone privado com **token de leitura** fornecido somente nas opções protegidas do HA. O token não aparece em linha de comando, URL remota, config Git, arquivos do pacote ou logs. Auxiliar de credencial restrito a arquivo temporário `0600` em pasta `0700`, apagado após clone.
- `server.py`: sincronização opcional ao iniciar, em **thread de fundo com a mesma trava global da API**, auditoria e mensagens sanitizadas `[WORKSPACE] SYNCED/UNCHANGED/POLICY_BLOCKED/BLOCKED`. Não muda os contratos HTTP nem expõe portas. Somente prepara pacote local quando `workspace_auto_prepare=true` **e** o preflight permitir; nunca faz push/merge/publicação.
- `run.sh` + `config.yaml`: três opções novas: `workspace_sync_project: str?`, `github_read_token: password?`, `workspace_auto_prepare: bool` (padrão `false`). Sem `workspace_sync_project` não há clone, rede ou processamento de código novo na inicialização. Nenhum token precisa ser enviado no chat.
- `Dockerfile`: inclui os dois módulos em validation/runtime, configura auxiliar executável, compila e roda os testes Git em UID não-root. Não adiciona capabilities, host mounts, Docker socket, ingress nem porta publicada.
- Refrescamento seguro: clone `--no-checkout --no-recurse-submodules`, sem executar scripts do projeto nem baixar dependências; verifica origem GitHub e ref Git por SHA, limite de 512 MiB no workspace. Diretório anterior **não é sobrescrito**: somente um workspace do próprio Runner, com manifesto de gerenciamento, pode ser arquivado; dados pré-existentes não gerenciados são recusados e preservados. Sem exclusão de backups.

## Operação prevista no Home Assistant

1. Instalar RC7 **somente após autorização de publicação** e salvar, na aba Configuração do Factory Runner, `workspace_sync_project: avisaqui` e um token fine-grained **somente leitura, Contents: Read**, limitado ao repositório privado de origem. Não divulgar nem colar o token na conversa.
2. Manter `workspace_auto_prepare: false` para primeira verificação. Ao iniciar, conferir `[WORKSPACE] SYNCED` (ou `UNCHANGED`), SHA de origem/destino e `[WORKSPACE] POLICY_BLOCKED` se o pacote estiver fechado.
3. Se e somente se a política de um **pacote novo** permitir, a preparação local pode ser ativada pela opção `workspace_auto_prepare: true`; não publica. A publicação remota continua fora do escopo e proibida.
4. Falta de token, DNS, TLS, permissão de leitura, SHA divergente, refs inválidas e diretórios não gerenciados geram BLOCKED sem enfraquecer controles de host.

**Situação atual verificada no GitHub:** `mmcromero/pager-virtual:desenvolvimento` usa `AVISAQUI-PACOTE-009`, status `closed_release_candidate_published_pending_homologation`. Portanto, **não** está autorizado preparar nova RC do Avisaqui como se houvesse pacote aberto; o resultado correto será sincronização de leitura + bloqueio por política.

## Evidências de testes executados

- **E2E adicional aprovado:** o workspace recém-sincronizado foi usado pelo caminho real `server.prepare_project` para gerar proveniência e pacote local; nenhuma publicação nem alteração dos repositórios de origem.\n- Testes com repositórios Git locais reais e clonagem `--no-checkout` simulando apenas o transporte GitHub: **18 testes de sincronização/controller PASS**, executados com UID Linux `nobody`. Casos: SHA Git versus REST, política aberta/fechada, autenticação de chamada sem vazamento, deduplicação sem reclone, preservação de workspace anterior, rollback de rename, recusa de diretórios não gerenciados, URL/ref inválidos, bloqueio quando SHA diverge.
- Conjunto local disponível, incluindo regressões da RC6: **45 testes PASS** como UID não-root, `bash -n run.sh` PASS, `python3 -m py_compile` PASS, `config.yaml` interpretado por PyYAML com `arch: [aarch64, amd64]` e porta host desativada.
- **Não executados:** clone GitHub real com PAT, integração privada no HA, suíte Docker completa, build ARM64 da RC7 e preparação real com um pacote novo aberto. O token da conta do proprietário **não está disponível e não deve ser enviado ao chat**.
- **Não há autorização para publicação RC7** nesta demanda. Manter na branch para revisão e autorização específica de release quando solicitado.

**Próximo responsável:** DEV revisa diff e PR da RC7; Segurança valida armazenamento/escopo do token; operador instala somente após publicação autorizada e informa blocos `[WORKSPACE]` dos logs. Não repetir diagnóstico Bubblewrap/E2E da RC6 nem alterar o Avisaqui para criar um pacote artificial.