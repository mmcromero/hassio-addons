# Proveniência — Central Instagram 0.1.49

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `23ea42ae0daa52f091c4a8d19f5856847f658645`.
- Versão: `0.1.49`; slug `umdoislab_instagram`; arquitetura declarada `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Corrige a divergência detectada após a atualização 0.1.48: a versão interna informada pelo endpoint `/health` permanecia em 0.1.47; agora `APP_VERSION` acompanha o manifesto 0.1.49.
- Preserva as correções de encaminhamento POST-only e os testes de regressão publicados na 0.1.48.
- Exportação incremental limitada a três arquivos do pacote e este registro. Demais arquivos, ícone, logo, opções do catálogo e outros add-ons preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- A publicação não equivale a instalação ou homologação. Build ARM64, suíte Dockerfile e verificação funcional da 0.1.49 aguardam atualização no Home Assistant.

## Arquivos exportados — Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `790c9804587e9ec25d5ecde67ee62c0322c0d39c` |
| `instagram-central/config.yaml` | `defccabed2b3d52741c80dd2fc04d943abe68ada` |
| `instagram-central/server.py` | `1b1d56bfc5150027945761d9614761eee12fe9e6` |

## Integridade
- Os três blobs foram criados a partir da candidata RC indicada.
- Nenhum outro caminho foi alterado nesta exportação.
