# Umdoislab — Correção de confirmação de encaminhamento humano (v1.7 proposta)

**Data:** 14/11/2026 BRT. **Estado:** código e JSON de laboratório em branch, **NÃO instalado/publicado**.

## Diagnóstico registrado
No workflow n8n **v1.6 publicado** (captura do proprietário), o Gemini respondeu que havia encaminhado uma solicitação após o cliente dizer **“Sim”**. A Central **0.3.0**, porém, mostrava zero pendências e uma ficha já resolvida. O código versionado da v1.6 só definia `handoffRequested=true` por palavras como “atendente” e “humano”; não havia estado persistente de oferta feita por Gemini. Portanto, “Sim” podia ser interpretado pela IA como confirmação, sem abrir ticket. **O payload exato da execução em produção não foi auditado.**

## Solução implementada em branch
1. A IA deve responder **exclusivamente** com `[[OFERECER_HUMANO]]` quando quiser oferecer um atendente. O nó n8n só transforma esse marcador exato em `kind:human_offer`.
2. `/bridge/send-auto` substitui o texto do marcador por uma pergunta fixa da Central: **“Quer que eu encaminhe sua dúvida para um atendente? Responda SIM ou NÃO.”** O n8n não pode sobrescrever essa pergunta.
3. **Somente após HTTP 2xx aceito pela Evolution**, a Central persiste oferta por remetente em `handoff_offers`. HTTP 2xx **não significa mensagem entregue**, apenas aceite.
4. A oferta vale até **duas horas** e exclusivamente para a **próxima mensagem recebida** do mesmo contato. `Sim` explícito cria uma pendência **antes** da resposta ao cliente; `Não`, outra frase ou prazo expirado consomem/invalidam a oferta. Um “Sim” solto **não cria atendimento**.
5. O resumo da ficha mantém a mensagem anterior do cliente quando disponível; não mostra apenas “Sim”.
6. O servidor **bloqueia** mensagem automática normal que declare “encaminhei”, “foi encaminhado” etc. Ofertas fora do protocolo também são rejeitadas. Em estado `human`, a Central não permite nova oferta.
7. O envio de confirmação de handoff segue a rota protegida da Central, que primeiro cria a pendência. Falha na Central **não** deve ser substituída por envio direto à Evolution.

## Arquivos
- `umdoislab-central/server.py`: tabela `handoff_offers`, transição vinculada a mensagem, guarda de saída.
- `umdoislab-central/n8n/atendimento-v1.7-handoff-verificado.json`: **nova cópia** do workflow com modelo Gemini e guardas; não substituir o JSON histórico v1.6.
- `umdoislab-central/test_handoff_confirm.py`: cenários isolados, sem enviar WhatsApp real.
- CI da Central: testes Python, validação do novo JSON e build ARM64 de laboratório.

## Homologação e limites
- O novo workflow **não foi importado, testado ou publicado no n8n real**.
- A Central **0.3.0 instalada não tem essa correção**. O add-on desta branch foi preparado como **0.4.0**, ainda não instalado; antes da futura publicação conferir migração SQLite, backup e compatibilidade com versões existentes.
- **Não publicar a v1.7 antes de atualizar e homologar a Central**, senão `human_offer` será rejeitado na instalação atual. Publicar cópia isolada e evitar dois Webhooks publicados com mesmo path.
- O modelo pode desobedecer o marcador ou fazer oferta não padronizada: nesse caso a resposta deve **falhar fechada**, sem prometer uma transferência. Isso é melhor do que declarar ação inexistente.
- O estado de oferta só é persistido depois de 2xx. Em erro de rede de resultado incerto, não repetir automaticamente; investigar se houve entrega.
- Registro de pendência é distinta de **notificação ao operador**, ainda não confirmada por execução real; a interface lista tickets pendentes.
- Sem ampliação de política de contatos, sem implementação do validador histórico adiado, sem troca do modelo Gemini, sem credenciais no Git.

## Próxima entrega autorizável
Revisar PR e CI; preparar plano de publicação em ordem **Central nova versão → n8n v1.7**. Exigir backup/rollback e testes com contato de teste já aprovado. **Não fazer deploy ou merge sem validação das condições específicas.**

## Preservação de contexto
A versão de produção continua: n8n workflow **v1.6**, Central HA **0.3.0**, Evolution add-on **0.1.0**. Nome do JSON da v1.6 ainda contém v1.5. O PR documenta correção futura, não atualização real do Raspberry.
