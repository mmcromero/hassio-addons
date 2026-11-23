# Proveniência — Central Editorial MCP 0.1.7

**Fonte canônica:** `mmcromero/instagram-automacoes`, branch `release-candidate`.
**Commit da candidata:** `de29a580096cb2996d3336014991d1118dcc8f2d`.
**Versão:** `0.1.7`. **Slug:** `editorial_mcp_universal`.
**Arquiteturas declaradas:** `aarch64`, `amd64`.
**Estado:** candidata pronta para exportação controlada; ainda não construída no Supervisor nem homologada com Claude.

## Mudança

- Preserva `X-Editorial-Key` usado pelo n8n.
- Acrescenta suporte ao cabeçalho padrão `X-API-Key` para Claude Custom Connector.
- Ambos os nomes carregam o mesmo token editorial `cei1...`, validado pelo mesmo formato e pelo endpoint account-scoped da Central.
- Rejeita cabeçalhos duplicados/ambíguos e valores malformados. Nenhuma autenticação sem chave foi introduzida.

## Testes

- Teste HTTP dirigido isolado do parser de cabeçalhos: 4 verificações aprovadas (cabeçalho legado, padrão, duplicidade e valor malformado).
- Testes completos e `py_compile` ainda não executados localmente neste ambiente.
- O Dockerfile executa `py_compile` e `unittest` das suítes `test_server`, `test_diagnostics`, `test_host_file_bridge` e `test_funnel_probe` durante o build do Supervisor. Esse resultado será o gate real de build/homologação ARM64.
- Nenhuma GitHub Actions foi executada.

## Inventário de arquivos do add-on

| Arquivo | Git blob SHA |
|---|---|
| `editorial-mcp/CHANGELOG.md` | `084458000fe2401387e8d7d80ffd62a0e8a294f2` |
| `editorial-mcp/DIAGNOSTICS.md` | `5097818c7586b5002b47c6e814f6eae31515eddc` |
| `editorial-mcp/Dockerfile` | `2deb28eecdb8628d15f6dc4d5dd9efd6dc5b40f2` |
| `editorial-mcp/README.md` | `b5a0830b984316889724bdbeba12931c759c23e3` |
| `editorial-mcp/config.yaml` | `e87af46d9e7c0dde489b43bfd8c3acf572dadca5` |
| `editorial-mcp/funnel_probe.py` | `1ce8d5c463dbd89d70edb108f6335e42530495b6` |
| `editorial-mcp/run.py` | `3284ca3510d0eb34ace52b47a19a66301a467728` |
| `editorial-mcp/server.py` | `86c0e33e7e0c0dcf97355fc77f1c99e40dbf7343` |
| `editorial-mcp/test_diagnostics.py` | `8298eb22baaf3c0e7a3833c3388b36c1f1779477` |
| `editorial-mcp/test_funnel_probe.py` | `8d9a73355b5e45a0f190704cbee09b40d23a10f8` |
| `editorial-mcp/test_host_file_bridge.py` | `23187cc36df597ba6ed3a661c1de5e2cffeff850` |
| `editorial-mcp/test_server.py` | `3b52f5b0e35bd0bba90aeb6800442aa100825570` |

## Homologação já realizada na 0.1.6

- HTTPS/TLS externo verificado.
- n8n: Streamable HTTP autenticado, initialize e tools/list aprovados.
- `consultar_conexao`: conta Umdoislab confirmada.
- Story de teste transferido para rascunho; proprietário confirmou visualmente. MCP retornou `status=draft`, `published=false`, `publicationAuthorized=false`.
- Claude ainda depende de instalação/homologação desta candidata e conexão real.
- ChatGPT Plus permanece pelo plugin original 1.1.1; não há alegação de MCP direto no ChatGPT Plus.

