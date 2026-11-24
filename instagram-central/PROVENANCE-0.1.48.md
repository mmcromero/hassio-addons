# Proveniência — Central Instagram 0.1.48

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA da candidata: `4b3e242bcaf8ff003d954fe52ffab6d769dc23d8`.
- Versão: `0.1.48`; slug `umdoislab_instagram`; arquitetura declarada `aarch64`.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Corrige o encaminhamento POST-only do formulário `/panel/automation/policy`, incluindo a rota com prefixo de conta.
- Corrige o fragmento NGINX distribuído para conter blocos com quebras de linha reais.
- Acrescenta teste para geração e arquivo distribuído; o Dockerfile passa a executar esse teste durante o build do Supervisor.
- A política de atendimento permanece em Testes com lista vazia por padrão. Não ativa workflow, não altera credenciais, Meta ou dados persistidos.
- Exportação limitada aos seis arquivos listados abaixo e a este registro de proveniência. Ícone, logo, opções do catálogo, demais add-ons e arquivos compartilhados foram preservados.
- Nenhum segredo, token, banco, opção privada ou dado de cliente foi exportado.
- Teste dirigido de geração executado em ambiente local isolado: PASS. Suíte completa do Dockerfile, build ARM64 e homologação funcional ainda aguardam execução no Supervisor/Home Assistant. A publicação no catálogo não equivale a instalação ou homologação.

## Arquivos exportados — Git blob SHA-1

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `bac7c86c929368a605ae2504642834b065eff421` |
| `instagram-central/Dockerfile` | `ad1300bf3d7727941e2038ffcaafb582056570a7` |
| `instagram-central/config.yaml` | `85a1aa348d90c62c11394143e284af893cddad2d` |
| `instagram-central/proxy/instagram.conf` | `42cbf03a93e1adc8cab878c6871661adef9d6dd8` |
| `instagram-central/tests/test_proxy_automation_policy.py` | `067a527dc645753c308193b585f5f5f1d295fb66` |
| `instagram-central/tools/generate_proxy.py` | `a405d2d64e57ca19f854e6810dd76daa405afa09` |

## Integridade
- Os seis blobs exportados foram criados a partir do conteúdo da candidata RC congelada.
- A árvore pública foi baseada no HEAD existente do catálogo; somente os seis caminhos do pacote e este arquivo de proveniência foram alterados/adicionados.
