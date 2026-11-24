# Proveniência — Central Instagram 0.1.44

- Fonte canônica: `mmcromero/instagram-automacoes`.
- SHA da release candidate: `ddbd54471ccc7b19af9c619e9a6bdeee41ae22a5`.
- Versão: `0.1.44`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Correção: ação `automation` incluída na lista permitida de ações CSRF do painel. Isso corrige os dois HTTP 403 dos testes de gravação da política.
- Teste de regressão reforçado para confirmar que o token CSRF de `automation` é gerado e validado.
- O modo padrão permanece `tests`, com lista vazia; nenhuma pessoa é automaticamente autorizada.
- Conferência de integridade: 101/101 blobs da pasta-fonte presentes e idênticos no catálogo. Sete arquivos alterados reexportados; ícone, logo e manifestos anteriores preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- Build ARM64 e suíte Dockerfile no Supervisor ainda aguardam repetição após a correção.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `059adb7783e0abcd3ef645b2016fb8780f0405a1` |
| `instagram-central/README.md` | `e9da90fc9a5571864eabc52a9f9c7da469ccf373` |
| `instagram-central/config.yaml` | `50cd05859644740eccecb5ec12c515e00cb0b5ea` |
| `instagram-central/panel_login.py` | `b9e17070a4b3e15e82ac4afd3b45d806dd6576da` |
| `instagram-central/server.py` | `fcb2a552ea2e327792ce2f976f1290e81e687032` |
| `instagram-central/tests/test_automation_policy_http.py` | `3593f255947bdf378c28645a6f3bc353cb7015be` |
| `instagram-central/tests/test_http.py` | `63ffa59b2bc26878a334c2e551e00fe4bf70f9b2` |

## Integridade

- HEAD do catálogo após os sete arquivos de 0.1.44 e antes deste manifesto: `07366cbf102e6653753618525efd8d8bf5836e8d`.
- 101 arquivos da fonte idênticos; sete extras preservados (ícone, logo e cinco manifestos históricos).
