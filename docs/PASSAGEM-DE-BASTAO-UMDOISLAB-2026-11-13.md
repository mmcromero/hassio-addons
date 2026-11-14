# UMDOISLAB — Passagem de bastão: Evolution API, WhatsApp e n8n

> **REGISTRO HISTÓRICO — NÃO USAR COMO ESTADO ATUAL (14/11/2026).** Este documento descreve a fase v1.1 e preserva suas evidências. A referência operacional vigente é [ESTADO-ATUAL-UMDOISLAB.md](ESTADO-ATUAL-UMDOISLAB.md): workflow n8n **v1.6 publicado**, Central HA **0.3.0** em execução e Evolution add-on **0.1.0**. O validador de contatos discutido está **adiado por decisão expressa do proprietário**, e não implementado. A cada pacote ou decisão importante, seguir [PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md](PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md). Os próximos passos e afirmações de ausência de IA abaixo são **históricos**, não instruções de execução atual.


**Data da consolidação:** 13/11/2026 (BRT)  
**Escopo:** documentação operacional e decisões; nenhuma mudança em código, serviços, servidores ou workflows.  
**Fonte de evidências:** capturas e resultados relatados pelo proprietário durante a configuração, comparados aos arquivos do repositório em 13/11/2026.  
**Estado:** v1.1 de classificação funcionando em produção **segundo execução/captura relatada**; não confundir com auditoria direta do ambiente.

## 1. Estado atual e objetivo de continuidade

**Confirmado pelo proprietário:** o workflow **Atendimento Umdoislab v1.1 — Classificação**, no n8n, recebeu evento real do WhatsApp, apresentou **Success**, executou **quatro nós** e classificou corretamente uma pergunta sobre **preço**. A integração WhatsApp → Evolution API → n8n funciona em produção. **Ainda não existe resposta automática**, IA conectada ao atendimento, memória persistente de conversa ou controle real de dispositivos domésticos pelo WhatsApp.

**Próxima meta:** evoluir o atendimento por regras para **respostas prontas/sugeridas, inicialmente sem envio automático**, preservando o JSON efetivo da v1.1; desenvolver atendimento Gemini em workflow separado com dados fictícios; manter automação pessoal isolada.

**Forma de trabalho preferida:** modo `/pair`, sem Codex/Work; entregar JSON completo, passos curtos e botões para confirmações. Para mudanças reversíveis, validar em produção de modo pragmático; para credenciais, respostas automáticas, dados de clientes e ações físicas, aplicar controles proporcionais.

## 2. Infraestrutura, versões e serviços

| Componente | Estado conhecido |
| --- | --- |
| Host | Raspberry Pi 4, 8 GB, ARM64; Home Assistant OS; residência e automações têm prioridade |
| n8n | Versão **2.47.3**, endereço utilizado `http://homeassistant.local:5678` |
| Evolution API | Add-on próprio **0.1.0** de `mmcromero/hassio-addons`, com upstream `evoapicloud/evolution-api:v2.3.7` |
| Evolution Manager | `http://homeassistant.local:8080/manager`, acessível e autenticado |
| PostgreSQL | No add-on; logs relatados com inicialização e 57 migrações Prisma |
| WhatsApp | Uma instância **`umdoislab`**, canal Baileys, conectada via QR |
| Outros | Jellyfin também no Pi; carga CPU/RAM não medida; Google Antigravity com MCP para n8n relatado, não auditado |

Configuração do add-on confirmada em [`evolution-api/config.yaml`](../evolution-api/config.yaml): ARM64, porta 8080 e opções `api_key`, `server_url`, `webhook_url`. A integração em uso foi configurada no **Webhook por instância do Manager**, não na opção global do add-on. Não documentar chave global, token, QR, telefone, nome de clientes, conteúdo pessoal ou segredos.

## 3. Webhook em produção

**Endpoint validado por execução:** `POST http://homeassistant.local:5678/webhook/umdoislab-atendimento-inicial`.

No Manager: **Instances → umdoislab → Events → Webhook**:
- **Enabled: ON**;
- **MESSAGES_UPSERT: ON**;
- **Webhook by Events: OFF**;
- **Webhook Base64: OFF**.

O campo URL no Manager deve apontar para a **Production URL** do Webhook publicado no n8n. Alternar **Test URL** e **Production URL** dentro do n8n apenas muda qual endereço é exibido; não salva nem altera o Webhook da Evolution. O botão de gravação está no **Manager**. O modo teste `/webhook-test/` requer `Listen for test event`; produção usa `/webhook/` com workflow publicado.

