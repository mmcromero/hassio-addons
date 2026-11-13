# Revisão técnica do PR #5 — Central de Atendimento Umdoislab

**Escopo revisado:** configuração do add-on, backend HTTP/SQLite, interface mobile-first, integração Evolution API, testes e preparação de instalação.  
**Ambiente real:** Home Assistant no Raspberry Pi **não acessado nem modificado**. A v1.4 no n8n continua publicada como antes.  
**Evidências:** diff no GitHub, documentação oficial do Home Assistant Ingress/base ARM64 e CI do PR.

## Correções realizadas nesta revisão

| Prioridade | Achado | Correção |
| --- | --- | --- |
| P0 | Regex do destinatário utilizava barras invertidas duplicadas e poderia rejeitar JIDs válidos | Função única `valid_sender_for_send`, formato `5511...@s.whatsapp.net` e testes positivos/negativos |
| P0 | Tentativa de envio com credencial ausente ficava reservada na tabela de idempotência e impediria repetição após correção | Validar opções/instância/destino **antes** do registro `request_id` |
| P1 | `crypto.randomUUID()` pode não estar disponível no HA aberto em HTTP local | Fallback seguro usando `crypto.getRandomValues`; sem gerador inseguro |
| P1 | Lista limitada às 150 conversas mais recentes poderia esconder pendências antigas | Retornar **todas as pendências abertas** e somente 50 registros resolvidos mais recentes, com ordem por atividade |
| P1 | CI inicial não construía a imagem para o Raspberry Pi | Adicionado build Docker `linux/arm64` sem publicar a imagem; testes de JID e estados |

## Segurança — avaliação

- Ingress, sem portas de host publicadas e com restrição de origem Supervisor (`172.30.32.2`), conforme [guia oficial](https://contributors.home-assistant.io/apps/guides/ingress/).
- Sidebar restrita a administradores (`panel_admin: true`), sem acesso externo direto ao serviço.
- Endpoint de entrada n8n→Central exige Bearer token forte e distinto da chave Evolution. Chaves em `/data/options.json`, não entregues ao navegador.
- API de controle protegida pela origem do Ingress e cabeçalho de requisição customizado; a instalação real deve testar comportamento da autenticação do Home Assistant e acessos negados de outras origens.
- Envio manual usa texto validado até 1500 caracteres, ID de tentativa único e destino WhatsApp individual (sem grupos, broadcasts ou LIDs sem resolução validada).
- Resposta HTTP 2xx da Evolution **não** prova entrega: a interface informa somente aceitação do envio.
- Na falha de rede, resultado é incerto. O usuário precisa verificar o WhatsApp antes de fazer outro envio.
- Eventos do n8n não geram fichas para cada mensagem: abrir pendência exige `handoffRequested: true`.
- Ainda não há política automática de exclusão/expiração. **Não introduzir exclusão automática de dados** sem homologação da retenção e backup.

## Interface — avaliação

- Layout de uma coluna no celular, cartões com resumo curto, botões de toque, filtros recolhidos e detalhes separados.
- Ordenação por atividade recente; pendências não são escondidas por limite de histórico.
- Ações `Assumir`, `Resolver`, `Reabrir` e `Enviar` são explícitas; enviar muda para estado humano, **não** resolve.
- O painel não implementa chat completo; mantém somente última mensagem e último envio manual.
- Não foi testado em telefone real via Ingress. A homologação visual deve ocorrer **antes** de permitir uso de clientes.

## Persistência

- SQLite salvo em `/data/central.sqlite3`, com chave por remetente e índice primário de requisições de envio.
- Deduplicação de evento por `last_message_id` **somente contra a última mensagem da conversa**. Eventos históricos fora de ordem e alta concorrência exigem testes adicionais.
- Backups requerem parada/backup consistente; `backup: cold` configurado, restauração ainda não testada.
- Sem limpeza automática. Histórico completo fica no WhatsApp, não no banco do painel.

## Bloqueios ainda não concluídos para USO REAL

1. **Integração n8n v1.4 → Central:** não existe conector ativo, nem consulta aos estados para suspender respostas quando humano assumir. **Não usar o painel para assumir clientes reais enquanto a v1.4 puder responder automaticamente.**
2. **Ligação de rede:** a URL para o n8n alcançar a Central e a URL da Evolution a partir do add-on precisam ser confirmadas no Raspberry.
3. **Homologação visual e operacional:** instalar isoladamente após autorização, verificar a UI no celular e testar enviar para contato autorizado, sem perder mensagens.
4. **Segurança e privacidade:** verificar retenção/backups/restauração antes de uso continuado, reavaliar anti-loop, tratamento de erros e monitoramento.
5. **CI global:** confirmar resultado de todos os checks atuais do PR antes de liberar o merge.

## Conclusão

**Pronto para revisão do PR e preparação de instalação isolada**, não pronto ainda para publicar a v1.5 como atendimento comercial completo. Não fazer merge ou instalar automaticamente a partir desta revisão. Ver [INSTALACAO.md](INSTALACAO.md).

## Complemento — Proteção n8n → Central (13/11/2026)

Implementação adicionada na **branch do PR #5**, sem instalação e sem alterar a v1.4:

1. `POST /bridge/decision`: consulta autenticada do estado. `human` e `pending` não autorizam resposta automática; entradas inválidas recebem erro, não permissão.
2. `POST /bridge/send-auto`: envio automático pelo backend, autenticado com o segredo de integração, restrito a `auto_test_sender` e deduplicado pelo par destinatário/messageId.
3. A trava compartilhada protege a decisão e a chamada Evolution contra o comando **Assumir** durante o envio, tornando o ordenamento explícito. A opção **Enviar manualmente** muda a conversa para `human` antes de chamar a Evolution.
4. O workflow importável [n8n/central-guard-lab.json](n8n/central-guard-lab.json) é **somente manual e diagnóstico**, sem envio de mensagens ou webhook publicado. O HTTP Request deve usar credencial Header Auth armazenada no n8n; nunca salvar segredos no JSON.
5. Testes unitários adicionais verificam estados `none/pending/human/done`, destinatários inválidos, whitelist de teste, bloqueio sem chamada externa e idempotência de envio.

**Limites:** integração real com a instância n8n ainda não realizada. A v1.4 não usa a nova rota; somente a futura versão migrada terá bloqueio efetivo. Em `pending`, a escolha explícita do cliente entre esperar e continuar com robô, além do anti-loop e da interpretação IA, permanecem pendentes. Não afirmar atendimento comercial concluído.
