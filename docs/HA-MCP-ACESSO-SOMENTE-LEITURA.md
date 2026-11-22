# HA-MCP — acesso operacional somente leitura pelo ChatGPT

**Registro:** 22/11/2026 · **Responsável:** Infraestrutura / Governança  
**Estado:** conexão e consultas homologadas; recuperação automática do túnel após reinício pendente.  
**Escopo:** referência central para todas as equipes dos projetos que compartilham o Home Assistant. Esta página pública não é um perfil de conexão nem contém credenciais.

## 1. Decisão e arquitetura

ChatGPT (plugin pessoal **Home Assistant — Somente leitura**) → OpenAI Secure MCP Tunnel → integração personalizada OpenAI Tunnel for HA-MCP executada no Home Assistant → app Home Assistant MCP Server → Core e Supervisor na rede doméstica.

- Raspberry Pi 4, ARM64, Home Assistant OS. Core 2026.10.4 confirmado pela consulta; Supervisor 2026.11.0 e OS 18.4 informados pelo proprietário durante a instalação.
- Forja 01 permanece na rede Guest isolada, sem rota nova para a rede doméstica. Não instalar o túnel no Forja nem enfraquecer esse isolamento.
- O túnel HA-MCP é separado do túnel n8n existente. Não depende do n8n nem de um processo no Windows para atender às consultas HA-MCP. A migração do túnel n8n não integra esta entrega.
- Não criar redirecionamentos de portas, regras de firewall permissivas ou novas rotas públicas para o MCP. Nenhuma mudança desse tipo foi solicitada nesta instalação.
- O antigo teste n8n de consulta ao Supervisor falhou (execução 2476, HTTP 401 na rota HTTP legada). A consulta ao Core por n8n foi comprovada separadamente (2615, success). Não repetir esse diagnóstico como requisito para usar o novo plugin.

## 2. Instalação reproduzível

Procedimento realizado pelo proprietário, com orientação assistida. Para reinstalação, confirmar documentação upstream e versão exata antes de alterar o ambiente.

