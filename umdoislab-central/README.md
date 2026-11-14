# Umdoislab — Central de Atendimento (protótipo funcional v0.1.0)

Add-on separado do Evolution API. Interface mobile-first via **Home Assistant Ingress**; banco SQLite em `/data/central.sqlite3`; resposta manual pelo backend para Evolution API. **Não instalado no Raspberry** e **não integrado ainda ao workflow v1.4**.

## Segurança e operação

- Página web e endpoints de gestão acessíveis somente pelo proxy Ingress do Home Assistant (IP do Supervisor `172.30.32.2`). Sidebar visível apenas a administradores.
- `POST /bridge/events` aceita eventos *normalizados* do n8n na rede interna **somente com** `Authorization: Bearer <bridge_secret>`. Não publicar portas para a Internet.
- O painel não recebe nem expõe a chave da Evolution API; o add-on a lê de `/data/options.json` e a envia ao backend Evolution somente ao clicar **Enviar**.
- Sem resposta automática e sem interrupção da v1.4. Envio manual não marca a conversa como resolvida.
- Dados sensíveis ficam no banco local do add-on. Não coletar conversas inteiras: salva ID da mensagem, remetente, nome, assunto, trecho limitado a 500 caracteres, resumo, estados e última resposta manual; histórico completo permanece no WhatsApp.
- Limpeza automática de dados **não habilitada**. Política de retenção, backup e restauração ainda devem ser aprovadas.

## Instalação FUTURA (após revisão do PR)

1. Disponibilizar o add-on na loja a partir do repositório `mmcromero/hassio-addons`.
2. Em opções: cadastrar `bridge_secret` forte e distinto das outras chaves, `evolution_api_key` já existente no add-on Evolution; conferir endereço interno acessível à Evolution API.
3. Instalar e iniciar **somente este add-on**; abrir pelo Ingress com usuário administrador; não ativar a entrada de eventos ainda.
4. Criar **integração em cópia de desenvolvimento do workflow v1.4**, enviando ao `/bridge/events` o item normalizado após `Organizar dados`. Verificar primeiro o DNS e a conectividade entre contêineres. Nunca expor `bridge_secret` na página ou no JSON versionado.
5. Testar recebimento sem envio; só então validar botão Enviar em contato de teste autorizado. A versão v1.4 permanece intacta até aprovação de substituição.

Formato JSON aceito por `POST /bridge/events`:
```json
{
  "instance": "umdoislab",
  "isClientMessage": true,
  "isGroup": false,
  "senderId": "5511999999999@s.whatsapp.net",
  "senderName": "Contato de teste",
  "messageId": "ID_UNICO",
  "messageText": "Quanto custa?",
  "category": "preco",
  "summary": "Consulta de preço",
  "handoffRequested": true
}
```
A **flag `handoffRequested: true` é obrigatória para criar uma nova pendência**. Eventos comuns da v1.4 não devem gerar uma ficha para cada mensagem. Se a pendência já existe, eventos novos podem atualizar a última mensagem mesmo sem a flag. Não compartilhar telefone/ID reais no GitHub. A origem precisa ser validada em rede privada, com secret e sem portas publicadas.

## Regras de produto

- Lista ordenada por `updated_at DESC`; cartões compactos; busca e estado; detalhes com resumo, última mensagem e resposta manual.
- `pending` (aguardando humano), `human` (assumido), `done` (resolvido). Resposta enviada pelo painel passa a `human`, nunca a `done`.
- Enquanto `human`, novos eventos atualizam a última mensagem, sem mudar o estado.
- Assumir, resolver e reabrir são operações explícitas. `done` só é reaberto por ação humana; entrada posterior do mesmo contato cria pendência novamente (nova conversa operacional).
- Falha ao enviar **não** é registrada como sucesso; repetição acidental reduzida pelo bloqueio do botão durante a requisição. Deduplicação no servidor por `request_id` exige chave por tentativa. Confirmação de entrega ao WhatsApp depende de eventos de ACK não implementados.
- O backend chama `POST /message/sendText/{instance}` com `apikey`; precisa de homologação real na Evolution API v2.3.7, e não exibe credenciais ao navegador.