**Observação comprovada durante configuração:** se o **Enabled** principal do Webhook estava desligado, o evento `MESSAGES_UPSERT` parecia desativar ao salvar. Ativar **Enabled** e o evento resolveu no teste do usuário; não afirmar que é um bug confirmado da versão upstream.

## 4. Histórico operacional e testes

1. Add-on Evolution API 0.1.0 instalado no Home Assistant; Manager e PostgreSQL iniciaram e Global API Key foi aceita.
2. Instância `umdoislab` criada com Baileys, QR pareado e estado Connected. O Chat interno do Manager não mostrava mensagens recentes, embora eventos chegassem aos logs e ao n8n. **Causa não investigada**, não bloqueia recepção de Webhook.
3. Workflow inicial `TESTE - WhatsApp Umdoislab`: Webhook POST path `whatsapp-teste`. Test URL recebeu mensagem; payload mostrou `event: messages.upsert`, `instance: umdoislab`, `data.key`, `data.message.conversation`; depois Production URL executou com Success.
4. IF na saída do Webhook: `{{ $json.body.data.key.fromMe }}` com operador Boolean `is false`. Testes relataram **True** para mensagem recebida de outra pessoa e **False** para enviada pela própria conta; foi preciso republicar após adicionar o IF.
5. Novo workflow `Umdoislab - Atendimento inicial (rascunho)`: JSON de 3 nós (Webhook → Code de organização → IF), endpoint dedicado `/webhook/umdoislab-atendimento-inicial`. Após troca da URL no Manager, execução em produção mostrou Success.
6. Importação da v1.1 causou **segundo conjunto de nós dentro do mesmo editor**, além de aviso **Conflicting Webhook Path** porque havia Webhooks concorrendo pelo mesmo caminho. Para resolver, o proprietário relatou despublicação de workflows antigos de teste, remoção dos **três nós duplicados** e manutenção dos **quatro nós da versão nova**.
7. **Último teste funcional:** workflow v1.1 publicou, recebeu mensagem real com Success, os quatro nós executaram e pergunta sobre preço foi classificada corretamente. **Esse é o marco de homologação vigente.**

Os detalhes do conteúdo privado das mensagens e identificadores de contatos foram deliberadamente omitidos.

## 5. Desenho funcional v1.1

```text
WhatsApp (instância umdoislab)
  → Evolution API (evento messages.upsert)
  → n8n: Entrada WhatsApp (Webhook POST)
  → Organizar dados da mensagem (Code)
  → É mensagem de cliente? (IF)
       True  → Classificar assunto (regras locais, sem IA)
       False → nenhuma ação
```

O status Success **não comprova** precisão de todas as categorias, idempotência, mídia, grupos, retomada após reinício ou anti-loop. Apenas o teste de classificação de preço foi confirmado. O atendimento ainda **não envia mensagens**.

**Workflows antigos:** `TESTE - WhatsApp Umdoislab` e `Umdoislab - Atendimento inicial (rascunho)` eram técnicos/experimentais. O proprietário recebeu instrução para usar **Unpublish**, não Delete; os status individuais atuais dos dois não foram auditados. Não apagar nada sem nova autorização.

**Erros já vistos e prevenção:** não publicar dois Webhooks com o mesmo path; importar um JSON no editor existente pode **adicionar** nós ao canvas, não substituir; conferir visualmente os nós antes de publicar; após mudar os nós, republicar a versão; o menu Test/Production URL do n8n não é configuração persistida no Manager.

## 6. Artefatos JSON entregues

- `umdoislab_atendimento_inicial_v1.json`: três nós, Webhook próprio.
- `umdoislab_atendimento_v1_1_classificacao.json`: quatro nós, com classificação sem IA.
- `automacao_pessoal_casa_laboratorio_v0_1.json`: **somente simulador** de comandos `/casa`, sem conexão com WhatsApp nem Home Assistant.

Esses arquivos foram entregues como anexos na conversa; **não são pressupostos como versionados aqui**. Antes de alterar a classificação, **exportar o JSON efetivamente publicado da v1.1**: a descrição e os prints não são suficientes para reproduzir todas as expressões com fidelidade. A integração presente no n8n não foi inspecionada diretamente por esta atualização documental.

## 7. Decisões de arquitetura e próximos passos

**Umdoislab / atendimento por regras:** continuar v1.1 como base. Próximo incremento v1.2: respostas prontas/sugeridas para revisão, **sem envio automático inicialmente**. Não inventar preços, estoque, prazos ou regras comerciais. Ainda não foi aprovada política definitiva de mensagens, voz, catálogo ou tom.

