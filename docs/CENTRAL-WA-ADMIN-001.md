# CENTRAL-WA-ADMIN-001 — Saída administrativa STATUS (proposta para homologação)

**Estado em 17/11/2026:** implementação em branch de trabalho. **Não instalada no Raspberry, não integrada à instância n8n ativa e não homologada.** Não depende de GitHub Actions.

## Decisão funcional

Um contato pode constar nas listas comerciais `test` e `excluded` simultaneamente: `excluded` prevalece. Esta política **não muda**.

O Orquestrador reconhece comandos do proprietário **antes** de processar mensagens comerciais. A resposta ao comando `status` usa canal administrativo dedicado, e nunca `/bridge/send-auto`, que deve continuar recusando os contatos excluídos.

## Contrato do endpoint

`POST /bridge/send-admin-status` é exclusivo de uso interno autenticado.

- Exige `Authorization: Bearer <admin_reply_secret>`, segredo distinto de `bridge_secret` e `evolution_api_key`, mínimo 32 caracteres.
- Exige `admin_owner_jid` definido no Home Assistant, JID individual numérico. **Não contém telefone nem segredo no repositório.**
- Exige corpo com **apenas** `instance`, `senderId`, `messageId`, `command`, `text`. `command` deve ser exatamente `status`; instância e destino precisam coincidir com as opções locais.
- `messageId` válido, texto limitado a 1200 caracteres, destino sempre retirado de `admin_owner_jid` local e não de valor arbitrário.
- Cada evento possui reserva persistente em `replies` com chave `admin-status-<sha256>`. Mesmo após envio incerto, **não repetir automaticamente**, para evitar duplicatas.
- Retorno 200 indica solicitação aceita pela Evolution, **não confirma entrega ao WhatsApp**. Falha/timeout: marcar `uncertain`.
- Não altera status comercial, escolha de atendimento, política `excluded`, nem registros `conversation_turns`. A API comercial mantém comportamento anterior.

## Integração n8n (ainda não ativada)

No Orquestrador Base, branch `release/v0.1.0-rc.1`:
`n8n/workflow-whatsapp-receptor-avisaqui-status-lab.json` passa a enviar a resposta `status` para a rota administrativa, por HTTP Request com **credencial Header Auth própria**, não reutilizando a credencial comercial.

**P0 antes de publicação:** validar autenticação Evolution→Webhook n8n na versão real instalada; configurar credencial segura do Webhook, JID pessoal e credencial específica do envio administrativo no n8n. O workflow é uma cópia LAB em caminho diferente e inativa. Não editar o receptor comercial atual sem cópia, revisão e homologação.

A rota administrativa autentica **o serviço chamador**, não confirma por si só a autoria da mensagem WhatsApp. A verificação da origem no n8n **é requisito obrigatório** antes de ligar o ramo que a chama.

## Configuração controlada do add-on

Duas novas opções **vazias por padrão** em `config.yaml`:
- `admin_reply_secret`: segredo forte **diferente** de todos os tokens existentes, não colocar no Git;
- `admin_owner_jid`: JID do proprietário no formato `<DDI+DDD+numero>@s.whatsapp.net` (configurar no Home Assistant, não no template).

A opção antiga `auto_test_sender` continua existindo; a inclusão do novo endpoint não remove ou altera seu valor.

## Validação local obrigatória (sem GitHub Actions)

Executar em clone isolado com Python 3 compatível:

```sh
python3 -m unittest discover -s umdoislab-central/tests -p 'test_admin_status.py' -v
python3 -m py_compile umdoislab-central/server.py
```

Cobrir: autenticação ausente/incorreta; credencial comercial diferente; destinatário diferente; comando `liberar`/`testar` recusado; exclusão comercial mantida; duplicação; timeout/rejeição da Evolution; corpo inválido; não registrar sucesso como entrega confirmada.

**Estado:** testes foram adicionados ao repositório e sua estrutura revisada, mas **não executados nesta rodada**. Também faltam teste real Evolution/HA/n8n e revisão do diff de implantação.

## Gates de segurança e publicação

1. Conferir diff e executar a suíte offline em ambiente compatível.
2. Confirmar versão exata instalada de Central, Evolution e n8n; garantir compatibilidade das opções e segurança da rede.
3. Validar o Webhook da Evolution em ambiente de ensaio com teste positivo e teste negativo de autenticação. Sem esse gate, comandos ficam desligados.
4. Configurar credenciais novas apenas no Home Assistant/n8n, sem copiá-las para logs/Issues.
5. Instalar versão validada por caminho **sem GitHub Actions** (empacotamento local controlado, com backup e rollback), somente depois de autorização e evidência.
6. Testar um evento real de `status` e confirmar que o proprietário excluído não recebe Gemini, mas recebe a resposta administrativa. Verificar que a esposa segue no fluxo comercial.
7. `testar` e `liberar` permanecem bloqueados e fora do escopo. Exigem outro contrato de autorização com gate do worker e rastreabilidade.

**Nenhuma ação em produção foi realizada nesta entrega.**
