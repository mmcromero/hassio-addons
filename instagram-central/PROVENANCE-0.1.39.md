# Proveniência — Central Instagram 0.1.39

- Fonte: `mmcromero/instagram-automacoes`.
- Commit que contém os blobs do pacote: `dbaaffbc6521b3c205f3fc52feeafb38d4a4908f`.
- HEAD da branch `release-candidate` no corte: `50716f642b8b7fd5cf66bfc295f2fca4f100d104`.
- Slug preservado: `umdoislab_instagram`; arquitetura declarada: `aarch64`.
- Base pública: `mmcromero/hassio-addons:main`, antes da publicação `2730bf607489829ae53aa33615922cba7c44ec72`.
- Somente os 15 arquivos desta pasta foram exportados da candidata. Ícone/logo, proxy, URLs, portas, slug, volumes e opções anteriores preservados.

## Manifesto de origem (Git blob SHA-1)
| Arquivo | SHA |
|---|---|
| `CHANGELOG.md` | `e13a26c3f52ebc9e59ce493706b41faa1e0c4e65` |
| `Dockerfile` | `311c832b5dd3e70c7cebf45a1fd4fe81d59f6e4b` |
| `README.md` | `12086529fad351825db37162368013cf6ac20fb7` |
| `config.yaml` | `1a10979e51bdf8b3a7d32b06acfeb9a5e5b9f5f8` |
| `editorial_connections.py` | `07825d7eea064d1403d73f6a27ccfbe6229a0d71` |
| `editorial_drive.py` | `1b60401e0390a5156165f63256a3ddadd611f4e2` |
| `editorial_http.py` | `c4326d01273843f9cdbb514501445c100126db65` |
| `editorial_import.py` | `81851a2ba3893d6b8395091cd39e30cbdeaff8fd` |
| `editorial_multi_api.py` | `5bf323f09aa089fd08c1270c65a716df32ee644c` |
| `interface-ui.js` | `af3d6fb0e8614af62ccfec75199337283f2a3e6d` |
| `panel_login.py` | `d0423d01cb936a0eef282d2454c04323de4e4a95` |
| `server.py` | `5be5a996f07497499e1e106df6847f1d4c0004d9` |
| `tests/test_editorial_connections.py` | `3b385ccec3f401f7b8197f98bd7502ea1ce537f4` |
| `tests/test_editorial_drive.py` | `149589667b4b76cf1cd518aed65ad4f5fbf253d3` |
| `tests/test_editorial_multi_http.py` | `4ae156bb1ccd7dd1050f721d1d24985976603621` |

## Verificações
- 11 testes locais sintéticos da implementação de autorização e Drive: PASS conforme registro da execução na fonte; não equivalem aos testes integrados HTTP/MCP.
- O Dockerfile executa `py_compile`, testes de concessões, Drive e HTTP integrado durante o build do Supervisor. Esse build ainda precisa ocorrer no HA.
- 15/15 arquivos passaram por varredura textual de padrões conhecidos de segredos (PEM, GitHub, Google API/OAuth, Slack, bearer e credenciais cei1/cei2): nenhuma ocorrência. Isso não substitui auditoria integral.
- `py3-google-auth` foi confirmado no índice Alpine v3.24 para aarch64; dependências e build final precisam ser confirmados pelo Supervisor.
- Credencial Google permanece vazia; não há conexão real ao Drive homologada. Sem publicação direta no Instagram, sem mudança Meta, n8n, Tailscale ou NGINX.
- Commit público de distribuição: `119944fcc6da374feb017241af6eb49e16fe9738` (`hassio-addons:main`). A atualização alterou somente os diretórios `instagram-central/` e `editorial-mcp/`; `repository.yaml`, workflows, registry e demais add-ons foram preservados. Commit usa `[skip ci]`, conforme exigência de não executar Actions.
- Estado: **PUBLICADO NO CATÁLOGO; NÃO INSTALADO/HOMOLOGADO**. A instalação requer atualização pelo Supervisor/operador; o conector HA disponível está em modo somente leitura. Preservar dados e opções persistentes. Não promover a main privada antes de PASS.