## Limites desta primeira implementação

- Este PR **não muda a Evolution API, o n8n, a v1.4 ou o Home Assistant instalado**. A interface, o backend e as regras estão no repositório, ainda sem homologação real do add-on.
- O endereço do add-on acessível do n8n depende da rede real entre contêineres. Não assumir o alias antes da instalação. O endpoint de ingestão não publica porta no host e exige Bearer secret.
- O primeiro conector do n8n deve encaminhar apenas eventos de **transferência humana**, com campos normalizados. O painel não implementa a detecção por IA nem o anti-loop da v1.5: eles pertencem à etapa posterior do workflow.
- Mensagem enviada pelo painel usa o destino WhatsApp no formato numérico `@s.whatsapp.net`. Se o evento trouxer ID `@lid` ou outro formato, o envio é bloqueado até implementar resolução segura do destino.
- Confirmação de HTTP 2xx da Evolution significa **solicitação aceita**, não mensagem entregue/lida. A UI informa esta diferença.
- A conexão via Ingress pressupõe autenticação do Home Assistant e restrição ao usuário administrador. Não colocar o serviço diretamente na Internet.
- SQLite faz persistência local na área `/data` do add-on; respaldos/retenção e restauração precisam de validação antes do uso contínuo.

## Integração n8n ↔ Central (implementada em branch, **NÃO publicada**)

O painel agora inclui endpoints privados que exigem o mesmo Bearer token `bridge_secret`:

| Rota | Uso | Regra |
|---|---|---|
| `POST /bridge/decision` | Consulta de estado pelo n8n | Devolve `allowAutoReply`, `state`, `reason`, `needsCustomerChoice` |
| `POST /bridge/send-auto` | Único caminho permitido de envio automático na **futura** v1.5 | Confere estado **no momento do envio**, sob trava compartilhada com Assumir/Resolver, autentica, verifica destinatário autorizado e impede duplicação por `messageId` |
| `POST /bridge/events` | Recebe mensagem normalizada e pendência humana | Somente `handoffRequested:true` cria uma ficha nova |

### Exemplo de consulta de estado (não contém segredo)

```json
{"instance":"umdoislab","senderId":"5511999999999@s.whatsapp.net"}
```

Para uma conversa sem pendência ou resolvida, `allowAutoReply:true`. Para `human` ou `pending`, `allowAutoReply:false`. Se a Central estiver indisponível, a chamada falha; **o fluxo não pode continuar por um ramo de erro**.

### Exemplo de envio automático protegido (não contém segredo)

```json
{
  "instance":"umdoislab",
  "senderId":"5511999999999@s.whatsapp.net",
  "messageId":"ID_DA_MENSAGEM_ORIGINAL",
  "text":"Texto aprovado pelo atendimento automático"
}
```

A Central verifica:
- O Bearer secret e a instância.
- Que o destinatário coincide exatamente com `auto_test_sender`, configurado no Home Assistant, e é um JID individual numérico válido.
- Que o estado do atendimento permite envio **sob a mesma trava que protege a ação Assumir**.
- Que não ocorreu tentativa anterior para o mesmo `senderId + messageId`.
- Que a Evolution API está configurada. HTTP 2xx indica **aceitação da solicitação**, não entrega.

Em `pending`, nenhuma resposta automática comum é enviada. A opção aprovada de *aguardar humano ou continuar com o robô* **ainda precisa ser implementada** com decisão explícita do cliente e proteção contra loops. Não habilitar envio automático para esse estado até a implementação.

O arquivo [n8n/central-guard-lab.json](n8n/central-guard-lab.json) pode ser importado em um workflow de laboratório **não publicado**. Possui gatilho manual e mensagem sintética, consulta `/bridge/decision` e apresenta o resultado; **não envia WhatsApp**. Deve-se configurar a URL **interna** real e a credencial Header Auth com cabeçalho `Authorization: Bearer <segredo>` no n8n. O JSON não contém segredo.

