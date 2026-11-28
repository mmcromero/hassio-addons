# Publicação de candidata — 0.2.0-dev.38

- Fonte privada: `mmcromero/fabricacao_e_orcamentos`
- Branch congelada: `release-candidate`
- SHA da fonte: `5abf26edef62603d8a98fbd46ae73b35d235c42d`
- Destino: `mmcromero/hassio-addons:main/artesaos-piloto/`
- Slug preservado: `artesaos_piloto`
- Arquitetura: `aarch64`
- Build: Node.js 24.19.0 pelo Supervisor no Raspberry Pi

## Escopo

Importação de fabricação com conciliação WooCommerce e Excel. WooCommerce é a fonte prioritária de categorias, incluindo categorias vazias; a planilha apenas complementa categorias ausentes. A prévia das categorias antecede a conciliação dos produtos. Nenhuma importação real é confirmada automaticamente.

## Validação

- Revisão estática do diff e da origem: concluída.
- Schemas e dependências: sem alteração em relação à versão anterior.
- Testes Node.js 24, build e verificação de schema: pendentes do build no Supervisor.
- Instalação e homologação funcional: pendentes após publicação.
- Nenhuma categoria ou produto real foi gravado durante a preparação.

Candidata experimental para homologação no Home Assistant; não é uma declaração de estabilidade.
