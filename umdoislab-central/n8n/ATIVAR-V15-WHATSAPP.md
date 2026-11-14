# Umdoislab v1.5 — WhatsApp real

O usuário confirmou em 13/11/2026 que a v1.4 foi desativada e removida do n8n, com backup exportado. Não reativar a v1.4.

## Workflow

Arquivo: `n8n/atendimento-v1.5-whatsapp-real.json`.

Cadeia: Webhook POST `umdoislab-v15` → validação da mensagem Evolution → `/bridge/inbound` → classificação Gemini apenas no estado automático → resposta controlada → `/bridge/send-auto`. Não há envio direto à Evolution no n8n.

Pré-requisitos de ativação:
1. Importar em workflow **novo** no n8n.
2. Nó **Validar remetente e classificar**: substituir `CONFIGURAR_JID_TESTE@s.whatsapp.net` pelo JID **exato** `<número>@s.whatsapp.net` recebido no evento Evolution. Não colocar número de outra pessoa. Eventos `@lid`, grupos e `fromMe=true` são bloqueados até tratamento explícito.
3. Add-on Central → Configuração → `auto_test_sender`: preencher o mesmo JID exato, salvar e reiniciar a Central para conferir aplicação. Até isso, nenhum envio automático é aceito.
4. Nos nós **Consultar e registrar na Central** e **Enviar apenas pela Central**, selecionar a credencial `Central Umdoislab` (Header Auth `Authorization: Bearer <bridge_secret>`). Nunca publicar a chave no repositório.
5. Confirmar que `http://45c28620-umdoislab-central:8099` ainda é o host real da Central e pode ser acessado do n8n.
6. Publicar **somente** este workflow, com Webhook de produção `http://homeassistant.local:5678/webhook/umdoislab-v15`; no Evolution Manager → instância `umdoislab` → Events → Webhook, habilitar `MESSAGES_UPSERT` e apontar URL ao novo webhook. Não publicar fluxos concorrentes.
7. Nó **Gemini — entender intenção**: selecionar a credencial já criada `Gemini — Umdoislab`. Se `models/gemini-2.5-flash` não aparecer no seletor dessa credencial, selecionar um modelo Flash disponível na conta, sem alterar o conteúdo das regras. A IA apenas classifica uma palavra de intenção; texto ao cliente é escolhido pelo código. Se Gemini falhar, o fluxo encerra sem envio (não usar Continue On Fail).
8. Usar **outro WhatsApp** para enviar à conta conectada à Evolution: mensagens enviadas da própria conta vêm como `fromMe=true` e são filtradas.
9. Confirmar uma execução real no n8n, primeiro contato no WhatsApp e verificação de nova pendência humana no painel.

## Regras

- Eventos recebidos com `fromMe=true`, grupos, mídias sem texto, JID não seguro ou fora da lista de teste são ignorados.
- `/bridge/inbound` mantém a decisão persistente e idempotente; o humano pode assumir a conversa e bloquear o robô; o cliente pode responder 1/2 após oferta.
- Envio final só por `/bridge/send-auto`, que valida estado e destinatário novamente; duplicados bloqueados.
- A v1.5 atual usa **Gemini para classificação de intenção** depois da decisão persistente na Central. O texto enviado é escolhido de uma lista de respostas controladas, sem preço, estoque ou frete inventados. Integração real ao WooCommerce e memória de contexto mais rica seguem pendentes. Evitar confundir automação funcional com interpretação por IA já homologada.

## Diagnóstico

Se não houver execução, verificar produção publicada, URL e evento no Manager, e se a instância está conectada. Se `/bridge/send-auto` responder 403, conferir apenas `auto_test_sender` e credencial; se responder 409, consultar estado da conversa no painel — pode ser bloqueio humano, repetição ou escolha pendente.

Se houver erro de formato no payload Evolution, usar captura sanitizada do nó Webhook para ajustar a leitura do objeto `body.data.key` — não tentar aceitar `fromMe=true` como solução.

Este pacote não altera add-on HA ou banco, e não substitui as credenciais no servidor.
