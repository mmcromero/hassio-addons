# Inventário e padronização — Distribuição Home Assistant

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


**Data:** 2026-11-19  
**Responsável:** Governança  
**Escopo:** repositórios GitHub acessíveis e catálogo `mmcromero/hassio-addons`. **Sem acesso à lista de lojas instaladas no Raspberry**; não declarar remoção ou migração executada.

## Arquitetura obrigatória — revisão do catálogo em 20/11/2026

Cada produto conserva sua fonte, sua documentação e seus dados; o `hassio-addons` distribui pacotes, não substitui a fonte privada. A `main` registra **cinco** pastas de add-on. Publicar não instala nem homologa.

## Catálogo compartilhado — leitura dos manifests na main

| Diretório | Slug | Versão | Arquitetura | Nome publicado |
|---|---|---|---|---|
| evolution-api | evolution_api | 0.1.0 | aarch64 | Fábrica de Softwares - Evolution API WhatsApp |
| pager-virtual | pager_virtual | 0.1.20-rc.11 | aarch64, amd64 | Pager Virtual |
| umdoislab-central | umdoislab_central | 0.5.0-rc.1 | aarch64 | Fábrica de Softwares - WhatsApp Umdoislab |
| factory-runner | fabrica_software | 0.1.0-rc.19 | aarch64, amd64 | Fábrica de Softwares - Factory Runner |
| instagram-central | umdoislab_instagram | 0.1.6 | aarch64 | Fábrica de Softwares - Central Instagram |

**Identidade visual:** ícones e logos em bytes padronizados: Git blob SHA `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a` e `7e500016222b0a5bf395be8ed17447edeb3e2af9`. `panel_icon` é propriedade distinta dos PNGs.

**WhatsApp:** o pacote original `umdoislab-central/` está publicado como candidato 0.5.0-rc.1, com código do PR privado #10 e o mesmo slug da instalação anterior. O LAB `umdoislab-central-lab/` foi **retirado somente do catálogo**; continua no histórico Git e nenhuma desinstalação de app/dados foi executada no HA. A presença/ausência do LAB instalado precisa ser observada no Supervisor antes de qualquer intervenção local.

## Distribuições HA em repositórios separados

| Produto | Repositório | Evidência | Conduta |
|---|---|---|---|
| Artesão Digital | `mmcromero/fabricacao-e-orcamentos-ha` | `repository.yaml`, `apps/artesaos-piloto/config.yaml` com `arch: aarch64`, versão 0.2.0-dev.28, slug artesaos_piloto | **Não remover a loja antiga.** Uso como contingência, preservar slug/instalação/dados. Planejar migração sem nova instalação involuntária |
| Fábrica de Ideias Kanban | `mmcromero/fabrica-de-ideias-kanban` | `repository.yaml`, `kanban/config.yaml` com `aarch64, amd64`, versão 0.0.25, slug kanban | **Não remover a loja antiga.** Avaliar integração posterior ao catálogo e distribuição pública separada conforme decisão do proprietário |
| Código de fabricação/orçamentos | `mmcromero/fabricacao_e_orcamentos` | materiais de build/distribuição `aarch64` e manifests internos; fonte própria | Não tratar código-fonte como loja extra sem verificar distribuição ativa |

**Local Apps:** é uma entrada da instalação HA, não um repositório Git identificado neste levantamento. Não foi possível verificar dependências e instalações ativas; não apagar nem desinstalar a entrada por inferência.

## Padronização aplicada e limites

- Título comum: **Fábrica de Softwares - Nome do aplicativo** no campo `name` do manifest do add-on. Não modificar `slug`, versão ou ID só para agrupar títulos.
- Logos: dois arquivos padronizados em cada um dos cinco diretórios do catálogo (10 arquivos com os mesmos dois hashes).
- Avisaqui: título novo e imagens já colocados na fonte privada `desenvolvimento` para próximo corte; **não alterar isoladamente o `pager-virtual/config.yaml` distribuído**, pois o pacote RC11 possui `SOURCE_PROVENANCE.json` e verificação por hash/arquivos. Próximo fechamento autorizado deve gerar distribuição auditável e atualizar os campos necessários com novos SHA e versão conforme a rotina específica.
- O pacote LAB do WhatsApp foi retirado da loja pública; a Central original mantém o slug e o nome visível já atualizado na main. Nenhum dado foi apagado no Home Assistant.
- O uso do mesmo título no catálogo pode facilitar agrupamento visual, mas a posição exata na interface do HA depende da UI/ordenação e não foi homologada no Raspberry.
- O inventário de instalações de 19/11/2026 deriva de captura do proprietário; os manifests do GitHub não demonstram estado atual do Supervisor. O acesso do conector n8n à API de add-ons retornou 401; não afirmar instalação do LAB sem confirmação.

## Etapas antes de limpar a loja do HA

1. Obter inventário real de repositórios cadastrados, apps instalados, slugs e volumes/dados do Supervisor, sem mudanças no host.
2. Separar por uso atual, app instalado e dependência de atualização. Preservar lojas de Artesão Digital/Kanban enquanto não houver estratégia de migração que mantenha ID de instalação, dados e continuidade.
3. Fazer migrações apenas em lote específico autorizado, com backup/verificação do alvo exato quando houver risco de dados, seguida de homologação real.
4. Remover entradas antigas somente após comprovar que não servem a nenhuma instalação e mediante autorização expressa.

**Regra operacional universal:** [CONTRIBUTING.md](../CONTRIBUTING.md) e [AGENTS.md](../AGENTS.md). O Supervisor pode construir no equipamento alvo quando aplicável. Build ARM64 externo/QEMU/Actions não são gates genéricos. Segurança e testes por risco continuam exigidos.