1. Na loja de apps do HA, adicionar o repositório https://github.com/homeassistant-ai/ha-mcp e instalar a versão estável do Home Assistant MCP Server; não escolher DEV. Configurar o modo somente leitura e iniciar o app.
2. No HACS já instalado, adicionar https://github.com/norpol/hass-codex-tunnel-mcp como repositório personalizado, categoria Integração. Instalar OpenAI Tunnel for HA-MCP e reiniciar o Core quando solicitado. Essa foi a via usada no Core 2026.10.4; não houve necessidade de atualizar Core/OS para a instalação.
3. No [gerenciador de túneis OpenAI](https://platform.openai.com/settings/organization/tunnels), criar túnel dedicado, associado à organização e ao workspace autorizado. Não reutilizar a identidade do túnel n8n. Criar chave de execução restrita às permissões Tunnels Read e Tunnels Use, sem Tunnels Manage ou permissões de API alheias. Verificar a política de expiração e rotação aplicável.
4. Em Configurações → Dispositivos e serviços → Adicionar integração → OpenAI Tunnel for HA-MCP, informar o Tunnel ID real, a chave de execução e a URL privada completa exibida pelo app HA-MCP. Deixar Home Assistant access token vazio para esse modo de autenticação por URL privada, manter os campos control-plane no padrão. A configuração orientada manteve a atualização automática do tunnel-client habilitada; o valor efetivo não foi relido. Não substituir pelo servidor MCP nativo /api/mcp: ele não é o app HA-MCP configurado nesta entrega.
5. Aguardar a integração indicar disponibilidade. No catálogo de plugins do ChatGPT, usar Adicionar → servidor MCP personalizado → conexão por Tunnel, informar o mesmo identificador e nome Home Assistant — Somente leitura. A opção No Auth no conector não substitui autenticação: o encaminhamento usa o endpoint privado configurado no cliente do túnel. Validar a identidade e o escopo do plugin na conta autorizada.
6. Executar somente os testes de leitura da seção 4. Nunca desativar proteções para obter PASS.

Não registrar valores reais de chave API, token HA, URL privada, identificadores de túnel/organização/workspace, cabeçalhos de autenticação ou logs brutos no Git, Issues, PRs ou conversas de equipe. A URL privada do app deve ser tratada como segredo. Armazenar credenciais somente nos mecanismos protegidos das respectivas plataformas; revogar/rotacionar se expostas. Não distribuir credenciais entre chats.

## 3. Configuração efetiva verificada via Supervisor em 22/11/2026

App HA-MCP 9.2.0, estado started, boot auto, watchdog true. Opções selecionadas por segurança na resposta da ferramenta (nenhum segredo coletado neste registro):

| Opção | Valor |
|---|---|
| read_only_mode | true |
| redact_secrets | true |
| backup_read_only | true |
| enable_auto_backup | false |
| ha_tool_concurrency | 2 |
| enable_snapshot_delete | false |
| enable_tool_security_policies | false |
| enable_security_policy_tool | false |
| enable_snapshot_actions | true |
| verify_ssl | true |

A opção enable_snapshot_actions permanece true, mas não concede escrita: backup_read_only e read_only_mode permanecem ativos. Não disparar ações de snapshot para testar a proteção. A filtragem de segredos não é garantia de anonimização de todo log ou campo aplicativo; minimizar a leitura, revisar e sanitizar qualquer saída antes de transferir. Não registrar opções livres com valores potencialmente sensíveis. Boot/watchdog acima são do app HA-MCP, não uma comprovação de recuperação do cliente do túnel.

## 4. Homologação e evidências

Consultas reais pelo plugin, em 22/11/2026; nenhum comando de escrita executado durante os testes.

| Teste | Evidência sanitizada | Resultado |
|---|---|---|
| H01 — conexão direta | ha_get_overview: success=true, Core RUNNING, cliente openai-mcp | PASS |
| H02 — Supervisor / inventário | ha_get_app(source=installed): success=true; 31 instalados, 28 em execução, 3 parados, 2 atualizações disponíveis | PASS |
| H03 — versão e estado | inventário retornou n8n, Instagram, WhatsApp, Avisaqui, Artesão Digital contingência, Factory Runner, Kanban, Evolution API e HA-MCP | PASS |
| H04 — logs do Instagram | ha_get_logs(source=supervisor, slug do app): success=true | PASS |
| H05 — logs do WhatsApp | mesma consulta, slug do app correspondente: success=true | PASS |
| H06 — logs do Supervisor | ha_get_logs(source=system_service, slug=supervisor): success=true | PASS |
| H07 — modo somente leitura | ha_get_overview: read_only_mode=true e mensagem explícita do servidor informando bloqueio de escrita; ha_get_app confirmou a opção efetiva | PASS para configuração e declaração do servidor |
| H08 — negação de escrita ponta a ponta | nenhuma tentativa de escrita; não executar teste destrutivo em ambiente compartilhado. Validação negativa isolada, se necessária, depende de plano específico | NÃO EXECUTADO |
| H09 — recuperação automática | boot/watchdog do app confirmados; não houve reinício controlado do ambiente após concluir a conexão nem prova de reconexão do tunnel-client | PENDENTE |
| H10 — filtragem integral de segredos | redact_secrets=true confirmado; cobertura de todos os campos/logs não demonstrada | PARCIAL |

Estado started não comprova saúde funcional ou homologação individual dos produtos. Inventário é fotografia datada, não deve ser copiado para outros projetos. Versões atuais devem ser consultadas novamente por necessidade.

## 5. Disponibilidade para todas as equipes

Governança, Gerência de Projeto, Tech Lead, Desenvolvimento, Homologação, Segurança/Privacidade, Infraestrutura e UX/Mídias podem usar a capacidade de **leitura pertinente à tarefa e à função**, desde que o plugin esteja disponível no contexto e a conta tenha acesso autorizado. A publicação desta referência não instala o plugin em outras contas, não concede acesso a terceiros e não comprova que chats existentes receberam a instrução.

Antes de pedir ao proprietário versões, estados, logs ou inventário, consultar este manual, confirmar a disponibilidade real do plugin e tentar a consulta direcionada. Usar o guia de boas práticas do servidor quando aplicável. Exemplos: overview com campos mínimos; ha_get_app para inventário/estado; ha_get_logs com slug e limite reduzido; ha_get_integration para diagnóstico específico sem divulgar opções privadas. Não consultar câmeras, presença, dados pessoais ou automações residenciais sem necessidade autorizada. Não contornar restrições via n8n, shell, serviço, proxy de API ou outro conector.

Ficam fora do escopo: ligar/desligar dispositivos, chamar serviços de escrita, reiniciar, instalar/remover/atualizar apps, alterar configuração, backup/restore com efeito de escrita, mudança de rede, exposição de credenciais e qualquer operação no Forja. Mesmo ferramentas de nome manage que ofereçam leitura só podem ser usadas em modo explicitamente de leitura, quando necessário. Não tentar a operação para verificar se será bloqueada. Seguir GOV-STD-001 e GOV-BLK-002 para impedimentos reais: informar erro, operação afetada e alternativa segura; não pedir ao proprietário dados já disponíveis.

**Recibo sugerido por chat/equipe:** data; plugin disponível sim/não; consulta mínima realizada e resultado; modo somente leitura confirmado; responsável. Não presumir adoção por outros chats. Governança acompanha distribuição e recebimento conforme as normas vigentes.

## 6. Manutenção e recuperação

Responsável: Infraestrutura, com autorização do proprietário para intervenções. Se a conexão falhar, verificar estado da integração e do app, logs sanitizados, validade da chave restrita e associação correta do túnel. Não alterar credenciais nem reiniciar serviços alheios por tentativa. Em janela autorizada de manutenção, medir retorno do túnel após reinício do Core/host conforme o evento escolhido; repetir H01, H02 e uma leitura curta de logs sem iniciar manualmente o cliente. Registrar resultado e eventual intervalo de indisponibilidade. Até então, recuperação automática permanece pendente. Sem reinício só para produzir evidência.

## Referências

- [Inventário central](HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md) e [AGENTS.md](../AGENTS.md).
- [HA-MCP upstream](https://github.com/homeassistant-ai/ha-mcp).
- [Integração HACS upstream](https://github.com/norpol/hass-codex-tunnel-mcp).
- [OpenAI — Secure MCP Tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
- [GOV-STD-001](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_STD_001.md) e [GOV-BLK-002](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_BLK_002.md).
