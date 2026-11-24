# Proveniência — Central Instagram 0.1.41

- Fonte de desenvolvimento: `mmcromero/instagram-automacoes:desenvolvimento`, HEAD `4134e1cec2b4ff30181fc6ee5ceaea26cf36febd`.
- Candidata privada: `mmcromero/instagram-automacoes:release-candidate`, HEAD no corte `a6d940bbbaf324d5b177f5c815612292fd69db41`.
- Versão: `0.1.41`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Catálogo público base: `mmcromero/hassio-addons:main`, `da6b868743f570e733d47f4d436cd3d171b58bda`.
- Exportação limitada a 10 arquivos de `instagram-central/`. Ícone, logo, proxy, opções, bancos, tokens, segredos, mídia, manifesto raiz, outros add-ons e workflows compartilhados preservados.
- A versão 0.1.40 foi publicada, mas o build ARM64 do Supervisor falhou no teste `test_settings_navigation.py` por literal bytes com caractere não ASCII. O defeito foi corrigido em 0.1.41 com codificação UTF-8 explícita; o Supervisor fará nova compilação e execução de testes.
- Não foram exportadas alterações de automação/política nem outras mudanças de produto existentes na branch `desenvolvimento`.
- Dockerfile da candidata executa `py_compile`, três testes focados editoriais existentes e os testes `test_interface_ui.py` e `test_settings_navigation.py`. O roteiro Chromium está no pacote, mas não é executado pelo build do Supervisor.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `CHANGELOG.md` | `9b755a10baaf2af64975fc855250a2762f3aae6e` |
| `Dockerfile` | `d3ac1f6c5973b4793964c1fe0cf2e62658dfaf1b` |
| `README.md` | `8559abcbc3264726dd35966f139a123f1097848d` |
| `config.yaml` | `a5a78087b768e22c8fbfd9dc8c2642c28d0f8ad8` |
| `interface_ui.py` | `a22d0017d97e438e292d7918e232d5a1e85d147a` |
| `interface-ui.css` | `7de06e2c21075846c978c68be8ab0133129aa9d2` |
| `interface-ui.js` | `7541e154b5575b7cb92fc1a5cf49a0fe2ed03d52` |
| `tests/test_interface_ui.py` | `9bf0f53d192cdd8200077069244a456de8fbfb53` |
| `tests/test_settings_navigation.py` | `81740a8e181f942027c0c0abc08eaccb839e501d` |
| `tests/ux_organization_browser.cjs` | `c0504eb2bafff8dada1aedfc81180eba95079ac8` |

## Segurança e compatibilidade

- Atualização mantém opções privadas atuais do Supervisor e os dados em `/data`.
- Nenhuma migração destrutiva, alteração de rotas, APIs, Meta, webhook, mensagens, Editorial, Drive, n8n ou publicação externa.
- Build real ARM64 e inicialização serão confirmados pelo Supervisor na atualização.
