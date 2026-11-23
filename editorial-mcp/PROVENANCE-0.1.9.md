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
- Testes locais sintéticos de concessões/Drive: 11 PASS no conjunto da Central. As suítes integradas MCP também foram executadas como etapas obrigatórias do build ARM64 concluído pelo Supervisor.
- Dockerfile executa `py_compile` e as suítes `test_server`, `test_multi_server`, `test_diagnostics`, `test_host_file_bridge` e `test_funnel_probe` durante o build do Supervisor.
- 7/7 arquivos passaram por varredura textual de padrões conhecidos de segredos: nenhuma ocorrência. Isso não substitui auditoria integral.
- Chave `cei1` permanece legada e restrita; `cei2` suporta escopo multi-conta sem publicação. Nenhuma chave real foi incluída.
- Commit público de distribuição: `119944fcc6da374feb017241af6eb49e16fe9738` (`hassio-addons:main`). A atualização alterou somente os diretórios `instagram-central/` e `editorial-mcp/`; `repository.yaml`, workflows, registry e demais add-ons foram preservados. Commit usa `[skip ci]`, conforme exigência de não executar Actions.
## Homologação Home Assistant — 23/11/2026
- Build real `aarch64` concluído pelo Supervisor às 12:07:55 BRT; app iniciado às 12:07:58, versão 0.1.9. Estado `started`, versão disponível igual à instalada, sem update pendente.
- O Dockerfile executa `py_compile` e as suítes `test_server`, `test_multi_server`, `test_diagnostics`, `test_host_file_bridge` e `test_funnel_probe` como etapas obrigatórias. O build concluído indica que essas etapas não bloquearam a imagem.
- Diagnóstico de inicialização: GET local em `/mcp` retorna 405 (esperado; o protocolo aceita POST); DNS A/AAAA confirmado; Funnel configurado para HTTPS 443 público com destino `127.0.0.1:8765`; handshake TLS externo verificado.
- Ressalva: uma amostra local mostrou `self_online=false` e zero peers ingress, mas o Tailscale Admin Console consultado em modo somente leitura mostra o dispositivo `central-editorial-mcp` como **Connected** e com marcador **Funnel**. O diagnóstico local é inconsistente e não deve ser tratado isoladamente como desconexão. O probe local também confirmou DNS A/AAAA, configuração Funnel HTTPS 443 para loopback e TLS externo verificado. Ainda falta uma chamada MCP externa autenticada.
- Não foi provisionada uma chave `cei2` para cliente externo; nenhuma chave real foi criada ou exibida nesta etapa. O registro anterior indica Claude Custom Connector ligado a Umdoislab e limite de um conector no plano Free; preservar o conector atual até validar a troca de chave.
- H2 foi comprovado na PoC Sites 0.1.3 com URL temporária assinada do host ChatGPT. O MCP 0.1.9 implementa `validar_arquivo_temporario` (somente leitura) e `enviar_arquivo_temporario_para_revisao` (exige autorização explícita, nunca publica, 4 MiB agregado); o build ARM64 executou a suíte `test_host_file_bridge`. A chamada real autenticada desses tools no MCP 0.1.9 ainda não foi executada.
- O MCP também contém a rota direta `validar_arquivo_drive`/`enviar_arquivo_drive_para_revisao`, mas depende de identidade de serviço Google `drive.readonly` e pasta-raiz privada por conexão; a opção está vazia e essa modalidade permanece não configurada. Não é requisito para o caminho de URL temporária.
- H3 (transferência real à Central, recibo e limpeza) permanece pendente; nenhuma mídia foi enviada ou publicada.
- Estado: **CATÁLOGO + BUILD ARM64 + INSTALAÇÃO + STARTUP PASS; TAILSCALE CONNECTED/FUNNEL; H2 PASS NA PoC; MCP AUTENTICADO E H3 PENDENTES**. Não promover a main privada antes de PASS.
