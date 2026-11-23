# Proveniência da publicação — Central Editorial MCP 0.1.3

- Catálogo: `mmcromero/hassio-addons:main/editorial-mcp/`
- Fonte privada: `mmcromero/instagram-automacoes:release-candidate/editorial-mcp/`
- Versão: `0.1.3`
- Slug: `editorial_mcp_universal`
- Arquiteturas declaradas: `aarch64`, `amd64`
- Estado: **publicado no GitHub; aguardando build/instalação/homologação no Supervisor**.

## Arquivos exportados e blob SHAs

| Arquivo | Blob SHA |
|---|---|
| `editorial-mcp/config.yaml` | `dde3491187c3a21b6d0a4a5cf1d0b240a412cf35` |
| `editorial-mcp/Dockerfile` | `2e690fb6316470b5a3d5a009359d50558ce75fae` |
| `editorial-mcp/README.md` | `fb515c0751b1f3ced5323480e8a595e3c6dc4fa3` |
| `editorial-mcp/CHANGELOG.md` | `1f5e17fc926e755098188582db05d89303278c40` |
| `editorial-mcp/DIAGNOSTICS.md` | `1bc5393361bb7696d72845342a12671b2a4a9150` |
| `editorial-mcp/run.py` | `942b09eea1026c3b9b2b464066c8c0efdf9b2531` |
| `editorial-mcp/server.py` | `d65c9c65d2127439920b1ffac7b8f1e8d139b4b9` |
| `editorial-mcp/test_server.py` | `37941b7f08fadce84ea050f11d1340414ad6e98d` |
| `editorial-mcp/test_diagnostics.py` | `1455050fbd10dd9366f4658a04f3e0aae713f965` |
| `editorial-mcp/test_host_file_bridge.py` | `23187cc36df597ba6ed3a661c1de5e2cffeff850` |

## Falha corrigida

A build 0.1.2 no Supervisor falhou em `server.py:428` com `SyntaxError: unmatched '}'`, antes dos testes. A causa foi um fragmento truncado e duplicado após a primeira definição de `make_server()`, seguido por cópias duplicadas das funções/servidor. A 0.1.3 remove esse bloco excedente e mantém uma única definição de `dispatch` e `make_server`, além das cinco ferramentas MCP.

## Testes

O Dockerfile executa primeiro `py_compile` nos cinco módulos e depois 24 testes automatizados (9 MCP, 3 diagnóstico e 12 ponte de arquivos). **Esses gates ainda não foram executados pela build 0.1.3 no hardware alvo.** A publicação Git não equivale à instalação nem à homologação.

## Escopo

Foram atualizados somente os dez arquivos listados em `editorial-mcp/`, mais o índice de versão no README raiz e este manifesto. Nenhum outro app, `repository.yaml`, registro de catálogo, workflow, opção persistida, segredo, chave, sessão ou dado de runtime foi alterado.
