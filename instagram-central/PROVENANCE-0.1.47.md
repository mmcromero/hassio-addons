# Proveniência — Central Instagram 0.1.47

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `c9cd4887edf8c442e9439a1ec80d1007ab73cd22`.
- Versão: `0.1.47`; slug `umdoislab_instagram`; arquitetura `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Corrige a marcação HTML do contêiner da caixa de entrada, fechando corretamente o atributo `class`.
- Atualiza o teste do webhook para verificar a contagem compacta `1 mensagem`, em vez do texto antigo `Mensagens armazenadas`.
- Preserva correções CSRF, validação do token Meta e os ajustes UX responsivos das versões anteriores.
- Integridade: 101/101 blobs da pasta-fonte presentes e idênticos no catálogo; arquivos alterados e atualizações de testes/registro reexportados. Ícone, logo e oito manifestos anteriores preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- Build ARM64 e suíte Dockerfile ainda aguardam execução no Supervisor.

## Manifesto Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `0478ed3b5ceb175e79ce754553e125c8af31646e` |
| `instagram-central/README.md` | `c224a3a2c936a80c48e71953eb33cf00d3dbad1b` |
| `instagram-central/config.yaml` | `55e05c578f8540c0d17886f19b4cda768c24bc51` |
| `instagram-central/server.py` | `6279429c4ec4d88b9c5fa7bef4fffc17dc7cad6f` |
| `instagram-central/tests/test_http.py` | `d807f0dfcdd7a39f30d1b543ddd307db2ac24cb2` |

## Integridade
- Comparação final da pasta-fonte: 101/101 blobs idênticos; nenhum arquivo-fonte ausente ou divergente.
