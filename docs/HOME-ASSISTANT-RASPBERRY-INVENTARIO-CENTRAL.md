# HOME ASSISTANT / RASPBERRY PI — INVENTÁRIO OPERACIONAL CENTRAL

**Revisão:** 19/11/2026 (capturas fornecidas pelo proprietário nesta data)  
**Responsável editorial:** Governança  
**Natureza:** referência compartilhada entre todos os projetos que usam o mesmo Home Assistant. Fonte de código, configurações e credenciais continuam isoladas em seus projetos e no dispositivo. **Não é um backup nem acesso remoto ao Supervisor.**

## Leitura obrigatória para qualquer equipe

Antes de perguntar ao proprietário sobre apps, infraestrutura, repositórios, publicação, ARM64, n8n ou disponibilidade do laboratório, consultar este inventário, [AGENTS.md](../AGENTS.md), [CONTRIBUTING.md](../CONTRIBUTING.md), [inventário de distribuições](INVENTARIO-DISTRIBUICOES-HA-2026-11-19.md) e manual do subsistema. **Não repetir perguntas respondidas aqui**, mas verificar dados voláteis no Supervisor quando necessário. Se uma decisão depender da versão exata, configuração real, arquivos persistentes ou operação irreversível, não inferir dados ausentes.

## 1. Ambiente compartilhado

- **Hardware informado pelo proprietário e documentado anteriormente:** Raspberry Pi 4, 8 GB, arquitetura ARM64/aarch64, Home Assistant OS; não foi exibida nesta captura a versão exata do sistema, kernel, Supervisor, espaço em disco ou endereço de rede.
- É um ambiente **compartilhado** entre automações residenciais, serviços de mídia, n8n, integração WhatsApp, Artesão Digital em contingência, Avisaqui em homologação, Kanban e Factory Runner. Não aplicar automaticamente ao Raspberry o status de produção ou dados descartáveis de um projeto específico.
- Evitar intervenções que afetem serviços alheios. **Não reiniciar, remover, reinstalar, parar ou apagar dados** com base somente neste inventário. Ações sobre HA exigem permissão real e verificação do destino.
- **Catálogo central de distribuições:** https://github.com/mmcromero/hassio-addons ; não confundir distribuição com fonte privada. [Procedimento universal](../CONTRIBUTING.md).

## 2. Aplicativos instalados — evidência de captura da interface

**Fonte:** captura do proprietário em 19/11/2026 da grade de aplicativos instalados no Home Assistant. A captura mostra 29 cartões; os estados abaixo descrevem apenas o instante fotografado. **Não mostra versão de cada instalação, origem do app, ID da instalação, configurações, logs ou saúde de longo prazo.**

| Aplicativo exibido | Estado observado |
|---|---|
| Apache2 | Em execução |
| Artesão Digital — Contingência | Em execução |
| Bazarr | Em execução |
| Duck DNS | Em execução |
| ESPHome Device Builder | Parado — atualização disponível |
| Evolution API — WhatsApp | Em execução |
| Fabrica de Ideias — Kanban | Em execução |
| Fábrica de Software — Factory Runner | Em execução |
| Home Assistant Google Drive Backup | Em execução |
| Jellyfin | Em execução |
| Lidarr | Em execução |
| Lovelace Kindle Screensaver | Parado |
| MariaDB | Em execução |
| Mosquitto broker | Em execução |
| Music Assistant | Em execução |
| n8n | Em execução |
| Nextcloud | Parado |
| NGINX Home Assistant SSL proxy | Em execução — atualização disponível |
| Node-RED | Em execução |
| Pager Virtual | Em execução |
| Prowlarr | Em execução |
| qBittorrent | Em execução |
| Radarr | Em execução |
| Samba NAS2 | Em execução |
| Sonarr | Em execução |
| Studio Code Server | Em execução |
| Tailscale | Em execução |
| Terminal & SSH | Em execução |
| Umdoislab — Central de Atendimento | Em execução |

**Contagem observada:** 29 instalados; 26 em execução e 3 parados. São estados de interface, não testes funcionais ou disponibilidade comprovada por endpoints. **Nunca excluir app parado por esse motivo isolado.**

## 3. Repositórios cadastrados — evidência de outra captura do proprietário

Captura da tela de repositórios da loja em 19/11/2026: **11 entradas**. As três do proprietário são:

