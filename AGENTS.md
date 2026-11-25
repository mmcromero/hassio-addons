# P0 — Bootstrap universal GOV-ACT-001

**Roteamento de esteiras — GOV-STD-001 v1.4 §0.2:** em pedidos de release/deploy/publicação/instalação, descubra a rota internamente pelo mapa central e manual específico; não peça ao PO branch/comando/workflow que possa ser descoberto nem declare impedimento por desconhecimento. Mantenha o contexto da rota na conversa e revalide apenas SHA, versão, destino, gatilhos e autorização nos deploys seguintes. Não presuma esteira universal.

Leia a [fonte única central](https://github.com/mmcromero/governanca-master/blob/main/ATIVAR.md), a [GOV-STD-001 v1.2](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_STD_001.md) e o [mapa operacional de diretórios/esteiras](https://github.com/mmcromero/governanca-master/blob/main/docs/PORTFOLIO-ESTRUTURA-ESTEIRAS.md). Confirme versão/commit realmente acessados; falha de leitura = BLOQUEADO. /at e /atg são aliases conversacionais que exigem leitura real, não comandos nativos. AGENTS.md só orienta runtimes que o carregam; não sincroniza outros chats. Preserve as regras locais abaixo e não aplique a esteira de outro produto.

---

# AGENTS.md — Instruções universais do catálogo Home Assistant

> **HA-MCP — ACESSO OPERACIONAL DE LEITURA E ESCRITA (atualizado em 25/11/2026):** o proprietário confirmou que habilitou escrita no HA-MCP para permitir diagnóstico, correção, publicação/atualização, instalação e acompanhamento operacional de add-ons dentro do escopo de cada missão autorizada. Consultar o [manual operacional HA-MCP](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) antes de atuar. A autorização cobre somente o projeto/add-on/ambiente explicitamente abrangidos pela missão; não autoriza alterações em outros serviços, reinício do Core/host, exclusão/restauração de dados, mudanças de rede ou rotação de credenciais sem autorização específica. Verificar as ferramentas de escrita realmente disponíveis na sessão e os limites efetivos do servidor; a configuração e os testes de somente leitura de 22/11 são históricos, não o estado vigente. O túnel n8n permanece uma entrada independente. Recuperação após reinício do Core/host ainda pendente; disponibilidade em outros chats deve ser verificada.

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](https://github.com/mmcromero/hassio-addons/blob/main/docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.


## Túneis compartilhados ChatGPT ↔ HA-MCP / n8n (22/11/2026)

Antes de diagnosticar, configurar ou usar os túneis compartilhados, ler o [manual operacional HA-MCP e n8n](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) e o [inventário do Raspberry](docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). A integração OpenAI Tunnel for HA-MCP está instalada uma vez e mantém duas entradas independentes: HA-MCP e n8n. Não reinstalar, duplicar entradas, recriar Tunnel IDs ou gerar chaves por tentativa. O túnel n8n já foi migrado do CMD Windows para o Raspberry e teve chamadas reais HTTP 200 após interromper o processo Windows.

**WhatsApp:** o webhook Evolution → n8n, o fluxo de atendimento e a Central WhatsApp são componentes de negócio separados dos túneis MCP. Não alterar Evolution, webhook, Gateway, worker ou credenciais comerciais para recuperar os túneis. O add-on distribuído em umdoislab-central/ tem fonte privada em mmcromero/whatsapp-automacoes. O manual dos túneis não altera o procedimento de atualização da Central nem autoriza instalação/reinício.

## P0 — Procedimento único para qualquer publicação no Home Assistant (19/11/2026)

**Aplica-se a todas as pessoas e agentes, independentemente do cargo, experiência ou projeto.** Ao receber ordem para criar, fechar, testar, empacotar ou publicar **qualquer add-on** por `mmcromero/hassio-addons`, consulte **antes de agir** a [rotina canônica do catálogo](https://github.com/mmcromero/hassio-addons/blob/main/CONTRIBUTING.md) e o manual vigente do add-on. O procedimento cobre fechamento do lote, validações proporcionais, publicação isolada em `hassio-addons:main/<pasta-do-add-on>/` mediante autorização, verificação remota e homologação real no Home Assistant. O manual do produto define sua fonte, branch e exportação; **não aplicar nomes de branch exclusivos do Avisaqui aos demais add-ons**.

**Proibição de falso bloqueio:** ausência de QEMU, emulador, máquina ARM64 externa, Actions ou build ARM64 em CI **não é impedimento automático**. Para add-ons com Dockerfile sem `image` pré-compilada, o Supervisor **pode executar o build no dispositivo-alvo na instalação/atualização**; o teste real ocorre na fase apropriada de homologação. Mudança com binário nativo, imagem pré-compilada, falha demonstrada ou risco de segurança pode exigir teste adicional justificado. Nunca marcar teste não executado como PASS nem confundir publicação com instalação/homologação. Antes de NO-GO, identificar causa, fonte/revisão consultada, tentativa autorizada, alternativa GOV-BLK-002 e razão objetiva de não resolver. Sem isso, classificar como **DESVIO DE PROCEDIMENTO** e corrigir só a etapa afetada. Bloqueios reais de segurança, permissão e autorização permanecem.

**Fiscalização:** Governança/Tech Lead exigem evidência em tarefa real e anotação na Issue existente; publicação desta instrução não comprova que chats externos a carregaram.

## P0 — Nomenclatura obrigatória da loja

Em todo `config.yaml` de add-on, `name` deve começar exatamente com `Fábrica de Ideias - `. Se `panel_title` existir, deve usar o mesmo prefixo. Conferir manifesto-fonte e pacote exportado antes de qualquer publicação. `Fábrica de Softwares` e outras variações são inválidas. Preservar slug, diretório e identificadores técnicos. Falha de nomenclatura reprova a validação; corrija a fonte e os exemplos relacionados, não apenas a cópia distribuída.

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
