# WhatsApp automático — estado observado do n8n (19/11/2026)

**Proveniência:** relatório técnico de validação V2 fornecido pelo proprietário após a leitura via MCP, **não uma exportação de JSON para o Git**. **Escopo: somente leitura.** Este documento é uma fotografia datada, não uma afirmação de estado corrente permanente.

## 1. Onde estão os artefatos hoje

- **Instância n8n** do Home Assistant hospeda os workflows efetivos e seus históricos.
- **GitHub `mmcromero/hassio-addons`** contém a Evolution API, a Central Umdoislab, JSONs históricos de atendimento e documentação da infraestrutura, porém **a versão atual do roteador de 39 nós ainda não foi exportada e versionada aqui**.
- Inventário comum: [N8N-HOME-ASSISTANT-INVENTARIO.md](N8N-HOME-ASSISTANT-INVENTARIO.md). Conexão do ChatGPT: [N8N-CHATGPT-MCP-V2-2026-11-19.md](N8N-CHATGPT-MCP-V2-2026-11-19.md).
- **Projeto de negócio**: atendimento e automações WhatsApp/Umdoislab; fluxos de Avisaqui e Fábrica de Software são dependências/consumidores distintos e não devem ter a governança deles substituída por este documento.

## 2. Inventário observado

Total: **14 workflows**; **3 ativos**, **11 inativos**, **4 habilitados para MCP**, **10 indisponíveis por MCP**.

**Ativos identificados no relatório:**
- `[Gateway] WhatsApp — Roteador Central` — ID `Co6h1m14rj2a1dyE`, **39 nós**, um gatilho, atualizado em 18/11/2026 às 18:55:56 UTC.
- `[Engenharia] Fábrica de Software Autônoma` — ID `yzSNydZhgxRlQbJ9`.
- `[Comercial] UmDois Lab — Autoatendimento` — ID `8fehbgwcaJmTwCYx`, **11 nós**.
- `Orquestrador Avisaqui` — ID `JuZvTwemmLlWGLpQ`, **inativo**, mas disponível via MCP.
- `Umdoislab v1.7 — WhatsApp Gemini` — ID `xFyLEySFh6IC7MfK`: consulta detalhada negada, `Workflow is not available in MCP`.

O roteador central inclui integrações observadas por leitura de nós: Evolution API/WhatsApp, Gemini, validação e processamento, Avisaqui, HTTP, GitHub e execução de outros workflows.

## 3. Histórico e falhas: não equivalem a problemas ativos

- A consulta inicial do Roteador Central retornou **62 execuções**. Cinco execuções recentes (`#2302`, `#2301`, `#2300`, `#2299`, `#2298`) apresentaram `success` no n8n; isso não prova entrega externa.
- Consulta global filtrada por `error, crashed`: **102 execuções históricas**, com primeira página de 30 registros.
- `#2289`, Roteador Central: nó `Avisaqui — Executar Compilacao e Publicacao Real`; erro de conexão `The connection was aborted, perhaps the server is offline`. Causa não confirmada.
- `#2281`, Fábrica de Software: `GitHub — Publicar Convocacao Tarefa`; referência a `Avisaqui — validar dono e status` não executado naquele caminho. Validar expressões/dependências antes de corrigir.
- `#2271`, Orquestrador Avisaqui: `WhatsApp — Notificar Dono`; JSON Body inválido: `Unexpected token '=', "={..." is not valid JSON`. Revisar modo de expressão/corpo JSON; sem correção aplicada.

## 4. Regras de trabalho a partir de agora

1. **Primeiro** auditar Roteador Central em somente leitura: gatilhos/rotas, idempotência e loop, permissões por origem, segredos expostos, fronteiras pessoal/comercial, dependências de serviços externos e recuperação.
2. Registrar documento e diagrama da arquitetura real, junto com **exportação sanitizada** do JSON integral quando autorizada e tecnicamente possível. Não tratar arquivos v1.x como se fossem o roteador vigente.
3. Preservar a operação comercial e a automação residencial. Não executar, editar, ativar/desativar, publicar ou enviar WhatsApp para testar sem autorização específica.
4. Para mudanças futuras: branch e PR, diff, teste proporcional, plano de reversão, registro de workflow ID e evidências de execução (sem dados de clientes).
5. Conservar responsáveis e normas do Avisaqui e da Fábrica de Software nos respectivos projetos; o roteador não autoriza publicação automatizada nesses projetos.
6. Nunca versionar tokens MCP, chaves de túnel/API, segredos Evolution/Gemini, sessões, contatos de clientes ou exportações com dados pessoais.

**Pendentes:** export/snapshot real sanitizado; inventário completo dos 14 workflows com versão e trigger; comprovação de persistência e restauração do n8n; relatório de auditoria do Roteador Central; decisão se o núcleo futuro de workflows WhatsApp merece repositório privado separado. **Nenhum desses itens foi declarado concluído.**
