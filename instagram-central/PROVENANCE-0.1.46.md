# Proveniência — Central Instagram 0.1.46

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `c3766708db49eaaeecc522be471056cf9e13976e`.
- Versão: `0.1.46`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Corrige o teste de permissões Meta: as asserções de `debug_token` pertencem ao teste de envio via Send API, não ao teste de assinatura de webhook.
- Mantém a correção de validação do Page Access Token, a política CSRF de atendimento e os ajustes UX responsivos introduzidos em 0.1.45.
- Integridade: 101/101 blobs da pasta-fonte presentes e idênticos no catálogo; seis arquivos modificados reexportados. Ícone, logo e sete manifestos anteriores preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- Build ARM64 e suíte Dockerfile ainda aguardam execução no Supervisor.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `bf3dbc5b356b7ca2e64e7356af116002993d3c04` |
| `instagram-central/README.md` | `2820ddc38b81ff95d3114496f243f447a4ec7206` |
| `instagram-central/config.yaml` | `bc9d9d7dd1f9464f875f3df74454639cbc3720b2` |
| `instagram-central/server.py` | `14fb514d67ec213d95c647f510849c5956f3226a` |
| `instagram-central/tests/test_http.py` | `7b74f719cfb45fbb9173c1d95b9c4d510e699e31` |
| `instagram-central/tests/test_instagram_connection.py` | `2f8e84f3aad67dcc00ba3317d3a0bda3116c5532` |

## Integridade
- Comparação final da pasta-fonte: 101/101 blobs idênticos; nenhum arquivo-fonte ausente ou divergente.