1. **Oficial central:** `https://github.com/mmcromero/hassio-addons` — manter.
2. **Artesão Digital:** `https://github.com/mmcromero/fabricacao-e-orcamentos-ha` — manter até migração segura da distribuição e conferência da instalação.
3. **Fábrica de Ideias Kanban:** `https://github.com/mmcromero/fabrica-de-ideias-kanban` — manter enquanto não houver migração aprovada e comprovada.

Oito outras entradas (terceiros): AlexxIT, Expaso, FaserF, alexbelgium, dianlight, Home Assistant Google Drive Backup, Legacy ESPHome versions, Lovelace Kindle Screensaver. **A captura não vincula cada app instalado a seu repositório; não concluir que alguma dessas lojas pode ser removida.** `Local Apps` não aparece na lista de repositórios, e pode ser categoria/local da instalação; origem e uso não verificados.

## 4. Separação de fonte e distribuição

O catálogo central contém quatro diretórios de app: `pager-virtual/`, `evolution-api/`, `umdoislab-central/`, `factory-runner/`. Os manifests do Git e as versões de distribuição estão no [inventário de distribuições](INVENTARIO-DISTRIBUICOES-HA-2026-11-19.md); **não assumir que versões instaladas são iguais às do GitHub.**

- Avisaqui/Pager Virtual: fonte `mmcromero/pager-virtual`; instalação atual aparece em execução; homologação específica permanece independente da publicação Git.
- Artesão Digital: fonte principal `mmcromero/fabricacao_e_orcamentos`; distribuição separada `mmcromero/fabricacao-e-orcamentos-ha`; contingência no Raspberry. **Preservar identidade da instalação e dados.**
- Kanban: repositório `mmcromero/fabrica-de-ideias-kanban` ainda mantém fonte/distribuição; versão do manifesto no Git não comprova a versão instalada.
- Evolution API, Central de Atendimento e Factory Runner: instalados e observados em execução; finalidade e procedimentos detalhados devem ser buscados nos manuais específicos, não presumidos pelo cartão da loja.

## 5. Operação e testes

- Para publicar qualquer pacote pelo `hassio-addons`, seguir [procedimento universal P0](../CONTRIBUTING.md): fechar lote e identificar fonte/HEAD, executar testes proporcionais, verificar versão/manifesto, segredos, arquitetura e proveniência, publicar somente a pasta autorizada, confirmar commit remoto e **separar publicação de instalação e homologação**.
- Ausência de QEMU, máquina ARM64 externa ou GitHub Actions **não é bloqueio automático**. Quando o app usa Dockerfile sem imagem pronta, o Supervisor pode construir no hardware alvo durante a instalação/atualização. O funcionamento real precisa ser verificado após instalação no HA; risco concreto pode exigir testes extras antes.
- Home Assistant Google Drive Backup aparece **em execução**, mas a captura não verifica a rotina, destino, criptografia, restauração ou quais apps estão incluídos. Não presumir que backups cubram todos os dados.
- n8n aparece em execução. Consultar o [inventário específico n8n](N8N-HOME-ASSISTANT-INVENTARIO.md) antes de criar workflows; sua presença na grade não valida workflows/credenciais.
- **Tailscale, NGINX SSL proxy, Duck DNS, Samba e Terminal & SSH** aparecem em execução, mas a captura não autoriza inferir URL, credencial, conectividade externa ou permissões da equipe.

## 6. Dados ainda não comprovados

- Versão HA OS, Supervisor, firmware e kernel; uso atual de CPU/RAM/disco, rede e portas efetivas.
- Versão instalada, slug/ID completo, origem e persistência de cada app; detalhes de reinício e logs.
- Quais lojas de terceiros ainda fornecem apps instalados; se `Local Apps` ainda possui instalações locais.
- Política e sucesso de backups/restore; dependências cruzadas entre serviços; disponibilidade de cada aplicação.

**A próxima verificação deve ser orientada por necessidade real de uma tarefa, sem pedir novamente os dados já registrados.** Para remoção de repositório ou migração, confirmar origem e identidade dos apps afetados e preservar dados; não executar remoção por inferência.

## 7. Controle de mudanças

A captura é evidência do estado de 19/11/2026, não estado vivo. Mudanças confirmadas devem atualizar **este documento central** na `main`, com data, origem, commit e referência à Issue existente. Os demais projetos devem **apontar para este arquivo**, não copiar inventários independentes que fiquem obsoletos. Nenhum documento autoriza ação destrutiva ou modifica automaticamente instruções em chats já abertos.
