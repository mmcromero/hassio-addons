# P0 — Bootstrap universal GOV-ACT-001

# AGENTS.md — Instruções universais do catálogo Home Assistant

> **HA-MCP — ACESSO OPERACIONAL DE LEITURA E ESCRITA (atualizado em 25/11/2026):** o proprietário confirmou que habilitou escrita no HA-MCP para permitir diagnóstico, correção, publicação/atualização, instalação e acompanhamento operacional de add-ons dentro do escopo de cada missão autorizada. Consultar o [manual operacional HA-MCP](docs/HA-MCP-ACESSO-SOMENTE-LEITURA.md) antes de atuar. A autorização cobre somente o projeto/add-on/ambiente explicitamente abrangidos pela missão; não autoriza alterações em outros serviços, reinício do Core/host, exclusão/restauração de dados, mudanças de rede ou rotação de credenciais sem autorização específica. Verificar as ferramentas de escrita realmente disponíveis na sessão e os limites efetivos do servidor; a configuração e os testes de somente leitura de 22/11 são históricos, não o estado vigente. O túnel n8n permanece uma entrada independente. Recuperação após reinício do Core/host ainda pendente; disponibilidade em outros chats deve ser verificada.

> **AMBIENTE COMPARTILHADO — FONTE CENTRAL (19/11/2026):** antes de perguntar sobre Raspberry Pi, Home Assistant, apps instalados, repositórios da loja, ARM64 ou homologação, consulte o [inventário operacional central](docs/HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md). Não copie a lista de apps para outros projetos; confirme no Supervisor apenas dados voláteis ou decisões críticas. Essa referência não autoriza remover, reiniciar, atualizar ou instalar apps.

## P0 — Procedimento único para qualquer publicação no Home Assistant (19/11/2026)

Ao criar, fechar, testar, empacotar ou publicar qualquer add-on, consulte antes a rotina canônica em [CONTRIBUTING.md](CONTRIBUTING.md) e o manual específico do add-on. Não invente uma esteira alternativa.

## P0 — Contrato universal de Ingress (25/11/2026)

- Com `ingress: true`, a página inicial na raiz `/` é o padrão: **omita `ingress_entry`** do `config.yaml`.
- Não declarar `ingress_entry: /` para a raiz. O Supervisor concatena o valor declarado ao URL-base `/api/hassio_ingress/<token>/`, produzindo `//` no final.
- Só declarar `ingress_entry` para uma subrota real, usando o caminho da subrota.
- Após instalar/atualizar, conferir `ingress_url` no Supervisor e testar a abertura pelo botão do HA, incluindo HTML, CSS, JS, API e navegação. `state: started` não comprova Ingress funcional.
- Referência técnica e evidência comparativa: [CONTRIBUTING.md — Contrato de URL do Ingress](CONTRIBUTING.md#p0--contrato-de-url-do-home-assistant-ingress).

## Aplicação obrigatória

- Toda tarefa recebida sobre pacote/add-on deste catálogo começa pela leitura do `CONTRIBUTING.md` vigente na main e do manual do add-on.
- Valide versão, SHA/HEAD, arquivos, arquitetura declarada, segredos e integridade conforme o diff e o risco. Não impor gates externos genéricos.
- Publique apenas a pasta do add-on autorizado na `main` do catálogo, mantendo os demais arquivos e add-ons intactos. Fonte privada e procedimentos próprios do produto devem ser respeitados.
- Registre o commit público e o resultado de verificação na Issue existente. Publicação, instalação, execução e homologação são estados distintos.
- Se houver instrução antiga contraditória, corrija-a no documento de origem quando autorizado; não invente novos fluxos. Normas superiores de segurança e autorizações prevalecem.

## UX-STD-001 — revisão e criação de interfaces

Referência documental registrada a pedido do proprietário em 22/11/2026: [UX-STD-001 v0.1](docs/ux/UX-STD-001_v0.1.md). Leia essa referência antes de planejar, revisar ou alterar telas neste projeto. A versão 0.1 preserva a pesquisa e a proposta original; seu registro não comprova aplicação ou homologação das telas existentes.

Planeje primeiro para celular. Defina a tarefa principal, agrupe o conteúdo por uso e mostre detalhes sob demanda. Use abas para poucas seções relacionadas e independentes; use telas próprias para tarefas extensas. Preserve dados, filtros e posição ao navegar. Evite empilhar funções independentes e evite cortar conteúdo para reduzir a altura. Apresente o mapa das seções e as evidências dos critérios de aceite aplicáveis.

Aplique ao trabalho com interfaces autorizado na demanda. Em firmware, bibliotecas, infraestrutura ou tarefas sem interface, registre os itens sem aplicação; não crie telas por consequência. Nos repositórios de distribuição, faça a evolução na fonte canônica do produto e siga a esteira vigente. Preserve identidade visual, regras de negócio, segurança e autorizações existentes. Esta referência não autoriza refatoração geral, publicação de pacote ou alteração de serviços.
