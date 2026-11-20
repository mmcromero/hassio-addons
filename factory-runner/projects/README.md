# Configurações de projetos do Factory Runner

## Seleção de projetos na RC8

`workspace_sync_enabled` é uma chave **global**, desligada por padrão. Ao ativá-la, o Factory Runner tenta sincronizar em sequência **todos os perfis aprovados e versionados** deste diretório (máximo 32), não só o Avisaqui. A falha de um projeto não impede o processamento dos demais. O campo `workspace_sync_project` da RC7 foi removido e não deve mais ser usado.

**Cadastro:** para adicionar Artesão Digital ou outro projeto, aprovar seu perfil JSON com repositórios, branches, contrato de política, versão e receita declarativa, registrar testes e distribuí-lo em `projects/<id>.json`. O Runner não supõe compatibilidade entre projetos ou cria perfis automaticamente. Cada perfil só pode acessar os repositórios que declarar. O `github_read_token` deve ser restrito aos repositórios privados necessários.

A sincronização não equivale à preparação (`workspace_auto_prepare=false` por padrão), muito menos à publicação. Consulte `../RC8-VALIDACAO.md`.


Este diretório guarda **perfis dos projetos atendidos**, não versões nem código desses projetos. O Factory Runner permanece um produto independente.

- `avisaqui.json`: primeira integração com o fechamento de RC do Avisaqui, usando a política e o exportador existentes no repositório `mmcromero/pager-virtual`.
- Cada projeto futuro terá seu próprio perfil, após levantamento da política, do fluxo de builds e de seus destinos. O Runner não deve presumir que todos usam Home Assistant.
- O campo `exporter_git_blob_sha` é obrigatório e contém o SHA Git do blob do exportador aprovado. Antes de executar o exportador, o Runner compara `HEAD:<exporter_path>` no snapshot fixado com esse SHA; uma divergência bloqueia a operação e exige revisão do perfil.
- Campos `source_repo` e `distribution_repo` identificam repositórios; `source_ref`, `rc_ref`, `public_ref` selecionam as referências fixadas; `package_policy_path`, `package_json_path`, `manifest_path` e `provenance_path` descrevem o contrato de versão; `distribution_prefix` restringe o escopo na loja; `exporter_path` identifica o exportador próprio.
- `allowed_shared_paths` lista exceções permitidas para exportação fora do prefixo. Deixar vazio se não houver nenhuma.
- **Limitação v1:** o motor atual exige política JSON com `active_package`, metadados de versão JSON em arquivo escolhido e um manifesto de versão no formato `version:`. Projetos com outro modelo exigem um adaptador explícito e seus testes. Um JSON diferente sozinho não garante suporte universal.
- Os perfis são *dados de configuração*, não comandos executáveis nem aprovação de publicação. O CLI somente lê os commits especificados e pode preparar uma cópia de exportação; não publica.

## Exemplo de preflight

```sh
python3 factory-runner-add-on/rc_fastlane.py \
  --profile factory-runner-add-on/projects/avisaqui.json \
  --source /checkout/pager-virtual \
  --distribution /checkout/hassio-addons \
  --expected-source-sha <SHA_COMPLETO_FIXADO_NO_GITHUB>
```

É necessário executar esse comando a partir da raiz do repositório de desenvolvimento do Runner, com Git/Python e checkouts locais devidamente atualizados. **Nota histórica:** a RC1 não tinha esse CLI; versões posteriores possuem preflight/preparação local sob as políticas vigentes. O estado instalado deve ser conferido no Supervisor.

Documentação canônica: `docs/governanca/FACTORY-RUNNER-ARQUITETURA-002.md`. Rastreamento: Issue #2 e PR #3.
