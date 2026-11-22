# AGENTS.md — Instruções universais do catálogo Home Assistant

> **CONSULTA DIRETA AO HOME ASSISTANT (22/11/2026):** o plugin pessoal **Home Assistant — Somente leitura** foi homologado para inventário, versões, estados e logs via Supervisor. Todas as equipes devem consultar o [manual operacional HA-MCP](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) e, quando a ferramenta estiver disponível e a leitura for pertinente à função, utilizá-la antes de pedir esses dados ao proprietário. Não autoriza escrita, compartilhamento de credenciais, acesso a dados pessoais não pertinentes ou alterações no Forja. O túnel n8n existente também foi migrado para uma segunda entrada da mesma integração no Raspberry Pi; chamadas reais foram homologadas com o CMD do Windows interrompido. Recuperação após reinício do Core/host ainda pendente; disponibilidade em outros chats deve ser verificada.

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


## Túneis compartilhados ChatGPT ↔ HA-MCP / n8n (22/11/2026)

Antes de diagnosticar, configurar ou usar os túneis compartilhados, ler o [manual operacional HA-MCP e n8n](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) e o [inventário do Raspberry](docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). A integração OpenAI Tunnel for HA-MCP está instalada uma vez e mantém duas entradas independentes: HA-MCP e n8n. Não reinstalar, duplicar entradas, recriar Tunnel IDs ou gerar chaves por tentativa. O túnel n8n já foi migrado do CMD Windows para o Raspberry e teve chamadas reais HTTP 200 após interromper o processo Windows.

**WhatsApp:** o webhook Evolution → n8n, o fluxo de atendimento e a Central WhatsApp são componentes de negócio separados dos túneis MCP. Não alterar Evolution, webhook, Gateway, worker ou credenciais comerciais para recuperar os túneis. O add-on distribuído em umdoislab-central/ tem fonte privada em mmcromero/whatsapp-automacoes. O manual dos túneis não altera o procedimento de atualização da Central nem autoriza instalação/reinício.

## P0 — Procedimento único para qualquer publicação no Home Assistant (19/11/2026)

**Aplica-se a todas as pessoas e agentes, independentemente do cargo, experiência ou projeto.** Ao receber ordem para criar, fechar, testar, empacotar ou publicar **qualquer add-on** por `mmcromero/hassio-addons`, consulte **antes de agir** a [rotina canônica do catálogo](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md) e o manual vigente do add-on. O procedimento cobre fechamento do lote, validações proporcionais, publicação isolada em `hassio-addons:main/<pasta-do-add-on>/` mediante autorização, verificação remota e homologação real no Home Assistant. O manual do produto define sua fonte, branch e exportação; **não aplicar nomes de branch exclusivos do Avisaqui aos demais add-ons**.

**Proibição de falso bloqueio:** ausência de QEMU, emulador, máquina ARM64 externa, Actions ou build ARM64 em CI **não é impedimento automático**. Para add-ons com Dockerfile sem `image` pré-compilada, o Supervisor **pode executar o build no dispositivo-alvo na instalação/atualização**; o teste real ocorre na fase apropriada de homologação. Mudança com binário nativo, imagem pré-compilada, falha demonstrada ou risco de segurança pode exigir teste adicional justificado. Nunca marcar teste não executado como PASS nem confundir publicação com instalação/homologação. Antes de NO-GO, identificar causa, fonte/revisão consultada, tentativa autorizada, alternativa GOV-BLK-002 e razão objetiva de não resolver. Sem isso, classificar como **DESVIO DE PROCEDIMENTO** e corrigir só a etapa afetada. Bloqueios reais de segurança, permissão e autorização permanecem.

**Fiscalização:** Governança/Tech Lead exigem evidência em tarefa real e anotação na Issue existente; publicação desta instrução não comprova que chats externos a carregaram.

## Aplicação obrigatória

- Toda tarefa recebida sobre pacote/add-on deste catálogo começa pela leitura do `CONTRIBUTING.md` **vigente na main** e do manual do add-on.
- Valide versão, SHA/HEAD, arquivos, arquitetura declarada, segredos e integridade conforme o diff e o risco. Não impor gates externos genéricos.
- Publique apenas a pasta do add-on autorizado na `main` do catálogo, mantendo os demais arquivos e add-ons intactos. Fonte privada e procedimentos próprios do produto devem ser respeitados.
- Registre o commit público e o resultado de verificação na Issue existente. Publicação, instalação, execução e homologação são estados distintos.
- Se houver instrução antiga contraditória, corrija-a no documento de origem quando autorizado; não invente novos fluxos. Normas superiores de segurança e autorizações prevalecem.


## UX-STD-001 — revisão e criação de interfaces

Referência documental registrada a pedido do proprietário em 22/11/2026: [UX-STD-001 v0.1](docs/ux/UX-STD-001_v0.1.md). Leia essa referência antes de planejar, revisar ou alterar telas neste projeto. A versão 0.1 preserva a pesquisa e a proposta original; seu registro não comprova aplicação ou homologação das telas existentes.

Planeje primeiro para celular. Defina a tarefa principal, agrupe o conteúdo por uso e mostre detalhes sob demanda. Use abas para poucas seções relacionadas e independentes; use telas próprias para tarefas extensas. Preserve dados, filtros e posição ao navegar. Evite empilhar funções independentes e evite cortar conteúdo para reduzir a altura. Apresente o mapa das seções e as evidências dos critérios de aceite aplicáveis.

Aplique ao trabalho com interfaces autorizado na demanda. Em firmware, bibliotecas, infraestrutura ou tarefas sem interface, registre os itens sem aplicação; não crie telas por consequência. Nos repositórios de distribuição, faça a evolução na fonte canônica do produto e siga a esteira vigente. Preserve identidade visual, regras de negócio, segurança e autorizações existentes. Esta referência não autoriza refatoração geral, publicação de pacote ou alteração de serviços. A cópia documental não se sincroniza automaticamente com outros repositórios ou chats.
