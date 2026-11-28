# Publicação de candidata — 0.2.0-dev.40

- Fonte privada: `mmcromero/fabricacao_e_orcamentos`
- Branch congelada: `release-candidate`
- SHA da fonte: `d20af4c496d515e6a252894ee6ef12f1ec5967ae`
- Destino: `mmcromero/hassio-addons:main/artesaos-piloto/`
- Slug preservado: `artesaos_piloto`
- Arquitetura: `aarch64`
- Build: Node.js 24.19.0 pelo Supervisor no Raspberry Pi

## Escopo

Importação de fabricação com conciliação WooCommerce e Excel. WooCommerce é a fonte prioritária de categorias, incluindo categorias vazias; a planilha apenas complementa categorias ausentes. A prévia das categorias antecede a conciliação dos produtos. Nenhuma importação real é confirmada automaticamente.

## Correções identificadas pelos builds do Supervisor

- dev.38: erro TypeScript de narrowing e `test/` excluído do contexto Docker.
- dev.39: suíte executou 12 testes; corrigidos escape inválido de regex em `test/reconciliation.test.ts` e asserção antiga do ID de rodapé em `test/pilot-entry.test.ts`.
- dev.40: inclui as duas correções; novo build e suíte Node.js 24 pendentes de execução no Supervisor.

## Validação

- Testes de categorias WooCommerce: passaram no build dev.39.
- Suíte completa dev.40: pendente.
- Build, verificação de schema e runtime: pendentes.
- Instalação e homologação funcional: pendentes.
- Nenhuma categoria ou produto real foi gravado durante a preparação.

Candidata experimental para homologação no Home Assistant; não é uma declaração de estabilidade.
