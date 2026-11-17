# CENTRAL-WA-RELEASE-001 — Portões para liberar atendimento a todos

**Data:** 17/11/2026 (BRT). **Estado:** bloqueios de lançamento documentados; nenhuma mudança operacional.  
**Origem:** revisão conjunta do proprietário e código versionado da Central 12Labs/Umdoislab.

## Estado e finalidade

- O proprietário confirmou que o workflow do n8n está **publicado/ativo**, mas o **atendimento automático está em fase de testes** e restrito ao número pessoal do proprietário e ao de sua esposa.
- O título `(NÃO PUBLICADO)` no JSON versionado `umdoislab-central/n8n/atendimento-v1.7-handoff-verificado.json` é histórico e **não equivale ao estado operacional da instância n8n**.
- **Não abrir modo `all` para clientes** apenas porque o workflow já responde no teste. O atendimento deve continuar funcionando durante o trabalho de segurança.

## Gate P0 — autenticação da origem do Webhook Evolution→n8n

**Evidência:** captura real do nó `WhatsApp recebido — Evolution`, com `POST`, path `umdoislab-v15`, `Authentication: None`. O JSON no Git usa Webhook sem autenticação. Isso **não prova que o endpoint esteja exposto**, nem que não haja proteção em rede, proxy ou no emissor; essas camadas não foram inspecionadas.

**Risco:** se um terceiro puder alcançar esse endpoint e enviar payload forjado, os campos `remoteJid`, `fromMe`, `instance` e `messageId` não constituem identidade autenticada. Isso é especialmente sensível para comandos de orquestração vindos do WhatsApp.

**Requisitos antes de mudar a política para `all` ou publicar comandos executivos:**

1. Verificar onde a URL é acessível, se existe controle de acesso de rede/proxy, e o mecanismo de autenticação da entrega Evolution→n8n. Distinguir fato comprovado de hipótese.
2. Selecionar autenticação compatível com a **versão realmente instalada** da Evolution e do n8n. Se for Header Auth, conferir que a Evolution emite o cabeçalho, que o n8n rejeita credenciais ausentes/incorretas e que segredos permanecem fora do Git.
3. Exigir HTTPS nos trechos expostos em rede não confiável; não confundir HTTPS com autenticação do emissor.
4. Validar instância, evento, identidade do remetente e formatos `@lid`, grupo/status, `fromMe`, deduplicação por `messageId`, limites e tratamento de falhas. **Não inventar números a partir de JIDs**.
5. Confirmar que a política da Central e as travas de atendimento humano continuam valendo, que testes negativos falham sem enviar, e que nenhuma resposta é duplicada.
6. Registrar evidência datada de teste real e parecer GO de Segurança/Tech Lead antes da autorização explícita do proprietário para `all`.

**Gate pendente:** nenhuma configuração de autenticação do nó/proxy foi verificada como suficiente e nenhum teste de rejeição foi executado nesta revisão. Não alterar o webhook de produção só para testar.

## Gate P0 — separar atendimento comercial e comandos executivos

- A conta pessoal do proprietário é **remetente externo** em relação à conta comercial conectada à Evolution; espera-se `fromMe=false`, sujeito à confirmação no evento real.
- O proprietário **pode permanecer na lista de testes** enquanto novos comandos são roteados antes do Gemini, com autorização separada e específica. A esposa permanece exclusivamente no atendimento comercial.
- Comandos `status` de leitura devem ser encaminhados apenas após autenticação de origem e verificação de identidade; `testar`/`liberar` não podem depender apenas da comparação do número ou contornar autorização canônica do worker.
- **Não retirar o número do proprietário por enquanto**: o fluxo de `status` atualmente preparado usa a decisão `action=auto` da Central. Removê-lo da lista pode bloquear também o comando.
- O backend possui exceção de retrocompatibilidade `auto_test_sender` em `config.yaml` e `contact_policy()`: com modo `tests`, remover o contato da lista visual **não garante** que perca autorização, se esse campo ainda apontar para o mesmo número.
- A lista de exclusões (`excluded`) prevalece na política, mas **bloquearia também a rota que usa autorização da Central**. Não usar como solução provisória para separar comandos.

## Gate P1 — rollout comercial

- Confirmar estado/backup e possibilidade de recuperação da Central, Evolution e workflows n8n; registrar versão e URLs internas sem segredos.
- Testar com dois contatos autorizados e um não autorizado, depois com piloto supervisionado antes de permitir `all`. Validar tratamento de mídia, handoff e falha de entrega.
- Conferir o controle histórico `baseline_ready` se optar pelo modo `new` e não presumir que consultas à Evolution cobrem todo contato.
- Separar autorização comercial de autorização executiva; uma pessoa autorizada a conversar com o bot **não** recebe acesso ao worker/HA/GitHub.
- Obter autorização de publicação/expansão do proprietário após evidências. Não tratar aceite HTTP da Evolution como ACK de entrega WhatsApp.

## Fontes e rastreabilidade

- Código: `umdoislab-central/server.py` (`contact_policy`, `/api/policy/remove`, `send_automated`).
- Configuração: `umdoislab-central/config.yaml` (`auto_test_sender`).
- Interface: `umdoislab-central/static/index.html` (lista de testes, exclusões, modo).
- Workflow comercial: `umdoislab-central/n8n/atendimento-v1.7-handoff-verificado.json`.
- Integração executiva em preparação: `mmcromero/orquestrador-projetos-base`, branch `release/v0.1.0-rc.1`, `n8n/INTEGRACAO-WHATSAPP-COMANDOS-AVISAQUI.md`.

**Esta entrega é exclusivamente documental.** Não foi executada mudança de política, exclusão de contatos, atualização de add-on, mudança de webhook, deploy ou teste externo.
