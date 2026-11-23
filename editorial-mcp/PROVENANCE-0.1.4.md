# Proveniência da publicação — Central Editorial MCP 0.1.4

- Catálogo: `mmcromero/hassio-addons:main/editorial-mcp/`
- Fonte: `mmcromero/instagram-automacoes:release-candidate/editorial-mcp/`
- Versão declarada: `0.1.4`
- Slug: `editorial_mcp_universal`
- Arquiteturas: `aarch64`, `amd64`
- Estado: **publicado no GitHub; build ARM64 do Supervisor pendente de nova execução.**

## Correções motivadas por log real

O Supervisor tentou construir a versão 0.1.3 em ARM64 em 23/11/2026. `py_compile` passou; dos 24 testes, 22 passaram e dois falharam:
1. `test_server.Contract.test_lifecycle_and_tools` esperava `serverInfo.version = 0.1.2`, mas o código já declarava 0.1.3.
2. `test_diagnostics.DiagnosticsOptionCompatibility.test_missing_option_is_disabled_for_existing_installations` gerou `NameError: run is not defined`, porque o teste importava apenas `sanitize_netcheck`.

Correções aplicadas:
- `test_diagnostics.py`: import explícito de `run`.
- `test_server.py`: expectativa atualizada para 0.1.4.
- `server.py`: `VERSION = '0.1.4'`.
- `config.yaml`: versão 0.1.4, criando uma tag nova de build e evitando reutilizar a imagem 0.1.3 que falhou.
- `CHANGELOG.md` e README raiz atualizados.

## Verificações de publicação

Os arquivos alterados foram conferidos na fonte privada e exportados para a pasta única `editorial-mcp/` do catálogo. O build da 0.1.4 **ainda não foi executado**. Não declarar testes aprovados, instalação ou homologação até a leitura do resultado do Supervisor.

## Impedimento operacional atual

O conector HA respondeu `READ_ONLY_MODE` ao tentar `check_updates`; nenhuma ação de escrita foi executada. A loja já reconhece a versão 0.1.3, mas o app instalado permanece 0.1.0. A nova versão 0.1.4 exige atualização da loja e nova tentativa de instalação/build após liberar o modo de escrita do conector.
