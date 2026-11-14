# UMDOISLAB — Estado operacional e passagem de bastão atual

**Consolidação:** 14/11/2026 (BRT)  
**Prioridade:** este arquivo prevalece sobre descrições históricas de v1.1, v1.4 e versões de laboratório em documentos antigos.  
**Tipo:** inventário baseado em capturas fornecidas pelo proprietário + código conferido no GitHub. **Não é auditoria direta do Raspberry, n8n ou banco do Home Assistant.**

## 1. Como usar este documento

Leia esta página **antes de desenvolver, atualizar ou orientar operação**. Em seguida leia [PROTOCOLO-DE-CONTINUIDADE](PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md), [CONTINUIDADE](CONTINUIDADE.md), [passagem histórica](PASSAGEM-DE-BASTAO-UMDOISLAB-2026-11-13.md) e [README da Central](../umdoislab-central/README.md). Não trate próximos passos de versões antigas como tarefas vigentes.

**Não confundir:**
- Versão do n8n (aplicativo), versão lógica do *workflow*, nome do arquivo JSON e versão do add-on Central são coisas distintas.
- Um merge no GitHub **não** significa implantação no HA/n8n. Um add-on em execução **não** garante que a imagem instalada corresponde byte a byte à última revisão do repositório.
- Um workflow **Published** confirma publicação na UI; **não** comprova que todos os nós fizeram o esperado numa execução específica.

## 2. Inventário atual

| Componente | Versão / identificação | Evidência e limite |
| --- | --- | --- |
| Host | Raspberry Pi 4 8 GB, Home Assistant OS, ARM64 | Histórico fornecido pelo proprietário; capacidade atual não medida |
| Evolution API — add-on HA | **0.1.0, em execução** | Captura do HA em 14/11/2026; início automático e watchdog ligados |
| Evolution API — aplicação | Imagem fixada no repositório: **evoapicloud/evolution-api:v2.3.7** | Código versionado; tag real em execução não foi inspecionada separadamente |
| Instância WhatsApp | **umdoislab** | Histórico de integração; houve conversa real respondida pelo fluxo |
| Central de Atendimento — add-on HA | **0.3.0, em execução**, Ingress | Captura do HA; confirmado painel com botão **Automação**, gestão de números, contadores e lista de pendências |
| n8n — aplicativo | **2.47.3** | Último registro documental; versão do binário não reconfirmada na UI nesta rodada |
| n8n — workflow operacional | **“Umdoislab v1.6 — WhatsApp Gemini com conversa contextual”**, **Published** | Capturas do n8n; este é o workflow atual, não v1.4 ou v1.5 |
| Workflow JSON no GitHub | `umdoislab-central/n8n/atendimento-v1.5-whatsapp-real.json` | Nome histórico do arquivo; README informa conteúdo lógico **v1.6**. Não renomear/importar/publicar automaticamente |
| Workflows antigos e LAB | v1.5, LAB v1.5 e anteriores | Existem na lista, mas estão **fora do escopo** do atendimento vigente; não orientar troca por versões antigas |
| “Atendimento 1.2 Lab” duplicado no HA | **Removido pelo proprietário** | Informação do proprietário; não inventariar como dois add-ons ainda instalados |

**Referência operacional única:** Evolution API + Central HA **0.3.0** + workflow **n8n v1.6** publicado. O n8n 2.47.3 é versão de aplicativo distinta do workflow.

## 3. Arquitetura em uso: evidências

A captura do editor v1.6 mostra a sequência (rótulos da própria UI):

```text
WhatsApp recebido — Evolution (webhook)
  → Validar remetente e classificar
  → Consultar e registrar na Central
  → Validar ação antes de resposta
  → Ação exige Gemini?
      → Consultar contexto na Central → Gemini — conversar ... → Validar resposta natural do Gemini
      → ou Resposta protocolar sem Gemini
  → Existe resposta autorizada?
      → Enviar apenas pela Central
      → ou Silêncio ou mensagem repetida
```

**Limite:** a captura comprova a presença dos nós e suas ligações, não o payload exato executado ou o processamento de um encaminhamento. O webhook antigo `/webhook/umdoislab-atendimento-inicial` documentado para v1.1 **não deve ser usado como referência atual**. O README da Central registra para v1.6 o caminho `/webhook/umdoislab-v15`; confirmar a URL atual no workflow/Manager antes de qualquer intervenção.

