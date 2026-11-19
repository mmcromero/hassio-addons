# Configurações de projetos do Factory Runner

Este diretório guarda **perfis dos projetos atendidos**, não versões nem código desses projetos. O Factory Runner permanece um produto independente.

- `avisaqui.json`: primeira integração com o fechamento de RC do Avisaqui, usando a política e o exportador existentes no repositório `mmcromero/pager-virtual`.
- Cada projeto futuro terá seu próprio perfil, após levantamento da política, do fluxo de builds e de seus destinos. O Runner não deve presumir que todos usam Home Assistant.
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

É necessário executar esse comando a partir da raiz do repositório de desenvolvimento do Runner, com Git/Python e checkouts locais devidamente atualizados. O add-on `0.1.0-rc.1` já instalado **não possui ainda esse CLI integrado à sua API**.

Documentação canônica: `docs/governanca/FACTORY-RUNNER-ARQUITETURA-002.md`. Rastreamento: Issue #2 e PR #3.
