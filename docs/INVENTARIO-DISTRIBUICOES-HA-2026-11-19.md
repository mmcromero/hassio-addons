# Inventário e padronização — Distribuição Home Assistant

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


**Data:** 2026-11-19  
**Responsável:** Governança  
**Escopo:** repositórios GitHub acessíveis e catálogo `mmcromero/hassio-addons`. **Sem acesso à lista de lojas instaladas no Raspberry**; não declarar remoção ou migração executada.

## Arquitetura obrigatória

Cada produto preserva seu código-fonte, dados e documentação sensível no repositório apropriado. O `hassio-addons` é o catálogo público de pacotes HA, não substituto da fonte privada. As **cinco pastas** de add-on registradas na `main` usam identidades e versões próprias (verificação dos manifests em 20/11/2026). A publicação de distribuição não autoriza instalação, remoção de repositórios, atualização do HA nem promoção de código-fonte.

## Catálogo compartilhado — conteúdo confirmado na main

| Diretório | Slug | Versão | Arquitetura | Título no catálogo (19/11/2026) |
|---|---|---|---|---|
| evolution-api | evolution_api | 0.1.0 | aarch64 | Fábrica de Softwares - Evolution API WhatsApp |
| pager-virtual | pager_virtual | 0.1.20-rc.11 | aarch64, amd64 | Pager Virtual |
| umdoislab-central | umdoislab_central | 0.4.0 | aarch64 | Fábrica de Softwares - 12Labs Central de Atendimento |
| factory-runner | fabrica_software | 0.1.0-rc.17 | aarch64, amd64 | Fábrica de Softwares - Factory Runner |
| instagram-central | umdoislab_instagram | 0.1.4 | aarch64 | Fábrica de Softwares - Central Instagram |

**Identidade visual:** `icon.png` e `logo.png` idênticos aos arquivos oficiais atuais de `mmcromero/fabrica-de-ideias-kanban/kanban/`. SHA Git do ícone: `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`; logo: `7e500016222b0a5bf395be8ed17447edeb3e2af9`. Os **dez arquivos** (`icon.png` e `logo.png` em cada uma das cinco pastas) têm o mesmo SHA Git na `main`; verificação do SHA em 20/11/2026. Isso confirma identidade binária entre as cópias, mas não é uma revisão visual nem informa dimensões dos PNGs. Não altera `panel_icon` ou a identidade interna das aplicações.

## Distribuições HA em repositórios separados

| Produto | Repositório | Evidência | Conduta |
|---|---|---|---|
| Artesão Digital | `mmcromero/fabricacao-e-orcamentos-ha` | `repository.yaml`, `apps/artesaos-piloto/config.yaml` com `arch: aarch64`, versão 0.2.0-dev.28, slug artesaos_piloto | **Não remover a loja antiga.** Uso como contingência, preservar slug/instalação/dados. Planejar migração sem nova instalação involuntária |
| Fábrica de Ideias Kanban | `mmcromero/fabrica-de-ideias-kanban` | `repository.yaml`, `kanban/config.yaml` com `aarch64, amd64`, versão 0.0.25, slug kanban | **Não remover a loja antiga.** Avaliar integração posterior ao catálogo e distribuição pública separada conforme decisão do proprietário |
| Código de fabricação/orçamentos | `mmcromero/fabricacao_e_orcamentos` | materiais de build/distribuição `aarch64` e manifests internos; fonte própria | Não tratar código-fonte como loja extra sem verificar distribuição ativa |

**Local Apps:** é uma entrada da instalação HA, não um repositório Git identificado neste levantamento. Não foi possível verificar dependências e instalações ativas; não apagar nem desinstalar a entrada por inferência.

## Nota de revisão — 20/11/2026

- O cadastro [`.github/addon-registry.json`](../.github/addon-registry.json) contém cinco entradas: a Central Instagram já integra o catálogo e não constava neste inventário datado de 19/11.
- A Central Umdoislab continua com `name: "Fábrica de Softwares - 12Labs Central de Atendimento"` e `slug: umdoislab_central`. Esse slug identifica a instalação atual: **não renomeá-lo** para criar laboratório.
- Uma futura instância de laboratório exige registro de outra pasta/ID/slug, com identidade e versão explícitas, e validação do catálogo. O catálogo ainda **não registra** uma segunda Central; não declarar instalação ou escolher slug como fato documentado.
- O `panel_icon: mdi:message-processing-outline` da Central é independente de `icon.png` e `logo.png`. Não substituir nenhuma dessas imagens com arte genérica.

## Padronização aplicada e limites

- Título comum: **Fábrica de Softwares - Nome do aplicativo** no campo `name` do manifest do add-on. Não modificar `slug`, versão ou ID só para agrupar títulos.
- Logos: duas imagens padronizadas em todos os quatro diretórios do catálogo.
- Avisaqui: título novo e imagens já colocados na fonte privada `desenvolvimento` para próximo corte; **não alterar isoladamente o `pager-virtual/config.yaml` distribuído**, pois o pacote RC11 possui `SOURCE_PROVENANCE.json` e verificação por hash/arquivos. Próximo fechamento autorizado deve gerar distribuição auditável e atualizar os campos necessários com novos SHA e versão conforme a rotina específica.
- Outros três títulos foram publicados na `main` do catálogo, sem modificar versões, slugs nem rotinas internas.
- O uso do mesmo título no catálogo pode facilitar agrupamento visual, mas a posição exata na interface do HA depende da UI/ordenação e não foi homologada no Raspberry.
- Sem acesso de leitura ao Supervisor desta instalação: **não afirmar** quais lojas estão configuradas, quais apps estão instalados ou quando serão removidos.

## Etapas antes de limpar a loja do HA

1. Obter inventário real de repositórios cadastrados, apps instalados, slugs e volumes/dados do Supervisor, sem mudanças no host.
2. Separar por uso atual, app instalado e dependência de atualização. Preservar lojas de Artesão Digital/Kanban enquanto não houver estratégia de migração que mantenha ID de instalação, dados e continuidade.
3. Fazer migrações apenas em lote específico autorizado, com backup/verificação do alvo exato quando houver risco de dados, seguida de homologação real.
4. Remover entradas antigas somente após comprovar que não servem a nenhuma instalação e mediante autorização expressa.

**Regra operacional universal:** [CONTRIBUTING.md](../CONTRIBUTING.md) e [AGENTS.md](../AGENTS.md). O Supervisor pode construir no equipamento alvo quando aplicável. Build ARM64 externo/QEMU/Actions não são gates genéricos. Segurança e testes por risco continuam exigidos.
