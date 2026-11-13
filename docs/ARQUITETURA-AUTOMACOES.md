# Arquitetura proposta — automações leves e processamento externo

**Decisão registrada:** 2026-11-13  
**Estado:** diretriz aprovada conceitualmente; **sem implementação de serviço externo**.

## Objetivo e contexto

Preservar as funções essenciais do Home Assistant OS no Raspberry Pi 4 de 8 GB e usar o computador para tarefas que consumam mais CPU/RAM quando houver necessidade. O Raspberry hospeda Home Assistant, n8n na porta 5678, Jellyfin e outros serviços. O Jellyfin costuma operar em Direct Play; o uso da casa é leve. Não há medição recente de recursos; nenhuma capacidade deve ser garantida por estimativa.

O WhatsApp de negócio da Umdoislab deve ser integrado via Evolution API e n8n para automações de baixo volume inicial. O usuário pode enviar mais comandos do que receber mensagens de clientes. O fluxo não deve virar uma plataforma de disparos em massa.

## Fluxo lógico previsto

```text
WhatsApp (conta empresarial)
       |
       v
Evolution API (add-on no Raspberry)
       |
       v
n8n principal (Raspberry, porta 5678)
       |                                \
       +--> tarefas leves                 +--> tarefa pesada [FUTURO]
       |      |                                  |
       |      +--> Home Assistant                 v
       |           (luzes, avisos)          Serviço no computador
       |                                      (imagens, vídeos, IA local)
       +<---------- resultado/callback ---------+
       |
       +--> resposta controlada via Evolution API
```

Um evento do GitHub (push, commit ou workflow) pode chamar n8n principal, que solicita ao Home Assistant acender uma luz ou emitir notificação. Esse fluxo é **exemplo futuro**, não instalado.

## Etapas e escolhas

| Caminho | Estado | Motivo |
| --- | --- | --- |
| Um n8n principal no Raspberry | Atual | Simplicidade, automações locais, sempre disponível quando HA estiver disponível |
| Serviço de processamento dedicado no computador, acionado por HTTP autenticado | Preferido para evolução, não implementado | Descarrega mídia e IA sem duplicar administração do n8n |
| Segundo n8n independente no computador | Alternativa futura | Útil só se houver muitos workflows locais e necessidade de editor/agenda separados |
| Workers distribuídos de n8n com Redis e banco compartilhado | Não escolhido | Aumenta complexidade operacional sem demanda justificada |

**Não mover processamento pesado para o computador como pré-requisito da Evolution API**. Só decidir após medir uma tarefa real.

## Regras mínimas antes de integrar comandos

- **Autorização**: lista de usuários/remetentes permitidos e controle de permissões por ação. A origem de mensagem sozinha não prova autorização suficiente.
- **Anti-loop**: distinguir mensagens recebidas das mensagens geradas pela própria automação; limitar encadeamento e respostas.
- **Limites**: aplicar cotas, controle de frequência, filas e idempotência de eventos.
- **Segurança de rede**: usar autenticação e, conforme a topologia, TLS/rede privada entre n8n e computador; não expor webhook de execução sensível à Internet sem proteção.
- **Queda do computador**: tarefas pesadas ficam pendentes em fila durável ou falham de forma controlada; nunca bloquear automações da casa aguardando o PC. Definir expiração e retentativas com limites.
- **Resposta assíncrona**: tarefas longas devem retornar identificador e fazer callback/consulta posterior, evitando timeouts HTTP.
- **Dados**: não enviar dados de clientes sem necessidade; aplicar proteção à mídia e retenção adequada.
- **WhatsApp**: a Evolution API é integração não oficial; há risco de restrições/bloqueios da conta e devem ser evitados disparos não solicitados. Avaliar alternativas oficiais se o uso comercial exigir garantias.
- **Operação**: manter logs sem segredos, métricas CPU/RAM e recursos do Pi; priorizar a casa.

## Critérios para evoluir

Somente avaliar instalação no PC quando houver demanda concreta (ex.: tratamento frequente de imagens/vídeos, IA local, atrasos ou picos medidos) e o computador for capaz de processá-la. Medir latência, consumo de recursos e disponibilidade antes de escolher tecnologia.

## Pendências / decisões futuras

1. Homologar a Evolution API e seu webhook com n8n (ver [CONTINUIDADE.md](CONTINUIDADE.md)).
2. Escolher primeiro workflow útil e de baixo risco, como notificação doméstica de evento GitHub, sem ações físicas irreversíveis.
3. Definir os comandos do WhatsApp e limites de autorização.
4. Só então desenhar protocolo e fila durável para tarefas pesadas e determinar o papel do computador.
5. Registrar implementação e evidências em PRs; atualizar estes documentos quando decisões mudarem.


## Atualização operacional — Umdoislab, 13/11/2026

A diretriz de manter **um n8n no Raspberry** continua válida. Após a elaboração deste documento, o proprietário confirmou a instalação da Evolution API, o pareamento da instância WhatsApp `umdoislab` e a classificação de mensagem por assunto em produção no n8n 2.47.3 (workflow v1.1, **Success**, quatro nós). A homologação foi relatada pelo proprietário; não é auditoria de carga, persistência ou proteção de dados. Ver [passagem de bastão completa](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md).

**Separação aprovada para a próxima evolução:**

- **Comercial, regras:** workflow v1.1 continua a entrada validada. Preparar respostas sugeridas para revisão antes de qualquer envio automático.
- **Comercial, IA:** Gemini em workflow separado, primeiro com dados sintéticos. Adotar uma única entrada WhatsApp com roteamento explícito para evitar duas respostas ao mesmo cliente. A API do Gemini ainda não está configurada.
- **Pessoal, residência:** laboratório de comandos `/casa` fornecido em JSON, **somente simulador**; sem conexão real ao Home Assistant. `fromMe` sozinho não autentica/autorizada comandos domésticos.

**Pendências:** exportar JSON efetivo da v1.1 antes de alterar regras; revisar segurança, idempotência, anti-loop, privacidade, permissões e backups antes de habilitar envio automático ou ações físicas. Nenhum serviço externo, segundo n8n ou IA local no computador foi implementado nesta atualização.