O código da Central tem endpoints autenticados `/bridge/inbound`, `/bridge/context`, `/bridge/decision`, `/bridge/send-auto` e controles internos do painel. `send-auto` aplica política de contato, bloqueio humano, idempotência e proteção contra repetição. **Não inferir que um encaminhamento foi registrado só porque o Gemini escreveu “encaminhei”.**

## 4. Observações dos testes reais (não confundir hipótese e prova)

- Conversa mostrada pelo proprietário: a v1.6 manteve contexto sobre um produto após intervalo de minutos; foi perguntado preço; o robô declarou não consultar preço/estoque e ofereceu encaminhar a pessoa.
- Após o cliente responder “Sim”, a resposta do WhatsApp disse que o encaminhamento havia sido feito. **O painel não mostrou uma nova pendência correspondente naquele momento.**
- O painel HA apresentou **1 pendência de “Contato de laboratório”** (assunto produto; mensagem “Quasimoto”), com registro anterior. Isso demonstra leitura de ao menos uma ficha, **não comprova encaminhamento da conversa real**.
- Hipóteses de investigação: ação de handoff não gerada no nó de classificação; parâmetro de handoff não enviado no `/bridge/inbound`; resposta textual do Gemini sem transição de estado; resultado do endpoint não avaliado. **Nenhuma causa foi confirmada.**
- Antes de qualquer alteração, examinar execução específica do n8n v1.6, nó **“Consultar e registrar na Central”** e ação retornada, removendo telefones/tokens de capturas e registros. Jamais declarar encaminhamento confirmado sem aceite verificável da Central.

## 5. Política de contatos e validador — decisão e estado

**Contexto de decisão, para não reiniciar a discussão:** o próprio assistente levantou a preocupação de que dados retornados da Evolution podem não formar um conjunto completo e confiável de contatos individuais. A restrição inicial **“Somente números de teste”** foi sugerida pelo assistente por precaução. O proprietário não pediu que essa restrição se tornasse permanente; diante da insistência, aceitou o desenvolvimento de uma **ferramenta de validação automática** como solução para a incerteza.

**Decisão atual do proprietário (14/11): DOCUMENTAR, NÃO IMPLEMENTAR AGORA.** Não iniciar esse trabalho nem solicitar novos testes manuais para ele neste pacote.

**Comprovado no código 0.3.0:**
- `historical_baseline()` solicita `/chat/findContacts/<instance>` e `/chat/findChats/<instance>`; exige listas, recolhe JIDs numéricos em formato individual e falha em alguns formatos inesperados.
- A Central guarda referência em `known_contacts`, regras em `contact_rules`, modo em `policy_settings` e permite `tests`, `new`, `all`. Exclusões têm precedência.
- A UI mostra **“Histórico consultado: 546 números”** com hora registrada e o modo **“Somente números de teste”** selecionado. Uma etiqueta de contato de teste apareceu na tela. **546 é a contagem da referência construída, não uma certificação dos 546 contatos.**
- O código citado **não** demonstra validação individual completa, confiabilidade da cobertura histórica, relatório de discrepâncias nem prova de existência de conta WhatsApp.

**Ferramenta futura discutida — requisitos funcionais recuperáveis, não uma implementação existente:**
1. Consultar as fontes disponíveis de contatos e chats da Evolution com critérios explícitos de completude, paginação/limites e tratamento de falha.
2. Normalizar identificadores, separar JIDs individuais de grupos, `@lid` e formatos incompatíveis sem inventar conversões.
3. Correlacionar, detectar duplicações/inconsistências, registrar origem e motivo por classificação.
4. Produzir resultado auditável por registro: **confiável para o critério definido / duvidoso / rejeitado**, com motivos; não equiparar formato válido a conta ativa no WhatsApp.
5. Exibir resumo e detalhes na Central, sem expor segredos nem dados de contato em repositório público.
6. Não promover política de contatos automaticamente a partir de consulta parcial ou resultado incerto; testar regras e manter rollback/configuração anterior.
7. Só considerar a implementação completa após teste contra os formatos reais da versão Evolution implantada, sem divulgar dados pessoais.