**A v1.4 continua usando sua rota atual de envio**, sem proteção nova. A consulta não substitui o envio protegido: o futuro fluxo v1.5 precisa usar **/bridge/send-auto em vez do HTTP Request direto à Evolution**, para que uma intervenção humana não possa ocorrer entre consulta e envio sem ser percebida. NÃO editar nem ativar a v1.4 para testar esta integração.

### Limitações controladas

- Nenhum teste foi executado contra o Raspberry real nem contra o n8n real; homologação em laboratório e testes de envio ao contato permitido ainda são necessários.
- A configuração `auto_test_sender` deve corresponder à lista de teste do workflow de desenvolvimento. Nunca usar todos os contatos por padrão.
- Conversas existentes no WhatsApp e mensagens manuais enviadas diretamente pelo aplicativo não são transferidas automaticamente ao painel nesta etapa.
- O anti-loop semântico, as mensagens de oferta de escolha e a interpretação de intenção por IA ainda não foram integrados. O bloqueio técnico de atendimento humano e de duplicação de saída já está na Central.

## Escolha do cliente, memória de estado e anti-loop — etapa de laboratório

Esta etapa adiciona `POST /bridge/inbound`, que recebe o evento normalizado uma vez por
`senderId + messageId`, guarda o estado em SQLite e responde com uma das ações:

| Ação | Quando | Saída |
| --- | --- | --- |
| `handoff` | Transferência nova; ou segunda dúvida não compreendida sem ficha | Enviar **uma única** mensagem de encaminhamento |
| `silent` | Cliente agradece, confirma espera, ou você já assumiu | Não enviar nova mensagem |
| `offer_choice` | Cliente tem pendência e escreve outra pergunta | Uma oferta de escolha: **1 = aguardar**, **2 = continuar** |
| `resume` | Cliente digita explicitamente **2** ou frase equivalente | Ativa o robô sem apagar pendência humana |
| `auto` | Sem pendência/resolvido ou retomada expressa | Selecionar resposta controlada; enviar pelo guard |
| `ignore` | Evento já registrado | Não enviar |

**Texto de encaminhamento e escolha é controlado no servidor** e não pode ser
substituído pelo workflow. O servidor permite **uma oferta por episódio de pendência**;
com `waiting`, o cliente ainda pode escolher `2` depois, mas não recebe ofertas
repetidas. Em `opted_in`, a ficha continua `pending` até o operador marcar resolvido.
Em `human`, nem o opt-in do cliente pode furar o bloqueio do responsável.

### Anti-loop

- Cada mensagem recebida é persistida em `inbound_ids` e ignorada na repetição.
- Cada tentativa de envio usa uma chave por contato/messageId/tipo.
- `bot_guard` guarda o último texto automático e o número de incompreensões mesmo
  antes de existir uma ficha no painel.
- Texto automático idêntico ao anterior é bloqueado. Em pendência humana com robô
  retomado, o estado passa a `exhausted`, encerrando a retomada; a pendência permanece.
- Uma resposta de incompreensão seguida de outro texto não entendido faz o fluxo
  solicitar atendimento humano; não insistir em respostas genéricas.
- Ao acertar uma resposta comum, o contador de incompreensão é reiniciado.
- Falha ou indisponibilidade da Central **não permite continuar enviando pela Evolution diretamente**.

### Arquivo importável

[n8n/atendimento-v1.5-laboratorio.json](n8n/atendimento-v1.5-laboratorio.json) — pipeline de laboratório com
`Manual Trigger`, mensagem sintética editável, classificação local limitada,
`POST /bridge/inbound`, seleção de resposta e etapa opcional de envio.
**Por padrão a condição de envio é sempre falsa**, portanto não envia WhatsApp.
A execução manual poderá gravar dados de teste na Central, se o add-on for instalado
e o endpoint configurado. Não publicar, não reutilizar o webhook da v1.4.

Antes de qualquer execução:
1. Instalar a Central **somente em homologação** e confirmar a URL interna.
2. Configurar a credencial n8n Header Auth `Authorization: Bearer <bridge_secret>`,
   sem inserir o segredo no arquivo JSON.
