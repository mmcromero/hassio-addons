# Proveniência — Central Instagram 0.1.53

- Fonte canônica: `mmcromero/instagram-automacoes`, branch `release-candidate`.
- SHA integral da candidata: `7af22aa118db21e88d60db848c440eb811df43cf`.
- Versão: 0.1.53; slug `umdoislab_instagram`; arquitetura declarada aarch64; Dockerfile com build pelo Supervisor.
- Destino: `mmcromero/hassio-addons:main/instagram-central/`.
- Exportação por comparação integral das árvores: 102 arquivos da fonte, 95 já idênticos, 7 atualizados. Preservados ícone, logo e 12 registros históricos de proveniência do catálogo; outros add-ons e workflows intactos.
- Recuperação de sessão: retorno local validado após login; tratamento de navegação e de requisições da interface; sem repetição automática de operações. Sem alterações a credenciais, dados persistentes, webhook, proxy, Meta ou n8n.
- Verificações: 43 casos isolados Python (trechos do validador, formulário e gate, com sessão simulada); 5 casos isolados JS (cliente de sessão com navegador simulado); sintaxe dos 2 arquivos JS completa validada. Suíte HTTP integrada, build ARM64 e homologação em navegador ainda não executados. Testes de regressão estão incluídos no Dockerfile.
- Nenhum arquivo novo de runtime ou segredo; valores sensíveis no manifesto continuam vazios. Nenhuma instalação ou reinício autorizado nesta etapa.

## Arquivos atualizados — Git blob SHA-1 da candidata

| Arquivo | Blob SHA |
|---|---|
| `instagram-central/CHANGELOG.md` | `263998d6fb2912a8fcd92fe3f009f5f46fe7e359` |
| `instagram-central/README.md` | `a340993ab7991f599c3ec37b0dfd9a9a5f78c0aa` |
| `instagram-central/config.yaml` | `71689aa8f5171401be14bda1e9f19b6646b834d3` |
| `instagram-central/editorial-ui/editorial.js` | `9cddda745ba445de8d008a517650c3da2b538d36` |
| `instagram-central/interface-ui.js` | `9985e6af8e75364643a4de1f9676f4246193ab59` |
| `instagram-central/server.py` | `ec33de67bbfc19598b2b795d8b46055d7914f71a` |
| `instagram-central/tests/test_http.py` | `bc56b182bef9bd023bed680f922e54d5054d389e` |
