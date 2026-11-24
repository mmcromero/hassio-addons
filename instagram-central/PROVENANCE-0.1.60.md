# Proveniência — Central Instagram 0.1.60

- Repositório-fonte: `mmcromero/instagram-automacoes`
- Branch congelada: `release-candidate`
- SHA-fonte: `581450de41691a877a22ddf67d3d0244389b26d3`
- Árvore-fonte: `635cab8a2c2e735d6aa88db038dbcea07c5984df`
- Diretório exportado: `instagram-central/`
- Destino: `mmcromero/hassio-addons:main/instagram-central/`
- Versão: `0.1.60`
- Exportação incremental: seis arquivos alterados; os demais arquivos da fonte já correspondem ao catálogo. Ícones e proveniências anteriores preservados.

| Arquivo | Git blob SHA |
|---|---|
| `CHANGELOG.md` | `33010c3b347cc256a052245be58ca8468d7a0602` |
| `README.md` | `7a24327243875a1f2e01a0fff7e30170848eb369` |
| `config.yaml` | `366915453693c6ab0d751850dbb8236fb85b5f4b` |
| `server.py` | `bdbc926f53bc53ffac80e9e966b2d8f075fed764` |
| `tests/test_http.py` | `90e3e5694c8379fe0960a46f1bb8137786b2fa41` |
| `tests/test_server.py` | `68a125c1dbb73768a449a2bcc03ae617f2f3d2c3` |

## Validação

- Harness dirigido Python/SQLite: 13/13 verificações PASS, incluindo concorrência e eventos atrasados. Não equivale à suíte integral.
- Build ARM64 e suíte completa: pendentes no Supervisor.
- Instalação e homologação de mensagem nova: pendentes.
- Adapter Instagram permanece desativado até a validação da instalação e preparação do teste. WhatsApp, demais apps, credenciais e políticas não alterados.
