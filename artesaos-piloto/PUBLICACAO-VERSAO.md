# Publicação de candidata — 0.2.0-dev.39

- Fonte privada: `mmcromero/fabricacao_e_orcamentos`
- Branch congelada: `release-candidate`
- SHA da fonte: `6beba7fb1f56f30208854b206dc3b3d693307f96`
- Destino: `mmcromero/hassio-addons:main/artesaos-piloto/`
- Slug preservado: `artesaos_piloto`
- Arquitetura: `aarch64`
- Build: Node.js 24.19.0 pelo Supervisor no Raspberry Pi

## Escopo

Importação de fabricação com conciliação WooCommerce e Excel. WooCommerce é a fonte prioritária de categorias, incluindo categorias vazias; a planilha apenas complementa categorias ausentes. A prévia das categorias antecede a conciliação dos produtos. Nenhuma importação real é confirmada automaticamente.

## Correções após o primeiro build

- O build dev.38 identificou dois acessos TypeScript não estreitados entre categorias e produtos; corrigidos com guarda explícita e variável local discriminada.
- O `.dockerignore` excluía `test/`, fazendo o comando `npm test` encontrar zero testes. A exclusão foi removida; a suíte passa a fazer parte do contexto de build e continua fora da imagem final.

## Validação

- Análise dos logs do Supervisor dev.38: causa identificada.
- Correção de tipagem e inclusão da suíte no contexto Docker: registradas.
- Testes Node.js 24, build e verificação de schema dev.39: pendentes do novo build no Supervisor.
- Instalação e homologação funcional: pendentes.
- Nenhuma categoria ou produto real foi gravado durante a preparação.

Candidata experimental para homologação no Home Assistant; não é uma declaração de estabilidade.
