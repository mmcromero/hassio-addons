# Proveniência — Central Instagram 0.1.45

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `e830a99d594a43d733512d42c6c3f1e2c969890c`.
- Versão: `0.1.45`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Correção de CSRF: `automation` passou a ser ação permitida; o token do painel agora pode ser gerado e validado.
- Regressões HTTP: três asserções de versão corrigidas após o erro de sintaxe da 0.1.44.
- UX: ajuste de densidade e hierarquia na Central Editorial e caixa de entrada com título único, contagem compacta, menor espaçamento inicial e sem títulos redundantes. Teste browser cobre desktop/mobile e asserções de hierarquia.
- Padrão de atendimento segue Testes com lista vazia; nenhuma resposta automática é liberada por padrão.
- Integridade conferida: 101/101 blobs da pasta-fonte presentes e idênticos no catálogo. Oito arquivos alterados foram exportados. Ícone, logo e seis manifestos anteriores foram preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- Build ARM64 e suíte Dockerfile no Supervisor ainda aguardam a atualização autorizada.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `c163a35edfe106a56d3a1d544151f798f6045894` |
| `instagram-central/README.md` | `ac2652af6062c63302f7dbaf3903f8aeee919e77` |
| `instagram-central/config.yaml` | `7e4daa4369e9e70ae106a4094991da9d038d48fc` |
| `instagram-central/editorial-ui/editorial.css` | `dd18559f910ffe7a7bc175a58aee1fd8f9abe79c` |
| `instagram-central/interface-ui.css` | `961ad12fedbe43a866499c93d90d0430d0c091bb` |
| `instagram-central/server.py` | `6b0b6914c00f11b7e9e80d56bba8dc08444512fe` |
| `instagram-central/tests/inbox_layout_browser.cjs` | `45e5cf4d310acc20e5d420528e445fef0bc57c87` |
| `instagram-central/tests/test_http.py` | `9342097511f95640bbee32adf26d229564ae089e` |

## Integridade
- O catálogo foi comparado com a pasta de origem: 101/101 blobs idênticos; nenhum arquivo-fonte ausente ou divergente.
