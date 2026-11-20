# Factory Runner RC8 — sincronização multiprojeto

**Estado do documento:** candidata `0.1.0-rc.8` preparada em branch. A publicação e a validação física no Home Assistant são etapas distintas. Controle: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2).

## Problema corrigido
A RC7 tinha `workspace_sync_project` e sincronizava apenas um projeto indicado manualmente (por exemplo, `avisaqui`). Essa escolha fixa era inadequada para a Fábrica de Software multi-projeto.

## Comportamento da RC8
- `workspace_sync_enabled`: chave **geral**, padrão **false**. Se estiver desligada, **nenhuma clonagem GitHub** é iniciada, ainda que haja a antiga opção de seleção individual no armazenamento.
- Ao habilitar, a API carrega a lista de perfis JSON **aprovados e validados** em `/app/projects/*.json`. Todos os IDs válidos são sincronizados de forma **sequencial**, independentemente da ordem de criação. Não existe mais seleção de um projeto fixo no formulário.
- Para cadastrar novos projetos (Artesão Digital ou futuros), é necessário **aprovar e versionar seu perfil** em `projects/<id>.json`. O motor é o mesmo; cada perfil define repositório, refs, política e receita de distribuição. Um projeto com formato de política diferente exige adaptador e teste próprios. Não se registra automaticamente qualquer repositório de propriedade da conta.
- Limite de segurança: **máximo 32 perfis aprovados** por rodada. Erro de um projeto é registrado sem impedir a próxima sincronização. A mesma trava usada pela API impede corrida com preflight/preparação em cada projeto, mas é liberada entre eles.
- `github_read_token` continua opcional no schema e deve ser preenchido apenas na configuração protegida do add-on quando houver origem privada. O token nunca deve ser enviado pelo chat nem embutido em repositório/URL/log.
- `workspace_auto_prepare` permanece **false** por padrão e é independente da sincronização. Mesmo quando ligado explicitamente, o preflight exige política de pacote aberta antes da preparação; a publicação e o Git push continuam proibidos.
- O campo antigo `workspace_sync_project` foi retirado do schema e ignorado pelo runtime para evitar seleção acidental. Esta é uma migração **sem sincronização automática** até a chave geral ser ligada.

## Segurança e limites
- Não altera portas, AppArmor, Docker socket ou permissões. Git apenas sincroniza repositórios autorizados por perfis versionados, sem executar scripts do projeto.
- Não altera Avisaqui nem Artesão Digital e não abre pacote fechado para permitir teste.
- O Home Assistant oferece um único campo opcional de token. A permissão da credencial deve abranger **apenas** os repositórios privados aprovados que serão sincronizados. Repositório inacessível falha isoladamente; os demais são processados.
- No catálogo atual existe **apenas** `projects/avisaqui.json`; nenhum perfil de Artesão Digital foi criado sem validar seus requisitos reais. A arquitetura é multiprojeto, mas a cobertura operacional dos projetos depende de cadastro.
- Não há agendamento recorrente: a rotina é executada na inicialização quando habilitada.

## Testes executados neste lote
- **50 testes Python, 50 aprovados como UID não-root** em Linux, incluindo sincronização Git local real e os testes do fluxo E2E sintético já existentes. Os **11 testes do controller** validaram configuração desligada, seleção automática de três projetos aprovados, ordem fixa, isolamento de falha entre projetos, limite de perfis, segredo ausente dos logs, migração do campo antigo e preparação somente com opção explícita.
- `python3 -m py_compile server.py workspace_sync.py`: aprovado.
- `bash -n run.sh`: aprovado.
- `config.yaml` interpretado por PyYAML: versão RC8; opção `workspace_sync_enabled=false`; `workspace_auto_prepare=false`; porta host desativada e arquitetura declarada `aarch64, amd64`.
- Arquivos da fonte e distribuição são conferidos por SHA de Git. Sem GitHub Actions, sem instalação de produção nem alteração de outros add-ons.

**Não executados:** build Docker/ARM64 específico da RC8, clone privado com credencial real, instalação/atualização no Raspberry ou registro do Artesão Digital. Uma aprovação de laboratório não comprova esses itens.

## Aceite no Home Assistant
Após publicação autorizada e atualização manual da RC8, confirmar a versão `0.1.0-rc.8`. Ativar `workspace_sync_enabled` apenas quando quiser iniciar a sincronização; preencher `github_read_token` no Home Assistant para repositórios privados; manter `workspace_auto_prepare` desligado. Nos logs: `[WORKSPACE] START: approved_projects=N`, resultado `SYNCED` ou `UNCHANGED` para cada projeto, bloqueio por política conforme aplicável e `[WORKSPACE] FINISHED: approved_projects=N`. `[DECLARATIVE] PASS` e `[E2E] PASS` continuam distintos dessa verificação.

**Status de publicação/instalação deve ser atualizado na Issue #2 somente com evidências remotas e físicas, respectivamente.**
