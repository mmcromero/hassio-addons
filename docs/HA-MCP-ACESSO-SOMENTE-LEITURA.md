# HA-MCP — acesso operacional somente leitura pelo ChatGPT

**Registro:** 22/11/2026 · **Responsável:** Infraestrutura / Governança  
**Estado:** HA-MCP e túnel n8n migrado para o Raspberry Pi; consultas pelos dois túneis homologadas após interromper o processo do Windows. Recuperação após reinício do Core/host ainda pendente.  
**Escopo:** referência central para todas as equipes dos projetos que compartilham o Home Assistant. Esta página pública não é um perfil de conexão nem contém credenciais.

## 1. Decisão e arquitetura

ChatGPT (plugin pessoal **Home Assistant — Somente leitura**) → OpenAI Secure MCP Tunnel → integração personalizada OpenAI Tunnel for HA-MCP executada no Home Assistant → app Home Assistant MCP Server → Core e Supervisor na rede doméstica.

- Raspberry Pi 4, ARM64, Home Assistant OS. Core 2026.10.4 confirmado pela consulta; Supervisor 2026.11.0 e OS 18.4 informados pelo proprietário durante a instalação.
- Forja 01 permanece na rede Guest isolada, sem rota nova para a rede doméstica. Não instalar o túnel no Forja nem enfraquecer esse isolamento.
- Há duas entradas independentes da integração `hass_codex_tunnel_mcp`: uma para o HA-MCP e outra para o n8n. Cada entrada usa seu próprio Tunnel ID, endpoint e credenciais; o túnel original do n8n foi preservado, sem criar outro ID na OpenAI. Ambos executam no Raspberry Pi.
- Em 22/11/2026, o processo do túnel no CMD do Windows foi interrompido. Depois disso, consultas reais ao n8n continuaram funcionando e o contador MCP da segunda entrada registrou 5 requisições aceitas/concluídas, HTTP 200, sem erros, retries ou falhas de entrega. O CMD não é mais necessário para a operação normal testada.
- O cliente da segunda entrada atualizou automaticamente de v0.0.19 para v0.0.21. A atualização automática está habilitada. Isso não substitui o teste de recuperação após reinício do Home Assistant/host.
- Não criar redirecionamentos de portas, regras de firewall permissivas ou novas rotas públicas para o MCP. Nenhuma mudança desse tipo foi solicitada nesta instalação.
- O antigo teste n8n de consulta ao Supervisor falhou (execução 2476, HTTP 401 na rota HTTP legada). A consulta ao Core por n8n foi comprovada separadamente (2615, success). Não repetir esse diagnóstico como requisito para usar o novo plugin.

## 2. Instalação reproduzível

Procedimento realizado pelo proprietário, com orientação assistida. Para reinstalação, confirmar documentação upstream e versão exata antes de alterar o ambiente.

