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
- O Dockerfile executa `py_compile` e as suítes de concessões, Drive e HTTP integrado como etapas obrigatórias. O build ARM64 do Supervisor foi concluído; essas etapas não bloquearam a imagem.
- 15/15 arquivos passaram por varredura textual de padrões conhecidos de segredos (PEM, GitHub, Google API/OAuth, Slack, bearer e credenciais cei1/cei2): nenhuma ocorrência. Isso não substitui auditoria integral.
- `py3-google-auth` e `py3-requests` foram instalados no build ARM64 concluído pelo Supervisor.
- H1/H2 foram comprovados em PoC isolada Sites 0.1.3: ChatGPT → Drive privado → URL temporária assinada do host → Worker. O Worker recebeu os bytes e confirmou tamanho/hash, sem persistir mídia e sem transferir à Central. Isso não comprova leitura direta da Google Drive API pelo add-on.
- Commit público de distribuição: `119944fcc6da374feb017241af6eb49e16fe9738` (`hassio-addons:main`). A atualização alterou somente os diretórios `instagram-central/` e `editorial-mcp/`; `repository.yaml`, workflows, registry e demais add-ons foram preservados. Commit usa `[skip ci]`, conforme exigência de não executar Actions.
## Homologação Home Assistant — 23/11/2026
- Build real `aarch64` concluído pelo Supervisor às 12:08:50 BRT; app iniciado às 12:08:55, versão 0.1.39. Estado `started`, versão disponível igual à instalada, sem update pendente.
- O Dockerfile executa `py_compile` e os testes `test_editorial_connections.py`, `test_editorial_drive.py` e `test_editorial_multi_http.py` como etapas obrigatórias. O build concluído indica que essas etapas não bloquearam a imagem.
- Log de runtime: `Central internal HTTP ready: port=8099 version=0.1.39`. Erros `BrokenPipeError`/tracebacks encontrados no histórico pertencem a inicializações anteriores (0.1.33 ou anteriores); não aparecem depois do início 0.1.39 no recorte verificado.
- O conector ChatGPT existente listou Umdoislab e Tudo é 3D; consultas individuais retornaram `connected=true` para ambas. É uma validação da API Central pelo conector existente (adapterVersion 1.1.1), não do MCP 0.1.9.
- A rota direta Drive API da Central 0.1.39 exige `drive_service_account_json` e uma pasta-raiz privada por conexão, com subpastas por conta. A opção está vazia e essa modalidade permanece pendente. Ela é separada do fluxo temporário do host e não bloqueia a validação desse fluxo.
- H3 (transferir um arquivo escolhido para rascunho da Central, conferir recibo e limpeza individual) ainda não foi executado. Nenhuma mídia foi enviada à Central ou publicada.
- Estado: **CATÁLOGO + BUILD ARM64 + INSTALAÇÃO + STARTUP PASS; H1/H2 PASS NA PoC; H3 PENDENTE; DRIVE API DIRETA NÃO CONFIGURADA**. Não promover a main privada antes de PASS.
