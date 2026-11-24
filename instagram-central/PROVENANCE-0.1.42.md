# Proveniência — Central Instagram 0.1.42

- Fonte canônica: `mmcromero/instagram-automacoes`.
- Branch de desenvolvimento e candidata reconciliadas: `4f1fa283817c2fa1b1b5fb063c0fdf3a1504fd6b`.
- Versão: `0.1.42`; add-on slug: `umdoislab_instagram`; arquitetura: `aarch64`.
- Catálogo de distribuição: `mmcromero/hassio-addons:main`.
- Exportação concluída exclusivamente no diretório `instagram-central/`. O pacote público foi comparado com a pasta-fonte: todos os 101 blobs da fonte estão presentes e com SHA idêntico; permanecem preservados o ícone, a logo e os manifestos históricos de proveniência.
- Arquivos de 0.1.42 adicionados: política de atendimento automático e testes dedicados; atualizados servidor, conexão Meta, configuração, Dockerfile, changelog, README e regressões relacionadas.
- A candidata continua em modo seguro: padrão `tests`, lista de teste vazia; workflow n8n inativo. Nenhum segredo, token, banco, dado de cliente ou credencial foi exportado.
- O Dockerfile executa compilação Python e a suíte de testes declarada no build do Supervisor. Esse build ARM64 ainda precisa ser executado na instalação Home Assistant; exportação para o catálogo não comprova build ou inicialização.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `836d9cbf4d2714b3a8126eec9a1b1a4dfac431ed` |
| `instagram-central/Dockerfile` | `2c481d21ef6e3bcdbc91b0a5484f1e44aba93bde` |
| `instagram-central/README.md` | `52d842d3b4bf1bc8020b56e34984799b1b224e9c` |
| `instagram-central/config.yaml` | `b20479e739c96a1a6c9e68cc818aa6d8d11ca351` |
| `instagram-central/instagram_connection.py` | `cc4244ba7ba21e7d09b946b0b2f78978dc3506ae` |
| `instagram-central/policy.py` | `c1fb05aa5e8236e7bbb7b0efe4cef8cf4d7e6bbe` |
| `instagram-central/server.py` | `19bcff5140513a76c6342f0bdaaa569b3cfbd5bd` |
| `instagram-central/automation_policy.py` | `9498e02accf2a608e1ce605c4d795f17ec4669ef` |
| `instagram-central/tests/test_http.py` | `8a6d112ca862aeb1c1778a2657e198f1afa65029` |
| `instagram-central/tests/test_instagram_connection.py` | `b9e19de0422e7389de3101f1b5ac9baf1f0f1996` |
| `instagram-central/tests/test_policy.py` | `c4c669dc6fe0b01b7437f836db0a348068eba2b7` |
| `instagram-central/tests/test_server.py` | `7099f227d26dca5009e91d44686fcae1e93dbc21` |
| `instagram-central/tests/test_smoke.py` | `5ebbf1aee11deeb463a4d0a90942f9fb2af5650d` |
| `instagram-central/tests/test_automation_policy.py` | `986fc4f3c1eaf993cb01777e03813d081fdac8de` |
| `instagram-central/tests/test_automation_policy_http.py` | `cc6fa92e16a508bd684fb5b230a978b6189ea69b` |

## Integridade

- HEAD do catálogo no início da escrita: `da6b868743f570e733d47f4d436cd3d171b58bda` (proveniência 0.1.41).
- HEAD do catálogo após exportação e antes deste manifesto: `936c5bf5ca4abdb602d412ffefb8b1e14cc9e1b8`.
- Conferência de diretório: 101/101 blobs da fonte idênticos; 5 arquivos extras preservados (ícone, logo e 3 manifestos anteriores).