1. Na loja de apps do HA, adicionar o repositório https://github.com/homeassistant-ai/ha-mcp e instalar a versão estável do Home Assistant MCP Server; não escolher DEV. Configurar o modo somente leitura e iniciar o app.
2. No HACS já instalado, adicionar https://github.com/norpol/hass-codex-tunnel-mcp como repositório personalizado, categoria Integração. Instalar OpenAI Tunnel for HA-MCP e reiniciar o Core quando solicitado. Essa foi a via usada no Core 2026.10.4; não houve necessidade de atualizar Core/OS para a instalação.
3. No [gerenciador de túneis OpenAI](https://platform.openai.com/settings/organization/tunnels), criar um túnel dedicado para HA-MCP e manter o Tunnel ID original do n8n em sua própria entrada. Não reutilizar o ID do HA-MCP para n8n nem gerar novo ID para substituir o túnel n8n existente. Cada entrada deve usar chave de execução restrita às permissões Tunnels Read e Tunnels Use, sem Tunnels Manage ou permissões de API alheias. Verificar a política de expiração e rotação aplicável.
4. Em Configurações → Dispositivos e serviços → Adicionar integração → OpenAI Tunnel for HA-MCP, informar o Tunnel ID real, a chave de execução e a URL privada completa exibida pelo app HA-MCP. Deixar Home Assistant access token vazio para esse modo de autenticação por URL privada, manter os campos control-plane no padrão. A configuração orientada manteve a atualização automática do tunnel-client habilitada; o valor efetivo não foi relido. Não substituir pelo servidor MCP nativo /api/mcp: ele não é o app HA-MCP configurado nesta entrega.
5. Aguardar a integração indicar disponibilidade. No catálogo de plugins do ChatGPT, usar Adicionar → servidor MCP personalizado → conexão por Tunnel, informar o mesmo identificador e nome Home Assistant — Somente leitura. A opção No Auth no conector não substitui autenticação: o encaminhamento usa o endpoint privado configurado no cliente do túnel. Validar a identidade e o escopo do plugin na conta autorizada.
6. Executar somente os testes de leitura da seção 4. Nunca desativar proteções para obter PASS.

Não registrar valores reais de chave API, token HA, URL privada, identificadores de túnel/organização/workspace, cabeçalhos de autenticação ou logs brutos no Git, Issues, PRs ou conversas de equipe. A URL privada do app deve ser tratada como segredo. Armazenar credenciais somente nos mecanismos protegidos das respectivas plataformas; revogar/rotacionar se expostas. Não distribuir credenciais entre chats.

### 2.1. Segunda entrada: túnel n8n no mesmo Raspberry Pi

A integração aceita múltiplas entradas porque o código usa o Tunnel ID como identificador único da config entry e bloqueia somente a duplicação do mesmo ID. Cada entrada recebe entry_id, diretório de execução e processo tunnel-client próprios. O desenho correto é uma instalação da integração com duas entradas independentes.

**Verificação de suporte a múltiplas entradas no código upstream:** revisão consultada `a56e5a5` de `norpol/hass-codex-tunnel-mcp`. O fluxo de configuração usa `async_set_unique_id(tunnel_id)` e bloqueia apenas a duplicação daquele ID ([config_flow.py, linhas 71–86](https://github.com/norpol/hass-codex-tunnel-mcp/blob/a56e5a5/custom_components/hass_codex_tunnel_mcp/config_flow.py#L71-L86)). O runtime é indexado por `entry.entry_id` e o diretório é separado por esse ID ([__init__.py, linhas 31–58](https://github.com/norpol/hass-codex-tunnel-mcp/blob/a56e5a5/custom_components/hass_codex_tunnel_mcp/__init__.py#L31-L58)). Assim, IDs de túnel diferentes podem coexistir na mesma instalação; não é necessário duplicar o componente.


| Entrada | Destino | Autenticação | Conector ChatGPT |
|---|---|---|---|
| HA-MCP | URL privada completa do app Home Assistant MCP Server; não usar /api/mcp nesta instalação | Bearer token vazio, conforme homologado | Home Assistant — Somente leitura |
| n8n | endpoint MCP local do add-on, porta 5678, caminho /mcp-server/http | Bearer token aceito pelo MCP do n8n | n8n — Home Assistant V2 existente |

**Configuração n8n já realizada:** adicionar uma segunda entrada da mesma integração; preservar o Tunnel ID original do n8n; usar Runtime API key com Tunnels Read e Tunnels Use; apontar para o host local do add-on na porta 5678 e caminho /mcp-server/http; preencher o campo Home Assistant access token com o Bearer token aceito pelo servidor MCP do n8n; manter control-plane base URL/path vazios e atualização automática ativada. O hostname e as credenciais reais são privados e não entram no Git.

**Configuração do conector ChatGPT n8n:** preservar o conector existente **n8n — Home Assistant V2**, tipo de conexão **Tunnel**, associado ao Tunnel ID original do n8n, com autenticação do conector em **Sem autenticação (No Auth)**. Isso não deixa o endpoint MCP aberto: o tunnel-client encaminha ao n8n o cabeçalho Bearer armazenado na entrada da integração. Não criar novo conector nem novo túnel para resolver falhas de autenticação.


O campo Home Assistant access token corresponde internamente a ha_mcp_bearer_token e é encaminhado como Authorization: Bearer ao MCP configurado. Na entrada n8n, não é a Runtime API key OpenAI nem deve ser confundido com token HA. O valor está mascarado e foi aceito nos testes; preservar, não tentar recuperar da máscara e não rotacionar por tentativa.

Com Bearer token e tunnel-client v0.0.21+, a integração define MCP_OAUTH_DISCOVERY=disabled. A Runtime API key vai por variável de ambiente CONTROL_PLANE_API_KEY; o Bearer token vai por HA_MCP_AUTH_HEADER. A revisão mascara API key, token e URL MCP nos logs. Não criar port forwarding, hostname público, regra de firewall ampla ou rota do Forja para a rede doméstica.

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

### 4.1. Migração e homologação do túnel n8n — 22/11/2026

A segunda entrada `OpenAI Tunnel for HA-MCP` foi adicionada à mesma integração HACS, sem remover ou editar a entrada HA-MCP. O Tunnel ID original do n8n foi reutilizado; o plugin/conector existente, workflows e credenciais não foram recriados nem rotacionados. Endpoint MCP local configurado para o app n8n no Raspberry Pi; os valores completos de URL e credenciais foram omitidos por segurança.

O processo do túnel no CMD do Windows foi interrompido antes dos testes abaixo. Depois da interrupção, chamadas de leitura pelo conector n8n tiveram sucesso: busca de workflows, busca de execuções e leitura de detalhes de workflow. O sensor da segunda instância registrou 5 requisições MCP aceitas e concluídas, HTTP 200, 0 retries, 0 falhas terminais, 0 falhas de entrega e 0 erros MCP. O estado observado foi `ready`, processo `healthy`, Control Plane `ok` sem falhas consecutivas e cliente `v0.0.21` com atualização automática habilitada.

A primeira instância (HA-MCP) permaneceu `ready`/`healthy`, com 0 erros MCP, após a criação e o teste da segunda entrada. Não houve alteração de workflows, execução de workflow, mudança de credenciais ou intervenção no Forja.

**Aviso observado:** o log do cliente registrou avisos de auto-registro de endpoints auxiliares OAuth/Harpoon porque o host local anunciado usa HTTP e esse registro auxiliar exige HTTPS. Apesar desses avisos, o canal MCP principal foi aceito e respondeu HTTP 200 nos testes. Não declarar o fluxo auxiliar OAuth homologado; se ele vier a ser necessário, avaliar HTTPS e testar separadamente.

| Teste n8n | Evidência | Resultado |
|---|---|---|
| N01 — segunda entrada da integração | duas entradas `hass_codex_tunnel_mcp` carregadas no HA | PASS |
| N02 — processo local após parar CMD | processo `healthy`, túnel `ready`, Control Plane `ok` | PASS |
| N03 — chamada real do conector após parar CMD | busca de workflows, execuções e detalhes retornou sucesso | PASS |
| N04 — tráfego confirmado no túnel Raspberry | 5 aceitas/concluídas, HTTP 200, sem retries, falhas ou erros | PASS |
| N05 — túnel HA-MCP preservado | primeira entrada `ready`/`healthy`, 0 erros MCP | PASS |
| N06 — independência do Windows | CMD interrompido antes das chamadas N03/N04 | PASS para operação atual |
| N07 — recuperação após reinício do HA/host | não foi realizado reinício controlado | PENDENTE |

Estado started não comprova saúde funcional ou homologação individual dos produtos. Inventário é fotografia datada, não deve ser copiado para outros projetos. Versões atuais devem ser consultadas novamente por necessidade.

## 5. Disponibilidade para todas as equipes

Governança, Gerência de Projeto, Tech Lead, Desenvolvimento, Homologação, Segurança/Privacidade, Infraestrutura e UX/Mídias podem usar a capacidade de **leitura pertinente à tarefa e à função**, desde que o plugin esteja disponível no contexto e a conta tenha acesso autorizado. A publicação desta referência não instala o plugin em outras contas, não concede acesso a terceiros e não comprova que chats existentes receberam a instrução.

Antes de pedir ao proprietário versões, estados, logs ou inventário, consultar este manual, confirmar a disponibilidade real do plugin e tentar a consulta direcionada. Usar o guia de boas práticas do servidor quando aplicável. Exemplos: overview com campos mínimos; ha_get_app para inventário/estado; ha_get_logs com slug e limite reduzido; ha_get_integration para diagnóstico específico sem divulgar opções privadas. Não consultar câmeras, presença, dados pessoais ou automações residenciais sem necessidade autorizada. Não contornar restrições via n8n, shell, serviço, proxy de API ou outro conector.

Ficam fora do escopo: ligar/desligar dispositivos, chamar serviços de escrita, reiniciar, instalar/remover/atualizar apps, alterar configuração, backup/restore com efeito de escrita, mudança de rede, exposição de credenciais e qualquer operação no Forja. Mesmo ferramentas de nome manage que ofereçam leitura só podem ser usadas em modo explicitamente de leitura, quando necessário. Não tentar a operação para verificar se será bloqueada. Seguir GOV-STD-001 e GOV-BLK-002 para impedimentos reais: informar erro, operação afetada e alternativa segura; não pedir ao proprietário dados já disponíveis.

**Recibo sugerido por chat/equipe:** data; plugin disponível sim/não; consulta mínima realizada e resultado; modo somente leitura confirmado; responsável. Não presumir adoção por outros chats. Governança acompanha distribuição e recebimento conforme as normas vigentes.

## 6. Manutenção, inicialização e recuperação

Responsável: Infraestrutura, com autorização do proprietário para intervenções. Não reconstruir os túneis, reinstalar a integração, criar novos Tunnel IDs ou reabrir CMD no Windows como procedimento normal.

### 6.1. Inicialização normal

- O Home Assistant carrega cada config entry durante o setup do Core. async_setup_entry valida o endpoint MCP, prepara diretório próprio, obtém o binário e inicia um processo tunnel-client independente por entrada.
- O add-on HA-MCP está em boot automático e watchdog ativo. O add-on n8n estava started, boot auto e watchdog ativo na captura de 22/11/2026.
- Se o endpoint MCP responder 404 ou estiver inacessível durante o startup, a integração sinaliza ConfigEntryNotReady e o Home Assistant repete o setup automaticamente. Um 404 temporário não é sucesso nem inicia processo túnel prematuramente.
- O n8n publica a porta interna 80/tcp na porta 5678 do host; o MCP HTTP usa /mcp-server/http. Obter o hostname privado atual pelo Supervisor, sem assumir que um alias local sempre resolve.
- A recuperação após reinício do Core/host é esperada pelo ciclo de setup das config entries, mas ainda não foi comprovada por reinício controlado nesta instalação. Não reiniciar apenas para produzir evidência.

### 6.2. Processo túnel encerrado com Core ativo

O supervisor do processo atualiza o estado para exited quando o subprocesso termina, mas não implementa loop permanente de reinício automático após saída inesperada.

1. Verificar Tunnel process state, Tunnel ready, Tunnel control plane e Tunnel MCP errors da entrada afetada.
2. Consultar logs sanitizados e verificar se o endpoint MCP local está disponível.
3. Corrigir a causa demonstrada antes de reiniciar.
4. Usar Restart tunnel ou o serviço hass_codex_tunnel_mcp.restart_tunnel com entry_id explícito. Sem entry_id, o serviço pode atingir todas as entradas; não omitir o alvo quando a intenção for reiniciar somente uma.
5. Executar restart pela UI/API local do Home Assistant, nunca pelo túnel que está sendo reiniciado.
6. Confirmar Ready + Healthy + Control Plane OK + chamada MCP real com contador incrementado e sem erros.

### 6.3. Falha de autenticação/Control Plane

- Ready isolado não prova que o Control Plane aceitou a Runtime API key. Verificar o sensor Control Plane e uma chamada MCP real.
- HTTP 401 no Control Plane: verificar validade e escopos Tunnels Read + Tunnels Use. Não gerar chave nem rotacionar por tentativa.
- HTTP 401/403 no MCP: verificar o Bearer token daquela entrada. A máscara da UI não indica erro e não revela o valor original. Não substituir token sem evidência.
- Não copiar credenciais entre entradas: HA-MCP e n8n têm destinos/autenticações distintos.
- Se o Bearer token MCP do n8n tiver sido perdido e não existir cópia segura, a UI não revela o valor anterior. Somente após autorização e avaliação dos outros clientes MCP, gerar outro em **n8n → Settings → Instance-level MCP → Connect → API key**, atualizar o campo Bearer somente na entrada n8n e validar uma chamada real. A rotação invalida o token anterior e pode afetar outros clientes MCP que o utilizem; não é a API REST do n8n.
- Se a Runtime API key OpenAI estiver ausente/invalidada, confirmar primeiro erro 401 do Control Plane. Criar uma nova chave de runtime na organização correta, com **Tunnels Read + Tunnels Use**, guardar o segredo no mecanismo seguro e atualizar a entrada afetada. Validar Control Plane e chamada MCP antes de revogar uma chave antiga. Não recriar o Tunnel ID.
- Se o Tunnel ID não estiver visível no contexto de um chat, consultar a página OpenAI Platform Tunnels na organização correta e localizar o túnel existente pelo nome/descrição. Não criar outro túnel como atalho.

### 6.4. Atualização e rollback

- Código da integração e executável tunnel-client têm ciclos separados. Atualizar código HACS/Marketplace pode exigir reload/restart do Core conforme a UI; o binário é gerenciado pela integração.
- Atualização automática do executável está habilitada nas duas entradas. O verificador retoma a agenda após startup/reload e mantém espera mínima de 8 dias para releases novas.
- O binário candidato é validado por SHA-256 e só é ativado após readiness. Se falhar, a integração retorna ao último binário conhecido como bom e registra Repair.
- Serviços disponíveis: restart_tunnel, redownload_tunnel_client, check_tunnel_client_update, update_tunnel_client e rollback_tunnel_client. Consulta de releases não instala; redownload é excepcional; update/rollback só com causa e alvo identificados.
- Na homologação de 22/11, o cliente da entrada n8n atualizou automaticamente de v0.0.19 para v0.0.21 e permaneceu Ready/Healthy.

### 6.5. Checklist de recuperação

1. Verificar se a entrada já existe; não duplicar Tunnel ID.
2. Verificar app MCP de destino e endpoint local.
3. Consultar Ready/Healthy e Control Plane.
4. Ler logs sanitizados com limite pequeno.
5. Se processo exited, reiniciar somente a entrada afetada pela UI/API local.
6. Fazer chamada MCP real de leitura e confirmar incremento, HTTP 200, zero erros e zero falhas.
7. Se chave/token estiver ausente ou inválido, parar antes de rotacionar e solicitar apenas a autorização/credencial indispensável.
8. Registrar resultado. Não reinstalar, recriar túnel, mexer no Forja nem pedir ao proprietário dados que Supervisor/connector já fornecem.

**Estado de homologação:** o túnel n8n foi testado com CMD do Windows interrompido e registrou 5 requisições aceitas/concluídas (HTTP 200), sem retries, erros ou falhas. O CMD não é necessário para a operação atual. O teste de reinício do Core/host permanece pendente.

## Referências

- [Inventário central](HOME-ASSISTANT-RASPBERRY-INVENTARIO-CENTRAL.md) e [AGENTS.md](../AGENTS.md).
- [HA-MCP upstream](https://github.com/homeassistant-ai/ha-mcp).
- [Integração HACS upstream](https://github.com/norpol/hass-codex-tunnel-mcp).
- [OpenAI — Secure MCP Tunnels](https://developers.openai.com/api/docs/guides/secure-mcp-tunnels).
- [GOV-STD-001](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_STD_001.md) e [GOV-BLK-002](https://github.com/mmcromero/fabricacao_e_orcamentos/blob/main/docs/operacao/GOV_BLK_002.md).
