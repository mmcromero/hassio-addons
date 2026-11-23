# Proveniência — Central Editorial MCP 0.1.9

- Fonte: `mmcromero/instagram-automacoes`.
- Commit que contém os blobs do pacote: `dbaaffbc6521b3c205f3fc52feeafb38d4a4908f`.
- HEAD da branch `release-candidate` no corte: `50716f642b8b7fd5cf66bfc295f2fca4f100d104`.
- Slug preservado: `editorial_mcp_universal`; arquiteturas declaradas: `aarch64`, `amd64`.
- Base pública: `mmcromero/hassio-addons:main`, antes da publicação `2730bf607489829ae53aa33615922cba7c44ec72`.
- Somente os sete arquivos desta pasta foram exportados da candidata. `icon.png`, `logo.png`, `run.py`, Funnel/Tailscale, opções, slug e dados persistentes preservados.

## Manifesto de origem (Git blob SHA-1)
| Arquivo | SHA |
|---|---|
| `CHANGELOG.md` | `4a301018601b9d9cedc18af890b0f2daf304917b` |
| `Dockerfile` | `161d291d5da7ecdcf5b7e71659bc99673a867a2f` |
| `README.md` | `9cb46153687e51db64a32662f4992a520b1900d1` |
| `config.yaml` | `24ca43b87e569f7452d1cab2267a09db487fbaf7` |
| `server.py` | `475e7d8e9a26d2b47942fc35c2781f59167590de` |
| `test_multi_server.py` | `b6c27e42beb4d2f9dced59482f0db383643ff2a8` |
| `test_server.py` | `1c772b953b945ddac1591e9c43ba78f9c4865128` |

## Verificações
- Testes locais de concessões/Drive sintéticos: 11 PASS no conjunto da Central. Os testes integrados MCP adicionais estão no Dockerfile e aguardam build real.
- Dockerfile executa `py_compile` e as suítes `test_server`, `test_multi_server`, `test_diagnostics`, `test_host_file_bridge` e `test_funnel_probe` durante o build do Supervisor.
- 7/7 arquivos passaram por varredura textual de padrões conhecidos de segredos: nenhuma ocorrência. Isso não substitui auditoria integral.
- Chave `cei1` permanece legada e restrita; `cei2` suporta escopo multi-conta sem publicação. Nenhuma chave real foi incluída.
- Commit público de distribuição: `119944fcc6da374feb017241af6eb49e16fe9738` (`hassio-addons:main`). A atualização alterou somente os diretórios `instagram-central/` e `editorial-mcp/`; `repository.yaml`, workflows, registry e demais add-ons foram preservados. Commit usa `[skip ci]`, conforme exigência de não executar Actions.
- Estado: **PUBLICADO NO CATÁLOGO; NÃO INSTALADO/HOMOLOGADO**. A instalação requer atualização pelo Supervisor/operador; o conector HA disponível está em modo somente leitura. Não promover a main privada antes de PASS.
