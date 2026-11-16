# UMDOISLAB — Monitor de conversas automáticas (Central 0.4.1)

**Data:** 14/11/2026 (BRT)  
**Estado:** implementação em branch; **não instalada** no Home Assistant nem homologada com mensagens reais.  
**Objetivo aprovado pelo proprietário:** acompanhar conversas sem ficar olhando o WhatsApp, ver quais receberam resposta aceita, quais precisam ser verificadas e quais foram encaminhadas a humano.

## Implementação

- Central `0.4.1`: painel de **Acompanhamento automático** na tela de Atendimentos, sem remover os filtros de fichas humanas.
- Indicadores: conversas recebidas, respostas com envio aceito, sem resposta/verificar e atendimento humano.
- Filtros de acesso rápido: **Precisam de atenção**, **Automáticos**, **Todas as conversas**.
- Cartões em ordem de última mensagem, com estado e trecho. Abertura de histórico recente (até 30 falas por contato), somente por **Ingress administrativo**, sem ação de envio no painel de histórico.
- API interna `GET /api/activity` (até 200 contatos) e `GET /api/activity/<sender>` (até 30 falas). Não publicar essas rotas fora do Ingress.
- Os dados de monitoramento são construídos a partir das mensagens **autorizadas pela política da Central** que chegaram pelo bridge; registros bloqueados por política não entram. Isso **não** equivale a listar todos os chats existentes no telefone nem comprova cobertura total do WhatsApp.
- A migração SQLite só adiciona `activity_contacts` e preenche dados de mensagens já persistidas; não apaga nem altera `conversations`, `conversation_turns` ou `replies`.

## Regras técnicas de estado

| Estado mostrado | Evidência |
| --- | --- |
| **Resposta aceita pela Evolution** | Último registro cronológico da conversa na Central é uma saída do robô persistida após HTTP 2xx |
| **Sem resposta registrada** | Último registro é entrada de cliente e não há envio aceito depois |
| **Envio sem confirmação / verificar** | Existe tentativa de envio recente incerta/solicitada sem resposta aceita posterior |
| **Aguardando humano** | Ficha `conversations.status=pending` |
| **Em atendimento humano** | Ficha `conversations.status=human` |

**Não afirmar “respondido com sucesso” ou “resolvido pelo robô”:** o aceite da Evolution não prova entrega, leitura ou satisfação do cliente. O painel apresenta evidência de fluxo, não qualidade semântica do atendimento. Alertas “sem resposta” podem incluir mensagens recentes ainda em processamento; não há prazo/SLA definido nesta primeira entrega.

## Limitações e decisões futuras

- Os indicadores contam **contatos/conversas listados** (até 200 recentes), não número de mensagens nem clientes únicos no aparelho.
- Mensagens não autorizadas pela política, mídia sem texto e eventos não recebidos pelo n8n podem não constar.
- Não há comprovante de entrega pelo WhatsApp; exigiria evento de status confiável da Evolution e modelagem própria.
- Não há notificação push, avaliação automática de qualidade do Gemini ou detecção de indisponibilidade por SLA. Essas são melhorias futuras, não parte desta versão.
- O validador de contatos históricos segue **adiado** conforme decisão anterior; não confundir este painel com aquela ferramenta.
- Não substituir o fluxo atual nem modificar credenciais, política de contatos, automação do Home Assistant ou n8n para lançar só a interface.

## Verificação e publicação

1. Rodar testes Python, sintaxe e build ARM64 na CI. O monitor deve exibir mensagem recebida sem ticket, entrada duplicada ignorada, resposta aceita, novo pedido sem resposta, estado humano e retrocompatibilidade.
2. Somente depois de CI verde, revisão do PR e verificação de migração, integrar à `main` com commit rastreável.
3. O proprietário poderá atualizar add-on HA para **0.4.1** pelo fluxo normal da loja; preservar o banco `/data/central.sqlite3`, sem apagá-lo/reinstalar.
4. Testar com contato autorizado e conferir os estados na tela; registrar evidências de instalação e homologação antes de declarar concluído em produção.

## Continuidade

Estado anterior: Central **0.4.0** disponível na `main`, workflow n8n **v1.7 JSON disponível na `main`**; não inferir se o proprietário já instalou/publicou cada componente. Estado proposto: Central 0.4.1 com monitor; **nenhum ajuste de workflow n8n** neste pacote.
