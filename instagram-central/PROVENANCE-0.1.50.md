# Proveniência — Central Instagram 0.1.50

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `ab7f6045b1f1d6b8b640c7d9fe08b7fed703e802`.
- Versão: `0.1.50`; slug `umdoislab_instagram`; arquitetura declarada `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Corrige as expectativas de versão dos testes HTTP que bloquearam o build 0.1.49; `APP_VERSION`, manifesto e asserções passam a concordar com 0.1.50.
- Preserva a correção de encaminhamento POST-only e os testes de proxy distribuído introduzidos em 0.1.48.
- Exportação incremental limitada aos quatro arquivos listados abaixo e a este registro; demais arquivos, ícone, logo, opções do catálogo e outros add-ons preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- A build ARM64 0.1.50 no Supervisor concluiu às 02:32:47 BRT; o contêiner iniciou às 02:32:52 BRT. Como a suíte Dockerfile é a etapa final do build, a execução integral das suítes listadas no Dockerfile terminou sem erro. O endpoint interno `/health` confirmou `version=0.1.50` e o app permaneceu `started`.
- A build 0.1.49 havia falhado por três expectativas antigas de versão em `tests/test_http.py`; corrigidas na 0.1.50.
- A configuração NGINX ativa em `/share/nginx_proxy/instagram.conf` ainda não foi substituída nem validada com `nginx -t`; portanto a rota POST não está homologada externamente. Não há PASS funcional do formulário até aplicar e validar esse fragmento.

## Arquivos exportados — Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `9768b3b70f47ac096e0b105ef977b9fc3b81e3b8` |
| `instagram-central/config.yaml` | `9fcfa63ca015ced7a97d20bee38b70b1ef65fc7e` |
| `instagram-central/server.py` | `dec86dbae43922bd79dacf94a5623c54627dfd6b` |
| `instagram-central/tests/test_http.py` | `cc2b362c90d7dc7c54641eb0ab22bdb8f748bf8a` |

## Integridade
- Os quatro blobs foram criados a partir da candidata RC indicada.
- Nenhum outro caminho foi alterado nesta exportação.
