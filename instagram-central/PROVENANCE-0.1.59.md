# Proveniência — Central Instagram 0.1.59

- Repositório-fonte: `mmcromero/instagram-automacoes`
- Branch congelada: `release-candidate`
- SHA-fonte: `9035d1c2e1aca415b3e6c57827ad95d9e5c73183`
- Árvore-fonte: `0e335c84ff813b1c240c4f2899f162bea22ed1c2`
- Diretório exportado: `instagram-central/`
- Destino: `mmcromero/hassio-addons:main/instagram-central/`
- Versão declarada em `config.yaml`: `0.1.59`
- Arquivos do pacote copiados nesta publicação: 10
- Arquivos adicionais próprios do catálogo (`icon.png`, `logo.png` e proveniências anteriores) preservados.
- Commit público do catálogo (pacote): `7b5659cd9c82d052990101d163ee0b98ed20c141`

## Arquivos copiados

| Arquivo | Git blob SHA |
|---|---|
| `CHANGELOG.md` | `40ba45421a9c197d728e5b4518076a98ba302242` |
| `Dockerfile` | `b2f3f1e7cb474603d1167078d4ca7866533d19a5` |
| `README.md` | `bba9b029b8ce84e17f74d2ecc9e97a1f3884e445` |
| `config.yaml` | `2351d1a285090061066fbfd95e3557f297bf84e9` |
| `policy.py` | `5e2c6c8ac762a35ddb8b833c1b0a96f58b774506` |
| `server.py` | `38e4dcf9f99bd3d81cd39949ed478aeb82442ea5` |
| `tests/test_http.py` | `0933336d20d4023b99508d53f58869d3224df965` |
| `tests/test_policy.py` | `969424daa23104c9bc68fb621fc73f393478f13b` |
| `tests/test_server.py` | `5dbd522bf61502b90dbdc1e6aac2d6a7fd03a7b0` |
| `tests/test_smoke.py` | `636e2f2e85c3ee543e01eb1ee812968df4e544cf` |

## Homologação

- Home Assistant antes da atualização: versão `0.1.58` instalada.
- Build ARM64 e suíte do Dockerfile: **pendentes**; não declarar PASS antes do resultado do Supervisor.
- Instalação 0.1.59: **pendente**.
- Homologação funcional: **pendente**.
- Workflows n8n, credenciais, configuração Meta, WhatsApp e demais add-ons: não alterados nesta publicação.


## Resultado da homologação no Home Assistant

- Add-on existente: `45c28620_umdoislab_instagram`.
- Supervisor ARM64: `Build 45c28620/aarch64-addon-umdoislab_instagram:0.1.59 done` em 24/11/2026 18:18:37 -03.
- Atualização do Supervisor concluída às 18:18:42 -03; versão instalada/latest `0.1.59`, estado `started`, `update_available=false`.
- Health check interno `GET /health`: HTTP 200, `ok=true`, `version=0.1.59`.
- Controle da ponte `POST /bridge/context` sem credencial: HTTP 403 `access denied`, comportamento esperado. A rota existe e exige autenticação.
- O build ARM64 foi concluído. Como o Dockerfile encadeia as etapas com `&&`, compilação e as 16 suítes declaradas terminaram com código zero. Os logs consultados não expuseram a saída individual de cada suíte; não há contagens por teste registradas.
- Logs atuais não mostram erro de execução da versão 0.1.59. Registros de `BrokenPipeError` e de build anterior pertencem a versões/eventos anteriores.
- Adapter n8n Instagram `XkIn9QnqW6Tml5Ld`: atualmente inativo (`active=false`, `activeVersionId=null`), draft `937ca466-c305-4a44-9a43-9bc331a5f6d6`. O núcleo compartilhado `71LrWsU2wdIfT7Hs` está ativo na versão `44e6c678-676f-4faa-8f32-bc2411ac6702`.
- Não houve teste ponta a ponta de mensagem nem envio externo nesta homologação. Nenhum workflow n8n, credencial, configuração Meta, WhatsApp ou outro add-on foi alterado.
- Estado final desta publicação: Central 0.1.59 instalada e saudável; integração ponta a ponta depende da autorização separada para publicar/ativar o adapter em TESTES RESTRITOS.
