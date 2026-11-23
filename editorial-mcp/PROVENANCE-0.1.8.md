# Proveniência — Central Editorial MCP 0.1.8

**Fonte canônica:** `mmcromero/instagram-automacoes`.
**Branch:** `release-candidate`.
**Commit do pacote:** `212ccc9b79df12a62fa786e9f6cb83dcc896ea25`.
**Árvore do pacote:** `48884d86dfb628564ff17a15ee8575d56801f990`.
**Versão:** `0.1.8`. **Slug:** `editorial_mcp_universal`.
**Arquiteturas declaradas:** `aarch64`, `amd64`.
**Estado:** publicada no catálogo público; atualização e homologação no Home Assistant pendentes.

## Escopo da 0.1.8

- Adiciona `icon.png` e `logo.png`, cópias binárias exatas da identidade oficial já usada por outros apps do catálogo.
- Atualiza `config.yaml`, `serverInfo.version` e as duas expectativas de versão no teste de contrato.
- Preserva o contrato de autenticação 0.1.7: `X-Editorial-Key` e `X-API-Key`, com a mesma validação account-scoped.
- Não altera permissões, ferramentas, API da Central, opções, estado Tailscale, plugin, n8n, banco ou dados persistentes.
- Nenhum segredo, token, arquivo de mídia, opção real ou dado pessoal foi adicionado.

## Identidade visual

| Arquivo | Origem | Git blob SHA | Tamanho |
|---|---|---|---:|
| `icon.png` | `hassio-addons/main/instagram-central/icon.png` | `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` | 111228 bytes |
| `logo.png` | `hassio-addons/main/instagram-central/logo.png` | `7e500016222b0a5bf395be8ed17447edeb3e2af9` | 194750 bytes |

## Manifesto do pacote

| Arquivo | Git blob SHA |
|---|---|
| `editorial-mcp/CHANGELOG.md` | `13c59b02bcb8479c260db465cb16bb92febc1466` |
| `editorial-mcp/DIAGNOSTICS.md` | `5097818c7586b5002b47c6e814f6eae31515eddc` |
| `editorial-mcp/Dockerfile` | `2deb28eecdb8628d15f6dc4d5dd9efd6dc5b40f2` |
| `editorial-mcp/PROVENANCE-0.1.7.md` | `9aec58ae948a6a160ce3575c7e95f55d5f19fe08` |
| `editorial-mcp/README.md` | `1ff8a6909e84fcaae548c55bd5d3fd8a1f032e55` |
| `editorial-mcp/config.yaml` | `56977558596fa89b7ecc8203aa468172eb0ea215` |
| `editorial-mcp/funnel_probe.py` | `1ce8d5c463dbd89d70edb108f6335e42530495b6` |
| `editorial-mcp/icon.png` | `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` |
| `editorial-mcp/logo.png` | `7e500016222b0a5bf395be8ed17447edeb3e2af9` |
| `editorial-mcp/run.py` | `3284ca3510d0eb34ace52b47a19a66301a467728` |
| `editorial-mcp/server.py` | `8ebf44b2da1c773a8686ee4a7a225f8b8b10069e` |
| `editorial-mcp/test_diagnostics.py` | `8298eb22baaf3c0e7a3833c3388b36c1f1779477` |
| `editorial-mcp/test_funnel_probe.py` | `8d9a73355b5e45a0f190704bcee09b40d23a10f8` |
| `editorial-mcp/test_host_file_bridge.py` | `23187cc36df597ba6ed3a661c1de5e2cffeff850` |
| `editorial-mcp/test_server.py` | `a6a239d419757baaafb14b213656f7c2bb729fe6` |

## Testes e homologação

- Revisão estática do diff: concluída. A alteração de código limita-se ao número de versão; os dois assets foram conferidos por hash.
- A 0.1.7 foi construída no Supervisor ARM64 e iniciou corretamente. O Dockerfile executou `py_compile` e as quatro suítes.
- A 0.1.8 ainda não foi construída no Supervisor. O mesmo gate será executado na instalação/atualização.
- A aceitação de `X-API-Key` está coberta pelo teste integrado da 0.1.7; a conexão real de um cliente Claude continua pendente.
- Não foram incluídos nomes de contas, chaves, tokens, URLs privadas, mídia, IDs pessoais ou logs operacionais.

## Publicação

- Commit do pacote privado: `212ccc9b79df12a62fa786e9f6cb83dcc896ea25`.
- HEAD da RC no corte: `b4a6eb449f3140b359b04203ba89962db0373f5d`.
- Catálogo público `mmcromero/hassio-addons:main`: commit `f7b1270734c5fb0dd352c120f02e1e155e57f6f9`.
- O diff público contém somente oito caminhos em `editorial-mcp/`; os manifestos históricos e todos os demais apps/arquivos foram preservados.
- O índice do Supervisor ainda retorna 0.1.7. A recarga da loja via MCP foi bloqueada por Read Only Mode; nenhuma ação foi executada no Home Assistant. O operador deve recarregar a loja pela interface e atualizar somente este app.
- Estado: **PUBLICADO NO CATÁLOGO; NÃO INSTALADO/HOMOLOGADO**. Não promover a `main` privada antes de homologação PASS.