3. Usar um remetente sintético para avaliar decisões; **não habilitar envio**.
4. Alterar o `messageId` a cada nova simulação; o mesmo ID é ignorado para evitar repetição.
5. Se houver autorização posterior para testar envio real, configurar
   `auto_test_sender` com o JID do contato autorizado e habilitar o ramo de envio
   somente nessa cópia isolada. Não publicar nem alterar a v1.4.

**Limites funcionais ainda abertos:** Gemini como intérprete, consulta real ao
WooCommerce, notificações de pendências, classificação de mídia e integração
com intervenção humana feita diretamente pelo aplicativo WhatsApp. A classificação
do fluxo de laboratório usa regras locais simples; não deve ser apresentada como
interpretação por IA. A interface móvel mantém o desenho anteriormente aprovado.

## Política de automação (Central 0.2.0 — branch de revisão)

O painel **Automação** controla o atendimento, separado da conexão técnica da Evolution:
- **Somente teste:** a lista editável permite vários JIDs. Em migração, o valor antigo
  `auto_test_sender` continua autorizado para não interromper o teste existente.
- **Somente novos:** consulta uma referência inicial de contatos/chats da Evolution,
  e não libera contatos registrados nela. A sincronização é **pré-requisito**, porém
  a completude dessa referência ainda precisa ser homologada contra o Manager.
  Não selecionar esta modalidade para público real antes da conferência.
- **Todos:** permite contatos individuais com JID numérico, exceto os bloqueados.
- **Lista de exclusão:** sempre prevalece, inclusive quando o atendente humano não
  assumiu a conversa. Não há envio automático para números excluídos.
- Números podem ser inseridos em lote com **ponto e vírgula, vírgula ou Enter**;
  aceita `+55 (11) 99999-9999`, `5511999999999` e o formato completo.
  Guarda o destino canônico `5511999999999@s.whatsapp.net`. Etiquetas com botão
  **×** permitem retirar números, sem reiniciar a Central.

**Atenção à atualização:** a versão anterior (0.1.0) ainda está no Home Assistant.
A 0.2.0 não foi instalada automaticamente. O n8n publicado deve manter seu fluxo
atual durante a homologação. O JSON atualizado na branch remove a lista fixa
do próprio n8n e delega todo controle de autorização à Central, que o valida
novamente antes do envio. O modo inicial continuará restrito a números de teste.

### Nota de backlog — Catálogo de clientes (futuro, fora do escopo atual)
Considerar uma ficha de clientes alimentada pelo histórico do WhatsApp com
informações adicionais opcionais e controle de privacidade. Não implementar
nesta demanda, nem ampliar acesso às mensagens de contatos sem consentimento
e avaliação da finalidade.


## Atendimento contextual Gemini — Central 0.3.0 / workflow v1.6

A Central armazena mensagens de entrada autorizadas e respostas automáticas aceitas,
isoladas pelo destinatário. O endpoint autenticado `POST /bridge/context` expõe no
máximo 12 falas do mesmo contato; não permite acesso ao histórico de outros contatos.
O n8n v1.6 passa a buscar esse contexto antes do Gemini produzir uma resposta
natural. A resposta é limitada e revisada por validações antes de atravessar
`/bridge/send-auto`, que continua controlando permissões, exclusões, estado
humano e deduplicação. Valores comerciais não são consultados e não devem ser
inventados. Sem histórico persistido, o modelo usa a mensagem atual.
A primeira resposta de mensagens anteriormente enviadas não é reconstruída.

**Publicação:** atualizar Central para 0.3.0 e depois atualizar o n8n com o arquivo
`n8n/atendimento-v1.5-whatsapp-real.json` (nome interno v1.6). Selecionar
credencial **Central Umdoislab** também no nó `Consultar contexto na Central`
e manter **Gemini — Umdoislab** no nó Gemini; conservar o webhook
`/webhook/umdoislab-v15`. Não ativar duas cópias com o mesmo caminho de webhook.
Fazer um teste com o número autorizado antes de ampliar a política.
