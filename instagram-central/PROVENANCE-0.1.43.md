# Proveniência — Central Instagram 0.1.43

- Fonte canônica: `mmcromero/instagram-automacoes`.
- SHA da RC privada após a correção: `c2f5710c30c0491b420bd361449909457d15bf64`.
- Versão: `0.1.43`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Catálogo de distribuição: `mmcromero/hassio-addons:main`.
- Atualização pública limitada aos sete arquivos alterados em `instagram-central/`; os demais arquivos do pacote não foram reescritos.
- Conferência final: **101/101 blobs** da pasta-fonte presentes e idênticos no catálogo. Permanecem preservados ícone, logo e manifestos históricos 0.1.39–0.1.42.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- 0.1.43 corrige a validação de permissões para examinar o Page Access Token efetivamente usado pela Send API. O teste de regressão confirma o token enviado como `input_token` e a separação do app access token no cabeçalho.
- O Dockerfile executa compilação Python e a suíte declarada no build do Supervisor. Build ARM64, inicialização e testes reais ainda não foram executados nesta exportação.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `568845ffe31402847c902534cc33d44e53d9d16b` |
| `instagram-central/README.md` | `6841f645ee61603a5b9b3f4e332125f42f62c40e` |
| `instagram-central/config.yaml` | `c7b13545473da3aa09ca40537436c625812c8008` |
| `instagram-central/instagram_connection.py` | `52ffb122dccfcdf55003273007cba4d22f7f160f` |
| `instagram-central/server.py` | `c942b50584c5ed2f240a5eafaf83efd78eed91d2` |
| `instagram-central/tests/test_http.py` | `397200400c0799b26a24638bdcab03cc8dec40ba` |
| `instagram-central/tests/test_instagram_connection.py` | `3bfdee32b90410bc454671a70abd45c79776f64b` |

## Integridade

- HEAD do catálogo após a exportação e antes deste manifesto: `ddfed5621bf1a5b2daf908a0e5afb611697459a7`.
- Comparação da pasta: 101 arquivos-fonte idênticos; seis arquivos extras preservados (ícone, logo e quatro manifestos anteriores).
