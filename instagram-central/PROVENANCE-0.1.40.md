# Proveniência — Central Instagram 0.1.40

- Fonte de desenvolvimento: `mmcromero/instagram-automacoes:desenvolvimento`, HEAD `e3fadb885d6fb3a0ba27a10c7a086bfb5ab1b9f7`.
- Candidata privada: `mmcromero/instagram-automacoes:release-candidate`, HEAD no corte `c4979c1bdf1e7b8a8eeeed42ca944c370d779255`.
- Versão: `0.1.40`; slug preservado `umdoislab_instagram`; arquitetura declarada `aarch64`.
- Catálogo público: `mmcromero/hassio-addons:main`, base `60f1aaef2ac2219eff8fbfaeed6058e7d0e469a4`.
- Escopo exportado: somente os 10 arquivos listados abaixo dentro de `instagram-central/`. Ícone, logo, proxy, opções, manifesto raiz, outros add-ons e workflows compartilhados foram preservados.
- A candidata exporta somente a reorganização UX aprovada. Alterações de automação/política e demais mudanças presentes em `desenvolvimento` não foram incluídas.
- Dockerfile da candidata executa `py_compile` dos módulos e os testes focados já existentes, acrescidos de `test_interface_ui.py` e `test_settings_navigation.py`. O Supervisor fará o build ARM64 e executará essas etapas na atualização.
- O teste Chromium `ux_organization_browser.cjs` foi exportado como evidência/roteiro, mas não é executado no build HA (não há Node/Chromium no runtime do add-on).

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `CHANGELOG.md` | `f1bd54463c1fa912f8f1c987fd376b4db92355f0` |
| `Dockerfile` | `d3ac1f6c5973b4793964c1fe0cf2e62658dfaf1b` |
| `README.md` | `0f8fe0b9a1b01bb702a6461eea4fbf5792443260` |
| `config.yaml` | `3c2d1588343b092d9be2b94284c56f4b28e1bbc3` |
| `interface_ui.py` | `a22d0017d97e438e292d7918e232d5a1e85d147a` |
| `interface-ui.css` | `7de06e2c21075846c978c68be8ab0133129aa9d2` |
| `interface-ui.js` | `7541e154b5575b7cb92fc1a5cf49a0fe2ed03d52` |
| `tests/test_interface_ui.py` | `9bf0f53d192cdd8200077069244a456de8fbfb53` |
| `tests/test_settings_navigation.py` | `2621b9d3f40029732c76e23415dc08651fc7105c` |
| `tests/ux_organization_browser.cjs` | `c0504eb2bafff8dada1aedfc81180eba95079ac8` |

## Segurança e compatibilidade

- Nenhuma opção do Supervisor foi reescrita: atualização mantém os valores privados existentes.
- Nenhum arquivo de dados, banco SQLite, sessão, token, segredo ou mídia foi exportado.
- Não há alteração de rotas, API, OAuth Meta, webhook, recebimento de mensagens, editor ou publicação.
- Atualização do Home Assistant é separada da publicação no Git; a homologação final depende de build e startup reais no host ARM64.