**Limite de recuperação:** a arquitetura detalhada da discussão anterior não foi localizada integralmente nas fontes consultadas. A lista acima consolida os objetivos e componentes conhecidos; **não alegar que reproduz a especificação original fielmente**. Antes de implementar no futuro, localizar a especificação original ou criar um desenho técnico versionado e revisado, explicitando o que é confirmado e o que é reconstruído. A ausência de detalhe não é autorização para inventar endpoints ou certezas.

**Não confundir com o botão “Consultar histórico”:** a consulta já existe; o **validador confiável e seu relatório** são pendência separada. Não repetir argumentação como se o proprietário tivesse exigido o validador por iniciativa própria.

## 6. Decisões de segurança e operação

- Não mudar agora modo de contatos, workflow v1.6, add-ons ou Evolution. Não fazer deploy, excluir bancos, publicar workflow ou alterar credenciais como parte desta atualização documental.
- O modo **“Somente números de teste”** é estado observado da instalação, **não** decisão de produto definitiva; não transformar incerteza da consulta em bloqueio permanente sem nova análise e decisão.
- Nenhum token, número real, nome de contato, mensagem privada ou credencial nos documentos públicos. O repositório `mmcromero/hassio-addons` é tratado como potencialmente público.
- Não confundir PR #5 integrado à main com instalação; a Central 0.3.0 instalada foi confirmada separadamente por captura.
- Dados de atendimento (SQLite) e sessão WhatsApp são persistentes: intervenções e remoções exigem identificação da instalação exata, plano de backup e autorização.

## 7. Próximos trabalhos, sem autorização de execução neste pacote

**Investigação prioritária, quando solicitada:** identificar por que o cliente recebeu confirmação de encaminhamento mas a nova ficha não apareceu; usar o workflow v1.6 publicado como fonte, não trocar por v1.5.

**Backlog deliberadamente adiado:** validador de contatos da Evolution com classificação auditável e relatório. Não implementar nesta tarefa documental.

**Conhecimento ainda não comprovado:** versão exata do aplicativo n8n instalada agora; completude dos 546 registros; cópia binária instalada do add-on; resultado de execução real do handoff; entrega/ACK de WhatsApp; política de retenção e restauração.

## 8. Regra obrigatória de continuidade — adotada neste projeto

A cada entrega importante, PR, pacote de build, alteração de workflow, publicação ou decisão técnica relevante, atualizar a passagem de bastão **na mesma mudança**, antes de considerar a entrega encerrada. Ver [PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md](PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md).

Não relatar “atualizado na main”, “implantado” ou “homologado” sem evidência separada. Se só houver PR aberto, dizer **documentação preparada no PR, ainda não integrada**.

## 9. Prompt curto para o próximo desenvolvedor

> Trabalhe na Umdoislab em modo /pair, sem Codex ou Work. Antes de agir, leia `docs/ESTADO-ATUAL-UMDOISLAB.md`, `docs/PROTOCOLO-DE-CONTINUIDADE-UMDOISLAB.md`, `docs/CONTINUIDADE.md` e `umdoislab-central/README.md`. Referência observada em 14/11/2026: Evolution API add-on HA 0.1.0 (imagem versionada v2.3.7); Central HA 0.3.0 em execução; n8n workflow **v1.6 publicado** com Gemini contextual e envio somente pela Central; n8n app 2.47.3 é último registro. Existe pendência de handoff dito confirmado pelo bot sem ficha observada. A ferramenta de validação de contatos foi proposta pelo assistente, discutida e adiada expressamente pelo proprietário; documentar sem implementar. Não usar v1.1/v1.4/v1.5 como workflow atual. Não alterar sistemas, dados ou main sem autorização. Toda entrega importante exige atualização da passagem de bastão com evidência real e limites conhecidos.

## 10. Atualização de engenharia — correção proposta de handoff (14/11/2026)

Foi preparada em branch isolada a correção do falso “encaminhei” observado na v1.6. A proposta usa **oferta registrada pela Central após aceite do envio**, confirmação explícita na próxima mensagem e criação de ficha antes da resposta de encaminhamento. O backend bloqueia confirmação inventada por texto do Gemini. **Não implantado:** workflow em produção permanece **v1.6** e Central HA permanece **0.3.0**. Leia [UMDOISLAB-HANDOFF-V17-CORRECAO.md](UMDOISLAB-HANDOFF-V17-CORRECAO.md) para implementação, casos de teste, limites e ordem segura da futura publicação. O validador de contatos continua adiado.
