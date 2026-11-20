# Inventário e padronização — Distribuição Home Assistant

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


**Data:** 2026-11-19  
**Responsável:** Governança  
**Escopo:** repositórios GitHub acessíveis e catálogo `mmcromero/hassio-addons`. **Sem acesso à lista de lojas instaladas no Raspberry**; não declarar remoção ou migração executada.

## Arquitetura obrigatória

Cada produto preserva seu código-fonte, dados e documentação sensível no repositório apropriado. O `hassio-addons` é o catálogo público de pacotes HA, não substituto da fonte privada. As seis pastas de add-on publicadas em 20/11/2026 usam identidades e versões próprias. A publicação de distribuição não autoriza instalação, remoção de repositórios, atualização do HA nem promoção de código-fonte.

## Catálogo compartilhado — revisão dos manifests na main em 20/11/2026

| Diretório | Slug | Versão | Arquitetura | Nome no manifesto publicado |
|---|---|---|---|---|
| evolution-api | evolution_api | 0.1.0 | aarch64 | Fábrica de Softwares - Evolution API WhatsApp |
| pager-virtual | pager_virtual | 0.1.20-rc.11 | aarch64, amd64 | Pager Virtual |
| umdoislab-central | umdoislab_central | 0.4.0 | aarch64 | Fábrica de Softwares - 12Labs Central de Atendimento *(nome legado; correção em branch)* |
| umdoislab-central-lab | umdoislab_central_lab | 0.4.1-rc.1 | aarch64 | Fábrica de Softwares - Umdoislab Central de Atendimento (LAB) |
| factory-runner | fabrica_software | 0.1.0-rc.18 | aarch64, amd64 | Fábrica de Softwares - Factory Runner |
| instagram-central | umdoislab_instagram | 0.1.5 | aarch64 | Fábrica de Softwares - Central Instagram |

**Identidade visual:** `icon.png` e `logo.png` são iguais, em SHA Git, nas seis pastas. Ícone: `a0fdd10938db1b6a65aa60469e83ed1c7c9bd33a`; logo: `7e500016222b0a5bf395be8ed17447edeb3e2af9`. São os arquivos do catálogo documentados na identidade atual do Kanban. `panel_icon` é configuração independente.

**Situação LAB:** o pacote Umdoislab foi publicado na [`main`](https://github.com/mmcromero/hassio-addons/commit/d73cebc3504d0f800501bcb6a30e92db7d98dd9e) como instalação separada, sem instalar no dispositivo nem modificar `umdoislab_central`. O nome legado da Central anterior continua publicado na main até atualização específica, preparada em branch. Não confundir publicação, instalação e homologação.

## Distribuições HA em repositórios separados

| Produto | Repositório | Evidência | Conduta |
|---|---|---|---|
| Artesão Digital | `mmcromero/fabricacao-e-orcamentos-ha` | `repository.yaml`, `apps/artesaos-piloto/config.yaml` com `arch: aarch64`, versão 0.2.0-dev.28, slug artesaos_piloto | **Não remover a loja antiga.** Uso como contingência, preservar slug/instalação/dados. Planejar migração sem nova instalação involuntária |
| Fábrica de Ideias Kanban | `mmcromero/fabrica-de-ideias-kanban` | `repository.yaml`, `kanban/config.yaml` com `aarch64, amd64`, versão 0.0.25, slug kanban | **Não remover a loja antiga.** Avaliar integração posterior ao catálogo e distribuição pública separada conforme decisão do proprietário |
| Código de fabricação/orçamentos | `mmcromero/fabricacao_e_orcamentos` | materiais de build/distribuição `aarch64` e manifests internos; fonte própria | Não tratar código-fonte como loja extra sem verificar distribuição ativa |

**Local Apps:** é uma entrada da instalação HA, não um repositório Git identificado neste levantamento. Não foi possível verificar dependências e instalações ativas; não apagar nem desinstalar a entrada por inferência.

## Padronização aplicada e limites

- Título comum: **Fábrica de Softwares - Nome do aplicativo** no campo `name` do manifest do add-on. Não modificar `slug`, versão ou ID só para agrupar títulos.
- Logos: dois arquivos padronizados em cada um dos seis diretórios do catálogo (12 arquivos com os mesmos dois hashes).
- Avisaqui: título novo e imagens já colocados na fonte privada `desenvolvimento` para próximo corte; **não alterar isoladamente o `pager-virtual/config.yaml` distribuído**, pois o pacote RC11 possui `SOURCE_PROVENANCE.json` e verificação por hash/arquivos. Próximo fechamento autorizado deve gerar distribuição auditável e atualizar os campos necessários com novos SHA e versão conforme a rotina específica.
- O LAB Umdoislab tem identidade e slug próprios. A correção de nome da Central anterior ainda está preparada em branch, sem atualizar a instalação.
- O uso do mesmo título no catálogo pode facilitar agrupamento visual, mas a posição exata na interface do HA depende da UI/ordenação e não foi homologada no Raspberry.
- O inventário de instalações de 19/11/2026 deriva de captura do proprietário; os manifests do GitHub não demonstram estado atual do Supervisor. O acesso do conector n8n à API de add-ons retornou 401; não afirmar instalação do LAB sem confirmação.

## Etapas antes de limpar a loja do HA

1. Obter inventário real de repositórios cadastrados, apps instalados, slugs e volumes/dados do Supervisor, sem mudanças no host.
2. Separar por uso atual, app instalado e dependência de atualização. Preservar lojas de Artesão Digital/Kanban enquanto não houver estratégia de migração que mantenha ID de instalação, dados e continuidade.
3. Fazer migrações apenas em lote específico autorizado, com backup/verificação do alvo exato quando houver risco de dados, seguida de homologação real.
4. Remover entradas antigas somente após comprovar que não servem a nenhuma instalação e mediante autorização expressa.

**Regra operacional universal:** [CONTRIBUTING.md](../CONTRIBUTING.md) e [AGENTS.md](../AGENTS.md). O Supervisor pode construir no equipamento alvo quando aplicável. Build ARM64 externo/QEMU/Actions não são gates genéricos. Segurança e testes por risco continuam exigidos.
