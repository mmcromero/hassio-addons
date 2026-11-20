# Histórico da distribuição — Central WhatsApp Umdoislab

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
