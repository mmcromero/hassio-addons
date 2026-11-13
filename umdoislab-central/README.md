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
  "summary": "Consulta de preço"
}
```
Não compartilhar telefone/ID reais no GitHub. A origem precisa ser validada em rede privada, com secret e sem portas publicadas.

## Regras de produto

- Lista ordenada por `updated_at DESC`; cartões compactos; busca e estado; detalhes com resumo, última mensagem e resposta manual.
- `pending` (aguardando humano), `human` (assumido), `done` (resolvido). Resposta enviada pelo painel passa a `human`, nunca a `done`.
- Enquanto `human`, novos eventos atualizam a última mensagem, sem mudar o estado.
- Assumir, resolver e reabrir são operações explícitas. `done` só é reaberto por ação humana; entrada posterior do mesmo contato cria pendência novamente (nova conversa operacional).
- Falha ao enviar **não** é registrada como sucesso; repetição acidental reduzida pelo bloqueio do botão durante a requisição. Deduplicação no servidor por `request_id` exige chave por tentativa. Confirmação de entrega ao WhatsApp depende de eventos de ACK não implementados.
- O backend chama `POST /message/sendText/{instance}` com `apikey`; precisa de homologação real na Evolution API v2.3.7, e não exibe credenciais ao navegador.
