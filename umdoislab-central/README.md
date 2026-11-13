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
