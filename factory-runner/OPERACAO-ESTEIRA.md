# Factory Runner — Candidato de pré-verificação multi-projeto

**Estado:** desenvolvimento, ainda não homologado ou publicado. **Produto independente** dos projetos atendidos.

## O que já existe

- `GET /api/status` — autenticado, informa preflight somente leitura.
- `GET /api/projects` — autenticado, mostra apenas perfis JSON previamente configurados.
- `POST /api/preflight` — autenticado, aceita exatamente `{"project":"avisaqui","expected_source_sha":"<SHA-40>"}`. Verifica referências e política dos checkouts locais, sem escrever.
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

**Atenção:** os caminhos acima são pré-requisitos; não são criados pela API. Sem eles, o endpoint devolve `503 preflight_unavailable`. Não comunicar que o serviço faz fechamento automático enquanto não houver integração, testes e autorização separada.

## Segurança

- API somente em `127.0.0.1` dentro do contêiner; nenhuma porta mapeada ao host.
- Token forte de pelo menos 32 caracteres, somente em `/data/options.json`.
- Nada de URL pública, upload de arquivo executável, rota de comandos arbitrários, GitHub Actions, `git push` ou auto-merge.
- Logs de auditoria sanitizados e gravados sob `/data/factory-runner/audit.jsonl`.
- Perfil JSON versionado e validado; cliente não escolhe paths arbitrários.
- Não encaminhar credenciais para subprocessos de testes/exportação.

## Verificações pendentes

```sh
python3 -m unittest discover -s tests -p 'test_factory_runner_*.py' -v
python3 -m py_compile factory-runner-add-on/server.py factory-runner-add-on/rc_fastlane.py
docker build --platform linux/arm64 -f factory-runner-add-on/Dockerfile factory-runner-add-on
```

A última linha depende de recursos ARM64/Buildx disponíveis; não foi executada nesta conversa. Os testes de Python também não foram executados com o código remoto; considerar resultado **não verificado**, não PASS.

## Critérios para uma versão instalável com publicação

Antes de integrar em `hassio-addons:main`, validar sintaxe, testes, build ARM64, limites de CPU/RAM e acesso aos checkouts. A próxima versão do Factory Runner é independente da `0.1.20-rc.8` do Avisaqui. Essa fase disponibiliza apenas o **preflight somente leitura**, não fecha pacotes.

Rastreabilidade: [Issue #2](https://github.com/mmcromero/orquestrador-projetos-base/issues/2), [PR #3](https://github.com/mmcromero/orquestrador-projetos-base/pull/3), `docs/governanca/FACTORY-RUNNER-ARQUITETURA-002.md`.