**Atendimento com Gemini:** criar workflow **separado e não conectado à entrada real** para testar com dados sintéticos; só rotear mensagens reais após validação e autorização. Uma única entrada da Evolution API e roteamento/sub-workflows no n8n evitam respostas duplicadas. O projeto não tem Gemini API configurada ou homologada. MCP entre Antigravity e n8n, relatado pelo usuário, é mecanismo de desenvolvimento/administração e não fornece sozinho inferência de IA ao fluxo. Desejo futuro de conexão do ChatGPT por MCP não foi implementado.

**Automação pessoal da casa:** manter separada da automação comercial. O simulador reconhece exemplos de comandos, mas **não liga nem desliga dispositivos**. `fromMe: true` não autoriza ação doméstica; são necessárias conversa/identidade permitidas, comando explícito (ex.: `/casa`), permissões por dispositivo e anti-loop.

**Ambiente:** manter n8n principal no Raspberry e considerar serviço de processamento no computador apenas após necessidade medida; não instalar outro n8n agora. Ver [ARQUITETURA-AUTOMACOES.md](ARQUITETURA-AUTOMACOES.md).

## 8. Gemini: fatos, limites e privacidade

O usuário trouxe parecer do Gemini sobre assinatura, API, tier gratuito, MCP e custo. **Não repetir como limites atuais** os números e preços históricos ou a recomendação de Gemini 1.5/2.0 sem conferir fontes atualizadas. Assinatura do aplicativo Gemini e consumo da Gemini API são produtos distintos. O tier gratuito pode ter condições de uso/revisão de dados; não passar mensagens reais de clientes a um modelo gratuito sem analisar termos, base legal e privacidade. Plano pago, isoladamente, não assegura conformidade com LGPD.

Próximo levantamento: verificar modelos, cotas e cobrança efetivos na conta/projeto Google AI Studio, sem expor chaves; depois configurar credenciais protegidas no n8n quando autorizado. Não conectar IA a clientes ainda.

## 9. Pendências conhecidas

- Logo quebrado no Evolution Manager: melhoria UX futura, não bloqueante; registrada na documentação anterior.
- Chat interno do Manager não mostra mensagens recentes; evento Webhook é recebido; causa não confirmada.
- Reinício real do add-on, reconexão WhatsApp e persistência longa não homologados.
- Backup e restauração de PostgreSQL/sessão e n8n não homologados.
- CPU/RAM do Pi e concorrência com HA/Jellyfin não medidos.
- Filtros de grupos, tipos de mídia, duplicações e idempotência não homologados de ponta a ponta.
- Anti-loop robusto para envio automático e permissão do comando doméstico não implementados.
- Integração Gemini API, histórico de conversa, revisão de respostas e envio automático: não implementados.
- A integração Baileys/Evolution API é não oficial para WhatsApp: há risco de restrições de conta. Evitar disparos em massa.
- Não há evidência de estado atual dos workflows após esta data; confirmar somente o necessário ao retomar.

## 10. Mensagem curta para retomar em outro chat

> Atue na automação WhatsApp da Umdoislab no modo /pair. Leia `docs/PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md`, `docs/CONTINUIDADE.md` e `docs/ARQUITETURA-AUTOMACOES.md` em `mmcromero/hassio-addons`. Estado confirmado pelo proprietário: Evolution API add-on 0.1.0 / upstream v2.3.7 em Raspberry Pi 4 8 GB, instância `umdoislab` Connected, n8n 2.47.3, webhook `/webhook/umdoislab-atendimento-inicial`; v1.1 com 4 nós apresentou Success e classificou pergunta de preço. Não envia respostas. Automação doméstica é somente simulador separado. Próximo passo: exportar o JSON **real da v1.1 publicada** e criar v1.2 com respostas preparadas e revisão, sem envio; IA Gemini em workflow separado com dados sintéticos. Evite nós duplicados, webhooks com path conflitante, instruções manuais longas e dados sensíveis. Não modificar serviços nem código sem autorização.

## 11. Convenções de evidência

- **Verificado no GitHub:** arquivos do próprio repositório lidos em 13/11/2026.
- **Confirmado pelo proprietário/capturas:** configuração e resultados de execução descritos; não equivale a acesso direto ao ambiente.
- **Planejado:** objetivo aprovado conceitualmente, não implementado.
- **Pendente/não verificado:** comportamento ou artefato sem evidência completa; não preencher por inferência.
