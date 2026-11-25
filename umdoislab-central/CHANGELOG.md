# Histórico da distribuição — Central WhatsApp Umdoislab

## 0.5.0-rc.5 — regressões de quarentena (24/11/2026)

- Corrige duas expectativas antigas de origem incerta: quarentena pending/origin_review, sem envio automático e sem oferta de escolha. Código de atendimento inalterado.
- RC4: 241 testes raiz, duas falhas; nova validação integral obrigatória.

## 0.5.0-rc.4 — candidata de compatibilidade Etapa 2 (24/11/2026)

- API de integração restrita ao modo de testes, com admissão temporária, vinculação ao inbound e prevenção de reenvio. Rotas legadas preservadas.
- Build exige compilação Python e execução das suítes completas antes da imagem final.
- Testes dirigidos aprovados; validação integral no Supervisor ainda pendente nesta publicação. Nenhum workflow n8n foi modificado.

## 0.5.0-rc.3 — saída incerta não assume atendimento humano (20/11/2026)

- A observação de saída `fromMe=true` sem vínculo em `bot_outbound_ids` continua `classification=uncertain`, mas **não grava `status=human`** sem evidência de intervenção humana.
- A Central mantém proteção contra envio indevido: `status=pending` e `choice_state=origin_review`; mensagens novas seguem `silent`, a consulta de autorização devolve `origin_unverified`, o outbox é cancelado e o envio automático permanece negado até revisão.
- Intervenções manuais confirmadas continuam em `human` sem alteração. Conversas existentes preservam histórico, últimas mensagens e IDs. A ação Ingress existente **Marcar como resolvido** permite liberar a conversa de teste antiga após revisão; não ocorre migração automática dos estados antigos.
- Código alterado somente em `server.py`; `config.yaml` recebe a nova versão. Sem mudança de schema, UI, DNS, Evolution, Gateway, Comercial, worker, secrets, slug, imagens ou outros apps.
- Teste dirigido isolado de SQLite/estado: **7 PASS, 0 FAIL/ERROR**, Python 3.13.5. Sete novos testes de regressão foram versionados na fonte privada, mas não executados como suíte integral. Os PASS de versões anteriores não são atribuídos à RC3.
- Publicação no GitHub não é instalação nem homologação no Raspberry. Atualizar o app original e revisar a conversa de teste; nenhum envio automático ou worker foi ativado pelo corte.

## 0.5.0-rc.2 — retorno sendText com PN/LID comprovados (20/11/2026)

- **Correção real de runtime:** a Central agora aceita `key.remoteJid=@lid` apenas se o LID for numérico (5–25 dígitos) e `key.remoteJidAlt` corresponder exatamente ao PN destinatário do envio. Mantido o caminho PN direto.
- Exige também `key.fromMe is True` e `key.id` válido; rejeita grupos, LID sem vínculo e PN divergente. O ID só é persistido em `bot_outbound_ids` quando os dados são completos e coerentes.
- A rota `/bridge/send-auto` continua a responder `accepted_not_confirmed`; não afirma entrega nem libera repetição em resultados incertos.
- Gateway de ecos n8n corrigido e publicado separadamente em versão `8fe90509-1af2-4936-852a-817c5a842578`. Webhook, Comercial, opções, slug e worker preservados.
- Testes dirigidos do helper isolado **16 PASS**, zero falhas; testes integrados adicionais foram versionados na fonte privada, mas a suíte completa do novo SHA não foi executada. Os **230 PASS antigos** pertencem ao SHA da RC1/M002 e não são atribuídos à RC2.
- Nenhuma migração de banco, instalação/atualização HA, envio de WhatsApp ou ativação do worker por este corte. Homologação ARM64/Ingress permanece com o operador da instalação original.

## 0.5.0-rc.1 — candidata multicontas para homologação controlada

- Mantido o **mesmo slug** `umdoislab_central` da Central original, com nome visual padronizado `Fábrica de Softwares - WhatsApp Umdoislab`.
- Nova estrutura `accounts.py`, preservando a conta real única `acct_001` e o banco legado `/data/central.sqlite3`. Bancos por conta são um recurso futuro, ainda sem contas adicionais cadastradas.
- Módulos completos de entrada Evolution, histórico PN/LID, verificação autenticada de saídas, outbox, reconciliação e recuperação conservadora.
- Correção M002 de falso negativo na prova PN/LID, com fallback somente após ausência principal comprovada.
- `evolution_webhook_secret` declarado no manifesto como senha, sem valor definido.
- UI e imagens preservadas exatamente por Git blob SHA.
- Evidência de fonte: commit `3165bf6aa9b448e1270e9aade60a8f367450d2a4`; commit de código testado `33ea55f67f94c21b5b61ed80abbfdc72bd39f3bd`; 230 testes offline PASS registrados no PR #10.
- **Ainda sujeito a teste de build/boot ARM64, Ingress e autenticação no Raspberry.** Worker desativado, sem alteração do Gateway n8n ou webhook Evolution.

## 0.4.0 — edição anterior

- Central original de atendimento humano, política, conversa e Ingress, com banco SQLite persistente.
- Nome na loja anteriormente: `Fábrica de Softwares - 12Labs Central de Atendimento`. Este nome é histórico; a marca correta é **Umdoislab**.
